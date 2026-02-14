"""Regression tests for global_settings_template.json integrity.

Ensures all hook commands referenced in the settings template actually
exist as source files in plugins/autonomous-dev/hooks/.

Incident: PR #336-#343 archived hooks but left stale references in
global_settings_template.json, causing "hook not found" errors after install.
"""

import json
import re
from pathlib import Path

import pytest


class TestSettingsTemplateIntegrity:
    """Verify settings template references only existing hooks."""

    TEMPLATE_PATH = "plugins/autonomous-dev/config/global_settings_template.json"

    def _load_template(self, project_root: Path) -> dict:
        """Load and parse the settings template."""
        template_file = project_root / self.TEMPLATE_PATH
        if not template_file.exists():
            pytest.skip(f"Template not found: {self.TEMPLATE_PATH}")
        return json.loads(template_file.read_text())

    def _extract_hook_refs(self, template: dict) -> list[str]:
        """Extract all hook file references from the template."""
        refs = []
        hooks_section = template.get("hooks", {})
        for lifecycle, matchers in hooks_section.items():
            if not isinstance(matchers, list):
                continue
            for matcher in matchers:
                hook_list = matcher.get("hooks", [])
                for hook in hook_list:
                    command = hook.get("command", "")
                    # Extract filename from command like "python3 ~/.claude/hooks/foo.py"
                    match = re.search(r'hooks/(\w+\.py)', command)
                    if match:
                        refs.append(match.group(1))
        return refs

    def test_all_template_hooks_exist_in_source(self, project_root: Path, plugins_dir: Path):
        """Every hook referenced in settings template must exist in hooks/ source."""
        template = self._load_template(project_root)
        hook_refs = self._extract_hook_refs(template)
        assert len(hook_refs) > 0, "No hook references found in template"

        hooks_dir = plugins_dir / "hooks"
        missing = []
        for hook_name in hook_refs:
            hook_path = hooks_dir / hook_name
            if not hook_path.exists():
                missing.append(f"  {hook_name} — referenced in template but not in hooks/")

        if missing:
            pytest.fail(
                f"Settings template references missing hooks ({len(missing)}):\n"
                + "\n".join(missing)
            )

    def test_template_is_valid_json(self, project_root: Path):
        """Settings template must be valid JSON."""
        template_file = project_root / self.TEMPLATE_PATH
        if not template_file.exists():
            pytest.skip(f"Template not found: {self.TEMPLATE_PATH}")
        # json.loads will raise on invalid JSON
        data = json.loads(template_file.read_text())
        assert isinstance(data, dict), "Template root must be a JSON object"
        assert "hooks" in data, "Template must have 'hooks' section"

    def test_no_archived_hook_references(self, project_root: Path):
        """Settings template must not reference hooks in archived/ directory."""
        template_file = project_root / self.TEMPLATE_PATH
        if not template_file.exists():
            pytest.skip(f"Template not found: {self.TEMPLATE_PATH}")
        content = template_file.read_text()
        assert "archived" not in content, (
            "Settings template references 'archived' — "
            "all hook references should point to active hooks only"
        )
