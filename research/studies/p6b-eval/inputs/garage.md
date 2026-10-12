# Parking-garage tally

A parking garage keeps a tally counter holding a whole number from 0 to 3, and an indicator light that starts off. Exactly two actions are available, named `toggle` and `reset`:

- `toggle`: flips the indicator light and adds 1 to the counter; it cannot be used when the counter is already 3.
- `reset`: sets the counter back to 0 and turns the light off; it can only be used when the counter is above 0.

Goal `three_toggles`: the counter equals 3.
