# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_2:escalate, h4_1:escalate, h4_0:access |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:pivot | OR | edge1:reach |
| h1_1:reach | OR | edge1:reach, edge0:reach |
| h1_2:pivot | OR | edge1:reach |
| h2_0:reach | OR | edge1:reach |
| h2_1:pivot | OR | edge0:reach, h1_1:reach, h1_2:pivot |
| h2_2:reach | OR | h1_0:pivot, h1_1:reach, edge0:reach |
| h3_0:pivot | OR | h1_2:pivot, h1_1:reach, h2_1:pivot |
| h3_1:access | OR | h2_0:reach |
| h3_2:reach | OR | h2_0:reach |
| h4_0:access | AND | h2_2:reach, h3_2:reach |
| h4_1:escalate | OR | h2_2:reach, h2_0:reach |
| h4_2:escalate | AND | h2_1:pivot, h3_2:reach |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
