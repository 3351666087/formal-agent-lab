# 阶段四交接（Phase 4：平台修复与可验证交接 + 领域收口）

任务书：[docs/execution/phase-4a.md](../execution/phase-4a.md)（原文 `04A_opus5_5_platform_closure.md`，2026-10-02，A1—A5，开发执行者 Opus 5.5）；B1—B3 由 `04B_opus4_8_domain_closure.md` 交接。本文件是阶段四唯一的交接记录：每个交付包完成时追加证据，最终补齐 [phase4.manifest.json](phase4.manifest.json) 与 [phase4-checks.json](phase4-checks.json)。整体 Phase 4 的完成标记留给 B3。阶段二（`4e1f959`）、阶段三（`67e1b82`，0.3.0 发布 `9203691`）的交接是历史证据。

## 接手核对（2026-10-02）

| 项 | 结果 |
|---|---|
| 基线 | HEAD = `bccda301e58905ee0b0f37b2be9ed2938064d726` = 核对基线，工作区干净，与 origin/main 一致；仓库无 AGENTS.md |
| doctor | Ubuntu 24.04.4 aarch64，4 vCPU，5910 MiB；Postgres / Temporal / S3 已起，API / Web 开发栈未起；LLM 已配置；java 缺失（PRISM 不涉及）（`docs/execution/evidence/phase4/doctor-takeover.json`） |
| 磁盘 | 接手时宿主盘仅 8.5 GiB（0.3.0 镜像构建撑大了 VM 稀疏盘）。经用户授权清理垃圾：VM 内 BuildKit 缓存 4.3 GB、未被引用的阶段二 `formal-agent-lab/*:4e1f959e81f2` 镜像、pip/uv 缓存，随后在 VM 内 fstrim 归还 13.7 GiB；宿主 uv 缓存 954 MB、npm 缓存、brew 旧版本、一个过期的 Codex 临时安装目录。宿主盘 8.5 → 18 GiB。保留：开发栈卷与服务镜像、当前项目镜像、kindest/node、VM 内 Playwright 浏览器、其它应用的活动运行时；废纸篓未动（本就为空）；未做任何宽泛 prune |

## A1 · 检查器与验收状态

**复现的缺口**（基线 `bccda301`）：
- `run_attempt` 只以退出码判定 PASS——D5 证据脚本在 CAGE 缺失时写 `status: BLOCKED` 却退出 0，被记为 PASS；
- 声明的证据文件从不检查存在、新鲜或内容：磁盘上的旧文件可以“替”失败的运行作证；
- 组状态混入早先调用的结果（同一工作树上只重跑一个检查，其它组仍按旧 PASS 计入 `mandatory_passed`）；
- 条件项没有固定触发条件；
- `acceptance_local.py` 在 `complete=false` 时仍返回 0，且直接读取磁盘上的报告（子进程崩溃时会采纳旧报告）。

**修复**（状态协议见 [check-protocol.md](../execution/check-protocol.md)）：
- `scripts/check_runner.py`（报告 `checks@3`，兼容 `checks@2` 的键）：每次 attempt 一次性 nonce 与 `FAL_CHECK_RESULT`；`decide()` 按“超时 → 带 nonce 的 BLOCKED/NOT_RUN → 退出码 → 结构化结果（过期/格式/缺失/必需断言）→ `produces` 证据（缺失/旧文件/格式/记录的状态/`assertions_from` 布尔）→ pytest 0 通过（跳过 = BLOCKED）”判定；只在 FAIL 时重试；条件项按 `trigger` 探针在执行前定适用性（`NOT_APPLICABLE` 或按必做计）；组状态与汇总只计本次调用；`complete`（= `mandatory_passed`）需完整运行且每个必需组 PASS，部分运行只给 `selection_status`；必需组无检查为 `NO_CHECKS`；`--strict`；拒绝把可执行代码排除出工作树摘要（退出 2）；每个结果带原因、attempt、日志、结构化结果位置、证据摘要。
- `scripts/check_result.py`：证据脚本上报接口（`fal-check-result@1`，仅标准库；PASS 0 / FAIL 1 / BLOCKED 3）。
- `scripts/acceptance_local.py`（`acceptance@2`）：依次运行 phase2 / phase3 / phase4，每个套件带一次性 `FAL_ACCEPTANCE_NONCE` 写入 `out/acceptance/<suite>/`；裁决 COMPLETE / INCOMPLETE / PARTIAL / REPORT_MISSING / STALE_REPORT / MALFORMED_REPORT / RUNNER_CRASHED；严格模式非 complete 退出 1；复跑的阶段二 / 三证据写入 `docs/execution/evidence/phase4/regression/<suite>/`，历史记录不被覆盖（`scripts/phase3_check.py` 的 EV 随 `FAL_EVIDENCE_DIR`）。
- `scripts/phase4_check.py`：组固定 `a1`—`a5`、`b1`—`b3`；`scripts/phase4_domain_checks.py` 是 B1—B3 的登记点（只允许 b 组，未登记时为 `NO_CHECKS`，整体保持未完成）。`make phase4-check`。
- 阶段三 D1—D6 证据检查改为 `produces` + `assertions_from="conclusion"`：在临时证据目录复跑 11 项全部 PASS；把 `FAL_CAGE_HOME` 指向不存在的路径时，真实 D5 脚本（退出 0、记 BLOCKED）现在被判为 **BLOCKED**（原先为 PASS）。

**验证**：`tests/tools` 35 项（新增 `test_check_status.py` 27、`test_acceptance_local.py` 6，原 `test_check_runner.py` 2 项不变）；`make phase4-check ARGS="--group a1"`：`p4-a1-engine`、`p4-a1-fault-injection`（对真实引擎注入八种情形，8/8 必需断言成立，证据 `docs/execution/evidence/phase4/a1-status-protocol.json`）PASS，部分运行 `complete=false`；`acceptance_local.py --suites phase4 --group a1` 退出 1，裁决 PARTIAL，`unmet` 列出 a2—a5、b1—b3 的 `NO_CHECKS`。

**留给后续执行者**：阶段三其余 G 组证据脚本仍以退出码 + 引用文件为准，未改为结构化上报；B1—B3 负责把所属领域脚本的真实业务断言接到 `CheckResult`。
