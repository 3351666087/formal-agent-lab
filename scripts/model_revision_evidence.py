#!/usr/bin/env python3
"""Capability negotiation, releases and one real model revision on the order example (phase 3A, G3).

1. IR model (orders): capability report + release with the default config → RELEASED, process completed.
2. Minimal protocol-only driver (examples/external-plugin counter_v1): accurate report (rules / queries / stats
   UNSUPPORTED with reasons); a release that requires GOAL_REACHABILITY is not passed, with the reason.
3. Real revision (orders `deviation`: the service runs station p2 at half speed, the model predicts nominal speed):
   run against the real service → effect differences → revision suggestions + regression cases; the old version is
   REJECTED by the cases, the revised version (`slow[p2] = true`) is RELEASED; a new run on it against the same
   service shows no model difference.
4. Stale basis (D-022): two handlers with round-start observations against the real service — differences caused by
   the other handler's earlier move stay in the trace and produce no suggestion / regression case.
Evidence: docs/execution/evidence/phase3/g3-release.json.

    scripts/in-vm.sh 'uv run --frozen python scripts/model_revision_evidence.py'
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from formal_lab_contracts import ModelSource, RegressionCase, ReleaseConfig
from formal_lab_env.ir_world import truth_model_ir
from formal_lab_example_orders.instance import CASES
from formal_lab_example_orders.lifecycle import ServiceManager
from formal_lab_example_orders.model import model_package
from formal_lab_example_orders.scenarios import EVALUATORS, scenario
from formal_lab_model import build_package
from formal_lab_runtime import default_registry, make_manifest, run_local
from formal_lab_runtime.release import capability_report, check_release

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3") / "g3-release.json"


def run_on(pkg, sc, reg, run_id: str):
    sc = sc.model_copy(update={"model": pkg.ref()})
    m = make_manifest(run_id=run_id, project_id="orders", scenario=sc, package=pkg, registry=reg, seed=1,
                      evaluators=EVALUATORS, config={"initial_check_horizon": 0})
    return run_local(m, pkg, reg)


def differences(res) -> dict:
    compared = [e.payload["comparison"] for e in res.events if str(e.event_type) == "EFFECT_COMPARED"]
    different = [c for c in compared if c["verdict"] == "DIFFERENT"]
    stale = [c for c in different if "basis stale" in (c.get("expected_by") or "")]
    return {"comparisons": len(compared), "different": len(different), "different_stale_basis": len(stale),
            "suggestions": sum(1 for e in res.events if str(e.event_type) == "MODEL_REVISION_SUGGESTED"),
            "regression_cases": sum(1 for e in res.events if str(e.event_type) == "REGRESSION_CASE_CREATED")}


def summary(rec) -> dict:
    return {"status": rec.status, "process_completed": rec.process_completed, "reasons": rec.reasons,
            "checks": [{"kind": str(c.kind), "subject": c.subject, "verdict": c.verdict, "executed": c.executed,
                        "required": c.required, "property_holds": c.property_holds, "claim": c.claim,
                        "backend": c.backend.plugin_id if c.backend else None} for c in rec.checks],
            "regression": [r.model_dump(mode="json") for r in rec.regression], "compiled": [c.stats for c in rec.compiled]}


def main() -> int:
    reg = default_registry()
    t0 = time.time()
    out: dict = {}
    pkg = model_package()

    rep = capability_report(pkg, reg)
    rec, _ = check_release(pkg, reg, config=ReleaseConfig(horizon=4))
    out["ir_model"] = {"features": {f.feature: f.status.value for f in rep.features}, "release": summary(rec)}

    from fal_example_external_plugin.counter_driver import package as counter_package

    cpkg = counter_package()
    crep = capability_report(cpkg, reg)
    plain, _ = check_release(cpkg, reg)
    needs_query, _ = check_release(cpkg, reg, config=ReleaseConfig(required_checks=["TYPE_CHECK", "GOAL_REACHABILITY"]))
    out["minimal_driver"] = {"features": [f.model_dump(mode="json") for f in crep.features],
                             "default_release": summary(plain), "requires_goal_reachability": summary(needs_query)}

    slow = CASES["deviation"]["service"]["slow_stations"]
    with tempfile.TemporaryDirectory() as tmp:
        mgr = ServiceManager(Path(tmp), project="g3-evidence").start()
        try:
            mgr.ready()
            dev = scenario("deviation", endpoint=mgr.endpoint, tenant="g3-old")
            before = run_on(pkg, dev, reg, "run_g3_deviation_v1")
            cases = [RegressionCase.model_validate(e.payload["case"]) for e in before.events
                     if str(e.event_type) == "REGRESSION_CASE_CREATED"]
            suggestion = next((e.payload for e in before.events if str(e.event_type) == "MODEL_REVISION_SUGGESTED"),
                              None)
            ir = truth_model_ir(pkg, {f"slow[{st}]": True for st in slow})  # the modeller's fix
            revised = build_package(ir, package_id=pkg.package_id, version=2,
                                    source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(),
                                                       origin=f"revision: slow{slow} after run_g3_deviation_v1"))
            old_rel, _ = check_release(pkg, reg, cases=cases, config=ReleaseConfig(horizon=4))
            new_rel, _ = check_release(revised, reg, cases=cases, config=ReleaseConfig(horizon=4))
            after = run_on(revised, scenario("deviation", endpoint=mgr.endpoint, tenant="g3-new"), reg,
                           "run_g3_deviation_v2")
            out["revision"] = {
                "service_truth": {"slow_stations": slow}, "before": {"status": before.status.value,
                                                                     **differences(before)},
                "suggestion": {k: suggestion[k] for k in ("action", "state_families", "constants_read")
                               if suggestion and k in suggestion} if suggestion else None,
                "regression_cases": len(cases), "old_version_release": summary(old_rel),
                "revised_version_release": summary(new_rel),
                "after": {"status": after.status.value, **differences(after)}}

            two = scenario("normal", endpoint=mgr.endpoint, tenant="g3-two", two_actors=True, timing="ROUND_START")
            stale = run_on(pkg, two, reg, "run_g3_two_handlers")
            out["stale_basis"] = {"status": stale.status.value, **differences(stale),
                                  "examples": [c["expected_by"] for e in stale.events
                                               if str(e.event_type) == "EFFECT_COMPARED"
                                               for c in [e.payload["comparison"]]
                                               if c["verdict"] == "DIFFERENT"][:3]}
        finally:
            mgr.close()
    rev, st = out["revision"], out["stale_basis"]
    checks = {
        "IR model released, process completed": out["ir_model"]["release"]["status"] == "RELEASED"
                                                and out["ir_model"]["release"]["process_completed"],
        "minimal driver: rules/queries/stats UNSUPPORTED": all(
            f["status"] == "UNSUPPORTED" for f in out["minimal_driver"]["features"]
            if f["feature"] in ("rules", "release.stats", "query.goal_reachability")),
        "minimal driver: default release passes": out["minimal_driver"]["default_release"]["status"] == "RELEASED",
        "minimal driver: required query not passed": out["minimal_driver"]["requires_goal_reachability"]["status"]
                                                     == "REJECTED"
                                                     and not out["minimal_driver"]["requires_goal_reachability"][
                                                         "process_completed"],
        "revision: differences found": rev["before"]["different"] > 0 and rev["regression_cases"] > 0,
        "revision: old REJECTED, revised RELEASED": rev["old_version_release"]["status"] == "REJECTED"
                                                   and rev["revised_version_release"]["status"] == "RELEASED",
        "revision: no model difference after": rev["after"]["different"] - rev["after"]["different_stale_basis"] == 0,
        "stale basis: classified, no suggestion": st["different_stale_basis"] > 0
                                                  and st["suggestions"] == 0 and st["regression_cases"] == 0,
    }
    doc = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "duration_s": round(time.time() - t0, 1),
           "checks": checks, "ok": all(checks.values()), **out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(checks, indent=1, ensure_ascii=False))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
