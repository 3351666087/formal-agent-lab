# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_2:reach, h3_0:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:escalate | OR | edge0:reach |
| h1_1:access | OR | edge0:reach |
| h1_2:escalate | OR | edge1:reach, edge0:reach |
| h2_0:access | OR | edge0:reach, h1_1:access |
| h2_1:reach | OR | h1_2:escalate, edge1:reach |
| h2_2:access | OR | h1_0:escalate, edge1:reach, edge0:reach |
| h3_0:obtain | OR | h2_0:access |
| h3_1:traverse | OR | h1_2:escalate, h1_1:access, h1_0:escalate |
| h3_2:reach | OR | h2_2:access, h1_0:escalate |

## Current state
The attacker has already compromised: edge0:reach, edge1:reach.

## Question
Is the step `h1_2:escalate` (type OR) enabled to be taken next?
