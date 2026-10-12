# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_0:obtain, h4_1:reach, h4_2:access |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:escalate | OR | edge0:reach |
| h1_1:access | OR | edge0:reach |
| h1_2:obtain | OR | edge2:reach, edge0:reach |
| h1_3:obtain | OR | edge2:reach, edge0:reach |
| h2_0:access | OR | edge2:reach |
| h2_1:reach | OR | edge0:reach, edge2:reach |
| h2_2:traverse | OR | edge0:reach |
| h2_3:escalate | AND | h1_3:obtain, edge0:reach |
| h3_0:access | OR | h2_3:escalate |
| h3_1:access | OR | h2_1:reach, h1_2:obtain |
| h3_2:obtain | OR | h1_2:obtain, h2_1:reach |
| h3_3:escalate | OR | h2_2:traverse, h1_0:escalate, h1_1:access |
| h4_0:obtain | AND | h2_3:escalate, h2_1:reach |
| h4_1:reach | AND | h2_0:access, h3_3:escalate, h3_0:access |
| h4_2:access | AND | h3_1:access, h2_1:reach |
| h4_3:reach | OR | h2_1:reach, h2_0:access |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h1_3:obtain, h2_1:reach.

## Question
With those defences in place, is the target still reachable?
