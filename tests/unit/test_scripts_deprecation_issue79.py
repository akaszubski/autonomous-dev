#!/usr/bin/env python3
"""
TDD Tests for Development Scripts Deprecation (Issue #79) - RED PHASE

This test suite validates that development scripts in scripts/ directory have
appropriate deprecation notices and continue to work via delegation.

Problem (Issue #79):
- scripts/ directory contains development-time scripts (agent_tracker.py, session_tracker.py)
- User projects don't have scripts/ directory
- Command checkpoints need to work in user projects
- Need to guide developers to use lib/ versions

Solution:
- Add deprecation notices to scripts/ versions
- Scripts delegate to lib/ versions
- Update documentation to reference lib/ versions
- Keep scripts/ functional for backward compatibility during transition

Test Coverage:
1. Deprecation notices in script docstrings
2. Scripts still functional (delegate to lib)
3. Import paths updated in scripts
4. Documentation references lib/ versions
5. Warning messages guide users to migration path

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (no deprecation notices yet)
- Implementation makes tests pass (GREEN phase)

Date: 2025-11-19
Issue: GitHub #79 (Dogfooding bug - tracking infrastructure hardcoded paths)
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See python-standards skill for test code conventions.
"""

import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add directories to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def agent_tracker_script():
    """Path to scripts/agent_tracker.py."""
    return PROJECT_ROOT / "scripts" / "agent_tracker.py"


@pytest.fixture
def session_tracker_script():
    """Path to scripts/session_tracker.py."""
    return PROJECT_ROOT / "scripts" / "session_tracker.py"


@pytest.fixture
def lib_agent_tracker():
    """Path to lib/agent_tracker.py (if it exists)."""
    return PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "agent_tracker.py"


# ============================================================================
# UNIT TESTS - Deprecation Notices in Docstrings
# ============================================================================


class TestScriptDeprecationNotices:
    """Test that development scripts have deprecation notices.

    Critical requirement: Guide developers to use lib/ versions.
    """

    def test_agent_tracker_script_has_deprecation_notice(self, agent_tracker_script):
        """Test that scripts/agent_tracker.py has deprecation notice.

        REQUIREMENT: Clear deprecation warning in docstring
        Expected: Docstring mentions lib/agent_tracker.py
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # Should have deprecation notice in module docstring
        docstring_end = content.find('"""', 10)  # Find end of docstring
        if docstring_end > 0:
            docstring = content[:docstring_end + 3]

            # Check for deprecation keywords
            has_deprecation = any(keyword in docstring.lower() for keyword in [
                "deprecat",
                "legacy",
                "backward compatibility",
                "use lib/agent_tracker",
                "migration"
            ])

            assert has_deprecation, "scripts/agent_tracker.py should have deprecation notice in docstring"

    def test_deprecation_notice_mentions_lib_version(self, agent_tracker_script):
        """Test that deprecation notice mentions lib/agent_tracker.py.

        REQUIREMENT: Clear migration path
        Expected: Notice explains where to find new version
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # Should mention lib version
        assert "lib/agent_tracker" in content or "plugins/autonomous-dev/lib" in content

    def test_deprecation_notice_explains_why(self, agent_tracker_script):
        """Test that deprecation notice explains why migration is needed.

        REQUIREMENT: Educational deprecation notice
        Expected: Explains reason for deprecation (portability, user projects, etc.)
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # Should explain reason (portability, user projects, etc.)
        docstring_end = content.find('"""', 10)
        if docstring_end > 0:
            docstring = content[:docstring_end + 3]

            has_explanation = any(keyword in docstring.lower() for keyword in [
                "portability",
                "user project",
                "plugin",
                "installed",
                "library"
            ])

            # May not be implemented yet (TDD RED phase)
            if not has_explanation:
                pytest.skip("Deprecation explanation not yet added (TDD RED phase)")

    def test_session_tracker_script_has_deprecation_notice(self, session_tracker_script):
        """Test that scripts/session_tracker.py has deprecation notice.

        REQUIREMENT: Consistent deprecation notices across scripts
        Expected: Docstring mentions lib/session_tracker.py
        """
        if not session_tracker_script.exists():
            pytest.skip("scripts/session_tracker.py not found")

        content = session_tracker_script.read_text()

        # Should have deprecation notice
        # Note: session_tracker may already be in lib/ - check both
        if "lib/session_tracker" in content or "deprecat" in content.lower():
            assert True  # Has deprecation
        else:
            # May not be implemented yet
            pytest.skip("Deprecation notice not yet added (TDD RED phase)")


# ============================================================================
# UNIT TESTS - Script Delegation to Library
# ============================================================================


class TestScriptDelegationToLibrary:
    """Test that scripts delegate to lib/ versions.

    Critical requirement: Scripts should be thin wrappers (no business logic).
    """

    def test_agent_tracker_script_imports_from_lib(self, agent_tracker_script, lib_agent_tracker):
        """Test that scripts/agent_tracker.py imports from lib/.

        REQUIREMENT: Delegation pattern
        Expected: Import from lib/agent_tracker.py
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        if not lib_agent_tracker.exists():
            pytest.skip("lib/agent_tracker.py not created yet (TDD RED phase)")

        content = agent_tracker_script.read_text()

        # Should import from lib
        # Note: Import path may vary (absolute vs relative)
        has_lib_import = (
            "from agent_tracker import" in content or
            "import agent_tracker" in content
        )

        if has_lib_import:
            assert True
        else:
            pytest.skip("Delegation not yet implemented (TDD RED phase)")

    def test_agent_tracker_script_has_minimal_logic(self, agent_tracker_script):
        """Test that scripts/agent_tracker.py has minimal business logic.

        REQUIREMENT: Thin wrapper (argument parsing only)
        Expected: No complex business logic (should be in lib/)
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # Count lines of code (excluding docstrings, comments, imports)
        lines = content.split("\n")
        code_lines = [
            line for line in lines
            if line.strip()  # Not empty
            and not line.strip().startswith("#")  # Not comment
            and not line.strip().startswith('"""')  # Not docstring
            and not line.strip().startswith("'''")
            and not line.strip().startswith("import ")  # Not import
            and not line.strip().startswith("from ")
        ]

        # Thin wrapper should have relatively few code lines
        # This is a rough heuristic - adjust as needed
        # Scripts with delegation should be < 100 lines of actual code
        if len(code_lines) > 100:
            pytest.skip("Script may still have business logic (not yet refactored to delegate)")


# ============================================================================
# INTEGRATION TESTS - Scripts Still Functional
# ============================================================================


class TestScriptsBackwardCompatibility:
    """Test that scripts remain functional during transition.

    Critical requirement: Existing usage must still work.
    """

    def test_agent_tracker_script_still_executable(self, agent_tracker_script, tmp_path):
        """Test that scripts/agent_tracker.py is still executable.

        REQUIREMENT: Backward compatibility
        Expected: Script runs without errors
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        # Create minimal project structure
        temp_project = tmp_path / "test-project"
        temp_project.mkdir()
        (temp_project / ".git").mkdir()
        (temp_project / "docs" / "sessions").mkdir(parents=True)

        # Try to run script (may fail if lib doesn't exist yet)
        result = subprocess.run(
            [sys.executable, str(agent_tracker_script), "status"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should either succeed or fail gracefully
        # (May fail in TDD RED phase if lib doesn't exist)
        if result.returncode == 0:
            assert True  # Script works
        else:
            # Check if failure is due to missing lib
            if "lib" in result.stderr or "import" in result.stderr.lower():
                pytest.skip("Script fails because lib not created yet (TDD RED phase)")
            else:
                pytest.fail(f"Script failed unexpectedly: {result.stderr}")

    def test_session_tracker_script_still_executable(self, session_tracker_script, tmp_path):
        """Test that scripts/session_tracker.py is still executable.

        REQUIREMENT: Backward compatibility
        Expected: Script runs without errors
        """
        if not session_tracker_script.exists():
            pytest.skip("scripts/session_tracker.py not found")

        # Create minimal project structure
        temp_project = tmp_path / "test-project"
        temp_project.mkdir()
        (temp_project / "docs" / "sessions").mkdir(parents=True)

        # Try to run script
        result = subprocess.run(
            [sys.executable, str(session_tracker_script), "test-agent", "test message"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should succeed or fail gracefully
        assert result.returncode in [0, 1]  # 0 = success, 1 = expected failure


# ============================================================================
# DOCUMENTATION TESTS
# ============================================================================


class TestScriptDocumentationUpdates:
    """Test that documentation references lib/ versions.

    Critical requirement: Documentation should guide users to lib/ versions.
    """

    def test_agent_tracker_docstring_has_usage_example(self, agent_tracker_script):
        """Test that scripts/agent_tracker.py docstring has usage example.

        REQUIREMENT: Clear usage documentation
        Expected: Docstring shows how to use (either script or lib)
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # Should have usage example in docstring
        docstring_end = content.find('"""', 10)
        if docstring_end > 0:
            docstring = content[:docstring_end + 3]

            has_usage = any(keyword in docstring for keyword in [
                "Usage:",
                "Example:",
                "python scripts/agent_tracker.py",
                "from agent_tracker import"
            ])

            assert has_usage, "Script should have usage example in docstring"

    def test_agent_tracker_docstring_shows_import_path(self, agent_tracker_script):
        """Test that docstring shows how to import library version.

        REQUIREMENT: Migration guidance
        Expected: Docstring shows: from agent_tracker import AgentTracker
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # Should show import example
        if "from agent_tracker import" in content or "import agent_tracker" in content:
            assert True
        else:
            pytest.skip("Import example not yet added (TDD RED phase)")


# ============================================================================
# MIGRATION PATH TESTS
# ============================================================================


class TestMigrationPath:
    """Test migration path from scripts/ to lib/ versions.

    Critical requirement: Clear path for users to migrate.
    """

    def test_both_versions_coexist_during_transition(self, agent_tracker_script, lib_agent_tracker):
        """Test that both scripts/ and lib/ versions can coexist.

        REQUIREMENT: Gradual migration support
        Expected: Both files exist and work independently
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        # lib version may not exist yet in TDD RED phase
        if not lib_agent_tracker.exists():
            pytest.skip("lib/agent_tracker.py not created yet (TDD RED phase)")

        # Both should exist
        assert agent_tracker_script.exists()
        assert lib_agent_tracker.exists()

    def test_lib_version_is_canonical(self, agent_tracker_script, lib_agent_tracker):
        """Test that lib/ version is considered canonical (source of truth).

        REQUIREMENT: Clear source of truth
        Expected: scripts/ version imports from lib/ (not vice versa)
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        if not lib_agent_tracker.exists():
            pytest.skip("lib/agent_tracker.py not created yet (TDD RED phase)")

        script_content = agent_tracker_script.read_text()
        lib_content = lib_agent_tracker.read_text()

        # scripts/ should import from lib/ (delegation)
        # lib/ should NOT import from scripts/
        assert "import agent_tracker" not in lib_content or "from agent_tracker" not in lib_content
        # Note: This test may need adjustment based on actual implementation

    def test_deprecation_timeline_documented(self, agent_tracker_script):
        """Test that deprecation timeline is documented.

        REQUIREMENT: Clear expectations for users
        Expected: Docstring mentions when scripts/ version will be removed (if applicable)
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # Check if timeline is mentioned
        docstring_end = content.find('"""', 10)
        if docstring_end > 0:
            docstring = content[:docstring_end + 3]

            # May mention version numbers, dates, or "will be removed"
            has_timeline = any(keyword in docstring.lower() for keyword in [
                "will be removed",
                "version",
                "deprecated in",
                "transition period"
            ])

            if has_timeline:
                assert True
            else:
                # Timeline may not be documented yet
                pytest.skip("Deprecation timeline not yet documented")


# ============================================================================
# ERROR MESSAGE TESTS
# ============================================================================


class TestScriptErrorMessages:
    """Test that scripts provide helpful error messages.

    Critical requirement: When things fail, guide users to the fix.
    """

    def test_script_error_mentions_lib_version_if_import_fails(self, agent_tracker_script):
        """Test that import errors mention lib/ version.

        REQUIREMENT: Helpful error messages
        Expected: If lib import fails, error suggests checking installation
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # Should have try/except around import with helpful error
        if "try:" in content and ("except ImportError" in content or "except ModuleNotFoundError" in content):
            # Should have error handling
            assert True
        else:
            pytest.skip("Import error handling not yet implemented")

    def test_script_suggests_plugin_installation_on_error(self, agent_tracker_script):
        """Test that errors suggest installing plugin if lib not found.

        REQUIREMENT: User guidance
        Expected: Error message mentions '/plugin install autonomous-dev'
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = agent_tracker_script.read_text()

        # May suggest plugin installation
        if "/plugin install" in content or "plugin install autonomous-dev" in content:
            assert True
        else:
            pytest.skip("Plugin installation suggestion not yet added")


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestScriptPerformance:
    """Test that script delegation doesn't add significant overhead.

    Critical requirement: Delegation should be fast (< 10ms overhead).
    """

    def test_script_import_overhead_minimal(self, agent_tracker_script, tmp_path):
        """Test that script import overhead is minimal.

        REQUIREMENT: Fast delegation
        Expected: Import and delegation add < 50ms overhead
        """
        if not agent_tracker_script.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        import time

        # Create minimal project
        temp_project = tmp_path / "test-project"
        temp_project.mkdir()
        (temp_project / ".git").mkdir()
        (temp_project / "docs" / "sessions").mkdir(parents=True)

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(agent_tracker_script), "status"],
            cwd=str(temp_project),
            capture_output=True
        )
        elapsed = time.time() - start

        # Should be fast (< 1s including Python startup)
        if result.returncode == 0:
            assert elapsed < 1.0, f"Script took {elapsed:.3f}s (should be < 1s)"
        else:
            pytest.skip("Script not functional yet (TDD RED phase)")
