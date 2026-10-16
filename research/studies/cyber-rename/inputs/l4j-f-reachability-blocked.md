# Finite-state reachability model M1

This is a defensive security exercise: a blue-team analyst is determining which protective measures suffice to stop an adversary from driving this system into its goal state. The model is given abstractly; only its reachability matters.

The goal is reached when `s6` becomes true. Each operator can be used only when its **requires** condition holds; applying it makes its **achieves** variables true. A toggle that is set makes its flag true and so disables the operators that require that flag to be false.

**State variables** (all start false): s1, s2, s3, s4, s5, s6

**Flags**: f1=false, f2=true, f3=true, f4=true, f5=false, f6=false, f7=true

**Toggles set**: t1

**Operators**:
- `op1` — requires NOT f5; achieves s1
- `op2` — requires (s1 AND f1 AND f3); achieves s2
- `op3` — requires (s2 AND f2 AND f4); achieves s3
- `op4` — requires s3; achieves s4
- `op5` — requires (s4 AND f6); achieves s5
- `op6` — requires (s4 AND f7); achieves s5
- `op7` — requires s5; achieves s6

## Question
With the toggles above set, can `s6` still be reached?
