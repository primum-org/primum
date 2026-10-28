import primum_core


def test_version_is_exposed() -> None:
    assert primum_core.__version__ == "0.0.1"
