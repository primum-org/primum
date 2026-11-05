"""The generator of core's types: the subset it supports, what it writes, and --check."""

import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pytest

import gen_schemas
from gen_schemas import SchemaError, differences, generate, write

DRAFT = "https://json-schema.org/draft/2020-12/schema"
ID = "8d0f6f1e-3b2a-4c55-9a51-1f2d3c4b5a69"

COMMON: dict[str, object] = {
    "$schema": DRAFT,
    "$id": "common.schema.json",
    "$defs": {
        "id": {"type": "string", "format": "uuid"},
        "name": {"type": "string", "minLength": 1},
    },
}
SHOW: dict[str, object] = {
    "$schema": DRAFT,
    "$id": "show.schema.json",
    "title": "Show",
    "description": "A show.",
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "kind", "name", "mode", "steps"],
    "properties": {
        "id": {"$ref": "common.schema.json#/$defs/id"},
        "kind": {"const": "show"},
        "name": {"$ref": "common.schema.json#/$defs/name"},
        "mode": {"enum": ["once", "loop"]},
        "level": {"enum": [1, 2, 3]},
        "steps": {"type": "array", "items": {"$ref": "#/$defs/step"}},
        "grid": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}},
        "speed": {"type": "number", "default": 1},
        "enabled": {"type": "boolean"},
    },
    "$defs": {
        "step": {
            "type": "object",
            "additionalProperties": False,
            "required": ["atMs", "if"],
            "properties": {
                "atMs": {"type": "integer", "minimum": 0},
                "if": {"type": "string"},
            },
        }
    },
}


def _write_schemas(directory: Path, *schemas: Mapping[str, object]) -> Path:
    for schema in schemas:
        (directory / str(schema["$id"])).write_text(json.dumps(schema), encoding="utf-8")
    return directory


def _import(path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    name = f"generated_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve the module's postponed annotations through sys.modules.
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    files = generate(_write_schemas(tmp_path, COMMON, SHOW))
    write(files, tmp_path / "out")
    return _import(tmp_path / "out" / "model.py", monkeypatch)


def test_every_object_becomes_a_frozen_dataclass_with_python_names(model: ModuleType) -> None:
    step = model.Step(at_ms=5, if_="dark")

    assert step.at_ms == 5
    with pytest.raises(AttributeError):
        step.at_ms = 6


def test_a_validated_document_is_parsed_into_the_dataclasses(model: ModuleType) -> None:
    document = {
        "id": ID,
        "kind": "show",
        "name": "Night",
        "mode": "loop",
        "level": 2,
        "steps": [{"atMs": 0, "if": "dark"}, {"atMs": 500, "if": "always"}],
        "grid": [[1, 2], [3]],
        "speed": 2,
        "enabled": True,
    }

    show = model.parse_show(document)

    assert show == model.Show(
        id=UUID(ID),
        name="Night",
        mode="loop",
        level=2,
        steps=(model.Step(at_ms=0, if_="dark"), model.Step(at_ms=500, if_="always")),
        grid=((1, 2), (3,)),
        speed=2.0,
        enabled=True,
    )
    assert show.kind == "show"


def test_absent_optional_fields_take_their_default_or_none(model: ModuleType) -> None:
    show = model.parse_show({"id": ID, "kind": "show", "name": "N", "mode": "once", "steps": []})

    assert (show.speed, show.enabled, show.level, show.grid) == (1, None, None, None)


def test_the_schemas_module_holds_each_schema_by_file_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = generate(_write_schemas(tmp_path, COMMON, SHOW))
    write(files, tmp_path / "out")

    schemas = _import(tmp_path / "out" / "schemas.py", monkeypatch).SCHEMAS

    assert schemas == {"common.schema.json": COMMON, "show.schema.json": SHOW}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"oneOf": []}, "keyword 'oneOf' is not supported"),
        ({"additionalProperties": True}, "additionalProperties to false"),
        ({"required": ["missing"]}, "unknown properties"),
        ({"properties": {"when": {"type": "string", "format": "date"}}}, "format 'date'"),
        ({"properties": {"inner": {"type": "object"}}}, "define nested objects in $defs"),
        ({"properties": {"kind": {"const": "show"}}, "required": []}, "const property must be"),
        ({"properties": {"mixed": {"enum": ["a", 1]}}}, "all strings or all integers"),
        ({"properties": {"bad": {"$ref": "#/$defs/nope"}}}, "must name a schema or one of"),
        ({"properties": {"bad": {"$ref": "other.schema.json"}}}, "unknown schema"),
        ({"properties": {"bad": {"type": ["string", "null"]}}}, "needs a single type"),
        ({"$id": "renamed.schema.json"}, "its $id must be its file name"),
    ],
)
def test_schemas_outside_the_subset_fail_with_their_place(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    schema: dict[str, object] = {
        "$schema": DRAFT,
        "$id": "thing.schema.json",
        "title": "Thing",
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        **change,
    }
    path = tmp_path / "thing.schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(SchemaError, match=re.escape(message)):
        generate(tmp_path)


def test_check_reports_missing_stale_and_extra_modules(tmp_path: Path) -> None:
    files = generate(_write_schemas(tmp_path, COMMON, SHOW))
    target = tmp_path / "out"
    write(files, target)
    (target / "model.py").write_text("# edited by hand\n", encoding="utf-8")
    (target / "schemas.py").unlink()
    (target / "old.py").write_text("", encoding="utf-8")

    assert differences(files, target) == [
        "missing or stale: schemas.py",
        "missing or stale: model.py",
        "extra: old.py",
    ]


def test_write_removes_modules_whose_source_is_gone(tmp_path: Path) -> None:
    target = tmp_path / "out"
    target.mkdir()
    (target / "old.py").write_text("", encoding="utf-8")

    write(generate(_write_schemas(tmp_path, COMMON, SHOW)), target)

    assert sorted(path.name for path in target.glob("*.py")) == [
        "__init__.py",
        "model.py",
        "schemas.py",
    ]


def test_the_repository_modules_are_up_to_date() -> None:
    assert gen_schemas.main(["--check"]) == 0
