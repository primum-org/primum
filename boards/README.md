# Board profiles

One data file per board model: header pins, buses, PWM channels, reserved pins, the GPIO
chip with the line of each GPIO, and the limits the board puts on the options of its elements
(each with the documentation it comes from). Adding a compatible board means adding a file here, named
after its `model`, then running `uv run just gen` (the runtime ships a copy).

- Format: `schemas/board-profile.schema.json`. Rules and use: `docs/specs/board-profiles.md`.
- `rpi4b.json`: Raspberry Pi 4 Model B.
