"""GENERATED from schemas/ by tools/gen_schemas.py: do not edit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from primum_core.json_values import JsonObject, as_str, as_uuid


@dataclass(frozen=True, kw_only=True, slots=True)
class Project:
    """The manifest of a project: project.json, at the root of the project's folder."""

    id: UUID
    kind: Literal["project"] = "project"
    schema_version: Literal[1] = 1
    name: str
    description: str | None = None


def parse_project(data: JsonObject) -> Project:
    """Build a ``Project`` from a document that passed its schema."""
    return Project(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        description=as_str(data["description"]) if "description" in data else None,
    )
