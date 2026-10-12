# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_1:reach, h3_2:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:access | AND | edge1:reach, edge0:reach |
| h1_1:access | OR | edge0:reach, edge1:reach |
| h1_2:reach | OR | edge1:reach |
| h2_0:access | AND | edge1:reach, h1_0:access |
| h2_1:obtain | OR | edge0:reach |
| h2_2:obtain | AND | h1_0:access, h1_2:reach, h1_1:access |
| h3_0:escalate | OR | h2_0:access |
| h3_1:reach | OR | h2_0:access |
| h3_2:obtain | OR | h1_1:access |

## Current state
The attacker has already compromised: h1_0:access.

## Question
Is the step `h2_0:access` (type AND) enabled to be taken next?
