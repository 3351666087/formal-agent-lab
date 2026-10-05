# 概率扩展：PRISM-games（深化轨道）

由 `scripts/prism_games_check.py` 于 2026-10-05T02:33:04Z 生成，勿手工编辑。决策 D-023；安装见 [local-development.md](../local-development.md) 第 9 节。确定性 profile `deterministic_finite_v1` 本身仍不支持随机转移（[能力矩阵](capability-matrix.md) 的 probabilistic_effects 行）；本扩展以独立的类型化载荷与 profile `prism_smg_turn_based_v1` 表达随机博弈。

- 后端：prism-games 3.2.4（aarch64，openjdk version "21.0.12.1" 2026-08-18 LTS），许可 GPL-2.0，不随平台分发；固定发行 https://github.com/prismmodelchecker/prism-games/releases/tag/v3.2.4
- 载荷 `org.formal-lab.prism-games/allocation-game@1` → 结果 `org.formal-lab.prism-games/result@1`

## 假设

- finite state space: jobs ≤ 3, machines ≤ 3, rounds ≤ 8
- turn-based: in every state exactly one player chooses (dispatcher, then environment, then the stochastic work step)
- fully observed: both players see finished jobs, the round and the current assignment
- stochastic transitions only in the work step, with the explicit per-machine success probabilities
- the environment is adversarial for robust queries (<<dispatcher>>) and cooperative for <<dispatcher,environment>>

## 能力与核对

| 能力 | 查询 | 状态 | 核对方式 |
|---|---|---|---|
| turn-based SMG reachability | `<<C>> Pmax=? [ F "done" ]` | SUPPORTED | value equals independent backward induction within 1e-6; state count equals the reference graph |
| strategy export and in-model verification | `-exportstrat (actions)` | SUPPORTED | exported dispatcher strategy achieves the reported value against the worst-case environment |
| cooperative coalition | `<<dispatcher,environment>> Pmax=? [ F "done" ]` | SUPPORTED | value equals the cooperative backward induction |
| rewards, bounded / multi-objective, concurrent games (CSG) | `R{..}, F<=k, multi(...)` | UNSUPPORTED | PRISM-games supports them; this adapter does not generate or verify them |
| partial observation | `—` | UNSUPPORTED | the allocation game is fully observed by construction |

## 实测规模与误差

| 博弈 | 状态 / 选择 / 转移 | 参照状态数 | 鲁棒值（PRISM / 参照） | 合作值 | 导出策略的值 | 耗时 s | 核对 |
|---|---|---|---|---|---|---|---|
| two-jobs-two-machines | 91 / 136 / 212 | 91 | 0.748683 / 0.748683 | 0.985203 | 0.748683 | 2.37 | 通过 |
| three-jobs-three-machines | 1101 / 1880 / 3869 | 1101 | 0.733502 / 0.733502 | 0.997564 | 0.733502 | 2.378 | 通过 |

误差：判定容差 1e-6（PRISM 值迭代的默认终止容差）；实测 PRISM 数值与独立求解器（逐轮倒推）的最大差 1.1e-16（博弈无环）。原始模型、性质、日志、导出策略与显式模型：`docs/execution/evidence/phase4/regression/phase2/prism-games/`。
