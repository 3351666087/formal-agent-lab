# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_3:obtain, h4_0:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:pivot | OR | edge1:reach |
| h1_1:reach | OR | edge1:reach, edge2:reach |
| h1_2:escalate | OR | edge1:reach |
| h1_3:access | OR | edge1:reach |
| h2_0:traverse | OR | h1_2:escalate |
| h2_1:obtain | OR | edge2:reach, edge0:reach |
| h2_2:escalate | OR | h1_3:access, h1_0:pivot |
| h2_3:traverse | OR | h1_0:pivot, h1_1:reach, edge1:reach |
| h3_0:pivot | AND | h1_1:reach, h2_3:traverse |
| h3_1:obtain | AND | h2_2:escalate, h2_0:traverse, h1_0:pivot |
| h3_2:escalate | OR | h2_2:escalate, h2_3:traverse, h1_0:pivot |
| h3_3:obtain | AND | h2_1:obtain, h2_0:traverse, h2_2:escalate |
| h4_0:pivot | OR | h3_3:obtain |
| h4_1:traverse | OR | h2_0:traverse |
| h4_2:obtain | OR | h3_1:obtain |
| h4_3:obtain | OR | h2_2:escalate, h2_1:obtain |

## Current state
The attacker has already compromised: h1_1:reach, h2_3:traverse.

## Question
Is the step `h3_0:pivot` (type AND) enabled to be taken next?
