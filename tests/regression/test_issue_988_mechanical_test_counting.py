"""Regression tests for Issues #988 and #1117 — mechanical test counting HARD GATE.

Background
----------
Issue #988: In session #970 the implementer reported "38 new tests added" when the
real delta was 34 — a memory-counting error that escaped review. The
fix introduces a HARD GATE in ``agents/implementer.md`` requiring the
canonical mechanical counter (``bugfix_detector.get_test_count``) to be
invoked before any test-count claim.

Issue #1117: The naive shell counter ``grep -cE "^def test_"`` is anchored at
column 0 and therefore returns ``0`` for class-method tests — the
common pattern in ``tests/regression/``. The fix mandates the
whitespace-tolerant variant ``grep -cE "^[[:space:]]*def[[:space:]]+test_"``
which mirrors the ``^\\s*def\\s+test_`` regex used inside
``bugfix_detector.get_test_count``.

These tests assert that:

1. The HARD GATE documents the canonical Python import.
2. The anchored shell variant is explicitly named as FORBIDDEN.
3. Both issue numbers (#988 and #1117) are referenced in the gate.
4. The documented shell fallback uses whitespace-tolerant matching.
5. The canonical counter actually handles class-method tests — proven by
   running it against this very file, which IS a class-method test
   container by design.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# tests/regression/<file>.py -> parents[2] is the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTER_MD = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "implementer.md"
)
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"


@pytest.fixture(scope="module")
def implementer_md_content() -> str:
    """Return the implementer.md file contents as a single string."""
    return IMPLEMENTER_MD.read_text(encoding="utf-8")


class TestMechanicalCountingGate:
    """Lock the HARD GATE: Mechanical Test Counting section into place."""

    def test_canonical_python_import_documented(
        self, implementer_md_content: str
    ) -> None:
        """The canonical Python import for get_test_count must be present.

        The gate must instruct the implementer to invoke the canonical counter
        rather than counting from memory.
        """
        assert "from bugfix_detector import get_test_count" in implementer_md_content, (
            "implementer.md HARD GATE must document the canonical "
            "`from bugfix_detector import get_test_count` import "
            "(Issue #988 fix)."
        )

    def test_anchored_grep_variant_forbidden(
        self, implementer_md_content: str
    ) -> None:
        """The anchored ``grep -cE "^def test_"`` variant must be FORBIDDEN.

        Issue #1117: the anchored form returns 0 for class-method tests. The
        gate must explicitly flag it as forbidden so the implementer does not
        fall back to it.
        """
        anchored = 'grep -cE "^def test_"'
        assert anchored in implementer_md_content, (
            "implementer.md must explicitly cite the forbidden anchored "
            f"variant `{anchored}` so future implementers do not regress "
            "to it (Issue #1117)."
        )

        # The citation must appear within ~500 chars after a FORBIDDEN /
        # MUST NOT marker, proving it is documented as prohibited rather
        # than recommended.
        idx = implementer_md_content.find(anchored)
        window_start = max(0, idx - 600)
        preceding_window = implementer_md_content[window_start:idx]
        markers = ("FORBIDDEN", "MUST NOT")
        assert any(m in preceding_window for m in markers), (
            "The anchored grep variant must be cited within a FORBIDDEN / "
            "MUST NOT block, not as a recommended option."
        )

    def test_both_issue_numbers_referenced(
        self, implementer_md_content: str
    ) -> None:
        """Both Issue #988 and Issue #1117 must be referenced in the gate."""
        assert "#988" in implementer_md_content, (
            "implementer.md must reference Issue #988 (memory-counting fix)."
        )
        assert "#1117" in implementer_md_content, (
            "implementer.md must reference Issue #1117 (anchored-grep fix)."
        )

    def test_shell_fallback_uses_whitespace_tolerance(
        self, implementer_md_content: str
    ) -> None:
        """The documented shell fallback must allow leading whitespace.

        Either the POSIX bracket class ``[[:space:]]*`` or an equivalent
        whitespace token must appear in the shell command block, mirroring
        the ``^\\s*def\\s+test_`` regex inside ``bugfix_detector``.
        """
        whitespace_tolerant = re.search(
            r"grep\s+-cE\s+\"\^\[\[:space:\]\]\*def\[\[:space:\]\]\+test_",
            implementer_md_content,
        )
        assert whitespace_tolerant is not None, (
            "implementer.md HARD GATE shell fallback must use the "
            "whitespace-tolerant form `^[[:space:]]*def[[:space:]]+test_` "
            "so it counts class-method tests, matching the canonical regex."
        )

    def test_get_test_count_finds_class_methods_in_this_file(
        self, tmp_path: Path
    ) -> None:
        """Prove the canonical counter handles class-method tests (Issue #1117).

        This file is the perfect fixture: all five tests live inside
        ``TestMechanicalCountingGate`` and are therefore indented class
        methods. If ``get_test_count`` is regressed to an anchored regex it
        will return 0 here; the canonical implementation returns at least 5.
        """
        if str(LIB_DIR) not in sys.path:
            sys.path.insert(0, str(LIB_DIR))
        from bugfix_detector import get_test_count

        # Build a minimal project tree: project_root/tests/<copy of this file>.
        tests_subdir = tmp_path / "tests"
        tests_subdir.mkdir()
        fixture = tests_subdir / "test_class_methods.py"
        fixture.write_text(
            Path(__file__).read_text(encoding="utf-8"), encoding="utf-8"
        )

        count = get_test_count(tmp_path)
        assert count >= 5, (
            "bugfix_detector.get_test_count must count indented "
            f"class-method tests (Issue #1117). Got {count}; expected >= 5 "
            "for a file containing TestMechanicalCountingGate."
        )
