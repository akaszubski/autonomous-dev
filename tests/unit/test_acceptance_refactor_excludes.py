"""Acceptance tests for: refactor_analyzer exclude dirs fix (Issue #514)

Validates that RefactorAnalyzer properly excludes .worktrees/, .claude/,
sessions/ directories and completes all analysis modes without hanging.
"""

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.genai
class TestAcceptanceRefactorExcludes:
    """Acceptance criteria for refactor_analyzer exclude fix (Issue #514)."""

    def test_default_exclude_dirs_exists(self):
        """RefactorAnalyzer must have a class-level DEFAULT_EXCLUDE_DIRS constant."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "plugins/autonomous-dev/lib"))
        from refactor_analyzer import RefactorAnalyzer

        assert hasattr(RefactorAnalyzer, "DEFAULT_EXCLUDE_DIRS"), (
            "RefactorAnalyzer must have DEFAULT_EXCLUDE_DIRS class constant"
        )
        assert isinstance(RefactorAnalyzer.DEFAULT_EXCLUDE_DIRS, (set, frozenset))

    def test_exclude_dirs_contains_required_entries(self):
        """DEFAULT_EXCLUDE_DIRS must include .worktrees, .claude, sessions."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "plugins/autonomous-dev/lib"))
        from refactor_analyzer import RefactorAnalyzer

        required = {".worktrees", ".claude", "sessions"}
        missing = required - RefactorAnalyzer.DEFAULT_EXCLUDE_DIRS
        assert not missing, f"DEFAULT_EXCLUDE_DIRS missing: {missing}"

    def test_exclude_set_defined_once_not_per_method(self):
        """Exclude set must be defined at class level, not duplicated per method."""
        lib_path = PROJECT_ROOT / "plugins/autonomous-dev/lib/refactor_analyzer.py"
        source = lib_path.read_text()

        # Count inline exclude_dirs = { definitions (should be 0 inside methods)
        import re
        # Find exclude_dirs assignments that look like inline sets (not self.exclude_dirs)
        inline_defs = re.findall(
            r'^\s+exclude_dirs\s*=\s*\{', source, re.MULTILINE
        )
        assert len(inline_defs) == 0, (
            f"Found {len(inline_defs)} inline exclude_dirs definitions. "
            "Should use class-level DEFAULT_EXCLUDE_DIRS instead."
        )

    def test_should_skip_path_helper_exists(self):
        """RefactorAnalyzer must have a _should_skip_path helper method."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "plugins/autonomous-dev/lib"))
        from refactor_analyzer import RefactorAnalyzer

        analyzer = RefactorAnalyzer(PROJECT_ROOT)
        assert hasattr(analyzer, "_should_skip_path"), (
            "RefactorAnalyzer must have _should_skip_path() helper method"
        )

    def test_init_accepts_exclude_dirs_override(self):
        """__init__ must accept optional exclude_dirs keyword argument."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "plugins/autonomous-dev/lib"))
        from refactor_analyzer import RefactorAnalyzer

        custom = {".git", "custom_dir"}
        analyzer = RefactorAnalyzer(PROJECT_ROOT, exclude_dirs=custom)
        assert analyzer.exclude_dirs == custom
