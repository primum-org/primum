# 0028. Conditions are a small language, compiled to a program without jumps

- Status: Accepted
- Date: 2026-11-22

## Context
An automation's `if` was stored as text and never read: any word in it that matched a name
counted as a use, even inside a text, and the package carried the text with its names
unresolved. Before the engine can run automations (block 4.4b) the condition needs a
grammar, checks that tell a person what is wrong before deploying, and a form a board can
run without parsing anything.

## Decision
- **Words for logic, in English**: `and`, `or`, `not`, `true`, `false`. Comparisons
  (`== != < <= > >=`), parentheses, numbers and texts in double quotes.
- **Arithmetic from the start**: `+ - * / %` and `-x`. `/` always gives a number with
  decimals; the rest give an integer from integers. `%` has the sign of the divisor.
- **Typed, and checked before deploying**: the four types of constants and variables.
  Integers and numbers mix; nothing else converts. A condition must give a boolean. A
  division by a zero that can be seen (written, or a constant) is an error of the project.
- **No calls, no assignment, no loops.** Windows of time are not a function of the
  language: an automation will name them in a field of its own (block 4.4c).
- **A board runs a compiled program, never the text**: steps in postfix order for a stack,
  constants inlined, variables by id. No jumps: each step runs once. Reading a package
  checks every program (stack, types, variables), since a hash is not a check
  (decision 0024).
- **One kind of number when evaluating: a double.** `integer` and `number` only matter to
  the checks; the package does not tell `3` from `3.0`.
- **What cannot be worked out is a failure, not an exception**: a division by zero, or a
  result of arithmetic that is not below 2^53 in size. The limit is on the value, not on
  how it is held or declared, so any runtime that works in doubles gives the same answer. `and` and
  `or` ignore a failed side when the other side settles the answer, whichever side it is.
- **One comparison, not a chain**: `1 < x < 5` is refused rather than read in a way a
  person does not expect.
- **Bounded**: 500 characters, 32 levels of nesting.

## Alternatives considered
- **Symbols (`&&`, `||`, `!`)**: familiar to programmers, who are not who Primum is for.
- **Words in the language of the UI** (`y`, `o`, `no`): a project would stop being readable
  on another person's machine; the file formats are English everywhere.
- **Comparisons and logic only, arithmetic later**: smaller now, but adding types of
  results, division and overflow later would change the compiled form already deployed.
- **Windows as a function** (`in_window("Open")`): the only call in the language, and a
  name inside a text that nothing can check or rename. A field with ids follows the rule
  that files reference each other by id.
- **Carrying the tree in the package**, evaluated by recursion: a hand-made package could
  nest it without bound. A flat program is checked in one pass and run in one loop.
- **Short-circuit by jumps**: guards would work only written on the left, and the program
  would need jump targets to check. Deciding `and`/`or` from both sides costs working out a
  side that is not needed, which in a language without calls costs nothing that matters.
- **Overflow by the declared type** (only integers have the limit): every step of the
  package would have to carry its type, and a constant `3.0` is already written `3`.
- **Overflow only when not finite**: whole numbers past 2^53 would round in silence and a
  counter compared with `==` would lie.
- **Raising on a division by zero**: every caller would have to catch it; a value that says
  why is harder to forget.

## Consequences
- The package format changed: `automations[].if` is an array of steps, not a string. No
  package is deployed anywhere yet, so `schemaVersion` stays and there is no migration.
- A project whose condition does not parse or does not fit its names is now invalid: before,
  any text passed.
- The engine (4.4b) only needs `evaluate` and a rule for a failure: the condition does not
  hold, and the user is told.
- Adding a function later means a new kind of step, and a bump of the package's version.
