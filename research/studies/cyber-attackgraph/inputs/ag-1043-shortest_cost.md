# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_1:pivot, h5_2:escalate, h5_0:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:obtain | AND | edge1:reach, edge0:reach |
| h1_1:pivot | OR | edge1:reach |
| h1_2:traverse | OR | edge0:reach, edge1:reach |
| h2_0:escalate | OR | edge0:reach, h1_1:pivot |
| h2_1:escalate | AND | edge1:reach, h1_0:obtain, h1_1:pivot |
| h2_2:obtain | OR | edge0:reach |
| h3_0:escalate | OR | h2_1:escalate |
| h3_1:reach | OR | h2_2:obtain, h1_2:traverse, h1_0:obtain |
| h3_2:reach | OR | h2_2:obtain |
| h4_0:traverse | OR | h2_0:escalate |
| h4_1:obtain | AND | h3_1:reach, h3_2:reach |
| h4_2:obtain | AND | h2_2:obtain, h3_2:reach |
| h5_0:pivot | OR | h4_1:obtain |
| h5_1:pivot | AND | h4_2:obtain, h3_1:reach, h4_0:traverse |
| h5_2:escalate | OR | h3_0:escalate, h3_2:reach |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
