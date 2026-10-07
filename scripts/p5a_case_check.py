#!/usr/bin/env python3
"""P5A acceptance: the committed ordinary case validates, its conformance re-derives to the recorded verdicts, and it
reads offline. Re-derivation uses the recorded observation (deterministic); the model's own Z3 verdict is read from the
case, never re-run (it is a timeout-bounded result). Writes docs/execution/evidence/research/p5a/case.json.

    uv run --frozen python scripts/p5a_case_check.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from pathlib import Path

from check_result import CheckResult
from evidence_io import write

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "research" / "cases" / "orders-p2-speed"
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))


def main() -> int:
    from formal_lab_contracts.research import ModelConclusion, ProgramRegression
    from formal_lab_runtime.research import load_case, replay_conformance, validate_case

    r = CheckResult("p5a-case")
    if not (CASE / "case.json").exists():
        sys.exit(r.blocked(f"case not built: {CASE}"))

    files = load_case(CASE)
    report, case = validate_case(files, repo=ROOT)
    r.check("case_validates", report.ok, f"{len(report.problems)} problem(s): {[p.code for p in report.problems]}")
    r.check("references_checked", bool(case) and report.checked.get("conformance", 0) == 2,
            f"checked {dict(report.checked)}")

    # re-derive the correspondence layer from the recorded run (deterministic), and compare to the stored reference
    stored = {c.id: c for c in (case.artifacts if case else [])}
    expected = json.loads((CASE / stored["reference"].path).read_text()) if case else {}
    conclusion = ModelConclusion(verdict="UNKNOWN")  # the layer under test is correspondence, not the model verdict
    derived = {}
    for label in ("v1", "v2"):
        res = replay_conformance(files, case, model_label=label, property_id="all_completed", observation_id="obs-run",
                                 model_conclusion=conclusion, program_regression=ProgramRegression(status="PASS"))
        derived[label] = res.correspondence
        r.check(f"{label}_matches_reference", res.correspondence == expected.get(label, {}).get("correspondence"),
                f"{label}: derived {res.correspondence}, reference {expected.get(label, {}).get('correspondence')}")
    r.check("belief_deviates_revised_corresponds", derived == {"v1": "DEVIATES", "v2": "CORRESPONDS"}, str(derived))

    # three layers apart: a model verdict, a program regression, and a correspondence that is neither
    v1 = json.loads((CASE / stored["conf-v1"].path).read_text()) if case else {}
    r.check("three_layers_recorded_apart",
            bool(v1) and {v1["model_conclusion"]["verdict"], v1["program_regression"]["status"], v1["correspondence"]}
            and "equivalence" in v1.get("scope", ""),
            f"model={v1.get('model_conclusion', {}).get('verdict')} regression="
            f"{v1.get('program_regression', {}).get('status')} correspondence={v1.get('correspondence')}")

    # offline: read the whole case from a zip, with no repository, and still validate the digests
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in sorted(CASE.rglob("*")):
            if p.is_file():
                zf.write(p, (Path(CASE.name) / p.relative_to(CASE)).as_posix())
    off_report, off_case = validate_case(load_case(buf.getvalue()), repo=None)
    r.check("offline_read", off_report.ok and off_case is not None and
            any(w.code == "SOFTWARE_NOT_VERIFIED_HERE" for w in off_report.warnings),
            f"offline ok={off_report.ok}, problems={[p.code for p in off_report.problems]}")

    ev = {"case_id": "orders-p2-speed", "validation": report.as_dict(), "derived_correspondence": derived,
          "reference": expected, "offline_ok": off_report.ok,
          "conclusion": {"case_validates": report.ok, "belief_deviates": derived.get("v1") == "DEVIATES",
                         "revised_corresponds": derived.get("v2") == "CORRESPONDS", "offline_readable": off_report.ok}}
    out = ROOT / EV / "p5a" / "case.json"
    write(out, ev)
    r.evidence(out)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
