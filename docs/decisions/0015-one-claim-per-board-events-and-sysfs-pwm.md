# 0015. The runtime claims a board's lines at once; inputs are events; PWM through sysfs

- Status: Accepted
- Date: 2026-11-08

## Context
Phase 1's HAL requested one GPIO line per output, as outputs were created one by one. Phase 3
adds inputs and hardware PWM, and phase 4 an arbiter per board that needs to know every line
the board drives. libgpiod v2 requests have a fixed set of lines, and the deployment package
(phase 4) names every element up front.

## Decision
- **One claim per board.** `Hal.claim(Claim(outputs, inputs, pwms))` is called once with
  everything the runtime needs; the real HAL makes **one request per GPIO chip** with every
  line, and claims the PWM channels. A second claim is `hal.already_claimed`. Pins are checked
  against the board profile before anything is requested, so a bad claim leaves nothing behind.
- **Inputs are read and listened to.** `DigitalInput.read()` gives the state; the HAL reports
  every change as an `InputEvent` with the kernel's monotonic timestamp (`read_events`,
  `wait_events`), so nothing is missed between two reads. Pull and debounce come from the spec
  and are the kernel's (`bias`, `debounce_period`). Edges are reported in logical terms:
  `active_low` is applied by libgpiod.
- **Hardware PWM through sysfs** (`/sys/class/pwm`), the controller found by its **device
  name** from the board profile (`pwmChip.device`), never by `pwmchipN`. Levels are 0 to 1
  (`hal.duty_out_of_range` otherwise); the safe state is 0 %. Which GPIO a channel reaches is
  decided by the overlay: the hardware manager's (phase 6); until then `provision.sh` enables
  `pwm-2chan` on the development Pi.
- **The safe state is verified.** After writing it, the HAL reads every output back; a line
  that reads otherwise is `hal.safe_state_unverified`, apart from `hal.safe_state_incomplete`
  for writes that failed. What the hardware reports is what matters, not what was written.
  For a digital output the kernel reads the line itself; for a PWM output sysfs reports the
  setting the controller holds, not the pin, so that check is nominal.
- Two PWM outputs on one channel (GPIO 12 and 18 share channel 0 on a Pi 4) are refused in
  `claim` as `hal.pwm_channel_in_use`: the second export would succeed and both would drive the
  same channel, and the second release would fail. `core` refuses the same at validation
  (`pwm.channel_in_use`); the HAL defends itself anyway.
- The simulated HAL mirrors all of it: `simulate_input` queues events with a given timestamp,
  `stick` makes a line read back wrong, `wait_events` never waits (no clock in tests).

## Alternatives considered
- **Re-requesting on every new line** (release and request a superset): keeps the incremental
  API, but another process can grab a line in between, and outputs would be re-driven.
- **Polling inputs** instead of edge events: simple, but misses short presses between polls
  and costs CPU on a board that also runs sequences.
- **PWM through `/dev/gpiomem` or a userspace library**: fast, but it bypasses the kernel and
  breaks decision 0010 (no software sharing GPIO with Primum; the kernel sees every user).

## Consequences
- `Controller` passes every output at once; phase 4's package maps straight onto a `Claim`.
- A request failure names every pin it covered (`pins`), since the request is all or nothing.
- Hardware PWM needs the overlay before the service starts: a missing controller is
  `hal.pwm_chip_not_found`, with the hint to enable it. A freshly exported channel belongs to
  root until udev hands it to the `gpio` group (some 10 ms later on Raspberry Pi OS): the HAL
  waits for that, up to a second, before `hal.pwm_unavailable`.
- A claim that fails halfway (the GPIO request made, a PWM channel refused) releases what it
  got, so nothing is left behind and the HAL can claim again.
- `hw` tests take optional `PRIMUM_HW_INPUT_PIN` and `PRIMUM_HW_PWM_PIN`.
