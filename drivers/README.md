# Driver manifests

One data file per element type: what a clip may ask of its elements (actions and their
parameters), the options an element takes in a `.hw` file, where it rests (safe state) and who
wins when two sequences command it (conflict policy). Adding a driver starts with a file here,
named after its `elementType`, then `uv run just gen` (the CLI ships a copy).

- Format: `schemas/driver.schema.json`. Rules and use: `docs/specs/drivers.md`. Why: decision
  0016.
- `digital_output.json`, `pwm_output.json`, `digital_input.json`: the drivers of phase 3.
