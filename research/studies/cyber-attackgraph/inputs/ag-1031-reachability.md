# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h5_1:escalate, h5_0:access, h5_2:pivot |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:traverse | OR | edge0:reach, edge1:reach |
| h1_1:escalate | OR | edge0:reach, edge1:reach |
| h1_2:escalate | AND | edge1:reach, edge0:reach |
| h2_0:reach | OR | edge1:reach, edge0:reach |
| h2_1:pivot | OR | h1_2:escalate |
| h2_2:traverse | AND | edge0:reach, edge1:reach, h1_0:traverse |
| h3_0:escalate | OR | h2_0:reach |
| h3_1:pivot | OR | h1_0:traverse, h2_1:pivot, h2_0:reach |
| h3_2:obtain | OR | h1_1:escalate, h1_2:escalate |
| h4_0:escalate | OR | h3_1:pivot |
| h4_1:escalate | OR | h2_2:traverse, h2_0:reach |
| h4_2:reach | OR | h2_2:traverse |
| h5_0:access | AND | h4_1:escalate, h3_1:pivot |
| h5_1:escalate | OR | h3_1:pivot |
| h5_2:pivot | OR | h4_0:escalate, h4_1:escalate, h3_2:obtain |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h3_1:pivot, h5_2:pivot.

## Question
With those defences in place, is the target still reachable?
