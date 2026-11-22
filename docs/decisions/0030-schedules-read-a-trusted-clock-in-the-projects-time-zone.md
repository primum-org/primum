# 0030. Schedules read a trusted clock, in the project's time zone, once a minute

- Status: Accepted
- Date: 2026-11-22

## Context
Decision 0023 said what a schedule is for: a time is an instant, a window starts its
automations when it opens and when the engine starts inside it, and neither fires until the
board knows the time. It left how. The Pi 4 has no clock with a battery; a schedule's
"20:30" said nothing of where; and clocks jump: set late from the network, summer time, a
correction.

## Decision
- **The time zone is the project's**: `timeZone` in `project.json` (an IANA name), required
  when there are schedules, carried in the package. `core` reads no time zone data: the
  runtime turns its clock into the project's local time and hands `core` that.
- **The time is known when the system has set its clock from the network since boot**
  (systemd-timesyncd's `/run/systemd/timesync/synchronized`), or when the service is told
  to trust the clock (`--trust-clock`). Until then no schedule happens, and an automation
  that only acts during a window does not act.
- **`core` says whether a schedule happens between two looks** (`primum_core.schedules`):
  a time that was passed, a window that is open now and was not before, or, the first time
  the time is known, a window that is open.
- **The runtime looks as each minute turns**, and every 10 s while the time is not known.
  One timer, the one the controller already had.
- **A time is lost in any gap longer than 90 s**: the board off, the time not known, the
  clock jumped forward, the hour summer time skips.
- **A clock that goes back is waited for** (up to two hours: the hour summer time repeats):
  nothing happens again until it is past where it was. Further back, the time is taken as
  newly known.
- **A window is a condition through a field of the automation**, `during`: schedules that
  must all have a window open. Not a function of the expression language (decision 0028).
- **A window that crosses midnight belongs to the day it opens.** One that starts and ends
  at the same time is refused.
- **Nothing is remembered across a restart** (as in 0023): a service that restarts inside a
  window starts its automations again.

## Alternatives considered
- **The time zone of the board's system**: no change of format, but the same package would
  do different things on two boards, and a board is set up once, by whoever images it.
- **Working out the next instant and sleeping until it**: one wake per event instead of one
  a minute, but the sleep is on a monotonic clock and the instant on one that jumps; every
  jump and every change of summer time would need its own care. Looking once a minute and
  asking "what happened since I last looked" is the same code for all of them, and a wake a
  minute costs nothing.
- **Taking the time from a client** (a phone on the local network) when there is no
  Internet: needed for boards that never see one, but it opens who may set the clock of a
  board; with the app.
- **Asking systemd over D-Bus, or the kernel (`adjtimex`), whether the clock is
  synchronized**: more exact, and a dependency or a struct to keep right. The file is what
  systemd's own `time-wait-sync` waits for.
- **Firing late the times that fell in a gap**: a shop that opens its shutters at 09:40
  because the network came then is a surprise; a window says "be on while it is open" and
  does come back.
- **Once per window, kept on disk**: persistent state is block 4.4d, and what a window
  starts is usually "on, and hold", which starting twice does not hurt.

## Consequences
- `project.json`, `.auto` and the package gain optional fields (`timeZone`, `during`). A
  project with schedules and no `timeZone` stops being valid: both examples with schedules
  gained one.
- A board with systemd-timesyncd and no network never knows the time: its schedules never
  happen, and the state says so (`timeKnown`). A board with another time service (chrony)
  needs `--trust-clock`.
- `primum validate` knows only the time zones of the system it runs on.
- A package with schedules wakes the service once a minute for as long as it runs.
