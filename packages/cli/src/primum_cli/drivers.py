"""The driver manifests the CLI knows: copies of ``drivers/`` inside the package (``just gen``).

``core`` reads no files, so the CLI loads the manifests and passes them, by element type, to the
workspace loader. They ship with Primum and are checked by its tests, so a broken one is a bug,
raised as ``ValueError``, not a problem of the user's project.
"""

from pathlib import Path, PurePosixPath

from primum_core.formats import read_driver
from primum_core.generated.model import Driver

DRIVERS = Path(__file__).resolve().parent / "generated" / "drivers"


def load_drivers() -> dict[str, Driver]:
    """Every shipped driver manifest, by element type."""
    drivers: dict[str, Driver] = {}
    for path in sorted(DRIVERS.glob("*.json")):
        parsed = read_driver(PurePosixPath(path.name), path.read_bytes())
        if parsed.value is None or parsed.value.element_type != path.stem:
            codes = ", ".join(issue.code for issue in parsed.issues) or "type differs from name"
            raise ValueError(f"invalid driver manifest {path}: {codes}")
        drivers[parsed.value.element_type] = parsed.value
    return drivers
