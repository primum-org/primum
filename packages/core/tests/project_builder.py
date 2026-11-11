"""A project to build file by file in tests, and what the loader found, in a flat form."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from uuid import UUID

from primum_core.errors import CoreErrorCode, Severity
from primum_core.formats import read_board_profile, read_driver
from primum_core.generated.model import BoardProfile, Driver
from primum_core.workspace import load_workspace

ROOT = Path(__file__).resolve().parents[3]
BOARDS = ROOT / "boards"
DRIVERS_FOLDER = ROOT / "drivers"


def shipped_profiles() -> dict[str, BoardProfile]:
    """The board profiles of ``boards/``, as the CLI passes them (by model)."""
    profiles: dict[str, BoardProfile] = {}
    for path in sorted(BOARDS.glob("*.json")):
        parsed = read_board_profile(PurePosixPath(path.name), path.read_bytes())
        assert parsed.value is not None, parsed.issues
        profiles[parsed.value.model] = parsed.value
    return profiles


def shipped_drivers() -> dict[str, Driver]:
    """The driver manifests of ``drivers/``, as the CLI passes them (by element type)."""
    drivers: dict[str, Driver] = {}
    for path in sorted(DRIVERS_FOLDER.glob("*.json")):
        parsed = read_driver(PurePosixPath(path.name), path.read_bytes())
        assert parsed.value is not None, parsed.issues
        drivers[parsed.value.element_type] = parsed.value
    return drivers


PROFILES = shipped_profiles()
DRIVERS = shipped_drivers()


type Found = tuple[CoreErrorCode, dict[str, object], str, str]
type Ids = Callable[[int], str]


def readable_id(number: int) -> str:
    """A stable UUID a person can tell apart: ``readable_id(7)`` ends in ``7``."""
    return str(UUID(int=number))


def driver_manifest(element_type: str, **fields: object) -> dict[str, object]:
    """The document of a driver manifest for a test: an output with one action, ``on``, unless
    ``fields`` say otherwise."""
    return {
        "id": readable_id(900),
        "kind": "driver",
        "schemaVersion": 1,
        "elementType": element_type,
        "capabilities": ["switch"],
        "platforms": ["linux"],
        "conflictPolicy": "latest_wins",
        "safeState": "on",
        "config": [],
        "actions": [{"name": "on", "parameters": []}],
        **fields,
    }


def driver(element_type: str, **fields: object) -> Driver:
    """A driver for a test, read as the shipped ones are."""
    document = json.dumps(driver_manifest(element_type, **fields)).encode()
    parsed = read_driver(PurePosixPath(f"{element_type}.json"), document)
    assert parsed.value is not None, parsed.issues
    return parsed.value


@dataclass
class Project:
    """The files of a project, built file by file; ``found()`` loads and flattens the issues.

    ``drivers`` are the shipped manifests unless a test gives its own.
    """

    files: dict[PurePosixPath, bytes] = field(default_factory=dict[PurePosixPath, bytes])
    drivers: dict[str, Driver] = field(default_factory=lambda: dict(DRIVERS))

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
            for issue in load_workspace(self.files, PROFILES, self.drivers).issues
            if severity is None or issue.severity is severity
        ]

    def is_valid(self) -> bool:
        return load_workspace(self.files, PROFILES, self.drivers).value is not None
