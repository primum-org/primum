#!/usr/bin/env bash
# Work against the development Pi from the laptop (block 1.4). Used by the `just pi-*` tasks.
#
#   tools/pi.sh provision PIN  copy the source and provision the Pi (first time: the LED's pin)
#   tools/pi.sh sync           copy the source, install it and restart the service
#   tools/pi.sh test           run the `hw` tests on the Pi, on the LED's pin (and on
#                              PRIMUM_HW_INPUT_PIN / PRIMUM_HW_PWM_PIN when set)
#   tools/pi.sh logs           follow the service's log
#
# The Pi is the SSH host in PRIMUM_PI_HOST, `primum-dev` by default: an alias of ~/.ssh/config
# with key-based login and passwordless sudo (image/README.md). Never point it at a Pi that runs
# other GPIO software (decision 0010); provisioning refuses to run there.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REMOTE_SOURCE=primum-src
DEFAULT_HOST=primum-dev

fail() {
  echo "pi: $*" >&2
  exit 1
}

host() {
  echo "${PRIMUM_PI_HOST:-$DEFAULT_HOST}"
}

# Mirror the working tree, local changes included, minus what .gitignore excludes (rsync reads
# the .gitignore files as filter rules), so files deleted here are deleted on the Pi too.
sync_source() {
  local pi=$1
  echo "==> copying the source to $pi:$REMOTE_SOURCE"
  rsync -a --delete --exclude .git --filter=':- .gitignore' "$ROOT/" "$pi:$REMOTE_SOURCE/"
}

provision() {
  local pi
  pi=$(host)
  [[ ${1:-} =~ ^[0-9]+$ ]] || fail "usage: tools/pi.sh provision PIN (the GPIO of the LED)"
  sync_source "$pi"
  # shellcheck disable=SC2029 # expanded here on purpose: the pin is checked above
  ssh "$pi" "sudo $REMOTE_SOURCE/image/provision.sh --pin $1"
}

sync() {
  local pi
  pi=$(host)
  sync_source "$pi"
  # shellcheck disable=SC2029 # expanded here on purpose: a constant path
  ssh "$pi" "sudo $REMOTE_SOURCE/image/provision.sh --app-only"
}

# The optional pins of the input and PWM tests, as assignments for `env` on the Pi, only when
# set here: ssh joins its arguments into one command line, so an empty argument would vanish
# and shift the ones after it.
optional_pins() {
  local name
  for name in PRIMUM_HW_INPUT_PIN PRIMUM_HW_PWM_PIN; do
    [[ -n ${!name:-} ]] && printf '%s=%q ' "$name" "${!name}"
  done
  return 0
}

# The service holds the LED's line, so it is stopped for the tests and started again after,
# whatever they return. The tests use the pin the service is configured with: the only line
# known to have just an LED on it.
test_hw() {
  local pi
  pi=$(host)
  sync_source "$pi"
  # shellcheck disable=SC2029 # expanded here on purpose: a constant path and %q-quoted pins
  ssh "$pi" "env $(optional_pins)bash -s -- $REMOTE_SOURCE" <<'REMOTE'
set -euo pipefail
cd "$1"
sudo ./image/check-gpio-users.sh
pin=$(sed -n 's/^PRIMUM_PIN=//p' /etc/primum/runtime.env)
sudo systemctl stop primum.service
trap 'sudo systemctl start primum.service' EXIT
# Only the runtime and pytest: some dev tools (shellcheck-py) have no wheel for the Pi.
uv sync --frozen --quiet --no-default-groups --group test
PRIMUM_HW_TEST_PIN=$pin uv run --frozen --no-sync pytest -m hw packages/runtime
REMOTE
}

logs() {
  ssh -t "$(host)" journalctl -u primum.service -n 50 -f
}

case ${1:-} in
  provision) provision "${2:-}" ;;
  sync) sync ;;
  test) test_hw ;;
  logs) logs ;;
  *) fail "usage: tools/pi.sh provision PIN | sync | test | logs" ;;
esac
