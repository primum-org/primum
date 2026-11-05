# Type stub for the part of fastjsonschema that primum-core uses (the library ships no hints).
# Checked against fastjsonschema 2.22: fastjsonschema/__init__.py and exceptions.py.

from collections.abc import Callable, Mapping

class JsonSchemaException(ValueError): ...

class JsonSchemaValueException(JsonSchemaException):
    message: str
    value: object
    name: str
    definition: dict[str, object]
    rule: str
    @property
    def path(self) -> list[str]: ...
    @property
    def rule_definition(self) -> object: ...

class JsonSchemaValuesException(JsonSchemaException):
    errors: list[JsonSchemaValueException]

class JsonSchemaDefinitionException(JsonSchemaException): ...

def compile(
    definition: Mapping[str, object] | bool,
    handlers: Mapping[str, Callable[[str], Mapping[str, object]]] = ...,
    formats: Mapping[str, str | Callable[[object], bool]] = ...,
    use_default: bool = ...,
    use_formats: bool = ...,
    detailed_exceptions: bool = ...,
    fast_fail: bool = ...,
) -> Callable[[object], object]: ...
