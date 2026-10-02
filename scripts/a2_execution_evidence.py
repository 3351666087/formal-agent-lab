"""A2 evidence: authoritative execution basis, conditional writes and the participant boundary, reproduced against a
real order-service process (secure writes) through the real kernel send path.

Every write count below is read from the service's own operation records (`/admin/export`), never inferred from the
kernel's answer. Sections:

  service    — the write credential: refused without / with a wrong one, reads open, loopback only, never in argv;
  basis      — receipt at 5 vs service at 7 → 0 writes; state change after the check → the conditional write refuses;
               a legal send at the same revision applies once; same id same request → the stored answer, other
               parameters → conflict; env / session / turn / version / actor mismatches → refused with the field named;
               unknown current revision → nothing sent;
  recovery   — a lost send re-sent after the state moved is checked against the fresh basis (refused, or re-issued and
               applied once); two workers sharing a ledger send once; a run stopped and resumed in a fresh component
               set keeps building fresh contexts;
  projection — two LLM participants through the real strategy factory, the real OpenAI-compatible client and a
               loopback protocol test service (not a model): what left each planner, the call records, the checkpoints,
               the operator export and the participant download (actual serialization, read back offline with
               `fal replay verify`) are searched for the withheld family and the test credentials;
  warehouse  — the pure-data warehouse (receiver + picker with views, capacity gate, round-robin and joint batch):
               every send's basis is SERIALIZED and the picker's download never shows the docks.

Reports through scripts/check_result.py and writes $FAL_EVIDENCE_DIR/a2-execution-basis.json.
"""

from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
OUT = EV / "a2-execution-basis.json"
for _k in ("NO_PROXY", "no_proxy"):  # loopback never through a proxy from the environment
    os.environ[_k] = ",".join(x for x in (os.environ.get(_k), "127.0.0.1,localhost,::1") if x)

import httpx  # noqa: E402
from formal_lab_contracts import (  # noqa: E402
    BudgetUsage,
    ExecutionPhase,
    OperationRecord,
    OperationState,
    OperationTransition,
    ScenarioManifest,
    utcnow,
)
from formal_lab_contracts.errors import Conflict, ResultUnknown  # noqa: E402
from formal_lab_domain_broker import (  # noqa: E402
    CheckBasis,
    HmacSigner,
    KeyStore,
    ReceiptStore,
    issue_for_context,
)
from formal_lab_example_orders.lifecycle import ServiceManager  # noqa: E402
from formal_lab_example_orders.model import model_package  # noqa: E402
from formal_lab_example_orders.scenarios import scenario  # noqa: E402
from formal_lab_runtime import default_registry, make_manifest, resume_local, run_local  # noqa: E402
from formal_lab_runtime.coordination import Coordinator, InMemoryLedger, request_digest  # noqa: E402
from formal_lab_runtime.engine import (  # noqa: E402
    RuntimeServices,
    _send_hook,
    apply_step,
    open_components,
    plan_step,
    start_run,
    turn_id,
)
from formal_lab_runtime.execution_context import build_context  # noqa: E402

BASIS = {"query_kind": "ACTION_PRECONDITION", "property_id": None, "verdict": "HOLDS", "scope": "MODEL_INTERNAL",
         "backend": "formal-lab.verifier.z3-bmc@1.1.0", "bound": {}}
ISSUER = {"plugin_id": "formal-lab.broker.receipt-issuer", "version": "1.0.0"}
BROKER = {"plugin_id": "formal-lab.broker.receipt-gate", "version": "1.0.0"}


class World:
    """One secure order service plus the key material, receipt files and helpers of this evidence run."""

    def __init__(self, work: Path):
        self.work = work
        self.svc = ServiceManager(work / "svc", project="a2-evidence", secure_writes=True).start()
        self.svc.ready()
        self.keys = work / "keys.json"
        self.keys.write_text(json.dumps({"issuer-1": os.urandom(24).hex()}))
        self.signer = HmacSigner(KeyStore({k: bytes.fromhex(v) for k, v in json.loads(self.keys.read_text()).items()}),
                                 "issuer-1")
        self.reg = default_registry()
        self.pkg = model_package()

    @property
    def token(self) -> str:
        return self.svc.write_token_file.read_text().strip()

    def export(self, tenant: str) -> dict[str, Any]:
        return httpx.get(f"{self.svc.endpoint}/t/{tenant}/admin/export", timeout=10).json()

    def writes(self, tenant: str, actor: str = "handler") -> list[dict[str, Any]]:
        """Business writes of an actor, from the service's own operation records."""
        return [o for o in self.export(tenant)["operations"] if o["actor_id"] == actor and o["status"] == "APPLIED"]

    def ops(self, tenant: str, actor: str = "handler") -> list[dict[str, Any]]:
        return [o for o in self.export(tenant)["operations"] if o["actor_id"] == actor]

    def revision(self, tenant: str) -> int:
        return int(httpx.get(f"{self.svc.endpoint}/t/{tenant}/health", timeout=10).json()["revision"])

    def other_writer(self, tenant: str, n: int) -> None:
        for _ in range(n):
            r = httpx.post(f"{self.svc.endpoint}/t/{tenant}/operations", headers=self.svc.write_headers(), timeout=10,
                           json={"operation_id": f"other-{uuid.uuid4().hex[:10]}", "actor_id": "other-writer",
                                 "action": "tick", "params": {}})
            assert r.status_code == 200 and r.json()["status"] == "APPLIED", r.text

    def manifest(self, tenant: str, gates: list[dict[str, Any]], run_id: str, receipts: Path, **kw: Any):
        cfgs = {"issuer": {"keystore_path": str(self.keys), "receipts_path": str(receipts), "basis": BASIS},
                "broker": {"keystore_path": str(self.keys), "receipts_path": str(receipts)}}
        specs = [{"plugin": ISSUER if g == "issuer" else BROKER, "config": cfgs[g]} for g in gates]
        base = scenario("normal", endpoint=self.svc.endpoint, tenant=tenant,
                        env_extra={"write_token_file": str(self.svc.write_token_file), **kw.pop("env_extra", {})},
                        **kw)
        sc = ScenarioManifest.model_validate({**base.model_dump(mode="json"), "execution_gates": specs})
        return make_manifest(run_id=run_id, project_id="a2", scenario=sc, package=self.pkg, registry=self.reg,
                             config={"initial_check_horizon": 0})

    def close(self) -> None:
        self.svc.close()


def _record(op_id: str, run_id: str, step: int, proposal) -> OperationRecord:
    return OperationRecord(operation_id=op_id, run_id=run_id, step=step, actor_id=proposal.actor_id,
                           state=OperationState.PREPARED, proposal_id=proposal.proposal_id, action=proposal.action,
                           based_on_revision=proposal.based_on_revision, request_digest=request_digest(proposal),
                           transitions=[OperationTransition(state=OperationState.PREPARED, at=utcnow(),
                                                            reason="evidence", effect="NONE")])


def _issue(w: World, receipts: Path, context) -> None:
    receipt = issue_for_context(context, check_basis=CheckBasis(**BASIS), guarantee_scope="action precondition",
                                signer=w.signer, ttl_seconds=600)
    ReceiptStore(receipts).put(context.request_digest, receipt)


def _reasons(record: OperationRecord) -> list[str]:
    return [f"{d.gate.plugin_id}: {d.reason}" for d in record.decisions if str(d.verdict) == "DENY"]


# ---------------------------------------------------------------------------------------------- service
def service_section(w: World) -> dict[str, Any]:
    tenant = "a2-auth"
    m = w.manifest(tenant, [], "run_a2_auth", w.work / "unused.json")
    rc = open_components(m, w.pkg, w.reg)
    start_run(rc)
    body = {"operation_id": "anon-1", "actor_id": "handler", "action": "tick", "params": {}}
    url = f"{w.svc.endpoint}/t/{tenant}/operations"
    anon = httpx.post(url, json=body, timeout=10).status_code
    wrong = httpx.post(url, json=body, headers={"Authorization": "Bearer not-the-token"}, timeout=10).status_code
    reset = httpx.post(f"{w.svc.endpoint}/t/{tenant}/admin/reset", json={}, timeout=10).status_code
    read = httpx.get(f"{w.svc.endpoint}/t/{tenant}/state", timeout=10).status_code
    cmdline = Path(f"/proc/{w.svc._proc.pid}/cmdline").read_bytes().replace(b"\0", b" ").decode() \
        if w.svc._proc is not None and Path(f"/proc/{w.svc._proc.pid}/cmdline").exists() else ""
    mode = oct(w.svc.write_token_file.stat().st_mode & 0o777)
    other_addrs = []
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5).stdout.split()
        other_addrs = [a for a in out if not a.startswith("127.") and ":" not in a]
    except (OSError, subprocess.SubprocessError):
        pass
    reach = {}
    for addr in other_addrs[:2]:
        s = socket.socket()
        s.settimeout(1.0)
        try:
            s.connect((addr, w.svc.port))
            reach[addr] = "CONNECTED"
        except OSError as exc:
            reach[addr] = f"refused ({type(exc).__name__})"
        finally:
            s.close()
    return {"tenant": tenant, "write_without_credential": anon, "write_with_wrong_credential": wrong,
            "admin_reset_without_credential": reset, "read_without_credential": read,
            "operations_recorded_for_refused_writes": len(w.export(tenant)["operations"]),
            "token_file_mode": mode, "token_in_service_argv": bool(cmdline) and w.token in cmdline,
            "token_file_path_in_service_argv": str(w.svc.write_token_file) in cmdline,
            "argv_inspected": bool(cmdline), "listen_host": w.svc.host, "non_loopback_reach": reach,
            "manifest_has_token": w.token in m.model_dump_json(),
            "manifest_has_token_path": str(w.svc.write_token_file) in m.model_dump_json(),
            "health_write_auth": httpx.get(f"{w.svc.endpoint}/health", timeout=10).json().get("write_auth")}


# ---------------------------------------------------------------------------------------------- basis
def stale_receipt_case(w: World) -> dict[str, Any]:
    """Receipt issued when the service was at 5; another writer moves it to 7 before the send."""
    tenant, run_id = "a2-stale", "run_a2_stale"
    receipts = w.work / "stale-receipts.json"
    rc = open_components(w.manifest(tenant, ["broker"], run_id, receipts), w.pkg, w.reg)
    start = start_run(rc)
    w.other_writer(tenant, 5)
    plan = plan_step(rc, start.snapshot, 1, BudgetUsage(), start.carry)
    p = plan.proposal
    op_id = f"{turn_id(run_id, 1, p.actor_id)}:apply"
    checked = build_context(rc, step=1, turn=plan.turn, actor=p.actor_id, record=_record(op_id, run_id, 1, p),
                            proposal=p, phase=ExecutionPhase.FIRST_SEND)
    _issue(w, receipts, checked)
    w.other_writer(tenant, 2)
    before = w.revision(tenant)
    ex = apply_step(rc, start.snapshot, plan, start.carry)
    decision = ex.operation.decisions[-1]
    return {"proposal_revision": p.based_on_revision, "receipt_revision": checked.current_revision,
            "service_revision_at_send": before, "context_current_revision": decision.execution.current_revision,
            "verdict": str(decision.verdict), "reasons": _reasons(ex.operation),
            "operation_state": str(ex.operation.state.value), "service_writes_of_actor": len(w.writes(tenant)),
            "service_operations_of_actor": len(w.ops(tenant)), "service_revision_after": w.revision(tenant)}


def race_case(w: World) -> dict[str, Any]:
    """Issuer + broker check at revision R; a concurrent writer commits between the last check and the write."""
    tenant, run_id = "a2-race", "run_a2_race"
    rc = open_components(w.manifest(tenant, ["issuer", "broker"], run_id, w.work / "race-receipts.json"), w.pkg, w.reg)
    start = start_run(rc)
    plan = plan_step(rc, start.snapshot, 1, BudgetUsage(), start.carry)
    real_step = rc.env.step
    raced: list[int] = []

    def racing_step(proposal, *, operation_id, expected_revision=None):
        w.other_writer(tenant, 1)  # lands after every gate allowed, before the write's transaction
        raced.append(w.revision(tenant))
        return real_step(proposal, operation_id=operation_id, expected_revision=expected_revision)

    rc.env.step = racing_step
    ex = apply_step(rc, start.snapshot, plan, start.carry)
    out = ex.operation.outcome
    svc_op = next(o for o in w.ops(tenant) if o["operation_id"] == ex.operation.operation_id)
    return {"checked_at_revision": ex.operation.decisions[-1].execution.current_revision,
            "service_revision_when_write_arrived": raced[0], "gate_verdicts": [str(d.verdict)
                                                                             for d in ex.operation.decisions],
            "outcome": str(out.status.value), "effect_applied": out.effect_applied,
            "reason": (out.result or {}).get("reason"), "service_record_status": svc_op["status"],
            "service_record_revision_before_after": [svc_op["revision_before"], svc_op["revision_after"]],
            "service_writes_of_actor": len(w.writes(tenant))}


def legal_case(w: World) -> dict[str, Any]:
    tenant, run_id = "a2-legal", "run_a2_legal"
    rc = open_components(w.manifest(tenant, ["issuer", "broker"], run_id, w.work / "legal-receipts.json"), w.pkg,
                         w.reg)
    start = start_run(rc)
    before = w.revision(tenant)
    plan = plan_step(rc, start.snapshot, 1, BudgetUsage(), start.carry)
    ex = apply_step(rc, start.snapshot, plan, start.carry)
    writes = w.writes(tenant)
    return {"revision_before": before, "verdicts": [str(d.verdict) for d in ex.operation.decisions],
            "context_current_revision": ex.operation.decisions[-1].execution.current_revision,
            "outcome": str(ex.operation.outcome.status.value), "service_writes_of_actor": len(writes),
            "service_write_revision_before": writes[0]["revision_before"] if writes else None,
            "service_revision_after": w.revision(tenant)}


def idempotency_case(w: World) -> dict[str, Any]:
    tenant, run_id = "a2-ids", "run_a2_ids"
    rc = open_components(w.manifest(tenant, [], run_id, w.work / "unused.json"), w.pkg, w.reg)
    start = start_run(rc)
    plan = plan_step(rc, start.snapshot, 1, BudgetUsage(), start.carry)
    p = plan.proposal
    first = rc.env.step(p, operation_id="op-ids", expected_revision=0)
    again = rc.env.step(p, operation_id="op-ids", expected_revision=0)
    other = p.model_copy(update={"action": p.action.model_copy(update={"params": {**p.action.params, "o": "o2"}})})
    try:
        rc.env.step(other, operation_id="op-ids", expected_revision=0)
        conflict = "no conflict"
    except Conflict as exc:
        conflict = f"Conflict: {exc.message[:120]}"
    ledger = InMemoryLedger()
    coord = Coordinator(rc.env, rc.env_caps, ledger, gate=_send_hook(rc, 1, p.actor_id, plan.turn))
    coord.execute(p, "op-ids-kernel", run_id=run_id, step=1)
    clash = coord.execute(other, "op-ids-kernel", run_id=run_id, step=1)
    return {"first": str(first.status.value), "again_replayed": again.result.get("replayed"),
            "other_params": conflict, "kernel_same_id_other_request": clash.conflict is not None and clash.unresolved,
            "service_operations_of_actor": [o["operation_id"] for o in w.ops(tenant)]}


def mismatch_cases(w: World) -> dict[str, Any]:
    """A receipt issued for a context that differs in one field; the kernel's send path checks it."""
    tenant, run_id = "a2-mismatch", "run_a2_mismatch"
    receipts = w.work / "mismatch-receipts.json"
    rc = open_components(w.manifest(tenant, ["broker"], run_id, receipts), w.pkg, w.reg)
    start = start_run(rc)
    plan = plan_step(rc, start.snapshot, 1, BudgetUsage(), start.carry)
    p = plan.proposal
    from formal_lab_contracts import PluginRef, TurnRef

    cases = {
        "environment": {"environment": PluginRef(plugin_id="formal-lab.example.orders.service-env", version="9.9.9")},
        "session": {"session_id": "orders-another-tenant"},
        "turn": {"turn": TurnRef(global_step=1, round=2, actor_id=p.actor_id, actor_step=1)},
        "versions": {"versions": {"model": "orders@other"}},
        "service": {"service_identity": "http://127.0.0.1:1"},
        "revision": {"current_revision": 99},
    }
    out: dict[str, Any] = {}
    for name, change in cases.items():
        op_id = f"op-mismatch-{name}"
        ctx = build_context(rc, step=1, turn=plan.turn, actor=p.actor_id, record=_record(op_id, run_id, 1, p),
                            proposal=p, phase=ExecutionPhase.FIRST_SEND)
        _issue(w, receipts, ctx.model_copy(update=change))
        res = Coordinator(rc.env, rc.env_caps, InMemoryLedger(), gate=_send_hook(rc, 1, p.actor_id, plan.turn)) \
            .execute(p, op_id, run_id=run_id, step=1)
        failed = [c.name + ": " + (c.detail or "")[:140] for d in res.record.decisions for c in d.conditions
                  if c.holds is not True]
        out[name] = {"denied": res.denied, "failed_conditions": failed}
    # identity claimed by the proposal, not the kernel's
    intruder = p.model_copy(update={"actor_id": "intruder"})
    res = Coordinator(rc.env, rc.env_caps, InMemoryLedger(), gate=_send_hook(rc, 1, p.actor_id, plan.turn)) \
        .execute(intruder, "op-mismatch-actor", run_id=run_id, step=1)
    out["actor_claimed_by_proposal"] = {"denied": res.denied, "reasons": _reasons(res.record)}
    # the current revision cannot be read at the moment of the send (fault injected; the service itself is up)
    real = rc.env.current_revision

    def unreadable() -> int:
        raise httpx.ConnectError("revision read failed (injected)")

    rc.env.current_revision = unreadable
    ctx = build_context(rc, step=1, turn=plan.turn, actor=p.actor_id,
                        record=_record("op-mismatch-unknown", run_id, 1, p), proposal=p,
                        phase=ExecutionPhase.FIRST_SEND)
    res = Coordinator(rc.env, rc.env_caps, InMemoryLedger(), gate=_send_hook(rc, 1, p.actor_id, plan.turn)) \
        .execute(p, "op-mismatch-unknown", run_id=run_id, step=1)
    rc.env.current_revision = real
    out["unknown_revision"] = {"denied": res.denied, "revision_source": ctx.revision_source,
                               "reasons": _reasons(res.record)}
    out["service_operations_of_actor"] = len(w.ops(tenant))
    out["service_writes_of_actor"] = len(w.writes(tenant))
    return out


# ---------------------------------------------------------------------------------------------- recovery
def _resend_case(w: World, name: str, gates: list[str]) -> dict[str, Any]:
    tenant, run_id = f"a2-resend-{name.replace('_', '-')}", f"run_a2_resend_{name}"
    receipts = w.work / f"resend-{name}.json"
    rc = open_components(w.manifest(tenant, gates, run_id, receipts), w.pkg, w.reg)
    start = start_run(rc)
    plan = plan_step(rc, start.snapshot, 1, BudgetUsage(), start.carry)
    p = plan.proposal
    op_id = f"{turn_id(run_id, 1, p.actor_id)}:apply"
    if name == "stale_receipt":  # the receipt of the first send
        _issue(w, receipts, build_context(rc, step=1, turn=plan.turn, actor=p.actor_id,
                                          record=_record(op_id, run_id, 1, p), proposal=p,
                                          phase=ExecutionPhase.FIRST_SEND))
    real_step = rc.env.step
    lost = {"n": 0}

    def lossy_step(proposal, *, operation_id, expected_revision=None):
        if lost["n"] == 0:  # the first send dies before the service commits; another writer lands meanwhile
            lost["n"] += 1
            w.other_writer(tenant, 2)
            raise ResultUnknown("connection reset before the service committed (injected)")
        return real_step(proposal, operation_id=operation_id, expected_revision=expected_revision)

    rc.env.step = lossy_step
    ledger = InMemoryLedger()
    ex = apply_step(rc, start.snapshot, plan, start.carry, ledger)
    phases = [(str(d.phase.value), d.execution.current_revision, str(d.verdict)) for d in ex.operation.decisions]
    writes = w.writes(tenant)
    second = Coordinator(rc.env, rc.env_caps, ledger, gate=_send_hook(rc, 1, p.actor_id, plan.turn)) \
        .execute(p, op_id, run_id=run_id, step=1)
    return {"decisions": phases, "operation_state": str(ex.operation.state.value),
            "service_writes_of_actor": len(writes),
            "write_revision_before": writes[0]["revision_before"] if writes else None,
            "second_worker_reused": second.reused, "service_writes_after_second_worker": len(w.writes(tenant))}


def resend_cases(w: World) -> dict[str, Any]:
    return {"stale_receipt": _resend_case(w, "stale_receipt", ["broker"]),
            "reissued": _resend_case(w, "reissued", ["issuer", "broker"])}


def resume_case(w: World) -> dict[str, Any]:
    tenant, run_id = "a2-resume", "run_a2_resume"
    m = w.manifest(tenant, ["issuer", "broker"], run_id, w.work / "resume-receipts.json")
    state = run_local(m, w.pkg, w.reg, stop_after=3)
    data = json.loads(json.dumps(state.to_json()))  # through JSON, as a fresh process would get it
    result = resume_local(data, w.pkg, w.reg)
    svc_ops = {o["operation_id"]: o for o in w.ops(tenant)}
    rows = []
    for op in result.operations:
        if not op.decisions or op.operation_id not in svc_ops:
            continue
        ctx = op.decisions[-1].execution
        rows.append({"step": op.step, "source": ctx.revision_source, "checked": ctx.current_revision,
                     "service_revision_before": svc_ops[op.operation_id]["revision_before"]})
    return {"status": str(result.status.value), "operations": len(rows),
            "after_resume": [r for r in rows if r["step"] > 3][:4],
            "all_fresh_and_equal": bool(rows) and all(r["source"] == "FRESH" and r["checked"] ==
                                                      r["service_revision_before"] for r in rows),
            "service_writes_of_actor": len(w.writes(tenant)), "rejected_by_service": sum(
                1 for o in svc_ops.values() if o["status"] == "REJECTED")}


# ---------------------------------------------------------------------------------------------- projection
def projection_section(w: World) -> dict[str, Any]:
    from formal_lab_contracts.bundle import read_bundle, write_bundle
    from formal_lab_runtime.bundles import bundle_from_local
    from formal_lab_runtime.participants import ParticipantServices, participant_bundle
    from formal_lab_strategies.protocol_server import MODEL, ProtocolTestServer

    llm_key = f"a2-protocol-test-key-{uuid.uuid4().hex[:8]}"  # a test credential for the protocol test service only
    env_before = {k: os.environ.get(k) for k in ("FAL_LLM_BASE_URL", "FAL_LLM_API_KEY", "FAL_LLM_MODEL",
                                                 "ORDERS_WRITE_TOKEN_FILE")}
    server = ProtocolTestServer().start()
    os.environ.update({"FAL_LLM_BASE_URL": server.base_url, "FAL_LLM_API_KEY": llm_key, "FAL_LLM_MODEL": MODEL,
                       "ORDERS_WRITE_TOKEN_FILE": str(w.svc.write_token_file)})
    try:
        llm = {"plugin": {"plugin_id": "formal-lab.planner.llm", "version": "1.1.0"},
               "config": {"client": "openai_compatible", "on_model_failure": "fail", "max_attempts": 2,
                          "timeout_s": 10}}
        tenant, run_id = "a2-proj", "run_a2_projection"
        m = w.manifest(tenant, ["issuer", "broker"], run_id, w.work / "proj-receipts.json", two_actors=True,
                       strategy=llm)
        sc = m.scenario.model_dump(mode="json")
        sc["participants"][0]["view"] = {"exclude": ["stock"], "settings": {"style": "careful"}}
        sc = ScenarioManifest.model_validate(sc)
        m = make_manifest(run_id=run_id, project_id="a2", scenario=sc, package=w.pkg, registry=w.reg,
                          config={"initial_check_horizon": 0})
        result = run_local(m, w.pkg, w.reg)
        hidden, full = sc.participants[0].actor_id, sc.participants[1].actor_id

        def payloads_of(actor: str) -> list[str]:
            out = []
            for r in server.requests:
                text = json.dumps(r["body"], ensure_ascii=False)
                user = next((x["content"] for x in r["body"].get("messages", []) if x.get("role") == "user"), "")
                if f'"actor": "{actor}"' in user:
                    out.append(text)
            return out

        sent_hidden, sent_full = payloads_of(hidden), payloads_of(full)
        calls = json.dumps(result.model_calls, ensure_ascii=False)
        calls_hidden = [c for c in result.model_calls if c.get("actor_id") == hidden]
        calls_full = [c for c in result.model_calls if c.get("actor_id") == full]
        checkpoints = json.dumps(result.carry.get("checkpoints", {}).get(hidden, {}), ensure_ascii=False) \
            if isinstance(result.carry, dict) else ""
        operator_bytes = bundle_from_local(result, w.pkg)
        operator = read_bundle(operator_bytes)
        mine = participant_bundle(operator, hidden)
        part_bytes = write_bundle(mine, provenance={"participant": hidden, "projected": True})
        part_path = w.work / f"{run_id}.{hidden}.participant.replay.zip"
        part_path.write_bytes(part_bytes)
        with zipfile.ZipFile(io.BytesIO(part_bytes)) as zf:
            part_text = "\n".join(zf.read(n).decode("utf-8", "replace") for n in zf.namelist()
                                  if not n.startswith("contracts/") and not n.startswith("model/"))
        with zipfile.ZipFile(io.BytesIO(operator_bytes)) as zf:
            operator_text = "\n".join(zf.read(n).decode("utf-8", "replace") for n in zf.namelist()
                                      if not n.startswith("contracts/"))
        verify = subprocess.run([sys.executable, "-m", "formal_lab_sdk.cli", "replay", "verify", str(part_path)],
                                capture_output=True, text=True, timeout=120, cwd=tempfile.gettempdir())
        participant = next(p for p in sc.participants if p.actor_id == hidden)
        services = ParticipantServices(RuntimeServices(w.pkg), participant)
        refused = {k: services.get_setting(k) for k in ("ORDERS_WRITE_TOKEN_FILE", "FAL_PARTICIPANT_TOKEN_KEY")}
        token = w.token
        return {
            "run_status": str(result.status.value), "participants": {"withheld_family": "stock", "projected": hidden,
                                                                     "unfiltered": full},
            "model_requests": {"total": len(server.requests), "of_projected": len(sent_hidden),
                               "of_unfiltered": len(sent_full), "labelled_model": MODEL,
                               "authorization_header_present": all(r["authorization"]["present"]
                                                                   for r in server.requests)},
            "withheld_in_requests_of_projected": sum("stock[" in t for t in sent_hidden),
            "withheld_in_requests_of_unfiltered": sum("stock[" in t for t in sent_full),
            "withheld_in_call_records_of_projected": sum("stock[" in json.dumps(c) for c in calls_hidden),
            "call_records_of_projected": len(calls_hidden), "call_records_of_unfiltered": len(calls_full),
            "withheld_in_call_records_of_unfiltered": sum("stock[" in json.dumps(c) for c in calls_full),
            "call_records_without_actor": sum(1 for c in result.model_calls if not c.get("actor_id")),
            "withheld_in_checkpoint_of_projected": "stock[" in checkpoints,
            "write_token_in_requests": token in server.bodies_text(),
            "llm_key_in_request_bodies": llm_key in server.bodies_text(),
            "write_token_in_call_records": token in calls, "llm_key_in_call_records": llm_key in calls,
            "operator_export": {"has_withheld_family": "stock[" in operator_text,
                                "has_token_path": str(w.svc.write_token_file) in operator_text,
                                "has_token": token in operator_text, "has_llm_key": llm_key in operator_text,
                                "events": len(operator.events)},
            "participant_download": {"bytes": len(part_bytes), "events": len(mine.events),
                                     "has_withheld_family": "stock[" in part_text,
                                     "has_token": token in part_text, "has_token_path":
                                         str(w.svc.write_token_file) in part_text,
                                     "has_llm_key": llm_key in part_text,
                                     "has_service_endpoint": w.svc.endpoint in part_text,
                                     "has_other_participant_events": any(e.actor_id == full for e in mine.events),
                                     "other_participant_view_or_config": any(
                                         p.view is not None or p.strategy.config for p in mine.manifest.participants
                                         if p.actor_id != hidden),
                                     "offline_verify_exit": verify.returncode,
                                     "offline_verify": (verify.stdout or verify.stderr).strip()[:300]},
            "participant_settings_refused": {k: v is None for k, v in refused.items()},
        }
    finally:
        server.stop()
        for k, v in env_before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def warehouse_section(work: Path) -> dict[str, Any]:
    """The warehouse (pure-data driver world, receiver + picker with views, capacity gate): the basis of every send is
    SERIALIZED (the run's own world, steps serialized), and the picker's download never shows the docks."""
    from formal_lab_contracts.bundle import read_bundle, write_bundle
    from formal_lab_example_warehouse.scenarios import JOINT, VIEWS, package, receiver_and_picker
    from formal_lab_runtime.bundles import bundle_from_local
    from formal_lab_runtime.participants import participant_bundle

    reg = default_registry()
    pkg = package()
    out: dict[str, Any] = {}
    for label, turns in (("round_robin", None), ("joint_batch", JOINT)):
        sc = receiver_and_picker(pkg, views=VIEWS, max_fill=0.9, turns=turns)
        m = make_manifest(run_id=f"run_a2_wh_{label}", project_id="a2", scenario=sc, package=pkg, registry=reg)
        result = run_local(m, pkg, reg)
        ctxs = [d.execution for op in result.operations for d in op.decisions if d.execution is not None]
        operator = read_bundle(bundle_from_local(result, pkg))
        mine = participant_bundle(operator, "picker")
        data = write_bundle(mine, provenance={"participant": "picker", "projected": True})
        back = read_bundle(data)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            text = "\n".join(zf.read(n).decode("utf-8", "replace") for n in zf.namelist()
                              if not n.startswith(("contracts/", "model/")))
        full_text = "\n".join(e.model_dump_json() for e in operator.events)
        out[label] = {"status": str(result.status.value), "sends": len(ctxs),
                      "revision_sources": sorted({c.revision_source for c in ctxs}),
                      "all_have_current_revision": all(c.current_revision is not None for c in ctxs),
                      "picker_download_events": len(back.events), "picker_download_has_dock": "dock[" in text,
                      "operator_has_dock": "dock[" in full_text,
                      "picker_download_has_receiver_events": any(e.actor_id == "receiver" for e in back.events)}
    (work / "warehouse.json").write_text(json.dumps(out))
    return out


def main() -> int:
    r = CheckResult("p4-a2-execution-basis")
    work = Path(tempfile.mkdtemp(prefix="a2-evidence-"))
    w = World(work)
    try:
        svc = service_section(w)
        stale, race, legal = stale_receipt_case(w), race_case(w), legal_case(w)
        ids, mism = idempotency_case(w), mismatch_cases(w)
        resend, resume = resend_cases(w), resume_case(w)
        proj = projection_section(w)
    finally:
        w.close()
    wh = warehouse_section(work)

    c = r.check
    c("credential_required", svc["write_without_credential"] == 401 and svc["write_with_wrong_credential"] == 401
      and svc["admin_reset_without_credential"] == 401 and svc["operations_recorded_for_refused_writes"] == 0,
      f"anon={svc['write_without_credential']} wrong={svc['write_with_wrong_credential']} "
      f"reset={svc['admin_reset_without_credential']} recorded={svc['operations_recorded_for_refused_writes']}")
    c("credential_distribution", svc["token_file_mode"] == "0o600" and not svc["token_in_service_argv"]
      and not svc["manifest_has_token"] and svc["read_without_credential"] == 200,
      f"mode={svc['token_file_mode']} argv_token={svc['token_in_service_argv']} manifest_token="
      f"{svc['manifest_has_token']} (path only: {svc['manifest_has_token_path']})")
    c("loopback_only", svc["listen_host"] == "127.0.0.1" and all(v != "CONNECTED"
                                                                 for v in svc["non_loopback_reach"].values()),
      f"host={svc['listen_host']} non-loopback={svc['non_loopback_reach'] or 'no other address'}")
    c("stale_receipt_zero_writes", stale["proposal_revision"] == 5 and stale["receipt_revision"] == 5
      and stale["context_current_revision"] == 7 and stale["verdict"] == "DENY"
      and stale["service_operations_of_actor"] == 0 and stale["service_revision_after"] == 7,
      f"proposal@{stale['proposal_revision']} receipt@{stale['receipt_revision']} service@"
      f"{stale['context_current_revision']} → {stale['verdict']}, service ops={stale['service_operations_of_actor']}")
    c("check_then_write_race_refused", race["outcome"] == "REJECTED" and not race["effect_applied"]
      and race["service_record_status"] == "REJECTED" and race["service_writes_of_actor"] == 0
      and race["service_record_revision_before_after"][0] == race["service_record_revision_before_after"][1],
      f"checked@{race['checked_at_revision']} write arrived @{race['service_revision_when_write_arrived']}: "
      f"{race['reason']}")
    c("legal_same_revision_applies_once", legal["outcome"] == "APPLIED" and legal["service_writes_of_actor"] == 1
      and legal["service_write_revision_before"] == legal["context_current_revision"],
      f"checked@{legal['context_current_revision']} written@{legal['service_write_revision_before']}")
    c("same_id_same_request_reuses", ids["first"] == "APPLIED" and ids["again_replayed"] is True,
      f"replayed={ids['again_replayed']}")
    c("same_id_other_params_conflict", ids["other_params"].startswith("Conflict")
      and ids["kernel_same_id_other_request"], ids["other_params"])
    names = ("environment", "session", "turn", "versions", "service", "revision")
    c("binding_mismatches_refused", all(mism[n]["denied"] for n in names) and mism["service_writes_of_actor"] == 0,
      "; ".join(f"{n}: {mism[n]['failed_conditions'][:1]}" for n in names))
    c("identity_claim_refused", mism["actor_claimed_by_proposal"]["denied"],
      str(mism["actor_claimed_by_proposal"]["reasons"][:1]))
    c("unknown_revision_blocks", mism["unknown_revision"]["denied"]
      and mism["unknown_revision"]["revision_source"] == "UNKNOWN", str(mism["unknown_revision"]["reasons"][:1]))
    c("resend_same_rules", resend["stale_receipt"]["service_writes_of_actor"] == 0
      and resend["reissued"]["service_writes_of_actor"] == 1
      and resend["reissued"]["write_revision_before"] == 2,
      f"stale: {resend['stale_receipt']['decisions']} reissued: {resend['reissued']['decisions']}")
    c("two_workers_send_once", resend["reissued"]["second_worker_reused"]
      and resend["reissued"]["service_writes_after_second_worker"] == 1, "shared ledger → reuse, no second write")
    c("resume_keeps_fresh_basis", resume["all_fresh_and_equal"] and resume["status"] == "SUCCEEDED",
      f"{resume['operations']} sends, every context FRESH and equal to the service's revision_before")
    pd = proj["participant_download"]
    c("projection_model_requests", proj["model_requests"]["of_projected"] > 0
      and proj["withheld_in_requests_of_projected"] == 0 and proj["withheld_in_requests_of_unfiltered"] > 0,
      f"projected: {proj['withheld_in_requests_of_projected']}/{proj['model_requests']['of_projected']} requests "
      f"with stock[…]; unfiltered (control): {proj['withheld_in_requests_of_unfiltered']}/"
      f"{proj['model_requests']['of_unfiltered']}")
    c("projection_call_records_checkpoint", proj["call_records_of_projected"] > 0
      and proj["withheld_in_call_records_of_projected"] == 0 and proj["call_records_without_actor"] == 0
      and proj["withheld_in_call_records_of_unfiltered"] > 0 and not proj["withheld_in_checkpoint_of_projected"],
      f"projected: {proj['withheld_in_call_records_of_projected']}/{proj['call_records_of_projected']} call records "
      f"with stock[…]; unfiltered (control): {proj['withheld_in_call_records_of_unfiltered']}/"
      f"{proj['call_records_of_unfiltered']}")
    c("credentials_never_leave", not any([proj["write_token_in_requests"], proj["llm_key_in_request_bodies"],
                                          proj["write_token_in_call_records"], proj["llm_key_in_call_records"],
                                          proj["operator_export"]["has_token"], proj["operator_export"]["has_llm_key"],
                                          pd["has_token"], pd["has_llm_key"]]),
      "write token and model key absent from request bodies, call records, operator export, participant download")
    c("participant_download_projected", not pd["has_withheld_family"] and not pd["has_token_path"]
      and not pd["has_service_endpoint"] and not pd["has_other_participant_events"]
      and not pd["other_participant_view_or_config"] and proj["operator_export"]["has_withheld_family"],
      f"download: {pd['events']} events, no stock[…], no endpoint / credential path; operator export keeps them")
    c("participant_download_replays_offline", pd["offline_verify_exit"] == 0 and pd["offline_verify"].startswith("OK"),
      pd["offline_verify"][:160])
    c("participant_settings_refused", all(proj["participant_settings_refused"].values()),
      str(proj["participant_settings_refused"]))
    c("warehouse_serialized_basis", all(v["status"] == "SUCCEEDED" and v["sends"] > 0
                                        and v["revision_sources"] == ["SERIALIZED"] and v["all_have_current_revision"]
                                        for v in wh.values()),
      "; ".join(f"{k}: {v['sends']} gated sends, basis {v['revision_sources']}" for k, v in wh.items()))
    c("warehouse_picker_download_projected", all(not v["picker_download_has_dock"] and v["operator_has_dock"]
                                                 and not v["picker_download_has_receiver_events"]
                                                 for v in wh.values()),
      "; ".join(f"{k}: {v['picker_download_events']} events, dock[…] absent" for k, v in wh.items()))

    EV.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "deliverable": "phase4A-A2", "service": "formal_lab_example_orders (process, secure writes, SQLite)",
        "write_counts_from": "the service's /admin/export operation records",
        "model_endpoint": "protocol test service (loopback, OpenAI-compatible; NOT a model)",
        "sections": {"service": svc, "stale_receipt": stale, "race": race, "legal": legal, "idempotency": ids,
                     "mismatch": mism, "resend": resend, "resume": resume, "projection": proj, "warehouse": wh},
        "conclusion": {a["id"]: a["holds"] for a in r.assertions}}, indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(OUT)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
