# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_0:access, h5_2:escalate |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:reach | OR | edge1:reach, edge0:reach |
| h1_1:access | OR | edge1:reach |
| h1_2:obtain | OR | edge0:reach |
| h2_0:reach | OR | edge0:reach |
| h2_1:obtain | OR | h1_2:obtain |
| h2_2:escalate | AND | h1_2:obtain, h1_0:reach |
| h3_0:traverse | OR | h1_1:access |
| h3_1:access | OR | h2_2:escalate, h1_2:obtain, h2_1:obtain |
| h3_2:access | OR | h1_1:access, h1_0:reach |
| h4_0:access | OR | h3_1:access |
| h4_1:escalate | OR | h3_1:access |
| h4_2:obtain | OR | h3_2:access |
| h5_0:access | OR | h4_2:obtain |
| h5_1:pivot | OR | h3_1:access, h4_0:access |
| h5_2:escalate | AND | h4_2:obtain, h3_2:access, h3_1:access |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h3_2:access.

## Question
With those defences in place, is the target still reachable?
