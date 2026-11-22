# Expressions

The language of an automation's condition (`if`): small, and safe to run on a board. It only
works out a value from constants and variables. It calls nothing, assigns nothing and cannot
loop (decision 0028). Code: `primum_core.expressions`.

```
visits < max_visits and not paused
mode == "night" or brightness / 2 > 30
```

## What can be written

| | |
|---|---|
| Numbers | `3`, `0.25`. The digits `0` to `9`, and a point with digits on both sides. No exponent, no sign: `-3` is the minus of `3` |
| Texts | `"night"`, in double quotes. Inside one, `\"` is a quote and `\\` a backslash |
| Yes and no | `true`, `false` |
| Names | A constant or a variable the automation sees (`variables-and-scopes.md`) |
| Arithmetic | `+`, `-`, `*`, `/`, `%`, and `-x` |
| Comparisons | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Logic | `and`, `or`, `not` |
| Grouping | `(` `)` |

The words are English and lower case in every language of the UI, like the file formats.
`and`, `or`, `not`, `true` and `false` are not names: a constant or a variable cannot be
called one of them (`name.reserved`, at its `name` in the `.vars` file). `True` and `order`
are fine.

What binds tighter comes first; each line binds its operands left to right:

1. `-x`
2. `*` `/` `%`
3. `+` `-`
4. comparisons: one, not a chain. `1 < x < 5` is refused; write `1 < x and x < 5`
5. `not`
6. `and`
7. `or`

So `not visits == 3` is `not (visits == 3)`, and `a or b and c` is `a or (b and c)`.

A condition is at most 500 characters (`expression.too_long`; the schema says the same, and
`parse` reads nothing longer, whoever calls it), and parentheses, `not` and `-x` nest at most
32 deep (`expression.too_deep`).

## Types

Every value is an `integer`, a `number`, a `boolean` or a `text`, the types of constants and
variables. A written `3` is an integer and `3.0` a number.

| Operator | Takes | Gives |
|---|---|---|
| `+` `-` `*` `%`, `-x` | numbers | an integer if every operand is one, else a number |
| `/` | numbers | a number, always: `7 / 2` is `3.5` |
| `<` `<=` `>` `>=` | numbers | a boolean |
| `==` `!=` | two numbers, two texts or two booleans | a boolean |
| `and` `or` `not` | booleans | a boolean |

An integer and a number mix freely, and compare (`visits == 7.0`). Nothing else converts: a
boolean is not a number, a text is not ordered. `%` gives the remainder with the sign of the
divisor: `-7 % 3` is `2`.

`integer` and `number` only differ in these checks. In a package and when evaluating there is
**one kind of number**, a double (IEEE 754, 64 bits): `3` and `3.0` are the same value, as
the canonical form of the package already writes them.

Numbers with decimals are not exact: `0.1 + 0.2 == 0.3` is **false**, as in most languages.
Compare them with a margin (`total > 0.29 and total < 0.31`), or count in whole numbers.

## What `primum validate` checks

All at the automation's `if` (`/if`). The first problem of a condition is reported, except
unknown names, which are all reported.

| Code | When | Params |
|---|---|---|
| `expression.syntax` | It cannot be read | `position` (from 1), `found` (what is there, or `end`) |
| `expression.single_equals` | A single `=`: to compare is `==` | `position` |
| `expression.too_long` | More than 500 characters | `max` |
| `expression.too_deep` | Nested more than 32 deep | `max` |
| `name.unknown` | A name the automation does not see | `name` |
| `expression.expected_number` | Arithmetic or an ordering on what is not a number | `operator` |
| `expression.expected_boolean` | `and`, `or` or `not` on what is not a boolean | `operator` |
| `expression.not_comparable` | `==` or `!=` between different kinds | `operator` |
| `expression.division_by_zero` | `/` or `%` by a written `0`, or by a constant that is `0` | `operator` |
| `expression.constant_too_large` | A constant not below 2^53 in size: it could not be written as a number either | `name` |
| `expression.not_a_condition` | The whole gives a number or a text | |

The limit is one rule: a number that is written, a constant and a result of arithmetic must
all be **below 2^53 in size** (`9007199254740991` is the largest). A number written at or
past it is `expression.syntax` at the number, judged as written, before any rounding. So
whatever can be written can also be negated: `x > -9007199254740991` works.

Every name of a condition that exists counts as a use of it, also when the condition
has something else wrong (another name that does not exist, or it cannot be read); a word
inside a text does not.

## In the deployment package

A board never reads the text. `primum build` compiles the condition into a **program**: its
steps in the order a stack takes them (postfix). Each step is exactly one of:

| Step | Does |
|---|---|
| `{"value": 100}` | Puts a value on the stack. A constant is already its value |
| `{"variable": "<id>"}` | Puts the value the variable has now |
| `{"op": "<"}` | Takes its operands off the stack and puts the result |

`op` is one of the operators above, with `neg` for `-x`. `visits < max_visits and not paused`,
with `max_visits` a constant of 100:

```json
[
  {"variable": "…visits"}, {"value": 100}, {"op": "<"},
  {"variable": "…paused"}, {"op": "not"},
  {"op": "and"}
]
```

A program has no jumps: it runs each step once, in order, and ends. Reading a package checks
that each program holds together (`expression.program_invalid`, at the automation's `if`):
every step is one of the three, every variable is one of the package's, every operator finds
operands of types it takes, and one boolean is left at the end.

## Evaluating

`evaluate(program, values)` gives the value, with the value each variable has. It never
raises.

What cannot be worked out is a **failure**, with its reason:

- `division_by_zero`: `/` or `%` by a variable or a result that is zero;
- `overflow`: a result of arithmetic (`+ - * / %`, `-x`) that is not below 2^53 in size, or
  a value no double holds.

The limit looks at the **value**, never at how it is held or at the type it was declared
with: `x + 1` with `x` at 2^53 fails the same whether `x` is an integer or a number. Below
it, arithmetic on whole numbers is exact; at it, it fails instead of rounding in silence. A
variable may hold a larger value (its own limits allow it): it compares (`x > 5`), but
arithmetic on it fails. A runtime in another language reproduces the rule with doubles and
one comparison per result.

A failure spoils whatever needs it, with one exception: `and` and `or` do not need a side
when the other settles the answer. `false and <failure>` is false and `true or <failure>` is
true, **whichever side fails**. So a guard works however it is written:

```
visits != 0 and total / visits > 3
total / visits > 3 and visits != 0
```

Both are false when `visits` is 0. Without a guard, the condition is a failure. What an
automation does with a condition that fails is the engine's (block 4.4b): it does not hold,
and it is told.

## Not yet

- Windows of time are not in the language: an automation names the schedules whose windows
  it needs in a field of its own (block 4.4c).
- No functions (`min`, `abs`), no texts joined or compared by order.
- The engine does not evaluate conditions yet (block 4.4b): this block is the language, its
  checks and its compiled form.
