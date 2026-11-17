"""Values given by name to what a manifest declares: the options of an element and the
arguments of an action, checked again on the board.

``core`` checks a project before it is deployed; a driver checks what reaches it all the
same, since it is the last thing between a value and the hardware. What a manifest limits on
every board and what the board limits in its profile both count.
"""

from collections.abc import Mapping

from primum_core.generated.model import DriverParameter
from primum_core.values import Value, fits
from primum_runtime.errors import ErrorCode, ErrorParam, PrimumError

type Limits = Mapping[str, tuple[float, float]]  # by the name of the value


def resolve(
    element: str,
    given: Mapping[str, Value],
    parameters: tuple[DriverParameter, ...],
    board: Limits | None = None,
) -> dict[str, Value]:
    """A value for each of ``parameters``: the one given, or its default.

    Fails with ``element.value_unknown`` for a name that is not declared,
    ``element.value_missing`` for one without a default that is not given,
    ``element.value_invalid`` for a value of another type or not among the choices, and
    ``element.value_out_of_range`` for a number outside the manifest's limits or the board's.
    """
    declared = {parameter.name for parameter in parameters}
    for name in given:
        if name not in declared:
            raise _problem(ErrorCode.ELEMENT_VALUE_UNKNOWN, element, name)
    values: dict[str, Value] = {}
    for parameter in parameters:
        value = given.get(parameter.name, parameter.default)
        if value is None:
            raise _problem(ErrorCode.ELEMENT_VALUE_MISSING, element, parameter.name)
        _check(element, parameter, value, (board or {}).get(parameter.name))
        values[parameter.name] = value
    return values


def _check(
    element: str, parameter: DriverParameter, value: Value, board: tuple[float, float] | None
) -> None:
    allowed = not parameter.choices or value in parameter.choices
    if not fits(value, parameter.type) or not allowed:
        raise _problem(ErrorCode.ELEMENT_VALUE_INVALID, element, parameter.name)
    if isinstance(value, bool | str):
        return
    manifest = None
    if parameter.min is not None and parameter.max is not None:
        manifest = (parameter.min, parameter.max)
    for limits in (manifest, board):
        if limits is not None and not limits[0] <= value <= limits[1]:
            params = {"min": limits[0], "max": limits[1]}
            raise _problem(ErrorCode.ELEMENT_VALUE_OUT_OF_RANGE, element, parameter.name, params)


def _problem(
    code: ErrorCode, element: str, name: str, more: Mapping[str, ErrorParam] | None = None
) -> PrimumError:
    return PrimumError(code, {"element": element, "name": name, **(more or {})})
