from importlib.metadata import version

import primum_cli


def test_version_has_a_single_source() -> None:
    assert primum_cli.__version__ == version("primum-cli")
