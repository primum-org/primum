#!/usr/bin/env bash
# Prepare a stock Raspberry Pi OS Lite (64-bit) for Primum, or update the installed runtime.
# Idempotent: running it again only changes what differs. Nothing is set up by hand on the Pi.
#
#   sudo image/provision.sh --pin 17   # first time: everything, with the LED on GPIO 17
#   sudo image/provision.sh            # again: everything, keeping the configured pin
#   sudo image/provision.sh --app-only # only install this source and restart the service
#
# Run it from a copy of the repository on the Pi (`just pi-provision` and `just pi-sync` copy
# it and run it). Layout:
#   /opt/primum/app      the source being installed      /opt/primum/venv  the runtime
#   /opt/primum/python   Python, installed by uv         /etc/primum/runtime.env  configuration
#   /data                the only writable path of the service (user `primum`, group `gpio`)
set -euo pipefail

UV_VERSION=0.11.32
PORT=8080
SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PRIMUM_HOME=/opt/primum
CONFIG=/etc/primum/runtime.env
UNIT=/etc/systemd/system/primum.service
MODEL_FILE=${MODEL_FILE:-/proc/device-tree/model}
PACKAGES=(git build-essential curl rsync)

pin=""
app_only=false

usage() {
  echo "usage: sudo $0 [--pin N] [--app-only]" >&2
  exit 2
}

log() { echo "==> $*"; }

fail() {
  echo "provision: $*" >&2
  exit 1
}

parse_args() {
  while (($#)); do
    case $1 in
      --pin)
        [[ ${2:-} =~ ^[0-9]+$ ]] || usage
        pin=$2
        shift 2
        ;;
      --app-only)
        app_only=true
        shift
        ;;
      *) usage ;;
    esac
  done
}

check_board() {
  local model
  model=$(tr -d '\0' <"$MODEL_FILE" 2>/dev/null || true)
  [[ $model == "Raspberry Pi"* ]] || fail "this is not a Raspberry Pi (${model:-no $MODEL_FILE})"
}

check_root() {
  ((EUID == 0)) || fail "run it as root: sudo $0"
}

install_packages() {
  local missing=()
  for package in "${PACKAGES[@]}"; do
    dpkg -s "$package" >/dev/null 2>&1 || missing+=("$package")
  done
  ((${#missing[@]})) || return 0
  log "installing ${missing[*]}"
  apt-get update -q
  # build-essential: gpiod builds its own libgpiod when PyPI has no wheel for this Python.
  apt-get install -y -q --no-install-recommends "${missing[@]}"
}

install_uv() {
  if [[ $(/usr/local/bin/uv --version 2>/dev/null) == "uv $UV_VERSION"* ]]; then
    return 0
  fi
  log "installing uv $UV_VERSION"
  curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" |
    env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
}

create_user() {
  if ! id primum >/dev/null 2>&1; then
    log "creating user primum"
    useradd --system --user-group --home-dir /var/lib/primum --create-home \
      --shell /usr/sbin/nologin primum
  fi
  usermod --append --groups gpio primum
  install -d -o primum -g primum -m 0750 /data
}

write_config() {
  if [[ -z $pin ]]; then
    [[ -f $CONFIG ]] || fail "first provisioning needs the LED's pin: --pin N (no default pin)"
    return 0
  fi
  log "configuring the LED on GPIO $pin, port $PORT"
  install -d -m 0755 "$(dirname "$CONFIG")"
  # Listens on the local network so a phone can reach the page. No authentication until
  # phase 5 (decision 0011): LEDs only.
  cat >"$CONFIG" <<CONFIG
PRIMUM_PIN=$pin
PRIMUM_HOST=0.0.0.0
PRIMUM_PORT=$PORT
CONFIG
  chmod 0644 "$CONFIG"
}

install_app() {
  log "installing the runtime from $SOURCE"
  install -d -m 0755 "$PRIMUM_HOME"
  rsync -a --delete --exclude .venv --exclude .git "$SOURCE/" "$PRIMUM_HOME/app/"
  # Not editable: the venv keeps working whatever later happens to the copied source.
  UV_PROJECT_ENVIRONMENT=$PRIMUM_HOME/venv \
    UV_PYTHON_INSTALL_DIR=$PRIMUM_HOME/python \
    UV_CACHE_DIR=/var/cache/primum/uv \
    /usr/local/bin/uv sync --directory "$PRIMUM_HOME/app" --frozen --no-dev --no-editable \
    --package primum-runtime --quiet
}

install_service() {
  if ! cmp -s "$SOURCE/image/primum.service" "$UNIT"; then
    log "installing $UNIT"
    install -m 0644 "$SOURCE/image/primum.service" "$UNIT"
    systemctl daemon-reload
  fi
  systemctl enable --quiet primum.service
}

restart_service() {
  log "restarting primum.service"
  systemctl restart primum.service
  sleep 2
  if ! systemctl is-active --quiet primum.service; then
    journalctl -u primum.service -n 20 --no-pager >&2
    fail "primum.service did not start (log above)"
  fi
  log "running: http://$(hostname).local:$PORT"
}

main() {
  parse_args "$@"
  check_board
  check_root
  "$SOURCE/image/check-gpio-users.sh" || fail "refusing to install Primum next to other GPIO software"
  if ! $app_only; then
    install_packages
    install_uv
    create_user
    write_config
  fi
  [[ -f $CONFIG ]] || fail "Primum is not provisioned yet: run it once with --pin N"
  install_app
  $app_only || install_service
  restart_service
}

main "$@"
