# Primum OS image

Everything installed or configured on the Pi lives here, as scripts: **nothing is set up by
hand on a board**. The provisioning script (phase 1) prepares a stock Raspberry Pi OS Lite for
development; in phase 7 rpi-image-gen runs the same script to build the Primum OS image
(partitions `boot` · `rootfs A` · `rootfs B` · `data`, read-only root, first-boot setup).

- `provision.sh`: prepares a Pi for Primum or updates its runtime; idempotent. From the laptop:
  `uv run just pi-provision 17` the first time (the LED on GPIO 17), then `uv run just pi-sync`.
  Layout and choices: decision 0012.
- `check-gpio-users.sh`: refuses a board where other software drives GPIO (decision 0010).
- `primum.service`: the systemd unit, configured by `/etc/primum/runtime.env`.

## The development Pi

A Raspberry Pi 4 (or an SD card) for Primum only, never one that runs other GPIO software.

1. Raspberry Pi Imager: Raspberry Pi OS Lite (64-bit), hostname `primum-dev`, a user, the Wi-Fi
   the laptop and the phone use, SSH with the laptop's public key. Keep "Exclude system drives"
   ticked and pick the card by its size.
2. Wire an LED and a 220–330 Ω resistor between GPIO 17 (physical pin 11) and GND (pin 9).
3. An SSH alias `primum-dev` in `~/.ssh/config`, and `ssh primum-dev hostname` working without a
   password. Check the LED with `ssh primum-dev 'sudo pinctrl set 17 op dh'` (then `dl`, `ip`).
4. `rsync` on the laptop and on the Pi, then `uv run just pi-provision 17`.

**From WSL.** Windows may resolve `primum-dev.local` only to an IPv6 link-local address
(`ping -4 primum-dev.local` in PowerShell gives the IPv4 one). When the Pi is on the network
Windows shares from the laptop (`192.168.137.x`), WSL cannot reach it directly: forward a local
port to it, in an administrator PowerShell, and point the alias there.

```powershell
netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=2223 connectaddress=<Pi IPv4> connectport=22
```

```
Host primum-dev
    HostName 127.0.0.1
    Port 2223
    User <your user>
    IdentityFile ~/.ssh/id_ed25519
```

Use a port of its own for each Pi; the phone opens the page at `http://<Pi IPv4>:8080`.
