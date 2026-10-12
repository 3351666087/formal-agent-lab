# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_1:access, h5_0:reach, h5_2:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:reach | OR | edge0:reach, edge1:reach |
| h1_1:pivot | OR | edge0:reach |
| h1_2:traverse | OR | edge0:reach |
| h2_0:access | OR | h1_0:reach, edge0:reach, h1_1:pivot |
| h2_1:pivot | OR | edge0:reach |
| h2_2:reach | OR | edge0:reach, h1_0:reach, h1_1:pivot |
| h3_0:escalate | AND | h1_1:pivot, h1_0:reach |
| h3_1:escalate | OR | h1_1:pivot |
| h3_2:reach | OR | h2_1:pivot |
| h4_0:access | OR | h3_0:escalate |
| h4_1:access | OR | h3_0:escalate, h2_2:reach |
| h4_2:access | OR | h3_0:escalate, h2_1:pivot |
| h5_0:reach | OR | h4_0:access, h4_2:access, h3_1:escalate |
| h5_1:access | OR | h3_0:escalate |
| h5_2:pivot | OR | h3_2:reach |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
