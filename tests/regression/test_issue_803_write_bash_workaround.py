"""Regression tests for Issue #803 — Write-to-Bash heredoc workaround detection.

When Write/Edit to a protected file is denied, agents may retry via Bash
heredoc or redirect. The deny cache must catch this cross-tool workaround.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import from unified_pre_tool
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "hooks"),
)
import unified_pre_tool


class TestWriteDeniedThenBashHeredocBlocked:
    """Write to protected file denied, then Bash heredoc to same file detected."""

    def test_write_denied_then_bash_heredoc_same_file_blocked(self, tmp_path):
        """Deny cache records Write denial; Bash heredoc to same file is caught."""
        cache_file = tmp_path / "deny_cache.jsonl"
        test_path = "/Users/dev/project/plugins/autonomous-dev/agents/implementer.md"

        with patch.object(unified_pre_tool, "DENY_CACHE_PATH", str(cache_file)):
            # Simulate Write denial by recording in deny cache
            unified_pre_tool._update_deny_cache(test_path)

            # Verify deny cache catches the same path
            assert unified_pre_tool._check_deny_cache(test_path) is True

    def test_write_denied_then_bash_redirect_same_file_blocked(self, tmp_path):
        """Deny cache records Write denial; redirect to same file is detected."""
        cache_file = tmp_path / "deny_cache.jsonl"
        test_path = "/Users/dev/project/plugins/autonomous-dev/hooks/my_hook.py"

        with patch.object(unified_pre_tool, "DENY_CACHE_PATH", str(cache_file)):
            unified_pre_tool._update_deny_cache(test_path)

            # Verify _extract_bash_file_writes detects the redirect
            command = f'echo "content" > {test_path}'
            targets = unified_pre_tool._extract_bash_file_writes(command)
            assert test_path in targets

            # Verify deny cache catches it
            assert unified_pre_tool._check_deny_cache(test_path) is True


class TestWriteDeniedThenGitCheckoutBlocked:
    """Issue #1408: denied Write/Edit, then `git checkout` to same path.

    git checkout overwrites working-tree files from a ref — a write vector the
    pre-#1408 #803 union (redirect/tee/cp/mv/python) did not cover. The
    extractor must surface the checkout target so the deny cache still matches.
    """

    def test_write_denied_then_git_checkout_same_file_blocked(self, tmp_path):
        cache_file = tmp_path / "deny_cache.jsonl"
        test_path = "plugins/autonomous-dev/lib/pipeline_state.py"

        with patch.object(unified_pre_tool, "DENY_CACHE_PATH", str(cache_file)):
            unified_pre_tool._update_deny_cache(test_path)

            # The git-checkout extractor surfaces the same path (feeds the #803
            # union at the wired call site).
            targets = unified_pre_tool._extract_git_checkout_targets(
                f"git checkout -- {test_path}"
            )
            assert test_path in targets

            # Deny cache still catches the same path via the union.
            assert unified_pre_tool._check_deny_cache(test_path) is True


class TestWriteDeniedDifferentFileAllowed:
    """Write denied to file A, Bash to file B should not be blocked."""

    def test_write_denied_then_different_file_allowed(self, tmp_path):
        """Deny cache for file A does not match file B."""
        cache_file = tmp_path / "deny_cache.jsonl"
        path_a = "/Users/dev/project/plugins/autonomous-dev/agents/implementer.md"
        path_b = "/tmp/test_output.txt"

        with patch.object(unified_pre_tool, "DENY_CACHE_PATH", str(cache_file)):
            unified_pre_tool._update_deny_cache(path_a)
            assert unified_pre_tool._check_deny_cache(path_b) is False


class TestBashHeredocToNonDeniedFileAllowed:
    """Bash heredoc to a file with no prior Write denial is allowed."""

    def test_bash_heredoc_to_non_denied_file_allowed(self, tmp_path):
        """No deny cache entry means _check_deny_cache returns False."""
        cache_file = tmp_path / "deny_cache.jsonl"
        test_path = "/tmp/output.txt"

        with patch.object(unified_pre_tool, "DENY_CACHE_PATH", str(cache_file)):
            assert unified_pre_tool._check_deny_cache(test_path) is False


class TestDenyCacheExpiry:
    """Deny cache entries expire after the time window."""

    def test_deny_cache_expiry_allows_after_timeout(self, tmp_path):
        """Entries older than window_seconds should not match."""
        cache_file = tmp_path / "deny_cache.jsonl"
        test_path = "/Users/dev/project/plugins/autonomous-dev/agents/foo.md"

        # Write entry with old timestamp (70 seconds ago)
        old_entry = {"path": test_path, "timestamp": time.time() - 70}
        cache_file.write_text(json.dumps(old_entry) + "\n")

        with patch.object(unified_pre_tool, "DENY_CACHE_PATH", str(cache_file)):
            # Default window is 60s, so 70s ago should be expired
            assert unified_pre_tool._check_deny_cache(test_path) is False


class TestDenyCachePathNormalization:
    """Write denied with absolute path, check with relative path via basename."""

    def test_deny_cache_path_normalization_basename_match(self, tmp_path):
        """Basename matching catches cross-tool path format differences."""
        cache_file = tmp_path / "deny_cache.jsonl"
        abs_path = "/Users/dev/project/plugins/autonomous-dev/agents/implementer.md"
        rel_path = "agents/implementer.md"

        with patch.object(unified_pre_tool, "DENY_CACHE_PATH", str(cache_file)):
            unified_pre_tool._update_deny_cache(abs_path)
            # Basename of both paths is "implementer.md" — should match
            assert unified_pre_tool._check_deny_cache(rel_path) is True
