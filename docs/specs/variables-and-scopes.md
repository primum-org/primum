# Variables and scopes

Constants and variables (`.vars` files), where their names are visible (decision 0005), and
components: sequences with parameters. Code: `primum_core.scopes`, `primum_core.components`
and the value checks of `primum_core.variants`. Formats: `schemas/variables.schema.json`,
`schemas/sequence.schema.json`.

## Constants and variables

A `.vars` file holds constants and variables for the folder it is in.

| | Constant | Variable |
|---|---|---|
| Changes while running | never: resolved when the project is compiled | yes, through atomic operations (set, increment) |
| Fields | `name`, `type`, `value` | `name`, `type`, `initial`, `min`/`max` (numeric only), `persistent`, `setting` |
| Set by an automation | no (`name.not_a_variable`) | yes |

- Types: `number`, `integer`, `boolean`, `text`. A value is of its declared type: `2` is an
  integer and a number, `2.5` only a number, `true` only a boolean, `"2"` only a text
  (`value.expected_number`, `value.expected_integer`, `value.expected_boolean`,
  `value.expected_text`). This holds for a constant's `value`, a variable's `initial`, the
  value an automation sets or adds, and the value given to a component's parameter.
- Limits: only a numeric variable has `min` and `max` (`schema.unexpected_field` otherwise);
  `min` is not above `max` (`variable.limits_invalid`); `initial` lies within them, limits
  included (`variable.initial_out_of_range`).
- Only a numeric variable is incremented (`variable.not_numeric`); the amount, when given, is
  of the variable's type.
- `setting: true` exposes a variable in the phone UI. `persistent: true` keeps its value across
  restarts.

## Scopes

Scopes follow the folders of the project: project root → folder → file → component (the
parameters of a sequence).

- A `.vars` file defines its names **for its folder**. Every `.vars` file of a folder adds to
  the same scope.
- A file **sees** the names of its own folder and of the folders above it, never those of
  sibling or child folders (`name.unknown` otherwise).
- **No shadowing**: a name is defined once in everything that sees it. Defining a name that
  is already visible, in the same folder or in a folder above, is `name.redefined` (with the
  path that already defines it). The second definition, by folder depth and then by path, is
  the one reported.
- **Exports and imports**: a folder shares a name by listing it in `exports` (of the file
  that defines it: `name.unknown` otherwise). Another folder uses it after importing it, by
  the `.vars` file's id and the name (`imports[]`): the name must exist there
  (`name.unknown`) and be exported (`name.not_exported`). An imported name enters the
  importing folder's scope, so the folders below it see it too, and the no-shadowing rule
  applies: importing a name that is already visible is `name.redefined`.
- **Parameters** are the innermost scope: unique within their sequence, and never a name the
  sequence's folder sees (`name.redefined`).

## Uses

An automation resolves names in the scope of its own folder:

- `do[].variable`, the variable an action sets or increments: it must be visible
  (`name.unknown`) and be a variable (`name.not_a_variable`).
- The words of its `if` condition. Conditions are text until phase 4 parses them, so for now
  any word that matches a visible name counts as a use, and nothing else is checked.

A constant or variable that nothing uses, is not exported and is not a setting is a warning:
`name.unused`.

## Components

A sequence with `parameters` is a component. Another sequence includes it with a block,
giving one argument per parameter:

| Parameter type | Argument | Otherwise |
|---|---|---|
| `element` | `element`: an element, or an element parameter of the including sequence | `argument.expected_element`; a `value` is `schema.unexpected_field` |
| `number`, `integer`, `boolean`, `text` | `value`, of that type | `argument.expected_value`, `value.expected_*`; an `element` is `schema.unexpected_field` |

Every parameter of the included sequence gets an argument (`argument.missing`), and each one
only once (`argument.duplicate`). An argument naming a parameter of another sequence is
`ref.wrong_kind` (workspace spec).

Sequences never include each other in a loop, directly (`sequence.includes_itself`) or through
others (`sequence.cycle`, with the chain of sequence names): a loop could never be flattened
into a deployment package. Each block that closes a loop is reported once. Including the same
sequence twice, at different times, is fine.

## Not yet

- Conditions (`if`) are stored, not interpreted: the expression language comes in phase 4,
  and with it the real uses of names in conditions.
- Which board owns a variable (decision 0005): phase 4, with the deployment package.
- Element parameters that no track plays are not reported.
