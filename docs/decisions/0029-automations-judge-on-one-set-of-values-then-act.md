# 0029. Automations judge on one set of values, then act; inputs declare what they tell

- Status: Accepted
- Date: 2026-11-22

## Context
The runtime ran the sequences of a package only when the API asked. Conditions had a
language and a compiled form (decision 0028) that nothing evaluated. Inputs were read, with
their edges, and only shown. Automations need rules for what the files leave open: several
automations on one event, a condition that fails, an increment past a limit, an action that
fails, panic, and who may make an event happen.

## Decision
- **Conditions first, all on the same values; then actions.** When an event happens, the
  condition of every automation that waits for it is worked out on the values the variables
  had at that moment. Then those that hold act, in the order of the package. Which act does
  not depend on their order.
- **`core` says which automations act; the runtime does their actions.** The rule is pure
  (`primum_core.automations`) and tested without a board. The controller starts and stops
  sequences through the engine and keeps the variables. An automation never writes an
  output.
- **A condition that cannot be worked out does not hold**, and is told
  (`automation.condition_failed`): in the log and in the automation's state.
- **An increment stays at the limit it would pass.** It is one operation on the value.
- **An action that fails does not stop the ones after it** (`automation.action_failed`),
  as an output that fails does not stop the others (decision 0026).
- **While panic is on, events start nothing and are not kept.** Firing one by hand is
  refused.
- **Only `ui` and `api` events are fired by hand.** An event of an element happens when the
  element says so: a request cannot pass for a sensor.
- **A driver declares what its element tells** (`triggers` in its manifest), as it declares
  the actions it takes. An event may only wait for one of them; `core` checks it in the
  project and the runtime in the package.

## Alternatives considered
- **Automations one after another, each seeing what the one before changed**: the result
  would depend on an order nobody chose (the package sorts by id). "If there is room,
  welcome; if it is full, close" would do both on the visit that fills the shop.
- **A failed condition counts as true**, or **disables the automation**: the first moves
  hardware on a mistake; the second stops something that may work again a moment later
  (a divisor that is zero only now).
- **An increment past the limit is refused**, or **wraps around**: a counter that stops
  counting one short of its maximum, or a full shop that reads as empty.
- **Stop at the first action that fails**: the ones before are already done, so the
  automation would be left half done either way; doing the rest is the smaller surprise.
- **Queue events during panic and replay them**: outputs moving on their own the moment
  panic is released, for things that happened minutes ago.
- **Any event can be fired through the API**: handy to test without touching the sensor,
  but the test mode already commands outputs, and what a sensor says should be the sensor's.
- **`core` knowing which element types are inputs** (a list in code): it already has one,
  for references; the manifest says what each tells, which a list cannot (a sensor that
  only tells `on`).

## Consequences
- The driver manifest has a new optional field, `triggers`. Manifests without it are still
  valid: `schemaVersion` stays.
- The state of the API has `events`, `automations` and, on each input, `lostEvents`.
- Schedules (4.4c) only have to make their own events happen: the rules above are theirs
  too.
- An automation's actions run on the event loop, in the reading of the inputs: they must
  stay cheap. They are: starting a sequence is a list operation, the outputs settle once
  per reading.
- Debounce is the input's (its driver's `debounceMs`, in the kernel), not the event's.
