#!/usr/bin/env python3
"""P5B acceptance: the committed tenant-isolation case validates, and each conformance re-derives — offline, from the
stored observation — to the recorded verdict (defect DEVIATES, fix CORRESPONDS, partial UNKNOWN: the three result
classes). The model's own Z3 verdict is read from the case, not re-run. Writes
docs/execution/evidence/research/p5b/case.json.

    uv run --frozen python scripts/p5b_case_check.py
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
CASE = ROOT / "research" / "cases" / "orders-tenant-isolation"
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))


def main() -> int:
    from formal_lab_contracts.research import ConformanceItem
    from formal_lab_example_orders.research_isolation import derive_items
    from formal_lab_runtime.research import decide_correspondence, load_case, validate_case

    r = CheckResult("p5b-case")
    if not (CASE / "case.json").exists():
        sys.exit(r.blocked(f"case not built: {CASE}"))

    files = load_case(CASE)
    report, case = validate_case(files, repo=ROOT)
    r.check("case_validates", report.ok, f"{len(report.problems)} problem(s): {[p.code for p in report.problems]}")
    r.check("references_checked", bool(case) and report.checked.get("conformance", 0) == 3,
            f"checked {dict(report.checked)}")

    art = {a.id: a for a in (case.artifacts if case else [])}
    reference = json.loads((CASE / art["reference"].path).read_text()) if case else {}
    derived = {}
    for conf_id, key in (("conf-defect", "defect"), ("conf-fix", "fix"), ("conf-partial", "partial")):
        conf = json.loads((CASE / art[conf_id].path).read_text())
        obs_id = conf["program_observations"][0]["artifact_id"]
        observation = json.loads((CASE / art[obs_id].path).read_text())
        items = [ConformanceItem(**d) for d in derive_items(observation)]
        status, _ = decide_correspondence(items, has_observation=True)
        derived[key] = status
        r.check(f"{key}_rederives", status == conf["correspondence"] == reference.get(key, {}).get("correspondence"),
                f"{key}: re-derived {status}, stored {conf['correspondence']}, "
                f"reference {reference.get(key, {}).get('correspondence')}")
    r.check("three_result_classes", derived == {"defect": "DEVIATES", "fix": "CORRESPONDS", "partial": "UNKNOWN"},
            str(derived))

    # three layers apart on the defect result
    defect = json.loads((CASE / art["conf-defect"].path).read_text())
    r.check("three_layers_recorded_apart",
            defect["model_conclusion"]["verdict"] == "NO_WITNESS_WITHIN_BOUND"
            and defect["program_regression"]["status"] == "PASS" and defect["correspondence"] == "DEVIATES"
            and "equivalence" in defect.get("scope", ""),
            f"model={defect['model_conclusion']['verdict']} regression={defect['program_regression']['status']} "
            f"correspondence={defect['correspondence']}")

    # offline: read the whole case from a zip, no repository, digests still check
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in sorted(CASE.rglob("*")):
            if p.is_file():
                zf.writestr((Path(CASE.name) / p.relative_to(CASE)).as_posix(), p.read_bytes())
    off_report, off_case = validate_case(load_case(buf.getvalue()), repo=None)
    r.check("offline_read", off_report.ok and off_case is not None
            and any(w.code == "SOFTWARE_NOT_VERIFIED_HERE" for w in off_report.warnings),
            f"offline ok={off_report.ok}, problems={[p.code for p in off_report.problems]}")

    ev = {"case_id": "orders-tenant-isolation", "validation": report.as_dict(), "derived_correspondence": derived,
          "reference": reference, "offline_ok": off_report.ok,
          "conclusion": {"case_validates": report.ok, "defect_deviates": derived.get("defect") == "DEVIATES",
                         "fix_corresponds": derived.get("fix") == "CORRESPONDS",
                         "partial_unknown": derived.get("partial") == "UNKNOWN", "offline_readable": off_report.ok}}
    out = ROOT / EV / "p5b" / "case.json"
    write(out, ev)
    r.evidence(out)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
