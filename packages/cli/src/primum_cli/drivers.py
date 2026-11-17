"""The driver manifests the CLI knows: copies of ``drivers/`` inside the package (``just gen``).

``core`` reads no files, so the CLI reads them and ``core`` makes of them what the workspace
loader takes. They ship with Primum and are checked by its tests, so a broken one is a bug,
raised as ``ValueError``, not a problem of the user's project.
"""

from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from primum_core.formats import read_drivers
from primum_core.generated.model import Driver

DRIVERS = Path(__file__).resolve().parent / "generated" / "drivers"


def load_drivers() -> Mapping[str, Driver]:
    """Every shipped driver manifest, by element type."""
    files = {PurePosixPath(path.name): path.read_bytes() for path in DRIVERS.glob("*.json")}
    parsed = read_drivers(files)
    if parsed.value is None:
        codes = ", ".join(f"{issue.code} ({issue.location})" for issue in parsed.issues)
        raise ValueError(f"invalid driver manifests in {DRIVERS}: {codes}")
    return parsed.value
