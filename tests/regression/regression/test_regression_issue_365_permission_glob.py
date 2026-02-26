"""Regression test for Issue #365: Edit/Read/Write permission glob syntax.

Claude Code permissions use bare tool names (Edit, Read, Write) for blanket
allow. The glob suffix (**)  doesn't match correctly, causing permission
prompts on every file operation in synced repos.

FORBIDDEN patterns: "Edit(**)", "Read(**)", "Write(**)", "Glob(**)", "Grep(**)"
REQUIRED patterns: "Edit", "Read", "Write", "Glob", "Grep"
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "plugins/autonomous-dev/templates"
CONFIG_DIR = PROJECT_ROOT / "plugins/autonomous-dev/config"
LIB_DIR = PROJECT_ROOT / "plugins/autonomous-dev/lib"

# Tools that must use bare names, never glob suffix
BARE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
FORBIDDEN_PATTERNS = [f'"{t}(**)"' for t in BARE_TOOLS]


class TestNoGlobSuffixInTemplates:
    """All settings templates must use bare tool names, not Tool(**)."""

    def test_all_templates_use_bare_tool_names(self):
        """Regression #365: No template should contain Edit(**) etc."""
        violations = []
        for template in TEMPLATES_DIR.glob("settings.*.json"):
            content = template.read_text()
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in content:
                    violations.append(f"{template.name}: contains {pattern}")
        assert not violations, f"Glob suffix found in templates:\n" + "\n".join(violations)

    def test_global_settings_template_bare_names(self):
        """Global settings template must use bare tool names."""
        content = (CONFIG_DIR / "global_settings_template.json").read_text()
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in content, f"global_settings_template.json contains {pattern}"

    def test_settings_generator_bare_names(self):
        """settings_generator.py SAFE_COMMAND_PATTERNS must use bare names."""
        content = (LIB_DIR / "settings_generator.py").read_text()
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in content, f"settings_generator.py contains {pattern}"

    def test_templates_do_contain_bare_edit(self):
        """At least one template must have bare 'Edit' in allow list."""
        found = False
        for template in TEMPLATES_DIR.glob("settings.*.json"):
            data = json.loads(template.read_text())
            allow = data.get("permissions", {}).get("allow", [])
            if "Edit" in allow:
                found = True
                break
        assert found, "No template has bare 'Edit' in permissions.allow"

    def test_templates_do_contain_bare_read(self):
        """At least one template must have bare 'Read' in allow list."""
        found = False
        for template in TEMPLATES_DIR.glob("settings.*.json"):
            data = json.loads(template.read_text())
            allow = data.get("permissions", {}).get("allow", [])
            if "Read" in allow:
                found = True
                break
        assert found, "No template has bare 'Read' in permissions.allow"
