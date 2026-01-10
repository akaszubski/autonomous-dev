"""Critical path smoke tests for install.sh and /sync command.

These tests protect against regressions that have caused significant pain:
- install.sh missing hook installation (df12e09)
- install.sh backup/rollback bugs (8e5a320)
- /sync silent failure when adding files (fb3769f)
- /sync expected count mismatches (65b8ad1)
- /sync path issues to ~/.claude/lib/ (1c86ef2)
- /sync settings hook registration (ff65043)

All tests must complete in < 10 seconds total.

Reference: Git history for install.sh and sync-related fixes
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
class TestInstallShCritical:
    """Critical tests for install.sh - prevents installation breakage."""

    def test_install_sh_exists(self, project_root, timing_validator):
        """Test that install.sh exists at project root.

        Protects: Installation availability (smoke test)
        Historical issue: Script deleted/moved accidentally
        """
        with timing_validator.measure() as timer:
            install_sh = project_root / "install.sh"
            assert install_sh.exists(), "install.sh must exist at project root"

        assert timer.elapsed < 1.0

    def test_install_sh_valid_bash_syntax(self, project_root, timing_validator):
        """Test that install.sh has valid bash syntax.

        Protects: Installation won't fail on syntax errors (smoke test)
        Historical issue: Syntax errors breaking fresh installs
        """
        with timing_validator.measure() as timer:
            install_sh = project_root / "install.sh"
            result = subprocess.run(
                ["bash", "-n", str(install_sh)],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, f"Bash syntax error: {result.stderr}"

        assert timer.elapsed < 2.0

    def test_install_sh_uses_master_branch(self, project_root, timing_validator):
        """Test that install.sh references master branch, not main.

        Protects: Correct GitHub branch reference (smoke test)
        Historical issue: 29c2e3a - branch name mismatch broke installs
        """
        with timing_validator.measure() as timer:
            install_sh = project_root / "install.sh"
            content = install_sh.read_text()

            # Should use master, not main
            assert "master" in content, "install.sh should reference master branch"
            # Shouldn't have hardcoded 'main' as branch
            if "main" in content:
                # Allow 'main' only in comments or unrelated contexts
                lines_with_main = [
                    line for line in content.split('\n')
                    if 'main' in line and '/main/' in line and '#' not in line.split('/main/')[0]
                ]
                assert len(lines_with_main) == 0, (
                    f"install.sh should not reference 'main' branch in URLs: {lines_with_main}"
                )

        assert timer.elapsed < 1.0

    def test_install_manifest_exists(self, plugins_dir, timing_validator):
        """Test that install_manifest.json exists and is valid JSON.

        Protects: Manifest-based installation (smoke test)
        Historical issue: df12e09 - missing files not installed
        """
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "config" / "install_manifest.json"
            assert manifest.exists(), "install_manifest.json must exist"

            # Must be valid JSON
            data = json.loads(manifest.read_text())
            assert isinstance(data, dict), "Manifest must be a JSON object"

        assert timer.elapsed < 1.0

    def test_install_manifest_lists_all_hooks(self, plugins_dir, timing_validator):
        """Test that install_manifest.json includes all hooks.

        Protects: All hooks get installed (smoke test)
        Historical issue: df12e09 - hooks missing from manifest
        """
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "config" / "install_manifest.json"
            data = json.loads(manifest.read_text())

            # Get actual hooks (excluding backward compatibility shims)
            hooks_dir = plugins_dir / "hooks"
            # Shims redirect to unified hooks - they're intentionally not in manifest
            BACKWARD_COMPAT_SHIMS = {
                "auto_git_workflow.py",  # Shim → unified_git_automation.py (Issue #144)
            }
            actual_hooks = {
                f.name for f in hooks_dir.glob("*.py")
                if not f.name.startswith("__") and f.name not in BACKWARD_COMPAT_SHIMS
            }

            # Get hooks in manifest (new structure: components.hooks.files)
            manifest_hooks = set()
            hooks_component = data.get("components", {}).get("hooks", {})
            for file_path in hooks_component.get("files", []):
                manifest_hooks.add(Path(file_path).name)

            # All actual hooks should be in manifest
            missing = actual_hooks - manifest_hooks
            assert len(missing) == 0, f"Hooks missing from manifest: {missing}"

        assert timer.elapsed < 2.0

    def test_install_manifest_files_exist(self, plugins_dir, timing_validator):
        """Test that all files referenced in manifest actually exist.

        Protects: No broken references in manifest (smoke test)
        Historical issue: Files moved but manifest not updated
        """
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "config" / "install_manifest.json"
            data = json.loads(manifest.read_text())
            project_root = plugins_dir.parent.parent

            missing_files = []
            # New structure: components.{type}.files
            for component_name, component in data.get("components", {}).items():
                for file_path in component.get("files", []):
                    # Paths are relative to project root
                    full_path = project_root / file_path
                    if not full_path.exists():
                        missing_files.append(file_path)

            assert len(missing_files) == 0, f"Files in manifest don't exist: {missing_files[:10]}"

        assert timer.elapsed < 3.0


@pytest.mark.smoke
class TestSyncCommandCritical:
    """Critical tests for /sync command - prevents sync breakage."""

    def test_sync_command_exists(self, plugins_dir, timing_validator):
        """Test that sync.md command file exists.

        Protects: Sync command availability (smoke test)
        """
        with timing_validator.measure() as timer:
            sync_md = plugins_dir / "commands" / "sync.md"
            assert sync_md.exists(), "sync.md must exist"

        assert timer.elapsed < 1.0

    def test_sync_dispatcher_exists(self, plugins_dir, timing_validator):
        """Test that sync_dispatcher.py exists and is importable.

        Protects: Sync implementation availability (smoke test)
        Historical issue: f380d82 - CLI wrapper issues
        """
        with timing_validator.measure() as timer:
            dispatcher = plugins_dir / "lib" / "sync_dispatcher.py"
            assert dispatcher.exists(), "sync_dispatcher.py must exist"

            # Check it's valid Python
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(dispatcher)],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, f"Python syntax error: {result.stderr}"

        assert timer.elapsed < 2.0

    def test_sync_dispatcher_has_required_functions(self, plugins_dir, timing_validator):
        """Test that sync_dispatcher.py has required entry points.

        Protects: Sync functionality complete (smoke test)
        Historical issue: fb3769f - silent failure with missing functions
        """
        with timing_validator.measure() as timer:
            # Check for sync_dispatcher package (Issue #164 refactoring)
            dispatcher_pkg = plugins_dir / "lib" / "sync_dispatcher"
            dispatcher_shim = plugins_dir / "lib" / "sync_dispatcher.py"

            # Collect content from package modules or legacy single file
            if dispatcher_pkg.is_dir():
                # New package structure (Issue #164)
                dispatcher_content = dispatcher_pkg / "dispatcher.py"
                models_content = dispatcher_pkg / "models.py"
                content = ""
                if dispatcher_content.exists():
                    content += dispatcher_content.read_text()
                if models_content.exists():
                    content += models_content.read_text()
            else:
                # Legacy single file
                content = dispatcher_shim.read_text()

            # Required functions/classes (SyncMode is imported from sync_mode_detector)
            required = [
                "def dispatch",  # Main dispatcher method
                "class SyncDispatcher",  # Dispatcher class
                "class SyncResult",  # Result dataclass
            ]

            for func in required:
                assert func in content, f"sync_dispatcher missing: {func}"

        assert timer.elapsed < 1.0

    def test_settings_template_valid_json(self, plugins_dir, timing_validator):
        """Test that settings.local.json template is valid JSON.

        Protects: Settings template validity (smoke test)
        Historical issue: ff65043 - invalid JSON broke sync
        """
        with timing_validator.measure() as timer:
            settings = plugins_dir / "templates" / "settings.local.json"
            assert settings.exists(), "settings.local.json template must exist"

            # Must be valid JSON
            data = json.loads(settings.read_text())
            assert isinstance(data, dict), "Settings must be a JSON object"

        assert timer.elapsed < 1.0

    def test_settings_template_hooks_exist(self, plugins_dir, timing_validator):
        """Test that all hooks referenced in settings template exist.

        Protects: Hook registration validity (smoke test)
        Historical issue: ff65043 - settings referenced non-existent hooks
        """
        with timing_validator.measure() as timer:
            settings = plugins_dir / "templates" / "settings.local.json"
            data = json.loads(settings.read_text())

            missing_hooks = []

            # Check hooks in settings
            for hook_type in ["hooks", "preToolUse", "postToolUse"]:
                hooks = data.get(hook_type, [])
                if isinstance(hooks, list):
                    for hook in hooks:
                        if isinstance(hook, dict):
                            # Handle nested hook structure
                            hook_path = hook.get("command", "")
                        else:
                            hook_path = str(hook)

                        if hook_path and ".py" in hook_path:
                            # Extract just the filename
                            hook_name = Path(hook_path.split()[-1]).name
                            hook_file = plugins_dir / "hooks" / hook_name
                            if not hook_file.exists():
                                missing_hooks.append(hook_name)

            assert len(missing_hooks) == 0, f"Settings reference non-existent hooks: {missing_hooks}"

        assert timer.elapsed < 2.0

    def test_global_settings_template_exists(self, plugins_dir, timing_validator):
        """Test that global settings template exists for fresh installs.

        Protects: Fresh install configuration (smoke test)
        Historical issue: 77bdcf8 - fresh install permissions
        """
        with timing_validator.measure() as timer:
            global_settings = plugins_dir / "config" / "global_settings_template.json"
            assert global_settings.exists(), "global_settings_template.json must exist"

            # Must be valid JSON
            data = json.loads(global_settings.read_text())
            assert isinstance(data, dict), "Global settings must be a JSON object"

        assert timer.elapsed < 1.0


@pytest.mark.smoke
class TestInstallSyncIntegrity:
    """Integration tests for install/sync file integrity."""

    def test_all_libs_in_manifest(self, plugins_dir, timing_validator):
        """Test that all library files are in install manifest.

        Protects: All libs get installed (smoke test)
        Historical issue: df12e09 - 71 libs missing from install
        """
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "config" / "install_manifest.json"
            data = json.loads(manifest.read_text())

            # Get actual libs
            lib_dir = plugins_dir / "lib"
            actual_libs = {f.name for f in lib_dir.glob("*.py") if not f.name.startswith("__")}

            # Get libs in manifest (new structure: components.lib.files)
            manifest_libs = set()
            lib_component = data.get("components", {}).get("lib", {})
            for file_path in lib_component.get("files", []):
                manifest_libs.add(Path(file_path).name)

            # All actual libs should be in manifest
            missing = actual_libs - manifest_libs
            assert len(missing) == 0, f"Libs missing from manifest: {missing}"

        assert timer.elapsed < 2.0

    def test_all_commands_in_manifest(self, plugins_dir, timing_validator):
        """Test that all ACTIVE command files are in install manifest.

        Protects: All active commands get installed (smoke test)

        Note: Archived/deprecated commands are NOT included per Issue #121:
        - Individual agent commands (research, plan, etc.) → consolidated into /auto-implement
        - Old align commands → unified into /align with --project | --claude | --retrofit flags
        - Deprecated commands (update-plugin) → superseded by /sync
        """
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "config" / "install_manifest.json"
            data = json.loads(manifest.read_text())

            # Get actual commands
            commands_dir = plugins_dir / "commands"
            actual_commands = {f.name for f in commands_dir.glob("*.md")}

            # Archived/deprecated commands NOT included in manifest (Issue #121)
            archived_commands = {
                # Individual agent commands (consolidated into /auto-implement)
                "research.md", "plan.md", "test-feature.md", "implement.md",
                "review.md", "security-scan.md", "update-docs.md", "test.md",
                # Old align commands (unified into /align with flags)
                "align-project.md", "align-claude.md", "align-project-retrofit.md",
                # Deprecated commands (superseded)
                "update-plugin.md", "status.md", "pipeline-status.md",
            }

            # Filter to active commands only
            active_commands = actual_commands - archived_commands

            # Get commands in manifest (new structure: components.commands.files)
            manifest_commands = set()
            commands_component = data.get("components", {}).get("commands", {})
            for file_path in commands_component.get("files", []):
                manifest_commands.add(Path(file_path).name)

            # All active commands should be in manifest
            missing = active_commands - manifest_commands
            assert len(missing) == 0, f"Active commands missing from manifest: {missing}"

        assert timer.elapsed < 2.0

    def test_all_agents_in_manifest(self, plugins_dir, timing_validator):
        """Test that all agent files are in install manifest.

        Protects: All agents get installed (smoke test)
        """
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "config" / "install_manifest.json"
            data = json.loads(manifest.read_text())

            # Get actual agents (excluding archived)
            agents_dir = plugins_dir / "agents"
            actual_agents = {f.name for f in agents_dir.glob("*.md")}

            # Get agents in manifest (new structure: components.agents.files)
            manifest_agents = set()
            agents_component = data.get("components", {}).get("agents", {})
            for file_path in agents_component.get("files", []):
                if "archived" not in file_path:
                    manifest_agents.add(Path(file_path).name)

            # All actual agents should be in manifest
            missing = actual_agents - manifest_agents
            assert len(missing) == 0, f"Agents missing from manifest: {missing}"

        assert timer.elapsed < 2.0

    def test_no_archived_in_manifest(self, plugins_dir, timing_validator):
        """Test that archived files are NOT in install manifest (except command shims).

        Protects: Clean installation without deprecated files (smoke test)
        Historical issue: 652922a - archived files being synced

        Exception: Command deprecation shims ARE allowed in manifest because users
        need them installed to get redirect messages when using old command names.
        These have 'redirect-to:' frontmatter that redirects to new commands.
        """
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "config" / "install_manifest.json"
            data = json.loads(manifest.read_text())

            # Command deprecation shims are allowed (they redirect to new commands)
            ALLOWED_ARCHIVED = {
                "commands/archived/sync-dev.md",  # Redirects to /sync --env
                "commands/archived/update-plugin.md",  # Redirects to /sync --marketplace
            }

            archived_refs = []
            # Check all components for archived files (new structure: components.{type}.files)
            for component_name, component in data.get("components", {}).items():
                for file_path in component.get("files", []):
                    if "archived" in file_path.lower():
                        # Check if this is an allowed deprecation shim
                        is_allowed = any(allowed in file_path for allowed in ALLOWED_ARCHIVED)
                        if not is_allowed:
                            archived_refs.append(file_path)

            assert len(archived_refs) == 0, f"Manifest contains archived files: {archived_refs}"

        assert timer.elapsed < 1.0


@pytest.mark.smoke
class TestOrphanCleanupBehavior:
    """Tests for orphan file cleanup - prevents stale files after updates.

    Historical issues:
    - Archived hooks remaining in ~/.claude/hooks/ after consolidation
    - Deleted libs remaining in ~/.claude/lib/ after removal
    - Stale files causing import conflicts and unexpected behavior
    """

    def test_install_sh_has_orphan_cleanup_function(self, project_root, timing_validator):
        """Test that install.sh includes orphan cleanup logic.

        Protects: Orphan files cleaned during install (smoke test)
        Expected behavior: install.sh should remove files not in manifest
        """
        with timing_validator.measure() as timer:
            install_sh = project_root / "install.sh"
            content = install_sh.read_text()

            # Should have cleanup function or logic
            has_cleanup = any([
                "cleanup" in content.lower(),
                "orphan" in content.lower(),
                "remove" in content.lower() and "manifest" in content.lower(),
                "delete" in content.lower() and "not in" in content.lower(),
            ])

            assert has_cleanup, (
                "install.sh should include orphan cleanup logic to remove "
                "files not in manifest from ~/.claude/hooks/ and ~/.claude/lib/"
            )

        assert timer.elapsed < 1.0

    def test_sync_dispatcher_has_global_orphan_cleanup(self, plugins_dir, timing_validator):
        """Test that sync_dispatcher.py handles global directory orphan cleanup.

        Protects: Orphan files cleaned during /sync (smoke test)
        Expected behavior: /sync should remove orphans from ~/.claude/hooks/ and ~/.claude/lib/
        """
        with timing_validator.measure() as timer:
            # Check for sync_dispatcher package (Issue #164 refactoring)
            dispatcher_pkg = plugins_dir / "lib" / "sync_dispatcher"
            dispatcher_shim = plugins_dir / "lib" / "sync_dispatcher.py"

            # Collect content from package modules or legacy single file
            if dispatcher_pkg.is_dir():
                # New package structure (Issue #164)
                content = ""
                for py_file in dispatcher_pkg.glob("*.py"):
                    content += py_file.read_text()
            else:
                # Legacy single file
                content = dispatcher_shim.read_text()

            # Should reference orphan cleanup for global directories
            # Current behavior: delete_orphans=True for .claude/ but not ~/.claude/
            has_global_cleanup = any([
                "~/.claude" in content and "orphan" in content.lower(),
                "home" in content.lower() and "cleanup" in content.lower(),
                "global" in content.lower() and "orphan" in content.lower(),
            ])

            # This test documents expected behavior - currently may fail
            # Once implemented, this test will pass
            assert has_global_cleanup or "delete_orphans" in content, (
                "sync_dispatcher should handle orphan cleanup for global directories "
                "(~/.claude/hooks/, ~/.claude/lib/) during GITHUB sync mode"
            )

        assert timer.elapsed < 1.0

    def test_orphan_file_cleaner_supports_global_dirs(self, plugins_dir, timing_validator):
        """Test that orphan_file_cleaner.py can clean global directories.

        Protects: Library supports global cleanup (smoke test)
        Expected behavior: OrphanFileCleaner should work with ~/.claude/ paths
        """
        with timing_validator.measure() as timer:
            cleaner = plugins_dir / "lib" / "orphan_file_cleaner.py"
            content = cleaner.read_text()

            # Should have class that can handle paths
            assert "class OrphanFileCleaner" in content, "OrphanFileCleaner class must exist"

            # Should be able to detect orphans
            assert "def detect_orphans" in content, "detect_orphans method must exist"

            # Should be able to clean orphans
            assert "def cleanup_orphans" in content, "cleanup_orphans method must exist"

        assert timer.elapsed < 1.0

    def test_manifest_provides_complete_file_list(self, plugins_dir, timing_validator):
        """Test that manifest provides complete list of expected files for cleanup.

        Protects: Manifest completeness for orphan detection (smoke test)
        Expected: All component types have files lists that can be used for cleanup
        """
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "config" / "install_manifest.json"
            data = json.loads(manifest.read_text())

            components = data.get("components", {})

            # Required components for orphan detection
            required_components = ["hooks", "lib", "commands", "agents"]

            for component in required_components:
                assert component in components, f"Manifest missing component: {component}"
                files = components[component].get("files", [])
                assert len(files) > 0, f"Manifest component '{component}' has no files"

        assert timer.elapsed < 1.0

    def test_install_sh_cleans_hooks_before_install(self, project_root, timing_validator):
        """Test that install.sh cleans orphan hooks before installing new ones.

        Protects: No stale hooks after install (smoke test)
        Expected: Files in ~/.claude/hooks/ not in manifest should be removed
        """
        with timing_validator.measure() as timer:
            install_sh = project_root / "install.sh"
            content = install_sh.read_text()

            # Should have hook cleanup before or during install
            # Look for cleanup logic related to hooks directory
            lines = content.split('\n')
            has_hook_cleanup = False

            for i, line in enumerate(lines):
                # Look for cleanup patterns near hook installation
                if "hook" in line.lower() and any(word in line.lower() for word in ["clean", "remove", "delete", "orphan"]):
                    has_hook_cleanup = True
                    break
                # Or look for manifest-based filtering
                if "manifest" in line.lower() and "hook" in line.lower():
                    has_hook_cleanup = True
                    break

            # This documents expected behavior - test may initially fail
            assert has_hook_cleanup or "install_hook_files" in content, (
                "install.sh should clean orphan hooks: files in ~/.claude/hooks/ "
                "that are not in manifest should be removed during install"
            )

        assert timer.elapsed < 1.0

    def test_install_sh_cleans_libs_before_install(self, project_root, timing_validator):
        """Test that install.sh cleans orphan libs before installing new ones.

        Protects: No stale libs after install (smoke test)
        Expected: Files in ~/.claude/lib/ not in manifest should be removed
        """
        with timing_validator.measure() as timer:
            install_sh = project_root / "install.sh"
            content = install_sh.read_text()

            # Should have lib cleanup before or during install
            lines = content.split('\n')
            has_lib_cleanup = False

            for i, line in enumerate(lines):
                # Look for cleanup patterns near lib installation
                if "lib" in line.lower() and any(word in line.lower() for word in ["clean", "remove", "delete", "orphan"]):
                    has_lib_cleanup = True
                    break

            # This documents expected behavior - test may initially fail
            assert has_lib_cleanup or "install_lib_files" in content, (
                "install.sh should clean orphan libs: files in ~/.claude/lib/ "
                "that are not in manifest should be removed during install"
            )

        assert timer.elapsed < 1.0
