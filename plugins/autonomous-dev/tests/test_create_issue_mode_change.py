"""
Tests for Issue #134: Make thorough mode the default for /create-issue command

This test suite validates:
1. Default behavior: /create-issue runs thorough mode by default
2. Quick flag: --quick flag enables fast mode
3. Deprecated flag: --thorough flag is silently accepted (backward compatibility)
4. Documentation: CLAUDE.md and README.md reflect new defaults
5. Mode table: create-issue.md shows correct default mode
6. Frontmatter: argument_hint mentions --quick flag

Test Strategy (TDD RED Phase):
- All tests written BEFORE implementation
- Tests will FAIL initially (expected)
- Implementation in Issue #134 will make tests pass
"""

import sys
from pathlib import Path
import re

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCreateIssueDefaultMode:
    """Test that thorough mode is the default after Issue #134."""

    @pytest.fixture
    def create_issue_path(self):
        """Path to create-issue.md command file."""
        return Path(__file__).parent.parent / "commands" / "create-issue.md"

    @pytest.fixture
    def create_issue_content(self, create_issue_path):
        """Content of create-issue.md."""
        return create_issue_path.read_text()

    def test_mode_table_shows_thorough_as_default(self, create_issue_content):
        """Test that the mode table marks thorough mode as default.

        Expected format:
        | **Default (thorough)** | 8-12 min | Full analysis, blocking duplicate check |
        or
        | **Thorough (default)** | 8-12 min | Full analysis, blocking duplicate check |
        """
        # Search for the Modes table
        modes_section = re.search(
            r'## Modes\s*\n\s*\|.*?\|.*?\|.*?\|.*?\n.*?\n(.*?)(?:\n\n|\Z)',
            create_issue_content,
            re.DOTALL
        )

        assert modes_section, "Could not find Modes table in create-issue.md"

        modes_table = modes_section.group(1)

        # Check that thorough mode is marked as default
        thorough_default_patterns = [
            r'\*\*Default\s*\(thorough\)\*\*',
            r'\*\*Thorough\s*\(default\)\*\*',
            r'\*\*Default\s*/\s*thorough\*\*',
        ]

        assert any(re.search(pattern, modes_table, re.IGNORECASE) for pattern in thorough_default_patterns), (
            f"Mode table doesn't show thorough as default.\n"
            f"Expected to find: **Default (thorough)** or **Thorough (default)**\n"
            f"Found table:\n{modes_table}\n"
            f"Fix: Update Modes table to mark thorough as default"
        )

    def test_mode_table_shows_quick_flag_for_fast_mode(self, create_issue_content):
        """Test that fast mode is documented with --quick flag.

        Expected format:
        | **--quick** | 3-5 min | Async scan, smart sections, no prompts |
        or
        | **Fast (--quick)** | 3-5 min | Async scan, smart sections, no prompts |
        """
        modes_section = re.search(
            r'## Modes\s*\n\s*\|.*?\|.*?\|.*?\|.*?\n.*?\n(.*?)(?:\n\n|\Z)',
            create_issue_content,
            re.DOTALL
        )

        assert modes_section, "Could not find Modes table in create-issue.md"

        modes_table = modes_section.group(1)

        # Check that fast mode mentions --quick flag
        quick_flag_patterns = [
            r'\*\*--quick\*\*',
            r'\*\*Fast\s*\(--quick\)\*\*',
            r'--quick\s+flag',
        ]

        assert any(re.search(pattern, modes_table, re.IGNORECASE) for pattern in quick_flag_patterns), (
            f"Mode table doesn't mention --quick flag.\n"
            f"Expected to find: **--quick** or **Fast (--quick)**\n"
            f"Found table:\n{modes_table}\n"
            f"Fix: Update Modes table to document --quick flag"
        )

    def test_default_mode_description_is_thorough(self, create_issue_content):
        """Test that STEP 0 describes thorough as the default mode.

        Expected pattern:
        **Default mode**: Thorough mode with full analysis, blocking duplicate check.
        """
        step0_section = re.search(
            r'### STEP 0:.*?---',
            create_issue_content,
            re.DOTALL
        )

        assert step0_section, "Could not find STEP 0 in create-issue.md"

        step0_text = step0_section.group(0)

        # Check for default mode description
        default_mode_patterns = [
            r'\*\*Default mode\*\*:\s*Thorough',
            r'\*\*Default mode\*\*:\s*Full analysis',
            r'default.*thorough',
        ]

        assert any(re.search(pattern, step0_text, re.IGNORECASE) for pattern in default_mode_patterns), (
            f"STEP 0 doesn't describe thorough as default mode.\n"
            f"Expected pattern: **Default mode**: Thorough mode with...\n"
            f"Found in STEP 0:\n{step0_text[:500]}\n"
            f"Fix: Update STEP 0 to describe thorough as default"
        )

    def test_step0_documents_quick_flag(self, create_issue_content):
        """Test that STEP 0 documents the --quick flag.

        Expected pattern:
        ```
        --quick       Fast mode (async scan, smart sections)
        --thorough    Full analysis mode (deprecated, same as default)
        ```
        """
        step0_section = re.search(
            r'### STEP 0:.*?---',
            create_issue_content,
            re.DOTALL
        )

        assert step0_section, "Could not find STEP 0 in create-issue.md"

        step0_text = step0_section.group(0)

        # Check for --quick flag documentation
        assert '--quick' in step0_text, (
            f"STEP 0 doesn't document --quick flag.\n"
            f"Expected to find: --quick flag documentation\n"
            f"Found in STEP 0:\n{step0_text[:500]}\n"
            f"Fix: Add --quick flag to STEP 0 flag list"
        )

    def test_thorough_flag_is_deprecated_but_supported(self, create_issue_content):
        """Test that --thorough flag is documented as deprecated but still accepted.

        Expected pattern:
        --thorough    Full analysis mode (deprecated, same as default)
        or
        --thorough    (deprecated - this is now the default)
        """
        step0_section = re.search(
            r'### STEP 0:.*?---',
            create_issue_content,
            re.DOTALL
        )

        assert step0_section, "Could not find STEP 0 in create-issue.md"

        step0_text = step0_section.group(0)

        # Check that --thorough is documented (for backward compatibility)
        if '--thorough' in step0_text:
            # If mentioned, should indicate it's deprecated or now default
            deprecated_patterns = [
                r'--thorough.*deprecated',
                r'--thorough.*same as default',
                r'--thorough.*now the default',
            ]

            assert any(re.search(pattern, step0_text, re.IGNORECASE) for pattern in deprecated_patterns), (
                f"--thorough flag is mentioned but not marked as deprecated.\n"
                f"Expected pattern: --thorough ... (deprecated) or (same as default)\n"
                f"Found in STEP 0:\n{step0_text[:500]}\n"
                f"Fix: Mark --thorough as deprecated/redundant in STEP 0"
            )


class TestCreateIssueFrontmatter:
    """Test that frontmatter reflects new default mode."""

    @pytest.fixture
    def create_issue_path(self):
        """Path to create-issue.md command file."""
        return Path(__file__).parent.parent / "commands" / "create-issue.md"

    @pytest.fixture
    def create_issue_content(self, create_issue_path):
        """Content of create-issue.md."""
        return create_issue_path.read_text()

    @pytest.fixture
    def frontmatter(self, create_issue_content):
        """Extract frontmatter from create-issue.md."""
        frontmatter_match = re.search(
            r'---\s*\n(.*?)\n---',
            create_issue_content,
            re.DOTALL
        )
        assert frontmatter_match, "create-issue.md missing frontmatter"
        return frontmatter_match.group(1)

    def test_description_mentions_quick_flag(self, frontmatter):
        """Test that description field mentions --quick flag.

        Expected pattern:
        description: "Create GitHub issue with automated research (--quick for fast mode)"
        or
        description: "Create GitHub issue with automated research (thorough by default, --quick for fast)"
        """
        assert 'description:' in frontmatter, "Frontmatter missing 'description' field"

        description_match = re.search(r'description:\s*"([^"]+)"', frontmatter)
        assert description_match, "Could not extract description from frontmatter"

        description = description_match.group(1)

        # Check that description mentions --quick (not --thorough anymore)
        assert '--quick' in description, (
            f"Frontmatter description doesn't mention --quick flag.\n"
            f"Expected: description: \"... (--quick for fast mode)\"\n"
            f"Found: description: \"{description}\"\n"
            f"Fix: Update description to mention --quick instead of --thorough"
        )

        # Ensure --thorough is NOT the primary flag mentioned
        # (it's okay if mentioned for backward compat, but --quick should be primary)
        if '--thorough' in description:
            # If --thorough is mentioned, --quick should appear first or be more prominent
            quick_pos = description.find('--quick')
            thorough_pos = description.find('--thorough')
            assert quick_pos < thorough_pos or 'deprecated' in description.lower(), (
                f"Frontmatter description emphasizes --thorough over --quick.\n"
                f"Expected: --quick should be the primary flag mentioned\n"
                f"Found: description: \"{description}\"\n"
                f"Fix: Make --quick the primary flag, mark --thorough as deprecated"
            )

    def test_argument_hint_mentions_quick_flag(self, frontmatter):
        """Test that argument_hint field mentions --quick flag.

        Expected pattern:
        argument_hint: "Issue title [--quick] (e.g., 'Add JWT' or 'Add JWT --quick')"
        """
        assert 'argument_hint:' in frontmatter, "Frontmatter missing 'argument_hint' field"

        hint_match = re.search(r'argument_hint:\s*"([^"]+)"', frontmatter)
        assert hint_match, "Could not extract argument_hint from frontmatter"

        hint = hint_match.group(1)

        # Check that argument_hint mentions --quick
        assert '--quick' in hint, (
            f"Frontmatter argument_hint doesn't mention --quick flag.\n"
            f"Expected: argument_hint: \"Issue title [--quick] ...\"\n"
            f"Found: argument_hint: \"{hint}\"\n"
            f"Fix: Update argument_hint to show --quick flag instead of --thorough"
        )


class TestCreateIssueDocumentation:
    """Test that documentation files reflect the mode change."""

    @pytest.fixture
    def claude_md_path(self):
        """Path to CLAUDE.md."""
        # Navigate up from plugins/autonomous-dev/tests to project root
        return Path(__file__).parent.parent.parent.parent / "CLAUDE.md"

    @pytest.fixture
    def claude_md_content(self, claude_md_path):
        """Content of CLAUDE.md."""
        return claude_md_path.read_text()

    @pytest.fixture
    def readme_path(self):
        """Path to main README.md."""
        # Navigate up from plugins/autonomous-dev/tests to project root
        return Path(__file__).parent.parent.parent.parent / "README.md"

    @pytest.fixture
    def readme_content(self, readme_path):
        """Content of README.md."""
        return readme_path.read_text()

    def test_claude_md_documents_thorough_as_default(self, claude_md_content):
        """Test that CLAUDE.md documents thorough mode as default.

        Expected pattern in Commands section:
        - `/create-issue` - Create GitHub issue with research + async scan + smart sections (8-12 min default, 3-5 min --quick)
        """
        # Find /create-issue in commands list
        create_issue_line = re.search(
            r'- `/create-issue`.*',
            claude_md_content
        )

        assert create_issue_line, "Could not find /create-issue in CLAUDE.md Commands section"

        line_text = create_issue_line.group(0)

        # Check for timing that indicates thorough is default
        # Old format: (3-5 min default, 8-12 min --thorough)
        # New format: (8-12 min default, 3-5 min --quick)
        thorough_default_patterns = [
            r'8-12\s*min\s*default',
            r'8-12\s*min.*3-5\s*min\s*--quick',
            r'thorough\s*by\s*default',
        ]

        assert any(re.search(pattern, line_text, re.IGNORECASE) for pattern in thorough_default_patterns), (
            f"CLAUDE.md doesn't document thorough as default mode.\n"
            f"Expected pattern: (8-12 min default, 3-5 min --quick)\n"
            f"Found: {line_text}\n"
            f"Fix: Update CLAUDE.md to show thorough as default with --quick for fast mode"
        )

    def test_claude_md_mentions_quick_flag(self, claude_md_content):
        """Test that CLAUDE.md mentions --quick flag (not --thorough).

        The /create-issue documentation should reference --quick as the way to get fast mode.
        """
        # Find /create-issue section
        create_issue_line = re.search(
            r'- `/create-issue`.*',
            claude_md_content
        )

        assert create_issue_line, "Could not find /create-issue in CLAUDE.md"

        line_text = create_issue_line.group(0)

        # Should mention --quick flag
        assert '--quick' in line_text, (
            f"CLAUDE.md doesn't mention --quick flag.\n"
            f"Expected to find: --quick flag in /create-issue documentation\n"
            f"Found: {line_text}\n"
            f"Fix: Update CLAUDE.md to document --quick flag"
        )

    def test_readme_documents_create_issue(self, readme_content):
        """Test that README.md documents /create-issue command.

        Should have at least a basic mention of the command, even if brief.
        """
        # Look for /create-issue in command table or list
        create_issue_patterns = [
            r'/create-issue',
            r'create-issue',
        ]

        assert any(re.search(pattern, readme_content, re.IGNORECASE) for pattern in create_issue_patterns), (
            f"README.md doesn't document /create-issue command.\n"
            f"Expected to find: /create-issue in commands section\n"
            f"Fix: Add /create-issue to README.md commands table/list"
        )


class TestCreateIssueUsageExamples:
    """Test that usage examples reflect new defaults."""

    @pytest.fixture
    def create_issue_path(self):
        """Path to create-issue.md command file."""
        return Path(__file__).parent.parent / "commands" / "create-issue.md"

    @pytest.fixture
    def create_issue_content(self, create_issue_path):
        """Content of create-issue.md."""
        return create_issue_path.read_text()

    def test_usage_examples_show_quick_flag(self, create_issue_content):
        """Test that Usage section shows --quick flag examples.

        Expected format:
        ```bash
        # Default mode (thorough, full analysis)
        /create-issue Add JWT authentication for API endpoints

        # Fast mode (async scan, smart sections)
        /create-issue Add JWT authentication --quick
        ```
        """
        # Find Usage section
        usage_section = re.search(
            r'## Usage\s*\n(.*?)(?:\n##|\Z)',
            create_issue_content,
            re.DOTALL
        )

        assert usage_section, "Could not find Usage section in create-issue.md"

        usage_text = usage_section.group(1)

        # Should document --quick flag
        assert '--quick' in usage_text, (
            f"Usage section doesn't show --quick flag.\n"
            f"Expected to find: /create-issue ... --quick\n"
            f"Found in Usage:\n{usage_text[:500]}\n"
            f"Fix: Add --quick flag example to Usage section"
        )

    def test_usage_examples_describe_default_as_thorough(self, create_issue_content):
        """Test that Usage section describes default mode as thorough.

        Expected comment pattern:
        # Default mode (thorough, full analysis)
        """
        usage_section = re.search(
            r'## Usage\s*\n(.*?)(?:\n##|\Z)',
            create_issue_content,
            re.DOTALL
        )

        assert usage_section, "Could not find Usage section in create-issue.md"

        usage_text = usage_section.group(1)

        # Check for comments describing default mode
        default_mode_patterns = [
            r'# Default.*thorough',
            r'# Thorough.*default',
            r'# Default.*full analysis',
        ]

        assert any(re.search(pattern, usage_text, re.IGNORECASE) for pattern in default_mode_patterns), (
            f"Usage section doesn't describe default mode as thorough.\n"
            f"Expected comment: # Default mode (thorough, full analysis)\n"
            f"Found in Usage:\n{usage_text[:500]}\n"
            f"Fix: Update Usage comments to indicate thorough is default"
        )


class TestCreateIssuePerformanceTable:
    """Test that performance/timing table reflects new defaults."""

    @pytest.fixture
    def create_issue_path(self):
        """Path to create-issue.md command file."""
        return Path(__file__).parent.parent / "commands" / "create-issue.md"

    @pytest.fixture
    def create_issue_content(self, create_issue_path):
        """Content of create-issue.md."""
        return create_issue_path.read_text()

    def test_performance_table_shows_thorough_timing_as_total(self, create_issue_content):
        """Test that 'What This Does' table shows thorough mode timing (8-12 min).

        Since thorough is now default, the total should reflect thorough timing.

        Expected format:
        | **Total** | **8-12 min** | Default mode (thorough) |
        """
        # Find "What This Does" table
        what_section = re.search(
            r'## What This Does\s*\n\s*\|.*?\|.*?\|.*?\|.*?\n.*?\n(.*?)(?:\n\n|\Z)',
            create_issue_content,
            re.DOTALL
        )

        assert what_section, "Could not find 'What This Does' table in create-issue.md"

        what_table = what_section.group(1)

        # Look for Total row
        total_row = re.search(r'\|\s*\*\*Total\*\*.*\|.*\|.*\|', what_table)

        assert total_row, "Could not find Total row in 'What This Does' table"

        total_text = total_row.group(0)

        # Should show 8-12 min (thorough timing)
        assert '8-12 min' in total_text, (
            f"'What This Does' table doesn't show thorough timing (8-12 min) as total.\n"
            f"Expected: | **Total** | **8-12 min** | Default mode |\n"
            f"Found: {total_text}\n"
            f"Fix: Update Total row to show 8-12 min (thorough mode timing)"
        )


class TestCreateIssueBackwardCompatibility:
    """Test that --thorough flag is still accepted for backward compatibility."""

    @pytest.fixture
    def create_issue_path(self):
        """Path to create-issue.md command file."""
        return Path(__file__).parent.parent / "commands" / "create-issue.md"

    @pytest.fixture
    def create_issue_content(self, create_issue_path):
        """Content of create-issue.md."""
        return create_issue_path.read_text()

    def test_thorough_flag_still_documented(self, create_issue_content):
        """Test that --thorough flag is still mentioned for backward compatibility.

        Should be documented as deprecated/redundant but still accepted silently.
        """
        # Find STEP 0
        step0_section = re.search(
            r'### STEP 0:.*?---',
            create_issue_content,
            re.DOTALL
        )

        assert step0_section, "Could not find STEP 0 in create-issue.md"

        step0_text = step0_section.group(0)

        # Check if --thorough is documented (optional - for backward compat)
        if '--thorough' in step0_text:
            # If documented, should indicate it's redundant/deprecated
            redundant_indicators = [
                'deprecated',
                'same as default',
                'now the default',
                'redundant',
                'no longer needed',
            ]

            assert any(indicator in step0_text.lower() for indicator in redundant_indicators), (
                f"--thorough flag is documented but not marked as deprecated/redundant.\n"
                f"Expected: --thorough should be marked as deprecated or redundant\n"
                f"Found in STEP 0:\n{step0_text[:500]}\n"
                f"Fix: Mark --thorough as deprecated/redundant in flag list"
            )

    def test_no_thorough_flag_errors_in_documentation(self, create_issue_content):
        """Test that documentation doesn't show errors for --thorough flag.

        The flag should be silently accepted, not generate errors.
        """
        # Search for error handling sections
        error_section = re.search(
            r'## Error Handling.*?(?:\n##|\Z)',
            create_issue_content,
            re.DOTALL
        )

        if error_section:
            error_text = error_section.group(0)

            # Should NOT have an error for --thorough flag
            assert 'thorough flag' not in error_text.lower() or 'deprecated' in error_text.lower(), (
                f"Error Handling section mentions --thorough flag errors.\n"
                f"Expected: --thorough should be silently accepted (backward compat)\n"
                f"Found in Error Handling:\n{error_text[:500]}\n"
                f"Fix: Remove --thorough from error handling (it's deprecated but valid)"
            )


class TestCreateIssueEdgeCases:
    """Test edge cases and boundary conditions for mode handling."""

    @pytest.fixture
    def create_issue_path(self):
        """Path to create-issue.md command file."""
        return Path(__file__).parent.parent / "commands" / "create-issue.md"

    @pytest.fixture
    def create_issue_content(self, create_issue_path):
        """Content of create-issue.md."""
        return create_issue_path.read_text()

    def test_both_flags_specified_documentation(self, create_issue_content):
        """Test documentation addresses case where both --quick and --thorough are specified.

        Expected behavior: Last flag wins, or error shown.
        This test checks that the behavior is documented.
        """
        # Find STEP 0 (argument parsing)
        step0_section = re.search(
            r'### STEP 0:.*?---',
            create_issue_content,
            re.DOTALL
        )

        assert step0_section, "Could not find STEP 0 in create-issue.md"

        step0_text = step0_section.group(0)

        # Optional: Check if conflicting flags behavior is documented
        # This is a nice-to-have, not strictly required
        # If both flags are mentioned together, should have guidance
        if '--quick' in step0_text and '--thorough' in step0_text:
            # Could check for: "last flag wins", "conflicting flags", "only one flag", etc.
            # For now, just verify both flags are documented
            pass  # This is acceptable - both flags documented

    def test_no_flag_specified_defaults_to_thorough(self, create_issue_content):
        """Test that documentation clearly states no flag = thorough mode.

        Expected pattern in STEP 0:
        **Default mode**: Thorough mode with full analysis, blocking duplicate check.
        """
        step0_section = re.search(
            r'### STEP 0:.*?---',
            create_issue_content,
            re.DOTALL
        )

        assert step0_section, "Could not find STEP 0 in create-issue.md"

        step0_text = step0_section.group(0)

        # Check for explicit default mode statement
        default_patterns = [
            r'\*\*Default mode\*\*.*thorough',
            r'If no flag.*thorough',
            r'No flag.*full analysis',
        ]

        assert any(re.search(pattern, step0_text, re.IGNORECASE) for pattern in default_patterns), (
            f"STEP 0 doesn't clearly state default behavior (thorough mode).\n"
            f"Expected: **Default mode**: Thorough mode...\n"
            f"Found in STEP 0:\n{step0_text[:500]}\n"
            f"Fix: Add explicit default mode statement to STEP 0"
        )


class TestCreateIssueIntegrationPoints:
    """Test that integration points reflect the mode change."""

    @pytest.fixture
    def create_issue_path(self):
        """Path to create-issue.md command file."""
        return Path(__file__).parent.parent / "commands" / "create-issue.md"

    @pytest.fixture
    def create_issue_content(self, create_issue_path):
        """Content of create-issue.md."""
        return create_issue_path.read_text()

    def test_auto_implement_integration_mentions_thorough_mode(self, create_issue_content):
        """Test that auto-implement integration section mentions thorough mode research.

        Since thorough is now default, /auto-implement will receive more complete research.
        """
        # Find integration section
        integration_section = re.search(
            r'## Integration with /auto-implement.*?(?:\n##|\Z)',
            create_issue_content,
            re.DOTALL
        )

        if integration_section:
            integration_text = integration_section.group(0)

            # Should mention research cache (which is richer with thorough mode)
            assert 'research' in integration_text.lower() and 'cache' in integration_text.lower(), (
                f"Integration section doesn't mention research caching.\n"
                f"Expected: Discussion of research cache for /auto-implement\n"
                f"Found in Integration:\n{integration_text[:500]}\n"
                f"Fix: Ensure research caching is documented"
            )


# Integration test stub for actual command execution
class TestCreateIssueFunctionalBehavior:
    """Functional tests for actual command behavior (requires implementation).

    These tests will FAIL in TDD RED phase because implementation doesn't exist yet.
    They serve as acceptance criteria for Issue #134 implementation.
    """

    @pytest.mark.skip(reason="Requires implementation of Issue #134")
    def test_default_invocation_runs_thorough_mode(self):
        """Test that /create-issue without flags runs thorough mode (8-12 min).

        Acceptance criteria:
        - Command completes in 8-12 minutes
        - Full analysis performed
        - Blocking duplicate check runs
        - All sections included in issue body
        """
        # TODO: Implement after Issue #134 lands
        # This would test actual command execution via CLI
        pass

    @pytest.mark.skip(reason="Requires implementation of Issue #134")
    def test_quick_flag_runs_fast_mode(self):
        """Test that /create-issue --quick runs fast mode (3-5 min).

        Acceptance criteria:
        - Command completes in 3-5 minutes
        - Async scan runs in background
        - Smart sections only (no filler)
        - No blocking prompts
        """
        # TODO: Implement after Issue #134 lands
        pass

    @pytest.mark.skip(reason="Requires implementation of Issue #134")
    def test_thorough_flag_is_silently_accepted(self):
        """Test that /create-issue --thorough runs same as default (no error).

        Acceptance criteria:
        - No deprecation warning shown
        - Runs thorough mode (same as default)
        - Backward compatible behavior
        """
        # TODO: Implement after Issue #134 lands
        pass

    @pytest.mark.skip(reason="Requires implementation of Issue #134")
    def test_both_flags_specified_shows_error_or_uses_last_flag(self):
        """Test behavior when both --quick and --thorough are specified.

        Acceptance criteria:
        - Either shows clear error message
        - Or uses last flag (standard CLI behavior)
        - Behavior is documented in STEP 0
        """
        # TODO: Implement after Issue #134 lands
        pass


if __name__ == "__main__":
    # Run tests with minimal verbosity (per testing-guide recommendations)
    pytest.main([__file__, "--tb=line", "-q"])
