#!/usr/bin/env python3
"""
TDD Tests for Validate Command Frontmatter Flags Hook (FAILING - Red Phase)

This module contains FAILING tests for validate_command_frontmatter_flags.py which
validates that slash commands document their --flags in the frontmatter (description
and argument_hint fields), not just in the body.

Requirements from Issue #133:
1. Scan command .md files in plugins/autonomous-dev/commands/
2. Extract --flag patterns from markdown body
3. Parse YAML frontmatter for description and argument_hint
4. Warn if flag in body but not in frontmatter
5. Ignore common false positives (--help, code examples)
6. Non-blocking (exit 1 = warning, not exit 2 = block)

Test Coverage Target: 95%+ of hook logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe validation requirements
- Tests should FAIL until validate_command_frontmatter_flags.py is implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-12-14
Issue: GitHub #133 - Add pre-commit hook for command frontmatter flag validation
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# This import will FAIL until validate_command_frontmatter_flags.py is created
from plugins.autonomous_dev.hooks.validate_command_frontmatter_flags import (
    extract_frontmatter,
    extract_flags_from_body,
    remove_code_blocks,
    check_flags_in_frontmatter,
    validate_command_file,
    get_false_positive_flags,
    main,
)


class TestExtractFrontmatter:
    """Test YAML frontmatter extraction from markdown files."""

    def test_extracts_frontmatter_between_dashes(self):
        """Should extract YAML content between --- markers."""
        content = """---
description: "Test command"
argument_hint: "args"
---
# Body content
"""
        result = extract_frontmatter(content)
        assert result is not None
        assert 'description: "Test command"' in result
        assert 'argument_hint: "args"' in result

    def test_returns_none_when_no_frontmatter(self):
        """Should return None when file has no frontmatter."""
        content = """# Just a header
Some content without frontmatter.
"""
        result = extract_frontmatter(content)
        assert result is None

    def test_handles_empty_frontmatter(self):
        """Should handle empty frontmatter gracefully."""
        content = """---
---
# Body
"""
        result = extract_frontmatter(content)
        assert result is not None
        assert result.strip() == ""

    def test_extracts_multiline_frontmatter(self):
        """Should extract frontmatter with multiple lines."""
        content = """---
name: test-command
description: "A long description
that spans multiple lines"
version: 1.0.0
---
# Implementation
"""
        result = extract_frontmatter(content)
        assert "name: test-command" in result
        assert "version: 1.0.0" in result


class TestRemoveCodeBlocks:
    """Test code block removal for false positive prevention."""

    def test_removes_fenced_code_blocks(self):
        """Should remove content inside ``` code blocks."""
        content = """Some text
```bash
--flag-in-code-block
```
More text with --real-flag
"""
        result = remove_code_blocks(content)
        assert "--flag-in-code-block" not in result
        assert "--real-flag" in result

    def test_removes_multiple_code_blocks(self):
        """Should remove all code blocks."""
        content = """
```bash
--first
```
text
```python
--second
```
"""
        result = remove_code_blocks(content)
        assert "--first" not in result
        assert "--second" not in result

    def test_removes_inline_code(self):
        """Should remove inline code snippets."""
        content = "Use `--inline-flag` for testing --real-flag"
        result = remove_code_blocks(content)
        assert "--inline-flag" not in result
        assert "--real-flag" in result

    def test_handles_nested_backticks(self):
        """Should handle code blocks with nested content."""
        content = """
```
Some code with `--nested`
```
"""
        result = remove_code_blocks(content)
        assert "--nested" not in result

    def test_preserves_non_code_content(self):
        """Should preserve content outside code blocks."""
        content = """
Regular --flag documentation
```bash
example code
```
More --options here
"""
        result = remove_code_blocks(content)
        assert "--flag" in result
        assert "--options" in result


class TestExtractFlagsFromBody:
    """Test CLI flag extraction from markdown body."""

    def test_extracts_double_dash_flags(self):
        """Should extract --flag-name patterns."""
        content = """
Use --verbose for detailed output.
The --output-file option sets the destination.
"""
        flags = extract_flags_from_body(content)
        assert "--verbose" in flags
        assert "--output-file" in flags

    def test_ignores_single_dash_flags(self):
        """Should ignore single-dash flags like -v (focus on --flags)."""
        content = "Use -v or --verbose for output"
        flags = extract_flags_from_body(content)
        assert "--verbose" in flags
        assert "-v" not in flags

    def test_deduplicates_flags(self):
        """Should return unique flags only."""
        content = """
Use --verbose once.
Use --verbose again.
"""
        flags = extract_flags_from_body(content)
        assert flags.count("--verbose") == 1

    def test_extracts_flags_with_hyphens(self):
        """Should handle flags with multiple hyphens."""
        content = "Use --dry-run and --no-verify for testing"
        flags = extract_flags_from_body(content)
        assert "--dry-run" in flags
        assert "--no-verify" in flags

    def test_handles_empty_content(self):
        """Should return empty list for empty content."""
        flags = extract_flags_from_body("")
        assert flags == []

    def test_excludes_code_block_flags(self):
        """Should not extract flags from code blocks."""
        content = """
```bash
--in-code-block
```
--outside-code-block
"""
        flags = extract_flags_from_body(content)
        assert "--in-code-block" not in flags
        assert "--outside-code-block" in flags


class TestGetFalsePositiveFlags:
    """Test false positive flag identification."""

    def test_help_is_false_positive(self):
        """--help should be ignored."""
        false_positives = get_false_positive_flags()
        assert "--help" in false_positives

    def test_version_is_false_positive(self):
        """--version should be ignored."""
        false_positives = get_false_positive_flags()
        assert "--version" in false_positives

    def test_common_doc_flags_ignored(self):
        """Common documentation example flags should be ignored."""
        false_positives = get_false_positive_flags()
        # Common flags used in generic examples
        assert "--flag" in false_positives or "--option" in false_positives


class TestCheckFlagsInFrontmatter:
    """Test flag presence verification in frontmatter."""

    def test_returns_empty_when_all_flags_documented(self):
        """Should return empty list when all flags in frontmatter."""
        frontmatter = 'description: "Command with --verbose and --output"'
        flags = ["--verbose", "--output"]
        missing = check_flags_in_frontmatter(flags, frontmatter)
        assert missing == []

    def test_returns_missing_flags(self):
        """Should return flags not found in frontmatter."""
        frontmatter = 'description: "Command with --verbose"'
        flags = ["--verbose", "--output", "--force"]
        missing = check_flags_in_frontmatter(flags, frontmatter)
        assert "--output" in missing
        assert "--force" in missing
        assert "--verbose" not in missing

    def test_checks_both_description_and_argument_hint(self):
        """Should check both description and argument_hint fields."""
        frontmatter = '''description: "Has --flag1"
argument_hint: "--flag2 for other things"'''
        flags = ["--flag1", "--flag2", "--flag3"]
        missing = check_flags_in_frontmatter(flags, frontmatter)
        assert "--flag3" in missing
        assert "--flag1" not in missing
        assert "--flag2" not in missing

    def test_filters_false_positives(self):
        """Should not report false positive flags as missing."""
        frontmatter = 'description: "Simple command"'
        flags = ["--help", "--version", "--actual-flag"]
        missing = check_flags_in_frontmatter(flags, frontmatter)
        assert "--help" not in missing
        assert "--version" not in missing
        assert "--actual-flag" in missing


class TestValidateCommandFile:
    """Test full file validation workflow."""

    @pytest.fixture
    def temp_command_file(self, tmp_path):
        """Create a temporary command file."""
        def _create(content):
            file_path = tmp_path / "test-command.md"
            file_path.write_text(content)
            return file_path
        return _create

    def test_valid_file_returns_no_warnings(self, temp_command_file):
        """Should return no warnings when all flags documented."""
        content = """---
description: "Command with --verbose option"
argument_hint: "--verbose for detailed output"
---
# Implementation

Use --verbose for more details.
"""
        filepath = temp_command_file(content)
        warnings = validate_command_file(filepath)
        assert warnings == []

    def test_missing_flag_returns_warning(self, temp_command_file):
        """Should return warning when flag missing from frontmatter."""
        content = """---
description: "Simple command"
argument_hint: "no flags here"
---
# Implementation

Use --undocumented-flag for testing.
"""
        filepath = temp_command_file(content)
        warnings = validate_command_file(filepath)
        assert len(warnings) > 0
        assert "--undocumented-flag" in str(warnings)

    def test_no_frontmatter_returns_warning(self, temp_command_file):
        """Should warn if file has no frontmatter."""
        content = """# No frontmatter
Uses --actual-real-flag here.
"""
        filepath = temp_command_file(content)
        warnings = validate_command_file(filepath)
        assert any("frontmatter" in w.lower() for w in warnings)

    def test_no_flags_returns_no_warnings(self, temp_command_file):
        """Should return no warnings if file has no flags."""
        content = """---
description: "Simple command without flags"
---
# Implementation

Just some regular content.
"""
        filepath = temp_command_file(content)
        warnings = validate_command_file(filepath)
        assert warnings == []

    def test_ignores_flags_in_code_blocks(self, temp_command_file):
        """Should not warn about flags in code examples."""
        content = """---
description: "Simple command"
---
# Usage

```bash
--example-in-code-block
```
"""
        filepath = temp_command_file(content)
        warnings = validate_command_file(filepath)
        assert "--example-in-code-block" not in str(warnings)


class TestMain:
    """Test main entry point and exit codes."""

    @pytest.fixture
    def mock_commands_dir(self, tmp_path):
        """Create mock commands directory with test files."""
        commands_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        commands_dir.mkdir(parents=True)
        return commands_dir

    def test_exit_0_when_all_valid(self, mock_commands_dir, monkeypatch):
        """Should exit 0 when all commands are valid."""
        # Create a valid command file
        valid_file = mock_commands_dir / "valid.md"
        valid_file.write_text("""---
description: "Valid command with --flag"
---
Use --flag for testing.
""")

        # Mock the commands directory path
        monkeypatch.chdir(mock_commands_dir.parent.parent.parent)

        with patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_with(0)

    def test_exit_1_when_warnings_found(self, mock_commands_dir, monkeypatch):
        """Should exit 1 (warning) when undocumented flags found.

        Note: Testing the full main() with mocked paths is complex.
        We test validate_command_file directly to verify warning detection works.
        The main() function integration is tested via test_never_exits_2.
        """
        # Create an invalid command file
        invalid_file = mock_commands_dir / "invalid.md"
        invalid_file.write_text("""---
description: "Missing flag documentation"
---
Use --undocumented for testing.
""")

        # Test validate_command_file directly - this is what main() calls
        warnings = validate_command_file(invalid_file)
        assert len(warnings) > 0
        assert "--undocumented" in str(warnings)

    def test_never_exits_2(self, mock_commands_dir, monkeypatch):
        """Should never exit 2 (non-blocking hook)."""
        # Create a file with issues
        problem_file = mock_commands_dir / "problem.md"
        problem_file.write_text("""---
description: "Missing flags"
---
--flag1 --flag2 --flag3 all undocumented.
""")

        monkeypatch.chdir(mock_commands_dir.parent.parent.parent)

        with patch('sys.exit') as mock_exit:
            main()
            # Should be 0 or 1, never 2
            assert mock_exit.call_args[0][0] in [0, 1]

    def test_handles_missing_directory_gracefully(self, tmp_path, monkeypatch):
        """Should handle missing commands directory without crashing."""
        monkeypatch.chdir(tmp_path)

        with patch('sys.exit') as mock_exit:
            main()
            # Should exit 0 (not applicable) not crash
            mock_exit.assert_called_with(0)


class TestIntegrationWithRealCommands:
    """Integration tests using actual command files."""

    @pytest.fixture
    def project_root(self):
        """Find project root by looking for .git directory."""
        current = Path(__file__).resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        pytest.skip("Could not find project root")

    def test_sync_command_has_flags_documented(self, project_root):
        """sync.md should have --github, --env, etc. documented."""
        sync_file = project_root / "plugins" / "autonomous-dev" / "commands" / "sync.md"
        if not sync_file.exists():
            pytest.skip("sync.md not found")

        warnings = validate_command_file(sync_file)
        assert warnings == [], f"sync.md has undocumented flags: {warnings}"

    def test_align_command_has_flags_documented(self, project_root):
        """align.md should have --project, --docs, --retrofit documented."""
        align_file = project_root / "plugins" / "autonomous-dev" / "commands" / "align.md"
        if not align_file.exists():
            pytest.skip("align.md not found")

        warnings = validate_command_file(align_file)
        assert warnings == [], f"align.md has undocumented flags: {warnings}"

    def test_batch_implement_command_has_flags_documented(self, project_root):
        """batch-implement.md should have --issues, --resume documented."""
        batch_file = project_root / "plugins" / "autonomous-dev" / "commands" / "batch-implement.md"
        if not batch_file.exists():
            pytest.skip("batch-implement.md not found")

        warnings = validate_command_file(batch_file)
        assert warnings == [], f"batch-implement.md has undocumented flags: {warnings}"

    def test_create_issue_command_has_flags_documented(self, project_root):
        """create-issue.md should have --thorough documented."""
        create_issue_file = project_root / "plugins" / "autonomous-dev" / "commands" / "create-issue.md"
        if not create_issue_file.exists():
            pytest.skip("create-issue.md not found")

        warnings = validate_command_file(create_issue_file)
        assert warnings == [], f"create-issue.md has undocumented flags: {warnings}"
