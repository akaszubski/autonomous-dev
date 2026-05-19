"""Regression tests for /refactor flag surface after Issue #1098 rename.

Verifies that both --docs (drift detection) and --docs-redundancy (renamed
prior behavior) are documented in commands/refactor.md and CHANGELOG.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REFACTOR_MD = _REPO_ROOT / "plugins/autonomous-dev/commands/refactor.md"
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"


def test_docs_flag_in_command_md() -> None:
    """--docs flag must appear in commands/refactor.md."""
    content = _REFACTOR_MD.read_text(encoding="utf-8")
    assert "--docs" in content, (
        "--docs flag not found in commands/refactor.md after Issue #1098 rename"
    )


def test_docs_redundancy_flag_in_command_md() -> None:
    """--docs-redundancy flag must appear in commands/refactor.md."""
    content = _REFACTOR_MD.read_text(encoding="utf-8")
    assert "--docs-redundancy" in content, (
        "--docs-redundancy flag not found in commands/refactor.md; "
        "rename from --docs was not documented"
    )


def test_changelog_dual_action() -> None:
    """CHANGELOG.md must mention both --docs-redundancy rename and --docs drift detection."""
    content = _CHANGELOG.read_text(encoding="utf-8")
    # (a) --docs-redundancy must appear (the renamed flag)
    assert "--docs-redundancy" in content, (
        "CHANGELOG.md does not mention --docs-redundancy; "
        "the historical entry for --docs should be corrected and [Unreleased] entry added"
    )
    # (b) drift detection for --docs must be mentioned
    assert "drift" in content.lower(), (
        "CHANGELOG.md does not mention 'drift'; "
        "the [Unreleased] Added entry for --docs drift detection is missing"
    )
