"""Final local acceptance (phase 4A A1 hardening of the phase-3B aggregator): the phase-2 mandatory regression, the
phase-3 applicable regression and the phase-4 mandatory checks on one engine, aggregated strictly.

    make acceptance-local                                   # phase2 + phase3 + phase4, full, strict
    make acceptance-local ARGS="--suites phase4 --group a1" # a partial run: reported, never complete
    make acceptance-local ARGS="--no-strict"                # same report, always exits 0 (informational)

Each suite runs through scripts/check_runner.py into out/acceptance/<suite>/ with a fresh `FAL_ACCEPTANCE_NONCE`; a
suite report is adopted only when it carries that nonce — a runner that crashed, a report that was never written and
an old report left on disk from an earlier run are all rejected with a definite verdict (RUNNER_CRASHED,
REPORT_MISSING, STALE_REPORT, MALFORMED_REPORT). Re-run suites write their evidence under
docs/execution/evidence/phase4/regression/<suite>/ so the historical phase-2 / phase-3 records stay untouched.

The acceptance is `complete` only when every suite ran in full, its report is this invocation's, and every required
group of it passed. Strict mode (the default) exits 1 otherwise. The report goes to
docs/execution/evidence/phase4/acceptance-local.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUITES = ("phase2", "phase3", "phase4")
EVIDENCE = {"phase2": "docs/execution/evidence/phase4/regression/phase2",
            "phase3": "docs/execution/evidence/phase4/regression/phase3",
            "phase4": "docs/execution/evidence/phase4"}


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def judge_suite(results_path: Path, nonce: str, runner_exit: int) -> dict:
    """Verdict for one suite from the report the runner should have written in this invocation."""
    base = {"report": _rel(results_path), "runner_exit": runner_exit}
    if not results_path.exists():
        return base | {"verdict": "REPORT_MISSING", "complete": False,
                       "detail": f"the runner exited {runner_exit} without writing a report"}
    try:
        doc = json.loads(results_path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return base | {"verdict": "MALFORMED_REPORT", "complete": False, "detail": str(exc)[:200]}
    run = doc.get("run") or {}
    base |= {"report_sha256": hashlib.sha256(results_path.read_bytes()).hexdigest(),
             "commit": (doc.get("source_revision") or {}).get("commit"), "groups": doc.get("groups"),
             "summary": doc.get("summary"), "unmet": doc.get("unmet", [])}
    if run.get("acceptance_nonce") != nonce:
        return base | {"verdict": "STALE_REPORT", "complete": False,
                       "detail": "the report on disk was not written by this acceptance run (nonce mismatch)"}
    if runner_exit not in (0, 1):
        return base | {"verdict": "RUNNER_CRASHED", "complete": False,
                       "detail": f"runner exit {runner_exit} (usage error or crash)"}
    if doc.get("format") != "checks@3":
        return base | {"verdict": "MALFORMED_REPORT", "complete": False, "detail": f"format {doc.get('format')}"}
    if not run.get("full"):
        return base | {"verdict": "PARTIAL", "complete": False, "detail": f"selection {run.get('selection')}"}
    if doc.get("complete") is True:
        return base | {"verdict": "COMPLETE", "complete": True, "detail": "every required group passed"}
    return base | {"verdict": "INCOMPLETE", "complete": False, "detail": f"unmet {doc.get('unmet')}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--suites", default=",".join(DEFAULT_SUITES), help="suite names or suite .py paths")
    ap.add_argument("--group", default="", help="restrict every suite to these groups (makes the run partial)")
    ap.add_argument("--out", default=str(ROOT / "out" / "acceptance"))
    ap.add_argument("--report", default=str(ROOT / "docs" / "execution" / "evidence" / "phase4" / "acceptance-local.json"))
    ap.add_argument("--no-strict", action="store_true", help="always exit 0 (the report still says complete=false)")
    args = ap.parse_args(argv)

    nonce = uuid.uuid4().hex
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    suites = [s for s in args.suites.split(",") if s]
    verdicts: dict[str, dict] = {}
    for suite in suites:
        key = Path(suite).stem.removesuffix("_check") if suite.endswith(".py") else suite
        out = Path(args.out) / key
        cmd = [sys.executable, str(ROOT / "scripts" / "check_runner.py"), "--suite", suite, "--out", str(out)]
        if args.group:
            cmd += ["--group", args.group]
        env = {**os.environ, "FAL_ACCEPTANCE_NONCE": nonce}
        if key in EVIDENCE:
            env["FAL_EVIDENCE_DIR"] = EVIDENCE[key]
        print(f"==> acceptance: {key}: {' '.join(cmd[1:])}", flush=True)
        proc = subprocess.run(cmd, cwd=ROOT, env=env)
        verdicts[key] = judge_suite(out / "results.json", nonce, proc.returncode)
        print(f"    {key}: {verdicts[key]['verdict']} — {verdicts[key]['detail']}", flush=True)

    complete = bool(verdicts) and not args.group and all(v["complete"] for v in verdicts.values())
    unmet = [f"{k}:{v['verdict']}" + (f" {v.get('unmet')}" if v.get("unmet") else "")
             for k, v in verdicts.items() if not v["complete"]]
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    report = {"acceptance": "local", "format": "acceptance@2", "nonce": nonce, "started_at": started,
              "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source_revision": rev,
              "suites": verdicts, "selection": {"suites": suites, "group": args.group or None},
              "complete": complete, "unmet": unmet, "strict": not args.no_strict,
              "rule": "complete only when every suite ran in full, its report carries this run's nonce, and every "
                      "required group passed; partial runs, missing / stale / malformed reports and crashed runners "
                      "are never complete"}
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"\n==> acceptance-local: complete={complete} → {_rel(report_path)}")
    if unmet:
        print(f"    unmet: {unmet}")
    if args.no_strict:
        return 0
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
