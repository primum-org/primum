"""Impure names that the import contracts cannot see.

`just arch` forbids importing time, random, os... but `datetime`, `uuid` and `pathlib` stay
importable because parsing dates, ids and pure paths is pure. This test walks the source of
`primum_core`, resolves every name through the module's imports (aliases included) and rejects
the impure parts of those modules: the concrete `Path` classes (filesystem I/O), random ids and
clock reads. `PurePath`, `PurePosixPath`, `UUID(...)` and `datetime.fromisoformat(...)` stay
allowed.

Names are matched by what they resolve to, never by method name, so `text.replace(...)` or
`resolver.resolve(...)` are not mistaken for filesystem calls.
"""

import ast
from pathlib import Path

import pytest

import primum_core

SOURCE_ROOT = Path(primum_core.__file__).parent

FORBIDDEN_NAMES = {
    "pathlib.Path": "uses the filesystem: use PurePosixPath for paths",
    "pathlib.PosixPath": "uses the filesystem: use PurePosixPath for paths",
    "pathlib.WindowsPath": "uses the filesystem: use PurePosixPath for paths",
    "uuid.uuid1": "generates an id: take ids as parameters",
    "uuid.uuid4": "generates a random id: take ids as parameters",
    "datetime.datetime.now": "reads the clock: take time as a parameter",
    "datetime.datetime.utcnow": "reads the clock: take time as a parameter",
    "datetime.datetime.today": "reads the clock: take time as a parameter",
    "datetime.datetime.fromtimestamp": "depends on the local clock settings",
    "datetime.datetime.utcfromtimestamp": "depends on the local clock settings",
    "datetime.date.today": "reads the clock: take time as a parameter",
    "datetime.date.fromtimestamp": "depends on the local clock settings",
}
FORBIDDEN_BUILTINS = frozenset({"open", "input", "breakpoint", "eval", "exec", "__import__"})


def _import_bindings(tree: ast.Module) -> dict[str, str]:
    """Map each name bound by an import to the fully qualified name it refers to."""
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bindings[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    bindings[top] = top
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                bindings[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return bindings


def _qualified_name(node: ast.expr, bindings: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value, bindings)
        return f"{owner}.{node.attr}" if owner else None
    return None


def find_impure_names(source: str, filename: str = "<source>") -> list[str]:
    """Return one ``file:line: reason`` entry per impure name used or imported in ``source``."""
    tree = ast.parse(source, filename=filename)
    bindings = _import_bindings(tree)
    found: list[str] = []
    for name, qualified in bindings.items():
        if qualified in FORBIDDEN_NAMES:
            found.append(f"{filename}: imports {qualified} as {name}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name | ast.Attribute):
            qualified = _qualified_name(node, bindings)
            if qualified in FORBIDDEN_NAMES:
                found.append(f"{filename}:{node.lineno}: {qualified} {FORBIDDEN_NAMES[qualified]}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_BUILTINS
            and node.func.id not in bindings
        ):
            found.append(f"{filename}:{node.lineno}: {node.func.id}() does I/O or runs code")
    return found


@pytest.mark.parametrize(
    "snippet",
    [
        "import datetime\ndatetime.datetime.now()",
        "from datetime import datetime\ndatetime.now()",
        "from datetime import datetime as dt\ndt.now()",
        "import datetime as d\nd.date.today()",
        "from datetime import date\ndate.today()",
        "import uuid\nuuid.uuid4()",
        "from uuid import uuid4 as new_id\nnew_id()",
        "from pathlib import Path\nPath('project.json').read_text()",
        "import pathlib\npathlib.Path.cwd()",
        "import pathlib as p\nmake = p.Path",
        "open('project.json')",
    ],
)
def test_detector_flags_impure_names(snippet: str) -> None:
    assert find_impure_names(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        "name.replace('-', '_')",
        "resolver.resolve(project)",
        "scope.exists(name)",
        "stream.open()",
        "from datetime import datetime\ndatetime.fromisoformat('2026-10-28T12:00:00')",
        "from datetime import timedelta\ntimedelta(seconds=3)",
        "from uuid import UUID\nUUID('12345678-1234-5678-1234-567812345678')",
        "from pathlib import PurePosixPath\nPurePosixPath('scenes') / 'star.sec'",
        "import pathlib\npathlib.PurePath('a').with_suffix('.sec')",
    ],
)
def test_detector_allows_pure_code(snippet: str) -> None:
    assert not find_impure_names(snippet)


def test_core_source_has_no_impure_names() -> None:
    found: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        found += find_impure_names(source, str(path.relative_to(SOURCE_ROOT)))

    assert not found, "core must stay pure:\n" + "\n".join(found)
