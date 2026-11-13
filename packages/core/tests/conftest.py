"""Fixtures shared by the tests of ``core``."""

import pytest

from project_builder import Ids, Project, readable_id


@pytest.fixture
def ids() -> Ids:
    """Readable, stable UUIDs: ``ids(7)``."""
    return readable_id


@pytest.fixture
def project(ids: Ids) -> Project:
    """A manifest, a Pi with an LED and a button, and nothing else."""
    return (
        Project()
        .add("project.json", "project", ids(1), name="Shop window")
        .add(
            "hardware.hw",
            "hardware",
            ids(2),
            boards=[{"id": ids(3), "name": "Pi", "model": "rpi4b"}],
            elements=[
                {"id": ids(4), "name": "LED", "board": ids(3), "type": "digital_output", "pin": 17},
                {
                    "id": ids(5),
                    "name": "Button",
                    "board": ids(3),
                    "type": "digital_input",
                    "pin": 27,
                    "config": [{"name": "pull", "value": "up"}],
                },
            ],
        )
    )
