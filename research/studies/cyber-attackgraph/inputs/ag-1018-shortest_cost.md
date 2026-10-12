# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_0:access, h4_2:reach, h4_3:access |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:access | OR | edge1:reach, edge0:reach, edge2:reach |
| h1_1:escalate | OR | edge2:reach |
| h1_2:pivot | OR | edge2:reach, edge1:reach, edge0:reach |
| h1_3:reach | AND | edge2:reach, edge1:reach, edge0:reach |
| h2_0:access | OR | h1_1:escalate |
| h2_1:access | OR | h1_1:escalate |
| h2_2:obtain | AND | edge2:reach, edge0:reach |
| h2_3:escalate | AND | edge2:reach, h1_0:access, h1_2:pivot |
| h3_0:escalate | OR | h1_0:access |
| h3_1:escalate | OR | h1_2:pivot |
| h3_2:pivot | AND | h2_2:obtain, h2_1:access, h1_1:escalate |
| h3_3:obtain | OR | h1_2:pivot |
| h4_0:access | OR | h2_0:access |
| h4_1:pivot | OR | h2_3:escalate, h2_1:access |
| h4_2:reach | OR | h2_3:escalate, h3_2:pivot, h3_1:escalate |
| h4_3:access | OR | h2_0:access |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
