"""Errors raised by the runtime: a stable code and parameters, never text (decision 0009)."""

from collections.abc import Mapping
from types import MappingProxyType

type ErrorParam = str | int | float | bool


class PrimumError(Exception):
    """An error identified by a stable ``code`` (``<area>.<reason>``) and simple ``params``.

    The message shown to users and AI comes from the ``i18n/`` catalogs, keyed by ``code``.
    """

    def __init__(self, code: str, params: Mapping[str, ErrorParam] | None = None) -> None:
        self.code = code
        self.params: Mapping[str, ErrorParam] = MappingProxyType(dict(params or {}))
        super().__init__(code, dict(self.params))
