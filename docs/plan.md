# Plan

Each phase ends with something working on a real Raspberry Pi 4B. Update the status column
when a phase starts or finishes.

| Phase | Goal | Status |
|---|---|---|
| 0 | Repository skeleton: structure, docs, rules, tooling, CI | Done |
| 1 | End-to-end skeleton: toggle an LED from a phone | Done |
| 2 | Project model and `core`: workspace of files, board profile, pin conflicts, validation | Done |
| 3 | HAL, basic drivers and safety | In progress |
| 4 | Engine: sequences, automations, events, variables, arbitration, deployment packages | Not started |
| 5 | Local web UI v1 | Not started |
| 6 | Hardware manager (`config.txt`, tryboot) and I2C, LED strip and audio drivers | Not started |
| 7 | Primum OS image | Not started |
| 8 | Local MCP server | Not started |

## Phase 0 · Repository skeleton

- [x] uv workspace with `primum-core` and `primum-runtime`
- [x] ruff, pyright (strict), pytest, import-linter, pre-commit
- [x] `justfile` with `check` (same as CI)
- [x] CI on GitHub Actions
- [x] Claude Code: `CLAUDE.md`, rules, hooks, permissions
- [x] Docs: vision, glossary, architecture, plan, decisions
- [x] Brand in `design/`: brandbook, tokens (single source) with generated CSS, logo, icons
- [x] Development Pi with Raspberry Pi OS Lite 64-bit reachable over SSH (`primum-dev`)

**Done when:** CI is green, `just check` passes locally and the development Pi is reachable.

## Phase 1 · End-to-end skeleton

The whole path, small: phone → page → API → runtime → HAL → GPIO → LED, keeping the repository's
rules from the first line. Blocks 1.1–1.3 need no Pi (simulated HAL); 1.4–1.5 need the
development Pi. One pull request per block.

**1.1 · Minimal HAL and safe state** · *no Pi* · **done**
- `primum_runtime.hal`: `Hal`, `DigitalOutput`, `OutputSpec`; `SimulatedHal` (tests,
  `--simulate`) and `GpiodHal` (libgpiod v2), chosen by `create_hal`.
- Safe state (off) when an output is created, on `apply_safe_state` and on `close`, also when
  leaving the `with` block on an exception (Ctrl+C). Best-effort across outputs: one failing
  line never stops the others from going safe or being released. Crash safety (watchdog) stays
  in phase 3.
- `DigitalOutput.read()` reads the hardware; `is_on` is the last state commanded.
- `gpiod` is a Linux-only dependency, imported lazily and only by `hal/gpiod_hal.py` (an
  import contract enforces it); its own type hints pass pyright strict (decision 0010).
- Errors with codes: `hal.pin_in_use`, `hal.pin_invalid`, `hal.pin_unavailable`,
  `hal.chip_not_found` (`hal.chip_unavailable` until 2.2), `hal.chip_access_denied`,
  `hal.unsupported_platform`, `hal.closed`, `hal.safe_state_incomplete`,
  `hal.release_incomplete` (catalog entries in 1.3). Lists of pins are tuples, never
  pre-joined text.
- A `hw` test for the real HAL, run on the Pi with `just test-hw`: it checks what the kernel
  reports for the line, not the LED itself. It needs `PRIMUM_HW_TEST_PIN` (a pin with nothing
  wired, or only an LED) and fails without it; from phase 2 the pin comes from the board profile.
- `GpiodHal` is also tested without a Pi (in CI), with a fake `gpiod.Chip`: requested
  configuration, values written, release on close, error mapping and `create_hal`.

**1.2 · Service, API and WebSocket** · *no Pi* · **done** (decision 0011)
- FastAPI + uvicorn (pydantic at this edge only, decision 0008): `GET /api/status`,
  `PUT /api/outputs/{name}` (`{"on": true}`), `POST /api/panic` and `DELETE /api/panic`
  (panic is latched until released), WebSocket `/api/ws` sending the full state on connect and
  after every change.
- Layers `cli` → `api` → `config` → `control` → `hal` → `errors`, enforced by import contracts;
  web frameworks only in `api` and `cli`.
- Configuration by CLI or `PRIMUM_*` variables: `--simulate`, `--chip`, `--pin` (required, no
  default), `--active-low`, `--host` (`127.0.0.1`), `--port` (8080). The data directory waits
  for the first file the runtime writes.
- The HAL lives in the app's lifespan. A test starts the simulated service as a real process,
  turns the LED on, sends `SIGTERM` and checks the log line written after the HAL closed with
  every output off; another ends the lifespan with the test client.
- API errors carry codes (decision 0009): `output.unknown`, `panic.active`, `request.invalid`.
- `uv run just dev`: the simulated service on the laptop. Tests with the test client.

**Done when:** `uv run just dev` and `curl` or a browser toggle the simulated LED, and the
WebSocket reports every change.

**1.3 · Minimal page and i18n** · *no Pi* · **done**
- `i18n/en.json` and `es.json`: `ui.*` strings of the page and `errors.*` for the codes of 1.1
  and 1.2 plus `request.not_found` and `request.method_not_allowed` (FastAPI's own 404 and 405
  carry codes too), each with a `message` and a `hint` (the hint of `hal.chip_access_denied` says
  to add the user to group `gpio`). Every code is a member of `ErrorCode`, so the type checker
  rejects an undeclared one (decision 0009).
- `test_catalogs.py`: same strings and placeholders in both catalogs; `ErrorCode` and the
  `errors` entries match both ways; messages never embed technical params; the page uses every
  `ui` key and only keys that exist (keys are written literally, so the test can find them).
- Params named `detail`, `consumer` and `fields` carry technical text: the page shows them apart,
  as a technical detail, never as the message. Tuple params (lists of pins) are formatted for
  the language with `Intl.ListFormat`. `request.invalid`'s detail is built from the field
  problems only, never from FastAPI's text, which names source files.
- A minimal page served by the runtime at `/` (HTML, CSS and JavaScript modules, no build step;
  Vue arrives in phase 5): a switch per output, the panic notice and its release, API errors
  with message, hint and technical detail, and "No connection" when the service is unreachable
  (switches disabled, panic never). Mobile first (≥ 44 px targets, panic 72 px with its
  octagonal chamfer), light and dark from the tokens, language from the browser. Icons are kept
  in memory, so the notice keeps its icon offline. Fonts fall back to system fonts until the
  woff2 files arrive (phase 5). Sizes come from the new `size.*` tokens (touch target,
  controls, rows, transport, panic and its chamfer, icons, focus ring, rules, content width),
  taken from the brandbook's density table: `app.css` has no literal pixel value. Offline, the
  switches become `aria-pressed="mixed"`, with no state word and the thumb in the middle: the
  last state may be stale.
- `just test-js` (part of `just check`, Node 22 or later; CI installs Node 24): Node's built-in
  runner tests `i18n.js` with the real catalogs (language choice, placeholders, lists, unknown
  codes, technical params).
- The page's shared assets (catalogs, `tokens.css`, icons, logo) are copied into
  `primum_runtime/ui/generated/` by `just gen` (`tools/gen_assets.py`), so the installed
  runtime serves them; `just gen-check` fails if a copy is stale.

**Done when:** from the laptop's browser the page toggles the simulated LED in English and
in Spanish, and the consistency test exists and passes (every code the runtime raises has an
entry in both catalogs).

**1.4 · Deployment to the development Pi** · *needs the Pi* · **done**
(decision 0012)
- The development Pi is a Pi, or an SD card, for Primum only. A Pi that already runs other GPIO
  software (RPi.GPIO or pigpio through `/dev/gpiomem`) is not one: that software may have
  relays wired to the very pins Primum would use. Provisioning refuses to run where other
  software drives GPIO, found generically by
  `image/check-gpio-users.sh` (processes holding `/dev/gpiomem` or `/dev/mem`, `pigpiod`); no
  program is named in the code. Software installed but not running is not found: that is why
  the Pi is for Primum only.
- `gpiod` 2.5.0 has wheels for Python 3.13 on aarch64, and `uv sync` installed it on the Pi with
  no build; provisioning still installs `build-essential` in case one is needed. A broken
  install (part of `gpiod` missing, such as `gpiod._ext`) is `hal.gpio_library_broken`, with a
  test.
- Other GPIO software is checked where the check can see it: `check-gpio-users.sh` needs root
  (a normal user cannot see other users' processes, so it would pass) and also runs as the
  service's `ExecStartPre`, so Primum does not start next to it. The HAL does not warn about a
  free line that is already an output: Primum's own released lines look the same, so the
  warning showed on every restart (decision 0010).
- `image/provision.sh` (idempotent): checks the board and GPIO users; packages, `uv` (pinned),
  user `primum` in group `gpio`, `/data`, `/etc/primum/runtime.env` (the LED's pin, required the
  first time, no default; listens on the local network, port 8080), the runtime in
  `/opt/primum/venv` (no dev tools, not editable), systemd unit `primum.service` (restart on
  failure, hardened, writes only `/data`; bytecode compiled at install, since the service
  cannot write it), a persistent journal on the development Pi. `--app-only` installs new
  source and the unit, then restarts. A restart counts only once `/api/status` answers (up to
  15 s): systemd's "active" comes before the HAL claims the pin.
- `tools/pi.sh` behind `just pi-provision PIN`, `just pi-sync`, `just pi-test`, `just pi-logs`
  and `just pi-watch`. The host comes from `PRIMUM_PI_HOST`, `primum-dev` by default.
  `pi-test` stops the service, runs the `hw` tests on the
  configured pin with only the runtime and the `test` group installed (some dev tools have no
  wheel for the Pi), then starts it again. Claude Code permissions allow `uv run just` tasks,
  not raw `ssh` or `rsync`.
- Off the Pi: `shellcheck` on every script (`just lint`) and `tools/tests/test_pi_scripts.py`
  (GPIO users found in a fake process tree, a board that is not a Pi, the default host, no pin).
- On the development Pi (2026-11-04: Pi 4, a clean Raspberry Pi OS Lite 64-bit, an LED on GPIO
  17, on the network Windows shares from the laptop): `just pi-provision 17`, `just pi-test`,
  the phone toggles the LED and panics, two pages follow each other, and after a reboot the LED
  goes off with the service and the page comes back by itself.

**Done when:** a phone on the same Wi-Fi opens the development Pi on port 8080, turns the LED on,
and it still works after a reboot.

**1.5 · Image spike** · *needs the Pi, half a day* · **done** (decision 0013)
- CI builds the minimal rpi-image-gen image on an ARM runner; boot it on the Pi. Only a check
  that the tool works: the real image is phase 7.
- `image/spike/` (config, a layer and its overlay) and `.github/workflows/image-spike.yml`
  (`ubuntu-24.04-arm`, rpi-image-gen pinned to v2.9.0, by hand or on pull requests that change
  the spike; uploads `primum-spike.img.xz`). Debian Trixie for a Pi 4, user `primum`, SSH with
  keys only. The Wi-Fi password and the SSH key go in `primum/` on the boot partition after
  flashing and a boot service applies them, so no secret goes through CI.
- Result (2026-11-05): the CI build works (about 3 minutes, 160 MB compressed) and the image
  boots on the Pi 4 and is reachable over SSH. The minimal base lacked a Wi-Fi country and mDNS
  (both added), Imager's customisation does not apply to a custom image, and a board without a
  password needs a status report on the boot partition (`primum/status.txt`) to be debugged.

**Watch during phase 1**
- Only LEDs, no relays: a released GPIO line may float, so relays wait for the watchdog
  (phase 3) and safe boot levels in `config.txt` (phase 6).
- Cost of the Stop hook: measure it at the end of each block; above ~10 s, limit it to the
  tests of the packages that changed.
- Scope: no sequences, automations or editor here.

## Phase 2 · Project model and `core`

`primum validate <project>` loads an example project (a folder of files), checks it against the
Raspberry Pi 4 board profile and explains typical conflicts clearly, in English or Spanish. No
Pi needed. Not here: running sequences (phase 4), new drivers (phase 3), the UI (phase 5), the
expression language of conditions (phase 4: conditions are stored, not interpreted).

Across the phase: `core` reads no files (it gets a map of path → bytes and returns an immutable
project or `Issue`s); every check is a small pure function returning issues; pins are BCM GPIO
numbers in files (messages also show the physical pin); times are integer milliseconds. One
pull request per block.

**2.1 · Formats and `core` errors** · **done** (decision 0014)
- `schemas/common.schema.json` (`id`, `name`, `description`) and `schemas/project.schema.json`
  (the `project.json` manifest); the subset of JSON Schema formats may use, in
  `schemas/README.md`.
- `tools/gen_schemas.py` (`just gen`, `just gen-check`): `primum_core/generated/schemas.py`
  and `model.py` (frozen dataclasses with a parser each). Our own generator:
  `datamodel-code-generator` keeps mutable lists and loses the JSON names.
- `fastjsonschema` in `core` (`>=2.22.2`), compiled on first use with `fast_fail=False`: every
  structural problem of a file is reported; a stub in `typings/` keeps pyright strict.
- `primum_core.errors`: `CoreErrorCode`, `Issue` (`code`, `params`, `location`, `severity`),
  `Location` (`path`, JSON `pointer`, `file_id` once known). `primum_core.formats.read_manifest`:
  UTF-8 (byte order mark accepted), JSON without repeated keys or `NaN` (`2.0` read as the
  integer it is), schema, dataclass.
- Codes `file.*` and `schema.*` in both catalogs, one per expected type so no message quotes
  JSON Schema's words; the catalog test checks `core`'s codes too.
- The generator compiles every schema (a malformed one fails `just gen-check`) and type-checks
  the code it generates for a fixture that uses every supported keyword.
- Formats are drafts until the first release: `schemaVersion` 1 may change without migrations.

**2.2 · Board profile `rpi4b`** · **done**
- `schemas/board-profile.schema.json` and `boards/rpi4b.json`: the 40 physical pins (GPIO,
  3V3, 5V, GND) with each GPIO's line and pull at power on, buses (I2C1 on 2/3, SPI0, UART0 on
  14/15), PWM channels (12/18 and 13/19, shared), reserved pins (0/1, HAT EEPROM) and the GPIO
  chip **by label** (`pinctrl-bcm2711`, never `/dev/gpiochipN`). `docs/specs/board-profiles.md`.
- `core`: `read_board_profile` checks the rules a schema cannot (`board.*` codes);
  `boards.gpio_lines`.
- Runtime: a copy of the profiles (`tools/gen_assets.py`, which also copies the page's
  assets), `--board` / `PRIMUM_BOARD` (`rpi4b` by default) instead of `--chip`. Both HALs take
  the board: they refuse pins it does not have (`hal.pin_invalid`), so `--simulate` fails where
  the Pi would; the real HAL finds the chip by label and requests each GPIO on its line.

**2.3 · Workspace, file types and `primum validate`** · **done** (`docs/specs/workspace.md`)
- Schemas of `.hw` (boards; elements of a generic type — `digital_output`, `digital_input`,
  `pwm_output`, `i2c_device` — with a pin or a bus and address), `.vars` (constants,
  variables, exports, imports), `.sec` (tracks of clips per element, blocks with arguments,
  parameters), `.evt` (from an element, the phone UI or the API), `.sched` (times and windows),
  `.auto` (`when` events or schedules, `if` stored as text until phase 4, `do` start/stop a
  sequence or set/increment a variable). The generator gained lists of scalar types (a value
  that may be a number, a boolean or a text); absent optional arrays read as `()`.
- `primum_core.workspace.load_workspace`: files by extension (others ignored with a warning),
  then, once every file reads, unique ids, references by id and kind (a track may play an
  element parameter of its own sequence), and fields that depend on the case. Codes
  `project.manifest_missing`, `file.not_in_format`, `id.duplicate`, `ref.unknown`,
  `ref.wrong_kind`, `schema.unexpected_field`.
- `packages/cli` (`primum validate <folder>`): messages and hints from the catalogs (new `cli`
  section), `--lang`, `--json`, `--strict`, exit codes 0/1/2; hidden files and links skipped.
  `tools/gen_assets.py` (was `gen_runtime_assets.py`) also copies the catalogs into it.
- `examples/minimal/`, kept valid by a test.
- From review: a track (and an argument's `element`) may play a parameter of type `element`
  only; an event comes from an input element; extensions match without regard to case; the
  fields of each file are checked even if another file does not read.
- Follow-up: the CLI reads every file of the folder before `core` ignores the ones of no
  project type. Before projects carry audio (phase 6), `core` should take the paths and read
  the contents it needs lazily, so a video left in the folder is not read to be ignored.

**2.4 · Scopes, variables and components** · **done** (`docs/specs/variables-and-scopes.md`)
- `primum_core.scopes`: a `.vars` file defines names for its folder; a file sees its folder's
  and the folders' above; export, and import by the `.vars` id plus the name; no shadowing
  (`name.redefined`, with the path that already defines it, also for parameters and for an
  import of a visible name); `name.unknown`, `name.not_exported`, `name.not_a_variable`,
  `variable.not_numeric`; `name.unused` (warning) unless exported, a setting, or a word of a
  visible condition (text until phase 4).
- Values of the declared type (`value.expected_number|integer|boolean|text`, one code per
  type) for constants, initial values, what automations set or add, and arguments; limits only
  on numeric variables, in order, with the initial value within them
  (`variable.limits_invalid`, `variable.initial_out_of_range`).
- `primum_core.components`: one argument per parameter, of the right shape and type
  (`argument.missing`, `argument.duplicate`, `argument.expected_element`,
  `argument.expected_value`); `sequence.includes_itself` and `sequence.cycle` (with the chain
  of names), one issue per block that closes a loop.
- Tests build projects with `packages/core/tests/project_builder.py` (on pytest's
  `pythonpath`, since `--import-mode=importlib` keeps test modules apart).
- From review: an import may go up (the root imports a scene's counter) and importing a
  definition already visible is redundant, not an error; `name.redefined` names the file that
  defines the name; a stray `variable` on `start_sequence` is reported once; the cycle walk
  keeps its own stack. Follow-ups: limits of an `integer` variable against its type, exported
  names nothing imports, and words inside text literals of conditions (phase 4).

**2.5 · Resources and pin conflicts** · **done** (`docs/specs/board-profiles.md`, resource allocation)
- `primum_core.resources.check_resources(files, profiles)`: `load_workspace` takes the board
  profiles by model (the CLI loads its copy of `boards/`, `primum_cli.boards`). Per board:
  `board.unknown_model`, `pin.not_on_board`, `pin.reserved`, `pin.in_use` (naming the other
  element), `pin.claimed_by_bus` (GPIO 2/3 with an I2C device: devices are placed first),
  `pin.function_unavailable`, `pwm.channel_in_use` (12 and 18), `bus.not_on_board`,
  `bus.not_i2c` (a device on `spi0`), `i2c.address_in_use`. Messages show `GPIO 17 (pin 11)`.
  `pin.not_gpio` dropped: elements name GPIOs, never physical pins, so it cannot happen.
- Follow-up for phase 5: issues of the resource check come board by board, devices first, not
  in file order; the UI sorts what it shows by file and pointer. The CLI loads the profiles on
  every run: cache them when there are many boards.
- `examples/invalid/<code>/`: one project per code; a test checks each gives exactly its code.

**2.6 · Overlapping sequences and closing the phase** · **done** (`docs/specs/workspace.md`,
"Sequences in time")
- `.sec` gains `priority` (0–100, default 0) and `exclusiveGroup` (decision 0006).
- `primum_core.overlaps`: each sequence flattened once (own clips plus included ones at their
  offset, parameters bound to arguments; a walk with its own stack, no recursion).
  `track.clips_overlap` (error, at the later clip or at the block it comes through);
  `sequence.may_overlap` (warning) between sequences that automations start, on one priority,
  not in one exclusive group, touching one element. Zero-length clips overlap nothing.
- `examples/shop-window/`: relay, PWM LED and presence sensor; variables in folders with an
  export and an import; a component; two automations and a schedule; valid without warnings.

**Done when:** example projects validate, and typical conflicts are reported clearly, without the Pi.
Met: `examples/minimal` and `examples/shop-window` validate with `--strict`; each of the nine
projects in `examples/invalid/` reports exactly its conflict, in English or Spanish.

Not in this phase: editing operations and the `.primum` archive (with the UI in phase 5 and the
MCP server in phase 8).

**Left for later phases, found in phase 2**
- Phase 3: the elements' `action` strings (`on`, `fade_in`) are free text until the drivers
  declare their actions; a `.hw` element type maps to a driver.
- Phase 4: the expression language of `if` (today a word in a condition counts as a use of a
  name, even inside a text literal); which board owns a variable; the re-trigger policy of a
  sequence (decision 0006); the engine's real arbitration, which `sequence.may_overlap` only
  approximates; an automation starting a component (it would need arguments). Once drivers
  declare exclusive elements (motors, servos; phase 3), `sequence.may_overlap` on one of them
  becomes an error. What a clip of `durationMs: 0` means: today it overlaps nothing, but with
  "the latest command wins" (decision 0006) an instant `off` inside a 10 s `on` does change the
  element; decide with the meaning of a clip.
- Phase 5: sort issues by file and pointer; lazy reading of a folder before projects carry
  audio; the `.primum` archive and editing operations; sequences the phone UI or the API start
  are not among the ones `sequence.may_overlap` compares.
- Small: limits of an `integer` variable against its type; exported names nothing imports;
  caching board profiles in the CLI once there are many; the flattening of sequences copies the
  clips of each level into the one above (quadratic on a long chain with clips at every link),
  fine today, revisit with the compiler of phase 4.

## Phase 3 · HAL, basic drivers and safety

The runtime drives digital outputs, digital inputs and hardware PWM through drivers with a
declared safe state and limits, and the outputs end in their safe state even when the service
dies at once. Blocks 3.2 and 3.3 need no Pi; 3.1 and 3.4 are checked on `primum-dev` (the LED
on GPIO 17, a button to ground on another GPIO, and an LED on GPIO 18 for PWM once the overlay
is on). Not here: running sequences (phase 4), I2C, LED strips, audio and `config.txt` (phase
6), the new UI (phase 5). One pull request per block.

**3.1 · The whole HAL** · **done** (decision 0015)
- `Hal.claim(Claim(outputs, inputs, pwms))` once per board: one request per GPIO chip, pins
  checked against the profile first (`hal.already_claimed`, `hal.pin_in_use`,
  `hal.pwm_unsupported_pin`, `hal.pwm_channel_in_use`); a failed request is
  `hal.request_failed` naming every GPIO it covered; a PWM output on a GPIO the overlay does not
  route (its line is free) is `hal.pwm_not_routed`.
- Digital inputs: `read()`, pull and debounce from the spec (the kernel's), every change an
  `InputEvent` with the monotonic timestamp (`read_events`, `wait_events`).
- Hardware PWM through sysfs, the controller by device name from the profile (`pwmChip`,
  `pwmChannels[].channel`), levels 0–1, safe state 0 % (`hal.pwm_chip_not_found`,
  `hal.pwm_unavailable`, `hal.duty_out_of_range`).
- The safe state is read back: `hal.safe_state_unverified` for a line that reads otherwise
  (the line itself for GPIO; the controller's setting for PWM).
- The simulated HAL mirrors it (`simulate_input`, `stick`); `hw` tests take optional
  `PRIMUM_HW_INPUT_PIN` and `PRIMUM_HW_PWM_PIN`; `provision.sh` enables `pwm-2chan` (full
  provisioning, not `--app-only`). Checked on `primum-dev`: LED, button and PWM LED.
- Left for 3.3, with the driver limits: `PwmSpec.frequency_hz` is not checked (0 divides by
  zero, a huge value gives a period of 0 ns and a misleading `hal.pwm_unavailable`); a channel
  exported by `SysfsPwmChannel` that then fails to configure stays exported until the next claim.
- From review of 2.6, in passing: `overlaps` names and the note on loops.

**3.2 · Driver manifests and what a clip is**
- `schemas/driver.schema.json` and `drivers/`: one manifest per driver, the element type it
  serves, capabilities (`switch`, `level`, `read`), actions with parameters, configuration,
  platforms, safe state, limits, conflict policy (latest wins / exclusive). Data, like the
  board profiles: `core` gets them from the caller.
- `core` validates clip `action`s against the manifest of the element's type (`action.unknown`,
  `action.param_missing`, `action.param_out_of_range`).
- Decision: what a clip is (duration, an instant command of 0 ms, what happens when it ends);
  `overlaps` adjusted so 0 ms clips count. `sequence.may_overlap` becomes an error on elements
  whose driver is exclusive.

**3.3 · The three drivers**
- `digital_output`, `digital_input` (debounce, pull), `pwm_output`, each implementing its
  manifest on the HAL, with tests against the simulated HAL.
- The `Controller` manages elements through drivers; the API and the page show inputs and PWM
  levels, and set levels.
- Input events without blocking the API's event loop (`control` has no locks): the gpiod
  request exposes its `fd`, so the loop watches it with `add_reader` and calls `read_events`
  when it fires; no thread, no polling. A HAL without inputs registers nothing (`wait_events`
  returns `False` at once there, so a waiting loop would spin).
- An `hw` test with a real edge and no finger: reconfiguring the input's bias from pull-up to
  pull-down (`reconfigure_lines`) flips a line nothing drives, which covers the logical polarity
  and the timestamps of the events; today's `hw` test only reads the idle state.
- The PWM driver compares a read level with tolerance: sysfs holds the duty cycle in whole
  nanoseconds, so `read()` is quantised to the period (`set(1/3)` reads back `0.33333` at 1 kHz).
- Input events lost in a burst: the kernel drops the oldest once its buffer is full (60 unread
  changes gave 32 on the Pi). The input driver decides what to do: detect the gap with the
  event's `line_seqno` and report it, ask for a larger `event_buffer_size`, or both.

**3.4 · Safety**
- Safe state on start, stop and crash: `Type=notify` and a systemd watchdog fed from the
  runtime; `OnFailure=primum-safe.service` drives what the runtime declared in `/data` to its
  safe state when the service does not come back (the 1.4 finding, `StartLimitBurst`): the GPIO
  lines, and the PWM channels too (`duty_cycle` 0, `polarity` normal and `enable` 0 through
  sysfs; seen on the Pi: after `kill -9` a channel stays at 50 % and its pin high, and with an
  inversed polarity a disabled channel holds it high).
- Test mode: manual commands that expire on their own, above sequences and below panic
  (decision 0006).
- `docs/specs/safety.md`, `docs/specs/drivers.md`; on the Pi: `kill -9`, restart, exhausted
  restarts, with the LED as witness.
- A sysfs PWM channel has no owner: the HAL adopts one already exported (what recovers it after
  a crash) and would take it from another program just the same. `check-gpio-users.sh` looks
  at the exported `pwmN` of `/sys/class/pwm` too, and the runtime logs a channel it adopted.

**Done when:** after `kill -9` of the service every output, PWM included, is in its safe state.

Found in 1.4: after `SIGKILL` a line keeps its last value until the service starts again, and
if systemd gives up restarting (`StartLimitBurst`) it stays so. The watchdog and the safe state
on start must cover a service that does not come back.

## Phase 4 · Engine and deployment packages

1. Sequence engine (monotonic clock, components flattened by the compiler).
2. Events (`.evt`), schedules (`.sched`), automations (`.auto`), runtime variables with atomic
   operations and a small, safe expression language for conditions.
3. Arbiter per element: layers by priority, latest command wins, exclusive elements,
   exclusive groups, re-trigger policy, safety on top.
4. Execution trace.
5. Deployment package: build, validate, atomic activation, rollback. Reliable-clock flag.

**Done when:** "presence sensor → 10 s sequence with relay, LED and servo" runs from a deployed
package, shows in the trace and can be rolled back.

## Phase 5 · Local web UI v1

Vue 3 + TypeScript, mobile first, English and Spanish: pairing with PIN, file explorer,
elements with *Test*, simple sequence editor with simulated preview, automations, settings
(exposed variables), daily control, alerts, "controlled by" per element.

## Phase 6 · Hardware manager

Managed block in `config.txt` (I2C, 1-Wire, PWM overlays, I2C speed, `gpio=` safe boot
lines) applied through tryboot with automatic rollback; I2C scan; drivers for MCP23017,
a BME280/VL53L0X sensor, WS2812B strip and audio.

## Phase 7 · Primum OS image

rpi-image-gen config; partitions `boot` · `rootfs A` · `rootfs B` (reserved) · `data`;
read-only root; first boot with its own Wi-Fi and setup wizard; CI publishes `.img.xz`.
Starts from the 1.5 spike (decision 0013): rpi-image-gen on `ubuntu-24.04-arm`, our layers with
overlays, the Wi-Fi country asked at first boot, mDNS, a status report on the boot partition,
and a networking stack chosen for the access point (the minimal base uses iwd + networkd).
`provision.sh` installs `uv` with `curl | sh` from a pinned version but no checksum: fine for the
development Pi, the image must verify what it downloads. The HAL's wait for a freshly exported
PWM channel to become writable counts on the udev rule of Raspberry Pi OS (`99-com.rules`) that
hands `/sys/class/pwm` to the `gpio` group; a plain Debian has none and gives
`hal.pwm_unavailable`, so the image ships that rule or an equivalent, and provisioning checks it.

## Phase 8 · Local MCP server

Tool catalogue on top of the operations (permissions, "needs confirmation"), resources,
prompts, proposals the user accepts in the UI, first evaluation set.

## After version 1

Primum Studio (Tauri) · ESP32 autonomous node and conformance suite · Arduino satellite ·
cloud (accounts, sync, licences, remote MCP) · built-in chat with the user's own key ·
Home Assistant integration over MQTT · A/B system updates.
