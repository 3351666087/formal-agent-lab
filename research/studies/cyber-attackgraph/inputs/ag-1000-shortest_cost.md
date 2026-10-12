# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_0:traverse, h3_1:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:access | OR | edge0:reach, edge1:reach |
| h1_1:access | OR | edge1:reach |
| h1_2:pivot | OR | edge0:reach |
| h2_0:escalate | OR | h1_1:access, edge1:reach, h1_0:access |
| h2_1:pivot | OR | edge1:reach, edge0:reach |
| h2_2:traverse | OR | edge1:reach, h1_1:access |
| h3_0:traverse | AND | h2_2:traverse, h1_1:access |
| h3_1:obtain | OR | h2_2:traverse, h1_1:access |
| h3_2:pivot | AND | h2_2:traverse, h1_0:access, h1_2:pivot |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
