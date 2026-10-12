# Mechanism: token-bucket capacity limiter (phase-7 held-out case)

A finite, in-process program (no network), different in mechanism from the order service and the tenant-isolation
fixture.

- **Subject.** A caller driving the limiter through a fixed operation sequence (`refill`, `take`). It controls only
  which operation runs next; it cannot set the token count directly.
- **Resource.** One bucket holding an integer token count between 0 and twice the capacity.
- **Capability.** `take()` spends one token when any remain (else it is denied); `refill()` adds the refill amount.
- **Trust boundary.** The capacity cap is enforced inside `refill`; the caller cannot bypass it. The defect is a
  missing cap in that one place.
- **Action.** `take` (precondition: tokens > 0; effect: tokens − 1) and `refill` (secure effect: tokens ←
  min(capacity, tokens + refill)).
- **Property.** `within_capacity` (invariant): the bucket is never above its capacity (`tokens ≤ cap`). Machine-checked
  on the finite model.
- **Oracle.** The real program's token count after each operation, read independently; the capped specification is the
  model. A recorded run above capacity is a violation.


## The recorded run to judge

Capacity is 3. Each row is one operation and the bucket's token count straight after it:

| step | operation | result | tokens after |
|---|---|---|---|
| 0 | refill | — | 2 |
| 1 | refill | — | 3 |
| 2 | take | granted | 2 |
| 3 | take | granted | 1 |
| 4 | refill | — | 3 |
| 5 | take | granted | 2 |
| 6 | take | granted | 1 |
| 7 | take | granted | 0 |
