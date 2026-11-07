"""The board profiles the CLI knows: copies of ``boards/`` inside the package (``just gen``).

``core`` reads no files, so the CLI loads the profiles and passes them, by model, to the
workspace loader. They ship with Primum and are checked by its tests, so a broken one is a bug,
raised as ``ValueError``, not a problem of the user's project.
"""

from pathlib import Path, PurePosixPath

from primum_core.formats import read_board_profile
from primum_core.generated.model import BoardProfile

PROFILES = Path(__file__).resolve().parent / "generated" / "boards"


def load_profiles() -> dict[str, BoardProfile]:
    """Every shipped board profile, by model."""
    profiles: dict[str, BoardProfile] = {}
    for path in sorted(PROFILES.glob("*.json")):
        parsed = read_board_profile(PurePosixPath(path.name), path.read_bytes())
        if parsed.value is None or parsed.value.model != path.stem:
            codes = ", ".join(issue.code for issue in parsed.issues) or "model differs from name"
            raise ValueError(f"invalid board profile {path}: {codes}")
        profiles[parsed.value.model] = parsed.value
    return profiles
