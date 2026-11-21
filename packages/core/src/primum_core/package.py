"""The deployment package: its hash, and reading one (decision 0024).

A package says its own hash: the sha256 of the rest of it in a canonical form (keys sorted, no
spaces, UTF-8, text as it is, a whole number without a fraction: ``80``, never ``80.0``).
Whoever reads a package checks it, so one that was cut short or edited by hand is refused
before anything runs.
"""

import hashlib
import json
from collections.abc import Mapping
from pathlib import PurePosixPath

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.formats import Parsed, decode
from primum_core.generated.model import Package, parse_package
from primum_core.json_values import as_object, is_array, is_object
from primum_core.schema_validation import validate

HASH_FIELD = "hash"
SCHEMA = "package.schema.json"


def package_hash(document: Mapping[str, object]) -> str:
    """The hash of a package: of everything in ``document`` but its ``hash``."""
    hashed = whole_numbers({key: value for key, value in document.items() if key != HASH_FIELD})
    canonical = json.dumps(hashed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def whole_numbers(value: object) -> object:
    """``value`` with every whole number as an integer, all the way in: JSON has one kind of
    number, so ``80.0`` and ``80`` are the same value and must give the same hash."""
    if is_object(value):
        return {key: whole_numbers(item) for key, item in value.items()}
    if is_array(value):
        return [whole_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def read_package(path: PurePosixPath, content: bytes) -> Parsed[Package]:
    """Read a deployment package: its shape, then that its hash is the hash of the rest."""
    location = Location(path)
    document = decode(content, location)
    if isinstance(document, Issue):
        return Parsed(None, (document,))
    issues = validate(SCHEMA, document, location)
    if issues:
        return Parsed(None, issues)
    if not is_object(document) or document[HASH_FIELD] != package_hash(document):
        at = Location(path, "/" + HASH_FIELD)
        return Parsed(None, (Issue(CoreErrorCode.PACKAGE_HASH_MISMATCH, {}, at),))
    return Parsed(parse_package(as_object(document)))
