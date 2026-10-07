<!-- 任务书原文：~/Downloads/05A_opus5_5_case_foundation.md（编制 2026-10-06，核对基线 a05c1d2）；复选框编号 P5A-01 / P5A-02 与原文一致，scripts/tick.py 记录证据。开发执行者：Opus 5.5。交接：docs/handoff/phase5.md。 -->

# Phase 5A：案例、模型与证据基础

执行者：Opus 5.5  
项目：https://github.com/3351666087/formal-agent-lab  
编制日期：2026-10-06  
核对基线：`a05c1d22006b864c336a907a1826b15e9ea7593a`（v0.4.0 后的交接提交）  
执行顺序：**5A → 5B → 6A → 6B → 7**。本文件完成后交接 [05B](05B_opus4_8_software_models.md)。

## 本轮交付目标

在现有平台上建立可追溯的软件验证案例，把源码版本、模型、假设、程序观测和验证结果关联起来。本文件负责通用机制，以现有订单服务和无害的有限状态样例独立验收。

整个 Phase 5—7 有两条分别统计的实验线：`implementation_conformance` 是保留实际用途说明的软件模型验证；`synthetic_representation` 是独立、无现实攻击用途的合成问题表示对照。后者使用固定、人工审定的题面，研究表示敏感性。本轮没有把真实攻击用途隐藏为无关业务、借此规避提供方安全机制的交付项；最终报告必须保留该范围差异。

平台、程序实例、验证器、数据库和证据都在本地运行；Phase 6 的模型推理通过在线 API 完成。沿用现有前端风格、插件、Temporal、PostgreSQL、FastAPI 和发行方式。研究结果为负也可以完成交付。

## 接手与工作量约定

读取实际 HEAD、工作区、适用的 `AGENTS.md`、`docs/handoff/phase4.md`、`docs/assurance-scope.md`、`docs/research-readout.md`。基线前进时先检查已有实现，保留用户改动。运行现有 `make doctor`，重型任务串行；云部署、RL 训练、新模拟器和视觉重做沿用后续范围。

本文件只有下面两个交付项。接口细节和验收例子属于这两项，避免拆成新的独立阶段。先复现缺口，再做最小兼容修改；验证只覆盖真实风险和必要回归。v1 契约保持冻结，v2 增量兼容，已有回放包继续可读。

## 已有实现：直接复用

| 用途 | 现有路径 | 使用方式 |
|---|---|---|
| 对象和插件接口 | `packages/contracts/src/formal_lab_contracts/objects.py`、`interfaces.py` | 继续使用 ModelPackage、ModelFrontend、SemanticDriver、Verifier、Environment、Evaluator；案例研究元数据优先使用独立版本化 schema 与现有扩展引用 |
| 有限模型 | `packages/model-core/src/formal_lab_model/frontend.py`、`driver.py` | 复用编译、类型检查、状态与动作解释，维持语义能力声明 |
| 形式验证 | `packages/solver-adapters/z3/` | 沿用当前有界检查和结果类型 |
| 本地运行与证据 | `packages/runtime/src/formal_lab_runtime/local_runner.py`、`artifacts.py`、`bundles.py` | 复用执行、产物摘要和回放；研究案例索引引用产物，不另建存储系统 |
| 模型修订 | `packages/contracts/src/formal_lab_contracts/governance.py`、`packages/platform-api/src/formal_lab_api/services/governance.py` | RegressionCase 表示已有行为偏差，研究案例包负责更宽的源码和实验来源关系 |
| 检查器 | `scripts/check_runner.py`、`check_result.py`、`evidence_io.py`、`phase4_check.py` | 沿用 nonce、证据新鲜度、严格状态与断言规则 |
| 展示 | `web/src/pages/ModelWorkbench.tsx`、`Evidence.tsx`、`Benchmarks.tsx` | 在现有页面增加必要的来源和对应关系，不新增一套导航 |

## A1 · 案例协议与来源关系

- [x] **P5A-01** 交付最小案例协议、导入校验与来源展示，并用一个普通业务案例跑通。
  - 证据：make research-check ARGS="--group p5a" → p5a PASS (p5a-unit 14, p5a-case 7 assertions); research/cases/orders-p2-speed built+validated by scripts/p5a_orders_case.py (belief DEVIATES, revised CORRESPONDS)
  - 实现：`packages/contracts/src/formal_lab_contracts/research.py`、`packages/runtime/src/formal_lab_runtime/research.py`、`scripts/p5a_orders_case.py`、`packages/platform-api/src/formal_lab_api/services/research.py`

建议目标位置为 `research/cases/<case_id>/case.json`；这是新增位置，不是当前已有文件。协议名固定为 `fal-research-case/v1`。5A 在现有合适包内确定实现位置并写入交接，后续文件复用它。

最少包含以下内容，字段实现可适配现有契约：

| 字段组 | 必须表达的内容 |
|---|---|
| 身份 | case_id、case_version、track、mechanism_family、可读的 purpose |
| 软件来源 | 仓库与许可、实际源码修订和目录、构建与运行依赖摘要；自有测试变体明确标注，不冒称上游发布版本 |
| 比较版本 | before/after 的各自修订或产物摘要、变更依据、回归测试来源；不存在某一侧时明确说明 |
| 模型 | ModelRef、semantic_profile、性质 ID 和性质表达式摘要、输入与执行界限、抽象假设与未覆盖语义 |
| 对应关系 | 程序组件与模型状态/动作/观测的来源引用；关系类型区分人工审阅、实测对应与形式证明 |
| 验证材料 | 测试夹具、预期判据、验证结果和程序观测的 ArtifactRef；参考答案单独保管 |
| 复现 | 本地环境入口、重置/清理方式、种子或外部非确定性、已执行命令与前提 |

软件版本、模型版本和后续提供方模型版本是三种不同身份，分别记录。修复提交的前一个提交不自动等于有效的缺陷基线；协议容纳真实构建前提与多个相关修订，由 5B 核实。

导入时拒绝失效引用、性质 ID 与表达式摘要不符、before/after 产物误引用和案例内容被修改但摘要未更新。文件存在只证明材料存在。源码 revision + relevant tree/config digest 与产物摘要一起构成来源，避免仅靠文件名判定对应。

首个普通业务样例可复用订单服务中处理速度的模型/实际偏差。它只验收通用协议，5B 再提供领域性质。验收输出必须能从一条结论定位到模型、程序版本、观测和测试。

## A2 · 对应验证、展示与后续检查接口

- [x] **P5A-02** 交付模型—程序对应验证的通用接口、案例证据视图和 Phase 5—7 共用检查入口。
  - 证据：fal-conformance-result/v1 + replay_conformance/decide_correspondence; ModelWorkbench 研究案例 + Evidence 对应验证 tabs; make research-check (groups p5a–p7, selected_passed+overall_complete); tests/tools/test_research_{validate,conformance}.py + tests/integration/test_research_platform.py
  - 实现：`scripts/research_check.py`、`scripts/research_checks.py`、`web/src/pages/Evidence.tsx`、`web/src/pages/ModelWorkbench.tsx`

对应验证报告协议为 `fal-conformance-result/v1`，至少包含案例/模型/软件引用、property_id 与 property_digest、bound、assumptions、模型结论、程序侧观测、逐项对应结果和验证工具身份。

区分三层结果：模型内检查结论、程序回归测试结果、二者是否在声明范围内对应。单次回归通过不升级为完整语义等价证明。`UNKNOWN`、超时、未支持语义和无法比较的观测保持独立状态。无法具体核实的模型反例记为 `UNCONFIRMED`；有证据证明来自抽象误差的才记为 `SPURIOUS`。

参考答案与程序侧裁判数据仅用于验证。本轮预留独立的任务输入产物；Phase 6 能明确选择输入，而不是把完整研究案例包直接发送给模型。这里验收数据分离和引用，不实现跨领域用途伪装或反向执行转换器。

展示沿用 ModelWorkbench/Evidence：性质、假设、界限、软件与模型版本、观测、对应状态均可定位。既有视觉规范继续使用。信息不足时展示未知与原因。

新增薄的 `scripts/research_check.py`，复用 `check_runner.py`，固定组 `p5a,p5b,p6a,p6b,p7`，给 `Makefile` 增加 `research-check`。后续组尚未登记时为 NO_CHECKS/未完成；只运行一组时不能把整体标为完成。沿用 `fal-check-result@1`，严格总验收在必做项 FAIL/BLOCKED/NOT_RUN/缺证据时返回非零。普通分组命令是否返回零按现有局部检查协议，报告始终同时给出 selected_passed 与 overall_complete。

完成时运行有意义的验证：合法普通样例、性质错配、版本错配、缺观测、陈旧证据、模型与实际存在偏差、离线读取。每个例子都有实际结果，避免只对手写布尔值断言。复用 `tests/tools/test_check_status.py`、`test_evidence_io.py` 的模式。

## 五份文件共用的交接协议

以下为本轮目标路径，5A 创建基础，后续阶段增量更新：

- `docs/research/protocol.md`：已实现的数据协议、字段映射、方法与范围。
- `docs/research/known-gaps.md`：已知缺口与原始研究目标覆盖情况。
- `docs/handoff/phase5.md`、`phase5.manifest.json`：5A/5B 各自状态和证据。
- 后续 `docs/handoff/phase6.md`、`phase6.manifest.json`，最终 `phase7.md`、`phase7.manifest.json`。
- `docs/execution/evidence/research/<stage>/`：每阶段验收摘要；较大的原始记录使用已有产物存储及摘要引用。
- `research/studies/<study_id>/`：Phase 6 创建研究定义；`research/results/<study_id>/`：其结果索引。

manifest 沿用当前 `phase-handoff/v1` 的兼容方式，阶段元数据扩展为任务状态、source_revision、配置摘要、命令、证据、blocked、下一阶段接口及假设。未经验证的能力标明计划或未运行。

验收目标入口（当前基线尚不存在）：

```bash
make research-check ARGS="--group p5a"
```

将上轮三项记录到 known-gaps，暂不因此额外开启阶段：`K01` 目标性质与凭据错配；`K02` LabPolicy.max_attack_steps 未执行；`K03` 门控详情未显示 detail。5B 判断 K01/K02 是否影响其实际路径；Phase 7 统一确认关闭情况。

## 可直接采纳的方法与交付回复

采用“独立程序观测核查抽象结论”的思路。参考《Formal Verification at Higher Levels of Abstraction》：https://www.kroening.com/papers/iccad2007.pdf 。本项目当前实现经验对应验证时准确使用该表述；正式的抽象保持性证明需要另外提供。

本阶段以现有 Z3 与本地订单服务完成；CBMC 作为 5B 的按语言条件启用项，不成为本阶段安装前提。所有外部方法和实际引入的代码分开记录，新增依赖核对版本与许可。

最终回复给出两个任务的实际状态、源码修订、协议与导入入口、普通业务样例的证据、未覆盖能力，以及 5B 可直接使用的函数/契约/命令。5A 完成只标记通用基础完成。
