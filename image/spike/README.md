# Image spike (block 1.5)

The smallest image that proves [rpi-image-gen](https://github.com/raspberrypi/rpi-image-gen)
works for Primum: Debian Trixie for a Raspberry Pi 4 with SSH and Wi-Fi, built in CI on an
arm64 runner. It is a check of the tool, not Primum OS: phase 7 builds the real image
(partitions A/B, read-only root, first-boot wizard) and will replace this folder.

- `config/primum-spike.yaml`: the build (Pi 4, hostname `primum-spike`, user `primum` with
  passwordless sudo and no password, SSH with keys only).
- `layer/primum-spike.yaml`: a service that, at boot, applies the files in `primum/` on the
  boot partition. Its files live in `layer/primum-spike.d/customize.overlay/`.
- `.github/workflows/image-spike.yml`: builds it with a pinned rpi-image-gen and uploads
  `primum-spike.img.xz` (kept 7 days). It runs by hand (Actions → Image spike → Run workflow)
  and on pull requests that change the spike.

## Trying it

1. Download the `primum-spike-image` artifact from the workflow run and unzip it.
2. Raspberry Pi Imager: Raspberry Pi 4, **Use custom** → `primum-spike.img.xz`, a spare microSD.
   The Imager's customisation (user, Wi-Fi) does not apply to this image: skip it.
3. Before ejecting the card, open its boot partition (`bootfs`) and create a folder `primum` with:
   - `wifi.txt`, two lines (the password is deleted from the card at first boot):
     ```
     SSID=<your Wi-Fi>
     PSK=<its password>
     ```
   - `authorized_keys`: your public key, the output of `cat ~/.ssh/id_ed25519.pub`.
4. Boot the Pi with it and connect as user `primum` (host `primum-spike`), for example with an
   SSH alias like the development Pi's (`image/README.md`):
   ```bash
   ssh primum-spike 'hostname && cat /etc/os-release | grep PRETTY && uname -m'
   ```

No secret goes through CI: the Wi-Fi password and the key are added to the card after flashing.
