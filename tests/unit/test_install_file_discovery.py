"""
TDD Tests for Installation File Discovery Engine (Issue #80 - Phase 1)

Tests the file discovery system that identifies ALL files in plugins/autonomous-dev/
for complete installation coverage.

Current State (RED PHASE):
- Installation manifest doesn't exist yet
- FileDiscovery class doesn't exist yet
- All tests should FAIL

Test Coverage:
- File discovery and counting
- Pattern exclusions
- Nested directory handling
- Manifest generation
"""

import pytest
from pathlib import Path
import json
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.file_discovery import FileDiscovery


class TestFileDiscoveryEngine:
    """Test file discovery for complete installation coverage."""

    def test_discovers_all_plugin_files(self, tmp_path):
        """Test that discovery finds all files in plugin directory.

        Expected behavior:
        - Scans plugins/autonomous-dev/ recursively
        - Counts all files (not just *.md)
        - Returns accurate file count

        Current: FAILS - FileDiscovery class doesn't exist
        """
        # Arrange: Create mock plugin structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Create various file types
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "auto-implement.md").touch()
        (plugin_dir / "commands" / "setup.md").touch()

        (plugin_dir / "lib").mkdir()
        (plugin_dir / "lib" / "security_utils.py").touch()
        (plugin_dir / "lib" / "project_md_updater.py").touch()

        (plugin_dir / "scripts").mkdir()
        (plugin_dir / "scripts" / "setup.py").touch()
        (plugin_dir / "scripts" / "validate.py").touch()

        (plugin_dir / "skills").mkdir()
        (plugin_dir / "skills" / "testing-guide.skill").mkdir()
        (plugin_dir / "skills" / "testing-guide.skill" / "skill.md").touch()
        (plugin_dir / "skills" / "testing-guide.skill" / "docs").mkdir()
        (plugin_dir / "skills" / "testing-guide.skill" / "docs" / "guide.md").touch()

        # Expected: 8 files total (excluding directories)
        expected_count = 8

        # Act: Discover files
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: All files found
        assert len(files) == expected_count, \
            f"Expected {expected_count} files, found {len(files)}"

        # Verify specific files included
        file_names = [f.name for f in files]
        assert "security_utils.py" in file_names
        assert "setup.py" in file_names
        assert "guide.md" in file_names

    def test_excludes_cache_and_build_files(self, tmp_path):
        """Test that discovery excludes cache and build artifacts.

        Expected exclusions:
        - __pycache__/
        - *.pyc
        - .pytest_cache/
        - .git/
        - *.egg-info/

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Create files with cache artifacts
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Valid files
        (plugin_dir / "lib").mkdir()
        (plugin_dir / "lib" / "utils.py").touch()

        # Cache files (should be excluded)
        (plugin_dir / "__pycache__").mkdir()
        (plugin_dir / "__pycache__" / "utils.cpython-39.pyc").touch()
        (plugin_dir / "lib" / "__pycache__").mkdir()
        (plugin_dir / "lib" / "__pycache__" / "utils.cpython-39.pyc").touch()

        # Pytest cache (should be excluded)
        (plugin_dir / ".pytest_cache").mkdir()
        (plugin_dir / ".pytest_cache" / "v").mkdir()
        (plugin_dir / ".pytest_cache" / "v" / "cache").mkdir()

        # Git directory (should be excluded)
        (plugin_dir / ".git").mkdir()
        (plugin_dir / ".git" / "config").touch()

        # Act: Discover files
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Only valid files found (1 file: utils.py)
        assert len(files) == 1, f"Expected 1 file, found {len(files)}"
        assert files[0].name == "utils.py"

        # Verify no cache files
        file_paths = [str(f) for f in files]
        assert not any("__pycache__" in p for p in file_paths)
        assert not any(".pyc" in p for p in file_paths)
        assert not any(".pytest_cache" in p for p in file_paths)
        assert not any(".git" in p for p in file_paths)

    def test_finds_nested_skill_files(self, tmp_path):
        """Test that discovery finds deeply nested files in skills.

        Skills structure:
        - skills/[name].skill/skill.md (metadata)
        - skills/[name].skill/docs/ (documentation)
        - skills/[name].skill/examples/ (examples)
        - skills/[name].skill/templates/ (templates)

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Create nested skill structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        skill_dir = plugin_dir / "skills" / "testing-guide.skill"
        skill_dir.mkdir(parents=True)

        # Create nested files
        (skill_dir / "skill.md").touch()

        (skill_dir / "docs").mkdir()
        (skill_dir / "docs" / "overview.md").touch()
        (skill_dir / "docs" / "advanced.md").touch()

        (skill_dir / "examples").mkdir()
        (skill_dir / "examples" / "pytest.md").touch()
        (skill_dir / "examples" / "unittest.md").touch()

        (skill_dir / "templates").mkdir()
        (skill_dir / "templates" / "test_template.py").touch()

        # Expected: 6 files
        expected_count = 6

        # Act: Discover files
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: All nested files found
        assert len(files) == expected_count, \
            f"Expected {expected_count} files, found {len(files)}"

        # Verify nested structure preserved
        file_names = [f.name for f in files]
        assert "overview.md" in file_names
        assert "advanced.md" in file_names
        assert "pytest.md" in file_names
        assert "test_template.py" in file_names

    def test_finds_all_lib_python_files(self, tmp_path):
        """Test that discovery finds ALL .py files in lib/ (not just *.md).

        Current bug: install.sh only copies *.md files
        Expected: Should find ALL Python files

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Create lib directory with Python files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir(parents=True)

        # Create Python library files
        python_files = [
            "security_utils.py",
            "project_md_updater.py",
            "version_detector.py",
            "sync_dispatcher.py",
            "batch_state_manager.py",
        ]

        for filename in python_files:
            (lib_dir / filename).touch()

        # Act: Discover files
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: All Python files found
        assert len(files) == len(python_files), \
            f"Expected {len(python_files)} files, found {len(files)}"

        file_names = {f.name for f in files}
        for expected_file in python_files:
            assert expected_file in file_names, \
                f"Missing Python file: {expected_file}"

    def test_finds_all_scripts(self, tmp_path):
        """Test that discovery finds ALL script files.

        Current bug: install.sh doesn't copy scripts/
        Expected: Should find all scripts/*.py

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Create scripts directory
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)

        # Create script files
        script_files = [
            "setup.py",
            "validate_installation.py",
            "session_tracker.py",
            "update_project_progress.py",
        ]

        for filename in script_files:
            (scripts_dir / filename).touch()

        # Act: Discover files
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: All scripts found
        assert len(files) == len(script_files)

        file_names = {f.name for f in files}
        for expected_file in script_files:
            assert expected_file in file_names

    def test_counts_files_accurately(self, tmp_path):
        """Test that file count matches actual file count.

        Current bug: install.sh reports ~152 files but should be ~201+

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Create realistic plugin structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Commands: 20 files
        cmd_dir = plugin_dir / "commands"
        cmd_dir.mkdir()
        for i in range(20):
            (cmd_dir / f"command{i}.md").touch()

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

        # Skills: 27 skills × 4 files each = 108 files
        skills_dir = plugin_dir / "skills"
        skills_dir.mkdir()
        for i in range(27):
            skill = skills_dir / f"skill{i}.skill"
            skill.mkdir()
            (skill / "skill.md").touch()
            (skill / "docs").mkdir()
            (skill / "docs" / "guide.md").touch()
            (skill / "examples").mkdir()
            (skill / "examples" / "example.md").touch()
            (skill / "templates").mkdir()
            (skill / "templates" / "template.md").touch()

        # Lib: 30 files
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir()
        for i in range(30):
            (lib_dir / f"lib{i}.py").touch()

        # Scripts: 10 files
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir()
        for i in range(10):
            (scripts_dir / f"script{i}.py").touch()

        # Total: 20 + 42 + 20 + 108 + 30 + 10 = 230 files
        expected_total = 230

        # Act: Discover and count
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()
        count = discovery.count_files()

        # Assert: Accurate count
        assert len(files) == expected_total
        assert count == expected_total

    def test_generates_installation_manifest(self, tmp_path):
        """Test that discovery generates installation manifest.

        Manifest format:
        {
            "version": "1.0",
            "total_files": 201,
            "files": [
                {"path": "commands/auto-implement.md", "size": 1234},
                {"path": "lib/security_utils.py", "size": 5678},
                ...
            ]
        }

        Current: FAILS - Manifest generation doesn't exist
        """
        # Arrange: Create plugin structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        cmd_file = plugin_dir / "commands" / "auto-implement.md"
        cmd_file.write_text("# Auto Implement\n" * 10)  # Some content

        (plugin_dir / "lib").mkdir()
        lib_file = plugin_dir / "lib" / "security_utils.py"
        lib_file.write_text("def secure(): pass\n" * 5)

        # Act: Generate manifest
        discovery = FileDiscovery(plugin_dir)
        manifest = discovery.generate_manifest()

        # Assert: Manifest structure
        assert "version" in manifest
        assert "total_files" in manifest
        assert "files" in manifest
        assert manifest["total_files"] == 2

        # Verify file entries
        assert len(manifest["files"]) == 2

        file_paths = [f["path"] for f in manifest["files"]]
        assert "commands/auto-implement.md" in file_paths
        assert "lib/security_utils.py" in file_paths

        # Verify file sizes
        for file_entry in manifest["files"]:
            assert "size" in file_entry
            assert file_entry["size"] > 0

    def test_saves_manifest_to_json(self, tmp_path):
        """Test that manifest can be saved to JSON file.

        Expected location: config/installation_manifest.json

        Current: FAILS - Manifest saving doesn't exist
        """
        # Arrange: Create plugin structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        manifest_path = plugin_dir / "config" / "installation_manifest.json"
        (plugin_dir / "config").mkdir()

        # Act: Generate and save manifest
        discovery = FileDiscovery(plugin_dir)
        discovery.save_manifest(manifest_path)

        # Assert: Manifest file created
        assert manifest_path.exists()

        # Verify JSON is valid
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["total_files"] == 1
        assert len(manifest["files"]) == 1

    def test_detects_missing_files_from_manifest(self, tmp_path):
        """Test that discovery can detect missing files using manifest.

        Use case: Validate installation completeness

        Current: FAILS - Validation doesn't exist
        """
        # Arrange: Create manifest with expected files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {
            "version": "1.0",
            "total_files": 3,
            "files": [
                {"path": "commands/test1.md", "size": 100},
                {"path": "commands/test2.md", "size": 200},
                {"path": "lib/utils.py", "size": 300},
            ]
        }

        # Create only 2 of 3 files (missing lib/utils.py)
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test1.md").touch()
        (plugin_dir / "commands" / "test2.md").touch()

        # Act: Validate against manifest
        discovery = FileDiscovery(plugin_dir)
        missing = discovery.validate_against_manifest(manifest)

        # Assert: Detected missing file
        assert len(missing) == 1
        assert missing[0] == "lib/utils.py"


class TestFileDiscoveryEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_empty_directory(self, tmp_path):
        """Test discovery handles empty plugin directory gracefully.

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Empty directory
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Act: Discover files
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Empty list returned
        assert len(files) == 0
        assert discovery.count_files() == 0

    def test_handles_nonexistent_directory(self, tmp_path):
        """Test discovery handles nonexistent directory with clear error.

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Nonexistent directory
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"

        # Act & Assert: Raises clear error
        with pytest.raises(FileNotFoundError) as exc_info:
            discovery = FileDiscovery(plugin_dir)
            discovery.discover_all_files()

        assert "Plugin directory not found" in str(exc_info.value)

    def test_excludes_hidden_files(self, tmp_path):
        """Test that hidden files (.*) are excluded from discovery.

        Exceptions: .env.example (should be included)

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Create hidden files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Valid file
        (plugin_dir / "README.md").touch()

        # Hidden files (should be excluded)
        (plugin_dir / ".gitignore").touch()
        (plugin_dir / ".DS_Store").touch()

        # Exception: .env.example should be included
        (plugin_dir / ".env.example").touch()

        # Act: Discover files
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Only README.md and .env.example
        assert len(files) == 2
        file_names = {f.name for f in files}
        assert "README.md" in file_names
        assert ".env.example" in file_names
        assert ".gitignore" not in file_names
        assert ".DS_Store" not in file_names

    def test_preserves_relative_paths(self, tmp_path):
        """Test that discovery preserves relative paths for copying.

        Example:
        - Source: plugins/autonomous-dev/lib/utils.py
        - Relative: lib/utils.py
        - Destination: .claude/lib/utils.py

        Current: FAILS - FileDiscovery doesn't exist
        """
        # Arrange: Create nested structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "lib" / "nested").mkdir(parents=True)
        (plugin_dir / "lib" / "nested" / "utils.py").touch()

        # Act: Discover files
        discovery = FileDiscovery(plugin_dir)
        files = discovery.discover_all_files()

        # Assert: Relative path preserved
        assert len(files) == 1
        relative_path = discovery.get_relative_path(files[0])
        assert relative_path == Path("lib/nested/utils.py")
