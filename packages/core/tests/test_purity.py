"""Calls that make core impure but that the import contracts cannot see.

`just arch` forbids importing time, random, os... but `datetime`, `uuid` and `pathlib` stay
importable because parsing dates, ids and pure paths is pure. This test walks the source of
`primum_core` and rejects the impure calls those modules offer: reading the clock, generating
random ids and touching the filesystem.
"""

import ast
from pathlib import Path

import pytest

import primum_core

SOURCE_ROOT = Path(primum_core.__file__).parent

CLOCK_METHODS = frozenset({"now", "utcnow", "today", "fromtimestamp", "utcfromtimestamp"})
CLOCK_OWNERS = frozenset({"datetime", "date"})
RANDOM_ID_FUNCTIONS = frozenset({"uuid1", "uuid4"})
IO_BUILTINS = frozenset({"open", "input", "breakpoint"})
FILESYSTEM_METHODS = frozenset(
    {
        "read_text", "read_bytes", "write_text", "write_bytes", "open", "touch", "mkdir",
        "rmdir", "unlink", "rename", "replace", "exists", "is_file", "is_dir", "iterdir",
        "glob", "rglob", "stat", "resolve", "cwd", "home", "expanduser",
    }
)  # fmt: skip


def _owner_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _impurity(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        if func.id in RANDOM_ID_FUNCTIONS:
            return f"{func.id}() generates a random id: take ids as parameters"
        if func.id in IO_BUILTINS:
            return f"{func.id}() does I/O"
        return None
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr in CLOCK_METHODS and _owner_name(func.value) in CLOCK_OWNERS:
        return f"{_owner_name(func.value)}.{func.attr}() reads the clock: take time as a parameter"
    if func.attr in RANDOM_ID_FUNCTIONS:
        return f"{func.attr}() generates a random id: take ids as parameters"
    if func.attr in FILESYSTEM_METHODS:
        return f".{func.attr}() touches the filesystem"
    return None


def find_impure_calls(source: str, filename: str = "<source>") -> list[str]:
    """Return one ``file:line: reason`` entry per impure call found in ``source``."""
    tree = ast.parse(source, filename=filename)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (reason := _impurity(node)):
            found.append(f"{filename}:{node.lineno}: {reason}")
    return found


@pytest.mark.parametrize(
    "snippet",
    [
        "datetime.now()",
        "datetime.datetime.utcnow()",
        "date.today()",
        "uuid.uuid4()",
        "uuid4()",
        "open('project.json')",
        "Path('x').read_text()",
        "path.write_bytes(b'')",
        "Path.cwd()",
    ],
)
def test_detector_flags_impure_calls(snippet: str) -> None:
    assert find_impure_calls(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        "datetime.fromisoformat('2026-10-28T12:00:00')",
        "UUID('12345678-1234-5678-1234-567812345678')",
        "PurePosixPath('scenes/nativity') / 'star.sec'",
        "timedelta(seconds=3)",
    ],
)
def test_detector_allows_pure_calls(snippet: str) -> None:
    assert not find_impure_calls(snippet)


def test_core_source_has_no_impure_calls() -> None:
    found: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        found += find_impure_calls(source, str(path.relative_to(SOURCE_ROOT)))

    assert not found, "core must stay pure:\n" + "\n".join(found)
