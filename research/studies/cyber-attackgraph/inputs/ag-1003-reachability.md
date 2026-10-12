# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_1:traverse, h5_0:pivot, h5_2:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:access | OR | edge1:reach, edge0:reach |
| h1_1:access | AND | edge1:reach, edge0:reach |
| h1_2:escalate | OR | edge1:reach |
| h2_0:obtain | OR | h1_2:escalate, edge0:reach |
| h2_1:escalate | AND | h1_2:escalate, edge0:reach, h1_0:access |
| h2_2:obtain | OR | edge0:reach, h1_0:access, h1_2:escalate |
| h3_0:obtain | OR | h1_1:access |
| h3_1:access | AND | h1_0:access, h2_1:escalate |
| h3_2:access | OR | h1_2:escalate |
| h4_0:access | OR | h2_2:obtain |
| h4_1:access | OR | h2_1:escalate, h3_2:access |
| h4_2:access | OR | h3_2:access |
| h5_0:pivot | OR | h4_1:access |
| h5_1:traverse | OR | h3_2:access, h3_1:access, h3_0:obtain |
| h5_2:pivot | AND | h3_2:access, h4_0:access, h4_2:access |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h1_1:access, h1_2:escalate.

## Question
With those defences in place, is the target still reachable?
