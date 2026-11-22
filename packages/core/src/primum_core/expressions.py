"""The expression language of conditions (decision 0028, ``docs/specs/expressions.md``).

Small and safe: numbers, texts, ``true`` and ``false``, the names of constants and variables,
arithmetic (``+ - * / %``), comparisons, ``and``, ``or``, ``not`` and parentheses. No calls,
no assignments, nothing that loops: an expression is read, checked and compiled here, and a
board only ever runs the compiled form.

- ``parse`` reads the text into a tree, or says where it stops making sense.
- ``check`` gives the tree its type from the types of its names, or says what does not fit.
- ``compile_program`` flattens it into a program for the deployment package: values,
  variables by id and operators in the order a stack machine takes them (postfix), constants
  already in place.
- ``check_program`` says whether a program holds together, for whoever reads a package.
- ``evaluate`` runs a program on the values the variables have.

Evaluating never raises and never loops. What cannot be worked out (a division by zero, a
number too large to be exact) is a ``Failure``, and it only spoils what needs it: ``false
and`` anything is false, ``true or`` anything is true, whichever side fails, so a guard works
whatever the order it is written in (``visits != 0 and total / visits > 3``).
"""

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol
from uuid import UUID

from primum_core.errors import CoreErrorCode, ParamValue
from primum_core.values import NUMERIC, Value

# How deep parentheses, ``not`` and ``-`` may nest: enough for anything a person writes, and
# a bound on what reading and checking an expression costs.
MAX_DEPTH = 32
MAX_LENGTH = 500  # characters, as the schema of an automation says
# Numbers are doubles, and below this size whole numbers are exact. One rule everywhere: a
# number that is written, a constant and a result of arithmetic must all be below it.
MAX_EXACT = 2**53

KEYWORDS = frozenset({"and", "or", "not", "true", "false"})
COMPARISONS = frozenset({"==", "!=", "<", "<=", ">", ">="})
ORDERINGS = frozenset({"<", "<=", ">", ">="})
ARITHMETIC = frozenset({"+", "-", "*", "/", "%"})
NEGATE = "neg"  # the unary minus, in a program
OPERATORS = frozenset({"or", "and", "not", NEGATE}) | COMPARISONS | ARITHMETIC
BOOLEAN, TEXT, INTEGER, NUMBER = "boolean", "text", "integer", "number"

_TOKEN = re.compile(
    r"""\s*(?:
        (?P<number>[0-9]+(?:\.[0-9]+)?)
      | (?P<text>"(?:[^"\\]|\\["\\])*")
      | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<symbol>==|!=|<=|>=|[<>+\-*/%()])
    )""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class Problem:
    """What is wrong with an expression: a code and its params. Whoever asked says where."""

    code: CoreErrorCode
    params: Mapping[str, ParamValue]


@dataclass(frozen=True)
class Literal:
    value: Value


@dataclass(frozen=True)
class Name:
    name: str


@dataclass(frozen=True)
class Unary:
    operator: str  # "not" or "neg"
    operand: "Node"


@dataclass(frozen=True)
class Binary:
    operator: str
    left: "Node"
    right: "Node"


type Node = Literal | Name | Unary | Binary


@dataclass(frozen=True)
class Failure:
    """An expression that could not be worked out, and why: ``division_by_zero`` or
    ``overflow``."""

    reason: str


class Item(Protocol):
    """One step of a program: a value, a variable to read, or an operator. One of the three
    (``primum_core.generated.model.ConditionItem``)."""

    @property
    def value(self) -> Value | None: ...
    @property
    def variable(self) -> UUID | None: ...
    @property
    def op(self) -> str | None: ...


# --- reading ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Token:
    kind: str  # "number", "text", "name", "symbol" or "end"
    text: str
    position: int  # 1-based, for a person


class _UnreadableError(Exception):
    def __init__(self, problem: Problem) -> None:
        super().__init__(problem.code)
        self.problem = problem


def parse(text: str) -> Node | Problem:
    """The tree of an expression, or the first thing in it that makes no sense
    (``expression.syntax``, with its ``position`` and what was ``found`` there;
    ``expression.single_equals`` for an ``=`` that should be ``==``; ``expression.too_long``;
    or ``expression.too_deep``). Bounded whatever the text: nothing longer than ``MAX_LENGTH``
    is read."""
    if len(text) > MAX_LENGTH:
        return Problem(CoreErrorCode.EXPRESSION_TOO_LONG, {"max": MAX_LENGTH})
    try:
        return _Parser(_tokens(text)).expression()
    except _UnreadableError as unreadable:
        return unreadable.problem


def names_in(node: Node) -> tuple[str, ...]:
    """Every name the expression uses, each once, in the order they appear."""
    found: dict[str, None] = {}
    pending = [node]
    while pending:
        current = pending.pop()
        match current:
            case Name(name):
                found.setdefault(name)
            case Unary(_, operand):
                pending.append(operand)
            case Binary(_, left, right):
                pending += (right, left)
            case Literal():
                pass
    return tuple(found)


def words_in(text: str) -> frozenset[str]:
    """Every word of a text that could be a name, for an expression that cannot be read: what
    it meant to use is still worth knowing."""
    return frozenset(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)) - KEYWORDS


def _tokens(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    position = 0
    while position < len(text):
        if text[position:].strip() == "":
            break
        match = _TOKEN.match(text, position)
        if match is None or match.end() == position:
            at = position + len(text[position:]) - len(text[position:].lstrip())
            if text[at] == "=":  # the likeliest slip: to compare is ==
                params = {"position": at + 1}
                raise _UnreadableError(Problem(CoreErrorCode.EXPRESSION_SINGLE_EQUALS, params))
            raise _UnreadableError(_syntax(at + 1, text[at]))
        kind = match.lastgroup or ""
        tokens.append(_Token(kind, match.group(kind), match.start(kind) + 1))
        position = match.end()
    tokens.append(_Token("end", "", len(text) + 1))
    return tokens


def _syntax(position: int, found: str) -> Problem:
    return Problem(CoreErrorCode.EXPRESSION_SYNTAX, {"position": position, "found": found})


class _Parser:
    """Recursive descent, one method per level of precedence, lowest first: ``or``, ``and``,
    ``not``, a comparison (one: ``a < b < c`` is not a thing), ``+ -``, ``* / %``, ``-x``."""

    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._index = 0
        self._depth = 0

    def expression(self) -> Node:
        node = self._or()
        if self._peek().kind != "end":
            raise self._unexpected()
        return node

    def _peek(self) -> _Token:
        return self._tokens[self._index]

    def _take(self) -> _Token:
        token = self._tokens[self._index]
        self._index += 1
        return token

    def _is(self, *texts: str) -> bool:
        token = self._peek()
        return token.kind in {"name", "symbol"} and token.text in texts

    def _unexpected(self) -> _UnreadableError:
        token = self._peek()
        return _UnreadableError(_syntax(token.position, token.text or "end"))

    def _deeper(self) -> None:
        self._depth += 1
        if self._depth > MAX_DEPTH:
            raise _UnreadableError(Problem(CoreErrorCode.EXPRESSION_TOO_DEEP, {"max": MAX_DEPTH}))

    def _or(self) -> Node:
        node = self._and()
        while self._is("or"):
            self._take()
            node = Binary("or", node, self._and())
        return node

    def _and(self) -> Node:
        node = self._not()
        while self._is("and"):
            self._take()
            node = Binary("and", node, self._not())
        return node

    def _not(self) -> Node:
        if not self._is("not"):
            return self._comparison()
        self._take()
        self._deeper()
        node = Unary("not", self._not())
        self._depth -= 1
        return node

    def _comparison(self) -> Node:
        node = self._sum()
        if self._is(*COMPARISONS):
            operator = self._take().text
            node = Binary(operator, node, self._sum())
            if self._is(*COMPARISONS):
                raise self._unexpected()  # a < b < c: write a < b and b < c
        return node

    def _sum(self) -> Node:
        node = self._term()
        while self._is("+", "-"):
            operator = self._take().text
            node = Binary(operator, node, self._term())
        return node

    def _term(self) -> Node:
        node = self._unary()
        while self._is("*", "/", "%"):
            operator = self._take().text
            node = Binary(operator, node, self._unary())
        return node

    def _unary(self) -> Node:
        if not self._is("-"):
            return self._atom()
        self._take()
        self._deeper()
        node = Unary(NEGATE, self._unary())
        self._depth -= 1
        return node

    def _atom(self) -> Node:
        token = self._peek()
        if token.kind == "number":
            self._take()
            return Literal(self._number(token))
        if token.kind == "text":
            self._take()
            return Literal(re.sub(r"\\(.)", r"\1", token.text[1:-1]))
        if token.kind == "name" and token.text in {"true", "false"}:
            self._take()
            return Literal(token.text == "true")
        if token.kind == "name" and token.text not in KEYWORDS:
            self._take()
            return Name(token.text)
        if self._is("("):
            self._take()
            self._deeper()
            node = self._or()
            self._depth -= 1
            if not self._is(")"):
                raise self._unexpected()
            self._take()
            return node
        raise self._unexpected()

    def _number(self, token: _Token) -> float:
        # Judged as written: past the limit a double would round it, in silence. And the
        # limit itself is out, as for a result: its minus could never be worked out.
        if Fraction(token.text) >= MAX_EXACT:
            raise _UnreadableError(_syntax(token.position, token.text))
        return float(token.text) if "." in token.text else int(token.text)


# --- checking --------------------------------------------------------------------------------


def check(
    node: Node, types: Mapping[str, str], constants: Mapping[str, Value] | None = None
) -> str | Problem:
    """The type of the expression (``boolean``, ``integer``, ``number`` or ``text``) given the
    type of each of its names, or the first thing that does not fit:

    - ``expression.expected_number``: arithmetic or an ordering on what is not a number;
    - ``expression.expected_boolean``: ``and``, ``or`` or ``not`` on what is not a boolean;
    - ``expression.not_comparable``: ``==`` or ``!=`` between things of different kinds;
    - ``expression.division_by_zero``: ``/`` or ``%`` by a zero that is written, or by a
      constant that is one (``constants``: the value of each name that is a constant);
    - ``expression.constant_too_large``: a constant not below 2^53 in size, which could not
      be written as a number either (with its ``name``).

    The others with the ``operator``. Every name must be in ``types``: one that is not is the
    caller's to report, before asking.
    """
    try:
        return _type_of(node, types, constants or {})
    except _UnreadableError as unfit:
        return unfit.problem


def _unfit(code: CoreErrorCode, operator: str) -> _UnreadableError:
    shown = "-" if operator == NEGATE else operator
    return _UnreadableError(Problem(code, {"operator": shown}))


def _type_of(node: Node, types: Mapping[str, str], constants: Mapping[str, Value]) -> str:
    match node:
        case Literal(value):
            return _type_of_value(value)
        case Name(name):
            if _too_large(constants.get(name)):
                params = {"name": name}
                raise _UnreadableError(Problem(CoreErrorCode.EXPRESSION_CONSTANT_TOO_LARGE, params))
            return types[name]
        case Unary(operator, operand):
            inner = _type_of(operand, types, constants)
            if operator == "not":
                if inner != BOOLEAN:
                    raise _unfit(CoreErrorCode.EXPRESSION_EXPECTED_BOOLEAN, operator)
                return BOOLEAN
            if inner not in NUMERIC:
                raise _unfit(CoreErrorCode.EXPRESSION_EXPECTED_NUMBER, operator)
            return inner
        case Binary(operator, left, right):
            return _type_of_binary(
                operator,
                _type_of(left, types, constants),
                _type_of(right, types, constants),
                _is_zero(right, constants),
            )


def _type_of_value(value: Value) -> str:
    if isinstance(value, bool):
        return BOOLEAN
    if isinstance(value, str):
        return TEXT
    return INTEGER if isinstance(value, int) else NUMBER


def _too_large(value: Value | None) -> bool:
    """Whether a constant is a number that could not be written in a condition."""
    return value is not None and not isinstance(value, bool | str) and abs(value) >= MAX_EXACT


def _is_zero(node: Node, constants: Mapping[str, Value]) -> bool:
    value: Value | None = None
    if isinstance(node, Literal):
        value = node.value
    elif isinstance(node, Name):
        value = constants.get(node.name)
    return value is not None and not isinstance(value, bool | str) and value == 0


def _type_of_binary(operator: str, left: str, right: str, by_zero: bool) -> str:
    """The type ``left operator right`` has, for types that fit the operator."""
    if operator in {"and", "or"}:
        if left != BOOLEAN or right != BOOLEAN:
            raise _unfit(CoreErrorCode.EXPRESSION_EXPECTED_BOOLEAN, operator)
        return BOOLEAN
    numbers = left in NUMERIC and right in NUMERIC
    if operator in {"==", "!="}:
        if not numbers and left != right:
            raise _unfit(CoreErrorCode.EXPRESSION_NOT_COMPARABLE, operator)
        return BOOLEAN
    if not numbers:
        raise _unfit(CoreErrorCode.EXPRESSION_EXPECTED_NUMBER, operator)
    if operator in ORDERINGS:
        return BOOLEAN
    if operator in {"/", "%"} and by_zero:
        raise _unfit(CoreErrorCode.EXPRESSION_DIVISION_BY_ZERO, operator)
    # A division is a number with decimals, even of two whole ones: 7 / 2 is 3.5.
    return INTEGER if left == right == INTEGER and operator != "/" else NUMBER


# --- compiling -------------------------------------------------------------------------------


def compile_program(node: Node, bindings: Mapping[str, Value | UUID]) -> list[dict[str, object]]:
    """The expression as a program for the deployment package: its steps in postfix order,
    each ``{"value": …}``, ``{"variable": "<id>"}`` or ``{"op": "<"}``. ``bindings`` says what
    each name is: the value of a constant, or the id of a variable."""
    program: list[dict[str, object]] = []
    # A walk with its own stack: no recursion, however the tree leans.
    pending: list[Node | str] = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            program.append({"op": current})
            continue
        match current:
            case Literal(value):
                program.append({"value": value})
            case Name(name):
                bound = bindings[name]
                if isinstance(bound, UUID):
                    program.append({"variable": str(bound)})
                else:
                    program.append({"value": bound})
            case Unary(operator, operand):
                pending += (operator, operand)
            case Binary(operator, left, right):
                pending += (operator, right, left)
    return program


def check_program(items: Sequence[Item], variables: Mapping[UUID, str]) -> str | None:
    """The type a program leaves, or ``None`` if it does not hold together: a step that is
    not exactly one of a value, a variable or an operator; a variable that is not in
    ``variables`` (each by id, with its type); an operator without its operands or with ones
    that do not fit; or anything but one result at the end."""
    stack: list[str] = []
    for item in items:
        given = [item.value is not None, item.variable is not None, item.op is not None]
        if sum(given) != 1:
            return None
        if item.value is not None:
            stack.append(_type_of_value(item.value))
        elif item.variable is not None:
            if item.variable not in variables:
                return None
            stack.append(variables[item.variable])
        elif not _apply_type(item.op or "", stack):
            return None
    return stack[0] if len(stack) == 1 else None


def _apply_type(operator: str, stack: list[str]) -> bool:
    """Replace the operands of ``operator`` on the stack of types with the type of its
    result; whether it could."""
    if operator not in OPERATORS:
        return False
    try:
        if operator in {"not", NEGATE}:
            if not stack:
                return False
            inner = stack.pop()
            fits = inner == BOOLEAN if operator == "not" else inner in NUMERIC
            stack.append(inner)
            return fits
        if len(stack) < 2:
            return False
        right, left = stack.pop(), stack.pop()
        stack.append(_type_of_binary(operator, left, right, by_zero=False))
    except _UnreadableError:
        return False
    return True


# --- evaluating ------------------------------------------------------------------------------


def evaluate(items: Sequence[Item], values: Mapping[UUID, Value]) -> Value | Failure:
    """The value of a program that holds together (``check_program``), with the value each
    variable has now. A ``Failure`` when it cannot be worked out."""
    stack: list[Value | Failure] = []
    for item in items:
        if item.value is not None:
            stack.append(_held(item.value))
        elif item.variable is not None:
            stack.append(_held(values[item.variable]))
        elif item.op in {"not", NEGATE}:
            stack.append(_unary(item.op, stack.pop()))
        else:
            right, left = stack.pop(), stack.pop()
            stack.append(_binary(item.op or "", left, right))
    return stack[0]


def _held(value: Value) -> Value | Failure:
    """A value as it is worked with: every number the same kind (a double), whether it was
    held as a whole one or not. One that no double holds is a failure."""
    if isinstance(value, bool | str):
        return value
    try:
        held = float(value)
    except OverflowError:
        return Failure("overflow")
    return held if math.isfinite(held) else Failure("overflow")


def _unary(operator: str, operand: Value | Failure) -> Value | Failure:
    if isinstance(operand, Failure):
        return operand
    if operator == "not":
        return not operand
    return _number(-_as_number(operand))


def _binary(operator: str, left: Value | Failure, right: Value | Failure) -> Value | Failure:
    if operator in {"and", "or"}:
        return _logic(operator == "and", left, right)
    if isinstance(left, Failure):
        return left
    if isinstance(right, Failure):
        return right
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    return _arithmetic(operator, _as_number(left), _as_number(right))


def _logic(is_and: bool, left: Value | Failure, right: Value | Failure) -> Value | Failure:
    """``and`` and ``or`` with a side that may have failed: one side that settles the answer
    settles it (false for ``and``, true for ``or``), whichever it is. Otherwise a failure is
    the answer."""
    settles = not is_and
    if left is settles or right is settles:
        return settles
    for side in (left, right):
        if isinstance(side, Failure):
            return side
    return is_and


def _arithmetic(operator: str, left: float, right: float) -> Value | Failure:
    match operator:
        case "<":
            return left < right
        case "<=":
            return left <= right
        case ">":
            return left > right
        case ">=":
            return left >= right
        case "+":
            return _number(left + right)
        case "-":
            return _number(left - right)
        case "*":
            return _number(left * right)
        case _:
            if right == 0:
                return Failure("division_by_zero")
            # The remainder has the sign of the divisor, as in Python: -7 % 3 is 2.
            return _number(left / right if operator == "/" else left % right)


def _as_number(value: Value) -> float:
    if isinstance(value, bool | str):  # a program that holds together never gets here
        raise TypeError(f"not a number: {value!r}")
    return value


def _number(result: float) -> float | Failure:
    """A result of arithmetic, or a failure when it is not below 2^53 in size (or not a
    number at all). The rule looks at the value alone, so it is the same in any runtime that
    works in doubles; and below that limit, arithmetic on whole numbers is exact."""
    if not abs(result) < MAX_EXACT:
        return Failure("overflow")
    return result
