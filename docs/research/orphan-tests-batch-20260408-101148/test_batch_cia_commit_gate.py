"""Unit tests for batch CIA commit gate in unified_pre_tool.py.

Tests the hook-level enforcement that blocks git commit in batch worktrees
when issues are missing continuous-improvement-analyst completion.

Issue: #712
"""

import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"


def _load_hook_module():
    """Load unified_pre_tool as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("unified_pre_tool", str(HOOK_PATH))
    mod = importlib.util.module_from_spec(spec)
    # Patch sys.stdin to avoid reading from stdin during import
    import io
    import sys
    old_stdin = sys.stdin
    sys.stdin = io.StringIO('{}')
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdin = old_stdin
    return mod


@pytest.fixture(scope="module")
def hook_mod():
    """Load the hook module once for all tests."""
    return _load_hook_module()


class TestCheckBatchCIACompletions:
    """Tests for _check_batch_cia_completions helper."""

    def test_function_exists(self, hook_mod) -> None:
        """The _check_batch_cia_completions function exists in the hook."""
        assert hasattr(hook_mod, "_check_batch_cia_completions")
        assert callable(hook_mod._check_batch_cia_completions)

    def test_returns_none_when_all_passed(self, hook_mod) -> None:
        """Returns None (no block) when all issues have CIA."""
        mock_mod = MagicMock()
        mock_mod.verify_batch_cia_completions.return_value = (True, [100, 101], [])

        with patch.object(hook_mod.importlib.util, "spec_from_file_location") as mock_spec_fn:
            mock_spec = MagicMock()
            mock_spec_fn.return_value = mock_spec
            mock_spec.loader.exec_module = lambda m: m.__dict__.update(
                verify_batch_cia_completions=mock_mod.verify_batch_cia_completions
            )

            result = hook_mod._check_batch_cia_completions("test-session")

        # Should return None (allow)
        assert result is None

    def test_returns_block_reason_when_missing(self, hook_mod) -> None:
        """Returns a block reason string when issues are missing CIA."""
        mock_mod = MagicMock()
        mock_mod.verify_batch_cia_completions.return_value = (False, [100], [101, 102])

        with patch.object(hook_mod.importlib.util, "spec_from_file_location") as mock_spec_fn:
            mock_spec = MagicMock()
            mock_spec_fn.return_value = mock_spec
            mock_spec.loader.exec_module = lambda m: m.__dict__.update(
                verify_batch_cia_completions=mock_mod.verify_batch_cia_completions
            )

            result = hook_mod._check_batch_cia_completions("test-session")

        assert result is not None
        assert "BLOCKED" in result
        assert "#101" in result
        assert "#102" in result
        assert "712" in result

    def test_returns_none_on_import_error(self, hook_mod) -> None:
        """Returns None (fail-open) when module cannot be loaded."""
        with patch.object(hook_mod.importlib.util, "spec_from_file_location", side_effect=Exception("import error")):
            result = hook_mod._check_batch_cia_completions("test-session")
        assert result is None

    def test_returns_none_when_no_lib_found(self, hook_mod) -> None:
        """Returns None when the lib file does not exist."""
        with patch.object(hook_mod.Path, "__new__", side_effect=Exception("no path")):
            result = hook_mod._check_batch_cia_completions("test-session")
        # Should fail-open
        assert result is None

    def test_hook_references_batch_cia(self) -> None:
        """The hook source code references the batch CIA gate."""
        content = HOOK_PATH.read_text()
        assert "_check_batch_cia_completions" in content
        assert "batch-" in content.lower() or ".worktrees/batch-" in content

    def test_hook_has_git_commit_detection(self) -> None:
        """The hook source code detects git commit commands."""
        content = HOOK_PATH.read_text()
        assert "git commit" in content

    def test_hook_has_skip_env_var(self) -> None:
        """The hook checks SKIP_BATCH_CIA_GATE env var."""
        content = HOOK_PATH.read_text()
        assert "SKIP_BATCH_CIA_GATE" in content
