# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_1:obtain, h5_0:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:traverse | OR | edge0:reach, edge1:reach |
| h1_1:reach | OR | edge1:reach |
| h1_2:reach | OR | edge0:reach |
| h2_0:reach | OR | edge0:reach |
| h2_1:reach | OR | edge0:reach, h1_0:traverse |
| h2_2:escalate | AND | edge0:reach, h1_1:reach, h1_2:reach |
| h3_0:access | OR | h1_1:reach |
| h3_1:escalate | AND | h2_2:escalate, h1_0:traverse, h1_2:reach |
| h3_2:escalate | OR | h1_0:traverse, h1_1:reach, h2_2:escalate |
| h4_0:obtain | OR | h2_1:reach |
| h4_1:escalate | OR | h3_2:escalate |
| h4_2:escalate | OR | h3_0:access |
| h5_0:obtain | AND | h3_2:escalate, h3_0:access |
| h5_1:obtain | OR | h3_2:escalate |
| h5_2:pivot | AND | h4_2:escalate, h3_2:escalate |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h3_1:escalate.

## Question
With those defences in place, is the target still reachable?
