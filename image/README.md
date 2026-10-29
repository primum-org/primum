# Primum OS image

Everything installed or configured on the Pi lives here, as scripts: **nothing is set up by
hand on a board**. The provisioning script (phase 1) prepares a stock Raspberry Pi OS Lite for
development; in phase 7 rpi-image-gen runs the same script to build the Primum OS image
(partitions `boot` · `rootfs A` · `rootfs B` · `data`, read-only root, first-boot setup).
