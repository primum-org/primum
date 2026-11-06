"""Generate primum-core's view of the formats from the hand-written JSON Schemas in schemas/.

Two modules under ``packages/core/src/primum_core/generated/``, never edited by hand:

- ``schemas.py``: the schemas, byte for byte, which ``core`` validates documents against;
- ``model.py``: a frozen dataclass for every object of the formats, and a ``parse_<name>()``
  for each, which builds it from a document that already passed validation.

The schemas use a small subset of JSON Schema (``schemas/README.md``), so the same formats can
be generated for TypeScript and, later, C++. Anything outside it fails here, with its place.

    uv run just gen         # write the modules
    uv run just gen-check   # fail if they are out of date (part of `just check`)
"""

import argparse
import json
import keyword
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TypeIs

import fastjsonschema

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "schemas"
TARGET = ROOT / "packages" / "core" / "src" / "primum_core" / "generated"
SCHEMA_SUFFIX = ".schema.json"
HEADER = '"""GENERATED from schemas/ by tools/gen_schemas.py: do not edit."""'

# The subset of JSON Schema that formats may use: common to every draft from 07 on and easy to
# map to types in any language.
KEYWORDS = frozenset(
    {
        "$schema", "$id", "$defs", "$ref", "$comment", "title", "description", "examples",
        "type", "properties", "required", "additionalProperties", "items", "enum", "const",
        "default", "format", "pattern", "minLength", "maxLength", "minimum", "maximum",
        "minItems", "maxItems", "uniqueItems",
    }
)  # fmt: skip
FORMATS = frozenset({"uuid"})
SCALARS = {
    "string": ("str", "as_str"),
    "integer": ("int", "as_int"),
    "number": ("float", "as_float"),
    "boolean": ("bool", "as_bool"),
}

type Schema = dict[str, object]
type JsonLiteral = str | int | bool
type Default = JsonLiteral | float


class SchemaError(ValueError):
    """A schema is outside the subset the generator supports."""


def _is_object(value: object) -> TypeIs[dict[str, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeIs[list[object]]:
    return isinstance(value, list)


# --- the model: what a schema says, in terms of Python types --------------------------------


@dataclass(frozen=True)
class Scalar:
    annotation: str
    parser: str


@dataclass(frozen=True)
class Constant:
    value: JsonLiteral


@dataclass(frozen=True)
class Choice:
    values: tuple[JsonLiteral, ...]


@dataclass(frozen=True)
class Array:
    item: "TypeSpec"


@dataclass(frozen=True)
class Reference:
    class_name: str


type TypeSpec = Scalar | Constant | Choice | Array | Reference


@dataclass(frozen=True)
class FieldSpec:
    json_name: str
    name: str
    type: TypeSpec
    required: bool
    default: Default | None = None


@dataclass(frozen=True)
class ClassSpec:
    name: str
    description: str
    fields: tuple[FieldSpec, ...]


# --- reading the schemas --------------------------------------------------------------------


def load(directory: Path) -> dict[str, tuple[str, Schema]]:
    """Every schema by file name, with its source text, checked against the subset."""
    schemas: dict[str, tuple[str, Schema]] = {}
    for path in sorted(directory.glob(f"*{SCHEMA_SUFFIX}")):
        text = path.read_text(encoding="utf-8")
        schema: object = json.loads(text)
        if not _is_object(schema):
            raise SchemaError(f"{path.name}: a schema must be an object")
        if schema.get("$id") != path.name:
            raise SchemaError(f"{path.name}: its $id must be its file name, {path.name!r}")
        _check_keywords(schema, path.name)
        schemas[path.name] = (text, schema)
    return schemas


def _check_keywords(schema: Schema, where: str) -> None:
    for key, value in schema.items():
        if key not in KEYWORDS:
            raise SchemaError(f"{where}: keyword {key!r} is not supported (schemas/README.md)")
        if key == "format" and value not in FORMATS:
            raise SchemaError(f"{where}: format {value!r} is not supported")
    for key in ("properties", "$defs"):
        for name, child in _children(schema, key).items():
            _check_keywords(child, f"{where}/{key}/{name}")
    items = schema.get("items")
    if _is_object(items):
        _check_keywords(items, f"{where}/items")


def _children(schema: Schema, key: str) -> dict[str, Schema]:
    value = schema.get(key, {})
    if not _is_object(value):
        raise SchemaError(f"{key} must be an object")
    children: dict[str, Schema] = {}
    for name, child in value.items():
        if not _is_object(child):
            raise SchemaError(f"{key}/{name} must be an object")
        children[name] = child
    return children


class _Builder:
    """Turns the schemas into class specs, resolving ``$ref`` between files."""

    def __init__(self, schemas: dict[str, Schema]) -> None:
        self._schemas = schemas
        self._classes: dict[str, ClassSpec] = {}

    def build(self) -> tuple[ClassSpec, ...]:
        for file, schema in self._schemas.items():
            if _is_object_schema(schema):
                self._add(_class_name(_text(schema, "title", file)), schema, file, file)
            for key, definition in _children(schema, "$defs").items():
                if _is_object_schema(definition):
                    self._add(_class_name(key), definition, file, f"{file}#/$defs/{key}")
        return tuple(self._classes.values())

    def _add(self, name: str, schema: Schema, file: str, where: str) -> None:
        if name in self._classes:
            raise SchemaError(f"{where}: class {name} is defined twice")
        if schema.get("additionalProperties") is not False:
            raise SchemaError(f"{where}: objects must set additionalProperties to false")
        properties = _children(schema, "properties")
        required = _strings(schema.get("required", []), f"{where}/required")
        if unknown := set(required) - set(properties):
            raise SchemaError(f"{where}: required names unknown properties {sorted(unknown)}")
        fields = tuple(
            self._field(name, child, name in required, file, f"{where}/properties/{name}")
            for name, child in properties.items()
        )
        description = _text(schema, "description", where) if "description" in schema else ""
        self._classes[name] = ClassSpec(name, description, fields)

    def _field(
        self, json_name: str, schema: Schema, required: bool, file: str, where: str
    ) -> FieldSpec:
        spec = self._type(schema, file, where)
        default = schema.get("default")
        if isinstance(spec, Constant) and not required:
            raise SchemaError(f"{where}: a const property must be required")
        if default is not None and (required or not _is_default(default)):
            raise SchemaError(
                f"{where}: a default must be a string, number or boolean, on an optional property"
            )
        return FieldSpec(json_name, _field_name(json_name), spec, required, default)

    def _type(self, schema: Schema, file: str, where: str) -> TypeSpec:
        if "$ref" in schema:
            return self._reference(_text(schema, "$ref", where), file, where)
        if "const" in schema:
            return Constant(_literal(schema["const"], where))
        if "enum" in schema:
            return _choice(schema["enum"], where)
        kind = schema.get("type")
        if kind == "string" and schema.get("format") == "uuid":
            return Scalar("UUID", "as_uuid")
        if kind == "array":
            items = schema.get("items")
            if not _is_object(items):
                raise SchemaError(f"{where}: an array needs an items schema")
            return Array(self._type(items, file, f"{where}/items"))
        if kind == "object":
            raise SchemaError(f"{where}: define nested objects in $defs and use them with $ref")
        if isinstance(kind, str) and kind in SCALARS:
            return Scalar(*SCALARS[kind])
        if _is_list(kind) and len(kind) > 1 and all(item in SCALARS for item in kind):
            # A value that may be a number, a boolean or a text (a variable's initial value).
            annotations = dict.fromkeys(SCALARS[str(item)][0] for item in kind)
            return Scalar(" | ".join(annotations), "as_scalar")
        raise SchemaError(
            f"{where}: needs a type (or a list of scalar types), a const, an enum or a $ref"
        )

    def _reference(self, ref: str, file: str, where: str) -> TypeSpec:
        target_file, _, pointer = ref.partition("#")
        target_file = target_file or file
        schema = self._schemas.get(target_file)
        if schema is None:
            raise SchemaError(f"{where}: $ref to an unknown schema {target_file!r}")
        if not pointer:
            return Reference(_class_name(_text(schema, "title", target_file)))
        match = re.fullmatch(r"/\$defs/(\w+)", pointer)
        definitions = _children(schema, "$defs")
        if match is None or match[1] not in definitions:
            raise SchemaError(f"{where}: $ref must name a schema or one of its $defs: {ref!r}")
        definition = definitions[match[1]]
        if _is_object_schema(definition):
            return Reference(_class_name(match[1]))
        return self._type(definition, target_file, f"{target_file}#{pointer}")


def _is_object_schema(schema: Schema) -> bool:
    return schema.get("type") == "object"


def _text(schema: Schema, key: str, where: str) -> str:
    value = schema.get(key)
    if not isinstance(value, str):
        raise SchemaError(f"{where}: {key} must be a string")
    return value


def _strings(value: object, where: str) -> list[str]:
    if not _is_list(value) or not all(isinstance(item, str) for item in value):
        raise SchemaError(f"{where}: must be a list of names")
    return [str(item) for item in value]


def _is_literal(value: object) -> TypeIs[JsonLiteral]:
    return isinstance(value, str | int | bool)


def _is_default(value: object) -> TypeIs[Default]:
    return isinstance(value, str | int | float | bool)


def _literal(value: object, where: str) -> JsonLiteral:
    if not _is_literal(value):
        raise SchemaError(f"{where}: const and enum values must be strings, integers or booleans")
    return value


def _choice(values: object, where: str) -> Choice:
    if not _is_list(values) or not values:
        raise SchemaError(f"{where}: enum must be a non-empty list")
    choices = tuple(_literal(value, where) for value in values)
    if len({type(choice) for choice in choices}) != 1 or isinstance(choices[0], bool):
        raise SchemaError(f"{where}: enum values must be all strings or all integers")
    return Choice(choices)


def _class_name(name: str) -> str:
    """``board profile``, ``board_profile`` or ``boardProfile`` → ``BoardProfile``."""
    words = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", name)
    if not words:
        raise SchemaError(f"cannot make a class name from {name!r}")
    return "".join(word[0].upper() + word[1:] for word in words)


def _field_name(name: str) -> str:
    """``schemaVersion`` → ``schema_version``; Python keywords get a trailing ``_``."""
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
    if not snake.isidentifier():
        raise SchemaError(f"property {name!r} is not a valid identifier")
    return f"{snake}_" if keyword.iskeyword(snake) else snake


# --- writing Python -------------------------------------------------------------------------


def _python_literal(value: Default) -> str:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, str) else repr(value)


def _annotation(spec: TypeSpec) -> str:
    match spec:
        case Scalar(annotation=annotation):
            return annotation
        case Constant(value=value):
            return f"Literal[{_python_literal(value)}]"
        case Choice(values=values):
            return f"Literal[{', '.join(_python_literal(value) for value in values)}]"
        case Array(item=item):
            return f"tuple[{_annotation(item)}, ...]"
        case Reference(class_name=class_name):
            return class_name


def _parser(spec: TypeSpec, expression: str, choices: str, depth: int = 0) -> str:
    """Python that builds the value of ``spec`` from the JSON value ``expression``.

    ``choices`` names the constant that holds the values of an enum (``_choices``).
    """
    match spec:
        case Scalar(parser=parser):
            return f"{parser}({expression})"
        case Constant(value=value):
            return _python_literal(value)
        case Choice():
            return f"as_choice({expression}, {choices})"
        case Array(item=item):
            variable = "item" if depth == 0 else f"item{depth}"
            parsed = _parser(item, variable, choices, depth + 1)
            return f"tuple({parsed} for {variable} in as_list({expression}))"
        case Reference(class_name=class_name):
            return f"{_parse_function(class_name)}(as_object({expression}))"


def _parse_function(class_name: str) -> str:
    return f"parse_{_field_name(class_name[0].lower() + class_name[1:])}"


def _field_line(field: FieldSpec) -> str:
    annotation = _annotation(field.type)
    if isinstance(field.type, Constant):
        return f"    {field.name}: {annotation} = {_python_literal(field.type.value)}"
    if field.required:
        return f"    {field.name}: {annotation}"
    if field.default is not None:
        return f"    {field.name}: {annotation} = {_python_literal(field.default)}"
    if isinstance(field.type, Array):
        return f"    {field.name}: {annotation} = ()"
    return f"    {field.name}: {annotation} | None = None"


def _fallback(field: FieldSpec) -> str:
    """The value of an optional field that is absent: its default, nothing, or no items."""
    if field.default is not None:
        return _python_literal(field.default)
    return "()" if isinstance(field.type, Array) else "None"


def _choices(spec: TypeSpec) -> Choice | None:
    """The enum of a field, directly or as the items of its arrays."""
    while isinstance(spec, Array):
        spec = spec.item
    return spec if isinstance(spec, Choice) else None


def _choices_name(owner: ClassSpec, field: FieldSpec) -> str:
    owner_name = _field_name(owner.name[0].lower() + owner.name[1:])
    return f"_{owner_name.upper()}_{field.name.upper().rstrip('_')}"


def _render_choices(owner: ClassSpec) -> list[str]:
    """One typed constant per enum: it lets ``as_choice`` return the field's ``Literal``."""
    lines: list[str] = []
    for field in owner.fields:
        choice = _choices(field.type)
        if choice is not None:
            values = ", ".join(_python_literal(value) for value in choice.values)
            values += "," if len(choice.values) == 1 else ""
            annotation = f"Final[tuple[{_annotation(choice)}, ...]]"
            lines.append(f"{_choices_name(owner, field)}: {annotation} = ({values})")
    return lines


def _argument_line(owner: ClassSpec, field: FieldSpec) -> str:
    value = _parser(field.type, f'data["{field.json_name}"]', _choices_name(owner, field))
    if not field.required:
        value = f'{value} if "{field.json_name}" in data else {_fallback(field)}'
    return f"        {field.name}={value},"


def _render_class(spec: ClassSpec) -> str:
    lines = ["@dataclass(frozen=True, kw_only=True, slots=True)", f"class {spec.name}:"]
    if spec.description:
        lines += [f'    """{spec.description}"""', ""]
    lines += [_field_line(field) for field in spec.fields] or ["    pass"]
    return "\n".join(lines)


def _render_parser(spec: ClassSpec) -> str:
    arguments = [_argument_line(spec, field) for field in spec.fields if not _is_constant(field)]
    call = f"{spec.name}(\n" + "\n".join(arguments) + "\n    )" if arguments else f"{spec.name}()"
    return (
        f"def {_parse_function(spec.name)}(data: JsonObject) -> {spec.name}:\n"
        f'    """Build a ``{spec.name}`` from a document that passed its schema."""\n'
        f"    return {call}"
    )


def _is_constant(field: FieldSpec) -> bool:
    return isinstance(field.type, Constant)


def render_model(classes: tuple[ClassSpec, ...]) -> str:
    choices = [line for spec in classes for line in _render_choices(spec)]
    body = "\n\n\n".join(
        ["\n".join(choices)] * bool(choices)
        + [_render_class(spec) for spec in classes]
        + [_render_parser(spec) for spec in classes]
    )
    helpers = sorted(set(re.findall(r"\b(as_\w+)\(", body)))
    typing = [name for name in ("Final", "Literal") if f"{name}[" in body]
    imports = ["from dataclasses import dataclass"]
    if typing:
        imports.append(f"from typing import {', '.join(typing)}")
    if re.search(r"\bUUID\b", body):
        imports.append("from uuid import UUID")
    imports.append("")
    imports.append(f"from primum_core.json_values import {', '.join(['JsonObject', *helpers])}")
    # Classes may refer to classes defined after them.
    head = "\n".join([HEADER, "", "from __future__ import annotations", "", *imports])
    return f"{head}\n\n\n{body}\n"


def render_schemas(schemas: dict[str, tuple[str, Schema]]) -> str:
    entries: list[str] = []
    for name, (text, _) in schemas.items():
        if '"""' in text or "\\" in text:
            raise SchemaError(f"{name}: triple quotes and backslashes are not supported")
        entries.append(f'    "{name}": json.loads(\n        """\n{text.strip()}\n"""\n    ),')
    return "\n".join(
        [
            HEADER,
            "",
            "import json",
            "from collections.abc import Mapping",
            "from typing import Final",
            "",
            "# Each schema by file name, which is also its $id.",
            "SCHEMAS: Final[Mapping[str, Mapping[str, object]]] = {",
            *entries,
            "}",
            "",
        ]
    )


def check_compiles(schemas: dict[str, Schema]) -> None:
    """Compile each schema as ``core`` will, so a malformed one fails here, not in ``core``."""
    for name, schema in schemas.items():
        try:
            fastjsonschema.compile(schema, handlers={"": schemas.__getitem__}, use_default=False)
        except (fastjsonschema.JsonSchemaDefinitionException, KeyError) as error:
            raise SchemaError(f"{name}: not a valid schema: {error}") from error


def generate(source: Path) -> dict[str, str]:
    """The content of every generated module, by file name."""
    schemas = load(source)
    parsed = {name: schema for name, (_, schema) in schemas.items()}
    classes = _Builder(parsed).build()
    check_compiles(parsed)  # after the subset checks, whose messages are clearer
    return {
        "__init__.py": f"{HEADER}\n",
        "schemas.py": render_schemas(schemas),
        "model.py": render_model(classes),
    }


def differences(files: dict[str, str], target: Path) -> list[str]:
    present = {path.name for path in target.glob("*.py")}
    problems = [
        f"missing or stale: {name}"
        for name, content in files.items()
        if name not in present or (target / name).read_text(encoding="utf-8") != content
    ]
    problems += [f"extra: {name}" for name in sorted(present - set(files))]
    return problems


def write(files: dict[str, str], target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in target.glob("*.py"):
        if path.name not in files:
            path.unlink()
    for name, content in files.items():
        (target / name).write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate core's types from schemas/.")
    parser.add_argument("--check", action="store_true", help="fail if a module is out of date")
    args = parser.parse_args(argv)

    try:
        files = generate(SOURCE)
    except SchemaError as error:
        sys.stderr.write(f"schemas/{error}\n")
        return 1
    if args.check:
        problems = differences(files, TARGET)
        for problem in problems:
            sys.stderr.write(f"{TARGET.relative_to(ROOT)}: {problem}\n")
        if problems:
            sys.stderr.write("Run `uv run just gen` and commit the result.\n")
        return 1 if problems else 0
    write(files, TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
