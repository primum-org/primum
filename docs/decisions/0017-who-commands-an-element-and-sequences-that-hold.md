# 0017. One rule says who commands an element; a sequence can hold until it is stopped

- Status: Accepted
- Date: 2026-11-13

## Context
Decision 0016 said in prose what a clip does to its element. It was rewritten four times in
its own pull request, no test held it, and two of its sentences disagreed: "a clip with a
length plays over the standing command" and "the command that started last wins" say
different things about an instant command that falls inside a clip. They only agreed because
`track.clips_overlap` refused that case, which also refused what the decision itself advised
(an instant `off` where a `fade` ends, with another clip starting there).

And nothing could be left on. Nothing a clip does outlives its sequence, and a sequence ends
with its last clip, so "turn the light on at dusk and off at 23:00" needed a clip whose length
was worked out by hand. What people write first, a sequence *On* with an instant `on` and a
sequence *Off* with an instant `off`, did nothing.

## Decision
- **A command is in force while it lasts.** A clip with a length, for its length. An instant
  command (a clip of 0 ms), until the next instant command of that element in its own
  sequence, the one it is written in, or until that sequence ends: the block, when it is
  included. A sequence does the same included as started on its own.
- **One rule says who commands an element**: of the commands in force on it, those of the
  highest priority count (decision 0006), and among them **the one that started last wins**,
  within a sequence as between sequences. Two that started in the same instant: a clip with a
  length wins over an instant command, then the sequence that was started last. With nothing
  in force, the element is in its driver's safe state.
- What follows from it, and is not a rule of its own:
  - a clip that starts after an instant command plays over it, and when it ends the element
    goes back to that command: `on` at 0 s and `set(30)` from 5 to 6 s is on, dimmed for a
    second, on again;
  - an instant command inside a clip cuts it: an `off` at 5.5 s inside a clip from 5 to 6 s
    turns the element off at 5.5 s;
  - an instant command and a clip that start together: the clip plays, then the element goes
    to the instant command;
  - to leave an element somewhere else after a clip, an instant command goes where the clip
    ends (a `fade` to 0, then an instant `off`).
- **A sequence can hold** (`whenDone`: `end`, the default, or `hold`). One that holds does not
  end with its last clip: it stays as it is in its last instant until it is stopped. Every
  command in force just before its end stays in force: its standing commands, and the clips
  that end with it, each in the state its action ends in (a `fade` from 0 to 100 that ends
  the sequence leaves the lamp at 100). A clip that ended earlier is not kept.
- A sequence that holds is stopped as any other: an automation (`stop_sequence`), another
  sequence of its exclusive group starting, stop and panic. Nothing outlives its sequence
  still. `whenDone` is ignored when the sequence is included in another: a block ends with the
  last clip of what it includes.
- **The rule runs**: `primum_core.commands.command_at` says which command is in force on an
  element at an instant, given the sequences that are running and when each started. Its
  tests are the specification the engine (phase 4) must meet.
- **The checks follow the rule.** An instant command and a clip with a length do not compete,
  so `track.clips_overlap` is only two clips with a length that overlap, or two instant
  commands of one element in one instant. `clip.instant_at_end` is an instant command that is
  the last thing of its own sequence, started on its own or included, unless the sequence
  holds.

This supersedes, in decision 0016: what an instant command lasts, the rule of who commands an
element, and that an instant clip takes its instant against clips with a length. The rest of
0016 stands: manifests, a clip holding its action while it lasts, the safe state, arguments by
name, exclusive drivers.

## Alternatives considered
- **A clip always over the instant commands of its own sequence**: two rules, one within a
  sequence and one between sequences, and an `off` dropped inside a clip would do nothing
  until the clip ends.
- **Holding only the standing commands**: a clip that ends with the sequence would give its
  element back, so "fade in and stay on" would need an instant `on` where the fade ends, easy
  to forget and impossible for `core` to warn about yet.
- **An automation that commands an element directly** ("turn the lamp on"): a state outside
  the sequences that nobody releases; stop, panic, priorities and exclusive groups would each
  need a second meaning.
- **A boolean `hold`**: shorter, but a sequence that starts again when it ends (a loop) would
  need another field and a rule for the two together. `whenDone` takes a third value.
- **A warning for a sequence that holds and that nothing stops**: it may be meant (lights
  always on), and `core` does not know everything that can stop it (the phone UI and the API
  of phase 5, another sequence of its exclusive group).

## Consequences
- "On at dusk, off at 23:00" is one sequence that holds, started by one automation and
  stopped by another (`examples/evening-lights`).
- The engine has a pure function to agree with, and what the reviews found has a test each.
- To hold a clip "in the state its action ends in" a driver must know that state (block 3.3,
  where manifests declare it). With it `core` can also warn about the trap that stays: a
  `fade` to 0 in the middle of a sequence gives its element back to a standing `on` unless an
  instant `off` follows it.
- `command_at` does not know who stops a sequence: its caller says which are running.
  Exclusive groups, the re-trigger policy and exclusive drivers are the engine's (phase 4).
- A loop is a third value of `whenDone`, decided with the re-trigger policy.
