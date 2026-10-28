import primum_core
import primum_runtime


def test_runtime_exposes_its_version() -> None:
    assert primum_runtime.__version__


def test_runtime_can_use_core() -> None:
    assert primum_core.__version__
