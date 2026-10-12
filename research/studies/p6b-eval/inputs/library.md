# Library return desk

A library return desk tracks returns on a small counter holding a whole number from 0 to 3, with a status lamp that starts off. Exactly two actions are available, named `toggle` and `reset`:

- `toggle`: switches the status lamp and increases the counter by 1; it is unavailable once the counter has reached 3.
- `reset`: returns the counter to 0 and switches the lamp off; it is available only while the counter is greater than 0.

Goal `three_toggles`: the counter equals 3.
