# 0032. The trace is decisions, kept in memory, each with what led to it

- Status: Accepted
- Date: 2026-11-22

## Context
Since automations and schedules, a board does things on its own. Why a light came on, or
did not, was only in the journal, as lines of text for whoever can read a terminal. Phase 4
is done when what a sensor starts "shows in the trace".

## Decision
- **An entry is a decision**: an event that happened, what each automation it concerned did
  (acted, did not, failed), a sequence that started, was stopped or ended, a variable
  changed, what a person commanded, panic. Not the level of an output at each instant, nor
  the steps of a fade.
- **A kind and params, never text**, as errors are (decision 0009). The texts are the UI's.
- **Each entry names what led to it** (`cause`, the number of another entry): the event
  for an automation, the automation for the sequence it started. "Why" is a walk back.
- **The controller notes them where it decides**, in a trace it owns
  (`primum_runtime.trace`). Sequences that start and end are found by comparing what runs
  before and after each thing it does, not by asking the engine to tell.
- **In memory, the last 1000**, numbered from 1. Nothing on the card.
- **Read by number**: `GET /api/trace?after=n`, and a WebSocket that sends what is kept and
  then what is new. A client that falls behind is sent what is kept above what it has;
  `first` tells it if some was dropped.

## Alternatives considered
- **Every change of every output**: complete, and a fade writes fifty a second. The state
  already says where each output is and who commands it.
- **The log as the trace**: it exists, and it is text, in one language, with no ids to
  follow and no way to ask "what led to this".
- **On disk, with rotation**: it would survive a restart, at the price of writes to the
  card for something that is mostly looked at while it happens. The journal covers the
  rest.
- **A tree of events with their consequences nested**: what a UI may show, but harder to
  page through and to cut at 1000. Numbers and a `cause` say the same and stay flat.
- **The trace inside the state**: every state message would carry a thousand entries.

## Consequences
- A restart of the service empties the trace.
- A burst of 1000 entries (a stuck sensor bouncing) pushes out what came before.
- Every place the controller decides something has a line that notes it; a new kind of
  decision must add its own.
- The kinds are a public contract, like error codes: adding is free, renaming breaks who
  reads them.
