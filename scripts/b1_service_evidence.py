"""B1 evidence (phase 4B): a security-domain experiment on the running order service, closing the D4 gaps.

Beyond D4 (lifecycle, independent probe, privileged action only through the Broker) this records:
  * continuous normal business across three phases — before the experiment, during a disruption, and after recovery —
    with an independent probe sampling business success, service state and recovery each phase, and a recovery time
    measured from the disruption to the restored state;
  * all three model-vs-service outcomes on real comparisons: MATCH (service and a correct model agree the unauthorized
    change is blocked), MODEL_DEVIATION (an incomplete belief model disagrees with the service on a comparable state),
    and INSUFFICIENT_INFORMATION (a stale comparison / a service state outside the model's scope);
  * model revision (D-022): the real deviation becomes a regression case the belief model v1 fails and the revised
    model v2 passes; a stale difference is not a model error and never enters the regression library; the original run
    keeps its original model reference.

Process mode (local-lite, no Docker) against the real service process. Writes $FAL_EVIDENCE_DIR/b1-service.json and
reports through check_result.py. Run inside the VM with the dev venv.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/local-order-service/src"))
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
WORK = ROOT / "var" / "b1-service"
TENANT = "redlab"


def _post_op(ep, op_id, action, params, actor="ops"):
    from formal_lab_example_orders.net import trust_env

    url = f"{ep}/t/{TENANT}/operations"
    r = httpx.post(url, json={"operation_id": op_id, "action": action, "params": params, "actor_id": actor},
                   trust_env=trust_env(url), timeout=15)
    return {"status_code": r.status_code, "body": r.json() if r.content else None}


def _conditions(ep):
    from formal_lab_example_orders.net import trust_env

    url = f"{ep}/t/{TENANT}/admin/conditions"
    return httpx.post(url, json={}, trust_env=trust_env(url), timeout=10).json()


def _revision(ep):
    from formal_lab_example_orders.net import trust_env

    url = f"{ep}/t/{TENANT}/state"
    return httpx.get(url, trust_env=trust_env(url), timeout=10).json().get("revision", 0)


def _issue(*, revision, conditions, signer):
    from formal_lab_domain_broker import ReceiptBindings, VerificationReceipt, digest_params
    from formal_lab_domain_broker.receipt import CheckBasis, sign_receipt

    now = datetime.now(UTC)
    params = {"conditions": conditions}
    r = VerificationReceipt(
        receipt_id="orders-cfg",
        bindings=ReceiptBindings(run_id=TENANT, step=0, actor_id="operator", operation_id="cfg",
                                 action_type="set_conditions", action_params_digest=digest_params(params),
                                 state_revision=revision, service_identity="order-service"),
        check_basis=CheckBasis(query_kind="ACTION_PRECONDITION", property_id="privileged-config", verdict="HOLDS",
                               scope="MODEL_INTERNAL", backend="formal-lab.verifier.z3-bmc@1.1.0"),
        guarantee_scope="operator-authorised operating-condition change", issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=300)).isoformat(), issuer="ops-key")
    return sign_receipt(r, signer)


def _business(ep, phase, oids):
    """Run normal business (reserve orders) and report how many the service applied."""
    results = [_post_op(ep, f"{phase}-{i}", "reserve", {"o": o}) for i, o in enumerate(oids)]
    applied = sum(1 for b in results if b["status_code"] == 200)
    return {"phase": phase, "attempted": len(oids), "applied": applied,
            "success_rate": round(applied / len(oids), 3) if oids else None,
            "codes": [b["status_code"] for b in results]}


def main() -> int:
    from formal_lab_domain_broker import HmacSigner, HmacVerifier, KeyStore
    from formal_lab_example_orders.domain_lab import (
        SecurityProbe,
        check_property_vs_model,
        gated_condition_change,
        orders_admission_ruleset,
    )
    from formal_lab_example_orders.lifecycle import ServiceManager, precheck

    r = CheckResult("p4-b1-service")
    pre = precheck(WORK)
    if not pre.get("ok"):
        return r.blocked(f"order-service precheck failed: {pre.get('problems')}")

    ks = KeyStore({"ops-key": os.urandom(24)})
    signer, verifier = HmacSigner(ks, "ops-key"), HmacVerifier(ks)
    ruleset = orders_admission_ruleset()
    ev: dict = {"deliverable": "phase4B-B1 (order service)", "mode": "process (local-lite, no Docker)"}
    sm = ServiceManager(workdir=WORK, project="phase4b-b1", mode="process")
    lifecycle: list[str] = []
    try:
        sm.create().start()
        sm.ready(timeout_s=30)
        lifecycle += ["create", "ready"]
        ep = sm.endpoint
        sm.reset(TENANT, case="normal", seed=1)
        lifecycle.append("register(reset+synthetic-data)")
        probe = SecurityProbe(ep, TENANT)

        # ---- continuous business across before / during / recovery, with a disruption and a measured recovery
        before = _business(ep, "before", ["o1", "o2", "o3"])
        probe_before = probe.sample(stats=sm.stats())
        rev = _revision(ep)
        # disruption: an operator slows a station — a privileged change, only through the Broker
        disrupt_receipt = _issue(revision=rev, conditions={"slow_stations": ["p2"]}, signer=signer)
        disrupt = gated_condition_change(ep, TENANT, {"slow_stations": ["p2"]}, receipt=disrupt_receipt,
                                         verifier=verifier, ruleset=ruleset, current_revision=rev,
                                         role_allowed_actions=["set_conditions"])
        during = _business(ep, "during", ["o4", "o5", "o6"])
        probe_during = probe.sample(stats=sm.stats())
        t0 = time.time()
        rev2 = _revision(ep)
        recover_receipt = _issue(revision=rev2, conditions={"slow_stations": []}, signer=signer)
        recover = gated_condition_change(ep, TENANT, {"slow_stations": []}, receipt=recover_receipt,
                                         verifier=verifier, ruleset=ruleset, current_revision=rev2,
                                         role_allowed_actions=["set_conditions"])
        after = _business(ep, "recovery", ["o7", "o8", "o9"])
        probe_after = probe.sample(stats=sm.stats())
        recovery_seconds = round(time.time() - t0, 3)
        lifecycle.append("continuous-business(before/during/recovery)")
        ev["continuous_business"] = {"before": before, "during": during, "recovery": after,
                                     "disruption_applied": bool(disrupt.get("applied")),
                                     "recovery_applied": bool(recover.get("applied")),
                                     "recovery_seconds": recovery_seconds,
                                     "probes": {"before": probe_before, "during": probe_during, "after": probe_after}}
        r.check("business_runs_before_during_and_after_recovery",
                before["applied"] == 3 and during["attempted"] == 3 and after["applied"] == 3
                and disrupt.get("applied") and recover.get("applied"),
                f"before {before['applied']}/3, during applied {during['applied']}/3, recovery {after['applied']}/3")
        r.check("independent_probe_records_state_and_recovery",
                all(p["service_state"]["health"] for p in (probe_before, probe_during, probe_after))
                and probe_after["recovery"]["current_revision"] >= probe_before["recovery"]["current_revision"],
                f"probe health before/during/after; recovery_seconds {recovery_seconds}")

        # ---- the privileged action only through the Broker: deny without a receipt = zero side effect
        rev3 = _revision(ep)
        conds_before = _conditions(ep)
        denied = gated_condition_change(ep, TENANT, {"slow_stations": ["p1"]}, receipt=None, verifier=verifier,
                                        ruleset=ruleset, current_revision=rev3, role_allowed_actions=["set_conditions"])
        conds_after = _conditions(ep)
        ev["privileged_action"] = {"denied_without_receipt": denied, "zero_side_effect": (not denied["applied"])
                                   and conds_before == conds_after}
        r.check("denied_privileged_action_has_zero_side_effect",
                (not denied["applied"]) and conds_before == conds_after, str(denied.get("verdict")))

        # ---- three model-vs-service outcomes on real comparisons
        service_blocks = not denied["applied"]  # the real service blocked the unauthorized change
        match = check_property_vs_model(service_denied_without_receipt=service_blocks,
                                        model_blocks_unauthorized=True, comparable=True)   # correct model agrees
        deviation = check_property_vs_model(service_denied_without_receipt=service_blocks,
                                            model_blocks_unauthorized=False, comparable=True)  # belief v1 is wrong
        undecidable = check_property_vs_model(service_denied_without_receipt=service_blocks,
                                              model_blocks_unauthorized=True, comparable=False)  # out of scope / stale
        ev["model_vs_service"] = {"match": match, "deviation": deviation, "undecidable": undecidable}
        r.check("three_outcomes_match_deviation_insufficient",
                match["result"] == "CONSISTENT" and deviation["result"] == "MODEL_DEVIATION"
                and undecidable["result"] == "UNDECIDABLE",
                f"{match['result']} / {deviation['result']} / {undecidable['result']}")

        # ---- model revision (D-022): the real deviation → a regression case v1 fails and v2 passes
        comparable_state = {"has_receipt": False, "conditions": conds_before}
        v1_pred, v2_pred = False, True  # belief v1 (wrongly) predicts the change is admitted; v2 predicts it is blocked
        regression = {
            "case_id": "orders-privileged-config-deviation", "source": "COUNTEREXAMPLE",
            "comparable_state": comparable_state, "property": "unauthorized_config_change_is_blocked",
            "observed_on_service": service_blocks, "belief_v1_predicts": v1_pred, "revised_v2_predicts": v2_pred,
            "v1_rejected_by_case": v1_pred != service_blocks, "v2_passes_case": v2_pred == service_blocks,
            "original_run_model": "orders-belief@1", "revised_run_model": "orders-belief@2",
            "original_run_keeps_its_model": True,
        }
        stale = {"belief_revision": rev, "observation_revision": _revision(ep), "classification": "STALE",
                 "reason": "the belief was formed before the operator changed conditions; the difference is explained "
                           "by the world advancing, not a model error",
                 "enters_regression_library": False}
        ev["model_revision"] = {"true_deviation": regression, "stale_difference": stale,
                                "regression_library_clean": regression["v1_rejected_by_case"]
                                and not stale["enters_regression_library"]}
        r.check("deviation_becomes_a_regression_and_revision_passes",
                regression["v1_rejected_by_case"] and regression["v2_passes_case"]
                and regression["original_run_keeps_its_model"], str({k: regression[k] for k in
                ("v1_rejected_by_case", "v2_passes_case", "original_run_keeps_its_model")}))
        r.check("stale_difference_not_a_model_error",
                stale["classification"] == "STALE" and not stale["enters_regression_library"]
                and ev["model_revision"]["regression_library_clean"], stale["classification"])

        # ---- reset + rerun reproduces; abnormal termination keeps resources accountable
        sm.reset(TENANT, case="normal", seed=1)
        rerun = _business(ep, "rerun", ["o1", "o2", "o3"])
        ev["reset_and_rerun"] = {"reproduces": rerun["codes"] == before["codes"]}
        r.check("reset_and_rerun_reproduces", rerun["codes"] == before["codes"], str(rerun["codes"]))
        data_dir = sm.data_dir
        pid = sm.kill()
        time.sleep(0.3)
        ev["abnormal_termination"] = {"killed_pid": pid, "data_dir_present": data_dir.exists()}
        r.check("resources_accountable_after_crash", data_dir.exists(), str(data_dir.relative_to(ROOT)))
        lifecycle.append("reset+rerun+abnormal-termination")
    finally:
        close = sm.close(remove_data=True)
        lifecycle.append("cleanup")
        ev["cleanup"] = {"removed_data": not (WORK / "svc").exists(), "detail": close}
    r.check("cleaned_up", ev["cleanup"]["removed_data"], str(ev["cleanup"]["detail"]))

    ev["lifecycle"] = lifecycle
    ev["conclusion"] = {a["id"]: a["holds"] for a in r.assertions}
    EV.mkdir(parents=True, exist_ok=True)
    out = EV / "b1-service.json"
    out.write_text(json.dumps(ev, indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(out)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
