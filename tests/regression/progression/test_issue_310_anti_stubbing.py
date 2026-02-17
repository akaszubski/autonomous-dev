"""
Regression tests for Issue #310: Anti-stubbing enforcement.

Bug: Model replaces broken code with `raise NotImplementedError()` and declares
the feature "implemented". Same root cause as #206 — path of least resistance.

Fix: HARD GATE "No Stubs, No Shortcuts" in implementer.md with FORBIDDEN list,
and matching HARD GATE in implement.md STEP 5.

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


class TestIssue310AntiStubbing:
    """Regression: implementer must forbid stubs and placeholders."""

    def test_implementer_md_has_forbidden_list(self):
        """implementer.md must have a FORBIDDEN list."""
        content = (PLUGIN_DIR / "agents" / "implementer.md").read_text()
        assert "FORBIDDEN" in content, "Regression #310: implementer must have FORBIDDEN list"

    def test_implementer_md_forbids_not_implemented_error(self):
        """implementer.md must explicitly mention NotImplementedError as forbidden."""
        content = (PLUGIN_DIR / "agents" / "implementer.md").read_text()
        assert "NotImplementedError" in content, (
            "Regression #310: must forbid NotImplementedError"
        )

    def test_implementer_md_has_hard_gate(self):
        """implementer.md must have HARD GATE language for anti-stubbing."""
        content = (PLUGIN_DIR / "agents" / "implementer.md").read_text()
        assert "HARD GATE" in content, "Regression #310: implementer must have HARD GATE"

    def test_implementer_md_has_usability_test(self):
        """implementer.md must ask 'Can a user actually USE this feature?'."""
        content = (PLUGIN_DIR / "agents" / "implementer.md").read_text()
        # The key test from the fix
        assert "USE" in content or "use this feature" in content.lower(), (
            "Regression #310: must include usability check"
        )

    def test_implement_md_step5_mentions_stubs(self):
        """implement.md STEP 5 must mention stub/placeholder prohibition."""
        content = (PLUGIN_DIR / "commands" / "implement.md").read_text()
        step5_section = content.split("### STEP 5:")[1].split("### STEP 5.5")[0]
        assert "stub" in step5_section.lower() or "placeholder" in step5_section.lower(), (
            "Regression #310: STEP 5 must mention stub/placeholder prohibition"
        )
