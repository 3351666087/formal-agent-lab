# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): edge0:reach, edge1:reach
- Target: crown:obtain

| step | type | parents |
|---|---|---|
| crown:obtain | OR | h4_2:escalate, h4_1:obtain |
| edge0:reach | OR | — (entry) |
| edge1:reach | OR | — (entry) |
| h1_0:access | OR | edge1:reach |
| h1_1:access | OR | edge0:reach |
| h1_2:reach | OR | edge0:reach |
| h2_0:traverse | OR | h1_2:reach, edge1:reach |
| h2_1:access | OR | edge1:reach, edge0:reach |
| h2_2:traverse | OR | edge0:reach, h1_1:access, h1_0:access |
| h3_0:traverse | OR | h2_2:traverse |
| h3_1:obtain | AND | h2_2:traverse, h1_1:access, h1_0:access |
| h3_2:access | OR | h2_1:access |
| h4_0:access | OR | h2_2:traverse, h2_1:access, h3_0:traverse |
| h4_1:obtain | OR | h2_2:traverse |
| h4_2:escalate | AND | h3_0:traverse, h2_0:traverse, h2_2:traverse |

## Deployed defences
The defender has blocked these steps (they can no longer be used): h2_2:traverse.

## Question
With those defences in place, is the target still reachable?
