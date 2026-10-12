# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_3:access, h4_1:escalate |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:pivot | AND | edge2:reach, edge1:reach |
| h1_1:access | AND | edge2:reach, edge0:reach, edge1:reach |
| h1_2:reach | OR | edge1:reach, edge2:reach |
| h1_3:access | OR | edge0:reach, edge2:reach |
| h2_0:traverse | OR | edge0:reach, edge1:reach |
| h2_1:pivot | OR | edge2:reach |
| h2_2:escalate | OR | h1_2:reach, edge1:reach, h1_0:pivot |
| h2_3:access | AND | h1_0:pivot, h1_1:access, edge0:reach |
| h3_0:reach | OR | h1_2:reach |
| h3_1:pivot | OR | h1_1:access, h1_0:pivot |
| h3_2:traverse | OR | h2_1:pivot, h2_0:traverse, h2_3:access |
| h3_3:traverse | AND | h2_1:pivot, h1_2:reach, h2_2:escalate |
| h4_0:pivot | OR | h2_2:escalate, h3_0:reach |
| h4_1:escalate | OR | h2_3:access, h2_0:traverse, h2_1:pivot |
| h4_2:access | OR | h2_1:pivot |
| h4_3:access | OR | h2_0:traverse |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
