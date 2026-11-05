# 0013. rpi-image-gen builds Primum OS, in CI on arm64 runners

- Status: Accepted
- Date: 2026-11-05

## Context
Phase 7 ships Primum OS as an image people flash and boot. Block 1.5 was a spike to learn early
whether [rpi-image-gen](https://github.com/raspberrypi/rpi-image-gen), Raspberry Pi's tool for
custom images, can build it in our CI and whether the result boots, before phase 7 depends on it.

## Decision
- **rpi-image-gen builds the image**, pinned to a release (v2.9.0 today), from a config and our
  own layers in `image/`. Layers ship files through `<layer>.d/customize.overlay/` and enable
  units in their hooks.
- **CI builds it on `ubuntu-24.04-arm`**, the runner rpi-image-gen's own CI uses: native arm64,
  no QEMU, no privileged container. The spike workflow runs by hand and on pull requests that
  change the image, not on every pull request.
- **No secret goes into the image or through CI.** Anything personal (Wi-Fi, keys) is added
  after flashing; in phase 7 through the board's own Wi-Fi and the setup wizard.

## What the spike found (2026-11-04/05, Pi 4)
- The build works at the first try: about 2 minutes for rpi-image-gen, 3 for the whole job, and
  a 160 MB `.img.xz` (Debian 13 Trixie, minimal base). It booted on the Pi 4.
- The minimal base is not Raspberry Pi OS, and three gaps showed up, all fixed in the spike:
  - **No Wi-Fi country** (regulatory domain "world"): set it (`ieee80211.regdom`). Phase 7 asks
    for it at first boot.
  - **No mDNS**: the board did not answer as `<name>.local` until `avahi-daemon` was added.
  - **Raspberry Pi Imager's customisation does not apply** to a custom image (it relies on
    Raspberry Pi OS's first-boot scripts). The spike reads `primum/wifi.txt` and
    `primum/authorized_keys` from the boot partition instead; phase 7 replaces this with its
    own Wi-Fi and wizard.
- **A board that cannot be reached cannot be debugged** when its user has no password: the
  spike writes `primum/status.txt` on the boot partition 90 s after boot (Wi-Fi state, networks
  seen, addresses, iwd's log). Phase 7 keeps a report of this kind.
- **Networking is iwd + systemd-networkd** in the minimal base, not NetworkManager as in
  Raspberry Pi OS. Phase 7 must choose the stack for its own access point (iwd has an AP mode).

## Alternatives considered
- **pi-gen**, the tool behind Raspberry Pi OS: heavier, builds from stages meant for the full
  distribution, and slower to change than layers.
- **Building on the Pi or under QEMU**: works, but slower and outside what rpi-image-gen
  supports; the arm64 runner is native and free for public repositories.
- **Remastering Raspberry Pi OS Lite**: keeps everything Raspberry Pi OS ships (Imager
  customisation, mDNS) but gives no control over partitions or a read-only root.

## Consequences
- Phase 7 starts from a working pipeline: `image/spike/` is replaced by the real config (A/B
  partitions, read-only root, `data`), keeping the overlay and status-report patterns.
- rpi-image-gen is under active development: upgrades are deliberate (the pinned version), and
  each one runs the image workflow and a boot on the Pi.
- Every Raspberry Pi OS convenience Primum relies on must be added to the image explicitly, as
  mDNS and the Wi-Fi country were.
