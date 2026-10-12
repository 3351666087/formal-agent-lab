# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_1:reach, h5_0:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:traverse | AND | edge0:reach, edge1:reach |
| h1_1:reach | AND | edge0:reach, edge1:reach |
| h1_2:reach | OR | edge1:reach, edge0:reach |
| h2_0:escalate | OR | edge1:reach |
| h2_1:access | AND | h1_1:reach, edge0:reach |
| h2_2:traverse | AND | h1_0:traverse, edge0:reach, h1_1:reach |
| h3_0:reach | OR | h2_2:traverse, h1_2:reach, h2_0:escalate |
| h3_1:obtain | OR | h2_0:escalate, h1_2:reach, h1_1:reach |
| h3_2:pivot | OR | h1_0:traverse |
| h4_0:traverse | OR | h2_0:escalate, h2_1:access |
| h4_1:access | OR | h3_0:reach, h2_0:escalate |
| h4_2:reach | OR | h2_2:traverse |
| h5_0:pivot | AND | h3_1:obtain, h4_2:reach |
| h5_1:reach | OR | h3_2:pivot |
| h5_2:pivot | AND | h3_1:obtain, h4_0:traverse, h3_2:pivot |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
