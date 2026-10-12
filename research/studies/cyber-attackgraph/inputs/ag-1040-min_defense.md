# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_1:traverse, h3_2:obtain, h3_0:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:escalate | OR | edge0:reach |
| h1_1:traverse | OR | edge1:reach, edge0:reach |
| h1_2:obtain | OR | edge1:reach, edge0:reach |
| h2_0:traverse | OR | edge1:reach, h1_2:obtain |
| h2_1:obtain | OR | h1_0:escalate, edge0:reach |
| h2_2:access | OR | h1_1:traverse, h1_2:obtain |
| h3_0:obtain | OR | h1_2:obtain |
| h3_1:traverse | OR | h2_2:access, h1_2:obtain, h2_0:traverse |
| h3_2:obtain | AND | h1_2:obtain, h2_1:obtain, h2_2:access |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
