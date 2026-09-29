"""The local order service as a persistent environment (P2-050 … P2-056, P2-060 … P2-068), against a real service
process started by the lifecycle manager."""

from __future__ import annotations

import concurrent.futures
import time

import httpx
import pytest
from formal_lab_contracts import ActionProposal, GroundAction, OperationRecord, ProposalSource, utcnow
from formal_lab_example_orders.compare import compare_runs
from formal_lab_example_orders.env import CAPABILITIES, OrderServiceEnvironment
from formal_lab_example_orders.lifecycle import (
    LifecycleError,
    ServiceManager,
    cleanup_project,
    precheck,
    run_with_timeout,
)
from formal_lab_example_orders.model import model_package
from formal_lab_example_orders.plugins import RULES, OrderProbe
from formal_lab_example_orders.scenarios import run, scenario
from formal_lab_runtime import default_registry
from formal_lab_runtime.coordination import Coordinator, InMemoryLedger, transition


@pytest.fixture(scope="module")
def svc(tmp_path_factory):
    mgr = ServiceManager(tmp_path_factory.mktemp("orders"), project="t-orders", supervise=True).start()
    mgr.ready()
    yield mgr
    mgr.close()


@pytest.fixture(scope="module")
def reg():
    return default_registry()


def env_for(svc, tenant: str, case: str = "normal", **cfg) -> OrderServiceEnvironment:
    env = OrderServiceEnvironment({"endpoint": svc.endpoint, "tenant": tenant, "case": case, **cfg})
    env.reset(scenario(case, endpoint=svc.endpoint), model_package(), run_id=f"run_{tenant}", seed=1)
    return env


def proposal(action: str, params: dict, *, step: int = 1, rev: int = 0) -> ActionProposal:
    return ActionProposal(proposal_id=f"p{step}", run_id="run_t", step_id=f"s{step}", step=step, actor_id="handler",
                          action=GroundAction(action_type=action, params=params), based_on_revision=rev,
                          source=ProposalSource(kind="RULE", strategy=RULES.ref()), rationale="test")


def ops(svc, tenant: str) -> list[dict]:
    return httpx.get(f"{svc.endpoint}/t/{tenant}/admin/export", timeout=10).json()["operations"]


def stock(env, sku: str = "a") -> int:
    return int(env.truth_state()[f"stock[{sku}]"])


def test_service_api_state_survives_a_process_kill(svc):
    """P2-060: fixed API, SQLite persistence, health; a SIGKILLed process restarts with its data and records the
    restart (the probe's recovery time comes from the service itself)."""
    env = env_for(svc, "api")
    assert httpx.get(f"{svc.endpoint}/health").json()["project"] == "t-orders"
    state = env.truth_state()
    assert {state[f"status[o{i}]"] for i in (1, 2, 3)} == {"submitted"} and state["status[o4]"] == "pending"
    res = Coordinator(env, set(CAPABILITIES), InMemoryLedger()).execute(proposal("reserve", {"o": "o1"}), "op-api-1",
                                                                        run_id="run_t", step=1)
    assert res.outcome.status == "APPLIED" and stock(env) == 4
    pid = svc.kill()
    deadline = time.time() + 20
    while time.time() < deadline and (not svc.restarts or "ready_after_s" not in svc.restarts[-1]):
        time.sleep(0.2)
    assert svc.restarts and svc.restarts[-1]["ready_after_s"] < 10
    assert httpx.get(f"{svc.endpoint}/health").json()["pid"] != pid
    assert stock(env) == 4 and env.query_operation("op-api-1").status == "APPLIED"
    probe = {p.metric: p for p in OrderProbe().sample(env.session(), step=1)}
    assert probe["recovery_seconds"].status == "OK" and probe["recovery_seconds"].value >= 0
    assert probe["queue_length"].value == 0 and probe["backlog"].value == 3


def test_a_stable_operation_id_takes_effect_once(svc):
    """P2-052: the intent is recorded before the call; the service returns the stored result for a known id —
    also for concurrent duplicates — so an order is reserved once."""
    env = env_for(svc, "idem")
    ledger = InMemoryLedger()
    seen = []
    original = env.step

    def step(p, *, operation_id):
        seen.append(ledger.get(operation_id).state.value)  # what the ledger said when the service was called
        return original(p, operation_id=operation_id)

    env.step = step  # type: ignore[method-assign]
    res = Coordinator(env, set(CAPABILITIES), ledger).execute(proposal("reserve", {"o": "o1"}), "op-idem-1",
                                                              run_id="run_t", step=1)
    assert seen == ["DISPATCHED"] and [t.state.value for t in res.record.transitions] == \
        ["PREPARED", "DISPATCHED", "COMPLETED"]
    body = {"operation_id": "op-idem-1", "actor_id": "handler", "action": "reserve", "params": {"o": "o1"}}
    again = httpx.post(f"{svc.endpoint}/t/idem/operations", json=body).json()  # the same request redelivered
    assert again["replayed"] is True and again["status"] == "APPLIED" and stock(env) == 4
    other = httpx.post(f"{svc.endpoint}/t/idem/operations", json={**body, "params": {"o": "o3"}})
    assert other.status_code == 409 and other.json()["error"] == "OPERATION_ID_CONFLICT"  # same id, other request
    assert stock(env) == 4
    body = {"operation_id": "op-idem-2", "action": "reserve", "params": {"o": "o3"}}
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        answers = list(pool.map(lambda _: httpx.post(f"{svc.endpoint}/t/idem/operations", json=body,
                                                     timeout=30).json(), range(8)))
    assert sum(1 for a in answers if not a["replayed"]) == 1 and {a["status"] for a in answers} == {"APPLIED"}
    assert stock(env) == 1 and [o["operation_id"] for o in ops(svc, "idem")] == ["op-idem-1", "op-idem-2"]


def test_a_lost_response_is_settled_by_looking_the_operation_up(svc):
    """P2-053: the service commits, the answer arrives after the client gave up; the coordinator asks for the
    operation id and the business state before deciding — one reservation, never a second one."""
    env = env_for(svc, "lost", timeout_s=0.5)
    env.set_conditions({"hold_after_commit_ms": 1500, "hold_every": 1})
    res = Coordinator(env, set(CAPABILITIES), InMemoryLedger()).execute(proposal("reserve", {"o": "o1"}), "op-lost-1",
                                                                        run_id="run_t", step=1)
    assert [t.state.value for t in res.record.transitions] == ["PREPARED", "DISPATCHED", "OUTCOME_UNKNOWN", "RECONCILED"]
    assert res.outcome.status == "APPLIED" and res.record.reconciliation.found is True
    env.set_conditions({"hold_after_commit_ms": 0})
    assert stock(env) == 4 and len(ops(svc, "lost")) == 1


def test_duplicate_activity_and_a_lost_process_cache(svc):
    """P2-054: a duplicated attempt returns the recorded outcome without calling the service; a fresh adapter
    (process cache lost) attached from the session marker settles a DISPATCHED record by lookup — found: not sent
    again; not found: re-sent with the same id — each order effect exactly once (service transactions + ids)."""
    env = env_for(svc, "dup")
    ledger = InMemoryLedger()
    coord = Coordinator(env, set(CAPABILITIES), ledger)
    first = coord.execute(proposal("reserve", {"o": "o1"}), "op-dup-1", run_id="run_t", step=1)
    second = coord.execute(proposal("reserve", {"o": "o1"}), "op-dup-1", run_id="run_t", step=1)
    assert second.outcome == first.outcome and second.record.attempts == 1 and len(ops(svc, "dup")) == 1
    marker = env.snapshot()
    # the old process sent op-dup-2 (the service committed it) and died before recording the answer
    httpx.post(f"{svc.endpoint}/t/dup/operations",
               json={"operation_id": "op-dup-2", "action": "reserve", "params": {"o": "o2"}}).raise_for_status()
    for op_id in ("op-dup-2", "op-dup-3"):  # op-dup-3: dispatched in the ledger, never reached the service
        rec = OperationRecord(operation_id=op_id, run_id="run_t", step=2, actor_id="handler", state="PREPARED",
                              action=GroundAction(action_type="reserve", params={"o": "o2" if op_id.endswith("2")
                                                                                 else "o3"}),
                              based_on_revision=1, transitions=[{"state": "PREPARED", "at": utcnow(),
                                                                 "reason": "intent recorded", "attempt": 1}])
        ledger.put(transition(rec, "DISPATCHED", "sent to the environment"))
    fresh = OrderServiceEnvironment()
    fresh.attach(marker)
    coord2 = Coordinator(fresh, set(CAPABILITIES), ledger)
    found = coord2.execute(proposal("reserve", {"o": "o2"}, step=2, rev=1), "op-dup-2", run_id="run_t", step=2)
    assert found.record.state.value == "RECONCILED" and found.outcome.status == "APPLIED"
    resent = coord2.execute(proposal("reserve", {"o": "o3"}, step=3, rev=2), "op-dup-3", run_id="run_t", step=3)
    states = [t.state.value for t in resent.record.transitions]
    assert states[-3:] == ["OUTCOME_UNKNOWN", "DISPATCHED", "COMPLETED"] and resent.outcome.status == "APPLIED"
    assert [o["operation_id"] for o in ops(svc, "dup")] == ["op-dup-1", "op-dup-2", "op-dup-3"]
    assert stock(fresh, "a") == 6 - 2 - 3 and stock(fresh, "b") == 6 - 1


def test_an_operation_that_cannot_be_looked_up_needs_review(tmp_path):
    """P2-058: the answer is lost and the service stays down past the readiness wait: the coordinator does not
    guess — NEEDS_REVIEW, run ends OPERATION_UNRESOLVED; once the service is back a person can confirm it."""
    mgr = ServiceManager(tmp_path, project="t-down").start()
    mgr.ready()
    try:
        env = env_for(mgr, "down", timeout_s=0.5, ready_timeout_s=1.0)
        env.set_conditions({"hold_after_commit_ms": 3000, "hold_every": 1})
        coord = Coordinator(env, set(CAPABILITIES), InMemoryLedger())
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            fut = pool.submit(coord.execute, proposal("reserve", {"o": "o1"}), "op-down-1", run_id="run_t", step=1)
            time.sleep(0.3)  # committed and held; now the process dies
            mgr.kill()
            res = fut.result(timeout=30)
        assert res.unresolved and res.record.review.status == "NEEDS_REVIEW"
        assert "looking up operation op-down-1 failed" in res.record.review.note
        port = mgr.port
        mgr._proc = None
        mgr.start()
        assert mgr.port == port
        mgr.ready()
        assert env.query_operation("op-down-1").status == "APPLIED"  # what the reviewer will confirm
    finally:
        mgr.close()


@pytest.mark.parametrize("case", ["normal", "shortage", "delayed", "restart", "deviation"])
def test_five_repeatable_cases_on_the_service(svc, reg, case):
    """P2-065: each case runs to completion on the business service with its characteristic behaviour."""
    res = run(case, backend="service", seed=1, endpoint=svc.endpoint, tenant=f"case-{case}", registry=reg)
    assert res.status == "SUCCEEDED" and res.metric("orders_completed").value == 6
    states = [o.state.value for o in res.operations]
    actions = [o.action.action_type for o in res.operations]
    probes = [p for p in res.probes if p.metric == "throughput"]
    assert probes and all(p.status == "OK" for p in probes)
    diffs = sum(1 for e in res.events if str(e.event_type) == "EFFECT_COMPARED"
                and e.payload["comparison"]["verdict"] == "DIFFERENT")
    if case == "shortage":
        assert "restock" in actions
    if case == "delayed":
        assert states.count("RECONCILED") >= 3
    if case == "restart":
        assert states.count("RECONCILED") == 1
        recovery = [p for p in res.probes if p.metric == "recovery_seconds" and p.status == "OK"]
        assert recovery, "the restart is visible to the independent probe"
    if case == "deviation":
        assert diffs > 0
    else:
        assert diffs == 0
    assert len(ops(svc, f"case-{case}")) == res.usage.steps  # one business operation per step, none twice


@pytest.mark.parametrize("case", ["normal", "deviation"])
def test_pure_model_and_service_compared_field_by_field(svc, reg, case):
    """P2-066: same case, seed and strategy on both backends; differences are located by step, operation and
    field. Normal: none. Deviation: only effects of `tick` on the slow station's orders — identical on both
    backends here, because the pure model carries the same hidden constant; against the planners' model the
    difference shows as EFFECT_COMPARED."""
    pure = run(case, backend="pure", seed=2, registry=reg, run_id=f"run_cmp_{case}_pure")
    service = run(case, backend="service", seed=2, endpoint=svc.endpoint, tenant=f"cmp-{case}", registry=reg,
                  run_id=f"run_cmp_{case}_svc")
    report = compare_runs(pure, service)
    assert report["aligned_steps"] == pure.usage.steps == service.usage.steps
    assert report["compared_fields"] > 500 and report["differences"] == []
    assert report["evidence_kinds"] == {"pure": [], "service": ["operation"]} or \
        report["evidence_kinds"]["service"] == ["operation"]
    # a deliberately different truth: the service slow, the pure model not → effect differences, located
    if case == "deviation":
        nominal = run("normal", backend="pure", seed=2, registry=reg, run_id="run_cmp_nominal")
        diff = compare_runs(nominal, service)
        assert diff["differences"] and {d["kind"] for d in diff["differences"]} <= {"effect", "trajectory",
                                                                                    "precondition"}
        first = diff["differences"][0]
        assert first["service_operation"] and first["pure_operation"] and "[" in first["field"]


def test_stale_observations_meet_the_service_conditional_update(svc, reg):
    """P2-056: two handlers observe at round start; the second commits on an observation the first one already
    changed. The service's conditional update (row revisions of the locations the operation reads) refuses it —
    the same arbitration the pure model applies by world revision."""
    kw = {"two_actors": True, "timing": "ROUND_START", "conflict_policy": "REJECT_STALE", "registry": reg}
    service = run("normal", backend="service", seed=1, endpoint=svc.endpoint, tenant="stale", **kw)
    pure = run("normal", backend="pure", seed=1, **kw)
    conflicts = [o for o in (e.payload["outcome"] for e in service.events if str(e.event_type) == "ACTION_OUTCOME")
                 if o.get("conflict")]
    assert conflicts, "a stale commit happened and was refused"
    c = conflicts[0]
    assert c["status"] == "REJECTED" and "STALE_REVISION" in c["result"]["reason"]
    assert c["conflict"]["changed_paths"] and c["conflict"]["based_on_revision"] < c["conflict"]["current_revision"]
    pure_conflicts = [e for e in pure.events if str(e.event_type) == "ACTION_OUTCOME"
                      and e.payload["outcome"].get("conflict")]
    assert pure_conflicts and service.status == pure.status


def test_lifecycle_labels_precheck_and_scoped_cleanup(tmp_path):
    """P2-062 / P2-068: create → start → ready → reset → close with a project label; the resource precheck; a
    failed run's leftovers are removed by project label while another project's service keeps running."""
    report = precheck(tmp_path)
    assert report["ok"] and report["cpus"] >= 1
    with pytest.raises(LifecycleError):
        precheck(tmp_path, min_disk_mb=10**9)
    a = ServiceManager(tmp_path, project="t-a").start()
    b = ServiceManager(tmp_path, project="t-b").start()
    try:
        a.ready()
        b.ready()
        a.reset("x", case="normal", seed=0)
        assert [t["status"] for t in a.transitions] == ["CREATED", "STARTING", "READY", "RESETTING", "READY"]
        manifest = (a.home / "manifest.json").read_text()
        assert '"dev.formal-lab.project": "t-a"' in manifest
        st = a.stats()
        assert st["rss_kb"] and st["data_bytes"] > 0
        removed = cleanup_project(tmp_path, "t-a")  # as after a failure: a was never closed
        assert removed["processes"] and not a.home.exists()
        with pytest.raises(httpx.HTTPError):
            httpx.get(f"{a.endpoint}/health", timeout=1)
        assert httpx.get(f"{b.endpoint}/health").json()["project"] == "t-b"  # the other project is untouched
    finally:
        cleanup_project(tmp_path, "t-a")  # no leftover service when an assertion above fails
        b.close()
    assert not (tmp_path / ".fal-orders").exists()
    with pytest.raises(LifecycleError):
        run_with_timeout(time.sleep, 0.2, 2)


def test_recovery_modes_are_declared_and_verified_by_probes(svc, reg):
    """P2-067: service-side reset and state import on the service; reseed and snapshot on the pure model — each
    verified by the independent probe (service) or the truth state (pure)."""
    env = env_for(svc, "recover")
    assert {m.value for m in env.session().recovery_modes} == {"SERVICE_RESET", "STATE_IMPORT"}
    initial = {p.metric: p.value for p in OrderProbe().sample(env.session(), step=0)}
    coord = Coordinator(env, set(CAPABILITIES), InMemoryLedger())
    for i, (a, p) in enumerate([("reserve", {"o": "o1"}), ("enqueue", {"o": "o1"}), ("start", {"o": "o1", "st": "p1"}),
                                ("tick", {}), ("tick", {})], start=1):
        assert coord.execute(proposal(a, p, step=i), f"op-rec-{i}", run_id="run_t", step=i).outcome.status == "APPLIED"
    exported = env.export_state()
    at_export = {p.metric: p.value for p in OrderProbe().sample(env.session(), step=5)}
    assert at_export["throughput"] > 0 and at_export != initial
    coord.execute(proposal("reserve", {"o": "o2"}, step=6), "op-rec-6", run_id="run_t", step=6)
    env.import_state(exported)
    after_import = {p.metric: p.value for p in OrderProbe().sample(env.session(), step=5)}
    assert {k: after_import[k] for k in ("throughput", "completion_rate", "queue_length", "backlog")} == \
        {k: at_export[k] for k in ("throughput", "completion_rate", "queue_length", "backlog")}
    env.reset_session(seed=1)
    after_reset = {p.metric: p.value for p in OrderProbe().sample(env.session(), step=0)}
    assert {k: after_reset[k] for k in ("throughput", "queue_length", "backlog")} == \
        {k: initial[k] for k in ("throughput", "queue_length", "backlog")}
    # pure model: reseed gives the same start, a FULL_STATE snapshot restores exactly
    from formal_lab_env.ir_world import IRWorldEnvironment

    sc = scenario("normal", backend="pure", seed=3)
    pure = IRWorldEnvironment(sc.environment.config)
    pure._package = model_package()
    first = pure.reset(sc, model_package(), run_id="run_pure", seed=3)
    snap = pure.snapshot()
    pure.step(proposal("reserve", {"o": "o1"}), operation_id="op-p-1")
    assert pure.truth_state() != snap.data["data"]["state"]
    pure.restore(snap)
    assert pure.truth_state() == snap.data["data"]["state"]
    again = IRWorldEnvironment(sc.environment.config).reset(sc, model_package(), run_id="run_pure", seed=3)
    assert again.facts == first.facts


def test_capabilities_are_negotiated_at_run_start(svc, reg):
    """P2-050: the run manifest records the environment's granted capabilities and the recovery path they imply —
    replay for the pure model, look-up-by-id for the service."""
    from formal_lab_contracts import PluginDescriptor
    from formal_lab_runtime import make_manifest
    from formal_lab_runtime.manifest import recovery_path

    def env_negotiation(backend: str):
        sc = scenario("normal", backend=backend, endpoint=svc.endpoint)
        m = make_manifest(run_id=f"run_neg_{backend}", project_id="p", scenario=sc, package=model_package(),
                          registry=reg, seed=0)
        return next(n for n in m.negotiation if n.role == "environment")

    pure, service = env_negotiation("pure"), env_negotiation("service")
    assert "env.pure_replayable" in pure.granted and any("pure-data replay" in r for r in pure.reasons)
    assert {"env.persistent_session", "env.query_operation"} <= set(service.granted)
    assert "env.pure_replayable" in service.missing_optional
    assert any("looked up by id" in r for r in service.reasons)
    bare = PluginDescriptor(plugin_id="x.env", version="1.0.0", interface="ENVIRONMENT",
                            capabilities=[{"id": "env.persistent_session"}], entrypoint="x:y",
                            ui={"label": "x"}, license="Apache-2.0", source="x")
    assert "manual review" in recovery_path(bare)


def test_the_service_environment_passes_the_public_contract_harness(svc):
    """P2-018: the public harness (formal_lab_sdk.plugin_testing) drives the service adapter through reset, step,
    session-marker re-attach, operation lookup and close."""
    from formal_lab_example_orders.env import ENV_ID, ENV_VERSION
    from formal_lab_sdk.plugin_testing import check_environment

    report = check_environment((ENV_ID, ENV_VERSION), {"endpoint": svc.endpoint, "tenant": "contract"},
                               package=model_package())
    assert report.ok, report.failures()
    details = {s.name: s.detail for s in report.stages}
    assert "SESSION_MARKER" in details["snapshot / restore"] and "found by id" in details["operation lookup"]
