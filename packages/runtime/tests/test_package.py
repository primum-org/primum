from importlib.metadata import version

import primum_core
import primum_runtime


def test_version_has_a_single_source() -> None:
    assert primum_runtime.__version__ == version("primum-runtime")


def test_runtime_can_use_core() -> None:
    assert primum_core.__version__
