<!-- 任务书原文：~/Downloads/05B_opus4_8_software_models.md（编制 2026-10-06，核对基线 a05c1d2）；复选框编号 P5B-01 / P5B-02 与原文一致，scripts/tick.py 记录证据。开发执行者：Opus 4.8。前置 docs/execution/phase-5a.md；交接 docs/handoff/phase5.md。 -->

# Phase 5B：有真实程序依据的软件安全模型

执行者：Opus 4.8。基线 `a05c1d2`，实际在 5A 之上（4d79513）推进。

回答对现有模型的核心质疑：模型中的主体能力、动作和成功判据，究竟对应程序里的什么行为。交付一个有真实程序观测支撑的本地安全性质案例，并用修复前后回归验证它的对应关系。沿用已同意的实验范围：本地自有实例、测试数据、透明的软件验证用途；合成表示研究单独属于 Phase 6。不构建真实攻击模型的无关业务伪装，不以诱导提供方绕过监管为验收条件，不生成攻击第三方系统的执行链。本地运行不等于模拟成功：使用实际进程、接口、存储与独立观测；程序侧判据和模型结论分别保存。

## B1 · 一个实现级案例

- [x] **P5B-01** 交付一个主体能力和动作语义明确的软件安全性质案例，能够在本地真实服务上观测。
  - 证据：research/cases/orders-tenant-isolation built+validated by scripts/p5b_isolation_case.py at 8d80e34; secure-spec model tenant_isolation invariant (Z3 NO_WITNESS_WITHIN_BOUND); observed on the real fixture over SQLite, oracle reads state back; MECHANISM.md one-page note
  - 实现：`examples/local-order-service/src/formal_lab_example_orders/research_isolation.py`、`scripts/p5b_isolation_case.py`

首个案例取订单服务的租户/对象访问隔离性质。先核实服务实际身份与权限能力（已有租户 URL ≠ 已有用户认证）：基础服务只有一个粗粒度写令牌、读开放，租户只是路径段与 SQLite 文件，没有按租户的授权。以独立测试模块 `research_isolation.py` 补齐最小可验证的授权层（项目自有研究夹具，与默认启动路径分离，普通示例不变）。缺陷/修复为该授权组件上的一个配置位：`authenticate_only` 省略对象级租户授权检查（缺陷），`per_tenant` 执行它（修复）。

先提交一页机制说明（`MECHANISM.md`：主体 / 资源 / 能力 / 信任边界 / 动作 / 性质 / 裁判），再据此建模。性质 `tenant_isolation`（不变式）：`forall s,t: accessed[s][t] -> grant[s][t]`。每个关键动作有真实操作与独立观测对应证据（裁判用该租户自身授权主体读回真实状态）；观测不到的状态保持未知。按 5A 协议输出到 `research/cases/orders-tenant-isolation/`，程序侧参考材料不进入模型待测输入。

## B2 · 修复前后核验与模型可信度

- [x] **P5B-02** 完成缺陷/修复变体的独立回归核验、模型与程序对应报告，并交接 Phase 6 所需任务材料。
  - 证据：defect DEVIATES / fix CORRESPONDS / rejected-write UNKNOWN (three result classes); regression test_research_isolation.py 6 PASS; model/program/correspondence kept apart; Phase 6 handoff contract in docs/research/protocol.md; make research-check ARGS=--group p5b → p5b PASS
  - 实现：`examples/local-order-service/tests/test_research_isolation.py`、`scripts/p5b_case_check.py`、`scripts/research_checks.py`

用夹具自身的最小验证用例，保持两侧输入、初始条件与环境可比较，记录构建/启动/就绪/运行/复位/二次执行/清理。分别保存程序侧实际结果、模型预测、形式检查结果、两者对应证据与未验证范围。用同一可信机制对三类结果验收：模型与程序对应（修复 CORRESPONDS）、存在真实模型偏差（缺陷 DEVIATES）、证据不足无法判定（业务拒绝写入 UNKNOWN）。单次回归通过不升级为完整语义等价证明；无法确认的模型路径不自动登记为真实缺陷。

目标性质绑定实际查询表达式、模型摘要、界限、状态与验证结果引用；模型内结论为 Z3 `INVARIANT_VIOLATION(tenant_isolation)`。`K01`（MAL 目标与凭据错配）、`K02`（领域预算字段未执行）：本阶段未复用其路径，保留 OPEN 及影响说明，Phase 7 收尾；`K03` 前端详情保留给通用收尾。

## 外部方法

抽象精化核查思想（Kroening ICCAD'07）仅借鉴概念、自行实现（`decide_correspondence` 的 `UNCONFIRMED`/`SPURIOUS` 区分）。CBMC 仅当案例是适合它的 C 片段时按子进程工具适配；本阶段案例为 Python，未安装、未依赖。方法参考与代码复制分别记入 `docs/reuse-ledger.md`。

## Phase 6 交接

在 `docs/research/protocol.md` 登记案例可供模型读取的任务材料（`task_input`：模型 + 性质 + 机制 + 授权表）、提供方不可见的参考答案（`reference`）、独立评分接口（复用 `fal-conformance-result/v1` 与案例回归），以及候选集/反馈策略；无辅助与已有辅助任务分别说明。模型回答只作待验证分析产物；没有把自由文本译成执行指令的组件。证据进入 `docs/execution/evidence/research/p5b/`，注册 `p5b`。

```bash
make research-check ARGS="--group p5b"
```

## 完成与停止条件

Phase 5 完成意味着一个可重建、可核查的程序—模型案例成立，不直接宣称通用攻击建模能力。真实服务运行缺失、目标性质未经核查、必要工具缺失、只有模型自报成功时，相应项保持未完成。最终回复给出两任务状态、案例 ID 与源码修订、程序/模型对应结论及范围、本地复现命令、参考答案与模型输入边界、K01/K02 状态与 Phase 6 入口。研究局限保留原样。
