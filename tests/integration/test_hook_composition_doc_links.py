"""Integration: docs/HOOK-COMPOSITION.md has no broken links (Issue #972 AC#7).

Uses the stdlib ``scripts/check_doc_links.py`` (no Node toolchain).
HTTP checks are disabled by default.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_doc_links.py"
DOC = REPO_ROOT / "docs" / "HOOK-COMPOSITION.md"


def test_hook_composition_doc_has_no_broken_links():
    """All relative links in HOOK-COMPOSITION.md MUST resolve."""
    assert DOC.exists(), f"missing {DOC}"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--no-http", str(DOC)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"check_doc_links.py reported broken links in {DOC}:\n"
        f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
    )
