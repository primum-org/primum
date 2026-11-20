#!/usr/bin/env bash
# Exit 1, listing them, if other software drives GPIO on this board; 0 if none is found.
#
# Primum never shares a Pi with other GPIO software (decision 0010): programs that write
# /dev/gpiomem or /dev/mem (RPi.GPIO, pigpio, wiringPi) drive lines the kernel reports as free,
# so the HAL cannot see them. Nothing here is specific to one program. Limit: software that is
# installed but not running holds nothing, so it is not found; a Pi for Primum has none.
#
# With --pwm it also refuses a board where a PWM channel is already exported
# (/sys/class/pwm/pwmchipN/pwmM): a channel has no owner, so the HAL would adopt one another
# program is using. The service asks for it at start, after primum-safe has unexported what a
# crash of Primum itself left; provisioning does not, since the running service holds its own.
#
# Needs root: other users' open files are hidden from a normal user, so without root the
# check would find nothing and pass. PROC (a fake process tree) and SYSFS_PWM (a fake
# /sys/class/pwm) are for the tests.
set -euo pipefail

check_pwm=false
case ${1:-} in
  "") ;;
  --pwm) check_pwm=true ;;
  *)
    echo "usage: $0 [--pwm]" >&2
    exit 2
    ;;
esac

if [[ -z ${PROC:-} ]] && ((EUID != 0)); then
  echo "check-gpio-users: run it as root (without root it cannot see other users' processes)" >&2
  exit 2
fi

proc=${PROC:-/proc}
found=()
exported=()

for fd in "$proc"/[0-9]*/fd/*; do
  [[ -L $fd ]] || continue
  target=$(readlink "$fd" || true)
  case $target in
    /dev/gpiomem* | /dev/mem)
      pid_dir=${fd%/fd/*}
      name=$(cat "$pid_dir/comm" 2>/dev/null || echo "?")
      found+=("process ${pid_dir##*/} ($name) has $target open")
      ;;
  esac
done

if command -v systemctl >/dev/null && systemctl is-active --quiet pigpiod 2>/dev/null; then
  found+=("the pigpiod service is running")
fi

if $check_pwm; then
  for channel in "${SYSFS_PWM:-/sys/class/pwm}"/pwmchip*/pwm[0-9]*; do
    [[ -d $channel ]] || continue
    chip=${channel%/*}
    found+=("PWM channel ${channel##*/pwm} of ${chip##*/} is in use (exported)")
    exported+=("echo ${channel##*/pwm} | sudo tee $chip/unexport")
  done
fi

if ((${#found[@]})); then
  echo "Other software drives GPIO on this board, so Primum must not run here:" >&2
  printf '  - %s\n' "${found[@]}" | sort -u >&2
  echo "Use a Pi (or an SD card) for Primum only. See docs/decisions/0010." >&2
  if ((${#exported[@]})); then
    # Primum's own runtime leaves a channel like this when it is started by hand and killed:
    # nothing ran primum-safe for it.
    echo "If no other program uses PWM here, free each channel and start again (or reboot):" >&2
    printf '  %s\n' "${exported[@]}" >&2
  fi
  exit 1
fi
