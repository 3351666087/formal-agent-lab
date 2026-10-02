"""A1 evidence: inject every known way a run could be mistaken for a pass into the real check engine.

Each case writes a throw-away suite into a scratch directory, runs scripts/check_runner.py (and, for the report-level
cases, scripts/acceptance_local.py) as a subprocess, and records what the engine concluded next to what it must
conclude. The first six cases must never aggregate into an overall pass; the last one must. Reports through the
check-result protocol (scripts/check_result.py) and writes $FAL_EVIDENCE_DIR/a1-status-protocol.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
OUT = EV / "a1-status-protocol.json"
PY = sys.executable
RUNNER = str(ROOT / "scripts" / "check_runner.py")


def helper(tmp: Path, name: str, body: str) -> str:
    p = tmp / f"{name}.py"
    p.write_text(f"import sys; sys.path.insert(0, {str(ROOT / 'scripts')!r})\n" + textwrap.dedent(body))
    return f"{PY} {p}"


def suite(tmp: Path, checks: str, name: str = "case_check.py") -> Path:
    p = tmp / name
    p.write_text(f'''import sys
sys.path.insert(0, {str(ROOT / "scripts")!r})
from pathlib import Path
from check_runner import Check, Suite
SUITE = Suite(name="case", groups=["a", "b"], out=Path({str(tmp / "out")!r}), checks=[
{checks}
])
''')
    return p


def engine(s: Path, *args: str) -> tuple[int, dict]:
    code = subprocess.run([PY, RUNNER, "--suite", str(s), *args], cwd=ROOT, capture_output=True).returncode
    return code, json.loads((s.parent / "out" / "results.json").read_text())


def observed(code: int, doc: dict, check: str | None = None) -> dict:
    c = next((x for x in doc["checks"] if x["id"] == check), {}) if check else {}
    return {"strict_exit": code, "complete": doc["complete"], "groups": doc["groups"],
            "check_result": c.get("result"), "check_reason": (c.get("reason") or "")[:160],
            "inherited": c.get("inherited")}


OK_B = '    Check("y", "b", "ok", "true"),'


def cases() -> list[dict]:
    out = []

    def record(name: str, risk: str, expect: dict, got: dict) -> None:
        holds = all(got.get(k) == v for k, v in expect.items())
        out.append({"case": name, "risk": risk, "expected": expect, "observed": got, "holds": holds})

    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        cmd = helper(t, "blocked", """
            from check_result import CheckResult
            CheckResult().blocked("toolchain not installed"); sys.exit(0)
        """)
        code, doc = engine(suite(t, f'    Check("x", "a", "", {cmd!r}, protocol=True),\n{OK_B}'), "--strict")
        record("exit_zero_reports_blocked", "脚本退出 0 但报告 BLOCKED",
               {"check_result": "BLOCKED", "complete": False, "strict_exit": 1}, observed(code, doc, "x"))
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        cmd = helper(t, "false", """
            import json, os
            json.dump({"protocol": "fal-check-result@1", "nonce": os.environ["FAL_CHECK_NONCE"], "status": "PASS",
                       "assertions": [{"id": "writes_zero", "required": True, "holds": False}]},
                      open(os.environ["FAL_CHECK_RESULT"], "w"))
        """)
        code, doc = engine(suite(t, f'    Check("x", "a", "", {cmd!r}, protocol=True),\n{OK_B}'), "--strict")
        record("required_assertion_false", "必需断言为 false（脚本自称 PASS）",
               {"check_result": "FAIL", "complete": False, "strict_exit": 1}, observed(code, doc, "x"))
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        code, doc = engine(suite(t, f'    Check("x", "a", "", "true", protocol=True),\n{OK_B}'), "--strict")
        record("report_missing", "报告丢失（命令退出 0 但未写结构化结果）",
               {"check_result": "FAIL", "complete": False, "strict_exit": 1}, observed(code, doc, "x"))
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        ev = t / "ev.json"
        ev.write_text(json.dumps({"conclusion": {"ok": True}}))
        old = time.time() - 3600
        os.utime(ev, (old, old))
        code, doc = engine(suite(t, f'    Check("x", "a", "", "exit 139", produces=[{str(ev)!r}]),\n'
                                    f'    Check("y", "b", "", "true", produces=[{str(ev)!r}]),'), "--strict")
        got = observed(code, doc, "x") | {"silent_rewrite_result": next(c for c in doc["checks"] if c["id"] == "y")["result"]}
        record("crash_with_old_pass_on_disk", "子进程失败但磁盘上留着旧 PASS（另一检查退出 0 却未重写）",
               {"check_result": "FAIL", "silent_rewrite_result": "FAIL", "complete": False, "strict_exit": 1}, got)
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        s = suite(t, f'    Check("x", "a", "", "true"),\n{OK_B}')
        code, doc = engine(s, "--group", "a", "--strict")
        got = observed(code, doc) | {"selection_status": doc["selection_status"]}
        record("single_group_selected", "只选一组",
               {"selection_status": "PASS", "complete": False, "strict_exit": 1}, got)
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        engine(suite(t, f'    Check("x", "a", "", "true"),\n{OK_B}'), "--strict")
        s2 = suite(t, '    Check("x", "a", "", "true"),\n    Check("y", "b", "", "true && true"),')
        code, doc = engine(s2, "--only", "x", "--strict")
        record("reuse_after_config_change", "代码/配置变化后复用旧证据",
               {"inherited": True, "complete": False, "strict_exit": 1}, observed(code, doc, "y"))
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        crashed = t / "crashed_check.py"
        crashed.write_text("raise RuntimeError('crash before any report')\n")
        stale = t / "acc" / "crashed" / "results.json"
        stale.parent.mkdir(parents=True)
        stale.write_text(json.dumps({"format": "checks@3", "complete": True, "run": {"full": True, "acceptance_nonce": "old"}}))
        rep = t / "acceptance.json"
        code = subprocess.run([PY, str(ROOT / "scripts" / "acceptance_local.py"), "--suites", str(crashed), "--out",
                               str(t / "acc"), "--report", str(rep)], cwd=ROOT, capture_output=True).returncode
        r = json.loads(rep.read_text())
        record("acceptance_stale_report", "汇总：子进程崩溃、旧报告残留",
               {"verdict": "STALE_REPORT", "complete": False, "strict_exit": 1},
               {"verdict": r["suites"]["crashed"]["verdict"], "complete": r["complete"], "strict_exit": code})
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        cmd = helper(t, "good", """
            from check_result import CheckResult
            r = CheckResult(); r.check("writes_zero", True, "writes=0"); sys.exit(r.finish())
        """)
        code, doc = engine(suite(t, f'    Check("x", "a", "", {cmd!r}, protocol=True),\n{OK_B}'), "--strict")
        record("full_mandatory_pass", "完整必做全部通过（唯一允许的整体通过）",
               {"check_result": "PASS", "complete": True, "strict_exit": 0}, observed(code, doc, "x"))
    return out


def main() -> int:
    r = CheckResult("p4-a1-fault-injection")
    results = cases()
    for c in results:
        r.check(c["case"], c["holds"], f"expected {c['expected']} observed {c['observed']}")
    EV.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"deliverable": "phase4A-A1", "engine": "scripts/check_runner.py (checks@3)",
                               "protocol": "docs/execution/check-protocol.md", "cases": results,
                               "conclusion": {c["case"]: c["holds"] for c in results}},
                              indent=2, ensure_ascii=False) + "\n")
    r.evidence(OUT)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
