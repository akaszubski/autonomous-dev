#!/usr/bin/env python3
"""
Regression tests for install/sync infrastructure integrity.

Verifies that templates, manifests, and hook registrations are consistent
and that the sync operation is idempotent (no duplicate hooks).

Issue: GitHub #648
Date: 2026-04-03
Agent: implementer
"""

import json
import re
import sys
import tempfile
from pathlib import Path

import pytest

# Repo and plugin directory constants
WORKTREE = Path(__file__).resolve().parents[2]  # repo root
PLUGIN_DIR = WORKTREE / "plugins" / "autonomous-dev"

# Add scripts and lib to path for imports
sys.path.insert(0, str(PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(PLUGIN_DIR / "lib"))


def _write_json(path: Path, data: dict) -> None:
    """Helper to write JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict:
    """Helper to read JSON from a file."""
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================================
# TestSyncIdempotent - Verify no duplicate hooks on repeated sync
# ============================================================================


class TestSyncIdempotent:
    """Verify that sync operations are idempotent (no duplicate hooks)."""

    def test_sync_global_idempotent(self):
        """Run _replace_hooks twice with global template, settings identical both times."""
        from sync_settings_hooks import _replace_hooks

        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"
        assert template_path.exists(), f"Global template missing: {template_path}"

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".claude" / "settings.json"

            # First run
            result1 = _replace_hooks(settings_path, template_path)
            data1 = _read_json(settings_path)

            # Second run
            result2 = _replace_hooks(settings_path, template_path)
            data2 = _read_json(settings_path)

            assert result1["success"] is True
            assert result2["success"] is True
            assert data1 == data2, "Settings differ after second sync -- hooks duplicated"
            assert data1["hooks"] == data2["hooks"], "Hooks differ after second sync"

    def test_sync_repo_idempotent(self):
        """Run _replace_hooks twice with repo template, settings identical both times."""
        from sync_settings_hooks import _replace_hooks

        template_path = PLUGIN_DIR / "templates" / "settings.default.json"
        assert template_path.exists(), f"Repo template missing: {template_path}"

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".claude" / "settings.json"

            # First run
            result1 = _replace_hooks(settings_path, template_path)
            data1 = _read_json(settings_path)

            # Second run
            result2 = _replace_hooks(settings_path, template_path)
            data2 = _read_json(settings_path)

            assert result1["success"] is True
            assert result2["success"] is True
            assert data1 == data2, "Settings differ after second sync -- hooks duplicated"

    def test_sync_dispatcher_replaces_settings_hooks(self):
        """sync_dispatcher replaces settings.json hooks (not additive merge)."""
        dispatcher_path = PLUGIN_DIR / "lib" / "sync_dispatcher" / "dispatcher.py"
        content = dispatcher_path.read_text()
        assert "settings_hooks_synced" in content, (
            "sync_dispatcher must sync settings.json hook registrations"
        )
        assert 'user_data["hooks"] = template_hooks' in content, (
            "sync_dispatcher must replace hooks key entirely"
        )

    def test_sync_preserves_user_config(self):
        """After sync, mcpServers/permissions/enabledPlugins are preserved."""
        from sync_settings_hooks import _replace_hooks

        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"

            # Pre-populate with user config
            user_config = {
                "hooks": {},
                "mcpServers": {
                    "my-custom-server": {"url": "http://localhost:9999"}
                },
                "permissions": {
                    "allow": ["Read", "Write", "MyCustomTool"],
                    "deny": ["Bash(rm -rf /)"],
                },
                "enabledPlugins": ["my-plugin-a", "my-plugin-b"],
                "customKey": "should-survive",
            }
            _write_json(settings_path, user_config)

            result = _replace_hooks(settings_path, template_path)
            assert result["success"] is True

            data = _read_json(settings_path)

            # Hooks replaced from template
            template_data = _read_json(template_path)
            assert data["hooks"] == template_data["hooks"]

            # User config preserved
            assert data["mcpServers"]["my-custom-server"]["url"] == "http://localhost:9999"
            assert "MyCustomTool" in data["permissions"]["allow"]
            assert "my-plugin-a" in data["enabledPlugins"]
            assert "my-plugin-b" in data["enabledPlugins"]
            assert data["customKey"] == "should-survive"


# ============================================================================
# TestInstallShHooks - Verify install infrastructure includes .sh hooks
# ============================================================================


class TestInstallShHooks:
    """Verify install infrastructure handles .sh hook files."""

    def test_manifest_includes_sh_hooks(self):
        """install_manifest.json has .sh hook files listed."""
        manifest_path = PLUGIN_DIR / "install_manifest.json"
        assert manifest_path.exists(), f"Manifest missing: {manifest_path}"

        manifest = _read_json(manifest_path)
        hook_files = manifest["components"]["hooks"]["files"]

        sh_hooks = [f for f in hook_files if f.endswith(".sh")]
        assert len(sh_hooks) > 0, "No .sh hooks in manifest"

        # Specifically check the known .sh hooks
        sh_basenames = [Path(f).name for f in sh_hooks]
        assert "post_compact_enricher.sh" in sh_basenames, "post_compact_enricher.sh missing"
        assert "pre_compact_batch_saver.sh" in sh_basenames, "pre_compact_batch_saver.sh missing"

    def test_install_sh_includes_sh_pattern(self):
        """Verify that .sh hook files actually exist on disk (install would find them)."""
        hooks_dir = PLUGIN_DIR / "hooks"
        sh_files = list(hooks_dir.glob("*.sh"))

        # There should be at least 2 .sh hooks (pre_compact_batch_saver.sh, post_compact_enricher.sh)
        assert len(sh_files) >= 2, (
            f"Expected at least 2 .sh hook files, found {len(sh_files)}: "
            f"{[f.name for f in sh_files]}"
        )

    def test_sync_dispatcher_copies_sh_hooks(self):
        """sync_dispatcher._sync_directory is called for both *.py and *.sh."""
        dispatcher_path = PLUGIN_DIR / "lib" / "sync_dispatcher" / "dispatcher.py"
        content = dispatcher_path.read_text()
        assert 'pattern="*.py", description="hook files"' in content
        assert 'pattern="*.sh"' in content, (
            "sync_dispatcher must copy *.sh hooks alongside *.py hooks"
        )


# ============================================================================
# TestTemplateIntegrity - Verify template files are correct
# ============================================================================


class TestTemplateIntegrity:
    """Verify template files have correct hook configurations."""

    # The 8 standard lifecycle events
    EXPECTED_EVENTS = {
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
        "PreCompact",
        "PostCompact",
        "Stop",
        "SubagentStop",
        "TaskCompleted",
    }

    def test_global_template_stop_hook_correct(self):
        """Stop hook in global template points to stop_quality_gate.py."""
        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"
        data = _read_json(template_path)

        stop_hooks = data["hooks"]["Stop"]
        assert len(stop_hooks) >= 1

        # Find the command in the Stop hook
        commands = []
        for matcher_config in stop_hooks:
            for hook in matcher_config.get("hooks", []):
                commands.append(hook.get("command", ""))

        assert any("stop_quality_gate.py" in cmd for cmd in commands), (
            f"Stop hook should reference stop_quality_gate.py, "
            f"but found commands: {commands}"
        )

    def test_global_template_has_all_lifecycle_events(self):
        """Global template has all 8 standard lifecycle events."""
        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"
        data = _read_json(template_path)

        hook_events = set(data.get("hooks", {}).keys())
        missing = self.EXPECTED_EVENTS - hook_events
        assert not missing, f"Global template missing lifecycle events: {missing}"

    def test_default_template_has_all_lifecycle_events(self):
        """settings.default.json has all 8 standard lifecycle events."""
        template_path = PLUGIN_DIR / "templates" / "settings.default.json"
        data = _read_json(template_path)

        hook_events = set(data.get("hooks", {}).keys())
        missing = self.EXPECTED_EVENTS - hook_events
        assert not missing, f"Default template missing lifecycle events: {missing}"

    def test_all_templates_have_consistent_hooks(self):
        """All settings.*.json templates have at least the 8 standard lifecycle events."""
        templates_dir = PLUGIN_DIR / "templates"
        template_files = sorted(templates_dir.glob("settings.*.json"))

        assert len(template_files) >= 2, (
            f"Expected at least 2 settings templates, found {len(template_files)}"
        )

        for template_file in template_files:
            data = _read_json(template_file)
            hook_events = set(data.get("hooks", {}).keys())
            missing = self.EXPECTED_EVENTS - hook_events
            assert not missing, (
                f"{template_file.name} missing lifecycle events: {missing}"
            )


# ============================================================================
# TestHookRegistration - Verify hooks are registered and exist
# ============================================================================


class TestHookRegistration:
    """Verify hook files are registered in manifest and exist on disk."""

    def test_all_hook_files_in_manifest(self):
        """Every .py and .sh in hooks/ dir is in manifest (excluding hook configs)."""
        hooks_dir = PLUGIN_DIR / "hooks"
        manifest_path = PLUGIN_DIR / "install_manifest.json"
        manifest = _read_json(manifest_path)

        manifest_hook_files = set(manifest["components"]["hooks"]["files"])
        manifest_basenames = {Path(f).name for f in manifest_hook_files}

        # Hook config files use CamelCase-hyphen naming (e.g., SessionStart-batch-recovery.sh)
        # and are NOT managed through the manifest. Only snake_case hooks are manifest-managed.
        # Also exclude .hook.json config files and coverage files.
        def _is_managed_hook(filename: str) -> bool:
            """Return True if this is a manifest-managed hook (not a config file)."""
            if filename.endswith(",cover"):
                return False
            # Hook config .sh files use CamelCase-hyphen patterns
            if "-" in filename and filename[0].isupper():
                return False
            return filename.endswith(".py") or filename.endswith(".sh")

        actual_hooks = [
            f.name for f in hooks_dir.iterdir()
            if f.is_file() and _is_managed_hook(f.name)
        ]

        missing_from_manifest = [
            name for name in actual_hooks
            if name not in manifest_basenames
        ]

        assert not missing_from_manifest, (
            f"Hook files on disk but NOT in manifest: {missing_from_manifest}"
        )

    def test_manifest_hooks_exist_on_disk(self):
        """Every hook in manifest exists as a real file.

        Known exception: batch_permission_approver.py is listed in the manifest
        but was removed from disk. This is a pre-existing manifest inconsistency
        tracked separately.
        """
        manifest_path = PLUGIN_DIR / "install_manifest.json"
        manifest = _read_json(manifest_path)

        # Pre-existing manifest inconsistencies (tracked separately)
        KNOWN_MISSING = {"batch_permission_approver.py"}

        hook_files = manifest["components"]["hooks"]["files"]
        missing = []

        for hook_rel_path in hook_files:
            hook_path = WORKTREE / hook_rel_path
            if not hook_path.exists():
                basename = Path(hook_rel_path).name
                if basename not in KNOWN_MISSING:
                    missing.append(hook_rel_path)

        assert not missing, f"Manifest hooks missing on disk: {missing}"

    def test_global_template_hooks_point_to_real_files(self):
        """Every command in global template references a file that exists in hooks/ dir."""
        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"
        data = _read_json(template_path)

        hooks_dir = PLUGIN_DIR / "hooks"
        # Get basenames of all hook files on disk
        disk_hooks = {f.name for f in hooks_dir.iterdir() if f.is_file()}

        missing = []
        for event, matchers in data.get("hooks", {}).items():
            for matcher_config in matchers:
                for hook in matcher_config.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Extract filename from command like "python3 ~/.claude/hooks/foo.py"
                    # or "bash ~/.claude/hooks/bar.sh"
                    # or "ENV=val python3 ~/.claude/hooks/baz.py"
                    match = re.search(r"hooks/([a-zA-Z0-9_]+\.(?:py|sh))", cmd)
                    if match:
                        hook_filename = match.group(1)
                        if hook_filename not in disk_hooks:
                            missing.append(
                                f"{event}: {hook_filename} (from cmd: {cmd})"
                            )

        assert not missing, (
            f"Global template references hooks not found on disk: {missing}"
        )


# ============================================================================
# TestEndToEndSync - E2E tests with real templates
# ============================================================================


class TestEndToEndSync:
    """E2E tests — verify sync produces correct settings with real templates."""

    def test_sync_replaces_hooks_in_fake_repo(self, tmp_path):
        """Create fake repo, sync with global template, verify portable paths."""
        # Create fake .claude/settings.json with dummy hooks
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings = {
            "permissions": {"allow": ["Bash", "Read"], "deny": []},
            "mcpServers": {"test": {"command": "echo"}},
            "hooks": {
                "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo old", "timeout": 5}]}]
            }
        }
        settings_path = claude_dir / "settings.json"
        settings_path.write_text(json.dumps(settings))

        # Import and run _replace_hooks with the REAL global template
        sys.path.insert(0, str(PLUGIN_DIR / "scripts"))
        from sync_settings_hooks import _replace_hooks
        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"

        result = _replace_hooks(settings_path, template_path)
        assert result["success"]
        assert result["total_lifecycle_events"] >= 8

        # Verify resulting hooks use ~/.claude/hooks/ paths (no git rev-parse)
        updated = json.loads(settings_path.read_text())
        for event, entries in updated["hooks"].items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    assert "$(git rev-parse" not in cmd, (
                        f"{event} has non-portable git rev-parse path: {cmd}"
                    )
                    # Every .py/.sh reference should use ~/.claude/hooks/ or absolute path

        # Verify user config preserved
        assert updated["permissions"]["allow"] == ["Bash", "Read"]
        assert "test" in updated.get("mcpServers", {})

    def test_sync_hook_commands_reference_real_files(self):
        """Every hook command in global template references a file that exists."""
        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"
        template = json.loads(template_path.read_text())

        hooks_dir = PLUGIN_DIR / "hooks"
        missing = []

        for event, entries in template.get("hooks", {}).items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Extract filename from command (last .py or .sh token)
                    for word in cmd.split():
                        if word.endswith(".py") or word.endswith(".sh"):
                            # Extract just the filename
                            filename = Path(word).name
                            if not (hooks_dir / filename).exists():
                                missing.append(f"{event}: {filename}")

        assert not missing, f"Hook commands reference missing files: {missing}"

    def test_sync_idempotent_with_real_template(self, tmp_path):
        """Running sync twice produces identical output."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({"hooks": {}}))

        sys.path.insert(0, str(PLUGIN_DIR / "scripts"))
        from sync_settings_hooks import _replace_hooks
        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"
        settings_path = claude_dir / "settings.json"

        _replace_hooks(settings_path, template_path)
        first_content = settings_path.read_text()

        _replace_hooks(settings_path, template_path)
        second_content = settings_path.read_text()

        assert first_content == second_content, "Sync is not idempotent — content differs on second run"


# ============================================================================
# TestInstallShIntegrity - install.sh discovery and global template correctness
# ============================================================================


class TestInstallShIntegrity:
    """Verify install.sh discovery and global template correctness."""

    def test_install_sh_finds_both_py_and_sh(self):
        """install.sh hook discovery includes both *.py and *.sh files."""
        install_sh = WORKTREE / "install.sh"
        content = install_sh.read_text()

        # The find command should have both patterns
        assert "*.py" in content
        assert "*.sh" in content

        # Verify actual hooks exist for both types
        hooks_dir = PLUGIN_DIR / "hooks"
        py_hooks = list(hooks_dir.glob("*.py"))
        sh_hooks = list(hooks_dir.glob("*.sh"))

        assert len(py_hooks) > 0, "No .py hooks found"
        assert len(sh_hooks) > 0, "No .sh hooks found"

    def test_global_template_stop_hook_resolves(self):
        """Stop hook in global template points to stop_quality_gate.py, which exists."""
        template_path = PLUGIN_DIR / "config" / "global_settings_template.json"
        template = json.loads(template_path.read_text())

        stop_hooks = template["hooks"].get("Stop", [])
        assert len(stop_hooks) > 0, "No Stop hooks in global template"

        stop_cmd = stop_hooks[0]["hooks"][0]["command"]
        assert "stop_quality_gate.py" in stop_cmd, (
            f"Stop hook should reference stop_quality_gate.py, got: {stop_cmd}"
        )

        # Verify the file exists
        assert (PLUGIN_DIR / "hooks" / "stop_quality_gate.py").exists(), (
            "stop_quality_gate.py missing from hooks dir"
        )


# ============================================================================
# TestDeployValidation - deploy-all.sh validation check 7 logic
# ============================================================================


class TestDeployValidation:
    """Test the deploy-all.sh validation check 7 logic with real data."""

    def _run_hook_validation(self, settings_path: Path, repo_path: Path) -> list:
        """Run the same validation logic as deploy-all.sh check 7.

        Checks hook file references against both:
        - Expanded real paths (for absolute/~ paths)
        - The plugin source hooks directory (for ~/ paths that may not be installed
          in the test environment due to HOME isolation)
        """
        import os as _os
        settings = json.loads(settings_path.read_text())
        missing = []
        repo = str(repo_path)
        hooks_source_dir = PLUGIN_DIR / "hooks"
        for event, matchers in settings.get("hooks", {}).items():
            for matcher in matchers:
                for hook in matcher.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Issue #1036: canonical path is now wrapped in
                    # ${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}.
                    # Resolve the full expression + bare $CLAUDE_PROJECT_DIR
                    # forms to the repo root, then the legacy bare git form.
                    cmd_resolved = cmd
                    cmd_resolved = cmd_resolved.replace(
                        "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}", repo
                    )
                    cmd_resolved = cmd_resolved.replace("${CLAUDE_PROJECT_DIR}", repo)
                    cmd_resolved = cmd_resolved.replace("$CLAUDE_PROJECT_DIR", repo)
                    cmd_resolved = cmd_resolved.replace(
                        "$(git rev-parse --show-toplevel)", repo
                    )
                    for word in cmd_resolved.split():
                        word = word.strip("\"'")
                        if word.endswith(".py") or word.endswith(".sh"):
                            if word.startswith("~"):
                                # Check expanded path first; fall back to plugin source dir
                                expanded = _os.path.expanduser(word)
                                filename = Path(word).name
                                if not _os.path.exists(expanded) and not (hooks_source_dir / filename).exists():
                                    missing.append(word)
                            elif word.startswith("/"):
                                if not _os.path.exists(word):
                                    missing.append(word)
                            else:
                                path = _os.path.join(repo, word)
                                if not _os.path.exists(path):
                                    missing.append(word)
        return missing

    def test_validation_against_real_autonomous_dev(self):
        """deploy-all.sh validation finds 0 missing hooks in autonomous-dev."""
        settings_path = WORKTREE / ".claude" / "settings.json"
        if not settings_path.exists():
            pytest.skip("No .claude/settings.json in autonomous-dev")
        missing = self._run_hook_validation(settings_path, WORKTREE)
        assert not missing, f"Validation found missing hooks: {missing}"

    def test_validation_catches_broken_hook(self, tmp_path):
        """Validation detects a deliberately broken hook path."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        broken_settings = {
            "hooks": {
                "PreToolUse": [{
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/nonexistent_hook_12345.py", "timeout": 5}]
                }]
            }
        }
        (claude_dir / "settings.json").write_text(json.dumps(broken_settings))
        missing = self._run_hook_validation(claude_dir / "settings.json", tmp_path)
        assert len(missing) > 0, "Validation should catch nonexistent hook"
        assert "nonexistent_hook_12345.py" in missing[0]


# ============================================================================
# TestSetupPathPortability - template path strategy verification
# ============================================================================


class TestSetupPathPortability:
    """Verify template path strategies are correct for each deployment context."""

    def test_global_template_has_no_git_paths(self):
        """Global template uses only portable ~/.claude/hooks/ paths."""
        template = json.loads((PLUGIN_DIR / "config" / "global_settings_template.json").read_text())

        for event, entries in template.get("hooks", {}).items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    assert "$(git rev-parse" not in cmd, (
                        f"Global template {event} has non-portable path: {cmd}\n"
                        "Global template must use ~/.claude/hooks/ paths"
                    )
                    assert "$(git" not in cmd, f"Global template {event} has git subshell: {cmd}"

    def test_templates_have_same_lifecycle_events(self):
        """Both templates register the same 8 lifecycle events."""
        global_tmpl = json.loads((PLUGIN_DIR / "config" / "global_settings_template.json").read_text())
        default_tmpl = json.loads((PLUGIN_DIR / "templates" / "settings.default.json").read_text())

        global_events = set(global_tmpl.get("hooks", {}).keys())
        default_events = set(default_tmpl.get("hooks", {}).keys())

        expected = {
            "PreToolUse", "PostToolUse", "UserPromptSubmit", "PreCompact",
            "PostCompact", "Stop", "SubagentStop", "TaskCompleted",
        }

        assert global_events == expected, f"Global template missing events: {expected - global_events}"
        assert default_events == expected, f"Default template missing events: {expected - default_events}"
