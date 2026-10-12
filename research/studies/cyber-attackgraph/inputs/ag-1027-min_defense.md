# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_0:reach, h5_1:obtain, h5_2:reach |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:reach | OR | edge0:reach |
| h1_1:obtain | OR | edge0:reach, edge1:reach |
| h1_2:traverse | OR | edge0:reach, edge1:reach |
| h2_0:obtain | AND | h1_0:reach, h1_2:traverse, h1_1:obtain |
| h2_1:access | AND | edge0:reach, h1_1:obtain, h1_0:reach |
| h2_2:obtain | OR | h1_2:traverse |
| h3_0:reach | AND | h1_2:traverse, h2_1:access, h2_2:obtain |
| h3_1:obtain | AND | h2_0:obtain, h2_2:obtain |
| h3_2:access | OR | h1_0:reach, h2_2:obtain, h1_1:obtain |
| h4_0:pivot | AND | h2_2:obtain, h3_2:access, h2_0:obtain |
| h4_1:access | AND | h2_2:obtain, h3_0:reach |
| h4_2:pivot | OR | h3_1:obtain, h2_1:access, h2_0:obtain |
| h5_0:reach | OR | h3_1:obtain, h3_0:reach, h4_1:access |
| h5_1:obtain | OR | h4_0:pivot |
| h5_2:reach | AND | h3_0:reach, h4_2:pivot, h4_1:access |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
