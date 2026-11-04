# 0012. Deploying the runtime to the development Pi

- Status: Accepted
- Date: 2026-10-30

## Context
Block 1.4 runs the runtime on a real Raspberry Pi as a service. Everything installed on a board
must come from scripts (phase 7 builds the image with the same ones), the board must never be
shared with other GPIO software (decision 0010), and the API has no authentication until phase 5
(decision 0011).

## Decision
- **One script, idempotent:** `image/provision.sh`. It checks that the board is a Raspberry Pi
  and that no other software drives GPIO, then installs packages, a pinned `uv`, the system user
  `primum` (group `gpio`), `/data`, the configuration, the runtime and its systemd unit.
  `--app-only` installs new source and the unit, and restarts the service. A restart counts
  once the API answers, not when systemd reports the process active.
- **Generic refusal:** `image/check-gpio-users.sh` looks for processes holding `/dev/gpiomem`
  or `/dev/mem` and for a running `pigpiod`. No program is named in the code. It runs as root
  (otherwise other users' processes are invisible and it would pass): in provisioning, before
  the tests on the Pi, and as the service's `ExecStartPre`.
- **Layout:** the copied source in `/opt/primum/app`, the runtime in `/opt/primum/venv` (uv,
  `--no-dev --no-editable --compile-bytecode`, from `uv.lock`), configuration in
  `/etc/primum/runtime.env`, data in `/data`. Python 3.13 is the system's when it has it
  (Raspberry Pi OS 13, as on the development Pi); otherwise uv installs it in
  `/opt/primum/python`. The service runs as `primum`, may write only
  `/data` (`ProtectSystem=strict`), restarts on failure and is stopped with `SIGTERM`, which
  applies the safe state.
- **The LED's pin is required** the first time (`--pin`), never defaulted.
- **Laptop side:** `tools/pi.sh` behind `just pi-*`, host from `PRIMUM_PI_HOST`, by default
  `primum-dev`: an SSH alias that names the development Pi and no other board. The source is
  mirrored with `rsync`, filtered by `.gitignore`, so local changes are tried without
  committing and deleted files disappear on the Pi too.
- **Tests on the Pi** (`just pi-test`) stop the service, which holds the LED's line, run the
  `hw` tests on the configured pin with only the runtime and the `test` dependency group, and
  start the service again whatever the result.

## Alternatives considered
- Installing from a git clone on the Pi: needs GitHub credentials there and a commit for every
  try.
- A wheel built on the laptop: one more step per change, and `uv.lock` already pins everything.
- Defaulting the pin to 17: a default pin is a pin someone wired a relay to (it happened, on a
  Pi that was running another installation).

## Consequences
- The laptop needs `ssh` and `rsync`; the Pi needs Internet the first time.
- The service listens on the local network (port 8080) with no authentication until phase 5:
  only LEDs, on a home network.
- Software that drives GPIO but is not running when the script runs is not found: the
  development Pi, or its SD card, is for Primum only.
- Phase 7 reuses `provision.sh` inside rpi-image-gen; what only makes sense on a live board
  (restarting the service) will move behind an option then.
