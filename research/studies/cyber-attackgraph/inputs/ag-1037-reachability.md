# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_0:pivot, h4_2:traverse |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:reach | AND | edge1:reach, edge0:reach |
| h1_1:escalate | OR | edge1:reach, edge0:reach |
| h1_2:obtain | OR | edge0:reach |
| h2_0:traverse | AND | edge0:reach, h1_2:obtain |
| h2_1:access | OR | edge0:reach, h1_0:reach, edge1:reach |
| h2_2:access | OR | edge1:reach, h1_2:obtain |
| h3_0:escalate | OR | h2_1:access |
| h3_1:escalate | OR | h1_1:escalate |
| h3_2:obtain | OR | h2_0:traverse, h2_2:access |
| h4_0:pivot | OR | h2_2:access |
| h4_1:escalate | OR | h2_2:access, h3_1:escalate |
| h4_2:traverse | OR | h3_1:escalate |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h1_1:escalate, h2_2:access.

## Question
With those defences in place, is the target still reachable?
