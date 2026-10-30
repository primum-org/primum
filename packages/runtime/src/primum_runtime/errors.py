"""Errors raised by the runtime: a stable code and parameters, never text (decision 0009)."""

from collections.abc import Mapping
from types import MappingProxyType

type ErrorScalar = str | int | float | bool
# Lists are tuples of scalars; the UI formats them for the user's language ("17 and 27").
type ErrorParam = ErrorScalar | tuple[ErrorScalar, ...]


class PrimumError(Exception):
    """An error identified by a stable ``code`` (``<area>.<reason>``) and simple ``params``
    (scalars or tuples of scalars).

    The message shown to users and AI comes from the ``i18n/`` catalogs, keyed by ``code``.
    """

    def __init__(self, code: str, params: Mapping[str, ErrorParam] | None = None) -> None:
        self.code = code
        self.params: Mapping[str, ErrorParam] = MappingProxyType(dict(params or {}))
        super().__init__(code, dict(self.params))

    def __str__(self) -> str:
        """``code (name=value, ...)`` for logs and tracebacks; users read the catalogs."""
        if not self.params:
            return self.code
        params = ", ".join(f"{name}={value}" for name, value in self.params.items())
        return f"{self.code} ({params})"
