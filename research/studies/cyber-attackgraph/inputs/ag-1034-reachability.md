# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach, edge2:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_3:escalate, h4_0:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| edge2:reach | OR | — (entry) |
| h1_0:reach | OR | edge0:reach, edge2:reach, edge1:reach |
| h1_1:pivot | OR | edge0:reach, edge2:reach |
| h1_2:reach | OR | edge0:reach |
| h1_3:escalate | OR | edge1:reach, edge0:reach, edge2:reach |
| h2_0:pivot | OR | edge0:reach, edge1:reach, h1_2:reach |
| h2_1:obtain | OR | h1_0:reach, h1_2:reach |
| h2_2:reach | AND | h1_2:reach, edge2:reach, edge1:reach |
| h2_3:reach | OR | h1_3:escalate, edge1:reach |
| h3_0:obtain | OR | h1_1:pivot |
| h3_1:access | OR | h2_3:reach, h2_1:obtain, h1_2:reach |
| h3_2:traverse | AND | h2_3:reach, h1_3:escalate |
| h3_3:pivot | OR | h1_0:reach, h2_0:pivot, h1_3:escalate |
| h4_0:pivot | OR | h2_2:reach |
| h4_1:access | OR | h2_2:reach, h2_0:pivot, h3_2:traverse |
| h4_2:access | OR | h2_0:pivot, h3_2:traverse |
| h4_3:escalate | OR | h2_1:obtain |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h1_0:reach, h2_1:obtain.

## Question
With those defences in place, is the target still reachable?
