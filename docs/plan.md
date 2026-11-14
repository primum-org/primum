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
dies at once. Blocks 3.2, 3.2b and 3.3 need no Pi; 3.1 and 3.4 are checked on `primum-dev` (the LED
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
- Until 3.4, after `kill -9` a PWM output stays at its last level: wire nothing but an LED to
  one. It is the safety gap this block leaves open.
- Left for 3.3, with the driver limits: `PwmSpec.frequency_hz` has no upper limit (under 1 Hz
  it is `hal.pwm_frequency_invalid`; a huge value gives a period of 0 ns and a misleading
  `hal.pwm_unavailable`; a high one leaves few steps of level: at 20 MHz the period is 50 ns and
  `set(0.001)` reads back `0.0` with no error, so the limit is a maximum frequency or a minimum
  resolution), and `InputSpec.debounce_ms` is not checked (a negative value ends as a misleading
  `hal.request_failed`). The manifests of 3.2 set those limits (1–100000 Hz, 0–10000 ms) for
  `core`; the drivers apply them on the board.
- From review of 2.6, in passing: `overlaps` names and the note on loops.

**3.2 · Driver manifests and what a clip is** · **done** (decision 0016, `specs/drivers.md`)
- `schemas/driver.schema.json` and `drivers/`: one manifest per element type, with its
  actions with parameters, the options of an element (`config`), its
  safe state and its conflict policy (latest wins / exclusive). Data, like the board profiles:
  `core` gets them from the caller. Three manifests: `digital_output` (`on`, `off`),
  `pwm_output` (`on`, `off`, `set(level)`, `fade(from, to)`; `frequencyHz`) and `digital_input`
  (no actions; `pull`, `debounceMs`).
- Clips take `arguments` and elements take `config`, both values by name. `core` checks them
  against the manifest of the element's type (`action.*`, `config.*`,
  `track.element_without_actions`, and `track.element_without_driver` for a type with no
  manifest yet); a component, where a block gives it its element.
- What a clip is: it holds its action while it lasts and then releases the element to the layer
  below or its safe state; a clip of 0 ms is an instant command that stands, under the clips
  with a length, until the next instant command of the element in its own sequence or the
  end of that sequence (of its block when included), and counts for overlaps. Two started sequences on
  an element of an exclusive driver are an error (`sequence.exclusive_element_shared`).
- Not here, for the compiler (phase 4): a clip that takes the value of a component's parameter
  or of a variable; the limits the HAL showed (frequency, debounce) are in the
  manifests as provisional values: they belong to the board, and 3.3 moves them to its profile.
- An instant clip that is the last thing of a sequence shows nothing (the sequence ends
  there): a warning, `clip.instant_at_end`, on the sequences automations start, unless it asks
  for the safe state. The sequences the phone UI or the API start join it in phase 5; block
  3.2b completes it.
- A new driver is not yet only a manifest: the element types are a closed `enum` in
  `hardware.schema.json`, and `variants`, `resources` and `references` know each type by name
  (its fields, its resources, whether it is an input). Opening the list needs manifests that
  declare their wiring and whether they are listened to. `activeLow` (a field of the element)
  and `pull` (an option of the driver) are chosen together and should then live together.
- A component nothing includes is not checked: a misspelt action in it passes until a block
  gives its parameter an element. An element parameter that declares the capability it
  expects (`level`, `switch`) would let it be checked on its own; it changes the format of
  sequences, and it is when manifests get their `capabilities`.
- A manifest has no `capabilities` and no `platforms`: the first draft had both, required and
  with values for things that do not exist (`esp32`, `avr`, `color`, `position`), and nothing
  read them. Each comes back with its first reader and the values that exist then:
  `platforms` in 3.3, when a board profile says its platform and `core` can check that the
  driver exists on the element's board; `capabilities` with the parameter above.
- Later, no date: the safe state is per element type. `off` is right for everything there is
  today; an element whose safe rest is another (a work light, a fan) needs it per element.
- For the engine (phase 4): `fade` needs its `from`, so "from where it is" cannot be
  said and a fade that enters over another layer jumps: it needs a parameter that may be left
  out without having a default, a small change of the manifest format, not of the sequences.
- For the UI (phase 5): a problem inside a component is reported at the block that gives it
  its element, without the clip of the component that has it (`FlatClip.clip` is at hand);
  the timeline should show the standing command of an element under its clips; an input is
  set up by picking how it is wired (button to ground, button to 3V3, normally closed switch),
  which fills in `pull` and `activeLow` together.
- Small, older than this block: `atMs` and `durationMs` have no maximum (2^62 ms is accepted).
- Small, a pull request of its own: `core` has six copies of the helper that points inside a
  file (`at`, `_at`), four of them older than this block.
- Small: the sequences are flattened twice, once for the actions and once for the overlaps;
  share it when the compiler (phase 4) needs it too.

**3.2b · What commands an element, and when** · **done** (decision 0017, `specs/workspace.md`)
- `primum_core.commands`: `command_at` says which command is in force on an element at an
  instant, given the sequences that are running and when each started; `timelines_of` prepares
  the sequences of a valid project. One rule: of the commands in force, the highest priority,
  and within it the one that started last (a tie goes to the clip with a length, then to the
  sequence started last); with nothing in force, the safe state. A clip with a length is in
  force for its length; an instant command, until the next one of its element in its own
  sequence or the end of that sequence, the block when it is included.
- A sequence can hold (`whenDone`: `end` or `hold`): it stays as it is in its last instant
  until it is stopped, its instant commands and the clips that end with it, each as it ended.
  "On at dusk, off at 23:00" is `examples/evening-lights`. Ignored when included.
- `track.clips_overlap` is two clips with a length, or two instant commands in one instant: an
  instant command and a clip do not compete. `clip.instant_at_end` covers every sequence, the
  components placed in the middle of another included, spares the sequences that hold,
  reports the sequence that is only an instant `off`, and its hint offers holding.
- A flattened clip knows the sequence it is written in (`FlatClip.scope`, `scope_end`).
- Left for the engine (phase 4): who is running is its caller's, so exclusive groups, the
  re-trigger policy, exclusive drivers and stopping are not in `command_at`; a sequence that
  starts again when it ends (a loop) is a third value of `whenDone`.
- For the engine, about `primum_core.commands` as it is:
  - `command_at` is an oracle for tests, not something to ask on every tick: each call walks
    the clips of the element (0.5 ms on a Pi 4 with 1000 clips per track). The engine keeps
    its own state and must agree with it.
  - `timelines_of` is quadratic in the clips of a track: every instant command walks all the
    clips of its element (8 tracks in each of 4 sequences: 0.1 s with 100 clips per track on
    a Pi 4, 1.5 s with 500, 5 s with 1000). Sort the instant commands by element and scope
    before the engine prepares projects with it.
  - Its public shape, to settle before the engine depends on it: `Timeline.spans` shows the
    private `_Span`, and a running sequence that is not among the timelines is a bare
    `KeyError`.
  - Two sequences that hold, *On* and *Off*, work the first day (*Off* started last, and
    `sequence.may_overlap` says so), but both keep running for ever: whether *On* turns the
    light on again the next day is the re-trigger policy's, or they share an exclusive group.
- A gap in `clip.instant_at_end`, rare: an instant command in the same instant as a clip of
  its element that lasts until the end of the sequence is never seen (the clip wins the tie
  and the sequence ends with it), and is not reported.
- Left for the UI (phase 5): a warning for a sequence that holds and that nothing stops, once
  what the phone and the API can stop is known.
- Not in this block, with 3.3: `core` knows the name of an action, not where it leaves its
  element (below). Holding a clip "as it ended" needs it too.

**3.3 · The three drivers**
- `digital_output`, `digital_input` (debounce, pull), `pwm_output`, each implementing its
  manifest on the HAL, with tests against the simulated HAL.
- The `Controller` manages elements through drivers; the API and the page show inputs and PWM
  levels, and set levels.
- What a board can do is data of its profile, taken from the manufacturer's documentation and
  cited there, never a limit in a driver manifest (a manifest is for every platform): the
  profile gains the limits of its PWM and of its inputs, the manifests keep the option, its
  type and its default, and `core` checks each element against the profile of its board.
  What the sources say for `rpi4b`: the Raspberry Pi kernel clocks the PWM at 50 MHz
  (`assigned-clock-rates` in `bcm283x.dtsi`; mainline says 10 MHz and the `pwm-2chan` overlay
  takes a `clock` parameter, so the profile describes the board with the system Primum
  ships); `pwm-bcm2835` takes a period of 2 clock cycles at least and of 2^32 at most (40 ns
  to about 85 s at 50 MHz, in steps of 20 ns); the BCM2711 peripherals datasheet gives the
  32-bit range and data registers and no frequency limit. So the useful maximum is a choice
  of resolution (steps between 0 and 100 %), derived from the clock. For inputs, the kernel's
  GPIO documentation sets no limit on the debounce time (32 bits of microseconds) and the Pi
  debounces in software: its limit is Primum's own, not a board's.
- An `hw` test on `primum-dev` at both ends of each limit, when the limits move to the board
  profile: a PWM output at its lowest and highest frequency, an input at its longest debounce.
  The provisional 1 Hz to 100 kHz and 0 to 10 s fit what the sources say (at 50 MHz, 1 Hz is
  50 million clock cycles of the 2^32 the driver takes and 100 kHz leaves 500 steps of level;
  the kernel takes a debounce of up to some 71 minutes), which is arithmetic, not a measure.
- Manifests declare the state each action leaves its element in (`on` 100, `off` 0, `set` its
  `level`, `fade` its `to`). A driver needs it anyway to carry out an instant command, which
  is "the state the action ends in". With it `core` warns about the trap of decision 0016, a
  `fade` to 0 in the middle of a sequence that gives the element back to a standing `on`
  because no instant `off` follows it, and `clip.instant_at_end` stops comparing names (an
  instant `set` to 0 at the end is reported today, `off` is not).
- One loader of manifests in `core`, for the CLI and the runtime, that keys each by its own
  `elementType`: today `load_workspace` trusts the key its caller gives, and only the CLI
  checks it.
- A driver hands the HAL every option, taken from the manifest and the element, never the
  HAL's own defaults, which say other things: `InputSpec.pull` is `UP` and the manifest has no
  default, `InputSpec.debounce_ms` is 0 and the manifest says 20. Take the defaults out of
  `InputSpec` and `PwmSpec` so the type checker ties it, not a test. The safe state of the
  manifest (`off`) is tied to the HAL's the same way: one test per driver that its safe-state
  action leaves the simulated HAL where the HAL's own safe state does.
- PWM is not exposed through the API before `primum-safe` covers PWM channels: today the
  `Controller` claims digital outputs only, so the `kill -9` gap of a PWM output cannot be
  reached from the service. Either the PWM part of 3.4 comes first, or 3.3 and 3.4 are merged
  together; decided when 3.3 is planned.
- The API and the page do not show the safe state of a PWM output as *verified* the way a
  digital output's is: its read-back is the controller's setting, not the pin (decision 0015).
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
- Two events of the same kind in a row: with both edges detected the kernel tells rising from
  falling by reading the level after the interrupt, so a very short pulse can give two equal
  events. The input driver takes the state from each event and never assumes they alternate;
  the simulated HAL, which drops a change to the same state, learns to produce that case.

**3.4 · Safety**
- Safe state on start, stop and crash: `Type=notify` and a systemd watchdog fed from the
  runtime; `OnFailure=primum-safe.service` drives what the runtime declared in `/data` to its
  safe state when the service does not come back (the 1.4 finding, `StartLimitBurst`): the GPIO
  lines, and the PWM channels too (`duty_cycle` 0, `polarity` normal and `enable` 0 through
  sysfs; seen on the Pi: after `kill -9` a channel stays at 50 % and its pin high, and with an
  inversed polarity a disabled channel holds it high).
- Test mode: manual commands that expire on their own, above sequences and below panic
  (decision 0006).
- `docs/specs/safety.md`; on the Pi: `kill -9`, restart, exhausted
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
