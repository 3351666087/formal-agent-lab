# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_0:escalate, h3_2:pivot, h3_1:escalate |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:escalate | OR | edge1:reach, edge0:reach |
| h1_1:pivot | OR | edge0:reach, edge1:reach |
| h1_2:reach | OR | edge1:reach, edge0:reach |
| h2_0:obtain | OR | edge1:reach, edge0:reach |
| h2_1:escalate | OR | h1_0:escalate, h1_2:reach |
| h2_2:escalate | OR | h1_0:escalate, edge1:reach |
| h3_0:escalate | AND | h1_0:escalate, h2_0:obtain, h1_1:pivot |
| h3_1:escalate | OR | h1_2:reach, h2_2:escalate, h2_1:escalate |
| h3_2:pivot | OR | h1_2:reach, h2_2:escalate |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
