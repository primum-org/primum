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
  A clip holds its action while it lasts; one of 0 ms is an instant command that stands until
  the next instant command of the element or the end of its own sequence. On an element, the
  command that started last wins: a clip plays over an instant command and gives the element
  back to it, and an instant command inside a clip cuts it.
- A sequence can hold (`whenDone: "hold"`): instead of ending with its last clip it stays as
  it is until it is stopped. "On at dusk, off at 23:00" is one sequence that holds, started by
  one automation and stopped by another (`examples/evening-lights/`). It only holds when it
  is started on its own: including it in another sequence gets a warning. A sequence that ends
  with an instant command and does not hold gets a warning: it would not be seen.
- The runtime can run a deployment package: `primum-runtime --package <file>` takes its
  elements and its board from it, and refuses to start with a package this board cannot run,
  saying what is wrong, always with exit status 1. It also refuses elements on a pin the
  board reserves or lacks, with `--pin` too (`--pin 0` started before). The API names elements by their id (`PUT /api/outputs/{id}`) and the
  state gives each its `id` and its `name`; with `--pin` the ids are `led`, `button` and
  `dimmer`, as before. Sequences are not run yet.
- `primum validate` refuses a PWM output with `activeLow`: its driver cannot invert the
  output yet, and it would have rested fully on.
- The runtime runs the sequences of its package: start and stop them from the page or with
  `POST /api/sequences/{id}/start` and `/stop`. A command on an output is now manual control
  over the sequences until it is released (`DELETE /api/outputs/{id}`, *Release* on the
  page); a test that expires gives the output back to the sequences. Panic stops every
  sequence. A fade moves its light smoothly over its clip, and a fade without `from` starts
  from where the light is. The variables of the package are in the state and can be set
  with `PUT /api/variables/{id}`; a value outside a variable's limits is refused.
- A file with half a character (an escape like `\ud83d` without its pair) is reported as a
  problem of the file; it used to pass validation and crash the build.
- Conditions of automations (`if`) are now a real language, checked by `primum validate`:
  `visits < max_visits and not paused`, with `and`, `or`, `not`, comparisons, arithmetic and
  parentheses. A condition that cannot be read, uses a name it does not see or mixes types
  is explained before deploying. The deployment package carries each condition compiled.
  Two things that passed before are now errors: an empty `if` (`""`; leave the field out
  for no condition), and a constant or a variable called `and`, `or`, `not`, `true` or
  `false`, in any case.
- The runtime runs the automations of its package: when an input turns on or off, or an
  event is fired (`POST /api/events/{id}/fire`, for events of the app or the API), the
  automations that wait for it check their condition and start or stop sequences and change
  variables. A counter that is incremented stays within its limits. Panic stops all of it.
  The state lists the events and the automations, with what went wrong in each, if anything.
- A board takes its packages through its API, in two steps: `PUT /api/package` checks one
  and keeps it, `POST /api/package/activate` runs it, and `POST /api/package/rollback` puts
  the one before back. A package the board cannot run is refused and what was running goes
  on. A service started without `--package` and `--pin` runs what was activated on it, and
  starts with nothing instead of failing when there is none.
- The board keeps a trace of what it did and why: what happened, which automations acted
  or did not, the sequences that started and ended, what a person commanded, panic. Read
  it with `GET /api/trace`, or follow it live on the WebSocket `/api/trace/ws`.
- Variables marked `persistent` keep their value across a restart and a power cut: a
  counter of visits, a brightness set from the phone. They are kept on the board for the
  project, so a new package of the same project finds them.
- Schedules run on the board: a time of day ("Monday at 20:30") and a window that opens
  ("Monday to Saturday, 10:00 to 20:30") start their automations, and a board that comes
  back inside a window starts them again. An automation can act only during the windows
  it names (`during`). Nothing happens until the board knows the time (set from the
  network, or `PRIMUM_TRUST_CLOCK=1`).
- A project with schedules says its time zone: `timeZone` in `project.json`
  (`Europe/Madrid`). Without it, it is no longer valid.
- `primum validate` refuses an event that waits for an element that tells nothing.
- `primum build <folder>` compiles a project into its deployment package, one JSON file with
  its own hash: what a board will run. A project with errors is not built.
- A clip can take a value from a name instead of writing it (`valueOf`): a constant, a
  variable (read while running; it needs limits within the parameter's) or a parameter of its
  component, which the including sequence gives, also by name. `examples/shop-window/` fades
  its LED up to the `brightness` setting.
- `fade` may leave its `from` out, to start from where the light is.
- `primum validate` refuses an automation that starts or stops a component (a sequence with
  parameters), and one that sets a variable to a value outside its limits.
- A sequence can say what starting it does while it is already running
  (`whenStartedAgain`): `restart`, the default, or `ignore`. Starting a sequence stops the
  others of its exclusive group. Decided for the engine to come: a schedule's window starts
  its automations when it opens and when the board comes back inside it, so
  `examples/evening-lights/` lights its lamp again after a power cut.
- `primum validate` checks each element against what its board takes: a PWM output on a
  Raspberry Pi 4 runs from 1 Hz to 100 kHz, a limit that now lives in the board's profile with
  the documentation it comes from. It also warns when a fade to 0 would end with the light
  jumping back on because an earlier instant `on` is still in force, and no longer warns
  about a sequence that ends with an instant `set` to 0.
- The runtime drives its elements through drivers, one per element type, that implement the
  manifests: an output is read back after every command, and a value outside the limits of
  its driver or of its board is refused. The service can listen to an input (`--input-pin`
  and `--input-pull`, or `PRIMUM_INPUT_PIN` and `PRIMUM_INPUT_PULL`): the page shows whether
  it is active, as it changes. `primum validate` refuses a number that nothing limits.
- If the service is killed or hangs, its outputs no longer stay as they were: systemd runs
  `primum-safe` after every stop, which puts the outputs the service had claimed in their
  safe state, and a watchdog restarts a service that stops answering.
- The service can drive a dimmable output (`--pwm-pin`, or `PRIMUM_PWM_PIN`): the page shows
  a slider for its level. The API now asks an output for an action
  (`{"action": "set", "arguments": {"level": 40}}`) instead of `{"on": true}`, and reports
  each output's level.
- Each output of the page has a *Test* button: it turns the output on for ten seconds and
  off on its own, to check a wire without leaving it on. Over the API, any command can
  expire (`durationMs`, from one second to five minutes).
- Pairing: a board has a pairing code (`primum-pairing` shows it), and a phone or a program
  must give it once before the board shows or takes anything from it, panic included.
  `primum-pairing --renew` makes a new code and unpairs every device. **Breaking:** a
  service asks for pairing unless started with `--no-pairing`.
- Error messages in English and Spanish (`i18n/`) for every error the runtime can return, each
  with a hint on what to do: unavailable or invalid pins, GPIO permissions, panic active, and
  invalid requests, unknown paths and methods of the API.
