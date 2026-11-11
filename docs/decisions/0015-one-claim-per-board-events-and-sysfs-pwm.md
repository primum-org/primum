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
  changes as `InputEvent`s with the kernel's monotonic timestamp (`read_events`,
  `wait_events`), so a short press between two reads is seen. The kernel keeps a bounded
  number of unread events and drops the oldest of a longer burst (60 unread changes gave 32 on
  the Pi): the state is always right, a count of presses may not be. Pull and debounce come
  from the spec and are the kernel's (`bias`, `debounce_period`). Edges are reported in logical
  terms: `active_low` is applied by libgpiod.
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
- A request failure is `hal.request_failed` naming every GPIO it covered (`pins`): the request
  is all or nothing and the kernel does not say which line it refused.
- A PWM output on a GPIO the kernel does not hold is `hal.pwm_not_routed`: on a Raspberry Pi
  the overlay that routes a channel to a GPIO makes `pinctrl` hold that line, so a free line
  means the signal would come out of another GPIO (channel 0 on 18, not 12, with `pwm-2chan`).
  It is an inference from the Pi's behaviour; the hardware manager (phase 6) will know which
  overlay is on.
- Hardware PWM needs the overlay before the service starts: a missing controller is
  `hal.pwm_chip_not_found`, with the hint to enable it. A freshly exported channel belongs to
  root until udev hands it to the `gpio` group (some 10 ms later on Raspberry Pi OS): the HAL
  waits for that, up to a second, before `hal.pwm_unavailable`.
- A claim that fails halfway (the GPIO request made, a PWM channel refused) releases what it
  got, so nothing is left behind and the HAL can claim again.
- A channel left exported by a crash is adopted: disabled, duty cycle to 0 and only then the
  period (the kernel refuses a period shorter than the duty cycle it holds), then enabled.
- The polarity of a channel is set to `normal` at the claim: it outlives an unexport, and
  inversed it turns 0 % into a pin held high, also after the release. `read()` reports the level
  the pin gets (1 − duty when inversed), and writing 0 % or releasing puts an inversed polarity
  back, so a polarity inverted while the runtime runs is corrected by the safe state, not only
  noticed. Only those two correct it: at any other level an inversed polarity shows in `read()`
  and nothing more, since checking it on every change of level would slow fades down to guard
  against another program on a board that is Primum's alone (decision 0010; `primum-safe` and
  `check-gpio-users.sh` in 3.4 are where that is handled).
- What is known of the kernel comes from the Pi (6.18): a channel not used since boot is
  exported with period 0 and takes the writes before the period; a later export keeps the last
  period and polarity; the line of a routed PWM GPIO is marked as used. Other kernels have not
  been checked: one that did not mark the routed line would make every PWM claim fail as
  `hal.pwm_not_routed`, which the `hw` tests would show.
- `hal.safe_state_incomplete` names in `pins` every output not confirmed safe: those whose
  write failed and those that read back wrong (`unverified_pins`), so the report leaves out
  nothing that may still be on.
- Releasing a PWM channel tries every step (0 %, polarity, disable, unexport) even if one
  fails: disabling is what turns the output off.
- `hw` tests take optional `PRIMUM_HW_INPUT_PIN` and `PRIMUM_HW_PWM_PIN`.
