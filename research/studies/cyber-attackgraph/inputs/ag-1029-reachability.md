# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_0:obtain, h4_1:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:obtain | OR | edge0:reach, edge1:reach |
| h1_1:escalate | AND | edge1:reach, edge0:reach |
| h1_2:escalate | OR | edge1:reach, edge0:reach |
| h2_0:traverse | OR | h1_1:escalate |
| h2_1:pivot | OR | h1_0:obtain |
| h2_2:reach | AND | edge0:reach, h1_0:obtain, h1_2:escalate |
| h3_0:pivot | OR | h2_1:pivot, h2_2:reach, h1_2:escalate |
| h3_1:pivot | OR | h1_1:escalate |
| h3_2:obtain | OR | h1_0:obtain, h1_2:escalate |
| h4_0:obtain | OR | h3_1:pivot, h2_0:traverse, h3_2:obtain |
| h4_1:pivot | OR | h2_0:traverse, h3_2:obtain |
| h4_2:reach | OR | h3_1:pivot |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h1_0:obtain, h4_0:obtain.

## Question
With those defences in place, is the target still reachable?
