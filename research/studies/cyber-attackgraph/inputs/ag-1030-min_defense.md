# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_2:reach, h4_3:reach, h4_1:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:reach | OR | edge2:reach, edge0:reach |
| h1_1:pivot | OR | edge2:reach, edge1:reach |
| h1_2:access | OR | edge0:reach, edge2:reach, edge1:reach |
| h1_3:pivot | OR | edge0:reach |
| h2_0:escalate | AND | h1_0:reach, h1_2:access |
| h2_1:reach | AND | edge2:reach, h1_0:reach, edge1:reach |
| h2_2:pivot | OR | h1_0:reach |
| h2_3:escalate | OR | h1_0:reach, h1_3:pivot, edge2:reach |
| h3_0:traverse | OR | h1_2:access |
| h3_1:access | OR | h2_1:reach |
| h3_2:reach | OR | h2_3:escalate, h1_1:pivot, h1_0:reach |
| h3_3:reach | OR | h2_0:escalate, h2_1:reach |
| h4_0:escalate | OR | h3_3:reach, h2_1:reach |
| h4_1:obtain | OR | h3_3:reach |
| h4_2:reach | AND | h2_3:escalate, h3_2:reach, h2_0:escalate |
| h4_3:reach | OR | h3_1:access, h3_2:reach |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
