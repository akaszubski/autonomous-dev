"""Regression tests for Issue #1488 — narrow the Issue #1408 diff-apply
protected-infra guard so it no longer false-positives on Bash commands where
the ``patch`` word and a protected directory name merely co-occur as
substrings (inside heredoc bodies, quoted grep patterns, comments, or prose).

The gate MUST still block real ``git apply`` / ``patch`` invocations that
reference a protected path (preserve original #1408 intent). It MUST NOT fire
on:
    - a ``cat <<'EOF' > /tmp/scratch`` heredoc whose BODY prose mentions
      ``patch`` and ``lib/``;
    - a ``grep -n 'patch' plugins/autonomous-dev/hooks/...`` read where the
      quoted pattern arg contains the trigger word;
    - an ``rg 'patch' plugins/autonomous-dev/lib/...`` read.

Issue: #1488 (fix for #1408 false-positives)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as upt  # noqa: E402


class TestIssue1488NoFalsePositive:
    """The narrowed #1408 guard must not fire on substring co-occurrence
    inside heredoc bodies, quoted patterns, or prose."""

    def test_heredoc_body_with_patch_word_not_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        cmd = (
            "cat <<'EOF' > /tmp/scratch_note.md\n"
            "This document describes how to patch a file in the lib/ directory.\n"
            "EOF"
        )
        result = upt._check_bash_infra_writes(cmd)
        assert result is None, f"expected no block, got: {result}"

    def test_grep_pattern_with_patch_word_not_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        cmd = 'grep -n "patch" plugins/autonomous-dev/hooks/unified_pre_tool.py'
        result = upt._check_bash_infra_writes(cmd)
        assert result is None, f"expected no block, got: {result}"

    def test_rg_pattern_with_patch_word_not_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        cmd = "rg 'git apply' plugins/autonomous-dev/lib/"
        result = upt._check_bash_infra_writes(cmd)
        assert result is None, f"expected no block, got: {result}"

    def test_single_quoted_patch_arg_not_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        cmd = "echo 'patch the lib/ directory'"
        result = upt._check_bash_infra_writes(cmd)
        assert result is None, f"expected no block, got: {result}"


class TestIssue1488PreservesOriginal1408Intent:
    """Actual git apply / patch invocations targeting protected paths must
    still be blocked — Issue #1488 narrowing MUST NOT weaken #1408's real
    protection."""

    def test_real_patch_invocation_to_lib_still_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        result = upt._check_bash_infra_writes(
            "patch lib/pipeline_state.py < p.diff"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_real_git_apply_to_hooks_still_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        # Comment retained — Issue #1408's existing test also relies on the
        # unstripped comment segment ("# touches hooks/...").
        result = upt._check_bash_infra_writes(
            "git apply < /tmp/patch.diff  # touches hooks/unified_pre_tool.py"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_real_patch_after_pipe_still_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Command-start position anchor must recognise ``|`` as a separator
        so ``echo x | patch lib/foo.py`` still blocks."""
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        result = upt._check_bash_infra_writes(
            "echo x | patch lib/pipeline_state.py"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_real_git_apply_after_semicolon_still_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Command-start anchor must recognise ``;`` as a separator."""
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        result = upt._check_bash_infra_writes(
            "cd /tmp; git apply /tmp/x.diff  # hooks/"
        )
        assert result is not None
        assert "BLOCKED" in result[1]
