# 0022. A test is a command that expires; the arbiter waits for the engine

- Status: Accepted
- Date: 2026-11-20

## Context
Decision 0006 puts manual control and test mode in one layer, above sequences and below
panic, and says an element returns to the layer below when a higher one ends. Block 3.4 asked
for test mode: manual commands that expire on their own. But there is no layer below yet:
sequences come with the engine (phase 4), and until then a command goes straight to its
driver and stays.

## Decision
- **A test is a command with a duration.** When it runs out, its output goes to rest: the
  safe-state action of its driver. From 1 s to 5 min.
- **Only a command that asks for it expires.** Without a duration a command stays, as before:
  until there are sequences, it is the only way to leave something on.
- **No arbiter yet.** "Goes to rest" is what "returns to the layer below" means while that
  layer is empty. The arbiter is built with the engine, with what it has to arbitrate.
- **The controller keeps the deadlines, the event loop keeps the time**: one timer for the
  next deadline, on the monotonic clock, injected so that tests move it by hand.
- **On the page, a *Test* button per output**: on for 10 s, then off. The switch and the
  slider go on doing what they did.
- **An output that cannot be sent to rest when its test expires is tried again** and says so
  in its state: it is the one thing test mode promises not to leave on. A log line alone
  would be read by nobody.

## Alternatives considered
- **Building the layered arbiter now**, with the layer of sequences empty: the design of the
  arbiter without its main user, which the plan places in phase 4. Three blocks of this phase
  fixed semantics before anything ran them, and each was rewritten.
- **Every manual command expires**: safer by default, and nothing could be left on until
  phase 4.
- **A test mode for the whole page**, in which the switch expires: fewer buttons, and one
  control that does two things.
- **The page turning the output off itself after a while**: a closed tab would leave it on.

## Consequences
- With the engine, expiry changes from "rest" to "what the layer below says", and a command
  without a duration becomes manual control, which the arbiter must also place. Both are
  noted in the plan for phase 4.
- A test is not held anywhere but in the process: if the service dies, `primum-safe` makes
  the output safe (decision 0020).
- The API still has no authentication (decision 0011): anyone on the local network can start
  a test, as they can any command.
