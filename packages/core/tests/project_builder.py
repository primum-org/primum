"""A project to build file by file in tests, and what the loader found, in a flat form."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from uuid import UUID

from primum_core.errors import CoreErrorCode, Severity
from primum_core.formats import read_board_profile
from primum_core.generated.model import BoardProfile
from primum_core.workspace import load_workspace

BOARDS = Path(__file__).resolve().parents[3] / "boards"


def shipped_profiles() -> dict[str, BoardProfile]:
    """The board profiles of ``boards/``, as the CLI passes them (by model)."""
    profiles: dict[str, BoardProfile] = {}
    for path in sorted(BOARDS.glob("*.json")):
        parsed = read_board_profile(PurePosixPath(path.name), path.read_bytes())
        assert parsed.value is not None, parsed.issues
        profiles[parsed.value.model] = parsed.value
    return profiles


PROFILES = shipped_profiles()

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
            for issue in load_workspace(self.files, PROFILES).issues
            if severity is None or issue.severity is severity
        ]

    def is_valid(self) -> bool:
        return load_workspace(self.files, PROFILES).value is not None
