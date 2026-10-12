# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_1:escalate, h3_2:reach |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:obtain | OR | edge1:reach, edge0:reach |
| h1_1:reach | OR | edge0:reach |
| h1_2:traverse | OR | edge0:reach, edge1:reach |
| h2_0:obtain | OR | h1_0:obtain, edge1:reach |
| h2_1:obtain | OR | edge1:reach |
| h2_2:pivot | AND | edge0:reach, edge1:reach, h1_1:reach |
| h3_0:reach | OR | h1_1:reach |
| h3_1:escalate | OR | h1_1:reach |
| h3_2:reach | AND | h2_2:pivot, h2_0:obtain |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
