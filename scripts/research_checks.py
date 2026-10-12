"""Research-track check registry (phases 5–7). 5A registers group `p5a`; later phases add `p5b`,`p6a`,`p6b`,`p7`.

A group nobody has registered a check in yet is NO_CHECKS, so the suite is never `complete` until every required
group passes — running one group reports `selected_passed` without ever reporting `overall_complete`."""

from __future__ import annotations

import os

from check_runner import Check

RESEARCH_GROUPS = ["p5a", "p5b", "p6a", "p6b", "p7"]

PYTEST = "uv run --frozen pytest -p no:cacheprovider -q"
PY = "uv run --frozen python"
EV = os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research")

RESEARCH_CHECKS = [
    # ------------------------------------------------------------------ P5A case + conformance foundation
    Check("p5a-unit", "p5a",
          "导入校验与对应验证（单元）：合法普通样例、性质错配、版本错配、缺观测、陈旧证据、参考答案不得作任务输入、离线读取；"
          "信念模型偏离、修订模型对应，三层结果各自独立，对应判定各分支",
          f"{PYTEST} tests/tools/test_research_validate.py tests/tools/test_research_conformance.py",
          ["P5A-01", "P5A-02"]),
    Check("p5a-case", "p5a",
          "普通业务样例端到端：委托案例通过校验、从记录运行重算对应得到参考判定（信念 DEVIATES / 修订 CORRESPONDS）、离线读取成立",
          f"{PY} scripts/p5a_case_check.py", ["P5A-01", "P5A-02"], protocol=True,
          produces=[f"{EV}/p5a/case.json"]),
    # ------------------------------------------------------------------ P5B implementation-level isolation case
    Check("p5b-unit", "p5b",
          "隔离授权夹具回归：未知主体拒绝、同租户正常、缺陷变体跨租户可达、修复变体拒绝；对应判定三类分支（偏离/对应/证据不足）",
          f"{PYTEST} examples/local-order-service/tests/test_research_isolation.py", ["P5B-01", "P5B-02"]),
    Check("p5b-case", "p5b",
          "实现级隔离案例端到端：案例通过校验、从记录观测离线重算三类对应（缺陷 DEVIATES / 修复 CORRESPONDS / 证据不足 UNKNOWN）、离线读取成立",
          f"{PY} scripts/p5b_case_check.py", ["P5B-01", "P5B-02"], protocol=True,
          produces=[f"{EV}/p5b/case.json"]),
]

# every check must live in a declared group
for c in RESEARCH_CHECKS:
    if c.group not in RESEARCH_GROUPS:
        raise ValueError(f"research check {c.id} registered in undeclared group {c.group!r}")
