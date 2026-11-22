# 0027. A fade moves in steps of the clock; a variable is read when its command starts

- Status: Accepted
- Date: 2026-11-22

## Context
The engine ran the sequences of a package (decision 0026) with three things left out. A
`fade` jumped to where it ends. An argument read from a variable took the variable's initial
value, since nothing could change one. And the engine walked every command of every running
sequence at each change: measured on the Pi 4 by its owner, 7 ms per change with 8 outputs
of 100 clips and 539 ms with 16 of 2000, all of it on the event loop, where panic waits too.

## Decision
- **What a sequence asks is worked out once**, when the package is loaded: per element, the
  instants at which it changes and what is asked from each. Asking is a search. A change
  costs the same whatever the length of the show.
- **A fade moves its output in proportion to the time gone by**, linearly, from where its
  clip starts to where it ends. The level is always worked out from the clock, never added
  up step by step: a step that comes late goes to where the fade is by then.
- **It is stepped every 20 ms, and only while something moves.** The one timer of the
  service is armed for the next step when an output is being moved by a sequence; the rest
  of the time it still waits for the next change. Listeners are told of a fade four times a
  second, not at every step, and when it ends.
- **A `fade` without its `from` starts from the level the output has** when the command
  first commands it: whatever took it there, a sequence, a person or rest. It is what a
  person sees. When it was a command of a sequence that had the output, that is the level
  that command had it at in that very instant, its end if its action was over, and not the
  last step that happened to be written: a fade stepped every 20 ms is rarely written at its
  last instant, and up and straight back down is what a show does most. Under a person's hand the fade goes on unseen from the level it found, and
  when the output is let go it is where the fade is by then.
- **A variable is read when its command first commands its output, and kept while the
  command lasts.** A fade has a fixed start and a fixed end. Setting the variable shows the
  next time a command that reads it starts.
- **A value set to a variable is of its type and within its limits, or it is refused**
  (`variable.value_invalid`, `variable.value_out_of_range`) and nothing changes. A clip that
  reads a variable counts on its limits (decision 0024): this is what holds them while
  running. Variables are set through the API (`PUT /api/variables/{id}`) until automations
  exist (block 4.4).
- **Every variable starts at its initial value** when the service starts. Keeping the ones
  marked `persistent` across a restart comes with the automations that change them.

## Alternatives considered
- **Following a variable while its command lasts**: moving a setting would move the lamp at
  once, and a fade whose end changes half way needs a rule of its own. It can be added
  without breaking what is decided here.
- **Clamping a value to the limits**: a mistake of whoever asks would pass in silence.
- **A fade from what the layer below says**, not from the level the output has: purer for
  the engine, and a visible jump when a person has just let go.
- **A fixed step always**, not only during fades: a processor kept awake for a show that
  only switches things.

## Consequences
- "When its command starts" is, exactly, when the command first commands its output. A
  command that starts while a higher priority has its output reads its variables, and takes
  the start of its fade, when it gets the output.
- A fade to 0 over a held sequence still gives the lamp back to it when it ends (the trap
  `core` warns about): the engine does what the project says.
- Each step is a write and a read-back of the output. How smooth 50 steps a second look on
  a real LED, and what they cost on the board, is to be seen there.
- Other curves than a straight line would be an option of the action, later.
