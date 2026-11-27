# Plan

Each phase ends with something working on a real Raspberry Pi 4B. Update the status column
when a phase starts or finishes.

| Phase | Goal | Status |
|---|---|---|
| 0 | Repository skeleton: structure, docs, rules, tooling, CI | Done |
| 1 | End-to-end skeleton: toggle an LED from a phone | Done |
| 2 | Project model and `core`: workspace of files, board profile, pin conflicts, validation | Done |
| 3 | HAL, basic drivers and safety | Done |
| 4 | Engine: sequences, automations, events, variables, arbitration, deployment packages | Built; its "done when" still to be run on the Pi |
| 5 | Local web UI v1 | In progress |
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
  (replaced on 2026-11-27 by the brand "Plano", decision 0036)
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
- Phase 4: the expression language of `if` (done in 4.4a); which board owns a variable; the
  re-trigger policy of a sequence (decision 0006); the engine's real arbitration, which
  `sequence.may_overlap` only approximates; an automation starting a component (it would need arguments). Once drivers
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
dies at once. Blocks 3.2, 3.2b and 3.3a need no Pi; 3.1, 3.3b and 3.4 are checked on
`primum-dev` (the LED
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
- Done in 3.3b, with the driver limits: `PwmSpec.frequency_hz` had no upper limit (under 1 Hz
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
  or of a variable; the limits the HAL showed (frequency, debounce) were in the
  manifests as provisional values until 3.3a gave each its place (decision 0018).
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
  `platforms` in 3.3b, when a board profile says its platform and `core` can check that the
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
- Small: the sequences are flattened twice, once for the actions and once for the overlaps
  (three times since 3.3a); share it when the compiler (phase 4) needs it too.

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
  reports the sequence that is only an instant `off`, and its hint offers holding; at the
  block that gives a component its element it is `block.instant_at_end`, whose hint does
  not. Including a sequence that holds is `block.hold_ignored`: it holds only when started on
  its own.
- A flattened clip knows the sequence it is written in (`FlatClip.scope`, `scope_end`).
- Left for the engine (phase 4): who is running is its caller's, so exclusive groups, the
  re-trigger policy, exclusive drivers and stopping are not in `command_at`; a sequence that
  starts again when it ends (a loop) is a third value of `whenDone`.
- For the engine, about `primum_core.commands`: `command_at` is an oracle for tests, not
  something to ask on every tick; each call walks the commands of the element (0.28 ms on a
  Pi 4 with 1000 clips per track). The engine keeps its own state and must agree with it.
  `timelines_of` sorts the instant commands of each element once (it walked all the clips of
  the element for each, 13 s on a Pi 4 for 4 sequences of 8 tracks of 1000 instant clips).
- Gaps in `clip.instant_at_end` and `block.hold_ignored`, rare: things not reported. (Three
  false warnings were found in review and fixed, all at the end of a show that holds: a
  sequence that is only an instant `on`, a sequence that holds, and a sequence that holds
  with nothing but a block. `clip.instant_at_end` is now checked against `command_at` on
  random projects; `block.hold_ignored` has no such test yet, and should before the engine
  relies on it.) An instant clip, or a block, that some sequence that holds keeps is not
  reported for the other places where its sequence runs and it is not kept: a check of one
  sequence does not know every way it is used.
  An instant command is never seen when something of its element covers it from its instant
  to the end of the sequence: a clip that lasts until the end, several clips one after another
  until the end, or a clip that comes through a block (each wins the tie, and the sequence
  ends with the last). And a component that is only an instant `off`, placed in the middle of
  a show over a standing `on`, leaves the light on and is not reported: the safe state is
  spared unless the sequence lasts no time, which is only looked at for a sequence's own
  clips, not for those a block brings.
- Left for the UI (phase 5): a warning for a sequence that holds and that nothing stops, once
  what the phone and the API can stop is known.
- Not in this block, done in 3.3a: `core` knew the name of an action, not where it leaves its
  element. Holding a clip "as it ended" (phase 4) needs it too.

**3.3a · What a board limits, and where an action ends** · **done** (decision 0018,
`specs/board-profiles.md`, `specs/drivers.md`)
- What a board can do is data of its profile, taken from the manufacturer's documentation and
  cited there: a profile has `limits` (element type, option, minimum, maximum, sources, a
  note), and `core` checks each element against those of its board
  (`primum_core.board_limits`, `config.out_of_board_range`), its driver's default included.
  `rpi4b` takes a PWM frequency of 1 Hz to 100 kHz: the Raspberry Pi kernel clocks the PWM at
  50 MHz and `pwm-bcm2835` takes a period of 2 to 2^32 cycles, so the maximum is a choice of
  resolution (500 steps of level). The manifest of `pwm_output` keeps the option, its type
  and its default. The debounce time stays in the manifest of `digital_input`, 0 to 10 s: no
  board limits it, so it is Primum's own.
- Manifests declare the state each action leaves its element in (`endState`: `on` 100, `off`
  0, `set` its `level`, `fade` its `to`) and, for an action that moves it, where it starts
  (`startState`: `fade` its `from`). With it `clip.instant_at_end` compares states, not names
  (an instant `set` to 0 may end a sequence, as `off` may), and `core` warns about the trap
  of decision 0017: a clip that moves its element to rest and then gives it back to an
  earlier instant command that asks for more (`clip.returns_to_instant`, checked against a
  rule written apart on random sequences).
- One loader of manifests in `core`, `read_drivers`, for the CLI and the runtime: each
  manifest by its own `elementType`, two of one type refused.
- Not reported by `clip.returns_to_instant`: a fade in an included sequence that names the
  element itself, under a standing `on` of the sequence that includes it (a check of one
  sequence does not know every way it is used); a fade to 0 with nothing standing, which
  goes to rest anyway; an instant command inside a fade, which cuts it (a warning of its
  own, if people fall into it); and across sequences (a fade in one under a held `on` of another: the
  cases of phase 4).
- The frequency of a PWM output has no limit but its board's, so a profile that forgets it,
  or misspells its type or option, would let any frequency through. Two tests on the shipped
  files hold it: every limit names a numeric option a shipped driver has, and every profile
  with PWM channels limits `pwm_output.frequencyHz`. `core` itself does not check it yet (3.3b).
- The profile cites the kernel branch `primum-dev` runs (`rpi-6.18.y`): cite the one Primum
  OS ships when there is one (phase 7).
- The limits are arithmetic on the sources, not a measure: the `hw` test at both ends is in
  3.3b.
- Small: the sequences are now flattened three times (actions, overlaps, states).

**3.3b · The three drivers** · **done** (decision 0019, `specs/drivers.md`)
- `primum_runtime.drivers`: `digital_output`, `digital_input` and `pwm_output`, each made from
  its element, its manifest and the limits of its board, with tests against the simulated
  HAL. An output is commanded with the actions of its manifest, as an instant command: it
  goes to the state the action ends in and is read back (`element.level_not_reached`; a PWM
  level within one step of its period, since sysfs holds whole nanoseconds, which the
  simulated HAL does too). An output that does not follow reports what its hardware reads from then
  on, until a command is followed again.
- The drivers enforce the limits again: an option or an argument outside its manifest's
  limits or its board's is refused before anything is claimed (`element.value_*`), and so
  is a number that neither limits (`element.value_unlimited`), as in `core`. The HAL
  refuses a PWM frequency outside what the board takes (`BoardGpio.pwm_frequency_hz`, from
  the profile), which also ends the misleading errors a huge frequency gave.
- `core` fails closed: a numeric option that neither its driver nor its board limits is
  `config.unlimited`, so a profile that forgets the frequency of its PWM, or misspells it, no
  longer lets any value through.
- `InputSpec` and `PwmSpec` have no defaults: a driver hands the HAL every option, from the
  manifest and the element, and the type checker sees to it. One test per output driver ties
  the safe state of its manifest to the HAL's.
- The `Controller` manages elements through their drivers and claims them all at once; its
  state has every output (with its level) and every input. The service still takes its
  elements from options: the LED, and now an optional input (`--input-pin`, `--input-pull`,
  with no default pull). The API's state and the page show the inputs.
- Input events without blocking the event loop: the HAL gives a descriptor (`events_fd`, the
  gpiod request's; a pipe in the simulated HAL), the API watches it with `add_reader` and the
  controller reads the events when it fires. Without inputs nothing is watched.
- Lost events: the request asks the kernel for a buffer of 1024 events, each event carries its
  line's sequence number, and the input driver counts and logs the gaps. The state stays
  right, since every event carries it. Two events of the same kind in a row do not flip it;
  the simulated HAL can produce both cases (`simulate_event`, `lose_events`).
- `hw` tests (`test_drivers_hw.py`), written without access to `primum-dev` and run there
  afterwards, as its owner reports (they passed): a digital output read back, a PWM output at 1 Hz and at 100 kHz,
  a real edge with no finger (the input's pull changed from up to down) with its polarity,
  its time and its sequence number, and an input with a debounce of 10 s.
- PWM was not offered by the service until 3.4b: the drivers and the `Controller` handle PWM outputs
  (tested against the simulated HAL and by the `hw` tests), but the options of the service
  cannot ask for one, so the `kill -9` gap of a PWM channel cannot be reached from it. With
  3.4, when `primum-safe` covers PWM channels: the option, the level in the API's state and
  in the page, and setting a level. Then the API and the page must not show the safe state
  of a PWM output as *verified* the way a digital output's is: its read-back is the
  controller's setting, not the pin (decision 0015).
- `platforms` does not come back yet: there is one platform, so a field for it would have one
  value and a check that cannot fail. With the second platform (ESP32): a board profile says
  its platform, a manifest the platforms that implement it, and `core` checks that the driver
  exists on the element's board. Until then the runtime refuses a type it has no driver for
  (`element.type_unsupported`).
- A limit of a profile that names an option no driver has is still only caught by the test
  on the shipped files, unless the option it meant is left unlimited (`config.unlimited`).
- Lost input events are logged and counted by the driver, not shown in the API or the page;
  when events start automations (phase 4), a loss is something to tell the user.
- For 3.4, when the API takes commands with arguments: `element.value_*` and
  `element.action_unknown` are the caller's mistakes and should be 4xx; today every
  `element.*` is a 500, and only `element.level_not_reached` can be reached from the API.
- If reading the inputs fails, the API stops watching them (the descriptor would stay
  readable and spin the loop) and logs it; the inputs keep their last state and nothing tells
  the user. With the watchdog of 3.4, decide whether that should restart the service.
- The service's input is not in `image/provision.sh`: to try it on the Pi, add
  `PRIMUM_INPUT_PIN` and `PRIMUM_INPUT_PULL` to `/etc/primum/runtime.env`.

**3.4a · Safe state after the process dies** · **done** (decision 0020, `specs/safety.md`)
- The runtime declares what it claims in its data directory before claiming it
  (`/data/claimed.json`, `--data-dir`), and removes the declaration after a clean stop, or
  when the claim fails.
- `primum-safe`, a second command of the runtime: it claims what was declared with the same
  HAL and closes it, which starts every output in its safe state, reads it back and releases
  it. systemd runs it after every stop of the service (`ExecStopPost=`), before any restart,
  not only when it gives up (the plan said `OnFailure=`), and before every start
  (`ExecStartPre=`). Nothing declared, it does nothing; a declaration it cannot read is an
  error and nothing is touched.
- The watchdog: `Type=notify`, `WatchdogSec=10`, and the runtime tells systemd it is ready and
  then, from the event loop, that it is alive.
- The HAL logs a PWM channel it adopted.
- Seen on `primum-dev` with the first version: uvicorn's lifespan and `Type=notify` agree on
  "ready", `ExecStopPost=` runs after the watchdog, `primum-safe` takes 0.34 s. Found there
  and fixed since: an output could stay on for good when `primum-safe` did not finish and
  the configuration changed pins, because the start replaced the declaration without making
  it safe (now `ExecStartPre=`); `systemctl kill` without `--kill-whom=main` kills
  `primum-safe` too, so the LED stays on until the restart (the spec says so); systemd never
  gives up restarting with these timings; a claim that failed left a declaration that made
  `primum-safe` log an error at every stop.
- Run on the board afterwards, as its owner reports: the procedure of `specs/safety.md` with
  those fixes, and the `hw` tests of `test_safe_hw.py` (a digital and a PWM output left on by
  a killed process). All passed.
- A start blocked by a declaration that cannot be made safe (an output stuck on, a file that
  cannot be read) needs a person: the service does not start, so the page cannot say why;
  only the journal does. Showing it is the hardware manager's or the UI's, later.
- If reading the inputs fails, the API still only stops watching them: whether that should
  end the service, now that a watchdog restarts it, is open.

**3.4b · PWM in the service** · **done** (decision 0021)
- The service can drive one PWM output, named `dimmer`: `--pwm-pin` and `--pwm-frequency-hz`
  (its driver's default if not given), or `PRIMUM_PWM_PIN` and `PRIMUM_PWM_FREQUENCY_HZ`. It
  is declared for `primum-safe` like the LED.
- The API asks an output for an action of its driver, with its arguments by name
  (`{"action": "set", "arguments": {"level": 40}}`); `{"on": true}` is gone. Each output of
  the state has its `level` and the `actions` it can be asked for.
- What an output cannot do or take is the caller's mistake: `element.action_unknown` and
  `element.value_unknown`, `_missing`, `_invalid` and `_out_of_range` are 422.
- The page shows a slider for an output that can be `set`; the level is asked for once, on
  letting go (of the pointer, of a held key, of the slider), and a state that arrives does
  not move a slider that is held. Tried in a browser, by hand of a script, not by a test of
  the repository: the page's script has none but its catalogs'.
- A PWM output reports the level its controller holds, in whole nanoseconds of the period:
  a level under one step is 0, not "on".
- `check-gpio-users.sh --pwm` refuses a board where a PWM channel is already exported; the
  unit runs it after `primum-safe`, which unexports what a crash of Primum left, so one still
  exported is someone else's. Provisioning runs it without `--pwm`: the running service
  holds its own channel.
- The page shows no output as *verified*, digital or PWM, so there is nothing to tell apart
  yet. When the UI shows a safe state as checked (phase 5), a PWM output's must not count:
  its read-back is the controller's setting, not the pin (decision 0015).
- `fade` can be asked through the API and jumps to its `to`: fades in time are the engine's
  (phase 4).
- Not in `image/provision.sh`: to try the PWM output on the Pi, add `PRIMUM_PWM_PIN=18` to
  `/etc/primum/runtime.env` (the overlay routes channels to GPIO 18 and 19).
- Tried here against the simulated service only, the page included. The PWM output of the
  service was tried on `primum-dev` afterwards, as its owner reports: it passed.

**3.4c · Test mode** · **done** (decision 0022, `specs/safety.md`)
- A command with a duration is a test: it expires on its own and its output goes to rest.
  From 1 s to 5 min (`test.duration_out_of_range`); a command without a duration stays, as
  before. Panic ends every test.
- The `Controller` keeps the deadlines on a monotonic clock it is given; the API arms one
  timer of the event loop for the next one (`api/expiry.py`). The state says how long each
  test has left, and the page has a *Test* button per output (on for 10 s) with a countdown.
- An output that cannot rest when its test expires does not stop the others, whatever it
  raises; it is tried again every 5 s and its state says so (`restFailed`).
- Tried against the simulated service in a browser: the button, the countdown, a test of one
  second expiring by the service's own timer, the switch ending a test, panic. And on
  `primum-dev` by its owner, with the LED and the PWM output: tests expiring at their time
  (2021 ms for one of 2 s), two at once, panic, and `kill -9` under a test (off in 602 ms by
  `primum-safe`), and `restFailed` with its retries, by taking the write permission of the
  PWM's `duty_cycle` away. Found there and fixed: a test whose read-back failed with an
  error of the hardware stayed on with no deadline; and a panic that failed on an output
  being tried again dropped the retries and left it on. The page was not opened on the board.
- No arbiter: with no sequences, "returns to the layer below" (decision 0006) is "goes to
  rest". For the engine (phase 4): expiry returns the output to what the sequences say, and
  a command without a duration becomes manual control, a layer the arbiter must place too.
- Found while trying it: the page showed the heading of the inputs with no inputs, since
  3.3b (a `display` that overrode `hidden`). Fixed here.

**Done when:** after `kill -9` of the service every output, PWM included, is in its safe state.
Met, on `primum-dev`.

Found in 1.4: after `SIGKILL` a line keeps its last value until the service starts again, and
if systemd gives up restarting (`StartLimitBurst`) it stays so. The watchdog and the safe state
on start must cover a service that does not come back.

## Phase 4 · Engine and deployment packages

The runtime runs a project: sequences in time, started by events and schedules, arbitrated
per element, from a deployment package that can be rolled back. One pull request per block;
4.1 and 4.2 need no Pi.

**4.1 · Which sequences are running** · **done** (decision 0023, `specs/engine-semantics.md`)
- The three cases the plan kept for this, decided and held by tests against `command_at`:
  *On* and *Off* that hold, each started by its automation, work day after day because
  starting a running sequence restarts it (it counts as started last); a sequence can ask to
  ignore that (`whenStartedAgain`), and a test keeps why that is not the default. Starting a
  sequence stops the others of its exclusive group, so a fade out in the group of *On*
  leaves the lamp off. Nothing is remembered across a restart: a schedule's window starts
  its automations when it opens and when the engine starts inside it, a time is lost if the
  board was off.
- `primum_core.runs`: `start`, `stop` and `still_running` keep the list of running sequences
  that `command_at` reads; a `Timeline` carries when its sequence ends, its group and whether
  it restarts.
- `examples/evening-lights` starts its lamp from a window.
- Queueing (decision 0006's third policy) is not built: nothing asks for it.
- Left for 4.3: exclusive elements and what priority does between sequences that wait or
  preempt. For 4.4: windows are only decided here (a clock that becomes reliable late,
  windows across midnight, once per window). Not warned about: a sequence that ignores being
  started again, holds and shares an element with another on its priority.

**4.2 · Deployment package and compiler** · **done** (decision 0024,
`specs/deployment-package.md`)
- `schemas/package.schema.json`: one JSON file for one board, with its own hash (sha256 of
  the rest in canonical form). Elements with every option of their driver, variables,
  sequences as commands (a clip after the rule of decision 0017: when it starts, how long
  its action lasts, until when it is in force), events, schedules and automations by id.
- `primum_core.compiler.compile_package` builds it from a valid project; `primum build
  <folder>` writes it; `primum_core.package.read_package` reads one and checks its hash. A
  project with no board or with several does not compile (`package.no_board`,
  `package.several_boards`).
- A randomized test holds a reader of the package to `command_at`, with two sequences
  running and priorities: the engine needs nothing but the package.
- An argument of a clip or of a block is a value or a name (`valueOf`): a constant is put in
  place, a component's parameter is what its block gives (passed on through components), a
  variable stays a reference and must be limited within the parameter's limits.
  `examples/shop-window` fades its LED up to `brightness`.
- A driver's parameter may be `optional`; `fade` leaves its `from` out to start where the
  element is. An automation cannot start a component (`automation.starts_component`).
- Found by its own tests: a whole number written `80.0` hashed differently from `80`, so a
  package with a limited variable did not read back.
- From review: an automation that sets a variable outside its limits is refused
  (`variable.set_out_of_range`); reading a package also checks that it holds together (ids,
  references, the fields of each case), since a right hash says nothing of a package built
  wrong; the canonical form is RFC 8785's, where Python's own wrote `1e-05` for JavaScript's
  `0.00001`; `primum build .` no longer makes its package a file of the project. A second
  round: a surrogate escape without its pair (`"\ud83d"`) validated and then crashed `build`
  and `read_package` with a traceback, so any file with one is refused when decoded
  (`file.invalid_text`); `check_package` also holds a package's variables to what a
  project's are held to (limits, initial value, values set, increments) and refuses an
  argument or an option given twice and a command outside the time of its sequence; keys
  are sorted by UTF-16 units; a `Workspace` keeps the drivers it was checked against, so
  `compile_package` cannot be given others; a limit on one side alone limits.
- Left for 4.3: when the engine reads the variable of an argument (once when the command
  starts, or following it); where the element "is" for a `fade` without `from`; **holding
  every assignment of a variable to its limits** (clamp or refuse), which the limits check
  of a clip's argument counts on; **checking a package against the drivers and the board
  when loading it** (actions, arguments, options, pins, and that a variable read for a parameter is of its type
  and limited within its limits), which `read_package` cannot: only a manifest says what a
  parameter takes. For 4.4: an
  automation's `if` travels as text with its names unresolved, and the constants it names are
  not in the package. Sequences are still flattened once per check that needs them (three
  of them, and the compiler): fine at today's sizes. `end_level` does not look through a
  `valueOf`, so `clip.returns_to_instant` does not see a constant or a parameter that is 0.
  No example in `examples/invalid/` for the new codes.

**4.3a · The service runs a package** · **done** (decision 0025,
`specs/deployment-package.md`)
- `primum-runtime --package <file>` (`PRIMUM_PACKAGE`): the elements and the board are the
  package's. The options of elements (`--pin` and the rest) stay, for one or the other, until
  4.5.
- `primum_runtime.package.load_package` reads the package with `core` and checks it against
  the runtime's drivers and the board's profile before anything is claimed: the board, each
  element's type and options, each command's action and arguments, and that a variable read
  for a parameter can only hold what it takes. One that fails is refused whole and the
  service does not start. Shared or missing pins are refused by the HAL's claim.
- Elements are asked for by id (`PUT /api/outputs/{id}`; the state gives `id` and `name`);
  the page shows the name and drops the rows of elements that are gone. `core`'s
  `check_package` also checks that an element is wired as its type is.
- The service starts no sequence yet: commands, test mode and panic, as before.
- Tried here against the simulated HAL, the page in a browser by a script and not by a test
  of the repository.
- Tried on `primum-dev` by its owner, who reports it, with the branch installed by `just
  pi-sync` and packages built from `examples/shop-window`. With options, as before: it
  starts, and the state gains `id` (`led`, `dimmer`). With a package: it starts, logs the
  hash and the project, and gives each element its `id` and `name`. The relay moved to GPIO
  17 goes on and off by id, a test of 1.5 s expires on its own, and by name it is a 404.
  Active low, with the package as it is (the relay on GPIO 27): the pin rests high, goes low
  with `on` and back high when the service stops. PWM: `set` 40 on GPIO 18 gives the period
  of 500 Hz the package asks for; sampling it gave 35/100 high, coarser than expected, which
  with nothing wired cannot be told from sampling noise. The input on GPIO 22 changes
  `active` when its pull changes. Panic leaves both pins at 0, and after `kill -9` with the
  relay on and the LED at 70 % `primum-safe` leaves them at 0. Refused, none starting and
  the journal giving the code with the names: an altered hash, two elements on one pin, an
  action the driver does not have, a package next to `PRIMUM_PIN`. The page was not opened
  on the board. `image/README.md` says how to run a package there.
- Found there, measured on GPIO 19 with nothing wired: a `pwm_output` with `activeLow` was
  accepted by `validate`, written by `build`, accepted by the service, and not carried out:
  the pin rested low, went high with `set` 100, low with `off` and low after the service
  stopped. A load wired active low would rest fully on, in panic and in the safe state too,
  with no warning. The options never gave the dimmer an `activeLow`; the package is the
  first way it could arrive. Refused now in a project and in a package
  (`schema.unexpected_field`) and by the driver itself (`element.active_low_unsupported`),
  until the HAL can invert a channel (sysfs has `polarity`): with the drivers of phase 6.
- Found there: a package with its sensor on GPIO 0 (reserved: the EEPROM of a HAT) started
  and claimed the line. The spec said the HAL refuses reserved pins, and nobody in the
  runtime read them; `--pin 0` had the same hole. The wiring of a package's elements, and of
  those told of by options, is checked by `core`'s rules for a project
  (`element.wiring_refused`, with `core`'s code), which also replaces the check of two
  elements on one pin. Every problem of a package is logged, not only the first; errors
  about its elements carry their id.
- Found there: when it is the HAL that refuses (two pins of one PWM channel), the process
  exited with uvicorn's 3 and not with 1 as the spec said. It is 1 now, for every refusal.
- From review: `--pin 0` next to a package passed for "not given" (0 equals `False` in
  Python); two elements on one pin are refused here, naming both, instead of by the HAL with
  the pin alone; a variable read for a number that nothing limits is refused as a written
  value is; the page shows the new name of an element that keeps its id.
- That an event's element is an input is checked since 4.4b. A service that refuses its package
  says why only in the journal.
- For 4.5, seen by the reviewer on a running unit: a package that is refused leaves systemd
  restarting the service for ever (`Restart=on-failure`, `RestartSec=2`), the same error at
  every turn; a bad configuration already did. An exit status of its own for "cannot run
  this" and `RestartPreventExitStatus=` in the unit would stop it; with activation, a
  refused package should never become the one that runs. And what the HAL refuses at the
  claim reaches the journal as a traceback of uvicorn's, some 25 lines for one fact. Seen
  on the board too: the unit stays `activating`, the same error at every turn.

**4.3b · Engine and arbiter** · **code done; not tried on `primum-dev`** (decision 0026,
`specs/engine-semantics.md`)
- `primum_runtime.engine`: which sequences of the package run (restart, ignore, exclusive
  groups, ending with the last clip) and what each element is asked, with no hardware and no
  clock. A test holds it to `command_at` and `primum_core.runs` on 400 random projects (267
  of them valid) with random starts and stops.
- The controller arbitrates each output: panic, then a person (a command without a duration
  is manual control until released; with one, a test), then the sequences, then rest. A
  test that expires gives the output back to the sequences. Panic stops every sequence.
- One timer for the next thing due; an output is written only when what it should be at
  changes; one that cannot be taken there is tried again every 5 s and does not stop the
  rest.
- `POST /api/sequences/{id}/start` and `/stop`, `DELETE /api/outputs/{id}`; the state gives
  the sequences and who commands each output. The page lists the sequences with *Start* and
  *Stop*, says who commands an output and has a *Release* for one held by hand.
- A `fade` still jumps to its end and a variable is read at its initial value: 4.3c.
- Tried here on the simulated HAL with a clock moved by hand, one test with the real timer
  of the service (a sequence of two seconds), and the page in a browser by a script, not by
  a test of the repository. On the board: nothing was run. To try there: the real times of
  a sequence, panic and `kill -9` in the middle of one, a held sequence across a restart.
- Open: a manual command that fails is not held, and its output goes back to what the
  layers say only the next time the controller has something to do. The page's text for
  `restFailed` still speaks of a test. Exclusive elements wait for a driver that is one.
  The randomized test for `block.hold_ignored` is still to write.

**4.3c · Fades and variables** · **code done; not tried on `primum-dev`** (decision 0027,
`specs/engine-semantics.md`)
- The engine's commands are indexed. `Engine.asked` walked every command of every running
  sequence, and the controller calls it for each output twice per change, besides
  `next_change_ms`: measured on the Pi 4 by its owner, with an equivalent loop over the
  engine, 7 ms per change for 8 outputs × 100 clips, 135 ms for 16 × 500 and 539 ms for 16 ×
  2000, all on the event loop, panic included. What a sequence asks of each element is now
  worked out when the package is loaded (a sweep with a heap), and asking is a search. On
  the machine it was written on, the same loop: 3.1 ms → 0.05 ms, 59 ms → 0.12 ms, 149 ms →
  0.10 ms per change; the largest package loads in 58 ms. Not measured on the Pi.
- A `fade` moves its output in a straight line over its clip, worked out from the clock,
  written every 20 ms while a sequence moves something and not otherwise. Listeners are told
  four times a second during a fade. Without a `from` it starts from the level the output
  has when the command first commands it, and goes on unseen under a person's hand.
- Variables: at their initial values when the service starts, in the state, set with `PUT
  /api/variables/{id}`. A value of another type or outside the variable's limits is refused
  and changes nothing, which is what the limits check of a clip's argument counted on
  (decision 0024). An argument reads its variable when its command first commands its
  output and keeps the value while the command lasts.
- Tried here on the simulated HAL with a clock moved by hand, and once with the real timer
  of a simulated service running `examples/shop-window`: the LED rose from 0 to `brightness`
  (set to 60) between 0.5 s and 2 s and fell back to 0 by 3.5 s, sampled over the API
  (after the fix below: it reaches 60.0 at 2.006 s; before it, the "59–60" first written
  here was the fault showing). On
  the board: nothing was run. To see there: whether 50 steps a second look smooth on a real
  LED, what a step costs (each is a write and a read-back through sysfs), and the cost per
  change after indexing.
- From review, reproduced there with the simulated service and its real timer: `NaN` set to
  a variable passed its limits (it is neither under a minimum nor over a maximum), and every
  command that then read it failed outside the `try` that protects the other outputs: the
  error left `expire` and `next_expiry_s`, the timer was not armed again, a test of another
  output never expired and could not be released. A value that is no number is refused
  (`Infinity` was refused before, with a 500: its own value could not be written in the
  answer); what cannot be worked out for one output is contained to it; and a wake that
  fails, which is not meant to happen, is tried again a second later instead of ending the
  timer.
- From review, measured by the reviewer: a fade that ends where a fade without `from`
  starts never reached its top, since the second started from the last step written of the
  first, and at the instant of the change the engine already asks for the new clip. Up from
  0 to 100 and straight down: 80 % with 100 ms a side and exact steps, 75 % with every step
  5 ms late, 98 % with a second a side, simulated; 88–89 % on the Pi, three times. The start
  is now where the command of a sequence that had the output had it at that instant by its
  own time. The Pi was not tried again after the fix. That fix took "that instant" to be
  when the new command started, which is wrong for one that starts under a higher priority
  and gets the output later: with a fade up over 10 s on priority 5 and a fade to 0 over 20 s
  started a second in, the lamp jumped from 99.8 % to 5.5 % at 10 s instead of going on from
  100 (55 %), as the reviewer found on the simulated HAL. It is the instant the command
  before hands the output over.
- From review, seen by the reviewer on the simulated service with its real timer and on
  `primum-dev`, the same on both: the next step of a fade was due "now + 20 ms", asked at
  every change of state, and every change arms the timer again, so each notification put
  the step off another 20 ms. With a fade from 0 to 100 in 10 s and `PUT`s of a variable or
  of another output one after another, the lamp was written once in 3 s instead of 150
  times, and jumped 30 points when they stopped; `GET /api/status` did not do it (141 of
  150). Inputs and automations (4.4) will notify too, and one every 20 ms would stop a fade
  altogether. The step is due 20 ms after the outputs were last settled, absolute like every
  other deadline. After the fix, on the simulated service with the real timer: 1746 `PUT`s
  in 3 s, 145 distinct levels seen, never more than 0.84 points off the fade's line. Not
  tried again on the Pi.
- Left for 4.4: variables marked `persistent` are not kept across a restart; nothing but
  the API sets a variable. A command that starts under a higher priority reads its
  variables, and takes the start of its fade, when it gets its output, not when it starts.
  The page shows no variables (settings are the UI's, phase 5).

**4.4 · Events, schedules, automations and variables**
- `.evt` from inputs (lost input events are told to the user), `.sched` times and windows
  with the reliable-clock flag, `.auto` with the expression language of `if`
  (`specs/expressions.md`, `specs/events.md`), runtime variables with atomic operations.
  In four blocks: 4.4a expressions, 4.4b events and automations, 4.4c schedules and the
  reliable clock, 4.4d persistent variables.
- **4.4a · Expressions: done** (`core` only, nothing to try on a board). The language of
  `if` (decision 0028, `specs/expressions.md`): `and`/`or`/`not`, comparisons, arithmetic,
  the four types, checked by `primum validate` with the names the automation sees. `primum
  build` compiles a condition to a program without jumps (constants inlined, variables by
  id) and reading a package checks it. `evaluate` exists and is tested (against Python's
  own evaluation of 3000 random conditions, among others) but nothing in the runtime calls
  it yet: that is 4.4b, with what a condition that fails to evaluate does (it does not
  hold, and it is told). Numbers are doubles when evaluating and every number of a
  condition must be below 2^53: a rule on the value, for runtimes that are not Python.
  Windows of time are not in the language: a field of the automation, in 4.4c. Not done:
  a variable whose limits allow 2^53 or more is not warned about when a condition reads it.
- **4.4b · Events and automations: code done; tried in part on `primum-dev` by its owner**
  (see below what; decision 0029,
  `specs/events.md`). An input that turns on or off, or an event fired through the API
  (`POST /api/events/{id}/fire`, only `ui` and `api` events), makes the automations of the
  package act: conditions worked out first, all on the same values, then actions in the
  order of the package. An increment stays at the limit it would pass. A condition that
  fails does not hold and an action that fails does not stop the rest; both are logged and
  stay in the automation's state. Panic ignores events and keeps none. Drivers declare what
  their element tells (`triggers`); an event that waits for anything else is refused by
  `primum validate` and by the runtime. The state has `events`, `automations` and
  `lostEvents` on each input.
  - First commit: 300 random runs of the controller against a simple model of its layers,
    woken only when `next_expiry_s` says. It found nothing; three faults put in on purpose
    were caught.
  - Tried only on the simulated HAL, a real service included (the line of the button
    changes, the loop reads it, the LED goes on). On a Pi: a real button or sensor, its
    bounce with `debounceMs`, and a burst that loses events.
  - On the Pi, by its owner: no change could be made to be lost. With `debounceMs` 0 and
    the service stopped with `SIGSTOP`, 300 changes all arrived when it went on,
    `lostEvents` at 0, each dealt with at that same instant. So losing events is checked
    only on the simulated HAL.
  - Also seen there by its owner: a counter incremented to its maximum became `3.0`, not
    `3` (the limits of a package are written with decimals, and the limit itself was
    returned). Fixed: an increment gives a value of the variable's type. Deduced from the
    code and not run: such a value would have been refused by a command reading it for an
    integer parameter.
  - Debounce needed nothing new: it is the `debounceMs` of the input's driver, in the
    kernel, since phase 3.
  - Left out: the page shows neither events nor automations; an automation cannot be
    enabled or disabled while the package runs; nothing is traced beyond the log (4.5).

- **4.4c · Schedules and the trusted clock: code done; seen in part on `primum-dev` by
  its owner, before the fixes listed below**
  (decision 0030, `specs/events.md`). A time of day and a window that opens start their
  automations; so does a window that is open when the service starts or when the time
  first comes to be known. Times are in the project's time zone (`timeZone` in
  `project.json`, required with schedules). The time is known once systemd-timesyncd has
  set the clock since boot, or with `--trust-clock`; until then nothing happens. The
  runtime looks as each minute turns and asks `core` what happened since
  (`primum_core.schedules`). A time in a gap longer than 90 s is lost; a clock that goes
  back is waited for. `during` on an automation: it only acts while the windows it names
  are open.
  - Tried only with a clock set by hand in the tests, the two changes of summer time of
    Madrid in 2026 among them, and a real service that starts inside a window.
  - On the Pi, by its owner, before the fixes below: restarting systemd-timesyncd removes
    its whole directory until the next synchronization; and the state said `timeKnown` 9 s
    before the LED of an open window went on. Found too, with the controller and the test
    harness: a time at 03:00 was lost the day summer time starts, and a window closing told
    no listener. All four fixed: the clock stays trusted once set, the state says what the
    service last looked at, the gap between looks is counted in real time, and a window
    that opens or closes is told. The fixes have not been reported as run on the Pi.
    The fix of the gap broke something its owner then found: a window that starts in the
    hour summer time skips did not open that day (the time counted back fell inside it).
    Fixed: a window opens against what the look before found open.
  - Still to try on a Pi: starting without network and getting it later; a real time of
    day.
  - Left out: the time from a client for a board that never has Internet; once per window
    across restarts; a window that opened during panic is not caught up with.

- **4.4d · Persistent variables: code done; not tried on `primum-dev`** (decision 0031,
  `specs/engine-semantics.md`). The values of variables marked `persistent` are kept in
  `variables.json` in the data directory, for the project, and found when the service
  starts. A kept value its variable no longer takes gives way to the initial one. A change
  is written a second later, off the event loop, and on shutdown; a write that fails is
  told in the state (`variablesUnsaved`) and tried again.
  - Tried with a temporary directory: the file, the controller, the saver with timers in
    the test's hand, and a real service stopped and started again on the same directory.
  - To try on a Pi: a real restart of the service, and a power cut a moment after a change
    (the last second may be lost; the file must be whole).
  - On the Pi, by its owner, before the fixes: 31 s after a write failed, with the
    directory writable again and nothing pending, the state still said `variablesUnsaved`.
    Found too with the tests' fake loop, not seen on the board: a write under way could
    land over the one made on closing. Both fixed; the fixes have not been reported as run
    on the Pi.
  - Then, also by its owner on the Pi: a `variables.json` of binary garbage kept the
    service from starting (only texts that were not what they should had been tried). And
    with the fake loop: a write under way could leave an old value when the variable went
    back to the kept one and the service stopped. Both fixed; not reported as run again.
  - Found by the CI of this block, in the simulated HAL and not in the block: a change of
    an input made from another thread could be queued and never announced (the reader woke
    between the two), and the one test that waits for it over a WebSocket hung until the
    job was cancelled. The queue and its announcement are now one step, a test with two
    threads fails without that, and that wait is bounded.
  - For 4.5: what was kept is copied to `variables.json.bak` before values that drop some
    of it replace it; nothing reads the copy yet, and putting a package back must say how
    its values come back.
  - For phase 5: nobody sees `variablesUnsaved` but the log and the API; the page does not
    show it, and the catalog message of `variables.unwritable` only reaches the log.
  - Left out: a way to reset the variables other than removing the file; "once per window"
    across restarts, which could use the same file.

**4.5 · Trace, activation and rollback**
- Execution trace; a package is activated atomically and the previous one can be brought
  back.
  In two blocks: 4.5a the trace, 4.5b activation and rollback.
- **4.5a · Trace: code done; not tried on `primum-dev`** (decision 0032, `specs/trace.md`).
  The controller notes what it decides: events, what each automation did and why,
  sequences started, stopped and ended, variables, what a person commanded, panic; each
  with the entry that led to it. The last 1000, in memory. `GET /api/trace?after=n` and
  the WebSocket `/api/trace/ws`.
  - Tried on the simulated HAL only, a real service with both routes included.
  - Found in review, each reproduced with a test first: every panic noted again an output
    it could not make safe; a command the hardware refused was not noted, and its test
    then ended in the trace out of nowhere; a client of the WebSocket that came back after
    a restart with an `after` above the new trace waited in silence. Fixed, the last with
    a first message that always goes and an id of the trace (`run`). In a second round:
    an output that failed and that panic then made safe never got its `output.recovered`;
    a stop that found nothing running was remembered for a later run. The kinds are now
    an enumeration, held to the spec by a test. In a third: the same missing
    `output.recovered` by the other door, a person commanding with success an output that
    was failing. Every place an output stops being failing now notes it (three: a retry,
    panic, a command).
  - Left for phase 5: texts for the kinds, and a page that shows it. Left out: a trace
    kept across restarts; a restart of a sequence in the very millisecond it started is
    not noted.

- **4.5b · Activation and rollback: code done; not tried on `primum-dev`** (decision 0033,
  `specs/deployment-package.md`). A service told neither a package nor pins runs what was
  activated on it. `PUT /api/package` checks and keeps a package, `POST
  /api/package/activate` runs it by its hash, `POST /api/package/rollback` puts the one
  before back. Activating closes what runs (safe state, HAL released) and starts the
  package on a HAL of its own; one that cannot be started leaves what ran before running.
  A service with nothing it can run starts empty and says why. Persistent variables and
  the trace carry over.
  - Tried on the simulated HAL only, with a new simulated HAL at each activation.
  - To try on a Pi, and it is what this block most needs: that the real HAL can be closed
    and opened again in one process (lines released and requested again, PWM unexported
    and exported), which activation relies on and no test here can show. Then the "done
    when" of the phase, below.
  - On the Pi and with large packages, by its owner, before the fixes: a show of 3000
    clips (834 kB) held the event loop a second to store and a second to activate, and
    half a second at every `GET /api/package`; 7.9 MB of JSON that is no package, 5.4 s.
    Found too: with `packages/` read-only the answer said the activation failed with the
    new package already running; a claim that fails at start (another process holding a
    line) still killed the service; a counter was lost going to a package of another
    project and back; a sequence running at an activation was left without its
    `sequence.stopped`. All fixed, each with a test that failed before: the check is off
    the loop and the names are in the state file, the state is written before anything
    is touched, the service starts empty whatever keeps the active package from running,
    persistent values are one file per project, and the trace notes the stop. The fixes
    have not been reported as run on the Pi. A check in a thread still shares the
    interpreter with the loop: requests are answered meanwhile, more slowly.
  - Second review, three problems reproduced by its owner on the simulated HAL: a panic
    that came while the board wrote its state was taken away by the activation (the last
    look at panic was before an `await`); a failed activation stopped everything and
    told no listener of the state; what runs failing to close was blamed on the new
    package. Fixed, each with a test that failed before: panic is looked at inside the
    swap, with nothing awaited after; a refused package publishes the state; a stop
    that fails is `package.stop_failed` and what ran is claimed again. Also: a refusal
    by panic is noted in the trace, and files a power cut left half written are dropped.
    Simulated HAL only. On a real board, whether lines can be claimed again after a
    close that failed is not known: if they cannot, the service runs nothing.
  - `provision.sh` still writes a `PRIMUM_PIN`: a board runs packages once it is removed.
    Not changed here: the script cannot be tried from this session.
  - Left for phase 5: the PIN, which activation must be the first thing behind. Left out:
    a service started with `--package` and a file it cannot run still does not start.

**Done when:** "presence sensor → 10 s sequence with relay, LED and PWM output" runs from a
deployed package, shows in the trace and can be rolled back. A servo, an exclusive element
with its pulse limits, comes with the drivers of phase 6.

## Phase 5 · Local web UI v1

Vue 3 + TypeScript, mobile first, English and Spanish: pairing with PIN, file explorer,
elements with *Test*, simple sequence editor with simulated preview, automations, settings
(exposed variables), daily control, alerts, "controlled by" per element.

Blocks, one pull request each: 5.1 pairing · 5.2 the skeleton of `apps/webui` (Vue,
TypeScript, build, generated types, tokens, i18n, how the runtime serves it) · 5.3 daily
control on the API there is · 5.4 the project on the board and the first edit operations of
`core` · 5.5 file explorer and elements · 5.6 sequence editor with simulated preview ·
5.7 automations and schedules · 5.8 build and deploy from the UI.

- [x] **5.1 Pairing** (decision 0034, `docs/specs/pairing.md`). A board has a pairing code
  of six digits, made on it; a device that gives it gets a token (cookie for a browser,
  `Authorization: Bearer` for a program) that does not expire. Nothing is shown or
  commanded without it, panic included; WebSockets are not opened. Five wrong codes and
  none is taken for five minutes. `primum-pairing` shows the code and renews it;
  `--no-pairing` is for a laptop and for tests. The page of phase 1 asks for the code.
  - Tried with tests on the simulated HAL. The page was tried by hand, not by a test of
    the repository, in a headless Chromium against a simulated service: it asks for the
    code, shows a wrong one as such, pairs, the WebSocket opens with the cookie, and a
    reload stays paired. Not tried on a phone nor in another browser.
  - Review: a wait that did not grow let every code be tried in under two years; a file
    that could not be read was taken for missing, so any wrong code forgot every device
    and changed the code (reproduced by its owner with `chmod 000`); the test that listed
    the routes did not see the WebSockets, and FastAPI's `/docs` and `/openapi.json`
    answered anyone; `pairing.unwritable` told a client the path of the file;
    `primum-pairing` without `sudo` showed a traceback; nothing looked at `Origin`; every
    Android was named alike. Fixed, each with a test that failed before but the name: the
    wait doubles up to a day, an unreadable file is left alone (`pairing.unreadable`), the
    test walks the app's routes, the service describes itself to nobody, paths are logged
    and not answered (those of `package.unwritable` too), the command says to use `sudo`,
    a request with an `Origin` that is not the service's is refused, and the page asks
    for a name. The tests stand in for a file without permission with a read that fails:
    they run as root, which `chmod 000` does not stop.
  - To try on the Pi: `sudo /opt/primum/venv/bin/primum-pairing` shows the code and the
    service (user `primum`) still reads the file after `--renew` as root; the page pairs
    from a phone; `provision.sh`, whose check of the service now asks `GET /api/pairing`,
    still ends well.
  - Left out: HTTPS; roles; closing the WebSocket of a device that is forgotten; showing
    the code without a shell (phase 7).
- [x] **5.2 The skeleton of `apps/webui`** (decision 0035, `apps/webui/README.md`). Vue 3,
  TypeScript, Vite, Vitest, Vue Router, pnpm. The app pairs a device and says whether the
  board answers; the page keeps the controls until 5.3. Texts from `i18n/` (section
  `webui`), tokens and icons from `design/`, read where they are. The API's types are
  generated from the runtime's models through `apps/webui/openapi.json` (`just gen`). The
  build is not in the repository: `just ui-build` puts it in the runtime's package, which
  serves it at `/app/`, and `just pi-sync` builds it before copying. `just check` and CI
  lint, type-check, test and build it.
  - Tried: its tests (Vitest), and by hand, not by a test of the repository, in a headless
    Chromium as a phone in Spanish against a simulated service that serves the build: it
    asks for the code, says a wrong one in words, pairs, stays paired after a reload, shows
    panic when it comes, and unpairs. The copy rules of `pi.sh` were tried with `rsync` to
    a local folder (the build goes, `node_modules` does not), and the wheel was built and
    has the UI in it.
  - Review, found by its owner: `just pi-watch` started over and over with nobody saving
    (each sync built the UI into two watched folders: 9 starts in 40 s, measured with a
    stand-in for the copy); the app stopped asking for good when the board answered with
    an error, and showed a blank page if that happened at start; `/app` without its last
    slash answered an error in JSON. Fixed: the watch ignores the two folders (reproduced
    here the same way, 11 starts in 24 s, then 1); an error from the board is asked again
    and shown, with tests that failed before; `/app` leads to `/app/`, with its test.
    Also: the index is served `no-cache` (a risk, not seen: a browser keeping an index
    that names files a deployment removed); the sync builds the UI only when it is older
    than what it is made from (tried by hand with the function taken out of `pi.sh`);
    `just ui-dev` now serves the app at `/app/` and hands the rest to the service, so
    the link to the page works there too; the line height and the font weights, which
    have no token, are noted as the exception they are.
  - Not tried: `just pi-sync` and `just pi-watch` against a Pi, a real phone. `just ui-dev`
    was tried by hand in a headless Chromium (pairing, the WebSocket through its proxy, the
    link to the page). The CI steps that install pnpm ran with this pull request.
  - Left for later: the fonts of the brand bundled for offline use (it shows the system's);
    TypeScript types of the project's formats, from `schemas/` (5.4); tests in a browser
    that are part of the repository.
- [x] **5.3a Daily control in the web UI; the page of phase 1 is gone.** Tabs at the bottom
  (Control, Settings; Activity comes with 5.3b). Control has the outputs (switch, level,
  *Test* with its countdown, who commands each and *Release*), the sequences, the inputs
  and the panic button, on that screen only. Above the content of every screen: no
  connection, panic and its release, what the board last refused, and the board's alerts
  (an output not confirmed off, lost changes of an input, values not saved, time not
  known with schedules waiting, an active package that does not run). The app is served
  at `/`; `primum_runtime/ui/`, its generated copies, its JavaScript tests and the `ui`
  section of the catalogs are removed.
  - Tried: its Vitest tests, the behaviour of the page ported with them (a switch that says
    nothing offline, a test not offered for an output left on, the slider asked for once on
    letting go and keeping the time of a test). By hand, not by a test of the repository:
    a headless Chromium as a phone in Spanish against a simulated service running
    `examples/shop-window`: pairing, a switch and its release, a test and its countdown,
    the level by keys, a sequence, panic from Control and its release from Settings.
  - Found by that browser run and not by the tests written first: keys pressed one after
    another on the slider went back to the old level between them. Fixed, with a test
    that failed before.
  - Review, found by its owner: panic pressed with the service stopped said "Retrying…"
    twice while the order was lost, and the second notice stayed after reconnecting; with
    an output stuck (provoked by taking the rights of the PWM's `duty_cycle` away and
    pressing panic) the red notice said "every output is off" above an alert saying one
    could not be confirmed off, and its row spoke of a test that never was. Fixed, each
    with a test that failed before: an order that did not get to the board is said as not
    sent, once, and forgotten when the board is back; panic has a second text for when an
    output is not confirmed off; the row says only what is known. Also: the controls of a
    row are side by side and in the same place in every row (*Release* went next to what
    says the output is held); nothing says "no connection" while the first connection is
    being made; a phone held sideways keeps a smaller panic button and more room;
    pairing is asked once at start. Seen while checking, not reported: a hairline of the
    panic button's color at the edge of its area on screens with a pixel ratio that is not
    whole; gone, measured by pixels.
  - Second review, found by its owner: an answer to a command that came late replaced a
    later state (a switch held back, panic from another device, and the screen showed the
    relay on and no panic); a board that does not answer without closing the connection
    passed for connected, and panic gave no sign in 35 s; the alert of an active package
    that does not run stayed after another device activated a good one; an alert with a
    long word ran off the screen, and that word was the path of a file, answered by
    `GET /api/package`; an order from a device the board had forgotten sent it to pair
    without saying it was not done. Fixed, each with a test that failed before: every
    state has a number (`revision`) rising across the controllers of a service, and the
    app drops one that is not later than the one it holds; a request is waited for 5 s,
    then said as not answered, and the connection is made again; the packages are asked
    again while their problem stands; notices break long words; no error a client is told
    has a file's path, inside another body either, and the two messages that had `{path}`
    in them no longer do (a test keeps it so); the pairing screen says the order was not
    carried out. Tried by hand in the browser with the service frozen (`SIGSTOP`): told
    after 5 s, "no connection" shown, back by itself when thawed. Not tried: a power cut
    or leaving the Wi-Fi's range, where nothing closes the connection; the limit of 5 s
    is what answers there, when something is asked. A screen nobody touches still shows
    a frozen board as connected: the WebSocket has no heartbeat yet.
  - Third review, found by its owner with the simulated service frozen for more than 10 s:
    "no connection, retrying" gave way to a second "the board did not answer: it is not
    known whether it did what was asked", with no way to close it. The question
    `connect()` asks (is this device paired?) ran out of time too, and was told as an
    order. Fixed, with tests that failed before: a question that is not answered is "no
    connection"; only an order can be left unanswered. The same for pairing itself. Tried
    by hand in the browser with the service frozen 26 s.
  - Fourth review, found by its owner with emulated touch: scrolling the page with the
    finger starting on the slider's track sent a level (the real PWM went from 18 % to
    71 %): the browser moves the slider under the finger, then takes the touch for a
    scroll, and the cancelled touch was treated as letting go. Fixed, with a test that
    failed before: a cancelled touch asks for nothing and the slider goes back to what the
    board reports; a drag up or down over the slider scrolls, one sideways moves it.
    Reproduced here the same way before the fix and gone after it, with touches sent
    through the browser's debugger. **Not tried with a finger on a phone**, and this
    would be a 220 V dimmer: to try before trusting it. Also: panic pressed while the
    screen waited to connect again was done by the board and the screen went on saying
    "no connection" for up to 10 s; an order the board answers now connects at once.
    Unpairing with no connection said "retrying"; it says it was not sent. More room
    between the rows; the rows of the inputs are no longer announced at every change.
  - For the start of 5.3b: a heartbeat on the WebSocket. A phone that leaves the Wi-Fi's
    range is the common case, and until then its screen shows an old state as current
    for as long as nothing is asked.
  - Noted for later, not done: the answer of a service that has just died, arriving after
    the first state of the one that replaced it, would carry a high `revision` and make
    the app drop every state until it connects again. Not reproduced, and very unlikely; a
    mark of the service's start next to the number would close it. Without a watchdog (a
    laptop), an order given to a frozen service is carried out when it thaws: the notice
    says to look at what the board is doing. Rows are not all of one height: a long name
    sends its controls to the next line.
  - Not done: `/app/`, the address of block 5.2, answers 404. It lived one day; a redirect
    would stay for ever.
  - Not tried: a real phone, a real board, a finger on the slider (only keys and
    synthetic pointer events), a screen reader.
  - Left for 5.3b: variables, firing events, the state of automations and schedules,
    packages, the trace, the list of paired devices.
- [x] **5.3b (1 of 3) A heartbeat, the project's settings and events.** The WebSocket of
  the state says the state again when nothing changed for 2 s (asked of what runs now,
  with a new `revision`), and the web UI takes 6 s of silence for a board that is gone and
  looks for it again: a screen nobody touches no longer shows the state of a frozen or
  unreachable board as current. Control gets the events a person may fire (a button, no
  confirmation, not in panic) and the variables the project exposes as settings: a slider
  for a number with both limits, a field for one without or for a text, a switch for true
  or false; sent on letting go or leaving the field, what the board refuses goes back to
  what it has. The slider of the outputs became a component of its own, used by both.
  - Tried: its tests (pytest for the beat, Vitest for the rest). By hand, not by a test
    of the repository, in a headless Chromium against a simulated service running a copy
    of `examples/shop-window` with more settings and an event: each kind of setting,
    Enter then leaving a field sends once, a value out of range is refused in words and
    the field goes back; with the service frozen and nobody touching, "no connection"
    after 4.8 s, and back when thawed; 7 s idle with the board there, no false alarm.
  - Review, found by its owner: the slider of a number with decimals moved in hundredths
    of its range, which missed round values (0.15 from 15 to 30: 20 shown at 19.95, and
    never 21); with the beat, an active package that does not run had the app ask for the
    packages every 2 s; a whole number with a wide range (0 to 10000) could not be set
    with a finger, and could not be typed; a value that was no value of its type went back
    without a word; firing an event said nothing when its automations showed nothing.
    Fixed, each with a test that failed before: decimals move in a round step (1, 2 or 5
    times a power of ten, at most 100 steps); the packages are asked for again only when
    the state says something new; a whole number with more than 100 values is a field
    within its limits; what is no value of its type is said as the board would; an event
    the board took says "done" for 2 s. Also: the tab of the board's own matters is
    *Board*, and the section of Control *Settings*, as the glossary calls them.
  - Noted for later, not done: variables have no name to show, so a setting is shown by
    its id (`delay_ms`); a `step` declared by the variable would let the project choose
    its own.
  - Not tried: a real phone, leaving a real Wi-Fi's range, a finger on the sliders.
  - Next: the Activity tab (the trace, the state of automations and schedules), then
    packages and paired devices in the Board tab.

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
