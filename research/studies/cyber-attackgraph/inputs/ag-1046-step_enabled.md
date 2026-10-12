# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_1:traverse, h4_2:traverse |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:access | OR | edge1:reach, edge0:reach, edge2:reach |
| h1_1:pivot | OR | edge0:reach |
| h1_2:traverse | OR | edge0:reach |
| h1_3:escalate | OR | edge0:reach, edge1:reach |
| h2_0:obtain | OR | h1_0:access |
| h2_1:access | OR | edge1:reach |
| h2_2:pivot | OR | h1_1:pivot, h1_3:escalate, edge0:reach |
| h2_3:reach | OR | edge2:reach, edge1:reach |
| h3_0:escalate | OR | h1_1:pivot, h2_2:pivot, h2_3:reach |
| h3_1:access | OR | h2_2:pivot, h1_3:escalate |
| h3_2:traverse | OR | h1_0:access |
| h3_3:escalate | AND | h1_3:escalate, h1_2:traverse |
| h4_0:escalate | AND | h3_3:escalate, h3_0:escalate |
| h4_1:traverse | OR | h2_3:reach |
| h4_2:traverse | OR | h2_0:obtain |
| h4_3:escalate | OR | h3_1:access |

## Current state
The attacker has already compromised: h1_3:escalate.

## Question
Is the step `h3_3:escalate` (type AND) enabled to be taken next?
