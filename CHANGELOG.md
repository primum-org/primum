# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project will follow
[Semantic Versioning](https://semver.org/) once it has releases.

## [Unreleased]

### Added

- Repository skeleton: uv workspace with `primum-core` and `primum-runtime`, strict tooling,
  CI, Claude Code configuration and initial documentation.
- Brand "Brass automaton · compact" in `design/`: brandbook, design tokens with generated CSS,
  logo symbol and 56 icons.
- `primum-runtime`: a local HTTP API and WebSocket to turn an LED on and off, with a panic
  button, on a Raspberry Pi or simulated (`uv run just dev`).
- A page served by the runtime to turn the LED on and off from a phone or a browser, with the
  panic button, in English and Spanish, light and dark.
- Scripts to install Primum on a Raspberry Pi as a service that starts with the board
  (`image/provision.sh`) and to work against it from a laptop (`just pi-*`). They refuse a
  board where other software drives GPIO.
- Board profile of the Raspberry Pi 4 Model B (`boards/rpi4b.json`): its 40 pins, buses, PWM
  channels and reserved pins. The runtime takes the board (`--board`, `rpi4b` by default) and
  refuses pins it does not have, also when simulated, and finds the board's GPIO chip by name.
- `primum validate <folder>`: checks a project folder without hardware and explains each
  problem in English or Spanish (`--lang es`), or as JSON (`--json`). It reads the six file
  types of a project (`.hw`, `.vars`, `.sec`, `.evt`, `.sched`, `.auto`), checks that ids are
  unique and that every reference names something of the right kind. Example:
  `examples/minimal/`. It also checks constants and variables (values of their type, limits,
  where names are visible: a file sees the names of its folder and of the folders above, and a
  name is never defined twice), and components (a sequence with parameters gets one argument
  per parameter, and sequences never include each other in a loop). It checks the wiring
  against the board: a GPIO the board does not have or reserves, two elements on one GPIO, a
  GPIO taken by the I2C bus, PWM outputs without hardware PWM or sharing a channel, and I2C
  devices on a missing bus or at the same address (`examples/invalid/` shows each case). Clips
  of one element that overlap in time are an error, and sequences that may run at once on the
  same element a warning; sequences have a `priority` and an `exclusiveGroup`.
  `examples/shop-window/` is a complete project.
- `primum validate` knows what each element can do. A clip asks for one of the actions of its
  element's driver, with their values: a digital output goes `on` and `off`; a PWM output also
  takes `set` (a `level` from 0 to 100) and `fade` (`from` a level `to` another); an input
  takes none, so a track on one is an error. Elements take the options of their driver in the
  `.hw` file (`config`): the frequency of a PWM output, the pull and the debounce of an input.
  A clip holds its action while it lasts; one of 0 ms is an instant command that stays until
  the next clip of the element or the end of the sequence.
- Error messages in English and Spanish (`i18n/`) for every error the runtime can return, each
  with a hint on what to do: unavailable or invalid pins, GPIO permissions, panic active, and
  invalid requests, unknown paths and methods of the API.
