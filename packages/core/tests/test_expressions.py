"""The expression language of conditions: reading, checking, compiling and evaluating."""

import random
from collections.abc import Mapping
from typing import cast
from uuid import UUID

import pytest

from primum_core import expressions
from primum_core.errors import CoreErrorCode
from primum_core.expressions import Binary, Failure, Literal, Name, Node, Problem, Unary
from primum_core.generated.model import ConditionStep
from primum_core.values import Value

VISITS, LIMIT, PAUSED, MODE, RATIO = (UUID(int=number) for number in range(1, 6))
TYPES = {
    "visits": "integer",
    "limit": "integer",
    "paused": "boolean",
    "mode": "text",
    "ratio": "number",
}
IDS: dict[str, Value | UUID] = {
    "visits": VISITS,
    "limit": LIMIT,
    "paused": PAUSED,
    "mode": MODE,
    "ratio": RATIO,
}
VALUES: dict[UUID, Value] = {VISITS: 7, LIMIT: 10, PAUSED: False, MODE: "night", RATIO: 0.5}


def _tree(text: str) -> Node:
    tree = expressions.parse(text)
    assert not isinstance(tree, Problem), tree
    return tree


def _steps(program: list[dict[str, object]]) -> list[ConditionStep]:
    return [
        ConditionStep(
            value=cast("Value | None", step.get("value")),
            variable=UUID(cast("str", step["variable"])) if "variable" in step else None,
            op=cast("None", step.get("op")),
        )
        for step in program
    ]


def _program(text: str, bindings: Mapping[str, Value | UUID] = IDS) -> list[ConditionStep]:
    return _steps(expressions.compile_program(_tree(text), bindings))


def _value(text: str, values: Mapping[UUID, Value] = VALUES) -> Value | Failure:
    return expressions.evaluate(_program(text), values)


@pytest.mark.parametrize(
    ("text", "tree"),
    [
        ("visits < limit", Binary("<", Name("visits"), Name("limit"))),
        ("1 + 2 * 3", Binary("+", Literal(1), Binary("*", Literal(2), Literal(3)))),
        ("(1 + 2) * 3", Binary("*", Binary("+", Literal(1), Literal(2)), Literal(3))),
        ("10 - 4 - 3", Binary("-", Binary("-", Literal(10), Literal(4)), Literal(3))),
        ("-visits * 2", Binary("*", Unary("neg", Name("visits")), Literal(2))),
        ("2 - -1", Binary("-", Literal(2), Unary("neg", Literal(1)))),
        (
            "not paused and visits > 3 or true",
            Binary(
                "or",
                Binary(
                    "and", Unary("not", Name("paused")), Binary(">", Name("visits"), Literal(3))
                ),
                Literal(True),
            ),
        ),
        ("not visits == 3", Unary("not", Binary("==", Name("visits"), Literal(3)))),
        ('mode != "a \\"b\\" \\\\"', Binary("!=", Name("mode"), Literal('a "b" \\'))),
        ("  ratio>=0.25 ", Binary(">=", Name("ratio"), Literal(0.25))),
        ("android", Name("android")),  # a name may start like a keyword
    ],
)
def test_an_expression_is_read_with_the_usual_precedence(text: str, tree: Node) -> None:
    assert expressions.parse(text) == tree


@pytest.mark.parametrize(
    ("text", "position", "found"),
    [
        ("", 1, "end"),
        ("   ", 4, "end"),
        ("visits <", 9, "end"),
        ("visits < < 3", 10, "<"),
        ("(visits < 3", 12, "end"),
        ("visits < 3)", 11, ")"),
        ("1 < 2 < 3", 7, "<"),
        ("visits && paused", 8, "&"),
        ("3 visits", 3, "visits"),
        ("and paused", 1, "and"),
        ("not", 4, "end"),
        ('mode == "night', 9, '"'),
        ("mode == 'night'", 9, "'"),
        ("1.", 2, "."),
        ("9007199254740993 > 1", 1, "9007199254740993"),
        ("f(1)", 2, "("),
        ("visits < \u0663", 10, "\u0663"),  # an Arabic three is not a digit of the language
        ("visits < 1\u0663", 11, "\u0663"),
    ],
)
def test_what_cannot_be_read_says_where(text: str, position: int, found: str) -> None:
    assert expressions.parse(text) == Problem(
        CoreErrorCode.EXPRESSION_SYNTAX, {"position": position, "found": found}
    )


@pytest.mark.parametrize(("text", "position"), [("visits = 3", 8), ("3=visits", 2)])
def test_a_single_equals_sign_has_its_own_code(text: str, position: int) -> None:
    assert expressions.parse(text) == Problem(
        CoreErrorCode.EXPRESSION_SINGLE_EQUALS, {"position": position}
    )


@pytest.mark.parametrize(
    "text",
    ["9" * 5000 + " > 1", " + ".join(["1"] * 3000) + " > 1", "visits < 3" + " " * 500],
)
def test_an_expression_longer_than_the_limit_is_refused_before_reading_it(text: str) -> None:
    assert expressions.parse(text) == Problem(
        CoreErrorCode.EXPRESSION_TOO_LONG, {"max": expressions.MAX_LENGTH}
    )


@pytest.mark.parametrize(
    "text",
    [
        "(" * 40 + "1" + ")" * 40,
        "not " * 40 + "true",
        "-" * 40 + "1",
        "1 < " + "(" * 40 + "1" + ")" * 40,
    ],
)
def test_an_expression_nested_too_deep_is_refused(text: str) -> None:
    assert expressions.parse(text) == Problem(
        CoreErrorCode.EXPRESSION_TOO_DEEP, {"max": expressions.MAX_DEPTH}
    )


def test_a_long_flat_expression_is_not_deep() -> None:
    text = " and ".join(["paused"] * 40)

    assert expressions.check(_tree(text), TYPES) == "boolean"


def test_the_names_of_an_expression_each_once_in_order() -> None:
    tree = _tree("limit > visits and (visits > 0 or not paused) and limit != 3")

    assert expressions.names_in(tree) == ("limit", "visits", "paused")


@pytest.mark.parametrize(
    ("text", "result"),
    [
        ("visits < limit and not paused", "boolean"),
        ("visits + 1", "integer"),
        ("visits % 2", "integer"),
        ("visits / 2", "number"),
        ("visits * ratio", "number"),
        ("-ratio", "number"),
        ("visits == ratio", "boolean"),  # a whole number and one with decimals compare
        ('mode == "night"', "boolean"),
        ("paused == true", "boolean"),
        ('"night"', "text"),
    ],
)
def test_an_expression_has_the_type_of_what_it_gives(text: str, result: str) -> None:
    assert expressions.check(_tree(text), TYPES) == result


@pytest.mark.parametrize(
    ("text", "code", "operator"),
    [
        ("visits + paused", CoreErrorCode.EXPRESSION_EXPECTED_NUMBER, "+"),
        ('mode < "z"', CoreErrorCode.EXPRESSION_EXPECTED_NUMBER, "<"),
        ("-paused", CoreErrorCode.EXPRESSION_EXPECTED_NUMBER, "-"),
        ("visits and paused", CoreErrorCode.EXPRESSION_EXPECTED_BOOLEAN, "and"),
        ("paused or 1", CoreErrorCode.EXPRESSION_EXPECTED_BOOLEAN, "or"),
        ("not visits", CoreErrorCode.EXPRESSION_EXPECTED_BOOLEAN, "not"),
        ("mode == 3", CoreErrorCode.EXPRESSION_NOT_COMPARABLE, "=="),
        ("paused != 0", CoreErrorCode.EXPRESSION_NOT_COMPARABLE, "!="),
        ("visits / 0", CoreErrorCode.EXPRESSION_DIVISION_BY_ZERO, "/"),
        ("visits % 0.0", CoreErrorCode.EXPRESSION_DIVISION_BY_ZERO, "%"),
        ("visits / nothing", CoreErrorCode.EXPRESSION_DIVISION_BY_ZERO, "/"),
    ],
)
def test_what_does_not_fit_its_operator_is_refused(
    text: str, code: CoreErrorCode, operator: str
) -> None:
    types = {**TYPES, "nothing": "integer"}

    assert expressions.check(_tree(text), types, {"nothing": 0}) == Problem(
        code, {"operator": operator}
    )


def test_a_program_is_the_expression_in_the_order_a_stack_takes_it() -> None:
    tree = _tree("visits < limit and not paused")
    bindings: dict[str, Value | UUID] = {"visits": VISITS, "limit": 100, "paused": PAUSED}

    assert expressions.compile_program(tree, bindings) == [
        {"variable": str(VISITS)},
        {"value": 100},
        {"op": "<"},
        {"variable": str(PAUSED)},
        {"op": "not"},
        {"op": "and"},
    ]


def test_a_minus_of_one_operand_has_its_own_name_in_a_program() -> None:
    assert expressions.compile_program(_tree("3 - -visits"), IDS) == [
        {"value": 3},
        {"variable": str(VISITS)},
        {"op": "neg"},
        {"op": "-"},
    ]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("visits < limit and not paused", True),
        ("visits >= limit or paused", False),
        ("visits + 3 == limit", True),
        ("limit - visits * 2", -4),
        ("(limit - visits) * 2", 6),
        ("visits / 2", 3.5),
        ("visits % 4", 3),
        ("-visits % 4", 1),  # the sign of the divisor
        ("7.5 % 2", 1.5),
        ("--visits", 7),
        ('mode == "night"', True),
        ('mode != "night"', False),
        ("paused == false", True),
        ("ratio * 4 == 2", True),
        ("visits == 7.0", True),
    ],
)
def test_a_program_gives_the_value_of_its_expression(text: str, value: Value) -> None:
    assert _value(text) == value


@pytest.mark.parametrize(
    ("text", "result"),
    [
        ("limit / (visits - 7) > 1", Failure("division_by_zero")),
        ("limit % (visits - 7) == 1", Failure("division_by_zero")),
        ("not (limit / (visits - 7) > 1)", Failure("division_by_zero")),
        ("9007199254740991 + visits > 0", Failure("overflow")),
        ("9007199254740991 * 9007199254740991 > 0", Failure("overflow")),
        ("9007199254740991 + 1 > 0", Failure("overflow")),
        ("9007199254740990 + 1 > 0", True),
        # A guard works whichever side it is written on.
        ("visits != 7 and limit / (visits - 7) > 1", False),
        ("limit / (visits - 7) > 1 and visits != 7", False),
        ("visits == 7 or limit / (visits - 7) > 1", True),
        ("limit / (visits - 7) > 1 or visits == 7", True),
        # Without one, what fails stays failed.
        ("visits == 7 and limit / (visits - 7) > 1", Failure("division_by_zero")),
        ("visits != 7 or limit / (visits - 7) > 1", Failure("division_by_zero")),
    ],
)
def test_what_cannot_be_worked_out_is_a_failure_unless_a_side_settles_it(
    text: str, result: Value | Failure
) -> None:
    assert _value(text) == result


@pytest.mark.parametrize("text", ["ratio + 1 > 0", "ratio * 1 > 0", "-ratio < 0"])
@pytest.mark.parametrize("held", [2**53, float(2**53)])
def test_a_result_too_large_fails_however_the_value_is_held(text: str, held: float) -> None:
    """The limit is on the value: the same number as a whole one or with decimals behaves
    the same (a package does not tell 3 from 3.0)."""
    assert _value(text, {**VALUES, RATIO: held}) == Failure("overflow")


@pytest.mark.parametrize("held", [2**53 - 2, float(2**53 - 2)])
def test_a_result_below_the_limit_is_exact_however_the_value_is_held(held: float) -> None:
    values = {**VALUES, RATIO: held}

    assert _value("ratio + 1 == 9007199254740991", values) is True
    assert _value("ratio + 1 == 9007199254740990", values) is False


@pytest.mark.parametrize("held", [2**54, float(2**54), 1e300])
def test_a_value_beyond_the_limit_compares_but_does_not_count(held: float) -> None:
    values = {**VALUES, RATIO: held}

    assert _value("ratio > 5", values) is True
    assert _value("ratio / 2 > 5", values) == Failure("overflow")


def test_a_value_no_number_can_hold_is_a_failure_wherever_it_is_used() -> None:
    assert _value("ratio > 5", {**VALUES, RATIO: 10**400}) == Failure("overflow")


@pytest.mark.parametrize(
    "number",
    ["9007199254740994.0", "9007199254740993.0", "9007199254740992.5", "9007199254740992.0"],
)
def test_a_decimal_written_beyond_the_limit_is_refused_like_a_whole_one(number: str) -> None:
    """Judged as written, not after rounding to the nearest double."""
    assert expressions.parse(f"ratio < {number}") == Problem(
        CoreErrorCode.EXPRESSION_SYNTAX, {"position": 9, "found": number}
    )


def test_the_limit_itself_cannot_be_written_since_no_result_reaches_it() -> None:
    """One rule for what is written and what is worked out: below 2^53. Its negative would
    otherwise validate and then fail every time."""
    assert expressions.parse("visits > -9007199254740992") == Problem(
        CoreErrorCode.EXPRESSION_SYNTAX, {"position": 11, "found": "9007199254740992"}
    )


@pytest.mark.parametrize("text", ["visits > -9007199254740991", "visits < 9007199254740991.0"])
def test_the_largest_number_that_can_be_written_works_with_its_minus(text: str) -> None:
    assert isinstance(_value(text), bool)


@pytest.mark.parametrize("text", ["visits + huge > 1", "visits < huge", "huge == visits"])
@pytest.mark.parametrize("value", [10**30, 1e30, -(2**53) - 2, 2**53, -float(2**53)])
def test_a_constant_too_large_to_write_is_refused_like_the_number(text: str, value: float) -> None:
    types = {**TYPES, "huge": "number"}

    assert expressions.check(_tree(text), types, {"huge": value}) == Problem(
        CoreErrorCode.EXPRESSION_CONSTANT_TOO_LARGE, {"name": "huge"}
    )


def test_the_largest_constant_is_taken_and_works_with_its_minus() -> None:
    types = {**TYPES, "huge": "integer"}
    bindings: dict[str, Value | UUID] = {**IDS, "huge": 2**53 - 1}

    assert expressions.check(_tree("visits > -huge"), types, {"huge": 2**53 - 1}) == "boolean"
    program = _steps(expressions.compile_program(_tree("visits > -huge"), bindings))
    assert expressions.evaluate(program, VALUES) is True


def test_decimals_that_overflow_are_a_failure() -> None:
    values = {**VALUES, RATIO: 1e308}

    assert _value("ratio * 10 > 0", values) == Failure("overflow")


VARIABLES = {VISITS: "integer", LIMIT: "integer", PAUSED: "boolean", MODE: "text", RATIO: "number"}


def test_a_compiled_program_holds_together() -> None:
    program = _program('visits / 2 > ratio and (paused or mode == "night")')

    assert expressions.check_program(program, VARIABLES) == "boolean"


@pytest.mark.parametrize(
    "program",
    [
        [{"op": "<"}],
        [{"value": 1}, {"op": "<"}],
        [{"value": 1}, {"value": 2}],
        [{"value": 1}, {"value": True}, {"op": "<"}],
        [{"value": 1}, {"op": "not"}],
        [{"value": True}, {"op": "neg"}],
        [{"value": 1}, {"value": "a"}, {"op": "=="}],
        [{"variable": str(UUID(int=99))}, {"value": 1}, {"op": "<"}],
        [{"value": 1, "op": "neg"}],
        [{}],
        [],
    ],
)
def test_a_program_that_does_not_hold_together_is_told_apart(
    program: list[dict[str, object]],
) -> None:
    assert expressions.check_program(_steps(program), VARIABLES) is None


# --- against a second way of working it out --------------------------------------------------

LEAVES: dict[str, list[str]] = {
    "integer": ["visits", "limit", "0", "1", "3", "7"],
    "number": ["ratio", "0.5", "2.5"],
    "boolean": ["paused", "true", "false"],
    "text": ["mode", '"night"', '"day"'],
}


def _random(rng: random.Random, kind: str, depth: int) -> str:
    """The text of a random expression of ``kind``, every operation in parentheses."""
    if depth == 0 or rng.random() < 0.2:
        return rng.choice(LEAVES[kind])
    numeric = rng.choice(["integer", "number"])
    if kind == "boolean":
        shape = rng.choice(["logic", "not", "order", "equal"])
        if shape == "logic":
            left, right = (_random(rng, "boolean", depth - 1) for _ in range(2))
            return f"({left} {rng.choice(['and', 'or'])} {right})"
        if shape == "not":
            return f"(not {_random(rng, 'boolean', depth - 1)})"
        operand = numeric if shape == "order" else rng.choice([*LEAVES])
        operators = ["<", "<=", ">", ">="] if shape == "order" else ["==", "!="]
        left, right = (_random(rng, operand, depth - 1) for _ in range(2))
        return f"({left} {rng.choice(operators)} {right})"
    if kind == "text":
        return rng.choice(LEAVES[kind])
    if rng.random() < 0.15:
        return f"(-{_random(rng, kind, depth - 1)})"
    operator = rng.choice(["+", "-", "*", "%"] if kind == "integer" else ["+", "-", "*", "/", "%"])
    other = "integer" if kind == "integer" else numeric
    left, right = _random(rng, kind, depth - 1), _random(rng, other, depth - 1)
    return f"({left} {operator} {right})"


def _python(text: str) -> object:
    """The value Python gives the same text, or the failure it raises: its ``and`` and ``or``
    stop at the first side that settles them, so only the result of both sides worked out is
    compared when a side fails (see the test)."""
    names = {
        "true": True,
        "false": False,
        **{name: VALUES[cast("UUID", IDS[name])] for name in IDS},
    }
    try:
        return eval(text, {"__builtins__": {}}, names)  # noqa: S307 (text built by the test)
    except ZeroDivisionError:
        return Failure("division_by_zero")


def test_random_expressions_give_what_python_gives() -> None:
    rng = random.Random(4)  # noqa: S311 (a fixed seed: the same conditions on every run)
    compared = failures = 0
    for _ in range(3000):
        text = _random(rng, "boolean", rng.randint(1, 5))
        tree = _tree(text)
        if isinstance(expressions.check(tree, TYPES), Problem):
            continue  # a division by a written zero
        program = _program(text)
        assert expressions.check_program(program, VARIABLES) == "boolean", text
        ours, theirs = expressions.evaluate(program, VALUES), _python(text)
        if isinstance(ours, Failure):
            # Python fails too, unless a side it never looked at would have failed.
            failures += 1
            continue
        if isinstance(theirs, Failure):
            continue  # settled by the other side: Python stopped at the failure first
        assert ours == theirs, text
        compared += 1
    assert compared > 1500, compared
    assert failures > 20, failures
