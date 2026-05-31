#!/usr/bin/env python3
"""Tests for already_done_detector — detect issues already implemented.

Acceptance criteria for Issue #1110:
  AC3: check_issue_already_implemented returns MatchResult when commit closes #N.
  AC4: check_issue_already_implemented returns None when no match found.

Acceptance criteria for Issue #1125 (false-positive fix):
  - Anti-markers (Pending: #N, Preflight-skipped: #N) MUST NOT match as done.
  - Closure markers (Closes #N, Fixes #N, Completed: #N) MUST match as done.
  - Commits not in HEAD ancestry MUST be downgraded to "stale_branch" and skipped.

Issue: #1110, #1125
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Add lib to path
sys.path.insert(
    0, str(Path(__file__).resolve().parents[3] / "plugins/autonomous-dev/lib")
)

from already_done_detector import (  # noqa: E402
    MatchResult,
    _classify_issue_in_body,
    _extract_symbols,
    check_issue_already_implemented,
)


# Verbatim body of commit 41a3def (used as a real-world fixture).
COMMIT_41A3DEF_BODY = (
    "Merge batch 20260524-230923 (partial): 2 of 16 issues (#980, #981)\n"
    "\n"
    "Remaining 14 issues require /clear + /implement --resume due to context "
    "saturation in this session.\n"
    "Preflight-skipped: #908 (stale branch with deferred ACs), #1112 (trends meta).\n"
    "Completed: #980, #981.\n"
    "Pending: #983, #986, #987, #988, #990, #1002, #1031, #1040, #1055, #1073, "
    "#1095, #1106, #1116, #1117.\n"
)


def _git_init_with_commit(
    tmp_path: Path, message: str, content: str = "placeholder"
) -> str:
    """Initialize a git repo in tmp_path and create one commit. Returns the SHA."""
    subprocess.run(
        ["git", "init", "-b", "main", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )
    test_file = tmp_path / "test_file.py"
    test_file.write_text(content)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", message],
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return head.stdout.strip()


class TestCommitMessageGrepIssueRef:
    """AC3: commit with explicit closure marker for #N is detected."""

    def test_commit_message_grep_issue_ref(self, tmp_path: Path) -> None:
        """When commit message contains 'Closes #42', returns MatchResult."""
        _git_init_with_commit(tmp_path, "fix(auth): resolve login failure\n\nCloses #42")

        result = check_issue_already_implemented(
            issue_number=42,
            title="Fix login failure",
            body="Users cannot log in.",
            repo_root=tmp_path,
        )

        assert result is not None, "Expected a match for issue #42"
        assert isinstance(result, MatchResult)
        assert len(result.sha) > 0
        assert result.classification == "closes"

    def test_commit_message_grep_exact_issue_number(self, tmp_path: Path) -> None:
        """Does not match wrong issue number."""
        _git_init_with_commit(tmp_path, "fix: close #99")

        # No commit references #42 explicitly with closure marker — grep
        # specifically should not match #42.
        grep_result = subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "log",
                "--all",
                "--oneline",
                "--grep=#42",
                "-1",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        assert grep_result.stdout.strip() == "", "grep for #42 should not match #99 commit"


class TestPickaxeSymbolMatch:
    """AC3: pickaxe path is advisory-only; must return None per docstring contract."""

    def test_pickaxe_does_not_return_when_no_issue_reference(
        self, tmp_path: Path
    ) -> None:
        """When commit introduces `my_function` and the title references it,
        the pickaxe path may find a match. Because the commit does not contain
        an explicit closure marker for the issue, the detector MUST return None.
        Per docstring (lines 304-307), only 'closes' classifications are ever
        returned to the caller — pickaxe is advisory-only (Issue #1131)."""
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

        # Pickaxe-only matches MUST return None — docstring contract at lines 304-307.
        assert result is None, (
            "Pickaxe-only matches must NOT return MatchResult — docstring "
            "contract at already_done_detector.py:304-307 (Issue #1131)"
        )

    def test_pickaxe_only_match_returns_none_per_docstring_contract(
        self, tmp_path: Path
    ) -> None:
        """Regression test for Issue #1131.

        When grep finds no commits referencing the issue but pickaxe finds a symbol
        hit, the function MUST return None — not MatchResult(classification='mention').
        The docstring (lines 304-307) promises only 'closes' classifications reach
        the caller. Pickaxe is advisory-only.

        This test MUST FAIL without the fix at line 337 and PASS with it.
        """
        # Set up a temp git repo with a commit whose body references a symbol
        # but contains NO #999 reference in the commit message.
        # The symbol `batch_mode_detector` is in the issue title, so pickaxe
        # will find the commit — but there is no closure marker.
        content = "def batch_mode_detector():\n    pass\n"
        _git_init_with_commit(
            tmp_path,
            "feat: add batch_mode_detector utility",
            content=content,
        )

        result = check_issue_already_implemented(
            issue_number=999,
            title="Fix `batch_mode_detector` symbol",
            body="",
            repo_root=tmp_path,
        )
        assert result is None, (
            "Pickaxe-only matches must NOT return MatchResult — docstring "
            "contract at already_done_detector.py:304-307 (Issue #1131)"
        )


class TestNoMatchReturnsNone:
    """AC4: returns None when no match found."""

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        """Empty repo or unrelated commits return None."""
        _git_init_with_commit(tmp_path, "chore: initial scaffold", content="# hello\n")

        result = check_issue_already_implemented(
            issue_number=12345,
            title="Add completely new feature xyz_abc_def_ghi",
            body="",
            repo_root=tmp_path,
        )

        assert result is None


class TestSymbolExtraction:
    """AC: _extract_symbols picks up backtick identifiers from issue title."""

    def test_backtick_identifiers_extracted(self) -> None:
        title = "Fix `batch_mode_detector` to handle edge cases"
        syms = _extract_symbols(title, "", max_count=5)
        assert "batch_mode_detector" in syms

    def test_multiple_backtick_symbols(self) -> None:
        title = "Update `foo_bar` and `baz_qux` functions"
        syms = _extract_symbols(title, "", max_count=5)
        assert "foo_bar" in syms
        assert "baz_qux" in syms

    def test_max_count_respected(self) -> None:
        title = "`a_b` `c_d` `e_f` `g_h` `i_j` `k_l` `m_n`"
        syms = _extract_symbols(title, "", max_count=3)
        assert len(syms) <= 3

    def test_path_symbols_extracted(self) -> None:
        title = "Add already_done_detector.py to the lib"
        syms = _extract_symbols(title, "", max_count=5)
        assert "already_done_detector.py" in syms


# ---------------------------------------------------------------------------
# Issue #1125: false-positive classification + stale-branch handling.
# ---------------------------------------------------------------------------


class TestAntiMarkers:
    """Anti-markers (Pending, Preflight-skipped) MUST NOT count as closures."""

    def test_anti_marker_pending_returns_none(self, tmp_path: Path) -> None:
        """Commit with 'Pending: #N' must not be treated as done."""
        _git_init_with_commit(
            tmp_path,
            "Merge batch: partial\n\nPending: #983.",
        )
        result = check_issue_already_implemented(
            issue_number=983,
            title="Some feature",
            body="",
            repo_root=tmp_path,
        )
        assert result is None, (
            "Pending: #983 must not be classified as already-done"
        )

    def test_anti_marker_preflight_skipped_returns_none(
        self, tmp_path: Path
    ) -> None:
        """Commit with 'Preflight-skipped: #N (reason)' must not match."""
        _git_init_with_commit(
            tmp_path,
            "Merge batch\n\nPreflight-skipped: #908 (stale branch with deferred ACs).",
        )
        result = check_issue_already_implemented(
            issue_number=908,
            title="Some feature",
            body="",
            repo_root=tmp_path,
        )
        assert result is None


class TestClosureMarkers:
    """Closure markers (Closes, Fixes, Completed) MUST match as done."""

    def test_closure_marker_closes_returns_match(self, tmp_path: Path) -> None:
        """'Closes #N' on a HEAD-ancestor commit returns classification 'closes'."""
        _git_init_with_commit(tmp_path, "feat: add thing\n\nCloses #500")
        result = check_issue_already_implemented(
            issue_number=500,
            title="Some feature",
            body="",
            repo_root=tmp_path,
        )
        assert result is not None
        assert isinstance(result, MatchResult)
        assert result.classification == "closes"

    def test_completed_comma_list_returns_closes(self, tmp_path: Path) -> None:
        """'Completed: #981, #982' returns 'closes' for either issue."""
        _git_init_with_commit(
            tmp_path,
            "Merge batch (partial)\n\nCompleted: #981, #982.",
        )
        result = check_issue_already_implemented(
            issue_number=981,
            title="x",
            body="",
            repo_root=tmp_path,
        )
        assert result is not None
        assert result.classification == "closes"


class TestStaleBranch:
    """Commits closing #N on an unmerged side branch must NOT match HEAD."""

    def test_stale_branch_downgrade_returns_none(self, tmp_path: Path) -> None:
        """A commit closing #N on a non-HEAD branch is downgraded to stale_branch."""
        # Build: main has one commit; a side branch has another commit that
        # closes #777. HEAD stays on main and never merges the side branch.
        _git_init_with_commit(tmp_path, "chore: initial")

        # Create the side branch and add a closing commit.
        subprocess.run(
            ["git", "-C", str(tmp_path), "checkout", "-b", "side"],
            check=True,
            capture_output=True,
        )
        side_file = tmp_path / "side.py"
        side_file.write_text("# side branch\n")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "side.py"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "feat: side\n\nCloses #777"],
            check=True,
            capture_output=True,
        )

        # Return HEAD to main — side commit is now NOT an ancestor of HEAD.
        subprocess.run(
            ["git", "-C", str(tmp_path), "checkout", "main"],
            check=True,
            capture_output=True,
        )

        result = check_issue_already_implemented(
            issue_number=777,
            title="x",
            body="",
            repo_root=tmp_path,
        )
        assert result is None, (
            "Closes #777 on an unmerged side branch must be downgraded to "
            "stale_branch and return None"
        )


class TestRealCommit41a3def:
    """Real-world regression: verbatim body of commit 41a3def from this repo.

    Pre-fix behavior: detector returned 41a3def for #983 because '#983' appeared
    in the commit body — but the body actually marked #983 as Pending.
    """

    def test_real_commit_41a3def_pending_983_returns_none(
        self, tmp_path: Path
    ) -> None:
        """#983 is in 'Pending: ...' — must return None."""
        _git_init_with_commit(tmp_path, COMMIT_41A3DEF_BODY)
        result = check_issue_already_implemented(
            issue_number=983,
            title="Some unrelated title",
            body="",
            repo_root=tmp_path,
        )
        assert result is None, "Pending #983 in 41a3def body must not match"

    def test_real_commit_41a3def_completed_981_returns_closes(
        self, tmp_path: Path
    ) -> None:
        """#981 is in 'Completed: #980, #981.' — must return 'closes'."""
        _git_init_with_commit(tmp_path, COMMIT_41A3DEF_BODY)
        result = check_issue_already_implemented(
            issue_number=981,
            title="Some unrelated title",
            body="",
            repo_root=tmp_path,
        )
        assert result is not None
        assert isinstance(result, MatchResult)
        assert result.classification == "closes"


class TestClassifyHelperUnit:
    """Direct unit coverage for _classify_issue_in_body (no git required)."""

    def test_classify_pending_marker(self) -> None:
        assert _classify_issue_in_body("Pending: #983.", 983) == "anti"

    def test_classify_preflight_skipped_marker(self) -> None:
        body = "Preflight-skipped: #908 (stale branch)."
        assert _classify_issue_in_body(body, 908) == "anti"

    def test_classify_closes_marker(self) -> None:
        assert _classify_issue_in_body("Closes #42", 42) == "closes"

    def test_classify_fixes_marker(self) -> None:
        assert _classify_issue_in_body("Fixes #42", 42) == "closes"

    def test_classify_completed_list(self) -> None:
        assert _classify_issue_in_body("Completed: #980, #981.", 981) == "closes"

    def test_classify_bare_mention(self) -> None:
        assert _classify_issue_in_body("See also #42 for context", 42) == "mention"

    def test_classify_not_referenced(self) -> None:
        assert _classify_issue_in_body("Unrelated body", 42) == "none"

    def test_classify_word_boundary_does_not_match_substring(self) -> None:
        """#1234 must not match a search for #123."""
        assert _classify_issue_in_body("Closes #1234", 123) == "none"

    def test_classify_real_41a3def_983_is_anti(self) -> None:
        assert _classify_issue_in_body(COMMIT_41A3DEF_BODY, 983) == "anti"

    def test_classify_real_41a3def_908_is_anti(self) -> None:
        assert _classify_issue_in_body(COMMIT_41A3DEF_BODY, 908) == "anti"

    def test_classify_real_41a3def_981_is_closes(self) -> None:
        assert _classify_issue_in_body(COMMIT_41A3DEF_BODY, 981) == "closes"
