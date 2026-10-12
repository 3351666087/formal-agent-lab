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
    # ------------------------------------------------------------------ P6A provider calls, raw answers, evaluation
    Check("p6a-unit", "p6a",
          "研究调用与评测（单元）：两种提供方协议的合法回答、HTTP 成功内的可见拒绝/内容过滤、空内容、截断、格式无效、模型变化/未命名、"
          "401/403/429/5xx/529、请求被拒/模型不可用、响应丢失（可能计费）、预算与取消在发送前检查、不读提供方环境变量、路由与主机一致、"
          "密钥不落盘；研究定义校验（参考答案不得进入任务输入）、答案轴、两个评分器、输出上限与复用键",
          f"{PYTEST} packages/strategies/tests packages/evaluation/tests/test_research_study.py",
          ["P6A-01", "P6A-02"]),
    Check("p6a-protocol", "p6a",
          "协议服务端到端（不是模型）：研究 p6a-protocol 全部 24 个单元逐一脚本化——各类调用结果与评分标签、原始先存后评、"
          "两轴分离、程序对应评分、合成任务 N/A、无模型回答记 MISSING、两条实验线不合并、未实现模式 NOT_RUN、配对比较；"
          "预算在发送前检查且恢复后不回补、取消在发送前检查、恢复复用已答单元并对未答单元新采样、重新评分不调用、密钥不落盘",
          f"{PY} scripts/p6a_protocol_evidence.py", ["P6A-01", "P6A-02"], protocol=True,
          produces=[f"{EV}/p6a/protocol.json"]),
    Check("p6a-real", "p6a",
          "真实端点最小调用（普通业务任务，已配置且已授权额度）：未配置凭据则 BLOCKED；记录路由（中转不记为官方）、返回模型身份、"
          "原始响应体、用量与预算；已保存的真实回答在重跑时复用而不重复购买；密钥不落盘",
          f"{PY} scripts/p6a_real_evidence.py", ["P6A-01"], protocol=True,
          produces=[f"{EV}/p6a/real-endpoint.json"]),
]

# every check must live in a declared group
for c in RESEARCH_CHECKS:
    if c.group not in RESEARCH_GROUPS:
        raise ValueError(f"research check {c.id} registered in undeclared group {c.group!r}")
