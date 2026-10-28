from importlib.metadata import version

import primum_core


def test_version_has_a_single_source() -> None:
    assert primum_core.__version__ == version("primum-core")
