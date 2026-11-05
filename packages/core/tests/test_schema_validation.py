"""How validation failures inside nested values are named and pointed at.

The manifest has no arrays yet, so these check the naming helpers directly; the formats of
block 2.3 will cover them end to end.
"""

import pytest

from primum_core.schema_validation import (
    _field,  # pyright: ignore[reportPrivateUsage] -- naming rules tested before any format uses arrays
    _pointer,  # pyright: ignore[reportPrivateUsage]
    _typed_steps,  # pyright: ignore[reportPrivateUsage]
)

DOCUMENT = {"outputs": [{"name": "a"}, {"name": "b", "pins": [1, 2]}], "a/b": {"~x": 1}}


@pytest.mark.parametrize(
    ("raw", "steps", "field", "pointer"),
    [
        ((), (), "", ""),
        (("outputs",), ("outputs",), "outputs", "/outputs"),
        (("outputs", "1", "name"), ("outputs", 1, "name"), "outputs[1].name", "/outputs/1/name"),
        (
            ("outputs", "1", "pins", "0"),
            ("outputs", 1, "pins", 0),
            "outputs[1].pins[0]",
            "/outputs/1/pins/0",
        ),
        (("a/b", "~x"), ("a/b", "~x"), "a/b.~x", "/a~1b/~0x"),
    ],
)
def test_steps_become_a_readable_field_and_a_json_pointer(
    raw: tuple[str, ...], steps: tuple[str | int, ...], field: str, pointer: str
) -> None:
    typed = _typed_steps(raw, DOCUMENT)

    assert typed == steps
    assert _field(typed) == field
    assert _pointer(typed) == pointer


def test_a_numeric_key_of_an_object_stays_a_key() -> None:
    assert _typed_steps(("7",), {"7": True}) == ("7",)
