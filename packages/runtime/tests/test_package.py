import primum_core
import primum_runtime


def test_runtime_and_core_versions_match() -> None:
    assert primum_runtime.__version__ == primum_core.__version__
