# 0031. Persistent variables are kept per project, and written a moment after they change

- Status: Accepted
- Date: 2026-11-22

## Context
A variable may be marked `persistent`; the mark travelled in the package and the runtime
ignored it: every variable went back to its initial value when the service started. A
counter of visits or a brightness set from the phone was lost with a restart or a power
cut. Keeping them raises what the mark leaves open: whose the values are when the package
changes, what a value is worth when its variable changed, and how often a card is written.

## Decision
- **The values belong to the project.** One file in the data directory
  (`variables.json`), with the id of the project and the value of each persistent variable
  by its id. A new package of the same project finds them; another project does not take
  them, and starts at its initial values.
- **A kept value that its variable no longer takes gives way to the initial one**, logged:
  a new package may have changed the type or the limits. The other variables keep theirs.
- **A change is written a moment later, not at once**: the first change arms a timer of a
  second, and what the values are then is written. However often a counter changes, the
  card sees one write a second. When the service stops, what is pending is written first.
- **The write is off the event loop, whole and renamed into place, and synced.** A write
  waits for the card, and panic must never wait behind it; a power cut leaves the file
  before or the file after, never half of one.
- **Nothing here stops the service.** A file that cannot be read gives no values. A write
  that fails is logged once, told in the state (`variablesUnsaved`) and tried again every
  30 s.
- **The controller keeps nothing on disk.** It starts from the values it is given, says
  which are worth keeping and repeats in the state how keeping them went. Who writes is
  the service, as with the timer.
- **Panic does not touch variables**, kept or not.

## Alternatives considered
- **Per package (by its hash)**: any new package, a fixed typo included, would start every
  counter again. The id of a variable is stable across packages; that is what ids are for.
- **Clamping a kept value to the new limits**: a brightness of 80 under a new maximum of 50
  becoming 50 looks right, but a type that changed has nothing to clamp to, and two rules
  are harder to tell a person than one. The initial value is what the project says the
  variable is worth when nothing else is known.
- **Writing at every change**: nothing lost in a power cut, and a card worn by a counter on
  a button. A second is less than a person notices.
- **Writing on the event loop**: simpler, and an `fsync` on an SD card can take tenths of a
  second, with panic waiting.
- **A file per variable, or a small database**: more files to keep whole, or a dependency,
  for a handful of values.
- **A schema in `schemas/` for the file**: it is the runtime's own, like what it declares
  for `primum-safe`, not a format of projects that other tools read.

## Consequences
- A power cut loses at most the changes of the last second.
- Deleting `variables.json` (or putting another project on the board) starts every
  variable at its initial value: that is the way to reset them until the UI has one.
- The data directory must be writable for persistent variables to be kept; when it is not,
  the service runs all the same and says so.
- "Once per window across restarts" (decision 0030) could use the same file; it is not
  done.
