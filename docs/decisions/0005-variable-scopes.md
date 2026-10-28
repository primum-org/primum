# 0005. Variables are scoped by folder; redefinition is an error

- Status: Accepted
- Date: 2026-10-28

## Context
Users want variables and constants that apply to a group of files and are not visible outside
it, without the confusion of programming-language scoping rules.

## Decision
- Scopes: project root → folder → file → component instance (parameters).
- A file sees the names of its folder and of the folders above it; **never** those of sibling or
  child folders.
- A folder may **export** a name; another folder uses it only after explicitly **importing** it.
- **Defining a name that already exists in an outer scope is a validation error** (no shadowing).
- Constants are resolved at compile time. Variables are runtime state with a type, an initial
  value, limits (if numeric) and a persistence flag; they may be exposed as phone **settings**.
- Each runtime variable lives on one board (its owner). Changes are atomic operations.

## Alternatives considered
- Shadowing allowed (as in most programming languages): confusing for non-programmers.
- Global variables only: does not scale and leaks names everywhere.

## Consequences
- The compiler resolves every name to a single definition and reports unknown, ambiguous or
  unused names.
- The UI must show where a variable comes from.
