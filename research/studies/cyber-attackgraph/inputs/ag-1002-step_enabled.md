# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_0:access, h4_3:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:obtain | AND | edge1:reach, edge0:reach, edge2:reach |
| h1_1:access | OR | edge2:reach |
| h1_2:obtain | AND | edge0:reach, edge1:reach, edge2:reach |
| h1_3:reach | OR | edge0:reach, edge2:reach |
| h2_0:pivot | OR | h1_0:obtain, h1_2:obtain |
| h2_1:traverse | OR | edge0:reach, h1_1:access |
| h2_2:traverse | OR | h1_0:obtain, h1_1:access, edge2:reach |
| h2_3:reach | OR | h1_0:obtain |
| h3_0:traverse | OR | h1_1:access |
| h3_1:access | OR | h1_2:obtain, h2_0:pivot |
| h3_2:access | OR | h1_2:obtain |
| h3_3:reach | OR | h1_1:access |
| h4_0:access | OR | h3_3:reach |
| h4_1:reach | AND | h3_0:traverse, h3_2:access |
| h4_2:pivot | OR | h2_1:traverse |
| h4_3:obtain | OR | h2_1:traverse |

## Current state
The attacker has already compromised: edge1:reach, edge2:reach.

## Question
Is the step `h1_0:obtain` (type AND) enabled to be taken next?
