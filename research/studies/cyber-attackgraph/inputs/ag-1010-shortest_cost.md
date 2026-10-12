# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_2:reach, h4_0:obtain, h4_3:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:traverse | OR | edge0:reach, edge2:reach, edge1:reach |
| h1_1:pivot | OR | edge1:reach |
| h1_2:traverse | OR | edge0:reach |
| h1_3:traverse | OR | edge2:reach, edge1:reach, edge0:reach |
| h2_0:pivot | OR | h1_0:traverse, h1_1:pivot |
| h2_1:escalate | OR | edge0:reach, h1_3:traverse, h1_1:pivot |
| h2_2:traverse | OR | h1_2:traverse, h1_3:traverse |
| h2_3:pivot | AND | edge1:reach, h1_2:traverse, edge0:reach |
| h3_0:access | OR | h1_0:traverse |
| h3_1:traverse | AND | h1_0:traverse, h2_3:pivot, h2_0:pivot |
| h3_2:obtain | AND | h1_0:traverse, h1_2:traverse, h1_1:pivot |
| h3_3:reach | OR | h2_0:pivot |
| h4_0:obtain | OR | h2_3:pivot, h3_2:obtain |
| h4_1:pivot | OR | h2_2:traverse, h3_3:reach |
| h4_2:reach | AND | h3_3:reach, h2_3:pivot, h3_2:obtain |
| h4_3:pivot | OR | h2_3:pivot |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
