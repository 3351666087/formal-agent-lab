# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h3_0:escalate, h3_1:reach |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:access | AND | edge0:reach, edge1:reach |
| h1_1:escalate | OR | edge0:reach, edge1:reach |
| h1_2:obtain | OR | edge1:reach |
| h2_0:access | OR | edge1:reach, h1_2:obtain |
| h2_1:reach | OR | h1_0:access |
| h2_2:traverse | AND | edge1:reach, h1_0:access |
| h3_0:escalate | OR | h1_0:access |
| h3_1:reach | OR | h1_1:escalate, h1_2:obtain |
| h3_2:escalate | OR | h2_1:reach, h1_1:escalate, h1_0:access |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h1_0:access, h3_1:reach.

## Question
With those defences in place, is the target still reachable?
