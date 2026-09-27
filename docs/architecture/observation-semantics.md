# 真值状态、观测与“未知”：实验语义

本平台区分两个对象，二者在契约、存储与界面中都分开表示：

| 对象 | 谁持有 | 谁能看到 | 契约 |
|---|---|---|---|
| **真值状态**（truth state） | 环境插件（`formal-lab.env.ir-world`）内部 | 平台用于评分、快照与证据回放；**参与者/策略永远拿不到** | `EnvironmentSnapshot.data`（仅快照/证据）、`EpisodeRecord.final_truth_state`（仅评分器） |
| **观测**（observation） | 每个逻辑步由环境为某个参与者生成 | 策略、界面“观测”面板 | `Observation`：`facts[]` + `unknowns[]` |

## 观测的组成

- `Fact{path, value, observed_at_step, source}`：参与者知道的值。`observed_at_step < step` 表示**过期事实**（来自更早的步骤，界面标为“过期”）。
- `UnknownItem{path, reason, last_known}`：参与者在当前步**无法知道当前值**的位置：
  - `OBSERVATION_DELAY`：场景配置 `observation.delay_steps` 使该变量延迟 k 步到达；`last_known` 给出上次已知值及其时间；
  - `NOT_OBSERVABLE`：模型标注 `observable: false` 或场景 `observation.hidden`；
  - `NOT_YET_OBSERVED`：保留给后续环境。

“未知”是**实验语义**：它描述参与者的信息状态，而不是模型的不确定性。模型本身（deterministic_finite_v1）是确定且全可观测的；部分观测由环境层产生（见 [capability-matrix.md](capability-matrix.md) 的 `partial_observation` 行）。

## 未知如何影响检查与比较

- **信念状态**：`formal_lab_model.belief.belief_from_observation` 用最新事实与上次已知值构造完整状态，并列出 `unknown_paths`。
- **单步前提检查**（`ACTION_PRECONDITION`，`SINGLE_STEP`）：未知位置作为自由变量。所有补全都适用 → `APPLICABLE`；都不适用 → `INAPPLICABLE`；取决于未知值 → `UNKNOWN`（证据不足保持未知，不做猜测）。候选动作的 `belief_applicability` 与每步的前提检查都遵循这一规则。
- **效果比较**（`compare_effects`）：预测来自运行固定的信念模型；某字段只有在当前步被**新鲜观测**时才判为 `MATCH/DIFFERENT`，否则为 `UNKNOWN`；整体结论：有差异 → `DIFFERENT`，否则有未知 → `INSUFFICIENT_INFORMATION`，否则 `MATCH`。
- **有界检查**（目标可达 / 不变量反例）：结论是**模型内**且**有界**的（`scope=MODEL_INTERNAL`，`NO_WITNESS_WITHIN_BOUND` 永远带 `bound`）。

## 演示：状态延迟场景

`examples/neutral-scheduling` 的“状态延迟”场景把 `phase / on / remaining / finish` 延迟 2 步。运行台中：

1. 观测面板把这些位置显示为“未知 · 上次 … 截至步 n”；
2. 许多 `assign` 候选的适用性为 `UNKNOWN`，规则策略按声明的探测规则尝试，环境裁决（拒绝不适用的动作）；
3. 效果比较常为“信息不足”，因为结果字段要 2 步后才可观测；
4. 证据与回放页并列展示真值快照（标注“参与者不可见”）与当时的观测。

## 界面图例

| 标签 | 含义 |
|---|---|
| 已观测 | 当前步直接观测的事实 |
| 过期 | 来自更早步骤的事实 |
| 未知 | 当前值不可知（附上次已知值） |
| 预测 | 信念模型对动作效果的预期 |
| 有界结论 | 只在给定步数边界内成立的检查结论 |
| 模型内结论 | 结论关于模型，不关于真实系统 |

## 阶段二：来源、假设与稳健性（formal-lab-contracts/v2）

### 每个位置的来源（`BeliefState.provenance`）

| 来源 | 含义 | 用于规划的值 | 补全检查中 |
|---|---|---|---|
| `KNOWN` | 本步新鲜观测 | 观测值 | 固定 |
| `STALE` | 过期事实，或未知项附带的上次已知值 | 上次已知值 | 未知项的位置为自由变量；过期事实固定 |
| `UNKNOWN` | 报告为未知且无任何值 | 模型初值（占位） | 自由变量 |
| `ASSUMED_INITIAL` | 观测从未提及 | 模型初值（假设） | 固定 |

`BeliefState.free_paths` 就是补全检查取遍的位置（观测的未知项，与阶段一语义一致）。除 `KNOWN` 外的每个位置都列入 `AssumptionSet`（值、时点与原因），并以其摘要标识。

### 基于假设的计划与稳健结论

- 用过期值或初值做出的规划标为 `ASSUMPTION_BASED`，提案携带 `AssumptionSetRef`（摘要、计数、依据）。全部位置新鲜观测时为 `FULLY_OBSERVED`，对全部补全检查过的为 `ROBUST`。
- **单步**：`ACTION_PRECONDITION` 判断“所有允许补全均满足前提”。结论为 `UNKNOWN` 时，同时给出一个适用补全与一个不适用补全，以及 `ObservationRequest`：前提读取的、且在两者间取值不同的未知位置。
- **多步**：`ROBUST_SEQUENCE` 检查给定的**固定动作序列**是否对每个补全都能逐步执行（可选：最终到达目标）。不成立时返回反例补全与首个失败动作，反例由参考解释器独立重放确认。
- **与策略综合的区别**：稳健序列是开环的，序列事先固定，不随后续观测分支。“能根据观测结果选择下一步”的条件策略综合不在本平台能力内，未实现的能力回答 `UNSUPPORTED`。

### 额外观测

策略可在提案中附上 `observation_request`（例如 Z3 规划器的 `request_observations`：下一动作在信念上为 `UNKNOWN` 时）。规则也可以产生 `OBSERVE_MORE`。环境声明 `env.observe_on_request` 时，平台在同一回合内取回这些位置的新鲜值（事件 `OBSERVATION_REQUESTED`），并让策略基于新信念再提案一次。每回合最多一次，否则按原提案执行。

### 效果证据等级（`FieldDiff.evidence`）

`observed`（本步新鲜观测）、`verified-within-scope`（未在参与者视图中，但由独立来源在声明范围内确认，例如业务服务的操作查询结果）、`predicted`（只有模型预测）、`unknown`（不可比较）。另附 `freshness`（FRESH / STALE / MISSING）与观测时点。
