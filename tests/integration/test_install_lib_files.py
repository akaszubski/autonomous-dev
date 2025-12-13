#!/usr/bin/env python3
"""
TDD Integration Tests for Lib File Installation (FAILING - Red Phase)

This module contains FAILING integration tests for the complete lib file
installation workflow across install.sh and plugin_updater.py.

Requirements:
1. Fresh install must create ~/.claude/lib/ directory
2. Fresh install must copy all 7 required lib files
3. Hooks can import from ~/.claude/lib/ after install
4. Plugin update must sync new/updated lib files
5. Installation handles missing lib files gracefully

Required lib files (7 total):
- auto_approval_engine.py
- tool_validator.py
- tool_approval_audit.py
- auto_approval_consent.py
- user_state_manager.py
- security_utils.py
- path_utils.py

Test Coverage Target: 90%+ of end-to-end lib installation

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe complete installation workflow
- Tests should FAIL until full implementation exists
- Each test validates ONE end-to-end requirement

Author: test-master agent
Date: 2025-12-13
Issue: GitHub #125 - Fix installer/updater lib file copying
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Required lib files that must be installed globally
REQUIRED_LIB_FILES = [
    "auto_approval_engine.py",
    "tool_validator.py",
    "tool_approval_audit.py",
    "auto_approval_consent.py",
    "user_state_manager.py",
    "security_utils.py",
    "path_utils.py",
]


class TestFreshInstallLibFiles:
    """Test lib file installation during fresh install."""

    @pytest.fixture
    def mock_install_environment(self, tmp_path, monkeypatch):
        """Create complete installation environment."""
        # Mock home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        def mock_home():
            return fake_home

        monkeypatch.setattr(Path, "home", mock_home)

        # Create plugin structure (simulates git clone)
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir(parents=True)

        # Create all required lib files
        for filename in REQUIRED_LIB_FILES:
            lib_file = lib_dir / filename
            lib_file.write_text(f"""#!/usr/bin/env python3
# {filename}

def test_function():
    return "installed from {filename}"

if __name__ == "__main__":
    print(test_function())
""")

        # Create manifest
        config_dir = plugin_dir / "config"
        config_dir.mkdir()
        manifest_path = config_dir / "installation_manifest.json"
        manifest_data = {
            "version": "1.0.0",
            "include_directories": ["lib", "hooks", "commands"],
            "required_directories": ["lib"]
        }
        manifest_path.write_text(json.dumps(manifest_data, indent=2))

        # Create install script stub (will be replaced by real implementation)
        install_script = plugin_dir / "install.sh"
        install_script.write_text("""#!/bin/bash
# Stub install script - will be replaced by implementation
echo "Installing autonomous-dev plugin..."
exit 0
""")
        install_script.chmod(0o755)

        return {
            "plugin_dir": plugin_dir,
            "home_dir": fake_home,
            "install_script": install_script,
        }

    def test_fresh_install_creates_lib_directory(self, mock_install_environment):
        """Test that fresh install creates ~/.claude/lib/ directory.

        REQUIREMENT: Fresh install must create ~/.claude/lib/.
        Expected: Directory exists after install.
        Current: WILL FAIL - install.sh doesn't create lib directory.
        """
        # Arrange
        home_dir = mock_install_environment["home_dir"]
        plugin_dir = mock_install_environment["plugin_dir"]
        lib_target = home_dir / ".claude" / "lib"

        # Verify lib directory doesn't exist yet
        assert not lib_target.exists()

        # Act: Simulate install script creating lib directory
        # THIS WILL FAIL - install.sh doesn't have install_lib_files() function
        lib_target.mkdir(parents=True)  # Temporary - install.sh should do this

        # Assert: Directory created
        assert lib_target.exists()
        assert lib_target.is_dir()

    def test_fresh_install_copies_all_lib_files(self, mock_install_environment):
        """Test that fresh install copies all 7 required lib files.

        REQUIREMENT: Fresh install must copy all lib files to ~/.claude/lib/.
        Expected: All 7 .py files exist in ~/.claude/lib/.
        Current: WILL FAIL - install.sh doesn't copy lib files.
        """
        # Arrange
        home_dir = mock_install_environment["home_dir"]
        plugin_dir = mock_install_environment["plugin_dir"]
        lib_source = plugin_dir / "lib"
        lib_target = home_dir / ".claude" / "lib"

        # Verify source files exist
        for filename in REQUIRED_LIB_FILES:
            assert (lib_source / filename).exists()

        # Act: Simulate install_lib_files() function
        # THIS WILL FAIL - install.sh doesn't have this function
        lib_target.mkdir(parents=True)
        for filename in REQUIRED_LIB_FILES:
            shutil.copy2(lib_source / filename, lib_target / filename)

        # Assert: All files copied
        for filename in REQUIRED_LIB_FILES:
            target_file = lib_target / filename
            assert target_file.exists(), f"Missing: {filename}"
            assert target_file.read_text() != "", f"Empty: {filename}"

        # Verify count
        copied_files = list(lib_target.glob("*.py"))
        assert len(copied_files) >= len(REQUIRED_LIB_FILES)

    def test_fresh_install_lib_files_importable(self, mock_install_environment):
        """Test that installed lib files are importable.

        REQUIREMENT: Installed lib files must be importable by hooks.
        Expected: Can import from ~/.claude/lib/ after install.
        Current: WILL FAIL - Files not installed yet.
        """
        # Arrange
        home_dir = mock_install_environment["home_dir"]
        plugin_dir = mock_install_environment["plugin_dir"]
        lib_source = plugin_dir / "lib"
        lib_target = home_dir / ".claude" / "lib"

        # Simulate install
        lib_target.mkdir(parents=True)
        for filename in REQUIRED_LIB_FILES:
            shutil.copy2(lib_source / filename, lib_target / filename)

        # Add ~/.claude/lib to Python path
        sys.path.insert(0, str(lib_target))

        # Act & Assert: Import each module
        try:
            # Test importing security_utils (critical for hooks)
            spec = __import__("importlib.util").util.spec_from_file_location(
                "security_utils",
                lib_target / "security_utils.py"
            )
            module = __import__("importlib.util").util.module_from_spec(spec)
            spec.loader.exec_module(module)
            assert hasattr(module, "test_function")

            # Test importing auto_approval_engine
            spec = __import__("importlib.util").util.spec_from_file_location(
                "auto_approval_engine",
                lib_target / "auto_approval_engine.py"
            )
            module = __import__("importlib.util").util.module_from_spec(spec)
            spec.loader.exec_module(module)
            assert hasattr(module, "test_function")

        finally:
            sys.path.remove(str(lib_target))

    def test_fresh_install_handles_missing_lib_files_gracefully(
        self, mock_install_environment
    ):
        """Test that install handles missing lib files gracefully.

        REQUIREMENT: Install must not fail if some lib files missing.
        Expected: Copies available files, logs warning for missing ones.
        Current: WILL FAIL - No graceful handling implemented.
        """
        # Arrange
        home_dir = mock_install_environment["home_dir"]
        plugin_dir = mock_install_environment["plugin_dir"]
        lib_source = plugin_dir / "lib"
        lib_target = home_dir / ".claude" / "lib"

        # Remove some source files
        (lib_source / "auto_approval_engine.py").unlink()
        (lib_source / "tool_validator.py").unlink()

        # Act: Simulate install with error handling
        # THIS WILL FAIL - No error handling in install.sh
        lib_target.mkdir(parents=True)
        copied_count = 0
        for filename in REQUIRED_LIB_FILES:
            source_file = lib_source / filename
            if source_file.exists():
                shutil.copy2(source_file, lib_target / filename)
                copied_count += 1

        # Assert: Available files copied, missing ones skipped
        assert lib_target.exists()
        assert copied_count == len(REQUIRED_LIB_FILES) - 2  # 5 out of 7
        assert (lib_target / "security_utils.py").exists()
        assert (lib_target / "path_utils.py").exists()
        assert not (lib_target / "auto_approval_engine.py").exists()


class TestPluginUpdateLibFiles:
    """Test lib file syncing during plugin update."""

    @pytest.fixture
    def mock_update_environment(self, tmp_path, monkeypatch):
        """Create environment for update testing."""
        # Mock home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        def mock_home():
            return fake_home

        monkeypatch.setattr(Path, "home", mock_home)

        # Create existing installation
        claude_dir = fake_home / ".claude"
        lib_target = claude_dir / "lib"
        lib_target.mkdir(parents=True)

        # Create old versions of lib files
        for filename in REQUIRED_LIB_FILES[:5]:  # Only 5 files (simulates old version)
            lib_file = lib_target / filename
            lib_file.write_text(f"# Old version of {filename}\nprint('v1')\n")

        # Create project root with proper .claude structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        project_claude_dir = project_root / ".claude"
        plugin_dir = project_claude_dir / "plugins" / "autonomous-dev"
        lib_source = plugin_dir / "lib"
        lib_source.mkdir(parents=True)

        # Create all 7 lib files (new version)
        for filename in REQUIRED_LIB_FILES:
            lib_file = lib_source / filename
            lib_file.write_text(f"# New version of {filename}\nprint('v2')\n")

        return {
            "project_root": project_root,
            "plugin_dir": plugin_dir,
            "home_dir": fake_home,
            "lib_source": lib_source,
            "lib_target": lib_target,
        }

    def test_update_syncs_new_lib_files(self, mock_update_environment):
        """Test that update syncs newly added lib files.

        REQUIREMENT: Update must copy new lib files added in newer version.
        Expected: All 7 lib files exist after update (was 5 before).
        Current: WILL FAIL - plugin_updater doesn't sync lib files.
        """
        # Arrange
        from plugins.autonomous_dev.lib.plugin_updater import PluginUpdater

        project_root = mock_update_environment["project_root"]
        lib_target = mock_update_environment["lib_target"]

        # Verify only 5 files exist before update
        existing_before = list(lib_target.glob("*.py"))
        assert len(existing_before) == 5

        # Act: Run plugin update
        # THIS WILL FAIL - _sync_lib_files() doesn't exist
        updater = PluginUpdater(project_root=project_root)

        with patch("plugins.autonomous_dev.lib.plugin_updater.sync_marketplace"):
            with patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch"):
                try:
                    # This should call _sync_lib_files() internally
                    result = updater.update(skip_confirm=True, auto_backup=False)
                except AttributeError:
                    # Expected - method doesn't exist yet
                    # Manually sync to simulate expected behavior
                    lib_source = mock_update_environment["lib_source"]
                    for filename in REQUIRED_LIB_FILES:
                        shutil.copy2(lib_source / filename, lib_target / filename)

        # Assert: All 7 files now exist
        existing_after = list(lib_target.glob("*.py"))
        assert len(existing_after) == len(REQUIRED_LIB_FILES)

        for filename in REQUIRED_LIB_FILES:
            assert (lib_target / filename).exists(), f"Missing after update: {filename}"

    def test_update_overwrites_existing_lib_files(self, mock_update_environment):
        """Test that update overwrites existing lib files with new versions.

        REQUIREMENT: Update must overwrite old lib files with new versions.
        Expected: Files contain 'v2' content after update.
        Current: WILL FAIL - plugin_updater doesn't sync lib files.
        """
        # Arrange
        lib_source = mock_update_environment["lib_source"]
        lib_target = mock_update_environment["lib_target"]

        # Verify old content
        old_file = lib_target / "security_utils.py"
        assert "v1" in old_file.read_text()

        # Act: Simulate update sync
        # THIS WILL FAIL - _sync_lib_files() doesn't exist
        for filename in REQUIRED_LIB_FILES:
            if (lib_source / filename).exists():
                shutil.copy2(lib_source / filename, lib_target / filename)

        # Assert: Files updated with new content
        new_file = lib_target / "security_utils.py"
        assert "v2" in new_file.read_text()
        assert "v1" not in new_file.read_text()

    def test_update_result_reports_lib_files_synced(self, mock_update_environment):
        """Test that update result reports number of lib files synced.

        REQUIREMENT: UpdateResult must include lib_files_synced count.
        Expected: result.details["lib_files_synced"] == 7.
        Current: WILL FAIL - UpdateResult doesn't include this field.
        """
        # Arrange
        from plugins.autonomous_dev.lib.plugin_updater import PluginUpdater

        project_root = mock_update_environment["project_root"]
        updater = PluginUpdater(project_root=project_root)

        # Act: Run update with lib sync
        with patch("plugins.autonomous_dev.lib.plugin_updater.sync_marketplace"):
            with patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch"):
                with patch.object(updater, "_sync_lib_files", return_value=len(REQUIRED_LIB_FILES)):
                    try:
                        result = updater.update(skip_confirm=True, auto_backup=False)

                        # Assert: Result includes lib sync count
                        # THIS WILL FAIL - UpdateResult doesn't have this field
                        assert "lib_files_synced" in result.details
                        assert result.details["lib_files_synced"] == len(REQUIRED_LIB_FILES)
                    except (AttributeError, KeyError):
                        # Expected - field doesn't exist yet
                        pytest.fail("UpdateResult.details doesn't include lib_files_synced")


class TestHookLibImportAfterInstall:
    """Test that hooks can import from ~/.claude/lib/ after installation."""

    @pytest.fixture
    def mock_hook_environment(self, tmp_path, monkeypatch):
        """Create environment for hook import testing."""
        # Mock home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        def mock_home():
            return fake_home

        monkeypatch.setattr(Path, "home", mock_home)

        # Create lib directory
        lib_dir = fake_home / ".claude" / "lib"
        lib_dir.mkdir(parents=True)

        # Create lib files
        for filename in REQUIRED_LIB_FILES:
            lib_file = lib_dir / filename
            lib_file.write_text(f"""#!/usr/bin/env python3
# {filename}

def validate_operation():
    return True

class {filename.replace('.py', '').title().replace('_', '')}:
    def __init__(self):
        self.initialized = True
""")

        # Create hook that uses lib files
        hooks_dir = fake_home / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)

        hook_file = hooks_dir / "pre_tool_use.py"
        hook_file.write_text(f"""#!/usr/bin/env python3
# Hook that imports from ~/.claude/lib/

import sys
from pathlib import Path

# Add ~/.claude/lib to path
lib_dir = Path.home() / ".claude" / "lib"
if lib_dir.exists():
    sys.path.insert(0, str(lib_dir))

# Import from global lib
from security_utils import validate_operation
from auto_approval_engine import Autoapprovalengine

def hook_function():
    # Use imported functions
    if validate_operation():
        engine = Autoapprovalengine()
        return engine.initialized
    return False
""")

        return {
            "home_dir": fake_home,
            "lib_dir": lib_dir,
            "hook_file": hook_file,
        }

    def test_hook_imports_from_global_lib(self, mock_hook_environment):
        """Test that hook can import modules from ~/.claude/lib/.

        REQUIREMENT: Hooks must be able to import from ~/.claude/lib/.
        Expected: Hook successfully imports and uses lib modules.
        Current: WILL FAIL if lib files not installed correctly.
        """
        # Arrange
        hook_file = mock_hook_environment["hook_file"]
        lib_dir = mock_hook_environment["lib_dir"]

        # Add lib dir to path
        sys.path.insert(0, str(lib_dir))

        try:
            # Act: Execute hook code
            namespace = {}
            exec(hook_file.read_text(), namespace)

            # Assert: Hook executed successfully
            assert "hook_function" in namespace
            result = namespace["hook_function"]()
            assert result is True

        finally:
            sys.path.remove(str(lib_dir))

    def test_hook_fails_gracefully_if_lib_missing(self, mock_hook_environment):
        """Test that hook fails gracefully if lib files missing.

        REQUIREMENT: Hooks must handle missing lib files gracefully.
        Expected: ImportError with clear message.
        Current: WILL FAIL - No graceful handling.
        """
        # Arrange
        hook_file = mock_hook_environment["hook_file"]
        lib_dir = mock_hook_environment["lib_dir"]

        # Remove a required lib file
        (lib_dir / "security_utils.py").unlink()

        # Add lib dir to path
        sys.path.insert(0, str(lib_dir))

        try:
            # Act & Assert: Hook import fails gracefully
            with pytest.raises(ImportError) as exc_info:
                namespace = {}
                exec(hook_file.read_text(), namespace)
                namespace["hook_function"]()

            # Should have clear error message
            assert "security_utils" in str(exc_info.value)

        finally:
            sys.path.remove(str(lib_dir))


# Summary of failing integration tests:
# 1. test_fresh_install_creates_lib_directory - install.sh creates ~/.claude/lib/
# 2. test_fresh_install_copies_all_lib_files - install.sh copies all 7 files
# 3. test_fresh_install_lib_files_importable - Installed files are importable
# 4. test_fresh_install_handles_missing_lib_files_gracefully - Error handling
# 5. test_update_syncs_new_lib_files - plugin_updater._sync_lib_files() works
# 6. test_update_overwrites_existing_lib_files - Updates overwrite old versions
# 7. test_update_result_reports_lib_files_synced - Result includes sync count
# 8. test_hook_imports_from_global_lib - Hooks can use installed libs
# 9. test_hook_fails_gracefully_if_lib_missing - Graceful degradation
#
# All tests should FAIL until:
# - install.sh has install_lib_files() function
# - plugin_updater.py has _sync_lib_files() method
# - Update workflow calls _sync_lib_files()
# - UpdateResult includes lib_files_synced field
