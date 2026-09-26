# 能力矩阵：deterministic_finite_v1

由 `python -m formal_lab_model.capability_matrix` 从 formal_lab_model/capability_matrix.py 生成，勿手工编辑。
状态含义：SUPPORTED = 已实现且有测试；PARTIAL = 在所述范围内实现；UNSUPPORTED = 引擎显式返回 UNSUPPORTED。

| feature | interpreter | z3_compiler | ir_world_env | z3_planner | unsupported answer | extension point |
|---|---|---|---|---|---|---|
| finite_entities — finite entity sets and enums as index domains | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED |  |  |
| bool_enum_bounded_int — bool, enum/entity symbols, bounded integers | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED |  |  |
| pure_expression_ast — pure expression AST incl. ∀/∃/count/sum over finite domains | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED |  |  |
| discrete_logical_steps — one grounded action per logical step, explicit order | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED |  |  |
| deterministic_effects — assign / when / forall effects, later write wins, domain guard | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED |  |  |
| partial_observation — observations with delayed/unknown facts (environment layer, not model semantics) | PARTIAL | PARTIAL | SUPPORTED | PARTIAL | precondition checks over unknown facts answer UNKNOWN when completions disagree | Environment.observe + Verifier state/unknown_paths arguments |
| dense_time — real-valued clocks / continuous time | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | new semantic profile + ModelFrontend/Verifier plugins |
| concurrent_actions — several actions in one logical step | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | new semantic profile (e.g. concurrent_finite_v1) |
| probabilistic_effects — stochastic transitions / probabilities | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | new semantic profile + probabilistic Verifier plugin |
| unbounded_integers — integer state without declared bounds | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | new semantic profile |

