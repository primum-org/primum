# 0024. The deployment package is flat JSON with its hash; a value may come from a name

- Status: Accepted
- Date: 2026-11-21

## Context
The runtime must never see a project's folders, scopes or components: it receives a flat,
validated deployment package. Until now the package was a word in the plan. And three things
a project could not say were waiting for the compiler: a clip that takes the value of a
component's parameter or of a variable (`examples/shop-window` showed a `times` parameter and
a `brightness` setting that did nothing), and a `fade` "from where it is", since `fade`
required its `from`.

## Decision
- **A package is one JSON file with a schema of its own** (`schemas/package.schema.json`),
  compiled by `core` (`primum_core.compiler`) from a project that passed every check, for
  **one board**. A project without a board, or on several, validates and does not compile
  (`package.no_board`, `package.several_boards`): splitting a project between boards comes
  after version 1.
- **It carries its own hash**: the sha256 of the rest of it in the canonical form of RFC 8785
  (keys sorted, no spaces, UTF-8, numbers as JavaScript writes them), so the UI computes it
  with `JSON.stringify`. The same project always gives the same bytes: nothing of when or
  where it was built is in it.
- **A hash is not a check.** It tells a file cut short or edited; a package built wrong has a
  right one. Reading a package checks its shape, its hash and that it holds together: ids,
  references, the fields of each case, and everything about its variables (their limits,
  their initial value, what automations set), since the safety of an argument that reads a
  variable rests on those limits holding. The runtime checks the rest when it loads it, with
  its drivers and its board: only a manifest says what a parameter takes. Nothing trusts a
  package for being one.
- **Sequences travel as commands, not clips.** The compiler expands components and applies
  the rule of decision 0017: each command says its element, when it starts, how long its
  action lasts and until when it is in force (no end: what a sequence that holds keeps). The
  engine picks, among the commands in force, the highest priority and then the one that
  started last; it never works out again what replaces what. A randomized test holds a
  reader of the package to `command_at`.
- **Nothing is left to look up.** Only sequences that can be started are in it (a component
  is inside the ones that include it); every element has every option of its driver and every
  command every parameter of its action, defaults included; an automation names its variable
  by id. No constants: they are in place.
- **An argument is a value or a name** (`valueOf`), in a clip and in a block: a value
  parameter of the sequence it is written in, or a constant or a variable its folder sees.
  - A **constant** is put in place when compiling, and checked as if written.
  - A **parameter** is whatever the block that includes the component gives it, a value or a
    name in turn, so a value passes through any number of components. Its type is checked in
    the component; its value, at the block that finally gives it.
  - A **variable** changes while running, so the package keeps a reference and the engine
    reads it. Nothing checks the value again before it reaches the driver, so the project
    must guarantee it: the variable's type fits and its limits lie within the parameter's
    (`action.param_variable_unlimited`). A text parameter with choices takes no variable.
    That only holds if the variable stays within its limits: an automation that sets a
    value outside them is refused (`variable.set_out_of_range`), and the engine holds every
    assignment to them while running.
- **A driver's parameter may be optional**: left out with nothing in its place, and the
  driver decides. `fade` takes its `from` so: without it, it starts where the element is.
- **An automation cannot start or stop a component** (`automation.starts_component`): it has
  nothing to give its parameters.
- **A package is rebuilt, never migrated.** Its `schemaVersion` tells a runtime whether it
  can read it; there is no separate minimum runtime version until the two can differ.

## Alternatives considered
- **Flattened clips in the package**: the engine on the board would apply decision 0017
  again, the rule living in two places that must agree for ever.
- **A zip from the start**, for the audio of phase 6: one file inside today, and `core` would
  have to produce reproducible zip bytes. How audio travels is decided with audio.
- **Clamping a variable to the parameter's limits while running**: a mistake of the project
  would pass in silence.
- **Python's own number format in the canonical form**: it writes `1e-05` where JavaScript
  writes `0.00001`, so the UI would compute another hash for a package with a small decimal.
  Cheaper to settle with one implementation than with two.
- **Arguments in the automation that starts a component**: more format and more checks for
  what a one-block sequence already does.
- **A parameter referenced by id, like an element parameter in a track**: a value comes from
  a name everywhere else (automations, conditions), and parameters are already the innermost
  scope of names.

## Consequences
- The engine (4.3) reads a package and nothing else. When exactly it reads a variable (once
  when its command starts, or following it while the command is in force) is decided there;
  the package says the same either way.
- An automation's `if` travels as the text the project wrote, its names unresolved: the
  expression language (4.4) replaces it with something the runtime can evaluate, and brings
  the constants it names.
- `fade` without `from` needs the engine to know where the element is.
- The engine must keep a variable within its limits on every assignment (an increment, a
  value from the phone), by clamping or refusing: decided in 4.3, written here so that it is
  not forgotten. Until then the guarantee above is only as good as `core`'s checks.
- Other implementations of the canonical form (a C++ runtime) follow the RFC; a test will
  hold each to a known hash.
