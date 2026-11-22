"""A project: a folder of files, read into one immutable ``Workspace`` (decision 0004).

``core`` reads no files: the caller passes every file of the project folder, by its path
relative to the folder, with its content. ``project.json`` at the root is the manifest; the
other files are read by their extension (``.hw``, ``.vars``, ``.sec``, ``.evt``, ``.sched``,
``.auto``). A file of no project type is ignored with a warning. The caller also passes the
board profiles (``boards/``, by model) and the driver manifests (``drivers/``, by element
type): the elements of each board are checked against the first (its resources and its
limits), and their configuration and what clips ask of them against the second.

Extensions are matched without regard to case (``SHOW.SEC`` is a sequence), as Windows does.

Checks come in stages, so a problem is reported once, where it is: first each file on its own
(text, JSON, schema, then the fields that depend on the case and the configuration of each
element),
and, once every file reads, the project as a whole: ids and references, which need every file;
then the scopes of names, the components, the actions of the clips, the clips and sequences
that overlap, the resources of each board and the limits it puts on its elements' options.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from primum_core.actions import check_actions
from primum_core.board_limits import check_board_limits
from primum_core.components import check_components
from primum_core.config import check_config
from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue, Location, Severity
from primum_core.events import check_events
from primum_core.formats import (
    PROJECT_FILE_FORMATS,
    Parsed,
    ProjectFileContent,
    read_manifest,
    read_project_file,
)
from primum_core.generated.model import Project
from primum_core.overlaps import check_overlaps
from primum_core.references import LocatedContent, check_references
from primum_core.resources import Profiles, check_resources
from primum_core.schedules import check_schedules
from primum_core.scopes import check_scopes
from primum_core.states import check_returns
from primum_core.variants import check_variants

MANIFEST = PurePosixPath("project.json")


@dataclass(frozen=True)
class ProjectFile:
    """A file of the project: where it is (for display) and what it holds."""

    path: PurePosixPath
    content: ProjectFileContent


@dataclass(frozen=True)
class Workspace:
    """A project that passed every check: its manifest, its files, by path, and the driver
    manifests it was checked against, which is what it means against: whoever compiles it
    uses these and no others."""

    manifest: Project
    files: tuple[ProjectFile, ...]
    drivers: Drivers


def load_workspace(
    files: Mapping[PurePosixPath, bytes],
    profiles: Profiles,
    drivers: Drivers,
    time_zones: Iterable[str] | None = None,
) -> Parsed[Workspace]:
    """Read and check a project from its files (path relative to the project folder → content),
    the board profiles it may use (by model), the driver manifests (by element type) and
    the names of the time zones there are (``None``: the project's is not checked).

    The workspace comes back when no issue is an error; warnings come with it.
    """
    issues: list[Issue] = []
    manifest = _manifest(files, issues)
    read: list[ProjectFile] = []
    complete = manifest is not None
    for path in sorted(files):
        if path == MANIFEST:
            continue
        if path.suffix.lower() not in PROJECT_FILE_FORMATS:
            issues.append(
                Issue(CoreErrorCode.FILE_NOT_IN_FORMAT, {}, Location(path), Severity.WARNING)
            )
            continue
        parsed = read_project_file(path, files[path])
        issues += parsed.issues
        if parsed.value is None:
            complete = False
            continue
        read.append(ProjectFile(path, parsed.value))
        issues += check_variants(_located(read[-1]))
        issues += check_config(_located(read[-1]), drivers)
    if complete and manifest is not None:
        located = [_located(file) for file in read]
        issues += check_references(located, (manifest.id, Location(MANIFEST, file_id=manifest.id)))
        issues += check_scopes(located)
        issues += check_components(located)
        issues += check_actions(located, drivers)
        issues += check_events(located, drivers)
        at = Location(MANIFEST, file_id=manifest.id)
        issues += check_schedules(located, (manifest, at), time_zones)
        issues += check_overlaps(located, drivers)
        issues += check_returns(located, drivers)
        issues += check_resources(located, profiles)
        issues += check_board_limits(located, profiles, drivers)
    if manifest is None or any(issue.severity is Severity.ERROR for issue in issues):
        return Parsed(None, tuple(issues))
    return Parsed(Workspace(manifest, tuple(read), dict(drivers)), tuple(issues))


def _manifest(files: Mapping[PurePosixPath, bytes], issues: list[Issue]) -> Project | None:
    if MANIFEST not in files:
        issues.append(Issue(CoreErrorCode.PROJECT_MANIFEST_MISSING, {}, Location(MANIFEST)))
        return None
    parsed = read_manifest(MANIFEST, files[MANIFEST])
    issues += parsed.issues
    return parsed.value


def _located(file: ProjectFile) -> LocatedContent:
    return LocatedContent(file.content, Location(file.path, file_id=file.content.id))
