# 0006. Events come from outside only; outputs are arbitrated by priority layers

- Status: Accepted
- Date: 2026-10-28

## Context
Several sequences, automations, manual controls and test mode can command the same output at
the same time. Without rules the result depends on timing, and with motors it is dangerous.
Events that sequences could emit would also allow loops (sequence → event → automation → sequence).

## Decision
- **Events (`.evt`) come only from outside**: sensors, buttons, time, the phone UI, external
  messages. **Sequences never emit events**; a sequence starts another sequence directly.
- Every element has **one arbiter, on the board it is wired to**. Order:
  1. panic, safe state and driver limits (nothing overrides them);
  2. manual control and test mode;
  3. sequences by priority layer; within the same priority the **latest command wins**.
- When a higher layer ends, the element returns to what the layer below says.
- Motors, servos and other risky elements are **exclusive**: one sequence owns them while it
  runs; others wait, are rejected or preempt according to priority. Motors never reverse
  instantly.
- Sequences can form **exclusive groups** and declare a **re-trigger policy** (restart, ignore, queue).
- The compiler warns about sequences that may overlap on the same element.

## Alternatives considered
- Latest command wins everywhere: unpredictable for layered scenes, unsafe for motors.
- Forbidding overlaps altogether: too restrictive for background plus foreground scenes.

## Consequences
- The engine needs a layered arbiter per element and the UI shows who controls each element.
- Drivers declare their default conflict policy.
