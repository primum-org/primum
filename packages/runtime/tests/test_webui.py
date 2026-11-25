"""The web UI (``apps/webui``) as the service serves it: built into the package when it is
deployed, next to the page of phase 1 until it replaces it."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from primum_runtime.api import app as app_module
from primum_runtime.api import create_app
from primum_runtime.config import parse_config

CONFIG = parse_config(["--simulate", "--pin", "17"], {})


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<title>the web UI</title>")
    (tmp_path / "assets" / "index.js").write_text("// the app")
    monkeypatch.setattr(app_module, "WEBUI_DIR", tmp_path)
    return tmp_path


@pytest.mark.usefixtures("built")
def test_a_built_web_ui_is_served_under_app_to_anyone_and_the_page_stays() -> None:
    """Like the page, it is where the pairing code is typed: served without pairing."""
    with TestClient(create_app(CONFIG)) as client:
        ui = client.get("/app/")
        script = client.get("/app/assets/index.js")
        page = client.get("/")

    assert (ui.status_code, ui.text) == (200, "<title>the web UI</title>")
    assert (script.status_code, script.text) == (200, "// the app")
    assert (page.status_code, "the web UI" in page.text) == (200, False)


@pytest.mark.usefixtures("built")
def test_the_web_ui_never_hides_the_api() -> None:
    with TestClient(create_app(CONFIG)) as client:
        assert client.get("/api/pairing").json() == {"required": True, "device": None}


def test_a_service_without_the_web_ui_built_starts_and_serves_the_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout that was not built: the build is not in the repository."""
    monkeypatch.setattr(app_module, "WEBUI_DIR", tmp_path / "missing")

    with TestClient(create_app(CONFIG)) as client:
        ui = client.get("/app/")
        page = client.get("/")

    assert (ui.status_code, ui.json()["code"]) == (404, "request.not_found")
    assert page.status_code == 200


@pytest.mark.usefixtures("built")
def test_the_address_without_its_last_slash_leads_to_the_web_ui() -> None:
    """What a person types by hand: an error in JSON is no answer to it."""
    with TestClient(create_app(CONFIG)) as client:
        typed = client.get("/app", follow_redirects=False)
        followed = client.get("/app")

    assert (typed.status_code, typed.headers["location"]) == (307, "/app/")
    assert followed.text == "<title>the web UI</title>"


@pytest.mark.usefixtures("built")
def test_the_index_is_asked_for_again_each_time_and_its_files_are_not() -> None:
    """After a deployment the index names other files: one kept by a browser would ask
    for files that are gone. The files have their content in their name."""
    with TestClient(create_app(CONFIG)) as client:
        index = client.get("/app/")
        named = client.get("/app/index.html")
        script = client.get("/app/assets/index.js")

    assert index.headers["cache-control"] == "no-cache"
    assert named.headers["cache-control"] == "no-cache"
    assert "no-cache" not in script.headers.get("cache-control", "")
