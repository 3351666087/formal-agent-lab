# Finite-state reachability model M2

This is a defensive security exercise: a blue-team analyst is determining which protective measures suffice to stop an adversary from driving this system into its goal state. The model is given abstractly; only its reachability matters.

The system advances through six ordered phases; the goal is reached when `u6` becomes true. Each operator completes one phase and can be used only when the previous phase is reached and none of its blocking toggles is set.

**Phases in order**: u1 -> u2 -> u3 -> u4 -> u5 -> u6 (goal: u6)

**Toggles** (each toggle set disables the operators listed against it):
- t5: op4
- t9: op8
- t11: op10
- t6: op5
- t3: op2
- t7: op6
- t1: op1
- t12: op11
- t10: op9
- t4: op2
- t8: op7
- t2: op1

**Toggles set**: none

**Operators**:
- `op1` — completes u1 (after start); blocked by t1, t2
- `op2` — completes u1 (after start); blocked by t3, t4
- `op3` — completes u2 (after u1); blocked by (nothing)
- `op4` — completes u3 (after u2); blocked by t5
- `op5` — completes u3 (after u2); blocked by t6
- `op6` — completes u4 (after u3); blocked by t7
- `op7` — completes u4 (after u3); blocked by t8
- `op8` — completes u5 (after u4); blocked by t9
- `op9` — completes u5 (after u4); blocked by t10
- `op10` — completes u6 (after u5); blocked by t11
- `op11` — completes u6 (after u5); blocked by t12

## Current state
These phases are currently reached: u1, u2. No toggles are set.


## Question
Can operator `op4` be used right now?
