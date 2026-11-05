"""Typed access to validated JSON: a mismatch is a bug in Primum, so it raises."""

from uuid import UUID

import pytest

from primum_core.json_values import (
    as_bool,
    as_choice,
    as_float,
    as_int,
    as_list,
    as_object,
    as_str,
    as_uuid,
)

ID = "8d0f6f1e-3b2a-4c55-9a51-1f2d3c4b5a69"


def test_values_of_the_expected_type_pass_through() -> None:
    assert as_object({"a": 1}) == {"a": 1}
    assert as_list([1]) == [1]
    assert as_str("a") == "a"
    assert as_int(3) == 3
    assert as_bool(True) is True
    assert as_uuid(ID) == UUID(ID)
    assert as_choice("on", ("on", "off")) == "on"


def test_a_json_integer_is_a_number() -> None:
    assert as_float(2) == 2.0
    assert isinstance(as_float(2), float)


@pytest.mark.parametrize(
    ("convert", "value"),
    [
        (as_object, []),
        (as_list, {}),
        (as_str, 1),
        (as_int, True),
        (as_int, 1.5),
        (as_float, False),
        (as_bool, 1),
    ],
)
def test_a_value_of_another_type_raises(convert: object, value: object) -> None:
    assert callable(convert)
    with pytest.raises(TypeError, match="the schema and the model disagree"):
        convert(value)


def test_a_choice_must_match_value_and_type() -> None:
    with pytest.raises(TypeError):
        as_choice(1, (True, 2))
    with pytest.raises(TypeError):
        as_choice("dim", ("on", "off"))
