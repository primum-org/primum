"""Read a project folder into what ``core`` takes: each file's path, relative to the folder,
and its bytes.

Hidden files and folders (a name starting with ``.``, such as ``.git``) are not part of the
project and are skipped, and so are links, so nothing outside the folder is read. So is a
deployment package (``*.package.json``): ``primum build .`` writes it there, and it is what the
project gives, not part of it.
"""

from pathlib import Path, PurePosixPath

PACKAGE_SUFFIX = ".package.json"


def read_folder(folder: Path) -> dict[PurePosixPath, bytes]:
    """Every file of ``folder``; ``OSError`` if one cannot be read."""
    files: dict[PurePosixPath, bytes] = {}
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if any(part.startswith(".") for part in relative.parts) or path.is_symlink():
            continue
        if path.name.endswith(PACKAGE_SUFFIX):
            continue
        if path.is_file():
            files[PurePosixPath(relative.as_posix())] = path.read_bytes()
    return files
