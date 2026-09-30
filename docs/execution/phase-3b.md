<!-- 任务书原文：~/Downloads/03_phase3_domain_integration .md（修订 2026-09-29）；复选框编号改为 P3B-D1…D6 以便 scripts/tick.py 记录证据。交接记录：docs/handoff/phase3-draft.md。 -->

# Phase 3B：领域集成与最终收口（Opus 4.8）

项目：https://github.com/3351666087/formal-agent-lab
修订日期：2026-09-29
前置：先完成 **phase-3a.md** 的 G1—G6，再执行本文件 D1—D6。执行顺序 D1 → D2 → D3 → D4 → D5 → D6。

## 工作量与交接边界

整个 Phase 3 共 **12 个交付包**：Opus 5.5 的 6 个通用交付包（G1—G6，见 [phase-3a.md](phase-3a.md)），以及本文件的 6 个领域交付包（D1—D6）。原 105 项主线要求合并为交付条件，原选配与后续部署移到文末备选清单。每包完成后在同一交接记录 [docs/handoff/phase3-draft.md](../handoff/phase3-draft.md) 追加一段证据，跨会话从该记录接续。基线 `0ae45712f6f7287acebec66836d0e1d70ca4fc1d`；阶段二产品验收 `4e1f959e81f282fd0b3d05103b5734437d357644` 为历史证据。

| 已由 Opus 5.5 交付 | 本文件负责的增量 |
|---|---|
| G1：契约、兼容、插件协议 | 领域载荷、配置与能力声明 |
| G2：执行决策接口、协调、去重和恢复 | Broker、VerificationReceipt、领域准入及其真实绑定 |
| G3：规则/驱动能力与发布检查 | 领域规则、性质、映射及保证范围 |
| G4：联合批次、参与者输入构造 | 上游原生轮次适配、红蓝可见性规则与身份边界 |
| G5：前端、Figma、README、SVG 动画和元数据接口 | 领域内容、字段、资产图映射、演示数据与必要视觉微调 |
| G6：本地检查、发行工具及交接骨架 | 领域检查注册、插件打包、一次最终产品验收与完整交接 |

## D1 · MAL 模型与原生模拟器

- [x] **P3B-D1** 完成 MAL/coreLang/MAL Simulator 的真实接入，以及最小确定性形式化闭环。
  - 证据：MAL/coreLang/mal-simulator 版本固定接入（隔离 venv + 类型化子进程，D-023 同模式）；场景包导入/展示/运行；确定性子集降低到 deterministic_finite_v1，原生可达集为 fold 预言，原生模拟器/参考解释器/Z3/ir-world 平台运行四者一致；见证/无见证/未知/不支持/不可比真实记录；LabPolicy/TargetSecurity/BusinessSLO 分开；离线可查。详见 docs/handoff/phase3-draft.md 阶段 3B · D1
  - 实现：`packages/domain-mal/src/formal_lab_domain_mal/lowering.py`、`packages/domain-mal/src/formal_lab_domain_mal/frontend.py`、`packages/domain-mal/src/formal_lab_domain_mal/config.py`、`packages/domain-mal/src/formal_lab_domain_mal/run.py`、`packages/environment-mal/src/formal_lab_env_mal/bridge.py`、`packages/environment-mal/src/formal_lab_env_mal/_worker.py`、`packages/environment-mal/src/formal_lab_env_mal/importer.py`、`packages/domain-mal/scenarios/net_app_data.scenario.json`、`scripts/d1_mal_evidence.py`、`scripts/phase3_check.py`

固定能共同运行的上游版本、摘要和许可，通过实际公开 API 导入模型、构图、运行模拟器。保留原始模型、语言版本、源位置与平台载荷；映射资产、关系、主动动作、防御配置、自动传播、时间与成本，新增扩展与上游原生能力明确区分。首个闭环采用可准确降低到已有有限确定性 IR 的子集，复用 IRFiniteDriver、Z3、G3 的规则/发布能力；小模型逐步核对 lowering 与原生后端。其他语义独立声明 profile 或 UNSUPPORTED。领域配置明确区分 **LabPolicy**（实验边界）、**TargetSecurity**（目标系统性质）、**BusinessSLO**（业务目标）；红方寻找 TargetSecurity 反例不能被当成违反 LabPolicy。

**直接复用：** mal-toolbox、coreLang、mal-simulator 与其动作/效果说明；平台 `packages/model-core/`、`packages/solver-adapters/z3/` 与 G1/G3 接口；领域包 `packages/domain-mal/`、`packages/environment-mal/`。

**完成证据：** 版本固定的 YAML/JSON 场景包能够导入、展示、运行；主动动作与自动效果有对照；见证、未知、超时/不支持与无法比较情况有真实记录，结论可离线查阅。

## D2 · Broker、领域规则与角色边界

- [ ] **P3B-D2** 在 G2—G4 的接口上完成领域准入、验证凭据和红蓝数据边界，验证拒绝零副作用。

实现领域动作合同（参数、环境/session、可观测前提、预期效果、失败/未知结果、时间、重试和探针）；类型化规则表达事件—条件—处理，自然语言转换的规则先可审查、再固定版本发布。VerificationReceipt 用成熟签名库与固定规范化格式，绑定 run/step/turn/actor、环境/session、operation_id、动作参数摘要、状态修订、模型/适配器/规则/投影版本、检查依据、范围及期限；Broker 验证绑定、服务身份与当前状态。通过 G2 的发送扩展点覆盖 local runner、Temporal、重发与模拟器重执行。使用 G4 参与者输入接口实施领域可见性；真值/凭据不进入策略工厂、调用记录、恢复或下载路径。

**完成证据：** 正常动作可执行；拒绝、错角色/环境、过期/旧修订为零副作用；同 id 异参、两 Worker 竞争、取消、丢响应后重启按合同处理；标记数据检查隐藏真值不泄漏；记录实际隔离强度。

## D3 · 红蓝策略与模型修订闭环

- [ ] **P3B-D3** 交付确定性红蓝基线、混合策略和独立结果复核，完成一次领域模型修订。

红方规则/符号策略与蓝方规则策略（蓝方在业务代价下选择观测、配置和恢复）；再实现混合策略统一输出 ActionProposal，复用 TaskPlan、CheckpointingPlanner、模型客户端、预算、调用记录与暂停恢复。规则/符号/混合使用相同角色可见信息，真值保留给独立裁判。区分陈旧观测、不完整信息、随机结果与真实模型偏差（D-022）；可比较状态上的真实偏差才产生修订/回归案例。

**完成证据：** 固定场景/种子/预算下双方基线完成实验；检查点恢复保持计划进度；真实模型条件项如实报告；一次真实偏差修订成功、一次旧观测差异不污染模型回归库。

## D4 · 本地服务实验闭环

- [ ] **P3B-D4** 在已有订单服务与生命周期上完成一个领域场景，保持正常业务与独立探针。

保留原订单样例，在独立场景包中增加领域状态和预定义管理/测试接口；合同动作只通过 D2 的执行路径调用。正常业务持续运行，探针独立记录访问、配置、服务状态、成功率、代价与恢复。复用 SessionEnvironment、Probe、reset/export/import/cleanup、Compose 与备份/恢复工具。

**完成证据：** 自动创建 → 就绪 → 正常业务与领域实验 → 探针 → 导出 → 复位 → 第二次运行 → 清理；异常终止后也能核对资源；与模拟器同合同、同可比较状态对照，保存一致、模型偏差与无法判断的情况。

## D5 · CAGE 与配对评测

- [ ] **P3B-D5** 完成 CAGE 4 的一个明确官方场景/公开基线往返，以及平台上的可复现配对比较。

固定 CAGE 4 版本，先跑公开基线记录原生观测/动作/world_step/联合动作/自动参与者/奖励与终止；再薄适配平台，需要联合步时用 G4 的批次能力，一次原生世界步只推进一次；Python 依赖冲突用独立 venv/容器与类型化进程接口。复用矩阵、数据划分、配对种子、聚类统计与离线报告。

**完成证据：** 官方基线与平台路径的轮次/结果可核对；CAGE 原始分数与平台指标分别保留并说明不可比项；MAL、CAGE 与本地探针在各自语义范围内交叉检查；同配置可重跑，数据和版本可追溯。

## D6 · 领域内容接入与最终本地交付

- [ ] **P3B-D6** 在已定稿的产品视觉和发行工具上完成领域接入，并统一完成本地主线验收。

视觉只作接入级微调（复用 G5 的 `docs/design-system.md`、tokens、组件、Figma 与基准截图，只增加领域字段/标签/资产关系图/角色视图/动作解释/Broker 状态/偏差内容）。README 与 SVG 动画保持 G5 结构，将已实现领域能力与真实截图/轨迹补入现有槽位。发行在既有 OCI/Compose/Helm、wheel 与离线包中增加领域依赖，交付 local-simulation、local-service-lab、local-offline 三种配置；领域检查注册进 G6 工具。最终提供 `make phase3-check` 与 `make acceptance-local`，运行阶段二 26 项必做回归与 D1—D6 适用检查。最终补齐 `docs/handoff/phase3.md`、`phase3.manifest.json`、`phase3-checks.json`，同步 `docs/assurance-scope.md`、`docs/acceptance-phase3.md`、`docs/research-readout.md`、`docs/reuse-ledger.md`。

**完成证据：** Web/API/CLI/SDK 完成导入、配置、运行、解释、导出与离线回放；从空目录安装发行包并运行真实实验；六个交付包的代码、命令、日志及产物可查；未完成必做时不标整体 complete。

## 备选清单：当前不执行

保留原选配/后续部署状态，只有用户以后明确选择时才执行：CALDERA、Strix、Cyberwheel/FIREWHEEL、PRISM-games 领域概率绑定、Pro2Guard/ProbGuard、VeriGuard 完整程序证明后端、CyberGym/历史题库、CAI、Keycloak 多人 OIDC，以及公网/多人生产部署/托管持久服务/多节点/远程 VM 等后续部署。可选轨道和云部署不计入本地主线完成条件。
