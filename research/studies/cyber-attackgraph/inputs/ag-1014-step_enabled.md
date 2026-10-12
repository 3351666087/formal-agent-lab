# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_1:traverse, h4_3:pivot, h4_0:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:obtain | OR | edge0:reach |
| h1_1:escalate | OR | edge1:reach |
| h1_2:access | OR | edge2:reach, edge0:reach, edge1:reach |
| h1_3:access | OR | edge2:reach, edge1:reach |
| h2_0:reach | OR | h1_3:access |
| h2_1:pivot | OR | h1_2:access, edge1:reach, h1_3:access |
| h2_2:pivot | OR | h1_1:escalate, edge2:reach |
| h2_3:obtain | OR | edge1:reach |
| h3_0:pivot | OR | h2_0:reach |
| h3_1:access | OR | h2_3:obtain, h1_2:access, h2_0:reach |
| h3_2:reach | AND | h1_2:access, h2_0:reach |
| h3_3:traverse | OR | h1_3:access |
| h4_0:obtain | OR | h2_3:obtain, h2_0:reach, h3_2:reach |
| h4_1:traverse | OR | h3_2:reach, h2_0:reach |
| h4_2:reach | OR | h3_3:traverse, h3_2:reach, h3_1:access |
| h4_3:pivot | OR | h2_0:reach, h3_1:access, h2_2:pivot |

## Current state
The attacker has already compromised: h2_0:reach.

## Question
Is the step `h3_2:reach` (type AND) enabled to be taken next?
