# 0023. Starting a running sequence restarts it; a window brings back what a restart lost

- Status: Accepted
- Date: 2026-11-21

## Context
Decision 0017 says who commands an element given the sequences that are running, and left
which ones are running to the engine. Decision 0006 named the pieces (exclusive groups, a
re-trigger policy of restart, ignore or queue) without saying what any of them does. Three
cases, all of them what people write first, had no answer:

- *On* and *Off*, two sequences that hold, each started by its own automation. The first day
  *Off* started last, so it wins. The second day, *On* is started while it is still running.
- *Off* as a `fade` to 0 over an *On* that holds: when the fade ends the lamp goes back to
  *On*, at 100.
- A sequence that holds, started at 19:00 by a schedule, and the board restarting at 20:00.

## Decision
- **A sequence that does not hold stops running when its last clip ends.** One that holds
  runs until it is stopped.
- **Starting a sequence that is already running restarts it**: it begins again from its
  first instant and counts as started last. So *On* and *Off* work day after day with nothing
  else written.
- **A sequence can ask to ignore that** (`whenStartedAgain`: `restart`, the default, or
  `ignore`): started while it runs, nothing happens. For a sequence that must not begin
  again half way, like a presence sensor firing twice during a fade in. Once it has ended,
  starting it starts it.
- **Starting a sequence stops the others of its exclusive group**, whatever their priority
  and whether they hold. Fading out is *On* and *Off* in one group: starting *Off* stops
  *On*, and when the fade ends nothing commands the lamp, which is in its safe state.
- **Stopping a sequence that is not running does nothing.**
- **Nothing is remembered across a restart.** When the engine starts (the board boots, the
  service restarts, a package is activated) no sequence is running and every element is in
  its safe state.
- **A schedule's window starts automations when it opens, and when the engine starts inside
  it.** A time of day ("at 19:00") is an instant: if the board was off then, it is lost. A
  window ("from 19:00 to 23:00") is a stretch: an automation started by it runs when the
  window opens, or as soon as the engine starts and finds itself inside. Which one a light
  needs is the user's choice, visible in the schedule. Both need a reliable clock: until the
  board knows the time, neither fires.
- **The rules run**, like decision 0017's: `primum_core.runs` (`start`, `stop`,
  `still_running`) keeps the list of running sequences that `command_at` reads. Its tests are
  the three cases above.

## Alternatives considered
- **Ignoring by default**: the second day *On* is still running, the start is ignored, *Off*
  remains the one that started last and the lamp stays off for ever. A test keeps this.
- **Queueing** (the third policy of decision 0006): it needs a queue, its limit, and what
  stopping does to what waits. Nothing asks for it yet; `whenStartedAgain` takes a third
  value when something does.
- **Remembering which sequences were holding**: a power cut from 20:00 to 02:00 would light
  the lamp that should have gone off at 23:00, and writing state on every start wears the
  card.
- **Running the schedule times missed while off**: it brings the lamp back, and also rings
  at 13:00 the bell that was for 12:00.
- **Recovering nothing**: simplest, and a blink of the mains leaves a shop window dark until
  the next day.

## Consequences
- `examples/evening-lights` starts its lamp from a window, so a restart at 20:00 lights it.
- Windows keep being conditions too (`if`, with the expression language).
- The engine keeps no state on disk for sequences. Persistent variables are another matter.
- For the events and schedules block: what "the engine starts inside a window" does when the
  clock becomes reliable late, windows that cross midnight, and whether an automation fires
  once per window. `specs/events.md` says it then.
- Not warned about yet: a sequence that ignores being started again, holds, and shares an
  element with another on its priority is the first case with the wrong answer.
- Exclusive elements (motors, servos) and priorities between sequences that wait or preempt
  are still to decide, with the arbiter.
