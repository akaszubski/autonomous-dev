"""Integration tests for CI audit scripts (Issue #970).

Validates that:
- ``scripts/audit_hook_recovery.py`` runs in WARN-ONLY mode and exits 0.
- ``unified_pre_tool.py`` instruments at least 3 deny sites with
  ``log_block_with_recovery(`` calls (AC #8).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_hook_recovery.py"
UNIFIED_PRE_TOOL = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
)


def test_hook_recovery_audit_warn_only():
    """Default (WARN-ONLY) audit must exit 0 even when violations exist."""
    assert AUDIT_SCRIPT.exists(), f"missing audit script: {AUDIT_SCRIPT}"
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"WARN-ONLY mode must exit 0 (Phase 1).\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_unified_pre_tool_has_min_3_recovery_calls():
    """``unified_pre_tool.py`` must have >= 3 log_block_with_recovery() calls (AC#8)."""
    assert UNIFIED_PRE_TOOL.exists(), f"missing target: {UNIFIED_PRE_TOOL}"
    source = UNIFIED_PRE_TOOL.read_text(encoding="utf-8")
    matches = re.findall(r"log_block_with_recovery\s*\(", source)
    assert len(matches) >= 3, (
        f"AC#8 requires at least 3 log_block_with_recovery() calls "
        f"in unified_pre_tool.py; found {len(matches)}"
    )


def test_audit_strict_mode_succeeds_on_self():
    """Audit script in --strict mode either passes (clean) or surfaces violations.

    This is a smoke test: we don't require a clean audit in Phase 1, but if
    --strict fails, the failure output must be human-readable.
    """
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--strict"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Either exit 0 (clean) or exit 1 (violations) — both acceptable.
    assert result.returncode in (0, 1)
    # Output must mention the audit, not crash.
    assert "hook_recovery audit" in result.stdout
