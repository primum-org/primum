"""GENERATED from schemas/ by tools/gen_schemas.py: do not edit."""

import json
from collections.abc import Mapping
from typing import Final

# Each schema by file name, which is also its $id.
SCHEMAS: Final[Mapping[str, Mapping[str, object]]] = {
    "common.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "common.schema.json",
  "title": "Common definitions",
  "description": "Definitions shared by every Primum format.",
  "$defs": {
    "id": {
      "description": "A UUID that identifies an entity for good. Files reference each other by id, never by path.",
      "type": "string",
      "format": "uuid"
    },
    "name": {
      "description": "A name a person reads: shown in the UI, never used as a reference.",
      "type": "string",
      "minLength": 1,
      "maxLength": 80
    },
    "description": {
      "description": "Free text that explains what something is for.",
      "type": "string",
      "maxLength": 2000
    }
  }
}
"""
    ),
    "project.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "project.schema.json",
  "title": "Project",
  "description": "The manifest of a project: project.json, at the root of the project's folder.",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "kind", "schemaVersion", "name"],
  "properties": {
    "id": { "$ref": "common.schema.json#/$defs/id" },
    "kind": { "const": "project" },
    "schemaVersion": { "const": 1 },
    "name": { "$ref": "common.schema.json#/$defs/name" },
    "description": { "$ref": "common.schema.json#/$defs/description" }
  }
}
"""
    ),
}
