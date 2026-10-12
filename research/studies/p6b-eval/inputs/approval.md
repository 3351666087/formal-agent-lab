# Document approval

A document starts at stage 0 of a 4-stage approval track (stages 0 to 3) and has used 0 fast-track steps (0 to 3). Exactly two actions are available, named `express` and `walk`:

- `express`: available only at stage 0; jumps the document to stage 3 and uses 1 fast-track step (cost 10).
- `walk`: available while the stage is below 3; advances the document by one stage (cost 1).

Goal `arrived`: the stage equals 3. Find the plan with the fewest actions (not the lowest cost).
