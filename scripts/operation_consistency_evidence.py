#!/usr/bin/env python3
"""Operation consistency on the real order-service process (phase 3A, G2).

Every case drives the actual adapter (OrderServiceEnvironment) through the coordinator, each in its own tenant, and
counts what the *service* recorded (its own operations table), so "sent once" means one row in the business system:

  success           one send, one row
  gate-deny         the inventory gate denies a reservation: no send, no row, a DENY decision on the record
  redelivery        the same step delivered again (same ledger, then a second worker without it): still one row
  id-conflict       same id, other request: refused by the coordinator (ledger) and by the service (409)
  lost-response     the answer is lost after commit: settled by query, one row, never re-sent
  revision-change   the gate allows at revision R, another actor takes the stock before the send: the service's
                    conditional update rejects it; decision, record and service row stay traceable
  two-workers       two workers without a shared ledger send the same operation at once: one row
  restart           the service process dies after committing: after its restart the lookup settles it, one row

Plus a full local-runner run of the gated scenario (safety stock 2). The durable (Temporal) path is covered by
tests/integration/test_operation_consistency_platform.py. Evidence: docs/execution/evidence/phase3/g2-operations.json.

    scripts/in-vm.sh 'uv run --frozen python scripts/operation_consistency_evidence.py'
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
from formal_lab_contracts import (
    ActionProposal,
    ExecutionDecision,
    GateRequest,
    GroundAction,
    ProposalSource,
    capabilities,
    utcnow,
)
from formal_lab_example_orders.env import CAPABILITIES, OrderServiceEnvironment
from formal_lab_example_orders.gates import InventoryGate
from formal_lab_example_orders.lifecycle import ServiceManager
from formal_lab_example_orders.model import model_package
from formal_lab_example_orders.plugins import RULES
from formal_lab_example_orders.scenarios import run, scenario
from formal_lab_runtime import default_registry
from formal_lab_runtime.coordination import Coordinator, InMemoryLedger, SendDecision

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3") / "g2-operations.json"
CAPS = set(CAPABILITIES)
PKG = model_package()


def env_for(mgr: ServiceManager, tenant: str, **cfg) -> OrderServiceEnvironment:
    env = OrderServiceEnvironment({"endpoint": mgr.endpoint, "tenant": tenant, "case": "normal", **cfg})
    env.reset(scenario("normal", endpoint=mgr.endpoint), PKG, run_id=f"run_{tenant.replace('-', '_')}", seed=1)
    return env


def proposal(action: str, params: dict, *, actor: str = "handler", rev: int = 0, step: int = 1) -> ActionProposal:
    return ActionProposal(proposal_id=f"p{step}", run_id="run_g2", step_id=f"s{step}", step=step, actor_id=actor,
                          action=GroundAction(action_type=action, params=params), based_on_revision=rev,
                          source=ProposalSource(kind="RULE", strategy=RULES.ref()), rationale="evidence")


def rows(mgr: ServiceManager, tenant: str, op: str | None = None) -> list[dict]:
    ops = httpx.get(f"{mgr.endpoint}/t/{tenant}/admin/export", timeout=10, trust_env=False).json()["operations"]
    return [o for o in ops if op is None or o["operation_id"] == op]


def submitted(env: OrderServiceEnvironment) -> list[str]:
    st = env.truth_state()
    return sorted(k[len("status["):-1] for k, v in st.items() if k.startswith("status[") and v == "submitted")


def gate_hook(env, gate: InventoryGate, *, before_send=None):
    """The real inventory gate wired like the kernel does (fresh values via observe_paths)."""

    def hook(phase, record, prop):
        paths = gate.paths(prop.action)
        obs = env.observe_paths(prop.actor_id, paths) if paths else None
        values = {f.path: f.value for f in obs.facts if f.path in paths} if obs else {}
        req = GateRequest(run_id="run_g2", step=prop.step, actor_id=prop.actor_id, operation_id=record.operation_id,
                          phase=phase, action=prop.action, proposal_id=prop.proposal_id,
                          based_on_revision=prop.based_on_revision, values=values,
                          values_source="FRESH" if paths else "NONE",
                          values_revision=obs.state_revision if obs else None, request_digest=record.request_digest)
        ans = gate.decide(req)
        d = ExecutionDecision(decision_id=f"{record.operation_id}:gate0:{phase.value.lower()}:{record.attempts}",
                              run_id="run_g2", step=prop.step, actor_id=prop.actor_id,
                              operation_id=record.operation_id, gate=gate.descriptor.ref(), phase=phase,
                              verdict=ans.verdict, reason=ans.reason, conditions=ans.conditions,
                              values_source=req.values_source, checked_at_revision=req.values_revision,
                              request_digest=record.request_digest, at=utcnow())
        if before_send is not None and ans.verdict.value == "ALLOW":
            before_send()
        return SendDecision(ans.verdict.value == "ALLOW", ans.reason, [d])

    return hook


def effects(record) -> list[str]:
    return [f"{t.state.value}:{t.effect.value}" for t in record.transitions]


def main() -> int:
    cases: dict[str, dict] = {}
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        mgr = ServiceManager(Path(tmp), project="g2-evidence", supervise=True).start()
        try:
            mgr.ready()

            # success: one send, one row
            env = env_for(mgr, "success")
            o = submitted(env)[0]
            res = Coordinator(env, CAPS, InMemoryLedger()).execute(proposal("reserve", {"o": o}), "op-success",
                                                                    run_id="run_g2", step=1)
            cases["success"] = {"outcome": res.outcome.status.value, "service_rows": len(rows(mgr, "success",
                                "op-success")), "transitions": effects(res.record)}

            # gate-deny: no send, no row
            env = env_for(mgr, "gate-deny")
            o = submitted(env)[0]
            gate = InventoryGate(PKG, min_stock_after=99)
            res = Coordinator(env, CAPS, InMemoryLedger(), gate=gate_hook(env, gate)).execute(
                proposal("reserve", {"o": o}), "op-denied", run_id="run_g2", step=1)
            cases["gate-deny"] = {"outcome": res.outcome.status.value, "reason": res.outcome.result["reason"],
                                  "decision": res.record.decisions[0].model_dump(mode="json"),
                                  "service_rows": len(rows(mgr, "gate-deny", "op-denied")),
                                  "service_lookup": env.query_operation("op-denied"), "transitions": effects(res.record)}

            # redelivery: same ledger (reuse), then a second worker without it (service deduplicates)
            env = env_for(mgr, "redelivery")
            o = submitted(env)[0]
            ledger = InMemoryLedger()
            first = Coordinator(env, CAPS, ledger).execute(proposal("reserve", {"o": o}), "op-redeliver",
                                                          run_id="run_g2", step=1)
            again = Coordinator(env, CAPS, ledger).execute(proposal("reserve", {"o": o}), "op-redeliver",
                                                          run_id="run_g2", step=1)
            other = Coordinator(env, CAPS, InMemoryLedger()).execute(proposal("reserve", {"o": o}), "op-redeliver",
                                                                    run_id="run_g2", step=1)
            cases["redelivery"] = {"first": first.outcome.status.value, "same_ledger_reused": again.reused,
                                   "second_worker_answer_replayed": "stored answer re-sent" in (
                                       other.outcome.evidence[0].note or ""),
                                   "service_rows": len(rows(mgr, "redelivery", "op-redeliver")),
                                   "transitions_same_ledger": effects(again.record)}

            # id-conflict: ledger level and service level
            env = env_for(mgr, "conflict")
            o1, o2 = submitted(env)[:2]
            ledger = InMemoryLedger()
            Coordinator(env, CAPS, ledger).execute(proposal("reserve", {"o": o1}), "op-conflict", run_id="run_g2",
                                                  step=1)
            at_ledger = Coordinator(env, CAPS, ledger).execute(proposal("reserve", {"o": o2}), "op-conflict",
                                                              run_id="run_g2", step=1)
            at_service = Coordinator(env, CAPS, InMemoryLedger()).execute(proposal("reserve", {"o": o2}),
                                                                         "op-conflict", run_id="run_g2", step=1)
            recorded = rows(mgr, "conflict", "op-conflict")
            cases["id-conflict"] = {"ledger_conflict": at_ledger.conflict, "ledger_sent": False,
                                    "service_answer": at_service.outcome.status.value,
                                    "service_error": at_service.outcome.error.code.value,
                                    "service_rows": len(recorded), "row_params": recorded[0]["params"]}

            # lost-response: committed, answer held past the client timeout → query → one row
            env = env_for(mgr, "lost", timeout_s=0.5)
            httpx.post(f"{mgr.endpoint}/t/lost/admin/conditions", json={"hold_after_commit_ms": 1500, "hold_every": 1},
                       timeout=10, trust_env=False)
            o = submitted(env)[0]
            res = Coordinator(env, CAPS, InMemoryLedger()).execute(proposal("reserve", {"o": o}), "op-lost",
                                                                    run_id="run_g2", step=1)
            httpx.post(f"{mgr.endpoint}/t/lost/admin/conditions", json={"hold_after_commit_ms": 0}, timeout=10,
                       trust_env=False)
            cases["lost-response"] = {"state": res.record.state.value, "outcome": res.outcome.status.value,
                                      "service_rows": len(rows(mgr, "lost", "op-lost")),
                                      "transitions": effects(res.record)}

            # revision-change: allowed at R, another actor takes the stock, then the send is rejected by the service
            env = env_for(mgr, "revchange", case="shortage")  # little stock: one reservation can starve another
            g0 = InventoryGate(PKG, 0)
            sku, qty = g0.sku_of, g0.qty

            def starving() -> list[tuple[str, str]]:  # (ours, competitor): each fits alone, not both
                st = env.truth_state()
                return [(a, b) for a in submitted(env) for b in submitted(env)
                        if a != b and sku[a] == sku[b] and qty[a] <= st[f"stock[{sku[a]}]"]
                        and qty[b] <= st[f"stock[{sku[b]}]"] < qty[a] + qty[b]]

            for i in range(12):  # let orders arrive until such a pair is waiting
                if starving():
                    break
                httpx.post(f"{mgr.endpoint}/t/revchange/operations", trust_env=False, timeout=10, json={
                    "operation_id": f"op-tick-{i}", "actor_id": "clock", "action": "tick", "params": {}})
            pair = starving()[0]

            def competitor() -> None:  # another handler reserves the same SKU between the decision and the send
                Coordinator(env, CAPS, InMemoryLedger()).execute(
                    proposal("reserve", {"o": pair[1]}, actor="handler_b"), "op-competitor", run_id="run_g2", step=1)

            try:
                res = Coordinator(env, CAPS, InMemoryLedger(), gate=gate_hook(env, InventoryGate(PKG, 0),
                                                                              before_send=competitor)).execute(
                    proposal("reserve", {"o": pair[0]}), "op-revchange", run_id="run_g2", step=1)
                d = res.record.decisions[0]
                cases["revision-change"] = {"decision": d.verdict.value, "checked_at_revision": d.checked_at_revision,
                                            "outcome": res.outcome.status.value,
                                            "service_revision_before": res.outcome.revision_before,
                                            "service_reason": res.outcome.result.get("reason"),
                                            "service_rows": len(rows(mgr, "revchange", "op-revchange"))}
            except StopIteration:
                cases["revision-change"] = {"skipped": "no two submitted orders share a SKU in this instance"}

            # two-workers: two coordinators without a shared ledger send the same operation at once
            env_a = env_for(mgr, "race")  # worker A's adapter; worker B attaches its own to the same session
            env_b = OrderServiceEnvironment({"endpoint": mgr.endpoint, "tenant": "race", "case": "normal"})
            env_b.attach(env_a.snapshot())
            o = submitted(env_a)[0]
            answers: list = []

            def worker(env) -> None:
                answers.append(Coordinator(env, CAPS, InMemoryLedger()).execute(
                    proposal("reserve", {"o": o}), "op-race", run_id="run_g2", step=1))

            threads = [threading.Thread(target=worker, args=(env_a,)), threading.Thread(target=worker, args=(env_b,))]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            cases["two-workers"] = {"answers": sorted(a.outcome.status.value for a in answers),
                                    "replayed": sum("re-sent" in (a.outcome.evidence[0].note or "") for a in answers),
                                    "service_rows": len(rows(mgr, "race", "op-race"))}

            # restart: the service dies right after committing; the lookup after its restart settles it
            env = env_for(mgr, "restart", timeout_s=2.0, ready_timeout_s=30.0)
            o = submitted(env)[0]
            seq = len(rows(mgr, "restart")) + 1
            httpx.post(f"{mgr.endpoint}/t/restart/admin/conditions", json={"crash_after_op": seq}, timeout=10,
                       trust_env=False)
            res = Coordinator(env, CAPS, InMemoryLedger()).execute(proposal("reserve", {"o": o}), "op-restart",
                                                                    run_id="run_g2", step=1)
            cases["restart"] = {"state": res.record.state.value, "outcome": res.outcome.status.value,
                                "service_rows": len(rows(mgr, "restart", "op-restart")),
                                "service_restarts": mgr.restarts if hasattr(mgr, "restarts") else None,
                                "transitions": effects(res.record)}

            # full local-runner run with the gate (safety stock 2)
            res = run("normal", backend="service", seed=1, endpoint=mgr.endpoint, tenant="gated-run",
                      registry=default_registry(), run_id="run_g2_gated", safety_stock=2)
            decisions = [e.payload["decision"] for e in res.events if str(e.event_type) == "EXECUTION_DECIDED"]
            denied_ops = sorted({d["operation_id"] for d in decisions if d["verdict"] == "DENY"})
            service_ids = {r["operation_id"] for r in rows(mgr, "gated-run")}
            cases["local-runner-gated-run"] = {
                "status": res.status.value, "reason": res.reason,
                "decisions": {"ALLOW": sum(d["verdict"] == "ALLOW" for d in decisions),
                              "DENY": len(denied_ops)},
                "denied_operations_in_service": sorted(service_ids & set(denied_ops)),
                "operations_recorded": len(res.operations), "service_rows": len(service_ids),
                "sent_operations": sum(1 for op in res.operations if any(t.effect and t.effect.value == "SEND"
                                                                         for t in op.transitions))}
        finally:
            mgr.close()
    checks = {
        "success once": cases["success"]["service_rows"] == 1,
        "gate deny: zero sends": cases["gate-deny"]["service_rows"] == 0 and cases["gate-deny"]["service_lookup"] is None,
        "redelivery: one row": cases["redelivery"]["service_rows"] == 1 and cases["redelivery"]["same_ledger_reused"],
        "id conflict refused twice": bool(cases["id-conflict"]["ledger_conflict"])
                                     and cases["id-conflict"]["service_error"] == "CONFLICT"
                                     and cases["id-conflict"]["service_rows"] == 1,
        "lost response: one row": cases["lost-response"]["service_rows"] == 1
                                  and cases["lost-response"]["state"] == "RECONCILED",
        "revision change: allowed at R, rejected by the service at R+1":
            cases["revision-change"].get("decision") == "ALLOW" and cases["revision-change"].get("outcome") == "REJECTED"
            and cases["revision-change"]["checked_at_revision"] < cases["revision-change"]["service_revision_before"]
            and cases["revision-change"]["service_rows"] == 1,
        "two workers: one row": cases["two-workers"]["service_rows"] == 1,
        "restart: one row": cases["restart"]["service_rows"] == 1,
        "gated run: denied never sent": not cases["local-runner-gated-run"]["denied_operations_in_service"]
                                        and cases["local-runner-gated-run"]["decisions"]["DENY"] > 0,
    }
    doc = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "duration_s": round(time.time() - t0, 1),
           "service": "examples/local-order-service (real process, SQLite tenant per case)",
           "capabilities": sorted(CAPS), "idempotent_step": capabilities.ENV_IDEMPOTENT_STEP in CAPS,
           "checks": checks, "ok": all(checks.values()), "cases": cases}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(checks, indent=1, ensure_ascii=False))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
