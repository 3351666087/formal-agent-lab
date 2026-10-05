"""D4 evidence: a security-domain experiment on the running order service, through its whole lifecycle.

From an empty work directory (process mode, local-lite — no Docker), in order:
  create → ready → register the lab (tenant, synthetic data) → normal business runs → security probe →
  a domain-privileged action only through the D2 Broker (denied without a receipt = zero side effect; allowed with one)
  → simulator comparison on a comparable state → export → reset → a second run reproduces → abnormal termination
  (kill mid-run) with a resource check → cleanup.

Everything runs against the real service process; the probe reads the service itself, not the agent's view. Writes
$FAL_EVIDENCE_DIR/d4-service-lab.json (default docs/execution/evidence/phase3).

Run: scripts/in-vm.sh 'export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/formal-agent-lab; cd <repo>; uv run --no-sync python scripts/d4_service_lab_evidence.py'
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from evidence_io import write as write_evidence
from formal_lab_domain_broker import HmacSigner, HmacVerifier, KeyStore, VerificationReceipt, digest_params
from formal_lab_domain_broker.receipt import CheckBasis, ReceiptBindings, sign_receipt
from formal_lab_example_orders.domain_lab import (
    SecurityProbe,
    check_property_vs_model,
    gated_condition_change,
    orders_admission_ruleset,
)
from formal_lab_example_orders.lifecycle import ServiceManager, precheck
from formal_lab_example_orders.net import trust_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3") / "d4-service-lab.json"
WORK = ROOT / "var" / "d4-lab"
TENANT = "redlab"


def _post_op(endpoint: str, tenant: str, op_id: str, action: str, params: dict, actor="ops") -> dict:
    url = f"{endpoint}/t/{tenant}/operations"
    r = httpx.post(url, json={"operation_id": op_id, "action": action, "params": params, "actor_id": actor},
                   trust_env=trust_env(url), timeout=15)
    return {"status_code": r.status_code, "body": r.json()}


def _conditions(endpoint: str, tenant: str) -> dict:
    # the service's operating conditions, through its read-only endpoint (no write, unlike POSTing an empty update)
    url = f"{endpoint}/t/{tenant}/admin/conditions"
    return httpx.get(url, trust_env=trust_env(url), timeout=10).json()


def _issue(*, revision: int, conditions: dict, signer) -> VerificationReceipt:
    now = datetime.now(UTC)
    params = {"conditions": conditions}
    r = VerificationReceipt(
        receipt_id="orders-cfg", bindings=ReceiptBindings(
            run_id=TENANT, step=0, actor_id="operator", operation_id="cfg", action_type="set_conditions",
            action_params_digest=digest_params(params), state_revision=revision, service_identity="order-service"),
        check_basis=CheckBasis(query_kind="ACTION_PRECONDITION", property_id="privileged-config", verdict="HOLDS",
                               scope="MODEL_INTERNAL", backend="formal-lab.verifier.z3-bmc@1.1.0"),
        guarantee_scope="operator-authorised operating-condition change", issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=300)).isoformat(), issuer="ops-key")
    return sign_receipt(r, signer)


def main() -> int:
    ks = KeyStore({"ops-key": os.urandom(24)})
    signer, verifier = HmacSigner(ks, "ops-key"), HmacVerifier(ks)
    ruleset = orders_admission_ruleset()
    ev: dict = {"deliverable": "phase3B-D4", "mode": "process (local-lite, no Docker)"}

    pre = precheck(WORK)
    ev["precheck"] = {"ok": pre.get("ok"), "cpus": pre.get("cpus"), "disk_free_mb": pre.get("disk_free_mb")}
    if not pre.get("ok"):
        ev["status"] = "BLOCKED"
        ev["reason"] = pre.get("problems")
        _write(ev)
        return 0

    sm = ServiceManager(workdir=WORK, project="phase3b-d4", mode="process")
    lifecycle: list[str] = []
    try:
        sm.create().start()
        ready = sm.ready(timeout_s=30)
        lifecycle += ["create", "ready"]
        ep = sm.endpoint
        ev["environment"] = {"identity": "order-service", "endpoint": ep, "project": "phase3b-d4",
                             "ready": ready.get("status"), "test_identity": TENANT}

        sm.reset(TENANT, case="normal", seed=1)  # synthetic data + reset condition
        lifecycle.append("register(reset+synthetic-data)")
        probe = SecurityProbe(ep, TENANT)

        # normal business runs
        business = [_post_op(ep, TENANT, f"op-{i}", "reserve", {"o": oid}) for i, oid in enumerate(["o1", "o2", "o3"])]
        ev["normal_business"] = {"reserved": [b["status_code"] for b in business],
                                 "applied": sum(1 for b in business if b["status_code"] == 200)}
        lifecycle.append("normal-business")
        probe_before = probe.sample(stats=sm.stats())

        # domain-privileged action ONLY through the Broker
        rev = _get_revision(ep)
        conds = {"slow_stations": ["p2"]}
        before = _conditions(ep, TENANT)
        denied = gated_condition_change(ep, TENANT, conds, receipt=None, verifier=verifier, ruleset=ruleset,
                                        current_revision=rev, role_allowed_actions=["set_conditions"])
        after_denied = _conditions(ep, TENANT)
        receipt = _issue(revision=rev, conditions=conds, signer=signer)
        allowed = gated_condition_change(ep, TENANT, conds, receipt=receipt, verifier=verifier, ruleset=ruleset,
                                         current_revision=rev, role_allowed_actions=["set_conditions"])
        after_allowed = _conditions(ep, TENANT)
        applied_change = bool(allowed.get("applied")) and "p2" in (after_allowed.get("slow_stations") or [])
        ev["contract_action_via_broker"] = {
            "denied_without_receipt": denied,
            "conditions_before": before, "conditions_after_deny": after_denied, "conditions_after_allow": after_allowed,
            "zero_side_effect_on_service": (not denied["applied"]) and (before == after_denied),
            "allowed_with_receipt": allowed, "conditions_changed_after_allow": applied_change,
        }
        lifecycle.append("broker-gated-privileged-action")

        # simulator comparison on a comparable state: what the service did (its own conditions, read back) against what
        # the admission model decided (the broker's verdict on the same request) — both sides observed, not assumed
        ev["simulator_comparison"] = {
            "authorized": check_property_vs_model(service_denied_without_receipt=not applied_change,
                                                  model_blocks_unauthorized=allowed.get("verdict") != "ALLOW",
                                                  comparable=True),
            "unauthorized": check_property_vs_model(service_denied_without_receipt=before == after_denied,
                                                    model_blocks_unauthorized=denied.get("verdict") == "DENY",
                                                    comparable=True),
            "out_of_scope": check_property_vs_model(service_denied_without_receipt=before == after_denied,
                                                    model_blocks_unauthorized=denied.get("verdict") == "DENY",
                                                    comparable=False),
        }

        probe_after = probe.sample(stats=sm.stats())
        exported = httpx.get(f"{ep}/t/{TENANT}/admin/export", trust_env=trust_env(ep), timeout=10).json()
        lifecycle.append("probe+export")

        # reset + second run reproduces
        sm.reset(TENANT, case="normal", seed=1)
        rerun = [_post_op(ep, TENANT, f"re-{i}", "reserve", {"o": oid}) for i, oid in enumerate(["o1", "o2", "o3"])]
        probe_reset = probe.sample(stats=sm.stats())
        ev["reset_and_rerun"] = {
            "second_run_applied": sum(1 for b in rerun if b["status_code"] == 200),
            "reproduces_first_run": [b["status_code"] for b in rerun] == [b["status_code"] for b in business],
            "recovery": probe_reset["recovery"],
        }
        lifecycle.append("reset+rerun")

        ev["probes"] = {"before": probe_before, "after": probe_after, "after_reset": probe_reset}
        ev["export_size"] = len(json.dumps(exported))

        # abnormal termination: kill the service mid-life, then check resources still owned & accountable
        data_dir = sm.data_dir
        pid = sm.kill()
        time.sleep(0.3)
        ev["abnormal_termination"] = {
            "killed_pid": pid, "process_alive": _pid_alive(pid),
            "data_dir_present": data_dir.exists(), "data_dir": str(data_dir.relative_to(ROOT)),
            "resources_accountable": data_dir.exists(),  # the project's data survives a crash for inspection
        }
        lifecycle.append("abnormal-termination+resource-check")
    finally:
        close = sm.close(remove_data=True)
        lifecycle.append("cleanup")
        ev["cleanup"] = {"removed_data": not (WORK / "svc").exists(), "detail": close}

    ev["lifecycle"] = lifecycle
    ev["container_vs_vm_boundary"] = (
        "process mode (local-lite): the service is a loopback child process in this VM; host/VM management stays in the "
        "ServiceManager lifecycle component. compose mode (local-services) would run it as a Docker container labelled "
        "with the project; cleanup removes exactly this project's process/containers/volumes, never another project's.")
    ev["conclusion"] = {
        "full_lifecycle": lifecycle,
        "normal_business_and_domain_experiment": ev["normal_business"]["applied"] == 3,
        "contract_action_only_via_broker": ev["contract_action_via_broker"]["zero_side_effect_on_service"]
        and ev["contract_action_via_broker"]["conditions_changed_after_allow"],
        "denied_action_never_reached_service": not ev["contract_action_via_broker"]["denied_without_receipt"]["applied"],
        # the probe reads the service itself: it sees the privileged change only after the broker allowed it
        "probes_independent": all(p["access"]["endpoint"] == ep and p["service_state"]["health"] is not None
                                  for p in ev["probes"].values())
        and "p2" not in ((ev["probes"]["before"].get("config") or {}).get("slow_stations") or [])
        and "p2" in ((ev["probes"]["after"].get("config") or {}).get("slow_stations") or []),
        "reset_reproduces": ev["reset_and_rerun"]["reproduces_first_run"],
        "resources_accountable_after_crash": ev["abnormal_termination"]["resources_accountable"],
        "cleaned_up": ev["cleanup"]["removed_data"],
        "simulator_comparison_recorded": ev["simulator_comparison"]["authorized"]["result"] == "CONSISTENT"
        and ev["simulator_comparison"]["unauthorized"]["result"] == "CONSISTENT"
        and ev["simulator_comparison"]["out_of_scope"]["result"] == "UNDECIDABLE",
    }
    _write(ev)
    print(f"  lifecycle: {' → '.join(lifecycle)}")
    print(f"  business applied={ev['normal_business']['applied']}/3 | broker deny zero-side-effect="
          f"{ev['contract_action_via_broker']['zero_side_effect_on_service']} allow-applied="
          f"{ev['contract_action_via_broker']['conditions_changed_after_allow']}")
    print(f"  reset reproduces={ev['reset_and_rerun']['reproduces_first_run']} | "
          f"crash resources accountable={ev['abnormal_termination']['resources_accountable']} | "
          f"cleaned={ev['cleanup']['removed_data']}")
    return 0


def _get_revision(endpoint: str) -> int:
    url = f"{endpoint}/t/{TENANT}/state"
    return httpx.get(url, trust_env=trust_env(url), timeout=10).json().get("revision", 0)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _write(ev: dict) -> None:
    write_evidence(OUT, ev)  # sets conclusion.offline_readable from reading the written file back
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
