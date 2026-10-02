"""Phase 4A (A2) against a real order-service process with a write credential: writes need the credential, the
verified revision is checked inside the write's own transaction, an operation id is bound to its request, and the
kernel's send path (issuer → broker gate → conditional write) admits only the basis it checked. Every count is read
from the service's own records."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from formal_lab_contracts import ActionProposal, GroundAction, ProposalSource, ScenarioManifest
from formal_lab_contracts.errors import Conflict
from formal_lab_example_orders.env import ENV_ID, OrderServiceEnvironment
from formal_lab_example_orders.lifecycle import ServiceManager
from formal_lab_example_orders.model import model_package
from formal_lab_example_orders.plugins import RULES
from formal_lab_example_orders.scenarios import run, scenario


@pytest.fixture(scope="module")
def svc(tmp_path_factory):
    mgr = ServiceManager(tmp_path_factory.mktemp("orders-secure"), project="t-secure", secure_writes=True).start()
    mgr.ready()
    yield mgr
    mgr.close()


def env_for(svc, tenant: str, **cfg) -> OrderServiceEnvironment:
    env = OrderServiceEnvironment({"endpoint": svc.endpoint, "tenant": tenant,
                                   "write_token_file": str(svc.write_token_file), **cfg})
    env.reset(scenario("normal", endpoint=svc.endpoint), model_package(), run_id=f"run_{tenant}", seed=1)
    return env


def proposal(action: str, params: dict, *, rev: int, actor: str = "handler", step: int = 1) -> ActionProposal:
    return ActionProposal(proposal_id=f"p{step}", run_id="run_t", step_id=f"s{step}", step=step, actor_id=actor,
                          action=GroundAction(action_type=action, params=params), based_on_revision=rev,
                          source=ProposalSource(kind="RULE", strategy=RULES.ref()), rationale="test")


def export(svc, tenant: str) -> dict:
    return httpx.get(f"{svc.endpoint}/t/{tenant}/admin/export", timeout=10).json()


def other_writer(svc, tenant: str, n: int) -> None:
    for _ in range(n):
        r = httpx.post(f"{svc.endpoint}/t/{tenant}/operations", headers=svc.write_headers(), timeout=10,
                       json={"operation_id": f"other-{uuid.uuid4().hex[:10]}", "actor_id": "other-writer",
                             "action": "tick",
                             "params": {}})
        assert r.status_code == 200 and r.json()["status"] == "APPLIED"


def test_writes_need_the_credential_reads_do_not(svc):
    env_for(svc, "auth")
    body = {"operation_id": "anon-1", "actor_id": "handler", "action": "tick", "params": {}}
    assert httpx.post(f"{svc.endpoint}/t/auth/operations", json=body).status_code == 401
    wrong = httpx.post(f"{svc.endpoint}/t/auth/operations", json=body, headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401
    assert httpx.post(f"{svc.endpoint}/t/auth/admin/reset", json={}).status_code == 401
    assert httpx.get(f"{svc.endpoint}/t/auth/state").status_code == 200
    assert httpx.get(f"{svc.endpoint}/health").json()["write_auth"] is True
    assert export(svc, "auth")["operations"] == []  # nothing recorded for refused writes


def test_receipt_at_5_service_at_7_writes_nothing(svc):
    env = env_for(svc, "stale")
    other_writer(svc, "stale", 5)
    assert env.current_revision() == 5
    other_writer(svc, "stale", 2)  # moves on after the check
    before = export(svc, "stale")
    out = env.step(proposal("reserve", {"o": "o1"}, rev=5), operation_id="op-stale", expected_revision=5)
    after = export(svc, "stale")
    assert out.status == "REJECTED" and not out.effect_applied and "STALE_REVISION" in out.result["reason"]
    assert after["meta"]["revision"] == before["meta"]["revision"] == 7
    assert len(after["changes"]) == len(before["changes"])  # no business write
    assert [o["status"] for o in after["operations"] if o["operation_id"] == "op-stale"] == ["REJECTED"]


def test_same_revision_send_applies_and_locations_policy_ignores_unrelated_writes(svc):
    env = env_for(svc, "fresh")
    out = env.step(proposal("reserve", {"o": "o1"}, rev=0), operation_id="op-fresh", expected_revision=0)
    assert out.status == "APPLIED" and out.revision_after == 1
    loc = env_for(svc, "loc", version_policy="LOCATIONS")
    other_writer(svc, "loc", 1)  # writes clock only
    ok = loc.step(proposal("reserve", {"o": "o1"}, rev=0), operation_id="op-loc", expected_revision=0)
    assert ok.status == "APPLIED"  # reserve does not read clock
    # o2 is SKU b: verified at 1, while only clock and stock[a] / status[o1] moved since → still applies
    assert loc.step(proposal("reserve", {"o": "o2"}, rev=1), operation_id="op-loc-2",
                    expected_revision=1).status == "APPLIED"
    # o3 is SKU a: verified at 1, but stock[a] was written at revision 2 → refused, nothing written
    revision = loc.current_revision()
    stale = loc.step(proposal("reserve", {"o": "o3"}, rev=1), operation_id="op-loc-3", expected_revision=1)
    assert stale.status == "REJECTED" and "stock[a]" in stale.conflict.changed_paths
    assert loc.current_revision() == revision


def test_same_id_same_request_is_replayed_other_params_conflict(svc):
    env = env_for(svc, "ids")
    first = env.step(proposal("reserve", {"o": "o1"}, rev=0), operation_id="op-id", expected_revision=0)
    again = env.step(proposal("reserve", {"o": "o1"}, rev=0), operation_id="op-id", expected_revision=0)
    assert first.status == again.status == "APPLIED" and again.result["replayed"] is True
    with pytest.raises(Conflict):
        env.step(proposal("reserve", {"o": "o2"}, rev=0), operation_id="op-id", expected_revision=0)
    assert [o["operation_id"] for o in export(svc, "ids")["operations"]] == ["op-id"]


def test_kernel_run_with_issuer_and_broker_admits_each_send_at_its_basis(svc, tmp_path):
    keys = tmp_path / "keys.json"
    keys.write_text(json.dumps({"issuer-1": "ab" * 24}))
    receipts = tmp_path / "receipts.json"
    basis = {"query_kind": "ACTION_PRECONDITION", "property_id": None, "verdict": "HOLDS", "scope": "MODEL_INTERNAL",
             "backend": "formal-lab.verifier.z3-bmc@1.1.0", "bound": {}}
    gates = [{"plugin": {"plugin_id": "formal-lab.broker.receipt-issuer", "version": "1.0.0"},
              "config": {"keystore_path": str(keys), "receipts_path": str(receipts), "basis": basis}},
             {"plugin": {"plugin_id": "formal-lab.broker.receipt-gate", "version": "1.0.0"},
              "config": {"keystore_path": str(keys), "receipts_path": str(receipts)}}]
    sc_kw = {"endpoint": svc.endpoint, "tenant": "kernel",
             "env_extra": {"write_token_file": str(svc.write_token_file)}}
    sc = ScenarioManifest.model_validate({**scenario("normal", **sc_kw).model_dump(mode="json"),
                                          "execution_gates": gates})
    from formal_lab_runtime import default_registry, make_manifest, run_local

    reg = default_registry()
    pkg = model_package()
    m = make_manifest(run_id="run_a2_kernel", project_id="orders", scenario=sc, package=pkg, registry=reg,
                      config={"initial_check_horizon": 0})
    result = run_local(m, pkg, reg, stop_after=None)
    ops = export(svc, "kernel")["operations"]
    assert str(result.status) == "SUCCEEDED" and ops and all(o["status"] == "APPLIED" for o in ops)
    decisions = [d for op in result.operations for d in op.decisions]
    assert decisions and all(str(d.verdict) == "ALLOW" for d in decisions)
    ctx = decisions[0].execution
    assert ctx.revision_source == "FRESH" and ctx.session_id and ctx.environment.plugin_id == ENV_ID
    assert str(svc.write_token_file) not in json.dumps(ctx.model_dump(mode="json"))
    token = svc.write_token_file.read_text().strip()
    assert token not in json.dumps(m.model_dump(mode="json"))  # only the credential's path is in the manifest
    assert run  # the scenario helper stays the public entry point for plain runs
