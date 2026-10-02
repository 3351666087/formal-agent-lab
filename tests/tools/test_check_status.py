"""Phase 4A A1: the check status protocol. Each known way a run could be mistaken for a pass is injected on purpose
(an exit 0 that reports BLOCKED, a false required assertion, a missing report, an old PASS left on disk, a single-group
selection, results reused after a configuration change) and must not aggregate into `complete`; a full run whose
mandatory checks all pass must."""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_runner", ROOT / "scripts" / "check_runner.py")
runner = importlib.util.module_from_spec(spec)
sys.modules["check_runner"] = runner
spec.loader.exec_module(runner)

PY = sys.executable


def script(tmp: Path, name: str, body: str) -> str:
    """A tiny evidence script; returns the shell command that runs it."""
    path = tmp / f"{name}.py"
    path.write_text(f"import sys; sys.path.insert(0, {str(ROOT / 'scripts')!r})\n" + textwrap.dedent(body))
    return f"{PY} {path}"


def suite(tmp: Path, checks_src: str, groups: str = '["a", "b"]', name: str = "demo_check.py") -> str:
    src = f'''
import sys
sys.path.insert(0, {str(ROOT / "scripts")!r})
from pathlib import Path
from check_runner import Check, Suite
OUT = Path({str(tmp / "out")!r})
SUITE = Suite(name="demo", groups={groups}, out=OUT, checks=[
{checks_src}
])
'''
    path = tmp / name
    path.write_text(src)
    return str(path)


def results(tmp: Path) -> dict:
    return json.loads((tmp / "out" / "results.json").read_text())


def by_id(doc: dict) -> dict:
    return {c["id"]: c for c in doc["checks"]}


# ------------------------------------------------------------------ the six ways that must not pass


def test_exit_zero_but_structured_result_blocked(tmp_path):
    cmd = script(tmp_path, "blocked", """
        from check_result import CheckResult
        r = CheckResult()
        r.blocked("toolchain not installed")
        sys.exit(0)  # the script lies with its exit code; the engine reads the result
    """)
    s = suite(tmp_path, f'    Check("x", "a", "blocked", {cmd!r}, protocol=True),\n    Check("y", "b", "ok", "true"),')
    assert runner.main(["--suite", s, "--strict"]) == 1
    doc = results(tmp_path)
    assert by_id(doc)["x"]["result"] == "BLOCKED" and "toolchain not installed" in by_id(doc)["x"]["reason"]
    assert doc["groups"]["a"] == "INCOMPLETE" and doc["complete"] is False and doc["mandatory_passed"] is False


def test_exit_zero_but_legacy_evidence_blocked(tmp_path):
    ev = tmp_path / "ev.json"
    cmd = script(tmp_path, "legacy", f"""
        import json
        open({str(ev)!r}, "w").write(json.dumps({{"status": "BLOCKED", "reason": "CAGE venv missing"}}))
    """)
    s = suite(tmp_path, f'    Check("x", "a", "legacy", {cmd!r}, produces=[{str(ev)!r}]),\n    Check("y", "b", "ok", "true"),')
    runner.main(["--suite", s])
    doc = results(tmp_path)
    assert by_id(doc)["x"]["result"] == "BLOCKED" and doc["complete"] is False


def test_required_assertion_false_fails_even_if_status_claims_pass(tmp_path):
    cmd = script(tmp_path, "assert_false", """
        import json, os
        doc = {"protocol": "fal-check-result@1", "nonce": os.environ["FAL_CHECK_NONCE"], "status": "PASS",
               "assertions": [{"id": "writes_zero", "required": True, "holds": False, "detail": "writes=1"}]}
        open(os.environ["FAL_CHECK_RESULT"], "w").write(json.dumps(doc))
    """)
    s = suite(tmp_path, f'    Check("x", "a", "assert", {cmd!r}, protocol=True),\n    Check("y", "b", "ok", "true"),')
    assert runner.main(["--suite", s]) == 1
    x = by_id(results(tmp_path))["x"]
    assert x["result"] == "FAIL" and "writes_zero" in x["reason"]


def test_legacy_conclusion_false_fails(tmp_path):
    ev = tmp_path / "ev.json"
    cmd = script(tmp_path, "concl", f"""
        import json
        open({str(ev)!r}, "w").write(json.dumps({{"conclusion": {{"engines_agree": True, "zero_side_effect": False}}}}))
    """)
    s = suite(tmp_path, f'    Check("x", "a", "c", {cmd!r}, produces=[{str(ev)!r}], assertions_from="conclusion"),\n'
                        '    Check("y", "b", "ok", "true"),')
    runner.main(["--suite", s])
    x = by_id(results(tmp_path))["x"]
    assert x["result"] == "FAIL" and "zero_side_effect" in x["reason"]


def test_missing_report_fails(tmp_path):
    ev = tmp_path / "never-written.json"
    s = suite(tmp_path, '    Check("x", "a", "no result", "true", protocol=True),\n'
                        f'    Check("y", "b", "no evidence", "true", produces=[{str(ev)!r}]),')
    runner.main(["--suite", s])
    c = by_id(results(tmp_path))
    assert c["x"]["result"] == "FAIL" and "structured result missing" in c["x"]["reason"]
    assert c["y"]["result"] == "FAIL" and "evidence missing" in c["y"]["reason"]
    assert results(tmp_path)["complete"] is False


def test_crash_with_old_pass_left_on_disk(tmp_path):
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"status": "PASS", "conclusion": {"ok": True}}))  # an earlier run's PASS
    import os
    import time
    old = time.time() - 3600
    os.utime(ev, (old, old))
    forge = script(tmp_path, "forge", """
        import json, os
        doc = {"protocol": "fal-check-result@1", "nonce": "old", "status": "PASS",
               "assertions": [{"id": "a", "required": True, "holds": True}]}
        open(os.environ["FAL_CHECK_RESULT"], "w").write(json.dumps(doc))
    """)
    s = suite(tmp_path, f'    Check("crash", "a", "crashes", "exit 139", produces=[{str(ev)!r}]),\n'
                        f'    Check("silent", "b", "exits 0 without rewriting", "true", produces=[{str(ev)!r}]),\n'
                        f'    Check("forged", "b", "old nonce", {forge!r}, protocol=True),')
    runner.main(["--suite", s])
    c = by_id(results(tmp_path))
    assert c["crash"]["result"] == "FAIL" and "exit 139" in c["crash"]["reason"]
    assert c["silent"]["result"] == "FAIL" and "stale evidence" in c["silent"]["reason"]
    assert c["forged"]["result"] == "FAIL" and "stale result" in c["forged"]["reason"]
    assert results(tmp_path)["complete"] is False


def test_single_group_selection_is_never_complete(tmp_path):
    s = suite(tmp_path, '    Check("x", "a", "ok", "true"),\n    Check("y", "b", "ok", "true"),')
    assert runner.main(["--suite", s, "--group", "a"]) == 0  # the selection itself passed
    assert runner.main(["--suite", s, "--group", "a", "--strict"]) == 1  # ...but it is not an overall pass
    doc = results(tmp_path)
    assert doc["selection_status"] == "PASS" and doc["complete"] is False
    assert doc["groups"] == {"a": "PASS", "b": "NOT_SELECTED"}


def test_results_from_an_earlier_invocation_never_aggregate(tmp_path):
    s = suite(tmp_path, '    Check("x", "a", "ok", "true"),\n    Check("y", "b", "ok", "true"),')
    assert runner.main(["--suite", s, "--strict"]) == 0 and results(tmp_path)["complete"] is True
    # same tree and config: a partial re-run still cannot inherit the other group's earlier PASS
    runner.main(["--suite", s, "--only", "x"])
    doc = results(tmp_path)
    assert doc["complete"] is False and doc["groups"]["b"] == "NOT_SELECTED"
    assert by_id(doc)["y"]["this_run"] is False and by_id(doc)["y"]["inherited"] is False
    # configuration change (a check's command): the earlier results become inherited
    s2 = suite(tmp_path, '    Check("x", "a", "ok", "true"),\n    Check("y", "b", "ok", "true && true"),')
    runner.main(["--suite", s2, "--only", "x"])
    doc = results(tmp_path)
    assert by_id(doc)["y"]["inherited"] is True and doc["complete"] is False


def test_full_mandatory_pass_is_complete(tmp_path):
    cmd = script(tmp_path, "good", """
        from check_result import CheckResult
        r = CheckResult()
        r.check("service_writes_zero", True, "writes=0")
        sys.exit(r.finish())
    """)
    s = suite(tmp_path, f'    Check("x", "a", "structured", {cmd!r}, protocol=True),\n    Check("y", "b", "ok", "true"),')
    assert runner.main(["--suite", s, "--strict"]) == 0
    doc = results(tmp_path)
    assert doc["complete"] is True and doc["mandatory_passed"] is True and doc["groups"] == {"a": "PASS", "b": "PASS"}
    x = by_id(doc)["x"]
    assert x["attempts"][0]["structured_result"] and x["attempts"][0]["assertions"][0]["holds"] is True
    assert x["run_nonce"] == doc["run"]["nonce"]


# ------------------------------------------------------------------ further rules


def test_all_skipped_pytest_is_blocked_not_pass(tmp_path):
    t = tmp_path / "test_skipped.py"
    t.write_text("import pytest\n\ndef test_needs_tool():\n    pytest.skip('toolchain absent')\n")
    s = suite(tmp_path, f'    Check("x", "a", "skips", "{PY} -m pytest -p no:cacheprovider -q -ra {t}"),\n'
                        '    Check("y", "b", "ok", "true"),')
    runner.main(["--suite", s])
    x = by_id(results(tmp_path))["x"]
    assert x["result"] == "BLOCKED" and "toolchain absent" in x["reason"]


def test_conditional_trigger_is_fixed_before_running(tmp_path, monkeypatch):
    s = suite(tmp_path, '    Check("m", "a", "mandatory", "true"),\n'
                        '    Check("c", "a", "real endpoint", "exit 1", kind="conditional", trigger="env:FAL_TEST_TRIGGER"),\n'
                        '    Check("y", "b", "ok", "true"),')
    monkeypatch.delenv("FAL_TEST_TRIGGER", raising=False)
    assert runner.main(["--suite", s, "--strict"]) == 0  # not applicable: the failing command never ran
    doc = results(tmp_path)
    assert by_id(doc)["c"]["result"] == "NOT_APPLICABLE" and by_id(doc)["c"]["attempts"] == []
    assert by_id(doc)["c"]["condition"]["met"] is False and doc["complete"] is True
    monkeypatch.setenv("FAL_TEST_TRIGGER", "1")  # trigger met: now it counts like a mandatory check
    assert runner.main(["--suite", s, "--strict"]) == 1
    doc = results(tmp_path)
    assert by_id(doc)["c"]["result"] == "FAIL" and doc["groups"]["a"] == "FAIL"


def test_missing_environment_is_blocking_for_required_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_API_URL", "http://127.0.0.1:9/api/v1")
    s = suite(tmp_path, '    Check("x", "a", "needs stack", "true", requires="devstack"),\n    Check("y", "b", "ok", "true"),')
    assert runner.main(["--suite", s, "--strict"]) == 1
    doc = results(tmp_path)
    assert by_id(doc)["x"]["result"] == "NOT_RUN" and doc["groups"]["a"] == "INCOMPLETE" and doc["complete"] is False


def test_empty_required_group_is_not_a_pass(tmp_path):
    s = suite(tmp_path, '    Check("x", "a", "ok", "true"),', groups='["a", "b1"]')
    assert runner.main(["--suite", s, "--strict"]) == 1
    doc = results(tmp_path)
    assert doc["groups"] == {"a": "PASS", "b1": "NO_CHECKS"} and doc["complete"] is False
    assert doc["unmet"] == ["b1=NO_CHECKS"]


def test_exclusions_may_not_hide_code(tmp_path):
    src = f'''
import sys
sys.path.insert(0, {str(ROOT / "scripts")!r})
from pathlib import Path
from check_runner import Check, Suite
SUITE = Suite(name="demo", groups=["a"], out=Path({str(tmp_path / "out")!r}), outputs=("scripts/",),
              checks=[Check("x", "a", "ok", "true")])
'''
    path = tmp_path / "hide_check.py"
    path.write_text(src)
    assert runner.main(["--suite", str(path)]) == 2


@pytest.mark.parametrize("kwargs,expected", [
    ({"exit_code": 0, "timed_out": True}, "FAIL"),
    ({"exit_code": 3, "structured": {"present": True, "doc": {"status": "BLOCKED", "reason": "x", "assertions": []}}},
     "BLOCKED"),
    ({"exit_code": 1, "structured": {"present": True, "doc": {"status": "PASS", "assertions": []}}}, "FAIL"),
    ({"exit_code": 0, "protocol": True}, "FAIL"),
    ({"exit_code": 0, "structured": {"present": True, "error": "malformed result: x"}}, "FAIL"),
    ({"exit_code": 0, "structured": {"present": True, "doc": {"status": "PASS", "assertions": []}}}, "FAIL"),
    ({"exit_code": 0, "structured": {"present": True, "doc": {"status": "PASS",
      "assertions": [{"id": "a", "required": True, "holds": None}]}}}, "FAIL"),
    ({"exit_code": 0, "structured": {"present": True, "doc": {"status": "PASS",
      "assertions": [{"id": "a", "required": True, "holds": True}]}}}, "PASS"),
    ({"exit_code": 0, "produced": [{"path": "e.json", "exists": True, "fresh": True, "status": "NOT_RUN",
                                    "status_reason": "stack down"}]}, "NOT_RUN"),
    ({"exit_code": 0, "pytest": {"passed": 0, "skipped": 0, "line": "no tests ran in 0.01s", "skip_reasons": []}},
     "FAIL"),
    ({"exit_code": 0, "pytest": {"passed": 3, "skipped": 1, "line": "3 passed, 1 skipped", "skip_reasons": []}},
     "PASS"),
    ({"exit_code": 0}, "PASS"),
])
def test_decide_rules(kwargs, expected):
    args = {"exit_code": 0, "timed_out": False, "structured": {"present": False}, "produced": [], "pytest": None,
            "protocol": False, "summary": "s"} | kwargs
    assert runner.decide(**args)[0] == expected


def test_pytest_summary_parsing():
    s = runner.pytest_summary("SKIPPED [1] t.py:3: toolchain absent\n2 passed, 1 skipped, 3 deselected in 0.5s\n")
    assert (s["passed"], s["skipped"], s["deselected"]) == (2, 1, 3) and "toolchain absent" in s["skip_reasons"][0]
    assert runner.pytest_summary("no output") is None
