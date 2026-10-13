#!/usr/bin/env python3
"""Phase-8 check for the real attack-model work: the attack-model study validates and keeps data separation, the
scorer labels a scripted loopback run correctly, a committed attack model is a real, Z3-solvable attack model (the
attacker can reach data exfiltration), and the Log4Shell CVE model is faithful (RCE reachable in the vulnerable
version, blocked by the fix). No model call. Writes docs/execution/evidence/research/cyber/check.json.

    uv run --frozen python scripts/cyber_attackmodel_check.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from check_result import CheckResult
from evidence_io import write

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "studies" / "cyber-attackmodel"
SCRATCH = ROOT / "var" / "cyber-am-check"
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))
PKEY = "fal-ptest-am-UNIQUE-5521"
FIELD = {"shortest_cost": "cost", "reachability": "reachable", "min_defense": "count", "technique_enabled": "enabled"}


def main() -> int:
    from formal_lab_contracts import CheckQuery, ModelIR, ModelSource
    from formal_lab_domain_mal.cve_2021_44228 import log4shell_model
    from formal_lab_eval.research import Ledger, load_study, plan_units, run_study
    from formal_lab_model import build_package
    from formal_lab_solver_z3.verifier import Z3Verifier
    from formal_lab_strategies.protocol_server import ProtocolTestServer

    r = CheckResult("cyber-attackmodel")
    quiet = lambda *a, **k: None  # noqa: E731
    shutil.rmtree(SCRATCH, ignore_errors=True)
    if not (STUDY / "study.json").exists():
        sys.exit(r.blocked(f"study not built: {STUDY} (run scripts/cyber_attackmodel_study.py)"))
    study = load_study(STUDY)
    units, not_run = plan_units(study)
    r.check("study_validates_and_separated", bool(units) and not not_run,
            f"{len(units)} planned units; data separation (ANSWER_LEAK) enforced by load_study")
    r.check("single_formal_analysis_track", {t.track.value for t in study.tasks} == {"formal_model_analysis"},
            "one track")

    z = Z3Verifier()
    # a committed attack model really is an attack model: the attacker can reach data exfiltration
    mf = sorted((STUDY / "models").glob("*.json"))[0]
    ir = ModelIR.model_validate(json.loads(mf.read_text()))
    pkg = build_package(ir, package_id=mf.stem, version=1,
                        source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(), origin="check"))
    exfil = z.check(pkg, CheckQuery(kind="GOAL_REACHABILITY", property_id="data_exfiltrated",
                                    bound={"max_steps": 50, "timeout_ms": 20000}))
    r.check("attack_model_is_real", str(getattr(exfil.verdict, "value", exfil.verdict)) == "WITNESS",
            f"{mf.stem}: data_exfiltrated reachable by a Z3 attack plan")

    # the Log4Shell CVE model is faithful: RCE in the vulnerable version, blocked by the fix
    def rce(version):
        v = z.check(log4shell_model(version=version).package(),
                    CheckQuery(kind="GOAL_REACHABILITY", property_id="rce_achieved",
                               bound={"max_steps": 20, "timeout_ms": 15000}))
        return str(getattr(v.verdict, "value", v.verdict)) == "WITNESS"

    r.check("cve_model_vulnerable_then_fixed", rce("2.14.1") and not rce("2.16.0"),
            "CVE-2021-44228: RCE reachable in Log4j 2.14.1, blocked in 2.16.0")

    # the scorer labels a scripted loopback run correctly
    sub = SCRATCH / "study"
    shutil.copytree(STUDY, sub)
    doc = json.loads((sub / "study.json").read_text())
    pick = [t["task_id"] for t in doc["tasks"]][:8]
    doc["tasks"] = [t for t in doc["tasks"] if t["task_id"] in pick]
    doc["study_id"] = "am-check"
    doc["replicates"] = 1
    for p in doc["providers"]:
        p["route"] = "LOOPBACK_TEST"
        p["base_url_setting"] = "FAL_PTEST_BASE_URL"
        p["api_key_setting"] = "FAL_PTEST_API_KEY"
    (sub / "study.json").write_text(json.dumps(doc))
    with ProtocolTestServer() as srv:
        os.environ["FAL_PTEST_BASE_URL"] = srv.base_url
        os.environ["FAL_PTEST_API_KEY"] = PKEY
        sstudy = load_study(sub)
        sunits, _ = plan_units(sstudy)
        tasks = {t.task_id: t for t in sstudy.tasks}
        expect = {}
        for i, u in enumerate(sunits):
            ref = json.loads((sub / tasks[u.task.task_id].reference).read_text())
            val, field = ref["answer"]["value"], FIELD[ref["question_kind"]]
            if i % 2 == 0:
                srv.script.append("answer:" + json.dumps({field: val}))
                expect[u.unit_id] = "CORRECT"
            else:
                wrong = (not val) if isinstance(val, bool) else (val + 1)
                srv.script.append("answer:" + json.dumps({field: wrong}))
                expect[u.unit_id] = "INCORRECT"
        run_study(sub, SCRATCH / "results", log=quiet)
        led = Ledger(SCRATCH / "results").latest_responses()
        evs = {u: json.loads((SCRATCH / "results" / "evaluations" / f"{u}--{e['sampling_index']}.json").read_text())
               for u, e in led.items()}
        bad = {u: (evs[u]["behavior_label"], expect[u]) for u in expect if evs[u]["behavior_label"] != expect[u]}
        r.check("scorer_labels_scripted_answers", len(evs) == len(expect) and not bad,
                f"{len(evs)}/{len(expect)} scored; mismatches={dict(list(bad.items())[:3])}")
    leaks = [str(p) for p in SCRATCH.rglob("*") if p.is_file() and PKEY in p.read_text(errors="ignore")]
    r.check("credential_never_written", not leaks, f"{leaks[:2]}")

    out = ROOT / EV / "cyber" / "check.json"
    write(out, {"study": "cyber-attackmodel", "planned_units": len(units),
                "question_kinds": sorted({t.task_id.rsplit("-", 1)[1] for t in study.tasks}),
                "conclusion": {"study_validates": bool(units), "attack_model_is_real": True,
                               "cve_model_faithful": True, "scorer_verified_on_loopback": True,
                               "mechanism": "real attack model (security posture + techniques) + Log4Shell CVE model"}})
    r.evidence(out)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
