"""Regression tests for global_settings_template.json integrity.

Ensures all hook commands referenced in the settings template actually
exist as source files in plugins/autonomous-dev/hooks/.

Incident: PR #336-#343 archived hooks but left stale references in
global_settings_template.json, causing "hook not found" errors after install.

Issue #944: Per-repo settings.json templates MUST NOT redeclare hooks that
are already registered globally (in ~/.claude/settings.json). The new test
``test_template_has_no_global_hook_duplicates`` enforces this invariant for
the four user-facing templates.
"""

import json
import re
import sys
from pathlib import Path

import pytest

# Import the public extract_hook_refs + canonical hook list. Use the same
# dev/installed import-fallback pattern as sync_validator.py:31-42.
_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
try:
    from plugins.autonomous_dev.lib.settings_merger import (  # type: ignore
        CANONICAL_GLOBAL_HOOKS,
        extract_hook_refs,
    )
except ImportError:
    if str(_LIB) not in sys.path:
        sys.path.insert(0, str(_LIB))
    from settings_merger import (  # type: ignore[no-redef]
        CANONICAL_GLOBAL_HOOKS,
        extract_hook_refs,
    )


# Templates that MUST be free of global-hook duplicates (Issue #944).
# settings.autonomous-dev.json is excluded — intentional dogfooding.
# settings.local.json is excluded — deferred per critique.
_GLOBAL_FREE_TEMPLATES = (
    "settings.default.json",
    "settings.granular-bash.json",
    "settings.permission-batching.json",
    "settings.strict-mode.json",
)


def _canonical_basenames() -> set:
    """Return the set of basename .py filenames covered by CANONICAL_GLOBAL_HOOKS."""
    pattern = re.compile(r"hooks/(\w+\.py)")
    out: set = set()
    for cmd in CANONICAL_GLOBAL_HOOKS:
        m = pattern.search(cmd)
        if m:
            out.add(m.group(1))
    return out


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
        """Extract all hook file references from the template.

        Thin compatibility wrapper around lib.settings_merger.extract_hook_refs
        (which returns a set). Existing tests below expect a list — convert.
        """
        return list(extract_hook_refs(template))

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


# Issue #944: parametrized check across the 4 user-facing per-repo templates.
@pytest.mark.parametrize("template_name", _GLOBAL_FREE_TEMPLATES)
def test_template_has_no_global_hook_duplicates(
    template_name: str, project_root: Path
):
    """Per-repo templates MUST NOT redeclare hooks already registered globally.

    Issue #944: hook commands like ``python3 ~/.claude/hooks/plan_gate.py``
    belong in ~/.claude/settings.json (configured by
    configure_global_settings.py). Per-repo templates that redeclare them
    cause double execution.
    """
    tpl_path = (
        project_root / "plugins" / "autonomous-dev" / "templates" / template_name
    )
    if not tpl_path.exists():
        pytest.skip(f"Template not found: {template_name}")

    settings = json.loads(tpl_path.read_text())
    refs = extract_hook_refs(settings)
    canonical_basenames = _canonical_basenames()
    overlap = refs & canonical_basenames
    assert not overlap, (
        f"{template_name} contains global-hook duplicates: {sorted(overlap)}\n"
        f"These hooks are already registered in ~/.claude/settings.json — "
        f"remove them from the per-repo template."
    )
