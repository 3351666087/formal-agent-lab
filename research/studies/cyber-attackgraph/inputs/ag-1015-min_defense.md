# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_0:pivot, h5_1:pivot, h5_2:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:reach | AND | edge1:reach, edge0:reach |
| h1_1:obtain | OR | edge1:reach, edge0:reach |
| h1_2:obtain | OR | edge0:reach |
| h2_0:access | OR | h1_1:obtain, h1_0:reach |
| h2_1:traverse | OR | edge1:reach |
| h2_2:escalate | OR | edge1:reach |
| h3_0:obtain | AND | h2_1:traverse, h1_0:reach |
| h3_1:access | OR | h2_1:traverse, h2_0:access |
| h3_2:obtain | AND | h1_2:obtain, h2_1:traverse |
| h4_0:pivot | OR | h2_0:access |
| h4_1:pivot | OR | h3_1:access, h2_0:access, h3_0:obtain |
| h4_2:reach | OR | h2_1:traverse |
| h5_0:pivot | OR | h4_0:pivot |
| h5_1:pivot | OR | h4_0:pivot |
| h5_2:pivot | OR | h4_0:pivot, h4_2:reach |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
