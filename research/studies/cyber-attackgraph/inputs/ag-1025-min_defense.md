# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_0:escalate, h4_2:pivot, h4_1:reach |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:pivot | OR | edge0:reach |
| h1_1:pivot | OR | edge0:reach, edge1:reach |
| h1_2:escalate | OR | edge1:reach, edge0:reach |
| h2_0:traverse | OR | edge0:reach |
| h2_1:escalate | AND | edge1:reach, h1_0:pivot, h1_1:pivot |
| h2_2:obtain | OR | h1_2:escalate |
| h3_0:escalate | OR | h1_0:pivot |
| h3_1:escalate | OR | h2_2:obtain |
| h3_2:escalate | OR | h2_0:traverse, h1_2:escalate, h1_1:pivot |
| h4_0:escalate | OR | h3_2:escalate, h2_0:traverse, h2_1:escalate |
| h4_1:reach | AND | h2_2:obtain, h2_0:traverse |
| h4_2:pivot | OR | h2_2:obtain, h3_2:escalate, h3_1:escalate |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
