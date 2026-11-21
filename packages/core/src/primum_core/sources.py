"""Where the value of an argument comes from (decision 0024).

An argument of a clip, or of a block, is a value written there or a name (``valueOf``): a
value parameter of the sequence it is written in, or a constant or a variable its folder sees.
A constant is as good as written. A parameter is whatever the block that includes the sequence
gives it, which may be a name in turn. A variable is read while running, so only its type and
its limits are known here.
"""

from collections.abc import Iterable, Mapping
from uuid import UUID

from primum_core.generated.model import ClipArgument, Sequence
from primum_core.given import Fixed, FromVariable, Source, Unbound
from primum_core.references import LocatedContent
from primum_core.scopes import visible_definitions
from primum_core.timeline import Binding, NameRef


class Names:
    """What the names of each sequence stand for."""

    def __init__(self, files: Iterable[LocatedContent]) -> None:
        files = tuple(files)
        self._visible = visible_definitions(files)
        self._parameters: Mapping[UUID, Mapping[str, str]] = {
            file.content.id: {
                parameter.name: parameter.type for parameter in file.content.parameters
            }
            for file in files
            if isinstance(file.content, Sequence)
        }

    def of_argument(
        self, argument: ClipArgument, origin: UUID | None, values: Mapping[str, Binding]
    ) -> Source | None:
        """Where the value of a clip's argument comes from; ``origin`` is the sequence the
        clip is written in and ``values`` what its parameters were given. ``None`` when it
        cannot be told: a name that is not one, which the scopes check reports."""
        if argument.value is not None:
            return Fixed(argument.value)
        if argument.value_of is None or origin is None:
            return None
        if argument.value_of in self._parameters.get(origin, {}) and argument.value_of in values:
            return self.of(values[argument.value_of])
        return self.of(NameRef(argument.value_of, origin))

    def of(self, binding: Binding) -> Source | None:
        """Where a value, or a name of a sequence, comes from."""
        if not isinstance(binding, NameRef):
            return Fixed(binding)
        value_type = self._parameters.get(binding.sequence, {}).get(binding.name)
        if value_type is not None:
            return None if value_type == "element" else Unbound(binding.name, value_type)
        definition = self._visible.get(binding.sequence, {}).get(binding.name)
        if definition is None:
            return None
        if definition.kind == "variable":
            return FromVariable(
                definition.id,
                definition.name,
                definition.value_type,
                definition.min,
                definition.max,
            )
        return None if definition.value is None else Fixed(definition.value)
