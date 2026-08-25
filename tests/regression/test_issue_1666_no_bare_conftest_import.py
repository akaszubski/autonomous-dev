"""Guard for Issue #1666: no bare `from conftest import X` / `import conftest`.

A bare import of `conftest` resolves to whichever `conftest.py` pytest binds
the name to during collection -- not necessarily the one the author intended.
When tests/unit and tests/integration are collected together, this silently
resolves to the wrong module and aborts collection of the whole combined run.
Package-qualified imports (e.g. `from tests.genai._genai_support import X`)
are the sanctioned pattern; see docs on Issue #1666.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_PATTERN = re.compile(r"^(?:from conftest import|import conftest)\b")
_SELF = Path(__file__).resolve()


def _bare_conftest_imports(root: Path) -> list[str]:
    """Return 'file:line' entries for bare `conftest` imports under root."""
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if "archived" in path.parts:
            continue
        if path.resolve() == _SELF:
            continue
        for i, line in enumerate(path.read_text().splitlines(), start=1):
            if _PATTERN.match(line.strip()):
                offenders.append(f"{path.relative_to(root)}:{i}")
    return offenders


def test_no_bare_conftest_import_in_repo() -> None:
    """No file under tests/ may bare-import conftest (Issue #1666)."""
    offenders = _bare_conftest_imports(REPO / "tests")
    assert offenders == [], f"Bare conftest imports found:\n" + "\n".join(offenders)


def test_helper_refuses_bare_import(tmp_path) -> None:
    """REFUSES arm: a scratch file with a bare conftest import is flagged."""
    scratch = tmp_path / "test_scratch_bare.py"
    scratch.write_text("from conftest import Foo\n")
    offenders = _bare_conftest_imports(tmp_path)
    assert len(offenders) == 1
    assert "test_scratch_bare.py:1" in offenders[0]


def test_helper_permits_qualified_import(tmp_path) -> None:
    """PERMITS arm: a package-qualified import is not flagged."""
    scratch = tmp_path / "test_scratch_qualified.py"
    scratch.write_text("from tests.genai._genai_support import GenAIClient\n")
    offenders = _bare_conftest_imports(tmp_path)
    assert offenders == []
