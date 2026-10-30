# Primum OS image

Everything installed or configured on the Pi lives here, as scripts: **nothing is set up by
hand on a board**. The provisioning script (phase 1) prepares a stock Raspberry Pi OS Lite for
development; in phase 7 rpi-image-gen runs the same script to build the Primum OS image
(partitions `boot` · `rootfs A` · `rootfs B` · `data`, read-only root, first-boot setup).

- `provision.sh`: prepares a Pi for Primum or updates its runtime; idempotent. From the laptop:
  `PRIMUM_PI_HOST=primum-dev uv run just pi-provision 17` the first time (the LED on GPIO 17),
  then `uv run just pi-sync`. Layout and choices: decision 0012.
- `check-gpio-users.sh`: refuses a board where other software drives GPIO (decision 0010).
- `primum.service`: the systemd unit, configured by `/etc/primum/runtime.env`.
