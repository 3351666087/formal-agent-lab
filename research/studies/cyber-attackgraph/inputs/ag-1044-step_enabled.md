# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_1:obtain, h3_0:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:pivot | OR | edge1:reach, edge0:reach |
| h1_1:obtain | OR | edge0:reach |
| h1_2:traverse | OR | edge0:reach |
| h2_0:obtain | OR | h1_1:obtain |
| h2_1:obtain | OR | edge0:reach |
| h2_2:escalate | OR | h1_2:traverse |
| h3_0:pivot | AND | h2_0:obtain, h1_2:traverse |
| h3_1:obtain | AND | h2_2:escalate, h2_0:obtain |
| h3_2:pivot | OR | h2_2:escalate |

## Current state
The attacker has already compromised: h2_0:obtain, h2_2:escalate.

## Question
Is the step `h3_1:obtain` (type AND) enabled to be taken next?
