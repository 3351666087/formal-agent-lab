# 阶段二验收：运行与解读

验收入口是 **`make phase2-check`**（`scripts/phase2_check.py`），在本地完成，不以远程 CI 或镜像仓库发布为通过条件。结果写入 [`docs/handoff/phase2-checks.json`](handoff/phase2-checks.json)，每项检查的完整输出在 `docs/execution/evidence/phase2/checks/<id>.log`；交接文件 [`phase2.manifest.json`](handoff/phase2.manifest.json) 与 [`phase2.md`](handoff/phase2.md) 由 `make handoff-phase2` 从这份结果生成。安装与日常操作见 [local-development.md](local-development.md)。

## 1. 前提

| 需要 | 用于 | 检查 |
|---|---|---|
| 虚拟机 + `make bootstrap`（uv、Node、pnpm、Playwright Chromium） | 所有检查 | `make doctor` |
| Docker + 后端服务（`make services-up`，脚本会自动启动） | `local-services` 各组 | `python3 scripts/doctor.py --require local-services` |
| kind、helm、kubectl（`scripts/bootstrap-dev-vm.sh` 安装） | `kind-install-upgrade` | `make doctor`（local-kind） |
| 宿主机磁盘 ≥ 15 GiB 空闲 | 镜像、kind、离线包 | `make disk-guard` |
| `.env` 中的 `FAL_LLM_*`（可选） | 条件检查 `model-real` | 未配置时记为 NOT_RUN |
| 本地 PRISM-games（可选） | 扩展检查 `prism-games` | 未安装时记为 BLOCKED 并写明原因 |

完整运行约 1.5–2 小时（4 vCPU / 5.9 GiB 的虚拟机），重型检查串行执行，每个 Docker 检查后回收磁盘。只跑一部分：`make phase2-check ARGS="--group service-operations"`、`ARGS="--only compose-smoke,offline-install"`、`ARGS="--skip kind-install-upgrade"`。

## 2. 检查组

| 组（check_id） | 检查 | 验证什么 |
|---|---|---|
| compatibility | `contracts-v1-v2`、`phase1-parity`、`unit-all`、`api-cli-sdk-old-bundles` | v1 契约冻结且摘要不变、v2 生成无漂移、v1 样例经适配器读取；阶段一单参与者轨迹与哨兵；全部单元 / 架构 / 示例测试；API / CLI / SDK 与阶段一回放包 |
| semantic-driver | `driver-and-second-profile`、`second-profile-platform` | 内核只经语义驱动接口；仓储分配（第二 profile）在本地与平台上运行、回放；插件合同工具与包外插件（含任务计划与检查点） |
| planning-objectives | `objectives-unknowns-cache` | 成本最优（区间与已证下界）、未知补全与鲁棒序列、见证由解释器重放、缓存键覆盖查询边界、Z3 单独 / 批量结果一致 |
| multi-actor-recovery | `task-plans-and-turns`、`multi-actor-platform-recovery` | 两种确定性策略的轮次运行；任务计划检查点在新进程恢复后与不中断运行一致；暂停 / 继续 / 取消 / Worker 重启后的轮次、计数与计划进度；状态延迟报告 |
| service-operations | `order-service`、`order-service-platform`、`order-service-e2e` | 订单服务的业务动作、独立探针、响应丢失后按 id 对账、重复提交、重置与清理、五种案例；平台持久路径上 Worker 被杀与取消交错；空目录到清理的端到端（真实日志） |
| model-release | `rules-releases`、`difference-to-revision` | 规则类型检查、发布记录、回归案例、效果证据等级；“差异 → 定位 → 新版本 → 检查 → 新实验”的 API / CLI 路径与规则暂停 |
| evaluation-replay | `reports-offline`、`matrix-v2-platform` | 配对比较与消融、开发 / 验收划分、按场景聚类统计、探针来源；空目录离线读包与报告；矩阵队列恢复 / 重跑 / 合并 / 复用；按轮次、计划、操作、模型版本定位的回放 |
| product-path | `web-product`、`sdk-vertical` | Web：新项目 → 两参与者成本对比 → 离线回放、界面状态截图、首屏体积与大轨迹测量；公共 SDK / CLI 完成同一路径 |
| local-release | `compose-smoke`、`orders-compose`、`offline-install`、`release-manifest`、`kind-install-upgrade`、`backup-restore` | 原生 arm64 Compose 整栈；订单服务 Compose 生命周期；离线包（镜像去重、空目录无包仓库安装、演示）；发行 manifest（摘要、异架构状态、许可证、资源读数）；kind 安装与从阶段一版本升级 / 回滚；备份 → 重置 → 恢复 |
| resource-profile | `doctor`、`concurrency` | 三个 profile 的可用性、资源估计与端口冲突；按实测资源设定并发，1 并发基线与 2 并发测量 |
| 条件：model-real | `model-real` | 真实模型端点：请求可复现、证据完整 |
| 扩展：prism-games | `prism-games` | PRISM-games 概率查询、策略导出、独立求解器核对、类型化扩展与 UI |

## 3. 结果怎么读

- 每项检查记录 `checked_commit`、工作区摘要（`worktree_sha256`：未提交改动与未跟踪文件的摘要；验收自身写出的证据、日志、交接文件与任务书勾选不计入，见 `excluded_outputs`）、profile、命令、退出码、开始 / 结束时间、耗时、日志与证据路径。
- 结果：**PASS** / **FAIL**（退出码非 0，`summary` 是日志最后一行）/ **NOT_RUN**（前提缺失，写明原因）/ **NOT_SELECTED** / **BLOCKED**（可选轨道的前提缺失，写明原因与解除条件）。
- **组状态**：组内全部检查在当前提交与工作区上 PASS 才是 PASS；有 FAIL 为 FAIL；否则 INCOMPLETE。部分重跑时，其它提交或工作区上的旧结果保留为 `inherited: true`，只作历史证据，不计入当前 PASS（P2-117）。
- `mandatory_passed` 为 true 且所有必做任务已勾选时，交接状态才是 `complete`（`make handoff-phase2` 判定）；条件与扩展检查单独列出，不影响必做结论。

## 4. 主要证据与解读

| 证据 | 解读 |
|---|---|
| `evidence/phase2/orders/comparison.md` | 业务服务与纯数据模拟在五种案例上逐步对照：状态差异为 0 才说明适配器与模型一致；慢工位对照中的差异是有意设置的定位样例 |
| `evidence/phase2/state-delay/report.md` | 延迟观测下各策略的拒绝、停滞、无进展停止；任务计划策略应零拒绝完成 |
| `evidence/phase2/offline-report/index.md` | 空目录离线读包：每个模型包一份报告，被篡改的包必须被拒绝 |
| `evidence/phase2/web/measurements.json` | 首屏体积（gzip）与大轨迹（数千事件）的加载、表格与滚动耗时 |
| `evidence/phase2/concurrency.json` | 读数先于设置：允许并发 = min(2, 可用 CPU, (可用内存 − 1 GiB) ÷ 单次峰值) |
| `evidence/phase2/backup-restore.json` | 重置后行数为 0、恢复后与备份一致、重新导出的回放包内容逐文件相同 |
| `evidence/helm/upgrade.json` | 阶段一 Chart 安装（迁移 0001）→ 升级（0002）后旧运行可读且新实验成功 → 回滚后阶段一应用在 0002 上仍能服务与运行；仅限单节点开发集群 |
| `evidence/phase2/release-manifest.json` | wheel / Web / 镜像摘要与来源修订；amd64 的构建、仿真运行、原生运行分别报告 |
| `evidence/phase2/prism-games/summary.json` | 概率数值与独立求解器一致（1e-6）、状态数一致、导出策略达到报告值 |

## 5. 失败时

1. 看 `phase2-checks.json` 中该项的 `summary` 与日志；日志第一行是实际命令，可直接在虚拟机中重跑。
2. 修复后只重跑该项：`make phase2-check ARGS="--only <id>"`。在同一提交与工作区上的其它结果仍然有效；提交了修复后，其它检查会变为历史结果，需要全量重跑才能得到 `complete`。
3. 结束后清理：`make dev-down`；kind 集群由脚本删除；`make disk-guard` 归还磁盘。
