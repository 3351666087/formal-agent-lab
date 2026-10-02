"""Phase 4A A1: the strict acceptance aggregator. Only reports written by this acceptance invocation count; a partial
run, a blocked mandatory check, a crashed runner with no report and an old report left on disk all end incomplete
with a non-zero exit."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("acceptance_local", ROOT / "scripts" / "acceptance_local.py")
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


def suite(tmp: Path, name: str, checks: str, groups: str = '["a", "b"]') -> str:
    path = tmp / f"{name}_check.py"
    path.write_text(f'''
import sys
sys.path.insert(0, {str(ROOT / "scripts")!r})
from pathlib import Path
from check_runner import Check, Suite
SUITE = Suite(name={name!r}, groups={groups}, out=Path({str(tmp / "unused")!r}), checks=[
{checks}
])
''')
    return str(path)


def run(tmp: Path, *suites: str, extra: list[str] | None = None) -> tuple[int, dict]:
    report = tmp / "acceptance.json"
    code = acceptance.main(["--suites", ",".join(suites), "--out", str(tmp / "out"), "--report", str(report),
                            *(extra or [])])
    return code, json.loads(report.read_text())


GOOD = '    Check("x", "a", "ok", "true"),\n    Check("y", "b", "ok", "true"),'


def test_all_suites_complete(tmp_path):
    code, rep = run(tmp_path, suite(tmp_path, "one", GOOD), suite(tmp_path, "two", GOOD))
    assert code == 0 and rep["complete"] is True and rep["unmet"] == []
    assert {v["verdict"] for v in rep["suites"].values()} == {"COMPLETE"}


def test_blocked_mandatory_makes_it_incomplete(tmp_path):
    blocked = tmp_path / "blocked.py"
    blocked.write_text(f"import sys; sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
                       "from check_result import CheckResult\nCheckResult().blocked('no endpoint'); sys.exit(0)\n")
    s = suite(tmp_path, "bad", f'    Check("x", "a", "b", "{sys.executable} {blocked}", protocol=True),\n'
                               '    Check("y", "b", "ok", "true"),')
    code, rep = run(tmp_path, suite(tmp_path, "one", GOOD), s)
    assert code == 1 and rep["complete"] is False
    assert rep["suites"]["bad"]["verdict"] == "INCOMPLETE" and rep["suites"]["one"]["verdict"] == "COMPLETE"


def test_partial_selection_is_never_complete(tmp_path):
    code, rep = run(tmp_path, suite(tmp_path, "one", GOOD), extra=["--group", "a"])
    assert code == 1 and rep["complete"] is False and rep["suites"]["one"]["verdict"] == "PARTIAL"


def test_crashed_runner_without_report(tmp_path):
    broken = tmp_path / "broken_check.py"
    broken.write_text("raise RuntimeError('suite definition cannot load')\n")
    code, rep = run(tmp_path, str(broken))
    assert code == 1 and rep["suites"]["broken"]["verdict"] == "REPORT_MISSING"


def test_old_report_left_on_disk_is_not_adopted(tmp_path):
    old = tmp_path / "out" / "broken" / "results.json"
    old.parent.mkdir(parents=True)
    old.write_text(json.dumps({"format": "checks@3", "complete": True, "mandatory_passed": True,
                               "run": {"full": True, "acceptance_nonce": "an-earlier-run"}}))
    broken = tmp_path / "broken_check.py"
    broken.write_text("raise RuntimeError('crash before writing')\n")
    code, rep = run(tmp_path, str(broken))
    assert code == 1 and rep["suites"]["broken"]["verdict"] == "STALE_REPORT" and rep["complete"] is False


def test_no_strict_reports_but_exits_zero(tmp_path):
    code, rep = run(tmp_path, suite(tmp_path, "one", GOOD), extra=["--group", "a", "--no-strict"])
    assert code == 0 and rep["complete"] is False and rep["strict"] is False
