"""Final local acceptance (phase 3B, D6): the phase-2 mandatory regression and the phase-3 D1–D6 applicable checks on
one engine, aggregated into a single honest report.

Runs both suites through scripts/check_runner.py (which classifies PASS / FAIL / NOT_RUN / BLOCKED by itself:
service-dependent checks are NOT_RUN when the stack is down, disk-heavy checks are BLOCKED below the guard). Writes
docs/handoff/phase3-checks.json (the phase-3 result), refreshes docs/handoff/phase2-checks.json (the phase-2 result),
and a combined docs/execution/evidence/phase3/acceptance-local.json. The overall acceptance is `complete` only when
every mandatory group of both suites passed — unmet mandatory (services, disk, node) are reported, never hidden.

    make acceptance-local                 # both suites, full
    make acceptance-local ARGS="--phase3-only"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "execution" / "evidence" / "phase3" / "acceptance-local.json"
PHASE3_RESULTS = ROOT / "docs" / "execution" / "evidence" / "phase3" / "checks" / "results.json"
PHASE2_CHECKS = ROOT / "docs" / "handoff" / "phase2-checks.json"
PHASE3_CHECKS = ROOT / "docs" / "handoff" / "phase3-checks.json"


def _run(cmd: list[str]) -> int:
    print(f"==> {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT).returncode


def _load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _summary(doc: dict) -> dict:
    return {"groups": doc.get("groups", {}), "summary": doc.get("summary", {}),
            "mandatory_passed": doc.get("mandatory_passed"), "commit": doc.get("source_revision", {}).get("commit")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--phase3-only", action="store_true", help="skip the phase-2 suite")
    ap.add_argument("--group", default="", help="restrict the phase-3 suite to these groups")
    args = ap.parse_args(argv)

    py = [sys.executable]
    # phase-3 suite (includes D1–D6 and the regression group: unit suite + phase-1 parity + integration)
    p3_cmd = [*py, "scripts/phase3_check.py"]
    if args.group:
        p3_cmd += ["--group", args.group]
    _run(p3_cmd)
    p3 = _load(PHASE3_RESULTS)
    if p3:
        PHASE3_CHECKS.write_text(json.dumps(p3, indent=2, ensure_ascii=False) + "\n")

    p2 = {}
    if not args.phase3_only:
        _run([*py, "scripts/phase2_check.py"])  # writes docs/handoff/phase2-checks.json itself
        p2 = _load(PHASE2_CHECKS)

    phase2_ok = p2.get("mandatory_passed") if p2 else None
    phase3_ok = p3.get("mandatory_passed")
    complete = bool(phase3_ok) and (phase2_ok if not args.phase3_only else True)

    report = {
        "acceptance": "phase3-local", "generated_at": p3.get("generated_at"),
        "source_revision": p3.get("source_revision", {}).get("commit"),
        "phase3": _summary(p3), "phase2": _summary(p2) if p2 else {"note": "not run (--phase3-only)"},
        "complete": complete,
        "unmet": _unmet(p3) + (_unmet(p2) if p2 else []),
        "note": "complete is True only when every mandatory group of both suites passed; NOT_RUN (services down) / "
                "BLOCKED (disk below guard) / environment gaps are reported here, not hidden. The phase-2 historical "
                "acceptance is commit 4e1f959 (28/28); this is the current-revision re-run.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"\n==> acceptance-local: complete={complete} → {OUT.relative_to(ROOT)}")
    print(f"    phase3 groups: {p3.get('groups')}")
    if p2:
        print(f"    phase2 groups: {p2.get('groups')}")
    print(f"    unmet: {report['unmet']}")
    return 0


def _unmet(doc: dict) -> list[str]:
    return [f"{doc.get('suite', '?')}:{g}={s}" for g, s in doc.get("groups", {}).items()
            if s not in ("PASS", "OPTIONAL")]


if __name__ == "__main__":
    raise SystemExit(main())
