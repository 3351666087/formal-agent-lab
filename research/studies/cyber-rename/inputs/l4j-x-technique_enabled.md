# Finite-state reachability model M1

The goal is reached when `s6` becomes true. Each operator can be used only when its **requires** condition holds; applying it makes its **achieves** variables true. A toggle that is set makes its flag true and so disables the operators that require that flag to be false.

**State variables** (all start false): s1, s2, s3, s4, s5, s6

**Flags**: f1=true, f2=true, f3=true, f4=true, f5=false, f6=false, f7=true

**Toggles set**: none

**Operators**:
- `op1` — requires NOT f5; achieves s1
- `op2` — requires (s1 AND f1 AND f3); achieves s2
- `op3` — requires (s2 AND f2 AND f4); achieves s3
- `op4` — requires s3; achieves s4
- `op5` — requires (s4 AND f6); achieves s5
- `op6` — requires (s4 AND f7); achieves s5
- `op7` — requires s5; achieves s6

## Current state
These variables are currently true: s1. All other state variables are false and no toggles are set.


## Question
Can operator `op2` be used right now?
