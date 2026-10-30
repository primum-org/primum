#!/usr/bin/env bash
# Exit 1, listing them, if other software drives GPIO on this board; 0 if none is found.
#
# Primum never shares a Pi with other GPIO software (decision 0010): programs that write
# /dev/gpiomem or /dev/mem (RPi.GPIO, pigpio, wiringPi) drive lines the kernel reports as free,
# so the HAL cannot see them. Nothing here is specific to one program. Limit: software that is
# installed but not running holds nothing, so it is not found; a Pi for Primum has none.
#
# PROC (default /proc) lets the tests use a fake process tree.
set -euo pipefail

proc=${PROC:-/proc}
found=()

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

if ((${#found[@]})); then
  echo "Other software drives GPIO on this board, so Primum must not run here:" >&2
  printf '  - %s\n' "${found[@]}" | sort -u >&2
  echo "Use a Pi (or an SD card) for Primum only. See docs/decisions/0010." >&2
  exit 1
fi
