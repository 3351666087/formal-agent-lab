#!/usr/bin/env python3
"""P7-01 case acceptance: the committed held-out case validates, its conformance re-derives offline to the recorded
verdicts (defect DEVIATES, fix CORRESPONDS), and it reads offline. Writes
docs/execution/evidence/research/p7/case.json.

    uv run --frozen python scripts/p7_case_check.py
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
CASE = ROOT / "research" / "cases" / "ratelimit-token-bucket"
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))


def main() -> int:
    from formal_lab_contracts.research import ConformanceItem
    from formal_lab_example_orders.research_ratelimit import derive_items
    from formal_lab_runtime.research import decide_correspondence, load_case, validate_case

    r = CheckResult("p7-case")
    if not (CASE / "case.json").exists():
        sys.exit(r.blocked(f"case not built: {CASE}"))
    files = load_case(CASE)
    report, case = validate_case(files, repo=ROOT)
    r.check("case_validates", report.ok, f"{len(report.problems)} problem(s): {[p.code for p in report.problems]}")
    r.check("references_checked", bool(case) and report.checked.get("conformance", 0) == 2, f"{dict(report.checked)}")

    art = {a.id: a for a in (case.artifacts if case else [])}
    reference = json.loads((CASE / art["reference"].path).read_text()) if case else {}
    derived = {}
    for conf_id, key in (("conf-defect", "defect"), ("conf-fix", "fix")):
        conf = json.loads((CASE / art[conf_id].path).read_text())
        obs_id = conf["program_observations"][0]["artifact_id"]
        observation = json.loads((CASE / art[obs_id].path).read_text())
        items = [ConformanceItem(**d) for d in derive_items(observation)]
        status, _ = decide_correspondence(items, has_observation=True)
        derived[key] = status
        r.check(f"{key}_rederives", status == conf["correspondence"] == reference.get(key, {}).get("correspondence"),
                f"{key}: re-derived {status}, stored {conf['correspondence']}")
    r.check("defect_deviates_fix_corresponds", derived == {"defect": "DEVIATES", "fix": "CORRESPONDS"}, str(derived))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in sorted(CASE.rglob("*")):
            if p.is_file():
                zf.writestr((Path(CASE.name) / p.relative_to(CASE)).as_posix(), p.read_bytes())
    off_report, off_case = validate_case(load_case(buf.getvalue()), repo=None)
    r.check("offline_read", off_report.ok and off_case is not None
            and any(w.code == "SOFTWARE_NOT_VERIFIED_HERE" for w in off_report.warnings),
            f"offline ok={off_report.ok}, problems={[p.code for p in off_report.problems]}")

    out = ROOT / EV / "p7" / "case.json"
    write(out, {"case_id": "ratelimit-token-bucket", "validation": report.as_dict(), "derived": derived,
                "offline_ok": off_report.ok,
                "conclusion": {"case_validates": report.ok, "defect_deviates": derived.get("defect") == "DEVIATES",
                               "fix_corresponds": derived.get("fix") == "CORRESPONDS", "offline_readable": off_report.ok}})
    r.evidence(out)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
