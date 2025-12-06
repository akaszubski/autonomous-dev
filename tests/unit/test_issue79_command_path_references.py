"""
Unit tests for Issue #79 - Command path reference portability

Tests validate (TDD RED phase - these will FAIL until implementation):
- auto-implement.md uses portable paths (plugins/autonomous-dev/scripts/)
- batch-implement.md uses portable paths
- create-issue.md uses portable paths
- pipeline-status.md uses portable paths
- No hardcoded 'python scripts/' references remain
- All commands use consistent portable path pattern

Test Strategy:
- File content validation (grep for patterns)
- Path reference consistency checks
- Cross-platform path separator handling
- Verify no hardcoded absolute paths

Expected State After Implementation:
- All commands reference: python plugins/autonomous-dev/scripts/
- No commands reference: python scripts/
- Consistent path pattern across all command files
- Works in user projects without scripts/ directory

Related to: GitHub Issue #79 - Dogfooding bug with hardcoded paths
"""

import re
from pathlib import Path
from typing import List, Tuple

import pytest


# Test constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
COMMANDS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands"


# =============================================================================
# TEST AUTO-IMPLEMENT COMMAND
# =============================================================================


class TestAutoImplementCommandPaths:
    """Test suite for auto-implement.md path references."""

    def test_auto_implement_uses_portable_agent_tracker_paths(self):
        """Test that auto-implement.md uses portable agent_tracker.py paths."""
        command_file = COMMANDS_DIR / "auto-implement.md"
        content = command_file.read_text()

        # Count hardcoded references
        hardcoded_pattern = r'python scripts/agent_tracker\.py'
        hardcoded_matches = re.findall(hardcoded_pattern, content)

        # WILL FAIL: Currently has ~10+ hardcoded references
        assert len(hardcoded_matches) == 0, (
            f"Found {len(hardcoded_matches)} hardcoded 'python scripts/agent_tracker.py' references\n"
            f"Expected: 0 (should use 'python plugins/autonomous-dev/scripts/agent_tracker.py')\n"
            f"Locations:\n" + "\n".join([f"  - Line {i+1}" for i, _ in enumerate(hardcoded_matches[:5])]) +
            f"\nAction: Replace with portable path\n"
            f"Issue: #79"
        )

    def test_auto_implement_uses_portable_session_tracker_paths(self):
        """Test that auto-implement.md uses portable session_tracker.py paths."""
        command_file = COMMANDS_DIR / "auto-implement.md"
        content = command_file.read_text()

        # Count hardcoded references
        hardcoded_pattern = r'python scripts/session_tracker\.py'
        hardcoded_matches = re.findall(hardcoded_pattern, content)

        # WILL FAIL: Currently has ~5+ hardcoded references
        assert len(hardcoded_matches) == 0, (
            f"Found {len(hardcoded_matches)} hardcoded 'python scripts/session_tracker.py' references\n"
            f"Expected: 0 (should use 'python plugins/autonomous-dev/scripts/session_tracker.py')\n"
            f"Action: Replace with portable path\n"
            f"Issue: #79"
        )

    def test_auto_implement_has_portable_agent_tracker_references(self):
        """Test that auto-implement.md has correct portable agent_tracker references."""
        command_file = COMMANDS_DIR / "auto-implement.md"
        content = command_file.read_text()

        # Count portable references
        portable_pattern = r'python plugins/autonomous-dev/scripts/agent_tracker\.py'
        portable_matches = re.findall(portable_pattern, content)

        # WILL FAIL: Currently has 0 portable references
        assert len(portable_matches) >= 7, (
            f"Found only {len(portable_matches)} portable agent_tracker.py references\n"
            f"Expected: At least 7 (for status checks, tracking)\n"
            f"Action: Update all 'scripts/agent_tracker.py' to 'plugins/autonomous-dev/scripts/agent_tracker.py'\n"
            f"Issue: #79"
        )

    def test_auto_implement_has_portable_session_tracker_references(self):
        """Test that auto-implement.md has correct portable session_tracker references."""
        command_file = COMMANDS_DIR / "auto-implement.md"
        content = command_file.read_text()

        # Count portable references
        portable_pattern = r'python plugins/autonomous-dev/scripts/session_tracker\.py'
        portable_matches = re.findall(portable_pattern, content)

        # WILL FAIL: Currently has 0 portable references
        assert len(portable_matches) >= 4, (
            f"Found only {len(portable_matches)} portable session_tracker.py references\n"
            f"Expected: At least 4 (for logging agent actions)\n"
            f"Action: Update all 'scripts/session_tracker.py' to 'plugins/autonomous-dev/scripts/session_tracker.py'\n"
            f"Issue: #79"
        )

    def test_auto_implement_no_mixed_path_styles(self):
        """Test that auto-implement.md doesn't mix hardcoded and portable paths."""
        command_file = COMMANDS_DIR / "auto-implement.md"
        content = command_file.read_text()

        hardcoded_count = len(re.findall(r'python scripts/(?:agent_tracker|session_tracker)\.py', content))
        portable_count = len(re.findall(r'python plugins/autonomous-dev/scripts/(?:agent_tracker|session_tracker)\.py', content))

        # WILL FAIL: Currently has mixed styles
        assert hardcoded_count == 0 or portable_count == 0, (
            f"Found mixed path styles:\n"
            f"  Hardcoded: {hardcoded_count}\n"
            f"  Portable: {portable_count}\n"
            f"Expected: All one style (prefer portable)\n"
            f"Action: Standardize on portable paths\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST BATCH-IMPLEMENT COMMAND
# =============================================================================


class TestBatchImplementCommandPaths:
    """Test suite for batch-implement.md path references."""

    def test_batch_implement_uses_portable_session_tracker_paths(self):
        """Test that batch-implement.md uses portable session_tracker.py paths."""
        command_file = COMMANDS_DIR / "batch-implement.md"

        # Skip test if file doesn't exist or doesn't use tracking
        if not command_file.exists():
            pytest.skip("batch-implement.md not found")

        content = command_file.read_text()

        # Check if it uses session tracking at all
        if "session_tracker" not in content:
            pytest.skip("batch-implement.md doesn't use session_tracker")

        # Count hardcoded references
        hardcoded_pattern = r'python scripts/session_tracker\.py'
        hardcoded_matches = re.findall(hardcoded_pattern, content)

        # WILL FAIL if batch-implement uses hardcoded paths
        assert len(hardcoded_matches) == 0, (
            f"Found {len(hardcoded_matches)} hardcoded 'python scripts/session_tracker.py' references\n"
            f"Expected: 0 (should use 'python plugins/autonomous-dev/scripts/session_tracker.py')\n"
            f"Action: Replace with portable path\n"
            f"Issue: #79"
        )

    def test_batch_implement_uses_portable_agent_tracker_paths(self):
        """Test that batch-implement.md uses portable agent_tracker.py paths."""
        command_file = COMMANDS_DIR / "batch-implement.md"

        if not command_file.exists():
            pytest.skip("batch-implement.md not found")

        content = command_file.read_text()

        # Check if it uses agent tracking
        if "agent_tracker" not in content:
            pytest.skip("batch-implement.md doesn't use agent_tracker")

        # Count hardcoded references
        hardcoded_pattern = r'python scripts/agent_tracker\.py'
        hardcoded_matches = re.findall(hardcoded_pattern, content)

        # WILL FAIL if batch-implement uses hardcoded paths
        assert len(hardcoded_matches) == 0, (
            f"Found {len(hardcoded_matches)} hardcoded 'python scripts/agent_tracker.py' references\n"
            f"Expected: 0 (should use 'python plugins/autonomous-dev/scripts/agent_tracker.py')\n"
            f"Action: Replace with portable path\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST CREATE-ISSUE COMMAND
# =============================================================================


class TestCreateIssueCommandPaths:
    """Test suite for create-issue.md path references."""

    def test_create_issue_uses_portable_session_tracker_path(self):
        """Test that create-issue.md line 159 uses portable session_tracker path."""
        command_file = COMMANDS_DIR / "create-issue.md"

        if not command_file.exists():
            pytest.skip("create-issue.md not found")

        content = command_file.read_text()
        lines = content.split('\n')

        # Check if session_tracker is referenced
        if "session_tracker" not in content:
            pytest.skip("create-issue.md doesn't use session_tracker")

        # Find all session_tracker references
        hardcoded_pattern = r'python scripts/session_tracker\.py'
        hardcoded_matches = []

        for i, line in enumerate(lines, 1):
            if re.search(hardcoded_pattern, line):
                hardcoded_matches.append((i, line))

        # WILL FAIL: Currently has hardcoded reference around line 159
        assert len(hardcoded_matches) == 0, (
            f"Found {len(hardcoded_matches)} hardcoded session_tracker references:\n" +
            "\n".join([f"  Line {i}: {line[:80]}" for i, line in hardcoded_matches]) +
            f"\nExpected: 0 (should use 'python plugins/autonomous-dev/scripts/session_tracker.py')\n"
            f"Action: Replace with portable path\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST PIPELINE-STATUS COMMAND
# =============================================================================


class TestPipelineStatusCommandPaths:
    """Test suite for pipeline-status.md path references."""

    def test_pipeline_status_uses_portable_agent_tracker_path(self):
        """Test that pipeline-status.md line 103 uses portable agent_tracker path."""
        command_file = COMMANDS_DIR / "pipeline-status.md"

        if not command_file.exists():
            pytest.skip("pipeline-status.md not found")

        content = command_file.read_text()
        lines = content.split('\n')

        # Find all agent_tracker references
        hardcoded_pattern = r'python scripts/agent_tracker\.py'
        hardcoded_matches = []

        for i, line in enumerate(lines, 1):
            if re.search(hardcoded_pattern, line):
                hardcoded_matches.append((i, line))

        # WILL FAIL: Currently has hardcoded reference around line 103
        assert len(hardcoded_matches) == 0, (
            f"Found {len(hardcoded_matches)} hardcoded agent_tracker references:\n" +
            "\n".join([f"  Line {i}: {line[:80]}" for i, line in hardcoded_matches]) +
            f"\nExpected: 0 (should use 'python plugins/autonomous-dev/scripts/agent_tracker.py')\n"
            f"Action: Replace with portable path\n"
            f"Issue: #79"
        )

    def test_pipeline_status_has_portable_agent_tracker_reference(self):
        """Test that pipeline-status.md has correct portable agent_tracker reference."""
        command_file = COMMANDS_DIR / "pipeline-status.md"

        if not command_file.exists():
            pytest.skip("pipeline-status.md not found")

        content = command_file.read_text()

        # Count portable references
        portable_pattern = r'python plugins/autonomous-dev/scripts/agent_tracker\.py'
        portable_matches = re.findall(portable_pattern, content)

        # WILL FAIL: Currently has 0 portable references
        assert len(portable_matches) >= 1, (
            f"Found only {len(portable_matches)} portable agent_tracker references\n"
            f"Expected: At least 1 (for pipeline status checks)\n"
            f"Action: Update 'scripts/agent_tracker.py' to 'plugins/autonomous-dev/scripts/agent_tracker.py'\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST CROSS-COMMAND CONSISTENCY
# =============================================================================


class TestCrossCommandConsistency:
    """Test suite for consistent portable paths across all commands."""

    def test_no_hardcoded_scripts_paths_in_any_command(self):
        """Test that no command file uses hardcoded 'python scripts/' pattern."""
        command_files = list(COMMANDS_DIR.glob("*.md"))

        violations = []
        hardcoded_pattern = r'python scripts/(?:agent_tracker|session_tracker)\.py'

        for command_file in command_files:
            content = command_file.read_text()
            matches = re.findall(hardcoded_pattern, content)

            if matches:
                violations.append({
                    'file': command_file.name,
                    'count': len(matches),
                    'pattern': hardcoded_pattern
                })

        # WILL FAIL: Currently has violations in 4+ files
        assert len(violations) == 0, (
            f"Found hardcoded 'python scripts/' paths in {len(violations)} command files:\n" +
            "\n".join([
                f"  - {v['file']}: {v['count']} violations"
                for v in violations
            ]) +
            f"\nExpected: 0 violations (all should use 'python plugins/autonomous-dev/scripts/')\n"
            f"Action: Replace with portable paths in all command files\n"
            f"Issue: #79"
        )

    def test_all_commands_use_plugin_scripts_pattern(self):
        """Test that all commands using tracking use portable plugin paths."""
        command_files = list(COMMANDS_DIR.glob("*.md"))

        # Commands that use tracking
        tracking_commands = []
        portable_pattern = r'python plugins/autonomous-dev/scripts/(?:agent_tracker|session_tracker)\.py'

        for command_file in command_files:
            content = command_file.read_text()

            # Check if it uses any tracking
            if "agent_tracker" in content or "session_tracker" in content:
                portable_matches = re.findall(portable_pattern, content)
                tracking_commands.append({
                    'file': command_file.name,
                    'portable_count': len(portable_matches)
                })

        # WILL FAIL: Currently most have 0 portable paths
        missing_portable = [cmd for cmd in tracking_commands if cmd['portable_count'] == 0]

        assert len(missing_portable) == 0, (
            f"Found {len(missing_portable)} commands using tracking without portable paths:\n" +
            "\n".join([f"  - {cmd['file']}" for cmd in missing_portable]) +
            f"\nExpected: All commands using tracking should use portable paths\n"
            f"Action: Add 'python plugins/autonomous-dev/scripts/' prefix to all tracking calls\n"
            f"Issue: #79"
        )

    def test_path_pattern_consistency(self):
        """Test that all portable paths use consistent pattern."""
        command_files = list(COMMANDS_DIR.glob("*.md"))

        # Expected pattern
        expected_pattern = r'python plugins/autonomous-dev/scripts/'

        # Alternative patterns (inconsistent)
        alternative_patterns = [
            r'python plugins/autonomous_dev/scripts/',  # underscore instead of hyphen
            r'python ./plugins/autonomous-dev/scripts/',  # relative path
            r'python \$\{PLUGIN_DIR\}/scripts/',  # variable substitution
        ]

        inconsistencies = []

        for command_file in command_files:
            content = command_file.read_text()

            for alt_pattern in alternative_patterns:
                if re.search(alt_pattern, content):
                    inconsistencies.append({
                        'file': command_file.name,
                        'pattern': alt_pattern,
                        'expected': expected_pattern
                    })

        # WILL PASS: We don't expect alternative patterns
        assert len(inconsistencies) == 0, (
            f"Found {len(inconsistencies)} inconsistent path patterns:\n" +
            "\n".join([
                f"  - {inc['file']}: uses {inc['pattern']} (should be {inc['expected']})"
                for inc in inconsistencies
            ]) +
            f"\nExpected: All commands use consistent 'python plugins/autonomous-dev/scripts/' pattern\n"
            f"Action: Standardize path pattern\n"
            f"Issue: #79"
        )

    def test_no_absolute_paths_in_commands(self):
        """Test that no command uses absolute paths like /Users/... or C:\\..."""
        command_files = list(COMMANDS_DIR.glob("*.md"))

        # Absolute path patterns
        absolute_patterns = [
            r'/Users/[a-zA-Z0-9_]+/',  # macOS
            r'/home/[a-zA-Z0-9_]+/',   # Linux
            r'C:\\\\Users\\\\',         # Windows
            r'/opt/',                   # Linux system
        ]

        violations = []

        for command_file in command_files:
            content = command_file.read_text()

            for pattern in absolute_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    violations.append({
                        'file': command_file.name,
                        'pattern': pattern,
                        'matches': matches[:3]  # First 3 matches
                    })

        # WILL PASS: We don't expect absolute paths
        assert len(violations) == 0, (
            f"Found {len(violations)} absolute path references:\n" +
            "\n".join([
                f"  - {v['file']}: {v['pattern']} ({', '.join(v['matches'])})"
                for v in violations
            ]) +
            f"\nExpected: All paths should be relative to project root\n"
            f"Action: Replace absolute paths with portable relative paths\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST PATH REFERENCE EXTRACTION
# =============================================================================


class TestPathReferenceExtraction:
    """Test suite for extracting and validating all path references."""

    def test_can_extract_all_python_script_references(self):
        """Test that we can extract all 'python .../*.py' references."""
        command_file = COMMANDS_DIR / "auto-implement.md"
        content = command_file.read_text()

        # Extract all python script references
        python_pattern = r'python\s+([a-zA-Z0-9_/.-]+\.py)'
        matches = re.findall(python_pattern, content)

        # WILL PASS: Should be able to extract references
        assert len(matches) > 0, (
            f"Found no python script references in auto-implement.md\n"
            f"Expected: Should have tracking script references"
        )

    def test_extracted_paths_are_portable(self):
        """Test that all extracted python paths use portable pattern."""
        command_file = COMMANDS_DIR / "auto-implement.md"
        content = command_file.read_text()

        # Extract all python script references
        python_pattern = r'python\s+([a-zA-Z0-9_/.-]+\.py)'
        paths = re.findall(python_pattern, content)

        # Filter tracking scripts
        tracking_paths = [
            p for p in paths
            if 'agent_tracker' in p or 'session_tracker' in p
        ]

        # Check portability
        non_portable = [
            p for p in tracking_paths
            if not p.startswith('plugins/autonomous-dev/scripts/')
        ]

        # WILL FAIL: Currently has non-portable paths
        assert len(non_portable) == 0, (
            f"Found {len(non_portable)} non-portable tracking script paths:\n" +
            "\n".join([f"  - {p}" for p in non_portable[:10]]) +
            f"\nExpected: All paths start with 'plugins/autonomous-dev/scripts/'\n"
            f"Action: Update paths to use portable prefix\n"
            f"Issue: #79"
        )


# =============================================================================
# RUN TESTS
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
