# 阶段三交接（Phase 3：通用平台 + 领域集成）

本文件是阶段三的最终交接。整个阶段三共 **12 个交付包**：Opus 5.5 的 6 个通用交付包（G1–G6，任务书 [phase-3a.md](../execution/phase-3a.md)）与 Opus 4.8 的 6 个领域交付包（D1–D6，任务书 [phase-3b.md](../execution/phase-3b.md)）。各包完成时的详细证据（接口、代码路径、命令、结果）见 [phase3-draft.md](phase3-draft.md)；本文件给出总览、验收与保证范围。阶段二验收（提交 `4e1f959`，28/28）是历史证据。

配套：[assurance-scope.md](../assurance-scope.md)（保证范围）· [acceptance-phase3.md](../acceptance-phase3.md)（验收结果）· [research-readout.md](../research-readout.md)（研究读数）· [reuse-ledger.md](../reuse-ledger.md)（复用与许可）· [phase3.manifest.json](phase3.manifest.json) · [phase3-checks.json](phase3-checks.json)。

## 交付包总览

| 包 | 主题 | 检查组 | 关键证据 |
|---|---|---|---|
| G1 | 契约与插件兼容 | g1-contracts | 阶段二 v2 回放样本、兼容策略 |
| G2 | 执行扩展点与操作一致性 | g2-operations | g2-operations.json |
| G3 | 语义驱动、规则与发布能力 | g3-release | g3-release.json |
| G4 | 联合批次与参与者输入 | g4-batch | g4-batch.json |
| G5 | 前端、Figma、README、媒体 | g5-product | g5-flows.json、g5-web.json |
| G6 | 本地检查与发行工具 | g6-release | release-manifest.json、licenses |
| **D1** | MAL 模型与原生模拟器 | d1-mal | d1-mal.json |
| **D2** | Broker、领域规则与角色边界 | d2-broker | d2-broker.json |
| **D3** | 红蓝策略与模型修订闭环 | d3-strategies | d3-strategies.json |
| **D4** | 本地服务实验闭环 | d4-service | d4-service-lab.json |
| **D5** | CAGE 与配对评测 | d5-cage | d5-cage.json |
| **D6** | 领域内容接入与最终交付 | d6-domain | d6-domain-acceptance.json |

## 领域集成要点（D1–D6）

- **D1**：MAL/coreLang/mal-simulator 版本固定接入（独立 venv + 类型化子进程，D-028）；确定性子集降低到 `deterministic_finite_v1`，原生可达集为 fold 预言，原生/参考解释器/Z3/ir-world 四者一致；见证/无见证/未知/不支持/不可比真实记录。
- **D2**：领域准入 Broker 作为 G2 执行门控（D-029），验证凭据（HMAC 签名 + 绑定 run/step/actor/operation/参数摘要/状态修订/版本/范围/期限），LabPolicy/动作前提/角色/TargetSecurity 四类判定各自解释，正常放行 + 8 类零副作用拒绝，红蓝边界与标记数据泄漏检查。
- **D3**：红方规则/符号/混合三基线到达目标；蓝方最小代价割（最大流）阻断全部红方；检查点恢复保持计划进度；模型修订沿用 D-022（真实偏差修订成功、陈旧不污染回归库）（D-030）。
- **D4**：真实订单服务进程全生命周期（创建→就绪→业务→探针→导出→复位→二次运行→异常终止资源核对→清理），特权动作只经 Broker（拒绝不触达服务），探针独立读服务，与模拟器按可比较状态对照（D-031）。
- **D5**：固定 CAGE 4（CybORG 4.0，Scenario4）官方脚本基线（独立 venv，仅核心依赖，D-032）；原生分数与平台指标分开、不可比项说明；成对 dev/holdout 种子含不确定性、可重跑；MAL/CAGE/本地探针分域交叉检查；RL 智能体为条件项。
- **D6**：MAL 领域端到端经平台公开接口（导入→配置→运行→解释→导出→离线回放）；领域插件可被 Web/CLI 发现；发行自动纳入领域 wheel，MAL/CAGE 工具链为外部前提。

## 验收

- 入口：`make phase3-check`（阶段三全部组）、`make acceptance-local`（阶段二必做 + 阶段三 D1–D6）。
- 结果见 [acceptance-phase3.md](../acceptance-phase3.md) 与 [phase3-checks.json](phase3-checks.json)。
- **条件项 / 备选（未在本环境执行，不冒充交付）**：真实 LLM 端点（D3 混合策略，未配置则标注替身）；CAGE RL 训练智能体（需 torch/ray，D5）；PRISM-games 领域概率绑定（备选清单）；带 OCI 镜像发行与去重离线包（宿主盘低于 15 GiB 保留量时 BLOCKED）。

## 本地入口

```bash
# 领域证据（无需服务）
scripts/in-vm.sh 'export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/formal-agent-lab; export FAL_MAL_HOME=$HOME/.venvs/fal-mal; export FAL_CAGE_HOME=$HOME/.venvs/fal-cage; cd <repo>; uv run --no-sync python scripts/d1_mal_evidence.py'   # d2…d6 同理
# 检查与验收
make phase3-check ARGS="--group d1-mal"     # 单组
make acceptance-local                        # 阶段二必做 + 阶段三 D1–D6
```

外部前提安装（MAL / CAGE 独立 venv）见 [local-development.md](../local-development.md) 第 10–11 节；PRISM 见第 9 节。
