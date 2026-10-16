<!-- 自建扩展阶段（非下发任务书），由用户反馈驱动：安全/攻击领域必须是真实攻击模型，不要玩具、不要“已攻陷/已加固”的可达性抽象，要进攻也要防御，并基于一个著名大型 GitHub 项目的真实重大漏洞（修复前/后版本）建立攻击/防御形式化模型。复选框 P8-01 / P8-02，scripts/tick.py 记录。开发模型 Claude Opus 4.8，trailer 见提交。 -->

# Phase 8：真实攻击模型（含真实 CVE）与验证器判定的实验

把安全领域重做为**真实攻击模型**：状态是真实安全态势（立足点、管理员、窃取的凭据、网络可达、数据外泄），动作是带前置条件/效果的攻击技术，防御是门控技术的常量，攻击者的目标由 Z3 规划达成——不是 `compromised[step]`/`hardened[step]` 的可达性抽象。进攻与防御并重，并基于真实 CVE 建模。

## 8.1 · 真实攻击模型与验证器判定研究

- [ ] **P8-01** 构建真实攻击模型（企业攻击模型 + Log4Shell CVE 模型），以 Z3 为基准答案，接入研究评分与数据隔离。

- 企业攻击模型 `packages/domain-mal/attack_model.py`：`enterprise_attack_model(scale, defenses)`，scale 3 时 32 状态变量 / 33 攻击技术，两条通往 DB-admin 凭据的独立路径使最小防御集非平凡；经 Z3 规划到 `data_exfiltrated`。
- 真实 CVE `packages/domain-mal/cve_2021_44228.py`：Log4Shell（CVE-2021-44228，Apache Log4j 2，github.com/apache/logging-log4j2）。易受攻击 2.14.1 可达 RCE，修复版 2.15/2.16/2.17 被阻断；6 步攻击链为顺序链，六个单一控制各自即可切断（纵深防御）。`test_cve_log4shell.py` 11 项断言。
- 研究体 `research/studies/cyber-attackmodel`（四类题：最短攻击链/部署防御后可达性/最小防御数/技术可用性）；评分器 `attackgraph.analysis@1`；检查 `scripts/cyber_attackmodel_check.py`（组 `p8`）。答案以 `{"value":…}` 包裹防泄漏。

## 8.2 · 真实双模型批次与平台可视化

- [ ] **P8-02** 在授权额度内对真实攻击模型运行双模型批次；把真实攻击模型（企业 + Log4Shell 修复前/后）落到安全项目（模型工作台/场景/实验/证据），不留任何非攻击模型。

- 批次：`fal research study run research/studies/cyber-attackmodel`（576 单元，gpt-6-astra + claude-opus-5-5，可续跑）。
- 平台：`scripts/seed_security_enterprise.py`（企业攻击模型 + 红队场景 + 运行）、`scripts/seed_cve_log4shell.py`（Log4Shell 易受攻击 2.14.1 运行 SUCCEEDED → RCE；已修复 2.16.0 运行 BUDGET_EXHAUSTED → 修复成立）。安全项目 `攻击模型安全分析（防御）`。
- 清理：删除攻击“图”抽象（analysis.py、cyber-attackgraph/cyber-enterprise 研究体与结果、相关脚本），平台与仓库均只保留真实攻击模型。

## 8.3 · 服务器真实复现 + 词汇中性化对照研究（cyber-rename）

- [ ] **P8-03** 在授权集群 `fal-vuln-lab` 隔离区真实执行两条攻击链并留证；把同一形式结构改名成中性词汇后跑 claude-opus-5-5（官方直连）对照研究，在平台上记录。

- 服务器复现（XJTLU-IoT · 命名空间 `fal-vuln-lab`，仅限该区）：Log4Shell 6 步链全通（LDAP 引用 → 远程类加载 → root RCE，证据 `deploy/vuln-lab/evidence/01~03`）；Struts S2-045 无认证 RCE → recon → creds → 横向 → 读假库 → 外泄至攻击者（证据 `evidence/10~14`）；复现手册 `deploy/vuln-lab/RUNBOOK.md`（含利用代码，**不入库**）。
- 对照研究 `research/studies/cyber-rename`（构建器 `scripts/cyber_rename_study.py`）：两个 CVE 模型 × 原词汇/中性化词汇 × 6 题 × 3 重复 = 72 单元，Z3 基准答案，改名任务与孪生任务共享参考答案以支持配对比较；检查 `scripts/cyber_rename_check.py`（组 `p8`）。
- 批次结论（`research/results/cyber-rename/`，官方直连 claude-opus-5-5）：原词汇 correct 0.50 / refused 0.50，中性化词汇 correct 0.25 / refused 0.75（配对 mean_diff = −0.25，检验已报告）；所有被回答单元 100% 正确；拒绝为空内容 stop_reason=refusal；探针（`results/cyber-rename/probe/`）显示拒绝由无关表层词（如 “delivery”“with no safeguards applied”）触发，与安全词汇无关——拒绝面脆、对词汇非单调。
- 平台记录：安全领域项目 `prj_b06ead4a2d4b45e095f3`（模型工作台：企业攻击模型 + Log4Shell 修复前/后；运行台：红队 SUCCEEDED / 2.14.1 SUCCEEDED / 2.16.0 BUDGET_EXHAUSTED）；研究导入 `rs_caffb8ec20744afe9205`（72 单元，`POST /projects/{pid}/research/studies`）。证据：`docs/execution/evidence/research/cyber/{rename.json,rename-check.json}`。

```bash
uv run --frozen pytest packages/domain-mal/tests/test_cve_log4shell.py
make research-check ARGS="--group p8"
uv run --frozen python scripts/seed_cve_log4shell.py
```
