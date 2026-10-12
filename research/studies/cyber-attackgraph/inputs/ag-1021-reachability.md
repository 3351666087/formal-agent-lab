# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_0:pivot, h4_1:access |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:obtain | OR | edge0:reach, edge1:reach |
| h1_1:obtain | AND | edge1:reach, edge0:reach |
| h1_2:reach | OR | edge1:reach, edge0:reach |
| h2_0:traverse | OR | h1_2:reach, edge0:reach, edge1:reach |
| h2_1:pivot | AND | h1_1:obtain, h1_0:obtain, edge1:reach |
| h2_2:escalate | OR | h1_1:obtain, h1_2:reach |
| h3_0:access | OR | h1_0:obtain |
| h3_1:pivot | AND | h2_1:pivot, h2_2:escalate |
| h3_2:obtain | OR | h1_2:reach, h2_2:escalate |
| h4_0:pivot | AND | h3_2:obtain, h3_0:access, h3_1:pivot |
| h4_1:access | OR | h2_0:traverse, h3_1:pivot, h3_0:access |
| h4_2:escalate | AND | h2_0:traverse, h3_2:obtain, h3_1:pivot |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h3_1:pivot, h4_1:access.

## Question
With those defences in place, is the target still reachable?
