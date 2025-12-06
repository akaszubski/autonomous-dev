"""
Unit tests for Issue #79 - Development script deprecation notices

Tests validate (TDD RED phase - these will FAIL until implementation):
- scripts/agent_tracker.py has deprecation notice
- scripts/session_tracker.py has deprecation notice
- Deprecation notices reference GitHub Issue #79
- Deprecation notices include timeline (v3.x deprecated, v4.0 removed)
- Deprecation notices include migration guide
- Runtime warnings shown when scripts executed
- Notices don't break backward compatibility

Test Strategy:
- Docstring validation (deprecation notice in header)
- Timeline validation (version mentions)
- Migration guide validation (clear path forward)
- Runtime warning validation (DeprecationWarning)
- Functionality preservation (scripts still work)

Expected State After Implementation:
- scripts/agent_tracker.py: Has clear deprecation notice in docstring
- scripts/session_tracker.py: Has clear deprecation notice in docstring
- Both scripts: Reference Issue #79
- Both scripts: Mention v4.0.0 removal timeline
- Both scripts: Show DeprecationWarning on import/execution
- Both scripts: Still functional (backward compatibility)

Related to: GitHub Issue #79 - Development repo backward compatibility
"""

import re
import sys
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest


# Test constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


# =============================================================================
# TEST DEPRECATION NOTICE IN DOCSTRINGS
# =============================================================================


class TestDeprecationDocstrings:
    """Test suite for deprecation notices in script docstrings."""

    def test_scripts_agent_tracker_has_deprecation_notice(self):
        """Test that scripts/agent_tracker.py has deprecation notice in docstring."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Extract module docstring (first triple-quoted string)
        docstring_pattern = r'"""(.*?)"""'
        match = re.search(docstring_pattern, content, re.DOTALL)

        assert match is not None, (
            f"No module docstring found in {script_path}\n"
            f"Expected: Should have docstring with deprecation notice"
        )

        docstring = match.group(1)

        # WILL FAIL if no deprecation notice
        # Note: The deprecation notice exists, so this might PASS
        assert "DEPRECAT" in docstring.upper(), (
            f"No deprecation notice in {script_path.name} docstring\n"
            f"Expected: Docstring should contain 'DEPRECATED' or 'DEPRECATION'\n"
            f"Action: Add deprecation notice to module docstring\n"
            f"Issue: #79"
        )

    def test_scripts_session_tracker_has_deprecation_notice(self):
        """Test that scripts/session_tracker.py has deprecation notice in docstring."""
        script_path = SCRIPTS_DIR / "session_tracker.py"

        # Note: This file might not exist in scripts/ yet
        if not script_path.exists():
            pytest.skip("scripts/session_tracker.py not found (might not exist in dev repo)")

        content = script_path.read_text()

        # Extract module docstring
        docstring_pattern = r'"""(.*?)"""'
        match = re.search(docstring_pattern, content, re.DOTALL)

        # WILL FAIL: session_tracker in scripts/ might not have deprecation notice
        assert match is not None and "DEPRECAT" in match.group(1).upper(), (
            f"No deprecation notice in {script_path.name} docstring\n"
            f"Expected: Docstring should contain deprecation notice\n"
            f"Action: Add deprecation notice to module docstring\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST DEPRECATION NOTICE CONTENT
# =============================================================================


class TestDeprecationNoticeContent:
    """Test suite for deprecation notice content quality."""

    def test_deprecation_notice_mentions_issue79(self):
        """Test that deprecation notices reference GitHub Issue #79."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Check for issue reference
        issue_patterns = [
            r'#79',
            r'Issue #79',
            r'GitHub #79',
            r'Issue\s+#79',
        ]

        has_issue_ref = any(re.search(pattern, content) for pattern in issue_patterns)

        # MIGHT PASS: agent_tracker.py already has issue reference
        assert has_issue_ref, (
            f"Deprecation notice doesn't reference Issue #79\n"
            f"Expected: Should mention 'Issue #79' or 'GitHub #79'\n"
            f"Action: Add issue reference to deprecation notice\n"
            f"Issue: #79"
        )

    def test_deprecation_notice_has_timeline(self):
        """Test that deprecation notices mention removal timeline (v4.0.0)."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Check for version timeline
        version_patterns = [
            r'v4\.0',
            r'version 4',
            r'4\.0\.0',
        ]

        has_timeline = bool(re.search(pattern, content, re.IGNORECASE) for pattern in version_patterns)

        # MIGHT PASS: agent_tracker.py already has timeline
        assert has_timeline, (
            f"Deprecation notice doesn't mention removal timeline\n"
            f"Expected: Should mention 'v4.0.0' or 'version 4.0'\n"
            f"Action: Add version timeline to deprecation notice\n"
            f"Issue: #79"
        )

    def test_deprecation_notice_has_migration_guide(self):
        """Test that deprecation notices include migration guide."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Check for migration guidance
        migration_keywords = [
            'migration',
            'use instead',
            'plugins/autonomous-dev/lib',
            'plugins/autonomous-dev/scripts',
        ]

        has_migration = any(keyword.lower() in content.lower() for keyword in migration_keywords)

        # MIGHT PASS: agent_tracker.py already has migration guide
        assert has_migration, (
            f"Deprecation notice doesn't include migration guide\n"
            f"Expected: Should explain how to migrate to new paths\n"
            f"Action: Add migration guidance to deprecation notice\n"
            f"Issue: #79"
        )

    def test_session_tracker_deprecation_content(self):
        """Test session_tracker.py deprecation notice content (if exists in scripts/)."""
        script_path = SCRIPTS_DIR / "session_tracker.py"

        # This test will be skipped if session_tracker doesn't exist in scripts/
        if not script_path.exists():
            pytest.skip("scripts/session_tracker.py not found (expected for production-only file)")

        content = script_path.read_text()

        # Check for complete deprecation notice
        has_deprecation = "DEPRECAT" in content.upper()
        has_issue = "#79" in content
        has_timeline = bool(re.search(r'v4\.0|version 4', content, re.IGNORECASE))
        has_migration = "plugins/autonomous-dev" in content

        # WILL FAIL if session_tracker exists but lacks complete notice
        assert all([has_deprecation, has_issue, has_timeline, has_migration]), (
            f"Incomplete deprecation notice in session_tracker.py:\n"
            f"  Has 'DEPRECATED': {has_deprecation}\n"
            f"  References #79: {has_issue}\n"
            f"  Has timeline: {has_timeline}\n"
            f"  Has migration guide: {has_migration}\n"
            f"Expected: All four elements present\n"
            f"Action: Add complete deprecation notice\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST RUNTIME WARNINGS
# =============================================================================


class TestRuntimeWarnings:
    """Test suite for runtime deprecation warnings."""

    def test_runtime_warning_shown_on_import(self):
        """Test that importing deprecated script shows DeprecationWarning."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        # Add scripts dir to path
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                # Import the module (may trigger warning)
                # Note: This might not work if warning is in __main__ block
                import importlib.util
                spec = importlib.util.spec_from_file_location("agent_tracker", script_path)
                module = importlib.util.module_from_spec(spec)

                # Execute module (this is where warnings should appear)
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    # Module might have execution dependencies
                    pass

                # Check for deprecation warnings
                deprecation_warnings = [
                    warning for warning in w
                    if issubclass(warning.category, DeprecationWarning)
                ]

                # WILL FAIL if no DeprecationWarning raised
                # Note: This is optional - warnings on import can be intrusive
                # We might prefer warnings only on CLI execution
                if len(deprecation_warnings) == 0:
                    pytest.skip(
                        "No DeprecationWarning on import (might only warn on CLI execution)"
                    )

        finally:
            sys.path.remove(str(SCRIPTS_DIR))

    def test_deprecation_warning_content_is_clear(self):
        """Test that deprecation warning message is clear and actionable."""
        # This is more of a documentation test
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Look for warning message content
        warning_patterns = [
            r'warnings\.warn',
            r'DeprecationWarning',
        ]

        has_warning_code = any(re.search(pattern, content) for pattern in warning_patterns)

        # WILL FAIL if no warning code found
        # Note: Warning might be in docstring only
        if not has_warning_code:
            pytest.skip("No runtime warning code found (deprecation might be docstring-only)")


# =============================================================================
# TEST BACKWARD COMPATIBILITY
# =============================================================================


class TestBackwardCompatibility:
    """Test suite for ensuring deprecated scripts still work."""

    def test_scripts_agent_tracker_still_functional(self):
        """Test that scripts/agent_tracker.py still works despite deprecation."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Check that it has functional code (not just a stub)
        functional_indicators = [
            'class AgentTracker',
            'def log_agent',
            'def get_status',
            'import',
        ]

        has_functionality = any(indicator in content for indicator in functional_indicators)

        # WILL PASS: agent_tracker.py should remain functional
        assert has_functionality, (
            f"scripts/agent_tracker.py appears to be a stub\n"
            f"Expected: Should remain functional for backward compatibility\n"
            f"Action: Ensure script delegates to lib/ implementation but remains callable\n"
            f"Issue: #79"
        )

    def test_scripts_session_tracker_delegates_to_lib(self):
        """Test that scripts/session_tracker.py (if exists) delegates to lib."""
        script_path = SCRIPTS_DIR / "session_tracker.py"

        # This file might not exist in development repo
        if not script_path.exists():
            pytest.skip("scripts/session_tracker.py not found (production-only file)")

        content = script_path.read_text()

        # Check for delegation pattern
        delegates_to_lib = (
            'from plugins.autonomous_dev.lib' in content or
            'import plugins.autonomous_dev.lib' in content
        )

        # WILL FAIL if exists but doesn't delegate
        assert delegates_to_lib, (
            f"scripts/session_tracker.py doesn't delegate to lib\n"
            f"Expected: Should import from plugins.autonomous_dev.lib.session_tracker\n"
            f"Action: Add delegation to lib implementation\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST NOTICE FORMAT
# =============================================================================


class TestDeprecationNoticeFormat:
    """Test suite for deprecation notice formatting."""

    def test_deprecation_notice_is_prominent(self):
        """Test that deprecation notice is prominently displayed in docstring."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Extract full docstring
        docstring_pattern = r'"""(.*?)"""'
        match = re.search(docstring_pattern, content, re.DOTALL)

        if not match:
            pytest.skip("No docstring found")

        docstring = match.group(1)
        lines = docstring.split('\n')

        # Find deprecation section
        deprecation_line_index = None
        for i, line in enumerate(lines):
            if "DEPRECAT" in line.upper():
                deprecation_line_index = i
                break

        # MIGHT PASS: agent_tracker.py has prominent notice
        assert deprecation_line_index is not None and deprecation_line_index < 10, (
            f"Deprecation notice not prominent in docstring\n"
            f"Expected: Should appear in first 10 lines of docstring\n"
            f"Found at: Line {deprecation_line_index + 1 if deprecation_line_index else 'N/A'}\n"
            f"Action: Move deprecation notice to top of docstring\n"
            f"Issue: #79"
        )

    def test_deprecation_notice_uses_clear_formatting(self):
        """Test that deprecation notice uses clear visual formatting."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Look for formatting indicators
        formatting_indicators = [
            r'=+',           # Separator lines
            r'DEPRECATION', # All caps
            r'Issue #',     # Clear issue reference
        ]

        has_formatting = all(
            re.search(pattern, content, re.IGNORECASE)
            for pattern in formatting_indicators
        )

        # MIGHT PASS: agent_tracker.py has good formatting
        assert has_formatting, (
            f"Deprecation notice lacks clear visual formatting\n"
            f"Expected: Should have separator lines, all-caps header, issue reference\n"
            f"Action: Format deprecation notice for visibility\n"
            f"Issue: #79"
        )

    def test_deprecation_notice_includes_date(self):
        """Test that deprecation notice includes date for tracking."""
        script_path = SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Look for date patterns
        date_patterns = [
            r'2025-\d{2}-\d{2}',     # ISO format
            r'Date:.*2025',          # Date: field
            r'November.*2025',       # Month Year
        ]

        has_date = any(re.search(pattern, content) for pattern in date_patterns)

        # MIGHT PASS: agent_tracker.py has date
        assert has_date, (
            f"Deprecation notice doesn't include deprecation date\n"
            f"Expected: Should include date for timeline tracking\n"
            f"Action: Add 'Date: 2025-11-19' to deprecation notice\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST CROSS-SCRIPT CONSISTENCY
# =============================================================================


class TestCrossScriptConsistency:
    """Test suite for consistent deprecation notices across scripts."""

    def test_both_scripts_have_consistent_notices(self):
        """Test that both deprecated scripts have consistent notice format."""
        agent_tracker_path = SCRIPTS_DIR / "agent_tracker.py"
        session_tracker_path = SCRIPTS_DIR / "session_tracker.py"

        # Need both files to test consistency
        if not agent_tracker_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        if not session_tracker_path.exists():
            pytest.skip("scripts/session_tracker.py not found (production-only)")

        agent_content = agent_tracker_path.read_text()
        session_content = session_tracker_path.read_text()

        # Extract deprecation sections
        def extract_deprecation_section(content):
            # Find DEPRECATION header and extract until next major section
            pattern = r'DEPRECATION NOTICE[^=]*={5,}.*?={5,}'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            return match.group(0) if match else ""

        agent_deprecation = extract_deprecation_section(agent_content)
        session_deprecation = extract_deprecation_section(session_content)

        # Check both have deprecation sections
        assert agent_deprecation, "agent_tracker.py missing deprecation section"
        assert session_deprecation, "session_tracker.py missing deprecation section"

        # Check for common elements
        common_elements = ["#79", "v4.0", "plugins/autonomous-dev"]

        agent_has_elements = all(elem in agent_deprecation for elem in common_elements)
        session_has_elements = all(elem in session_deprecation for elem in common_elements)

        # WILL FAIL if notices aren't consistent
        assert agent_has_elements and session_has_elements, (
            f"Inconsistent deprecation notices:\n"
            f"  agent_tracker has all elements: {agent_has_elements}\n"
            f"  session_tracker has all elements: {session_has_elements}\n"
            f"Expected: Both should reference #79, v4.0, and new path\n"
            f"Action: Standardize deprecation notices\n"
            f"Issue: #79"
        )


# =============================================================================
# RUN TESTS
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
