import json

import pytest

from gen_tokens import SOURCE, TokenError, render

MINIMAL = {
    "meta": {"name": "Test"},
    "radius": {"md": "2px"},
    "themes": {
        "light": {"color": {"text": {"primary": "#111111"}}},
        "dark": {"color": {"text": {"primary": "#eeeeee"}}},
    },
}


def test_render_names_properties_after_their_path() -> None:
    css = render(MINIMAL)

    assert "--radius-md: 2px;" in css
    assert "--color-text-primary: #111111;" in css


def test_render_emits_dark_theme_for_attribute_and_system_preference() -> None:
    css = render(MINIMAL)

    assert css.count("--color-text-primary: #eeeeee;") == 2
    assert '[data-theme="dark"]' in css
    assert "@media (prefers-color-scheme: dark)" in css


def test_render_skips_meta() -> None:
    assert "Test" not in render(MINIMAL)


def test_render_rejects_themes_with_different_tokens() -> None:
    broken = {**MINIMAL, "themes": {"light": {"a": "1"}, "dark": {"b": "2"}}}

    with pytest.raises(TokenError):
        render(broken)


def test_project_tokens_define_every_reserved_semantic_color() -> None:
    css = render(json.loads(SOURCE.read_text(encoding="utf-8")))

    for meaning in ("danger", "warning", "success", "running", "offline", "safe", "proposal"):
        assert f"--color-semantic-{meaning}:" in css
