# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_0:pivot, h5_2:traverse, h5_1:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:escalate | AND | edge0:reach, edge1:reach |
| h1_1:access | AND | edge1:reach, edge0:reach |
| h1_2:access | OR | edge1:reach, edge0:reach |
| h2_0:reach | OR | edge1:reach, edge0:reach |
| h2_1:obtain | OR | h1_1:access, edge0:reach |
| h2_2:pivot | OR | edge0:reach, h1_0:escalate, h1_1:access |
| h3_0:traverse | AND | h1_0:escalate, h1_2:access, h2_0:reach |
| h3_1:access | OR | h2_0:reach |
| h3_2:traverse | AND | h1_0:escalate, h1_1:access, h2_0:reach |
| h4_0:escalate | OR | h2_0:reach |
| h4_1:obtain | AND | h3_0:traverse, h3_2:traverse, h2_0:reach |
| h4_2:escalate | OR | h2_1:obtain |
| h5_0:pivot | AND | h3_1:access, h3_0:traverse |
| h5_1:obtain | AND | h4_1:obtain, h3_1:access |
| h5_2:traverse | OR | h3_2:traverse |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
