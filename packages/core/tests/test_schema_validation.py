"""How places inside a document are named and pointed at.

fastjsonschema reports array indices as text; they become ints by looking at the document.
"""

import pytest

from primum_core.pointers import field_name, pointer
from primum_core.schema_validation import (
    _typed_steps,  # pyright: ignore[reportPrivateUsage] -- the mapping from fastjsonschema's paths
)

DOCUMENT = {"outputs": [{"name": "a"}, {"name": "b", "pins": [1, 2]}], "a/b": {"~x": 1}}


@pytest.mark.parametrize(
    ("raw", "steps", "field", "expected_pointer"),
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
    raw: tuple[str, ...], steps: tuple[str | int, ...], field: str, expected_pointer: str
) -> None:
    typed = _typed_steps(raw, DOCUMENT)

    assert typed == steps
    assert field_name(typed) == field
    assert pointer(typed) == expected_pointer


def test_a_numeric_key_of_an_object_stays_a_key() -> None:
    assert _typed_steps(("7",), {"7": True}) == ("7",)
