# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_1:reach, h3_2:escalate, h3_0:escalate |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:access | OR | edge0:reach |
| h1_1:pivot | OR | edge0:reach, edge1:reach |
| h1_2:escalate | OR | edge0:reach |
| h2_0:traverse | OR | edge1:reach |
| h2_1:traverse | OR | edge1:reach |
| h2_2:pivot | OR | h1_2:escalate |
| h3_0:escalate | AND | h1_2:escalate, h1_0:access |
| h3_1:reach | OR | h2_2:pivot, h1_0:access |
| h3_2:escalate | OR | h1_0:access, h1_1:pivot, h2_2:pivot |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
