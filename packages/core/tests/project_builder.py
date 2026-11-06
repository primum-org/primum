"""A project to build file by file in tests, and what the loader found, in a flat form."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from uuid import UUID

from primum_core.errors import CoreErrorCode, Severity
from primum_core.workspace import load_workspace

type Found = tuple[CoreErrorCode, dict[str, object], str, str]
type Ids = Callable[[int], str]


def readable_id(number: int) -> str:
    """A stable UUID a person can tell apart: ``readable_id(7)`` ends in ``7``."""
    return str(UUID(int=number))


@dataclass
class Project:
    """The files of a project, built file by file; ``found()`` loads and flattens the issues."""

    files: dict[PurePosixPath, bytes] = field(default_factory=dict[PurePosixPath, bytes])

    def add(self, path: str, kind: str, id_: str, **fields: object) -> "Project":
        document = {"id": id_, "kind": kind, "schemaVersion": 1, **fields}
        self.files[PurePosixPath(path)] = json.dumps(document).encode()
        return self

    def found(self, *, severity: Severity | None = None) -> list[Found]:
        """``(code, params, path, pointer)`` per issue, every severity unless one is asked."""
        return [
            (
                issue.code,
                dict(issue.params),
                str(issue.location.path) if issue.location else "",
                issue.location.pointer if issue.location else "",
            )
            for issue in load_workspace(self.files).issues
            if severity is None or issue.severity is severity
        ]

    def is_valid(self) -> bool:
        return load_workspace(self.files).value is not None
