# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_1:reach, h4_0:escalate, h4_2:reach |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:traverse | OR | edge1:reach |
| h1_1:access | OR | edge0:reach |
| h1_2:traverse | OR | edge0:reach, edge1:reach |
| h2_0:access | OR | edge1:reach |
| h2_1:reach | OR | h1_1:access |
| h2_2:reach | OR | h1_1:access |
| h3_0:access | OR | h2_2:reach |
| h3_1:access | OR | h2_0:access, h1_0:traverse, h2_2:reach |
| h3_2:escalate | OR | h1_0:traverse, h1_2:traverse |
| h4_0:escalate | OR | h2_1:reach, h3_0:access, h2_2:reach |
| h4_1:reach | OR | h2_2:reach |
| h4_2:reach | OR | h2_0:access, h3_1:access, h2_2:reach |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
