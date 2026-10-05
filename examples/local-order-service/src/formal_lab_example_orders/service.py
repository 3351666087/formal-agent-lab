"""Local order service: an independent business process (FastAPI + SQLite) implementing order handling.

It shares only the *vocabulary* and the synthetic instance data with the model; the rules are implemented here in
SQL, independently of the IR. The platform reaches it only through the environment adapter (`env.py`).

Fixed business API (per tenant = one environment session; each tenant is its own SQLite file):

  GET  /health                                   process health (project label, pid, start time)
  GET  /t/{tenant}/health                        tenant readiness and revision
  GET  /t/{tenant}/state                         business state as location → value (+ revision, clock)
  POST /t/{tenant}/operations                    execute one operation (stable operation_id, idempotent)
  GET  /t/{tenant}/operations/{operation_id}     what happened to an operation (404 = never received)
  GET  /t/{tenant}/metrics?window=W              business metrics for probes (logical window of W ticks)
  POST /t/{tenant}/admin/reset                   service-side reset to a case instance (SERVICE_RESET)
  GET  /t/{tenant}/admin/export                  business state export;  POST …/admin/import  (STATE_IMPORT)
  POST /t/{tenant}/admin/conditions              operating conditions (slow stations, held responses, crash)
  GET  /t/{tenant}/admin/conditions              the current operating conditions (a read: probes, no writes)
An operation id is bound to the request it was first received with: the same id with the same request returns the
stored answer (`replayed`), with another actor / action / parameters it is refused with 409 OPERATION_ID_CONFLICT.
  DELETE /t/{tenant}                             remove the tenant (session close)

Guarantees (and their limits): every operation runs in one SQLite transaction taken with BEGIN IMMEDIATE; the
operation id is the primary key of the operations table and is checked inside that transaction, so the same id takes
effect at most once — a re-sent id returns the stored answer (`replayed: true`), also when the first attempt is still
in flight (the second waits for the write lock). Updates are conditional on the business preconditions; with
`conflict_policy = REJECT_STALE` they are also conditional on the locations the operation reads not having been
written after the caller's `based_on_revision` (per-field change log). A crash before COMMIT leaves no trace; a crash
after COMMIT leaves the operation recorded — an unanswered call is settled by looking the id up. Not covered: several
service processes sharing one file over a network file system.

    python -m formal_lab_example_orders.service --data ./var/orders --port 8765 --project demo
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import sqlite3
import statistics
import threading
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

from .instance import HORIZON, MAX_STOCK, RESTOCK_QTY, Instance, instance

SERVICE_VERSION = "1.0.0"
TENANT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY, sku TEXT NOT NULL, qty INTEGER NOT NULL, arrive_at INTEGER NOT NULL,
    due INTEGER NOT NULL, proc_time INTEGER NOT NULL, status TEXT NOT NULL, station TEXT,
    remaining INTEGER NOT NULL DEFAULT 0, queued_seq INTEGER NOT NULL DEFAULT 0, done_at INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS inventory (sku TEXT PRIMARY KEY, stock INTEGER NOT NULL CHECK (stock >= 0),
    restocked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS stations (station_id TEXT PRIMARY KEY, order_id TEXT, slow INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS operations (
    operation_id TEXT PRIMARY KEY, seq INTEGER NOT NULL, actor_id TEXT, action TEXT NOT NULL, params TEXT NOT NULL,
    status TEXT NOT NULL, result TEXT NOT NULL, revision_before INTEGER NOT NULL, revision_after INTEGER NOT NULL,
    received_at REAL NOT NULL, committed_at REAL NOT NULL, handling_ms REAL NOT NULL,
    context TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS changes (revision INTEGER NOT NULL, path TEXT NOT NULL, old TEXT, new TEXT,
    actor_id TEXT, operation_id TEXT);
CREATE INDEX IF NOT EXISTS changes_path ON changes (path, revision);
CREATE TABLE IF NOT EXISTS restarts (started_at REAL NOT NULL, downtime_s REAL, last_commit_at REAL);
"""


class Rejected(Exception):
    def __init__(self, reason: str, conflict: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.conflict = conflict


# ---------------------------------------------------------------------------------------------------- storage


class Store:
    """One tenant's SQLite file."""

    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=60, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def meta(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    @staticmethod
    def set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
        conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, json.dumps(value)))


def values(conn: sqlite3.Connection) -> dict[str, Any]:
    """The business state in the shared vocabulary (location → value)."""
    out: dict[str, Any] = {}
    stations = [r["station_id"] for r in conn.execute("SELECT station_id FROM stations ORDER BY station_id")]
    for o in conn.execute("SELECT * FROM orders ORDER BY order_id"):
        oid = o["order_id"]
        out[f"status[{oid}]"] = o["status"]
        out[f"remaining[{oid}]"] = o["remaining"]
        out[f"proc_time[{oid}]"] = o["proc_time"]
        out[f"queued_seq[{oid}]"] = o["queued_seq"]
        out[f"done_at[{oid}]"] = o["done_at"]
        for st in stations:
            out[f"on[{oid},{st}]"] = o["station"] == st
    for i in conn.execute("SELECT * FROM inventory ORDER BY sku"):
        out[f"stock[{i['sku']}]"] = i["stock"]
        out[f"restocked[{i['sku']}]"] = bool(i["restocked"])
    out["next_seq"] = Store.meta(conn, "next_seq", 1)
    out["clock"] = Store.meta(conn, "clock", 0)
    out["tick_parity"] = Store.meta(conn, "tick_parity", False)
    return out


def properties(conn: sqlite3.Connection) -> dict[str, bool]:
    clock = Store.meta(conn, "clock", 0)
    orders = list(conn.execute("SELECT status, due, station FROM orders"))
    per_station: dict[str, int] = {}
    for o in orders:
        if o["station"]:
            per_station[o["station"]] = per_station.get(o["station"], 0) + 1
    return {"all_completed": all(o["status"] == "completed" for o in orders),
            "station_capacity": all(n <= 1 for n in per_station.values()),
            "on_time": all(o["status"] == "completed" or clock <= o["due"] for o in orders)}


# ---------------------------------------------------------------------------------------------------- business rules

PARAMS = {"reserve": ["o"], "enqueue": ["o"], "start": ["o", "st"], "tick": [], "restock": ["s"]}


def reads(conn: sqlite3.Connection, action: str, params: dict[str, Any]) -> list[str]:
    """Location patterns an operation's checks read (for REJECT_STALE); `*` matches one index."""
    if action == "reserve":
        row = conn.execute("SELECT sku FROM orders WHERE order_id = ?", (params["o"],)).fetchone()
        return [f"status[{params['o']}]", f"stock[{row['sku'] if row else '*'}]"]
    if action == "enqueue":
        return [f"status[{params['o']}]", "next_seq"]
    if action == "start":
        return ["status[*]", "queued_seq[*]", f"on[*,{params['st']}]"]
    if action == "tick":
        return ["clock"]
    return [f"stock[{params['s']}]", f"restocked[{params['s']}]"]


def apply_operation(conn: sqlite3.Connection, action: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run the business rules inside the caller's transaction; returns location → new value (only real changes)."""
    before = values(conn)
    if action == "reserve":
        o = conn.execute("SELECT * FROM orders WHERE order_id = ?", (params["o"],)).fetchone()
        if o is None:
            raise Rejected(f"UNKNOWN_ORDER: {params['o']}")
        cur = conn.execute("UPDATE orders SET status = 'reserved' WHERE order_id = ? AND status = 'submitted'",
                           (o["order_id"],))
        if cur.rowcount != 1:
            raise Rejected(f"PRECONDITION_FALSE: order {o['order_id']} is {o['status']}, not submitted")
        cur = conn.execute("UPDATE inventory SET stock = stock - ? WHERE sku = ? AND stock >= ?",
                           (o["qty"], o["sku"], o["qty"]))
        if cur.rowcount != 1:
            raise Rejected(f"PRECONDITION_FALSE: stock of {o['sku']} is below {o['qty']}")
    elif action == "enqueue":
        seq = Store.meta(conn, "next_seq", 1)
        if seq >= 9:
            raise Rejected("PRECONDITION_FALSE: queue sequence exhausted")
        cur = conn.execute("UPDATE orders SET status = 'queued', queued_seq = ? WHERE order_id = ? "
                           "AND status = 'reserved'", (seq, params["o"]))
        if cur.rowcount != 1:
            raise Rejected(f"PRECONDITION_FALSE: order {params['o']} is not reserved")
        Store.set_meta(conn, "next_seq", seq + 1)
    elif action == "start":
        oid, st = params["o"], params["st"]
        station = conn.execute("SELECT * FROM stations WHERE station_id = ?", (st,)).fetchone()
        if station is None:
            raise Rejected(f"UNKNOWN_STATION: {st}")
        head = conn.execute("SELECT order_id FROM orders WHERE status = 'queued' ORDER BY queued_seq LIMIT 1").fetchone()
        if head is None or head["order_id"] != oid:
            raise Rejected(f"PRECONDITION_FALSE: {oid} is not at the head of the queue")
        cur = conn.execute("UPDATE stations SET order_id = ? WHERE station_id = ? AND order_id IS NULL", (oid, st))
        if cur.rowcount != 1:
            raise Rejected(f"PRECONDITION_FALSE: station {st} is busy")
        conn.execute("UPDATE orders SET status = 'processing', station = ?, remaining = proc_time, queued_seq = 0 "
                     "WHERE order_id = ?", (st, oid))
    elif action == "tick":
        clock = Store.meta(conn, "clock", 0)
        if clock >= HORIZON:
            raise Rejected("PRECONDITION_FALSE: horizon reached")
        parity = Store.meta(conn, "tick_parity", False)
        slow = {r["station_id"] for r in conn.execute("SELECT station_id FROM stations WHERE slow = 1")}
        for o in list(conn.execute("SELECT * FROM orders WHERE status = 'processing'")):
            if o["station"] in slow and not parity:
                continue  # a slow station advances only on every other tick
            if o["remaining"] <= 1:
                conn.execute("UPDATE orders SET status = 'completed', remaining = remaining - 1, done_at = ?, "
                             "station = NULL WHERE order_id = ?", (clock + 1, o["order_id"]))
                conn.execute("UPDATE stations SET order_id = NULL WHERE station_id = ?", (o["station"],))
            else:
                conn.execute("UPDATE orders SET remaining = remaining - 1 WHERE order_id = ?", (o["order_id"],))
        conn.execute("UPDATE orders SET status = 'submitted' WHERE status = 'pending' AND arrive_at = ?", (clock + 1,))
        Store.set_meta(conn, "clock", clock + 1)
        Store.set_meta(conn, "tick_parity", not parity)
    elif action == "restock":
        cur = conn.execute("UPDATE inventory SET stock = stock + ?, restocked = 1 WHERE sku = ? AND restocked = 0 "
                           "AND stock + ? <= ?", (RESTOCK_QTY, params["s"], RESTOCK_QTY, MAX_STOCK))
        if cur.rowcount != 1:
            raise Rejected(f"PRECONDITION_FALSE: {params['s']} was already restocked or would exceed {MAX_STOCK}")
    else:
        raise Rejected(f"INVALID_ACTION: unknown action {action!r}")
    return {path: value for path, value in values(conn).items() if before.get(path) != value}


def _matches(pattern: str, path: str) -> bool:
    return re.fullmatch(re.escape(pattern).replace(r"\*", r"[^,\]]+"), path) is not None


def stale(conn: sqlite3.Connection, action: str, params: dict[str, Any], based_on: int) -> dict[str, Any] | None:
    """Locations the operation reads that were written after `based_on` (REJECT_STALE)."""
    patterns = reads(conn, action, params)
    rows = conn.execute("SELECT DISTINCT path, actor_id FROM changes WHERE revision > ?", (based_on,)).fetchall()
    changed = sorted({r["path"] for r in rows if any(_matches(p, r["path"]) for p in patterns)})
    if not changed:
        return None
    writers = sorted({r["actor_id"] for r in rows if r["path"] in changed and r["actor_id"]})
    return {"changed_paths": changed, "writers": writers}


# ---------------------------------------------------------------------------------------------------- reset / import


def reset_tenant(store: Store, inst: Instance, conditions: dict[str, Any] | None = None) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{store.path}{suffix}").unlink(missing_ok=True)
    with store.connect() as conn:
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        slow = set((conditions or inst.service).get("slow_stations", []))
        for o in inst.orders:
            conn.execute("INSERT INTO orders (order_id, sku, qty, arrive_at, due, proc_time, status) VALUES "
                         "(?, ?, ?, ?, ?, ?, ?)", (o.order_id, o.sku, o.qty, o.arrive_at, o.due, o.proc_time,
                                                   "submitted" if o.arrive_at == 0 else "pending"))
        for sku, qty in inst.stock.items():
            conn.execute("INSERT INTO inventory (sku, stock) VALUES (?, ?)", (sku, qty))
        for st in inst.stations:
            conn.execute("INSERT INTO stations (station_id, slow) VALUES (?, ?)", (st, int(st in slow)))
        for key, value in {"revision": 0, "clock": 0, "next_seq": 1, "tick_parity": False, "op_seq": 0,
                           "instance": inst.as_dict(), "conditions": dict(conditions or inst.service),
                           "created_at": time.time(), "clean_shutdown": False, "crashed_at_op": None}.items():
            Store.set_meta(conn, key, value)
        conn.execute("COMMIT")


def export_tenant(conn: sqlite3.Connection) -> dict[str, Any]:
    return {"format": "local-order-service/state@1",
            "meta": {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM meta")},
            "orders": [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY order_id")],
            "inventory": [dict(r) for r in conn.execute("SELECT * FROM inventory ORDER BY sku")],
            "stations": [dict(r) for r in conn.execute("SELECT * FROM stations ORDER BY station_id")],
            "operations": [dict(r) for r in conn.execute("SELECT * FROM operations ORDER BY seq")],
            "changes": [dict(r) for r in conn.execute("SELECT * FROM changes ORDER BY revision, path")]}


def import_tenant(store: Store, state: dict[str, Any]) -> None:
    if state.get("format") != "local-order-service/state@1":
        raise ValueError("not a local-order-service state export")
    store.path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{store.path}{suffix}").unlink(missing_ok=True)
    with store.connect() as conn:
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        for table in ("orders", "inventory", "stations", "operations", "changes"):
            for row in state.get(table, []):
                cols = ", ".join(row)
                conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
        for key, value in state["meta"].items():
            Store.set_meta(conn, key, value)
        conn.execute("COMMIT")


# ---------------------------------------------------------------------------------------------------- app


def create_app(data_dir: Path, *, project: str = "local", write_token: str | None = None) -> Any:
    """`write_token` (phase 4A, A2): when set, every mutating route (operations, admin/*, tenant removal) needs
    `Authorization: Bearer <token>`; reads stay open. The token is the environment adapter's write credential — a
    participant's read / propose channel never holds it, so a direct write from that side is refused here, in a
    separate process, whatever the caller's Python code does."""
    from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
    from fastapi.responses import JSONResponse

    def writer(authorization: str | None = Header(default=None)) -> None:
        if write_token and not hmac.compare_digest((authorization or "").encode(), f"Bearer {write_token}".encode()):
            raise HTTPException(401, "WRITE_CREDENTIAL_REQUIRED: mutating routes need the environment's write token")

    write = [Depends(writer)]

    data_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    locks: dict[str, threading.Lock] = {}

    def store(tenant: str, *, must_exist: bool = True) -> Store:
        if not TENANT.match(tenant):
            raise HTTPException(400, f"invalid tenant id {tenant!r}")
        s = Store(data_dir / f"{tenant}.db")
        if must_exist and not s.path.exists():
            raise HTTPException(404, f"tenant {tenant} does not exist (reset it first)")
        return s

    def tenants() -> list[str]:
        return sorted(p.stem for p in data_dir.glob("*.db"))

    def record_restarts() -> None:
        """Downtime = start of this process − last committed operation, for tenants not shut down cleanly."""
        for t in tenants():
            with Store(data_dir / f"{t}.db").connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if not Store.meta(conn, "clean_shutdown", True):
                    last = conn.execute("SELECT MAX(committed_at) AS t FROM operations").fetchone()["t"]
                    # wall clock across two processes: a small backward clock step (seen under VM load) can make
                    # the raw difference negative; a downtime is never below zero
                    conn.execute("INSERT INTO restarts (started_at, downtime_s, last_commit_at) VALUES (?, ?, ?)",
                                 (started, max(0.0, started - last) if last else None, last))
                Store.set_meta(conn, "clean_shutdown", False)
                conn.execute("COMMIT")

    def mark_clean() -> None:
        for t in tenants():
            with Store(data_dir / f"{t}.db").connect() as conn:
                Store.set_meta(conn, "clean_shutdown", True)

    @asynccontextmanager
    async def lifespan(_app):
        record_restarts()
        yield
        mark_clean()

    app = FastAPI(title="local-order-service", version=SERVICE_VERSION, lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service": "local-order-service", "version": SERVICE_VERSION, "project": project,
                "pid": os.getpid(), "started_at": started, "tenants": len(tenants()),
                "write_auth": bool(write_token)}

    @app.get("/t/{tenant}/health")
    def tenant_health(tenant: str) -> dict[str, Any]:
        with store(tenant).connect() as conn:
            return {"status": "ready", "revision": Store.meta(conn, "revision", 0),
                    "case": Store.meta(conn, "instance", {}).get("case"), "project": project}

    @app.get("/t/{tenant}/state")
    def state(tenant: str) -> dict[str, Any]:
        with store(tenant).connect() as conn:
            conn.execute("BEGIN")
            out = {"revision": Store.meta(conn, "revision", 0), "clock": Store.meta(conn, "clock", 0),
                   "operations": Store.meta(conn, "op_seq", 0), "values": values(conn),
                   "properties": properties(conn)}
            conn.execute("COMMIT")
            return out

    def stored(row: sqlite3.Row) -> dict[str, Any]:
        return {"operation_id": row["operation_id"], "actor_id": row["actor_id"], "action": row["action"],
                "params": json.loads(row["params"]), "status": row["status"], **json.loads(row["result"]),
                "revision_before": row["revision_before"], "revision_after": row["revision_after"],
                "seq": row["seq"], "committed_at": row["committed_at"], "handling_ms": row["handling_ms"],
                "context": json.loads(row["context"])}

    @app.get("/t/{tenant}/operations/{operation_id}")
    def get_operation(tenant: str, operation_id: str) -> dict[str, Any]:
        with store(tenant).connect() as conn:
            row = conn.execute("SELECT * FROM operations WHERE operation_id = ?", (operation_id,)).fetchone()
            if row is None:
                raise HTTPException(404, f"operation {operation_id} was never received")
            return stored(row)

    @app.post("/t/{tenant}/operations", dependencies=write)
    def post_operation(tenant: str, body: dict[str, Any] = Body(...)) -> JSONResponse:
        t0 = time.time()
        op_id = str(body.get("operation_id") or "")
        action = str(body.get("action") or "")
        params = dict(body.get("params") or {})
        actor = body.get("actor_id")
        if not op_id:
            raise HTTPException(400, "operation_id is required")
        s = store(tenant)
        lock = locks.setdefault(tenant, threading.Lock())
        with lock, s.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM operations WHERE operation_id = ?", (op_id,)).fetchone()
            if row is not None:
                conn.execute("COMMIT")
                if (row["actor_id"], row["action"], json.loads(row["params"])) != (actor, action, params):
                    # the id is bound to the request it was first received with: another request is a conflict,
                    # never an answer for the first one (phase 3A, G2)
                    return JSONResponse(status_code=409, content={
                        "error": "OPERATION_ID_CONFLICT", "operation_id": op_id,
                        "recorded": {"actor_id": row["actor_id"], "action": row["action"],
                                     "params": json.loads(row["params"])},
                        "requested": {"actor_id": actor, "action": action, "params": params}})
                return JSONResponse({**stored(row), "replayed": True})
            revision = Store.meta(conn, "revision", 0)
            seq = Store.meta(conn, "op_seq", 0) + 1
            conditions = Store.meta(conn, "conditions", {})
            conn.execute("SAVEPOINT op")
            status, result = "APPLIED", {}
            try:
                if action not in PARAMS or sorted(params) != sorted(PARAMS[action]):
                    raise Rejected(f"INVALID_ACTION: {action}({', '.join(sorted(params))})")
                if body.get("conflict_policy") == "REJECT_STALE" and body.get("based_on_revision") is not None \
                        and int(body["based_on_revision"]) < revision:
                    found = stale(conn, action, params, int(body["based_on_revision"]))
                    if found is not None:
                        raise Rejected(f"STALE_REVISION: {len(found['changed_paths'])} location(s) it depends on "
                                       f"changed since revision {body['based_on_revision']}", conflict=found)
                if body.get("expected_revision") is not None:  # phase 4A: the revision the send was verified on,
                    expected = int(body["expected_revision"])  # checked here, inside the write's own transaction
                    if body.get("version_policy", "EXACT") == "LOCATIONS":
                        found = stale(conn, action, params, expected) if expected < revision else None
                        if found is not None:
                            raise Rejected(f"STALE_REVISION: {len(found['changed_paths'])} location(s) it depends on "
                                           f"changed since the verified revision {expected}",
                                           conflict={**found, "expected_revision": expected})
                    elif revision != expected:
                        changes = conn.execute("SELECT DISTINCT path, actor_id FROM changes WHERE revision > ?",
                                               (expected,)).fetchall()
                        raise Rejected(f"STALE_REVISION: verified at revision {expected}, the service is at {revision}",
                                       conflict={"changed_paths": sorted({r["path"] for r in changes}),
                                                 "writers": sorted({r["actor_id"] for r in changes if r["actor_id"]}),
                                                 "expected_revision": expected})
                writes = apply_operation(conn, action, params)
                for path, new in writes.items():
                    conn.execute("INSERT INTO changes (revision, path, old, new, actor_id, operation_id) VALUES "
                                 "(?, ?, NULL, ?, ?, ?)", (revision + 1, path, json.dumps(new), actor, op_id))
                Store.set_meta(conn, "revision", revision + 1)
                conn.execute("RELEASE op")
                result = {"written_paths": sorted(writes), "written": writes, "properties": properties(conn)}
            except Rejected as exc:
                conn.execute("ROLLBACK TO op")
                conn.execute("RELEASE op")
                status = "REJECTED"
                result = {"reason": exc.reason, "properties": properties(conn)}
                if exc.conflict:
                    result["conflict"] = {**exc.conflict, "based_on_revision": body.get("based_on_revision"),
                                          "current_revision": revision}
            after = Store.meta(conn, "revision", 0)
            now = time.time()
            Store.set_meta(conn, "op_seq", seq)
            context = {k: body.get(k) for k in ("step_id", "proposal_id", "turn") if body.get(k) is not None}
            conn.execute("INSERT INTO operations (operation_id, seq, actor_id, action, params, status, result, "
                         "revision_before, revision_after, received_at, committed_at, handling_ms, context) VALUES "
                         "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (op_id, seq, actor, action, json.dumps(params), status, json.dumps(result), revision, after,
                          t0, now, (now - t0) * 1000, json.dumps(context)))
            crash = conditions.get("crash_after_op") == seq and Store.meta(conn, "crashed_at_op") is None
            if crash:
                Store.set_meta(conn, "crashed_at_op", seq)
            conn.execute("COMMIT")
            answer = {**stored(conn.execute("SELECT * FROM operations WHERE operation_id = ?", (op_id,)).fetchone()),
                      "replayed": False}
        if crash:
            os._exit(3)  # committed, never answered: the process dies (the supervisor restarts it)
        hold = int(conditions.get("hold_after_commit_ms") or 0)
        every = int(conditions.get("hold_every") or 0)
        if hold and every and seq % every == 0:
            time.sleep(hold / 1000)  # committed, answered too late for the caller
        return JSONResponse(answer)

    @app.get("/t/{tenant}/metrics")
    def metrics(tenant: str, window: int = Query(4, ge=1, le=HORIZON)) -> dict[str, Any]:
        with store(tenant).connect() as conn:
            conn.execute("BEGIN")
            clock = Store.meta(conn, "clock", 0)
            orders = [dict(r) for r in conn.execute("SELECT * FROM orders")]
            arrived = [o for o in orders if o["status"] != "pending"]
            done = [o for o in orders if o["status"] == "completed"]
            recent = [o for o in done if clock - window < o["done_at"] <= clock]
            ops = [r["handling_ms"] for r in conn.execute(
                "SELECT handling_ms FROM operations ORDER BY seq DESC LIMIT ?", (window * 4,))]
            restarts = [dict(r) for r in conn.execute("SELECT * FROM restarts ORDER BY started_at")]
            conn.execute("COMMIT")
        return {
            "clock": clock, "window": {"kind": "LOGICAL_STEPS", "size": window, "start": max(0, clock - window),
                                       "end": clock},
            "throughput": len(recent) / window,
            "completion_rate": (len(done) / len(arrived)) if arrived else None,
            "queue_length": sum(1 for o in orders if o["status"] == "queued"),
            "backlog": sum(1 for o in orders if o["status"] in ("submitted", "reserved", "queued")),
            "latency_ticks": statistics.mean(o["done_at"] - o["arrive_at"] for o in recent) if recent else None,
            "op_latency_ms_p50": statistics.median(ops) if ops else None,
            "restarts": len(restarts),
            "recovery_seconds": restarts[-1]["downtime_s"] if restarts else None,
        }

    @app.post("/t/{tenant}/admin/reset", dependencies=write)
    def reset(tenant: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        s = store(tenant, must_exist=False)
        inst = Instance.from_dict(body["instance"]) if body.get("instance") else \
            instance(body.get("case", "normal"), int(body.get("seed", 0)))
        with locks.setdefault(tenant, threading.Lock()):
            reset_tenant(s, inst, body.get("conditions"))
        return state(tenant)

    @app.get("/t/{tenant}/admin/export")
    def export(tenant: str) -> dict[str, Any]:
        with store(tenant).connect() as conn:
            conn.execute("BEGIN")
            out = export_tenant(conn)
            conn.execute("COMMIT")
            return out

    @app.post("/t/{tenant}/admin/import", dependencies=write)
    def import_(tenant: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        with locks.setdefault(tenant, threading.Lock()):
            try:
                import_tenant(store(tenant, must_exist=False), body)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        return state(tenant)

    @app.get("/t/{tenant}/admin/conditions")
    def current_conditions(tenant: str) -> dict[str, Any]:
        with store(tenant).connect() as conn:
            return Store.meta(conn, "conditions", {})

    @app.post("/t/{tenant}/admin/conditions", dependencies=write)
    def conditions(tenant: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        with store(tenant).connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = {**Store.meta(conn, "conditions", {}), **body}
            Store.set_meta(conn, "conditions", current)
            conn.execute("UPDATE stations SET slow = 0")
            for st in current.get("slow_stations", []):
                conn.execute("UPDATE stations SET slow = 1 WHERE station_id = ?", (st,))
            conn.execute("COMMIT")
        return current

    @app.delete("/t/{tenant}", dependencies=write)
    def close(tenant: str) -> dict[str, Any]:
        s = store(tenant, must_exist=False)
        for suffix in ("", "-wal", "-shm"):
            Path(f"{s.path}{suffix}").unlink(missing_ok=True)
        return {"tenant": tenant, "closed": True}

    return app


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    ap = argparse.ArgumentParser(description="local order service (synthetic data)")
    ap.add_argument("--data", default=os.environ.get("ORDERS_DATA", "./var/orders"))
    ap.add_argument("--host", default=os.environ.get("ORDERS_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("ORDERS_PORT", "8765")))
    ap.add_argument("--project", default=os.environ.get("ORDERS_PROJECT", "local"))
    ap.add_argument("--write-token-file", default=os.environ.get("ORDERS_WRITE_TOKEN_FILE"),
                    help="file holding the environment adapter's write credential (mutating routes need it)")
    args = ap.parse_args(argv)
    token = Path(args.write_token_file).read_text().strip() if args.write_token_file else None
    uvicorn.run(create_app(Path(args.data), project=args.project, write_token=token), host=args.host, port=args.port,
                log_level="warning", timeout_graceful_shutdown=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
