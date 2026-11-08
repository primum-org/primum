# Board profiles

A board profile describes a board model as data: the pins of its header, its buses, its
hardware PWM channels, the GPIOs Primum never assigns, and how its GPIOs map to the lines of
its GPIO chip. One file per model in `boards/` (`boards/rpi4b.json`), named after the model.
Format: `schemas/board-profile.schema.json`. Adding a compatible board means adding a profile.

## Contents

| Field | Meaning |
|---|---|
| `id`, `kind` (`board_profile`), `schemaVersion` (1) | As every file format |
| `model` | Short, stable identifier (`rpi4b`): the file name, used by projects and the runtime |
| `name` | The model's name for people (`Raspberry Pi 4 Model B`) |
| `gpioChip.label` | The label of the GPIO chip that drives the header (`pinctrl-bcm2711`) |
| `pwmChip.device` | The device name of the hardware PWM controller (`fe20c000.pwm`), what `/sys/class/pwm/pwmchipN/device` points at: the chip number can change with the kernel |
| `pins` | Every pin of the header: `physical` number and `kind` (`gpio`, `power_3v3`, `power_5v`, `ground`) |
| `buses` | Each bus (`i2c`, `spi`, `uart`) with the GPIO of each signal (`sda` → GPIO 2) |
| `pwmChannels` | Each hardware PWM channel: its `channel` index on the controller and the GPIOs that can use it |
| `reserved` | GPIOs never assigned to an element, with the reason (`hat_eeprom`) |

A `gpio` pin also has `gpio` (its number, BCM on a Raspberry Pi), `line` (its line on the GPIO
chip) and `defaultPull` (`up` or `down`, its pull at power on, before anything configures it).

## Rules

The schema checks the shape; `core` (`primum_core.boards`, run by
`primum_core.formats.read_board_profile`) checks the rest, each with its code:

- each physical pin appears once (`board.duplicate_pin`);
- a `gpio` pin has `gpio`, `line` and `defaultPull` (`board.incomplete_gpio_pin`); other pins
  have none of them (`board.power_pin_with_gpio`);
- each GPIO is on one pin (`board.duplicate_gpio`) and each line belongs to one GPIO
  (`board.duplicate_line`);
- buses, PWM channels and reserved pins name GPIOs the board has (`board.unknown_gpio`);
- bus and PWM channel ids are unique (`board.duplicate_id`).

Every profile in `boards/` must read without issues and be named after its model: a test
checks it.

## How it is used

- **The chip is found by its label**, never by its device path: `/dev/gpiochipN` can change
  with the kernel (on a Pi 5 it did). The runtime opens every GPIO chip and keeps the one with
  the profile's label; a chip that cannot be opened is skipped, as another may be the one. If
  none matches, `hal.chip_not_found` (or `hal.chip_access_denied`, if a chip could not be
  opened for lack of permission) names every chip it found. Links between devices
  (`gpiochip4 -> gpiochip0` on Raspberry Pi OS) are skipped.
- **A GPIO is requested on its `line`**, never on its number: on a Pi 4 they are equal, on
  other boards they need not be. A line the chip does not have means the profile is wrong for
  the board: `hal.profile_mismatch`, not the user's `hal.pin_invalid`.
- **The runtime refuses pins the board does not have** with `hal.pin_invalid`, simulated or
  not (`--simulate` fails where the Pi would). It ships a copy of the profiles
  (`primum_runtime/generated/boards/`, `just gen`) and drives the board given by `--board`
  (`PRIMUM_BOARD`), `rpi4b` by default.
- `core` gives out the board's resources to the elements of a project (below).

## Resource allocation

`primum_core.resources.check_resources` takes the project's files and the profiles by model
(`core` reads no files: the CLI loads them from its copy of `boards/`). For every board of a
`.hw` file, it finds the profile of its `model` (`board.unknown_model` otherwise, and the
board's elements are not checked) and checks each element wired to it:

| Case | Code | Params |
|---|---|---|
| A GPIO the board does not have | `pin.not_on_board` | `pin`, `board` |
| A reserved GPIO (0/1 on a Pi) | `pin.reserved` | `pin`, `physical` |
| A GPIO another element already has | `pin.in_use` | `pin`, `physical`, `other` (the element) |
| A GPIO of a bus with a device on it (2/3 with an I2C device) | `pin.claimed_by_bus` | `pin`, `physical`, `bus` |
| A PWM output on a pin without hardware PWM | `pin.function_unavailable` | `pin`, `physical` |
| Two PWM outputs on one channel (12 and 18) | `pwm.channel_in_use` | `pin`, `physical`, `other` |
| An I2C device on a bus the board does not have | `bus.not_on_board` | `bus`, `board` |
| An I2C device on a bus of another kind (`spi0`) | `bus.not_i2c` | `bus`, `board` |
| Two I2C devices at one address on one bus | `i2c.address_in_use` | `address`, `bus`, `other` |

Rules of the allocation:

- Boards are independent: GPIO 17 on two boards is fine.
- I2C devices are placed first, so a bus with a device claims the GPIOs of its signals before
  any element asks for them; GPIO 2 is free while nothing uses `i2c1`.
- Only the first problem of an element's pin is reported (a reserved pin is not also in use).
- Messages show `GPIO {pin} (pin {physical})`: the number elements use, and where it is on the
  header, from the profile.
- Issues come board by board, devices before the other elements, not in file order. The UI of
  phase 5 will sort what it shows by file and pointer.
- Which GPIOs a bus really claims when enabled is the hardware manager's (phase 6,
  `config.txt`); here a device on a bus means the bus is enabled.

`examples/invalid/` has one project per code, each kept giving exactly that code by a test.

## The Raspberry Pi 4 Model B (`rpi4b`)

- 40 pins: GPIO 0–27, two 3V3, two 5V, eight ground. GPIO 17 is physical pin 11.
- GPIO chip `pinctrl-bcm2711`; each GPIO on the line of the same number. PWM controller
  `fe20c000.pwm`, channel 0 on GPIO 12 or 18 and channel 1 on GPIO 13 or 19; which GPIO a
  channel is routed to is the overlay's (`pwm-2chan`: 18 and 19), the hardware manager's from
  phase 6; the runtime refuses a PWM output on a GPIO the kernel does not hold
  (`hal.pwm_not_routed`), since the signal would come out of the routed one.
- Pull at power on: up on GPIO 0–8, down on GPIO 9–27 (BCM2711 datasheet).
- Buses: I2C1 (SDA 2, SCL 3), SPI0 (MOSI 10, MISO 9, SCLK 11, CE0 8, CE1 7), UART0 (TX 14,
  RX 15). The other buses of the BCM2711 come with the hardware manager (phase 6).
- PWM: channel 0 on GPIO 12 or 18, channel 1 on GPIO 13 or 19.
- Reserved: GPIO 0 and 1, the I2C bus of the HAT EEPROM (ID_SD, ID_SC).
