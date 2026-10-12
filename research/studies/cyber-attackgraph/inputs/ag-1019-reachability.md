# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_1:reach, h5_2:obtain, h5_0:escalate |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:reach | OR | edge0:reach, edge1:reach |
| h1_1:access | OR | edge0:reach, edge1:reach |
| h1_2:access | AND | edge1:reach, edge0:reach |
| h2_0:traverse | AND | h1_1:access, edge0:reach |
| h2_1:access | AND | h1_1:access, h1_2:access |
| h2_2:reach | OR | edge1:reach, h1_2:access |
| h3_0:traverse | AND | h2_0:traverse, h2_2:reach |
| h3_1:traverse | OR | h1_0:reach |
| h3_2:traverse | OR | h1_0:reach, h2_0:traverse |
| h4_0:obtain | OR | h2_0:traverse, h2_2:reach, h2_1:access |
| h4_1:pivot | AND | h3_2:traverse, h3_0:traverse |
| h4_2:pivot | OR | h2_1:access, h3_2:traverse, h2_0:traverse |
| h5_0:escalate | OR | h3_1:traverse |
| h5_1:reach | AND | h4_1:pivot, h3_0:traverse |
| h5_2:obtain | AND | h4_2:pivot, h4_0:obtain, h3_0:traverse |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h1_0:reach, h5_1:reach.

## Question
With those defences in place, is the target still reachable?
