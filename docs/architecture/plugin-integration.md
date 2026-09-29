# 插件接入指南（formal-lab-contracts/v2）

扩展能力一律以**插件**接入：实现 `formal_lab_contracts.interfaces` 中的一个协议，用 `PluginDescriptor` 声明版本、能力、语义 profile、配置 schema 与界面元数据，并通过 entry point 注册。核心包（contracts / model-core / runtime / platform-api / orchestrator / sdk）从不 import 插件，只经注册表创建实例（`tests/architecture/test_boundaries.py` 检查）。包外插件只依赖 `formal-lab-sdk`：`formal_lab_sdk.plugins` 再导出下文所有协议与数据对象，`formal_lab_sdk.plugin_testing` 按内核的生命周期检查插件。

## 1. 注册机制

```toml
# 插件包的 pyproject.toml
[project]
dependencies = ["formal-lab-sdk"]          # 包外插件只需要公开 SDK（带来 formal-lab-contracts）

[project.entry-points."formal_lab.plugins"]
my-plugin = "my_package:registrations"
```

```python
from formal_lab_sdk.plugins import PluginDescriptor, PluginRegistration

DESCRIPTOR = PluginDescriptor(
    plugin_id="org.example.my-planner", version="0.1.0", interface="PLANNER",
    capabilities=[{"id": "plan.rule"}], semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "properties": {...}, "additionalProperties": False},
    entrypoint="my_package:create", ui={"label": "My planner", "category": "rule"},
)

def create(config: dict, services) -> "MyPlanner":      # PluginFactory(config, services)
    return MyPlanner(config)

def registrations() -> list[PluginRegistration]:
    return [PluginRegistration(DESCRIPTOR, create)]
```

- 注册表（`formal_lab_runtime.registry.PluginRegistry`）在 API 与 Worker 启动时发现 entry point，校验 `contract_version` 与 `interface_version`（`"1"` 或 `"2"`；`SEMANTIC_DRIVER`、`PROBE` 只有 `"2"`），记录描述符摘要，同步到 `plugin_catalog` 表与 `GET /api/v1/plugins`。加载失败的插件记入 `plugin_load_errors`，不影响平台启动。
- 运行创建时 `RunManifest.plugins` 固定每个角色（environment / strategy:<actor> / verifier / evaluator:<i> / driver）的插件 id、版本、接口版本与描述符摘要；之后安装新版本不影响已创建的实验。配置按 `config_schema` 在 API 保存场景与 Worker 打开运行时用同一函数校验。
- `services`（`PluginServices`）提供 `pinned_model()`、`get_model(ref)`、`get_setting(key)` 与 `loaded_model()`（按模型 profile 由语义驱动加载）；密钥只从设置读取，永不出现在契约对象中。
- 能力协商：运行 manifest 的 `negotiation` 为每个插件列出所需与获准的能力及理由；不支持的组合在运行开始前拒绝。
- 界面：`PluginDescriptor.ui` 的 `label/description/category/state_labels/action_labels/action_display/metric_labels/value_labels` 决定 Web 中的显示，配置表单由 `config_schema` 渲染。核心 UI 不写领域代码。

## 2. 接口一览：协议、数据对象、枚举与记录

插件**实现协议**（行为），平台与插件之间**交换数据对象**（Pydantic 契约对象，有 JSON Schema 与 TypeScript 类型），内核**写记录**（插件不产生）。

| 名称 | 种类 | 定义 | 谁实现 / 谁产生 | 能力声明 |
|---|---|---|---|---|
| `ModelFrontend` | 协议 | `interfaces.py` | 插件（MODEL_FRONTEND） | — |
| `SemanticDriver` | 协议 | `interfaces.py` | 插件（SEMANTIC_DRIVER，v2） | `profile.<name>`、`driver.*` |
| `LoadedModel` | 协议 | `interfaces.py` | 驱动的 `load()` 返回的对象（不是插件本身） | 同驱动 |
| `Prediction` | 数据类（非契约对象） | `interfaces.py` | `LoadedModel.predict()` 返回 | `driver.predict` |
| `Planner` | 协议 | `interfaces.py` | 插件（PLANNER） | `plan.*` |
| `CheckpointingPlanner` | 协议（可选扩展 `Planner`） | `interfaces.py` | 有记忆的规划器 | `plan.checkpoint`、`plan.task_plan` |
| `PlannerCheckpoint`、`TaskPlan` | 数据对象 | `execution.py` | 规划器产生，内核持久化 | — |
| `Verifier` | 协议 | `interfaces.py` | 插件（VERIFIER） | `query.*` |
| `Environment` | 协议 | `interfaces.py` | 插件（ENVIRONMENT） | `env.*` |
| `SessionEnvironment` | 协议（可选扩展 `Environment`） | `interfaces.py` | 持久业务服务的适配器 | `env.persistent_session`、`env.query_operation` … |
| `EnvironmentSession` | 数据对象 | `execution.py` | 会话环境产生 | — |
| `Probe` | 协议 | `interfaces.py` | 插件（PROBE，v2） | `probe.metrics` |
| `ProbeResult` | 数据对象 | `execution.py` | 探针产生，带 `EvidenceRef` 来源 | — |
| `TurnScheduler` | 协议 | `interfaces.py` | 内核（`formal_lab_runtime.turns.CycleScheduler`）；`TurnPolicy` 选择模式 | — |
| `TurnPolicy`、`TurnRef`、`TurnState` | 数据对象 | `kernel.py` / `execution.py` | 场景声明 / 内核记录 | — |
| `Evaluator` | 协议 | `interfaces.py` | 插件（EVALUATOR） | `eval.applies_to` |
| `ArtifactStore` | 协议 | `interfaces.py` | 平台（本地 / S3） | — |
| `ExecutionStage`、`StageStatus`、`RetrySemantics` | 枚举 | `kernel.py` | — | — |
| `StageRecord`、`StepRecord`、`OperationRecord` | 记录 | `execution.py` | 内核写入（插件不产生） | — |

## 3. 各类扩展

### 3.1 模型前端（MODEL_FRONTEND）

```python
class MyFrontend:
    descriptor = DESCRIPTOR   # interface="MODEL_FRONTEND"
    def compile(self, source: ModelSource, *, package_id: str, version: int) -> ModelPackage: ...
```

IR 格式用 `formal_lab_model.build_package` 做类型检查、规范化与摘要（参考 `formal_lab_model/frontend.py`）；非 IR 格式产出 `payload.kind = "namespaced"` 的包，由同 profile 的语义驱动校验（参考 `examples/warehouse-allocation/.../plugins.py::WarehouseFrontend`）。格式不支持 → `Unsupported`；源有错误 → `InvalidInput`（`field_errors` 指向位置）。

### 3.2 语义驱动（SEMANTIC_DRIVER）与 `LoadedModel`

内核只经驱动读取模型语义（D-015）。驱动声明 `semantic_profiles=[<profile>]` 与 `driver.*` 能力，实现：

```python
class MyDriver:
    descriptor = DESCRIPTOR   # interface="SEMANTIC_DRIVER", interface_version="2"
    def validate(self, package: ModelPackage) -> list[str]: ...      # 空列表 = 有效
    def load(self, package: ModelPackage) -> LoadedModel: ...
```

`LoadedModel` 是**协议**：`action_specs()`、`state_paths()`、`initial_state()`、`belief(observation)`、`candidates(belief, scope=, partial_checker=)`、`predict(state, action) -> Prediction`、`properties(state)`、`property_kinds()`、`display()`。内核、规则与发布只调用这些方法；只有声明 `driver.ir` 的驱动才会被 Z3 查询、IR 规则与成本目标使用，其余能力按声明协商（见第 5 节与 [capability-matrix.md](capability-matrix.md)）。参考：`formal_lab_model/driver.py::IRFiniteDriver`（deterministic_finite_v1）、`examples/warehouse-allocation/.../driver.py::WarehouseDriver`（第二 profile）。

### 3.3 规划器（PLANNER）与 `CheckpointingPlanner`

```python
class MyPlanner:
    descriptor = DESCRIPTOR   # interface="PLANNER"
    def propose(self, context: PlanningContext) -> ActionProposal: ...
    # 可选（CheckpointingPlanner）：
    def checkpoint(self) -> PlannerCheckpoint | None: ...
    def restore(self, checkpoint: PlannerCheckpoint) -> None: ...
    def current_plan(self) -> TaskPlan | None: ...
```

- `PlanningContext`（数据对象）包含观测、动作规格、候选（每个带 `belief_applicability`、原因与可选 `observation_request`）、预算与用量、种子，以及 v2 字段：`turn`、`goal`、`objective`、`actor_budget`/`actor_usage`、`participants`、`observation_request_allowed`、`assumptions`、`last_outcome`（含效果比较）、`replan_requested`。**只能从候选中选择**；环境拒绝非模型声明的动作。
- 返回 `ActionProposal`：`proposal_id = f"{context.step_id}:proposal"`、`source.kind`（RULE / SYMBOLIC / LLM / LLM_STUB / HUMAN / EXTERNAL）、`rationale`、`usage`；可带 `observation_request`（能力 `plan.observation_requests`，环境 `env.observe_on_request` 时内核先补观测再重新询问一次）。
- 实现检查点时，内核在每次提案后保存 `PlannerCheckpoint`，下一步先 `restore` 再 `propose`：暂停、取消后重跑或 Worker 重启都从同一状态继续（D-020）。检查点必须可 JSON 序列化并只含规划器自己的状态。
- 参考：规则 `examples/neutral-scheduling/.../rule_planner.py`、任务计划 `.../task_planner.py`、Z3 `packages/solver-adapters/z3/.../planner.py`、LLM `packages/strategies/.../llm_planner.py`、包外 `examples/external-plugin/.../checklist.py`。

### 3.4 验证器（VERIFIER）

```python
class MyVerifier:
    descriptor = DESCRIPTOR   # interface="VERIFIER"
    def check(self, package, query: CheckQuery, *, state=None, unknown_paths=None) -> BoundedCheckResult: ...
```

结果语义见 [docs/contracts/v2.md](../contracts/v2.md)：`WITNESS / NO_WITNESS_WITHIN_BOUND / UNKNOWN / UNSUPPORTED`，超时与未支持用结论表达而不是异常；见证能被参考解释器重放；每次检查写出 `QueryBundle`（输入、假设、范围、结果、后端）。参考：`formal_lab_solver_z3/verifier.py`、`optimize.py`。

### 3.5 环境（ENVIRONMENT）与 `SessionEnvironment`

```python
class MyEnvironment:
    descriptor = DESCRIPTOR   # interface="ENVIRONMENT"
    def reset(self, scenario, package, *, run_id, seed) -> Observation: ...
    def observe(self, actor_id) -> Observation: ...
    def step(self, proposal, *, operation_id) -> ActionOutcome: ...
    def snapshot(self) -> EnvironmentSnapshot: ...
    def restore(self, snapshot) -> None: ...
    def close(self) -> None: ...
```

两类环境按能力区分，内核据此选择恢复方式（D-018）：

- **纯数据**（`env.pure_replayable`、`env.restore`）：`step` 只依赖快照与提案，恢复时从步前快照精确重放。参考 `packages/neutral-environment/.../ir_world.py`。
- **持久会话**（`env.persistent_session`，实现 `SessionEnvironment`）：状态在外部服务中、从不回滚；`session()` 返回 `EnvironmentSession`（数据对象，含恢复方式与快照种类 `SESSION_MARKER`）；`query_operation(id)` 回答某操作发生了什么（`None` = 服务从未见过）；可选 `observe_paths`、`reset_session`、`export_state`/`import_state`。服务端必须以操作 id 在一个事务内去重（`env.idempotent_step`）。响应丢失时协调器按 id 查询后对账，查询也失败则 `NEEDS_REVIEW`，不猜测。参考 `examples/local-order-service/.../env.py`（D-021）。

在 `outcome.result["properties"]` 报告真值性质供停止条件使用；`Observation` 中不可知的当前值放 `unknowns`（附 `last_known`）。

### 3.6 探针（PROBE）

```python
class MyProbe:
    descriptor = DESCRIPTOR   # interface="PROBE", interface_version="2"
    def definitions(self) -> list[MetricDefinition]: ...
    def sample(self, session: EnvironmentSession, *, step: int | None) -> list[ProbeResult]: ...
```

探针独立于智能体视角读取业务系统，`ProbeResult` 带来源（`EvidenceRef`）与状态（OK / MISSING / ERROR）。报告中探针与环境评分保留各自来源。参考 `examples/local-order-service/.../plugins.py::OrderProbe`。

### 3.7 轮次（TurnScheduler）

轮次由内核实现，场景以 `TurnPolicy` 选择：`ROUND_ROBIN`、`FIXED_TABLE`、`SIMULTANEOUS_SNAPSHOT`（轮初共同观测、随后顺序执行）；观测时机 `TURN_START` / `ROUND_START`；冲突策略 `REVALIDATE` / `REJECT_STALE`。游标（`TurnState`）随运行持久化。参考 `formal_lab_runtime/turns.py`。

### 3.8 评分器（EVALUATOR）与产物存储（ARTIFACT_STORE）

评分器 `metric_definitions()` / `score(episode)`，只由真值与轨迹确定性计算，无法计算时返回 `MISSING` / `NOT_APPLICABLE`；`eval.applies_to` 决定用于哪些模型包。产物存储 `put` / `get` / `describe`，按 sha256 内容寻址（`formal_lab_runtime/artifacts.py`）。

### 3.9 执行阶段记录（内核写入）

每步按 `ExecutionStage`（TURN → OBSERVE → PROPOSE → CHECK → EXECUTE → RECONCILE → PROBE → COMPARE → TERMINATE）写 `StageRecord`：输入 / 输出摘要、重试语义、错误与证据。插件不产生阶段记录；回放与证据页据此定位。

## 4. 验证新插件

1. 合同检查（不需要平台）：

   ```python
   from formal_lab_sdk.plugin_testing import check_planner, check_environment
   report = check_planner(("org.example.my-planner", "0.1.0"), {"...": "..."})
   assert report.ok, report.failures()
   ```

   规划器：注册 → 初始化 → 协商 → 观察与提案 → 状态推进（有检查点时计划版本递增）→ 恢复（中途序列化继续 = 不中断，检查点逐一相同）→ 结束。环境：注册 → 初始化 → 重置与观察 → 步进 → 快照 / 恢复 → 按 id 查询（声明时）→ 关闭。
2. `fal plugins` / `GET /api/v1/plugins` 确认已注册、描述符摘要固定。
3. 平台矩阵（`fal matrix create`）与现有策略配对比较。
4. 影响扩展的选择记入 `docs/execution/decisions.md`。

## 5. 兼容策略

- `formal-lab-contracts/v1` 冻结（摘要不变），读取经 `formal_lab_contracts.compat` 升级；新数据只写 v2。
- 阶段三对 v2 的补充是**增量**的：新对象与带默认值的可选字段，契约版本仍为 `formal-lab-contracts/v2`，摘要随之变化并记入交接；阶段二写出的 v2 回放包必须原样可读（`tests/compat/fixtures/phase2/`，`tests/compat/test_phase2_fixtures.py`）。破坏性变化发布 v3 并提供 v2 读取。
- 插件接口：v1 协议不变；v2 可选方法（检查点、会话方法）按能力声明启用，未声明时内核走原路径。

## 6. 示例对照

| 示例 | 部件 |
|---|---|
| `examples/neutral-scheduling/` | IR 模型、规则 / 任务计划规划器、评分器、四个单参与者与两名调度员场景、回归哨兵 |
| `examples/warehouse-allocation/` | 第二语义 profile：前端、`WarehouseDriver`、规则规划器、评分器、收货员 + 拣货员场景 |
| `examples/local-order-service/` | 持久业务服务、`SessionEnvironment` 适配器、`OrderProbe`、生命周期管理、五种案例 |
| `examples/external-plugin/` | 包外规划器（偏好）与任务计划规划器（检查点），只依赖公开 SDK |
| `packages/solver-adapters/prism-games/` | 可选扩展：随机博弈载荷、进程适配器、独立核对（D-023） |
