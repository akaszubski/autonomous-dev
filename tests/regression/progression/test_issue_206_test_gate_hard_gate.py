"""
Regression tests for Issue #206: Test gate bypass.

Bug: Model sees failing tests (e.g., "45/56 passing, 80%"), declares it a
"solid foundation", and skips to STEP 6 (validation) without fixing failures.

Fix: HARD GATE language in implement.md STEP 5 with explicit FORBIDDEN behaviors
and three allowed resolutions (fix, skip, adjust).

These tests verify the fix infrastructure exists and would break if removed.
"""

from pathlib import Path

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

PLUGIN_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev"


class TestIssue206TestGateHardGate:
    """Regression: STEP 5 must enforce 0 test failures as HARD GATE."""

    def test_implement_md_step5_has_hard_gate(self):
        """STEP 5 must contain HARD GATE language."""
        content = (PLUGIN_DIR / "commands" / "implement.md").read_text()
        # Split at STEP 5 heading, take content before STEP 5.5
        step5_section = content.split("### STEP 5:")[1].split("### STEP 5.5")[0]
        assert "HARD GATE" in step5_section, "Regression #206: STEP 5 must be a HARD GATE"

    def test_implement_md_step5_requires_zero_failures(self):
        """STEP 5 must explicitly require 0 failures."""
        content = (PLUGIN_DIR / "commands" / "implement.md").read_text()
        step5_section = content.split("### STEP 5:")[1].split("### STEP 5.5")[0]
        assert "0 failures" in step5_section, "Regression #206: must require 0 failures"

    def test_implement_md_step5_has_three_resolutions(self):
        """STEP 5 must offer three resolution options: fix, skip, adjust."""
        content = (PLUGIN_DIR / "commands" / "implement.md").read_text()
        step5_section = content.split("### STEP 5:")[1].split("### STEP 5.5")[0]
        assert "Fix it" in step5_section, "Regression #206: must offer 'Fix it' resolution"
        assert "Skip it" in step5_section, "Regression #206: must offer 'Skip it' resolution"
        assert "Adjust it" in step5_section, "Regression #206: must offer 'Adjust it' resolution"

    def test_implement_md_step5_blocks_step6(self):
        """STEP 5 must explicitly block progression to STEP 6."""
        content = (PLUGIN_DIR / "commands" / "implement.md").read_text()
        step5_section = content.split("### STEP 5:")[1].split("### STEP 5.5")[0]
        assert "Do NOT proceed to STEP 6" in step5_section, (
            "Regression #206: must explicitly block STEP 6 with failures"
        )
