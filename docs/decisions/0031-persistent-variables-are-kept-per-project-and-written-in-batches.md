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
- **The write is off the event loop, whole and renamed into place, and synced**, the
  directory too. A write waits for the card, and panic must never wait behind it; a power
  cut leaves the file before or the file after, never half of one. Writes land in the
  order they were asked for: one that gets to the card after a later one writes nothing.
- **What is kept is not replaced by values that drop some of it without a copy left
  beside it** (`variables.json.bak`): another project's values, a file that could not be
  read, a value a new package no longer takes. A package put back (block 4.5) must be able
  to find its counter; how it does is that block's to say.
- **On stopping, the last save is made before the outputs are made safe.** It is a write
  of milliseconds. A card that hangs would hold the stop until systemd's `TimeoutStopSec`
  ends it and `primum-safe` makes the outputs safe: the same net as for any hang. Saving
  after the HAL closes would need the service to outlive its own shutdown.
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
- A power cut loses the changes of about the last second: the second a change waits, and
  the time the card takes to take the write.
- Nobody but the log and the API's state sees that the values are not kept
  (`variablesUnsaved`): the page of the runtime does not show it. For the UI of phase 5.
- Only the last file set aside is there: a second replacement writes over the copy.
- Deleting `variables.json` (or putting another project on the board) starts every
  variable at its initial value: that is the way to reset them until the UI has one.
- The data directory must be writable for persistent variables to be kept; when it is not,
  the service runs all the same and says so.
- "Once per window across restarts" (decision 0030) could use the same file; it is not
  done.
