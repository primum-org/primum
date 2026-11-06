"""Read a project folder into what ``core`` takes: each file's path, relative to the folder,
and its bytes.

Hidden files and folders (a name starting with ``.``, such as ``.git``) are not part of the
project and are skipped, and so are links, so nothing outside the folder is read.
"""

from pathlib import Path, PurePosixPath


def read_folder(folder: Path) -> dict[PurePosixPath, bytes]:
    """Every file of ``folder``; ``OSError`` if one cannot be read."""
    files: dict[PurePosixPath, bytes] = {}
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if any(part.startswith(".") for part in relative.parts) or path.is_symlink():
            continue
        if path.is_file():
            files[PurePosixPath(relative.as_posix())] = path.read_bytes()
    return files
