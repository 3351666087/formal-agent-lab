# 插件接入指南

扩展能力一律以**插件**接入：实现一个稳定接口（`formal_lab_contracts.interfaces`），用 `PluginDescriptor` 声明版本、能力、语义 profile、配置 schema 与界面元数据，并通过 entry point 注册。核心包（contracts / model-core / runtime / platform-api / orchestrator / sdk）从不 import 插件，只经注册表创建实例（由 `tests/architecture/test_boundaries.py` 检查）。

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
    return MyPlanner(services.pinned_model(), config)

def registrations() -> list[PluginRegistration]:
    return [PluginRegistration(DESCRIPTOR, create)]
```

- 注册表（`formal_lab_runtime.registry.PluginRegistry`）在 API 与 Worker 启动时发现 entry point，校验 `contract_version` 与 `interface_version`（当前 `"1"`），记录描述符摘要，并同步到 `plugin_catalog` 表与 `GET /api/v1/plugins`。加载失败的插件记入 `plugin_load_errors`，不影响平台启动。
- 运行创建时 `RunManifest.plugins` 固定每个角色（environment / strategy:<actor> / verifier / evaluator:<i>）的插件 id、版本、接口版本与描述符摘要；之后安装新版本不影响已创建的实验。
- `services`（`PluginServices`）提供 `pinned_model()`、`get_model(ref)`、`get_setting(key)`；密钥只从设置读取，永不出现在契约对象中。
- 能力协商：`registry.negotiate(ref, [CapabilityRequirement(...)])`；平台据此判断兼容性（例如策略/场景兼容检查、评分器 `eval.applies_to`）。
- 界面：`PluginDescriptor.ui` 的 `label/description/category/state_labels/action_labels/action_display/metric_labels/value_labels` 决定 Web 中的显示；配置表单由 `config_schema` 渲染。核心 UI 不写任何领域代码。

完整的包外示例：[`examples/external-plugin`](../../examples/external-plugin)（只依赖 `formal-lab-sdk`，集成测试 `test_external_plugin_registered_through_public_interfaces` 用它完成实验，提案来源为 `EXTERNAL`）。

## 2. 各类扩展

### 2.1 模型前端（MODEL_FRONTEND）

把某种源格式编译为 `ModelPackage`（中性 IR + 摘要 + 来源）。

```python
class MyFrontend:
    descriptor = DESCRIPTOR   # interface="MODEL_FRONTEND"
    def compile(self, source: ModelSource, *, package_id: str, version: int) -> ModelPackage:
        ir = translate(source.text)                                   # → formal_lab_contracts.ModelIR
        return formal_lab_model.build_package(ir, package_id=package_id, version=version, source=source)
```

- 格式不支持 → 抛 `Unsupported`；源有错误 → 抛 `InvalidInput`（`field_errors` 指向位置）。`build_package` 负责类型检查、规范化与摘要。
- 参考实现：`packages/model-core/src/formal_lab_model/frontend.py`（`fal-ir-json/v1`）。

### 2.2 语义 profile

`deterministic_finite_v1` 之外的语义（概率、并发、稠密时间、无界整数、模型内部分观测）以**新 profile** 引入：

1. 选定 profile 名（如 `probabilistic_finite_v1`），在 `ModelIR.semantic_profile`/`features` 中使用；
2. 提供能处理它的前端、验证器与环境插件，各自在 `semantic_profiles` 与 `capabilities`（`profile.<name>`、`query.*`）中声明；
3. 现有引擎对未知 profile/feature 已返回 `UNSUPPORTED`（附 `extension_point`），因此新 profile 不会被旧引擎误判；
4. 在 `formal_lab_model/capability_matrix.py` 中增加行，重新生成 `docs/architecture/capability-matrix.md`。

### 2.3 规划器 / 策略（PLANNER）

```python
class MyPlanner:
    descriptor = DESCRIPTOR   # interface="PLANNER"
    def propose(self, context: PlanningContext) -> ActionProposal: ...
```

- 输入只有契约对象：`Observation`（事实 + 未知项）、`ActionSpec[]`、`CandidateAction[]`（每个候选带 `belief_applicability`）、预算与用量、种子。**只能从候选中选择**；环境拒绝非模型声明的动作。
- 返回 `ActionProposal`：`proposal_id = f"{context.step_id}:proposal"`（确定性 id，重试幂等）、`source.kind`（RULE / SYMBOLIC / LLM / LLM_STUB / HUMAN / EXTERNAL）、`rationale`、`usage`（模型调用与 tokens，平台据此计预算）。
- 若调用模型，把调用记录放在实例属性 `last_calls`（`ModelResponse` 列表），平台会存为 `model_call` 产物并在事件中引用；该步的提案先持久化再施加效果，重试不会重复调用模型。
- 参考：规则 `examples/neutral-scheduling/.../rule_planner.py`、Z3 `packages/solver-adapters/z3/.../planner.py`、LLM `packages/strategies/.../llm_planner.py`。

### 2.4 验证器（VERIFIER）

```python
class MyVerifier:
    descriptor = DESCRIPTOR   # interface="VERIFIER"
    def check(self, package, query: CheckQuery, *, state=None, unknown_paths=None) -> BoundedCheckResult: ...
```

必须遵守 `docs/contracts/v1.md` 的结果语义：`WITNESS / NO_WITNESS_WITHIN_BOUND / UNKNOWN / UNSUPPORTED` 与 `APPLICABLE / INAPPLICABLE / UNKNOWN / UNSUPPORTED`；超时与未支持用结论表达而不是异常；`scope = MODEL_INTERNAL`；见证应能被参考解释器重放（`Interpreter.replay`）。参考：`formal_lab_solver_z3/verifier.py`；运行中通过 manifest 的 `verifier` 角色选择。

### 2.5 环境（ENVIRONMENT）

```python
class MyEnvironment:
    descriptor = DESCRIPTOR   # interface="ENVIRONMENT"
    def reset(self, scenario, package, *, run_id, seed) -> Observation: ...
    def observe(self, actor_id) -> Observation: ...
    def step(self, proposal, *, operation_id) -> ActionOutcome: ...
    def snapshot(self) -> EnvironmentSnapshot: ...
    def restore(self, snapshot) -> None: ...
    def close(self) -> None: ...
    # 可选（平台存在时使用）：truth_state() / truth_properties() → 评分器与停止条件
```

- **纯数据与可重放**：每步都从快照 `restore` 后执行，`step` 必须只依赖快照与提案；同一 `operation_id` 重复投递返回同一结果（幂等）。
- 真值状态只经快照与评分器离开环境；`Observation` 中不可知的当前值放在 `unknowns`（附 `last_known`）。
- 在 `outcome.result["properties"]` 报告真值上的性质取值，供 `GOAL_REACHED / INVARIANT_VIOLATED` 停止条件使用。
- 参考：`packages/neutral-environment/.../ir_world.py`（延迟观测、真值覆盖、按种子扰动）。

### 2.6 评分器（EVALUATOR）

```python
class MyEvaluator:
    descriptor = DESCRIPTOR   # interface="EVALUATOR", capabilities 含 {"id": "eval.applies_to", "params": {"package_ids": [...]}}
    def metric_definitions(self) -> list[MetricDefinition]: ...
    def score(self, episode: EpisodeRecord) -> list[MetricResult]: ...
```

- 指标只由模拟器真值与轨迹确定性计算；无法计算时返回 `MISSING` / `NOT_APPLICABLE`（不要返回 0）。
- `eval.applies_to` 决定评分器自动用于哪些模型包（`{"all": true}` 表示通用）。参考：`formal_lab_eval/generic.py` 与 `examples/neutral-scheduling/.../scorer.py`。

### 2.7 产物存储（ARTIFACT_STORE）

`put(data, *, name, media_type, format_version) -> ArtifactRef` / `get(ref) -> bytes`，按 sha256 内容寻址并在读取时校验摘要。参考：`formal_lab_runtime/artifacts.py`（本地、S3 兼容）。

## 3. 生产调度示例如何接入（完整走查）

| 部件 | 文件 | 接入方式 |
|---|---|---|
| 模型 | `examples/neutral-scheduling/src/formal_lab_example_scheduling/model.py` | 纯 IR（实体、常量、状态、动作、性质），由通用前端打包 |
| 场景 | `.../scenarios.py` | 四个 `ScenarioManifest`，只通过 IR 世界环境的配置（初值覆盖、按种子扰动、观测延迟、真值常量覆盖）区分 |
| 规则策略 | `.../rule_planner.py` | PLANNER 插件 `formal-lab.example.scheduling.edd-dispatch` |
| 评分器 | `.../scorer.py` | EVALUATOR 插件，`eval.applies_to` = `neutral-scheduling` |
| 注册 | `examples/neutral-scheduling/pyproject.toml` | entry point `neutral-scheduling = formal_lab_example_scheduling:registrations` |
| Inspect 任务 | `.../inspect_task.py` | 通用 `formal_lab_eval.inspect_adapter.platform_task` |
| 回归哨兵 | `python -m formal_lab_example_scheduling …`，`examples/neutral-scheduling/tests/test_sentinel.py` | 无服务独立运行 |

## 4. 验证新插件

1. `tests/contracts/` 的样例与测试可直接复用来检查插件产出的契约对象；
2. `fal plugins` / `GET /api/v1/plugins` 确认已注册且描述符摘要固定；
3. 用 `python -m formal_lab_example_scheduling compare --strategies ...` 或平台矩阵与现有策略对比；
4. 在 `docs/execution/decisions.md` 记录影响扩展的选择。
