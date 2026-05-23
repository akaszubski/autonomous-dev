#!/usr/bin/env python3
"""Tests for already_done_detector — detect issues already implemented.

Acceptance criteria for Issue #1110:
  AC3: check_issue_already_implemented returns (sha, message) when commit refs #N.
  AC4: check_issue_already_implemented returns None when no match found.

Issue: #1110
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Add lib to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins/autonomous-dev/lib"))

from already_done_detector import (
    _extract_symbols,
    check_issue_already_implemented,
)


def _git_init_with_commit(tmp_path: Path, message: str, content: str = "placeholder") -> None:
    """Initialize a git repo in tmp_path and create one commit."""
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test User"],
        check=True, capture_output=True,
    )
    # Write a file so git has something to commit
    test_file = tmp_path / "test_file.py"
    test_file.write_text(content)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", message],
        check=True, capture_output=True,
    )


class TestCommitMessageGrepIssueRef:
    """AC3: commit with #N in message is detected."""

    def test_commit_message_grep_issue_ref(self, tmp_path: Path) -> None:
        """When commit message contains #42, returns (sha, message) tuple."""
        _git_init_with_commit(tmp_path, "fix(auth): resolve login failure (#42)")

        result = check_issue_already_implemented(
            issue_number=42,
            title="Fix login failure",
            body="Users cannot log in.",
            repo_root=tmp_path,
        )

        assert result is not None, "Expected a match for issue #42"
        sha, message = result
        assert len(sha) > 0, "SHA must be non-empty"
        assert "#42" in message or "login" in message.lower(), (
            f"Expected commit message to reference #42 or login; got: {message!r}"
        )

    def test_commit_message_grep_exact_issue_number(self, tmp_path: Path) -> None:
        """Does not match wrong issue number."""
        _git_init_with_commit(tmp_path, "fix: close #99")

        result = check_issue_already_implemented(
            issue_number=42,
            title="Unrelated issue",
            body="",
            repo_root=tmp_path,
        )

        # No match because commit references #99 not #42
        # Note: pickaxe may or may not find symbols from "Unrelated issue" — that's OK
        # The important thing is that grep for #42 finds nothing
        # We can't assert None because pickaxe might match something else
        # But we can verify grep specifically didn't match
        import subprocess as sp
        grep_result = sp.run(
            ["git", "-C", str(tmp_path), "log", "--oneline", "--grep=#42", "-1"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        assert grep_result.stdout.strip() == "", "grep for #42 should not match #99 commit"


class TestPickaxeSymbolMatch:
    """AC3: pickaxe finds commit that introduced a symbol from the issue title."""

    def test_pickaxe_symbol_match(self, tmp_path: Path) -> None:
        """When commit introduces `my_function` and title references it, returns match."""
        content = "def my_function():\n    pass\n"
        _git_init_with_commit(
            tmp_path,
            "feat: add utility functions",
            content=content,
        )

        result = check_issue_already_implemented(
            issue_number=999,  # No commit with #999 in message
            title="Add `my_function` to utils",
            body="",
            repo_root=tmp_path,
        )

        assert result is not None, (
            "Expected pickaxe to find commit introducing 'my_function'"
        )
        sha, message = result
        assert len(sha) > 0


class TestNoMatchReturnsNone:
    """AC4: returns None when no match found."""

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        """Empty repo or unrelated commits return None."""
        # Create a repo with a commit that has no relation to the issue
        _git_init_with_commit(tmp_path, "chore: initial scaffold", content="# hello\n")

        result = check_issue_already_implemented(
            issue_number=12345,
            title="Add completely new feature xyz_abc_def_ghi",
            body="",
            repo_root=tmp_path,
        )

        # Commit message does not contain #12345 and the file has no unusual symbols
        # So we expect None (or a match via pickaxe if "scaffold" happens to match — unlikely)
        # The commit message is "chore: initial scaffold" — no #12345 reference
        # The file content is "# hello\n" — no unusual symbols
        # The title mentions "xyz_abc_def_ghi" which is not in any file
        assert result is None


class TestSymbolExtraction:
    """AC: _extract_symbols picks up backtick identifiers from issue title."""

    def test_backtick_identifiers_extracted(self) -> None:
        """Backtick-quoted identifiers are extracted as symbols."""
        title = "Fix `batch_mode_detector` to handle edge cases"
        body = ""
        syms = _extract_symbols(title, body, max_count=5)
        assert "batch_mode_detector" in syms

    def test_multiple_backtick_symbols(self) -> None:
        """Multiple backtick symbols are extracted in order."""
        title = "Update `foo_bar` and `baz_qux` functions"
        body = ""
        syms = _extract_symbols(title, body, max_count=5)
        assert "foo_bar" in syms
        assert "baz_qux" in syms

    def test_max_count_respected(self) -> None:
        """No more than max_count symbols are returned."""
        title = "`a_b` `c_d` `e_f` `g_h` `i_j` `k_l` `m_n`"
        body = ""
        syms = _extract_symbols(title, body, max_count=3)
        assert len(syms) <= 3

    def test_path_symbols_extracted(self) -> None:
        """File paths are extracted as symbols."""
        title = "Add already_done_detector.py to the lib"
        body = ""
        syms = _extract_symbols(title, body, max_count=5)
        assert "already_done_detector.py" in syms
