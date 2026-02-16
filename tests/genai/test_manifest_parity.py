"""GenAI tests for manifest and installation parity.

Validates that install_manifest.json stays in sync with:
- Actual files on disk
- Plugin version metadata
- Settings template hook references
"""

import json
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"
MANIFEST_PATH = PLUGIN_ROOT / "install_manifest.json"


def _load_manifest():
    """Load and return install manifest data."""
    if not MANIFEST_PATH.exists():
        pytest.skip("install_manifest.json not found")
    return json.loads(MANIFEST_PATH.read_text())


class TestManifestParity:
    """Validate manifest accurately reflects plugin structure."""

    def test_install_manifest_lists_all_source_files(self, genai):
        """Manifest should list all installable source files."""
        manifest = _load_manifest()

        # Collect files from comparable components only (not skills/templates/config)
        comparable_components = {"agents", "commands", "hooks", "lib", "scripts"}
        manifest_files = set()
        for component, info in manifest.get("components", {}).items():
            if component in comparable_components:
                for f in info.get("files", []):
                    if "__init__" not in f:
                        manifest_files.add(f)

        # Collect actual files on disk for each component type
        disk_files = set()
        component_dirs = {
            "agents": ("agents", "*.md"),
            "commands": ("commands", "*.md"),
            "hooks": ("hooks", "*.py"),
            "lib": ("lib", "*.py"),
            "scripts": ("scripts", "*.py"),
        }
        for component, (subdir, pattern) in component_dirs.items():
            comp_dir = PLUGIN_ROOT / subdir
            if comp_dir.exists():
                for f in comp_dir.glob(pattern):
                    if "archived" not in str(f) and f.stem != "__init__":
                        rel = f"plugins/autonomous-dev/{subdir}/{f.name}"
                        disk_files.add(rel)

        in_manifest_not_disk = sorted(manifest_files - disk_files)
        on_disk_not_manifest = sorted(disk_files - manifest_files)

        result = genai.judge(
            question="Does install_manifest.json list all source files that exist on disk?",
            context=f"**In manifest but NOT on disk ({len(in_manifest_not_disk)}):** "
            f"{in_manifest_not_disk[:15]}\n\n"
            f"**On disk but NOT in manifest ({len(on_disk_not_manifest)}):** "
            f"{on_disk_not_manifest[:15]}\n\n"
            f"**Total manifest files:** {len(manifest_files)}\n"
            f"**Total disk files (non-archived):** {len(disk_files)}",
            criteria="Manifest should accurately list files for installation. "
            "Files in manifest but not on disk = broken install. "
            "Files on disk but not in manifest = won't be installed. "
            "Skills/templates/config have different structures, focus on agents/commands/hooks/lib. "
            "Deduct 2 per dead manifest entry, 1 per missing file.",
        )
        assert result["score"] >= 5, f"Manifest ↔ disk drift: {result['reasoning']}"

    def test_manifest_version_matches_plugin_json(self, genai):
        """Manifest version should match plugin.json version."""
        manifest = _load_manifest()
        manifest_version = manifest.get("version", "NOT SET")

        plugin_json_path = PLUGIN_ROOT / "plugin.json"
        if not plugin_json_path.exists():
            pytest.skip("plugin.json not found")

        plugin_data = json.loads(plugin_json_path.read_text())
        plugin_version = plugin_data.get("version", "NOT SET")

        result = genai.judge(
            question="Does install_manifest.json version match plugin.json version?",
            context=f"**install_manifest.json version:** {manifest_version}\n"
            f"**plugin.json version:** {plugin_version}",
            criteria="Both files should declare the same version. "
            "Version mismatch = users may install wrong version. "
            "Score 10 = match, 0 = mismatch.",
        )
        assert result["score"] >= 5, f"Version mismatch: {result['reasoning']}"

    def test_manifest_no_orphaned_entries(self, genai):
        """Files listed in manifest should exist on disk."""
        manifest = _load_manifest()

        # Skip skills/templates — they use a different install path (.claude/skills/)
        comparable = {"agents", "commands", "hooks", "lib", "scripts", "config"}
        orphaned = []
        total = 0
        for component, info in manifest.get("components", {}).items():
            if component not in comparable:
                continue
            for f in info.get("files", []):
                total += 1
                full_path = PROJECT_ROOT / f
                if not full_path.exists():
                    orphaned.append(f)

        result = genai.judge(
            question="Do all files listed in install_manifest.json exist on disk?",
            context=f"**Total entries:** {total}\n"
            f"**Orphaned (file missing) ({len(orphaned)}):** {orphaned[:20]}",
            criteria="Every file in the manifest must exist on disk. "
            "Orphaned entries cause installation failures. "
            "Score 10 = zero orphaned, deduct 2 per orphaned entry.",
        )
        assert result["score"] >= 5, f"Orphaned manifest entries: {result['reasoning']}"

    def test_settings_template_hooks_all_exist(self, genai):
        """Hooks referenced in settings templates must exist as files."""
        import re

        templates_dir = PLUGIN_ROOT / "templates"
        if not templates_dir.exists():
            pytest.skip("Templates directory not found")

        template_hook_refs = set()
        for tmpl in templates_dir.glob("settings.*.json"):
            content = tmpl.read_text(errors="ignore")
            # Extract hook filenames from command strings
            matches = re.findall(r'(\w+\.py)', content)
            template_hook_refs.update(matches)

        hooks_dir = PLUGIN_ROOT / "hooks"
        existing_hooks = {f.name for f in hooks_dir.glob("*.py")} if hooks_dir.exists() else set()

        missing = sorted(template_hook_refs - existing_hooks)
        extra = sorted(existing_hooks - template_hook_refs)

        result = genai.judge(
            question="Do settings templates reference only hooks that exist?",
            context=f"**Hooks in templates:** {sorted(template_hook_refs)}\n\n"
            f"**Hook files on disk:** {sorted(existing_hooks)}\n\n"
            f"**Referenced but MISSING ({len(missing)}):** {missing}\n"
            f"**On disk but not in templates ({len(extra)}):** {extra}",
            criteria="Templates should reference hooks that exist as files. "
            "Missing hooks = broken settings after install. "
            "Hooks not in templates may be optional. "
            "Score 10 = no missing references, deduct 3 per missing hook.",
        )
        assert result["score"] >= 5, f"Template hook drift: {result['reasoning']}"
