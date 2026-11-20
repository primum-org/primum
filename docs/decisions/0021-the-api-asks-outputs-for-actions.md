# 0021. The API asks an output for an action of its driver

- Status: Accepted
- Date: 2026-11-20

## Context
The API of phase 1 (decision 0011) turned an output on or off: `PUT /api/outputs/{name}`
with `{"on": true}`, and a state of `{"name", "on"}` per output. With PWM outputs offered by
the service (block 3.4b) an output also has a level, and the `Controller` already commands
outputs with the actions of their drivers' manifests (decision 0019).

## Decision
- **A command is an action of the output's driver, with its arguments by name**:
  `{"action": "on"}`, `{"action": "set", "arguments": {"level": 40}}`. One form for every
  output and every driver; `{"on": true}` is gone.
- **The state says what each output can be asked for**: `name`, `on`, `level` (0 to 100) and
  `actions`, the names of its driver's actions. The page shows a level for an output that
  can be `set`, without knowing its type.
- **What the caller got wrong is a 422**, with the code and the params the driver gives: an
  action the output does not have, an argument it does not take, one that is missing, of
  another type or outside its limits. An output that does not follow a command stays a 500.
- **The page asks for a level once, on letting go of the slider**, not while it moves.

## Alternatives considered
- **Widening the old body** (`{"on": true}` or `{"level": 40}`): enough for the page today,
  and a second vocabulary next to the manifests' that every new driver would have to extend.
- **The element's type in the state**, for the page to decide what to show: the page would
  then know what each type can do, which is what manifests are for.
- **Sending the level while the slider moves**: the light follows the finger, at the price
  of bursts of writes to the hardware and of answers that arrive out of order.

## Consequences
- This changes the API of decision 0011: a client of the old body gets `request.invalid`.
  There are no clients but the page, which ships with the service.
- `fade` can be asked through the API and, as an instant command, jumps to its `to`. Fades
  in time come with the engine (phase 4).
- The API still has no authentication (decision 0011): now a level can be set by anyone on
  the local network, as on and off already could. LEDs only until phase 5.
- A new driver's actions reach the API and the state with no change to either.
