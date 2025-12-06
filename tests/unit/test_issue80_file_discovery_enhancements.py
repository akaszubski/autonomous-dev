"""
TDD Tests for Issue #80 - Enhanced File Discovery (Phase 1)

Tests the enhanced FileDiscovery system that ensures 100% file coverage
(all 201+ files) instead of the current ~76% (152 files).

Current State (RED PHASE):
- Enhanced discovery methods don't exist yet
- Nested skills support doesn't exist
- All tests should FAIL

Test Coverage:
- Enhanced recursive discovery (nested skills, all file types)
- Intelligent exclusion patterns
- File count verification (201+ files)
- Manifest generation with complete file list
- Validation against expected file count

GitHub Issue: #80
Agent: test-master
Date: 2025-11-19
"""

import pytest
from pathlib import Path
import json


class TestEnhancedFileDiscovery:
    """Test enhanced file discovery for 100% coverage."""

    def test_discovers_nested_skill_files(self, tmp_path):
        """Test that discovery finds nested skill directory files.

        Current install.sh misses:
        - skills/[name].skill/docs/*.md
        - skills/[name].skill/examples/*.py
        - skills/[name].skill/tests/*.py

        Current: FAILS - Enhanced discovery doesn't exist
        """
        # Arrange: Create nested skill structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Create skill with nested structure
        skill_dir = plugin_dir / "skills" / "testing-guide.skill"
        skill_dir.mkdir(parents=True)

        (skill_dir / "skill.md").write_text("# Testing Guide")

        (skill_dir / "docs").mkdir()
        (skill_dir / "docs" / "guide.md").write_text("Guide")
        (skill_dir / "docs" / "advanced.md").write_text("Advanced")

        (skill_dir / "examples").mkdir()
        (skill_dir / "examples" / "example1.py").write_text("example")
        (skill_dir / "examples" / "example2.md").write_text("example")

        # Act: Discover all files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: All nested files found
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]

        assert "skills/testing-guide.skill/skill.md" in relative_paths
        assert "skills/testing-guide.skill/docs/guide.md" in relative_paths
        assert "skills/testing-guide.skill/docs/advanced.md" in relative_paths
        assert "skills/testing-guide.skill/examples/example1.py" in relative_paths
        assert "skills/testing-guide.skill/examples/example2.md" in relative_paths

        # Total: 5 files in nested structure
        assert len(files) == 5

    def test_discovers_all_lib_files_not_just_md(self, tmp_path):
        """Test that discovery finds ALL lib/ files, not just *.md.

        Current install.sh uses glob patterns that miss Python files.
        Missing: 23 of 48 lib/ files

        Current: FAILS - Enhanced discovery doesn't exist
        """
        # Arrange: Create lib/ with mixed file types
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir(parents=True)

        # Python files (currently missed)
        (lib_dir / "security_utils.py").write_text("# Security utils")
        (lib_dir / "batch_state_manager.py").write_text("# Batch manager")
        (lib_dir / "file_discovery.py").write_text("# File discovery")

        # Nested Python files (currently missed)
        (lib_dir / "nested").mkdir()
        (lib_dir / "nested" / "utils.py").write_text("# Nested utils")

        # Markdown files (currently found)
        (lib_dir / "README.md").write_text("# Readme")

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: All files found (Python AND Markdown)
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]

        # Python files
        assert "lib/security_utils.py" in relative_paths
        assert "lib/batch_state_manager.py" in relative_paths
        assert "lib/file_discovery.py" in relative_paths
        assert "lib/nested/utils.py" in relative_paths

        # Markdown files
        assert "lib/README.md" in relative_paths

        assert len(files) == 5

    def test_discovers_all_scripts_files(self, tmp_path):
        """Test that discovery finds ALL scripts/ files.

        Current install.sh misses all 9 scripts/ files.

        Current: FAILS - Enhanced discovery doesn't exist
        """
        # Arrange: Create scripts/ directory
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)

        # Create all 9 scripts
        scripts = [
            "setup.py",
            "validate.py",
            "performance_timer.py",
            "session_tracker.py",
            "health_check.py",
            "pipeline_status.py",
            "update_plugin.py",
            "sync_dispatcher.py",
            "validate_marketplace_version.py",
        ]

        for script_name in scripts:
            (scripts_dir / script_name).write_text(f"#!/usr/bin/env python3\n# {script_name}")

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: All 9 scripts found
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]

        for script_name in scripts:
            assert f"scripts/{script_name}" in relative_paths

        assert len(files) == 9

    def test_discovers_agent_implementation_files(self, tmp_path):
        """Test that discovery finds agent implementation files.

        Current install.sh misses 3 agent implementation files.

        Current: FAILS - Enhanced discovery doesn't exist
        """
        # Arrange: Create agents/ with both .md and .py files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir(parents=True)

        # Agent definitions (.md) - currently found
        (agents_dir / "researcher.md").write_text("# Researcher")
        (agents_dir / "planner.md").write_text("# Planner")

        # Agent implementations (.py) - currently missed
        (agents_dir / "researcher_impl.py").write_text("# Implementation")
        (agents_dir / "planner_impl.py").write_text("# Implementation")
        (agents_dir / "__init__.py").write_text("# Init")

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Both .md and .py files found
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]

        assert "agents/researcher.md" in relative_paths
        assert "agents/planner.md" in relative_paths
        assert "agents/researcher_impl.py" in relative_paths
        assert "agents/planner_impl.py" in relative_paths
        assert "agents/__init__.py" in relative_paths

        assert len(files) == 5

    def test_excludes_cache_and_build_artifacts(self, tmp_path):
        """Test that discovery excludes cache and build artifacts.

        Exclusions:
        - __pycache__/
        - *.pyc, *.pyo
        - .pytest_cache/
        - *.egg-info/

        Current: FAILS - Enhanced exclusion doesn't exist
        """
        # Arrange: Create files with artifacts
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Valid files
        (plugin_dir / "lib").mkdir()
        (plugin_dir / "lib" / "utils.py").write_text("# Utils")

        # Cache artifacts (should be excluded)
        (plugin_dir / "lib" / "__pycache__").mkdir()
        (plugin_dir / "lib" / "__pycache__" / "utils.cpython-311.pyc").touch()

        # Pytest cache (should be excluded)
        (plugin_dir / ".pytest_cache").mkdir()
        (plugin_dir / ".pytest_cache" / "v").mkdir()
        (plugin_dir / ".pytest_cache" / "v" / "cache.json").touch()

        # Egg info (should be excluded)
        (plugin_dir / "autonomous_dev.egg-info").mkdir()
        (plugin_dir / "autonomous_dev.egg-info" / "PKG-INFO").touch()

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Only valid files found
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]

        assert "lib/utils.py" in relative_paths
        assert len(files) == 1  # Only utils.py

        # Cache artifacts excluded
        assert not any("__pycache__" in p for p in relative_paths)
        assert not any(".pyc" in p for p in relative_paths)
        assert not any(".pytest_cache" in p for p in relative_paths)
        assert not any(".egg-info" in p for p in relative_paths)

    def test_excludes_git_and_ide_files(self, tmp_path):
        """Test that discovery excludes git and IDE files.

        Exclusions:
        - .git/
        - .gitignore
        - .vscode/
        - .idea/
        - .DS_Store

        Current: FAILS - Enhanced exclusion doesn't exist
        """
        # Arrange: Create files with git/IDE artifacts
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Valid files
        (plugin_dir / "README.md").write_text("# Readme")

        # Git artifacts (should be excluded)
        (plugin_dir / ".git").mkdir()
        (plugin_dir / ".git" / "config").touch()
        (plugin_dir / ".gitignore").write_text("*.pyc")

        # IDE files (should be excluded)
        (plugin_dir / ".vscode").mkdir()
        (plugin_dir / ".vscode" / "settings.json").touch()

        (plugin_dir / ".idea").mkdir()
        (plugin_dir / ".idea" / "workspace.xml").touch()

        (plugin_dir / ".DS_Store").touch()

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Only valid files found
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]

        assert "README.md" in relative_paths
        assert len(files) == 1  # Only README.md

        # Git/IDE files excluded
        assert not any(".git" in p for p in relative_paths)
        assert not any(".gitignore" in p for p in relative_paths)
        assert not any(".vscode" in p for p in relative_paths)
        assert not any(".idea" in p for p in relative_paths)
        assert not any(".DS_Store" in p for p in relative_paths)

    def test_includes_hidden_env_example(self, tmp_path):
        """Test that discovery includes .env.example despite being hidden.

        Current: FAILS - Enhanced exclusion doesn't exist
        """
        # Arrange: Create files with .env variants
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Should be included
        (plugin_dir / ".env.example").write_text("API_KEY=")

        # Should be excluded
        (plugin_dir / ".env").write_text("API_KEY=secret")
        (plugin_dir / ".env.local").write_text("API_KEY=secret")

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Only .env.example included
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]

        assert ".env.example" in relative_paths
        assert ".env" not in relative_paths
        assert ".env.local" not in relative_paths

    def test_counts_total_files_accurately(self, tmp_path):
        """Test that file count matches expected 201+ files.

        Current install.sh finds ~152 files (76% coverage).
        Target: 201+ files (100% coverage).

        Current: FAILS - Enhanced discovery doesn't exist
        """
        # Arrange: Create comprehensive plugin structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Commands: 20 files
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir()
        for i in range(20):
            (commands_dir / f"command{i}.md").touch()

        # Hooks: 42 files
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir()
        for i in range(42):
            (hooks_dir / f"hook{i}.py").touch()

        # Agents: 20 files
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir()
        for i in range(20):
            (agents_dir / f"agent{i}.md").touch()

        # Lib: 30 files (mix of .py and .md)
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir()
        for i in range(30):
            ext = ".py" if i % 2 == 0 else ".md"
            (lib_dir / f"lib{i}{ext}").touch()

        # Scripts: 10 files
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir()
        for i in range(10):
            (scripts_dir / f"script{i}.py").touch()

        # Skills: 27 skills × 5 files = 135 files
        skills_dir = plugin_dir / "skills"
        skills_dir.mkdir()
        for i in range(27):
            skill = skills_dir / f"skill{i}.skill"
            skill.mkdir()
            (skill / "skill.md").touch()
            (skill / "docs").mkdir()
            (skill / "docs" / "guide.md").touch()
            (skill / "docs" / "advanced.md").touch()
            (skill / "examples").mkdir()
            (skill / "examples" / "example1.py").touch()
            (skill / "examples" / "example2.md").touch()

        # Total: 20 + 42 + 20 + 30 + 10 + 135 = 257 files

        # Act: Count files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        count = discovery.count_files()

        # Assert: Accurate count
        assert count == 257

    def test_generates_complete_manifest(self, tmp_path):
        """Test that manifest includes all 201+ files.

        Current: FAILS - Enhanced manifest generation doesn't exist
        """
        # Arrange: Create plugin files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Create mix of files
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").write_text("test" * 100)  # 400 bytes

        (plugin_dir / "lib").mkdir()
        (plugin_dir / "lib" / "utils.py").write_text("utils" * 50)  # 250 bytes

        (plugin_dir / "scripts").mkdir()
        (plugin_dir / "scripts" / "setup.py").write_text("setup" * 75)  # 375 bytes

        # Act: Generate manifest
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        manifest = discovery.generate_manifest()

        # Assert: Manifest complete
        assert manifest["version"] == "1.0"
        assert manifest["total_files"] == 3
        assert len(manifest["files"]) == 3

        # Verify file entries
        file_paths = {f["path"] for f in manifest["files"]}
        assert "commands/test.md" in file_paths
        assert "lib/utils.py" in file_paths
        assert "scripts/setup.py" in file_paths

        # Verify sizes
        file_sizes = {f["path"]: f["size"] for f in manifest["files"]}
        assert file_sizes["commands/test.md"] == 400
        assert file_sizes["lib/utils.py"] == 250
        assert file_sizes["scripts/setup.py"] == 375

    def test_saves_manifest_to_json_file(self, tmp_path):
        """Test that manifest can be saved to JSON file.

        Current: FAILS - Enhanced manifest saving doesn't exist
        """
        # Arrange: Create plugin files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        manifest_path = plugin_dir / "config" / "installation_manifest.json"

        # Act: Save manifest
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        discovery.save_manifest(manifest_path)

        # Assert: Manifest saved
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["total_files"] == 1
        assert manifest["files"][0]["path"] == "commands/test.md"


class TestFileDiscoveryEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_empty_plugin_directory(self, tmp_path):
        """Test discovery handles empty plugin directory gracefully.

        Current: FAILS - Enhanced discovery doesn't exist
        """
        # Arrange: Empty plugin directory
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: No files found
        assert len(files) == 0
        assert discovery.count_files() == 0

    def test_handles_deeply_nested_directories(self, tmp_path):
        """Test discovery handles deeply nested directories.

        Current: FAILS - Enhanced discovery doesn't exist
        """
        # Arrange: Deep nesting
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        deep_dir = plugin_dir / "a" / "b" / "c" / "d" / "e" / "f"
        deep_dir.mkdir(parents=True)

        (deep_dir / "deep_file.py").write_text("deep")

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Deep file found
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]
        assert "a/b/c/d/e/f/deep_file.py" in relative_paths

    def test_handles_unicode_filenames(self, tmp_path):
        """Test discovery handles unicode filenames correctly.

        Current: FAILS - Enhanced discovery doesn't exist
        """
        # Arrange: Unicode filenames
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "测试.md").write_text("test")
        (plugin_dir / "commands" / "ファイル.md").write_text("file")

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Unicode files found
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]
        assert "commands/测试.md" in relative_paths
        assert "commands/ファイル.md" in relative_paths

    def test_skips_symlinks_for_security(self, tmp_path):
        """Test that discovery skips symlinks (prevents CWE-59).

        Current: FAILS - Enhanced security doesn't exist
        """
        # Arrange: Create symlink
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Regular file
        (plugin_dir / "real_file.py").write_text("real")

        # Symlink to file outside plugin dir
        external_file = tmp_path / "external.py"
        external_file.write_text("external")

        symlink = plugin_dir / "symlink.py"
        try:
            symlink.symlink_to(external_file)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        # Act: Discover files
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Symlink excluded
        relative_paths = [str(f.relative_to(plugin_dir)) for f in files]
        assert "real_file.py" in relative_paths
        assert "symlink.py" not in relative_paths
        assert len(files) == 1

    def test_validates_plugin_directory_path_security(self, tmp_path):
        """Test that discovery validates plugin directory path (prevents CWE-22).

        Current: FAILS - Enhanced security doesn't exist
        """
        # Arrange: Path traversal attempt
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        # Act & Assert: Path validation fails
        with pytest.raises(ValueError) as exc_info:
            # Attempt path traversal
            FileDiscovery("../../etc/passwd")

        assert "path" in str(exc_info.value).lower() and ("outside" in str(exc_info.value).lower() or "traversal" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower())

    def test_handles_permission_denied_gracefully(self, tmp_path):
        """Test that discovery handles permission denied errors.

        Current: FAILS - Enhanced error handling doesn't exist
        """
        # Arrange: Create directory with no read permissions
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "accessible.py").write_text("accessible")

        restricted_dir = plugin_dir / "restricted"
        restricted_dir.mkdir()
        (restricted_dir / "secret.py").write_text("secret")

        # Remove read permissions
        import stat
        restricted_dir.chmod(0o000)

        try:
            # Act: Discover files
            from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

            discovery = FileDiscovery(plugin_dir)
            files = discovery.discover_all_files()

            # Assert: Accessible file found, restricted gracefully skipped
            relative_paths = [str(f.relative_to(plugin_dir)) for f in files]
            assert "accessible.py" in relative_paths

            # Restricted dir should be skipped (not crash)
            assert not any("restricted" in p for p in relative_paths)

        finally:
            # Cleanup: Restore permissions
            try:
                restricted_dir.chmod(0o755)
            except:
                pass
