# Courier route

A courier is at position 0 of a route with positions 0 to 3 and has taken 0 express rides (0 to 3). Exactly two actions are available, named `express` and `walk`:

- `express`: available only at position 0; moves to position 3 and adds 1 to the express rides (cost 10).
- `walk`: available while the position is below 3; moves forward by 1 (cost 1).

Goal `arrived`: the position equals 3. Find the plan with the fewest actions (not the lowest cost).
