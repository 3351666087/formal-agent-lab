"""The local check engine (scripts/check_runner.py, phase 3A G6): attempts, retries, digests, timing, history."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_runner", ROOT / "scripts" / "check_runner.py")
runner = importlib.util.module_from_spec(spec)
sys.modules["check_runner"] = runner
spec.loader.exec_module(runner)


def suite_file(tmp: Path) -> Path:
    marker = tmp / "marker"
    src = f'''
import sys
sys.path.insert(0, {str(ROOT / "scripts")!r})
from pathlib import Path
from check_runner import Check, Suite
SUITE = Suite(name="demo", groups=["a", "b"], out=Path({str(tmp / "out")!r}), checks=[
    Check("ok", "a", "always passes", "echo fine"),
    Check("flaky", "a", "fails once, then passes", "test -f {marker} || (touch {marker}; echo first try failed; exit 1)", retries=1),
    Check("broken", "b", "always fails", "echo nope; exit 3", retries=1),
    Check("needs-llm", "b", "precondition missing", "true", requires="devstack"),
])
'''
    path = tmp / "demo_check.py"
    path.write_text(src)
    return path


def test_attempts_first_failure_flaky_and_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_API_URL", "http://127.0.0.1:9/api/v1")  # no running stack: devstack probe fails
    code = runner.main(["--suite", str(suite_file(tmp_path))])
    assert code == 1  # `broken` failed
    doc = json.loads((tmp_path / "out" / "results.json").read_text())
    checks = {c["id"]: c for c in doc["checks"]}
    assert checks["ok"]["result"] == "PASS" and len(checks["ok"]["attempts"]) == 1
    flaky = checks["flaky"]
    assert flaky["result"] == "PASS" and flaky["flaky"] and [a["result"] for a in flaky["attempts"]] == ["FAIL", "PASS"]
    assert flaky["first_failure"]["attempt"] == 1 and "first try failed" in flaky["first_failure"]["summary"]
    logs = [ROOT / a["log"] if not Path(a["log"]).is_absolute() else Path(a["log"]) for a in flaky["attempts"]]
    assert all(p.exists() for p in logs) and len(set(logs)) == 2  # one log per attempt
    broken = checks["broken"]
    assert broken["result"] == "FAIL" and len(broken["attempts"]) == 2 and broken["attempts"][0]["exit_code"] == 3
    assert checks["needs-llm"]["result"] == "NOT_RUN" and checks["needs-llm"]["attempts"] == []
    assert doc["groups"] == {"a": "PASS", "b": "FAIL"} and doc["config"]["sha256"] and doc["resources_before"]["cpus"]
    assert doc["source_revision"]["commit"] and doc["timing"]["last_full_run_s"] is not None


def test_partial_rerun_keeps_history_and_times_separately(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_API_URL", "http://127.0.0.1:9/api/v1")
    suite = str(suite_file(tmp_path))
    runner.main(["--suite", suite])
    runner.main(["--suite", suite, "--only", "ok"])
    doc = json.loads((tmp_path / "out" / "results.json").read_text())
    assert [r["full"] for r in doc["runs"]] == [True, False]
    assert doc["timing"]["partial_runs"][0]["selection"]["only"] == ["ok"]
    assert doc["timing"]["last_full_run_s"] == doc["runs"][0]["duration_s"]
    ok = next(c for c in doc["checks"] if c["id"] == "ok")
    assert ok["history"] and ok["history"][0]["result"] == "PASS"  # the earlier invocation is kept
    broken = next(c for c in doc["checks"] if c["id"] == "broken")
    assert broken["inherited"] is False and broken["result"] == "FAIL"  # same commit, tree and config: still current


def test_freshness_uses_the_file_systems_clock(tmp_path):
    """Phase 4B (B3): produced files are judged fresh against the attempt's start on the clock of the file system
    they live on. A VM writing to a host-shared mount sees mtimes seconds behind its own clock; a file written
    during the attempt must still count as fresh, and one written before it must not."""
    import os
    import time

    skew = 5.0  # the file system's clock runs 5 s behind the process clock
    start_fs = time.time() - skew
    fresh, stale = tmp_path / "fresh.json", tmp_path / "stale.json"
    fresh.write_text("{}")
    stale.write_text("{}")
    os.utime(fresh, (start_fs + 0.2, start_fs + 0.2))  # written just after the attempt started (fs clock)
    os.utime(stale, (start_fs - 30, start_fs - 30))    # left over from an earlier run
    assert runner.read_produced(fresh, start_fs, None)["fresh"]
    assert not runner.read_produced(fresh, time.time(), None)["fresh"]  # the old process-clock comparison failed
    assert "stale evidence" in runner.read_produced(stale, start_fs, None)["error"]
