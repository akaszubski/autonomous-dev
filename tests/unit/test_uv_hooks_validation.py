#!/usr/bin/env python3
"""
TDD Tests for UV Single-File Script Validation - RED PHASE

This test suite validates that all hook files conform to PEP 723 single-file
script standards for UV execution (Issue #172).

Feature:
UV single-file scripts eliminate dependency conflicts by running hooks in
isolated environments with explicit dependencies declared in PEP 723 metadata.

Problem:
Current hooks use sys.path.insert() to find plugin libraries, which:
- Creates dependency conflicts with user projects
- Fails when user has incompatible library versions
- Makes hooks brittle and hard to debug
- Violates Python best practices for dependency management

Solution:
Convert all hooks to PEP 723 single-file scripts that:
1. Use UV shebang: #!/usr/bin/env -S uv run --script --quiet --no-project
2. Include PEP 723 metadata block with dependencies
3. Keep sys.path.insert() as fallback for non-UV environments
4. Are executable (chmod +x) after installation
5. Detect UV environment via UV_PROJECT_ENVIRONMENT variable

Benefits:
- Isolated execution (no dependency conflicts)
- Explicit dependencies (clear requirements)
- Backward compatible (fallback to sys.path)
- Production-ready (UV is stable and fast)

Test Coverage:
1. PEP 723 Metadata Validation
   - All hooks have valid # /// script block
   - Metadata is after shebang, before docstring
   - All hooks declare requires-python >= 3.11
   - All hooks declare dependencies = [] (no external deps)
   - Metadata block format is correct

2. UV Shebang Validation
   - All hooks have UV-compatible shebang
   - Shebang format matches: #!/usr/bin/env -S uv run --script --quiet --no-project
   - Shebang is on first line

3. Executable Permissions
   - All hook files are executable (stat check)
   - install.sh sets executable permissions

4. UV Detection Logic
   - is_running_under_uv() function exists
   - Returns True when UV_PROJECT_ENVIRONMENT is set
   - Returns False when env var missing
   - Doesn't crash on edge cases

5. Fallback Behavior
   - sys.path.insert() pattern still exists
   - Works when UV unavailable

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (hooks not yet updated)
- Implementation makes tests pass (GREEN phase)

Date: 2026-01-02
Feature: UV single-file scripts for hooks
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See hook-patterns skill for hook lifecycle and exit codes.
    See python-standards skill for code conventions.
"""

import os
import re
import stat
from pathlib import Path
from typing import List, Tuple

import pytest


# Constants
HOOKS_DIR = Path(__file__).parent.parent.parent / "plugins/autonomous-dev/hooks"
EXPECTED_UV_SHEBANG = "#!/usr/bin/env -S uv run --script --quiet --no-project"
EXPECTED_PYTHON_VERSION = ">=3.11"
PEP723_PATTERN = re.compile(
    r"^# /// script\n"
    r"# requires-python = \"([^\"]+)\"\n"
    r"# dependencies = \[(.*?)\]\n"
    r"# ///\n",
    re.MULTILINE,
)


# Fixtures
@pytest.fixture
def hook_files() -> List[Path]:
    """Get all Python hook files."""
    if not HOOKS_DIR.exists():
        pytest.skip(f"Hooks directory not found: {HOOKS_DIR}")

    hooks = list(HOOKS_DIR.glob("*.py"))
    if not hooks:
        pytest.skip(f"No hook files found in {HOOKS_DIR}")

    return hooks


@pytest.fixture
def hook_manifest() -> List[str]:
    """Get expected hook files from install manifest."""
    manifest_path = Path(__file__).parent.parent.parent / "plugins/autonomous-dev/config/install_manifest.json"
    if not manifest_path.exists():
        pytest.skip(f"Manifest not found: {manifest_path}")

    import json
    manifest = json.load(manifest_path.open())
    hooks_component = manifest["components"]["hooks"]

    # Extract just the filenames from full paths
    hook_files = [Path(f).name for f in hooks_component["files"]]
    return hook_files


# Test Classes
class TestPEP723MetadataValidation:
    """Test PEP 723 metadata block validation in all hooks."""

    def test_all_hooks_have_pep723_metadata(self, hook_files: List[Path]):
        """All hooks must have valid PEP 723 metadata block."""
        missing_metadata = []

        for hook_file in hook_files:
            content = hook_file.read_text()
            match = PEP723_PATTERN.search(content)

            if not match:
                missing_metadata.append(hook_file.name)

        assert not missing_metadata, (
            f"Hooks missing PEP 723 metadata: {missing_metadata}\n\n"
            f"Expected format:\n"
            f"# /// script\n"
            f'# requires-python = ">=3.11"\n'
            f"# dependencies = []\n"
            f"# ///\n"
        )

    def test_metadata_after_shebang_before_docstring(self, hook_files: List[Path]):
        """PEP 723 metadata must be after shebang, before docstring."""
        incorrect_placement = []

        for hook_file in hook_files:
            lines = hook_file.read_text().split("\n")

            # Find positions
            shebang_line = 0 if lines[0].startswith("#!") else None
            metadata_start = None
            docstring_start = None

            for i, line in enumerate(lines):
                if line.startswith("# /// script"):
                    metadata_start = i
                if line.strip().startswith('"""') and i > 5:  # Skip shebang/metadata
                    docstring_start = i
                    break

            # Validate placement
            if metadata_start is None:
                continue  # Covered by other test

            if shebang_line is not None and metadata_start <= shebang_line:
                incorrect_placement.append((hook_file.name, "metadata before shebang"))

            if docstring_start is not None and metadata_start >= docstring_start:
                incorrect_placement.append((hook_file.name, "metadata after docstring"))

        assert not incorrect_placement, (
            f"Hooks with incorrect metadata placement: {incorrect_placement}\n\n"
            f"Expected order:\n"
            f"1. Shebang (#!/usr/bin/env ...)\n"
            f"2. PEP 723 metadata block\n"
            f"3. Docstring\n"
        )

    def test_requires_python_version(self, hook_files: List[Path]):
        """All hooks must declare requires-python >= 3.11."""
        incorrect_version = []

        for hook_file in hook_files:
            content = hook_file.read_text()
            match = PEP723_PATTERN.search(content)

            if not match:
                continue  # Covered by other test

            python_version = match.group(1)
            if python_version != EXPECTED_PYTHON_VERSION:
                incorrect_version.append((hook_file.name, python_version))

        assert not incorrect_version, (
            f"Hooks with incorrect Python version: {incorrect_version}\n\n"
            f'Expected: requires-python = "{EXPECTED_PYTHON_VERSION}"\n'
        )

    def test_dependencies_empty_list(self, hook_files: List[Path]):
        """All hooks must declare dependencies = [] (no external deps)."""
        incorrect_deps = []

        for hook_file in hook_files:
            content = hook_file.read_text()
            match = PEP723_PATTERN.search(content)

            if not match:
                continue  # Covered by other test

            deps_str = match.group(2).strip()
            if deps_str != "":
                incorrect_deps.append((hook_file.name, deps_str))

        assert not incorrect_deps, (
            f"Hooks with non-empty dependencies: {incorrect_deps}\n\n"
            f"Expected: dependencies = []\n"
            f"UV hooks should use only standard library (no external deps)\n"
        )

    def test_metadata_block_format(self, hook_files: List[Path]):
        """PEP 723 metadata must match exact format specification."""
        format_errors = []

        for hook_file in hook_files:
            content = hook_file.read_text()

            # Check for metadata block existence
            if "# /// script" not in content:
                continue  # Covered by other test

            # Find metadata block
            lines = content.split("\n")
            metadata_lines = []
            in_metadata = False

            for line in lines:
                if line.startswith("# /// script"):
                    in_metadata = True
                    metadata_lines.append(line)
                elif in_metadata:
                    metadata_lines.append(line)
                    if line.startswith("# ///") and len(metadata_lines) > 1:
                        break

            # Validate format
            if len(metadata_lines) != 4:
                format_errors.append((hook_file.name, f"expected 4 lines, got {len(metadata_lines)}"))
                continue

            expected = [
                "# /// script",
                f'# requires-python = "{EXPECTED_PYTHON_VERSION}"',
                "# dependencies = []",
                "# ///",
            ]

            for i, (actual, exp) in enumerate(zip(metadata_lines, expected)):
                if actual != exp:
                    format_errors.append((hook_file.name, f"line {i+1}: expected '{exp}', got '{actual}'"))

        assert not format_errors, (
            f"Hooks with format errors: {format_errors}\n\n"
            f"Expected exact format:\n"
            f"# /// script\n"
            f'# requires-python = "{EXPECTED_PYTHON_VERSION}"\n'
            f"# dependencies = []\n"
            f"# ///\n"
        )


class TestUVShebangValidation:
    """Test UV-compatible shebang validation in all hooks."""

    def test_all_hooks_have_uv_shebang(self, hook_files: List[Path]):
        """All hooks must have UV-compatible shebang."""
        missing_shebang = []

        for hook_file in hook_files:
            first_line = hook_file.read_text().split("\n")[0]

            if first_line != EXPECTED_UV_SHEBANG:
                missing_shebang.append((hook_file.name, first_line))

        assert not missing_shebang, (
            f"Hooks with incorrect shebang: {missing_shebang}\n\n"
            f"Expected: {EXPECTED_UV_SHEBANG}\n"
        )

    def test_shebang_on_first_line(self, hook_files: List[Path]):
        """Shebang must be on first line of file."""
        incorrect_position = []

        for hook_file in hook_files:
            lines = hook_file.read_text().split("\n")

            if not lines[0].startswith("#!"):
                incorrect_position.append(hook_file.name)

        assert not incorrect_position, (
            f"Hooks without shebang on first line: {incorrect_position}\n"
        )

    def test_shebang_format_components(self, hook_files: List[Path]):
        """Shebang must include all required UV components."""
        format_errors = []

        required_components = [
            "/usr/bin/env",
            "-S",
            "uv run",
            "--script",
            "--quiet",
            "--no-project",
        ]

        for hook_file in hook_files:
            first_line = hook_file.read_text().split("\n")[0]

            for component in required_components:
                if component not in first_line:
                    format_errors.append((hook_file.name, f"missing '{component}'"))

        assert not format_errors, (
            f"Hooks with incomplete shebang: {format_errors}\n\n"
            f"Required components: {required_components}\n"
        )


class TestExecutablePermissions:
    """Test that hook files are executable."""

    def test_all_hooks_executable(self, hook_files: List[Path]):
        """All hook files must be executable."""
        non_executable = []

        for hook_file in hook_files:
            file_stat = os.stat(hook_file)
            is_executable = bool(file_stat.st_mode & stat.S_IXUSR)

            if not is_executable:
                non_executable.append(hook_file.name)

        assert not non_executable, (
            f"Hooks not executable: {non_executable}\n\n"
            f"Fix with: chmod +x plugins/autonomous-dev/hooks/*.py\n"
        )

    def test_install_manifest_includes_all_hooks(self, hook_files: List[Path], hook_manifest: List[str]):
        """Install manifest must include all hook files."""
        hook_names = {f.name for f in hook_files}
        manifest_names = set(hook_manifest)

        missing_from_manifest = hook_names - manifest_names
        extra_in_manifest = manifest_names - hook_names

        assert not missing_from_manifest, (
            f"Hooks missing from install manifest: {missing_from_manifest}\n"
        )

        assert not extra_in_manifest, (
            f"Extra hooks in manifest (files don't exist): {extra_in_manifest}\n"
        )


class TestUVDetectionLogic:
    """Test UV environment detection logic in hooks."""

    def test_is_running_under_uv_function_exists(self, hook_files: List[Path]):
        """All hooks should have is_running_under_uv() function."""
        missing_function = []

        for hook_file in hook_files:
            content = hook_file.read_text()

            # Check for function definition
            if "def is_running_under_uv(" not in content:
                missing_function.append(hook_file.name)

        assert not missing_function, (
            f"Hooks missing is_running_under_uv() function: {missing_function}\n\n"
            f"Expected function signature:\n"
            f"def is_running_under_uv() -> bool:\n"
            f'    """Detect if running under UV environment."""\n'
            f'    return "UV_PROJECT_ENVIRONMENT" in os.environ\n'
        )

    def test_uv_detection_uses_env_var(self, hook_files: List[Path]):
        """UV detection must check UV_PROJECT_ENVIRONMENT variable."""
        incorrect_detection = []

        for hook_file in hook_files:
            content = hook_file.read_text()

            if "def is_running_under_uv(" not in content:
                continue  # Covered by other test

            # Extract function body
            func_start = content.find("def is_running_under_uv(")
            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = len(content)

            func_body = content[func_start:func_end]

            # Check for UV_PROJECT_ENVIRONMENT check
            if "UV_PROJECT_ENVIRONMENT" not in func_body:
                incorrect_detection.append(hook_file.name)

        assert not incorrect_detection, (
            f"Hooks with incorrect UV detection: {incorrect_detection}\n\n"
            f'Must check: "UV_PROJECT_ENVIRONMENT" in os.environ\n'
        )

    def test_uv_detection_returns_bool(self, hook_files: List[Path]):
        """UV detection function must return bool."""
        incorrect_return_type = []

        for hook_file in hook_files:
            content = hook_file.read_text()

            if "def is_running_under_uv(" not in content:
                continue  # Covered by other test

            # Check return type annotation
            if "is_running_under_uv() -> bool:" not in content:
                incorrect_return_type.append(hook_file.name)

        assert not incorrect_return_type, (
            f"Hooks with incorrect return type annotation: {incorrect_return_type}\n\n"
            f"Expected: def is_running_under_uv() -> bool:\n"
        )


class TestFallbackBehavior:
    """Test that hooks maintain sys.path.insert() fallback for non-UV environments."""

    def test_sys_path_insert_pattern_exists(self, hook_files: List[Path]):
        """All hooks must keep sys.path.insert() as fallback."""
        missing_fallback = []

        for hook_file in hook_files:
            content = hook_file.read_text()

            # Check for sys.path.insert pattern
            if "sys.path.insert(" not in content:
                missing_fallback.append(hook_file.name)

        assert not missing_fallback, (
            f"Hooks missing sys.path.insert() fallback: {missing_fallback}\n\n"
            f"UV hooks should maintain backward compatibility:\n"
            f"if not is_running_under_uv():\n"
            f"    sys.path.insert(0, str(lib_path))\n"
        )

    def test_fallback_conditional_on_uv_detection(self, hook_files: List[Path]):
        """sys.path.insert() should be conditional on UV detection."""
        unconditional_fallback = []

        for hook_file in hook_files:
            content = hook_file.read_text()

            if "sys.path.insert(" not in content:
                continue  # Covered by other test

            # Find sys.path.insert block
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "sys.path.insert(" in line:
                    # Check previous lines for UV check
                    context = "\n".join(lines[max(0, i-5):i+1])

                    # Should be inside a conditional block checking UV
                    if "is_running_under_uv()" not in context and "UV_PROJECT_ENVIRONMENT" not in context:
                        unconditional_fallback.append(hook_file.name)
                    break

        assert not unconditional_fallback, (
            f"Hooks with unconditional sys.path.insert(): {unconditional_fallback}\n\n"
            f"sys.path.insert() should be conditional:\n"
            f"if not is_running_under_uv():\n"
            f"    sys.path.insert(0, str(lib_path))\n"
        )


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_hooks_handle_missing_env_vars(self, hook_files: List[Path]):
        """Hooks must not crash when UV env vars missing."""
        # This is validated by checking is_running_under_uv() uses 'in os.environ'
        # rather than os.environ['UV_PROJECT_ENVIRONMENT'] which would KeyError

        unsafe_env_access = []

        for hook_file in hook_files:
            content = hook_file.read_text()

            # Check for unsafe os.environ access patterns
            unsafe_patterns = [
                r'os\.environ\["UV_PROJECT_ENVIRONMENT"\]',
                r"os\.environ\['UV_PROJECT_ENVIRONMENT'\]",
            ]

            for pattern in unsafe_patterns:
                if re.search(pattern, content):
                    unsafe_env_access.append(hook_file.name)
                    break

        assert not unsafe_env_access, (
            f"Hooks with unsafe env var access: {unsafe_env_access}\n\n"
            f'Use: "UV_PROJECT_ENVIRONMENT" in os.environ\n'
            f"Not: os.environ['UV_PROJECT_ENVIRONMENT']\n"
        )

    def test_metadata_block_not_duplicated(self, hook_files: List[Path]):
        """Each hook should have exactly one PEP 723 metadata block."""
        duplicate_metadata = []

        for hook_file in hook_files:
            content = hook_file.read_text()

            # Count metadata block markers
            count = content.count("# /// script")

            if count > 1:
                duplicate_metadata.append((hook_file.name, count))

        assert not duplicate_metadata, (
            f"Hooks with duplicate metadata blocks: {duplicate_metadata}\n\n"
            f"Each hook should have exactly one # /// script block\n"
        )

    def test_no_hardcoded_paths(self, hook_files: List[Path]):
        """Hooks should not contain hardcoded absolute paths."""
        hardcoded_paths = []

        # Common hardcoded path patterns
        patterns = [
            r"/home/\w+/",
            r"/Users/\w+/",
            r"C:\\Users\\",
        ]

        for hook_file in hook_files:
            content = hook_file.read_text()

            for pattern in patterns:
                if re.search(pattern, content):
                    hardcoded_paths.append(hook_file.name)
                    break

        assert not hardcoded_paths, (
            f"Hooks with hardcoded paths: {hardcoded_paths}\n\n"
            f"Use Path(__file__).parent or dynamic path detection\n"
        )


# Performance Tests
class TestPerformanceConsiderations:
    """Test performance-related aspects of UV hooks."""

    def test_hooks_use_quiet_flag(self, hook_files: List[Path]):
        """UV shebang should use --quiet flag to reduce output."""
        missing_quiet = []

        for hook_file in hook_files:
            first_line = hook_file.read_text().split("\n")[0]

            if "--quiet" not in first_line:
                missing_quiet.append(hook_file.name)

        assert not missing_quiet, (
            f"Hooks missing --quiet flag: {missing_quiet}\n\n"
            f"UV should run quietly to avoid polluting output\n"
        )

    def test_hooks_use_no_project_flag(self, hook_files: List[Path]):
        """UV shebang should use --no-project flag for isolation."""
        missing_no_project = []

        for hook_file in hook_files:
            first_line = hook_file.read_text().split("\n")[0]

            if "--no-project" not in first_line:
                missing_no_project.append(hook_file.name)

        assert not missing_no_project, (
            f"Hooks missing --no-project flag: {missing_no_project}\n\n"
            f"UV should run in isolation (no project context)\n"
        )


# Summary Test
class TestUVHooksSummary:
    """Summary test that validates all UV requirements."""

    def test_all_hooks_uv_compliant(self, hook_files: List[Path]):
        """All hooks must be UV-compliant (comprehensive check)."""
        non_compliant = []

        for hook_file in hook_files:
            content = hook_file.read_text()
            lines = content.split("\n")

            issues = []

            # 1. Check shebang
            if lines[0] != EXPECTED_UV_SHEBANG:
                issues.append("incorrect shebang")

            # 2. Check PEP 723 metadata
            if not PEP723_PATTERN.search(content):
                issues.append("missing PEP 723 metadata")

            # 3. Check executable
            file_stat = os.stat(hook_file)
            if not bool(file_stat.st_mode & stat.S_IXUSR):
                issues.append("not executable")

            # 4. Check UV detection
            if "def is_running_under_uv(" not in content:
                issues.append("missing UV detection")

            # 5. Check fallback
            if "sys.path.insert(" not in content:
                issues.append("missing fallback")

            if issues:
                non_compliant.append((hook_file.name, issues))

        if non_compliant:
            error_msg = "Hooks not UV-compliant:\n\n"
            for hook_name, issues in non_compliant:
                error_msg += f"  {hook_name}:\n"
                for issue in issues:
                    error_msg += f"    - {issue}\n"

            error_msg += "\nAll hooks must:\n"
            error_msg += f"1. Have UV shebang: {EXPECTED_UV_SHEBANG}\n"
            error_msg += "2. Include PEP 723 metadata block\n"
            error_msg += "3. Be executable (chmod +x)\n"
            error_msg += "4. Have is_running_under_uv() function\n"
            error_msg += "5. Keep sys.path.insert() fallback\n"

            pytest.fail(error_msg)


# Integration with install.sh
class TestInstallScriptIntegration:
    """Test that install.sh properly handles UV hooks."""

    def test_install_script_sets_executable(self):
        """install.sh must set executable permissions on hooks."""
        install_script = Path(__file__).parent.parent.parent / "install.sh"

        if not install_script.exists():
            pytest.skip("install.sh not found")

        content = install_script.read_text()

        # Check for chmod command
        assert "chmod +x" in content or "chmod" in content, (
            "install.sh must set executable permissions on hooks\n"
            "Expected: chmod +x on hooks after installation"
        )
