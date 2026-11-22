# 0026. The controller arbitrates each output; the engine only says what the sequences ask

- Status: Accepted
- Date: 2026-11-22

## Context
Decision 0006 put each output under one arbiter with three layers: panic and the safe
state, then manual control and test mode, then sequences by priority. Until now only the
first two existed, and without sequences "returns to the layer below" meant "goes to rest"
(decision 0022). The service can load a package (decision 0025); it could not run one.

## Decision
- **The engine touches no hardware and reads no clock** (`primum_runtime.engine`). It keeps
  which sequences of the package are running and answers two questions for an instant it
  is given: what a given element is asked, and when that may next change. It runs the rules
  of decisions 0017 and 0023 on the package's commands, and a test holds it to `core`'s
  `command_at` and `runs` on random projects with random starts and stops.
- **The controller is the arbiter.** For each output, from the top: panic (rest); what a
  person asked (a command of the API); what the engine says; otherwise rest. It writes an
  output only when the level it should be at changes.
- **A command without a duration is manual control**: it stays over the sequences until it
  is released (`DELETE /api/outputs/{id}`) or panic. With a duration it is a test and
  expires. One or the other per output: a command replaces the one before. Either way,
  when it ends the output goes to what the sequences say, and to rest only if they say
  nothing.
- **Panic stops every sequence**, ends all manual control and every test, and nothing starts
  until it is released. Releasing it brings nothing back.
- **The engine works only at changes.** One timer of the event loop, the one test mode
  already had, armed for the next thing due: a test that runs out, a command of a running
  sequence that starts or ends, an output to be tried again. Between two changes nothing
  runs.
- **An output that cannot be taken where it should be does not stop its sequence**, nor the
  other outputs: it is logged once, its state says so, and it is tried again every 5 s, as
  an output that could not rest already was.
- **Sequences are started and stopped through the API** (`POST
  /api/sequences/{id}/start`, `/stop`) until events and automations exist (block 4.4). The
  state lists the sequences of the package, which are running, and who commands each output.
- **Not yet, on purpose** (block 4.3c): a `fade` jumps to where it ends, as it does when
  asked through the API, and an argument read from a variable takes its initial value.

## Alternatives considered
- **Manual control that always expires**: nothing would be left held by forgetting it, and
  "turn this on and leave it" would need a sequence.
- **Stopping a sequence when one of its outputs fails**: one LED that does not answer would
  turn the rest of a show off.
- **A fixed step** (every 20 ms while something runs): times rounded to the step and a
  processor kept awake for nothing, until there are fades to move.
- **The engine asking `core`'s `command_at` over the package**: one rule in one place, but
  `command_at` works on clips of a project, and the package carries commands; an engine of
  its own, held to the oracle by a test, keeps the package the only thing the runtime needs.

## Consequences
- `restFailed` now says more than its name: the output could not be taken where it should
  be, to rest or to what a sequence asks. The page's text for it still speaks of a test.
- A manual command that fails is not held: the output is taken to what the layers say the
  next time the controller has something to do, not at once and not on a timer of its own.
- Exclusive elements (motors, servos) have no driver yet: an exclusive driver's rule (one
  sequence owns it while it runs) is written in decision 0006 and built with the first one.
- A sequence that restarts or ends is not told apart in the state from one that never ran:
  the trace (block 4.5) says what happened.
