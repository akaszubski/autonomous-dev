#!/usr/bin/env python3
"""
Unit tests for batch_orchestrator.py (Issue #203).

Tests for unified /implement command orchestration with:
- Flag parsing (--quick, --batch, --issues, --resume)
- Auto-worktree creation for batch modes
- Mode detection and routing

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (no implementation exists yet).

Coverage Target: 95%+ for batch_orchestrator module
Security: CWE-22 (path traversal), CWE-78 (command injection)

Date: 2026-01-10
Issue: GitHub #203 (Consolidate commands)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Optional

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root with .git directory."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    git_dir = project_root / ".git"
    git_dir.mkdir()
    return project_root


@pytest.fixture
def temp_features_file(tmp_path):
    """Create temporary features file."""
    features_file = tmp_path / "features.txt"
    features_file.write_text("""# Authentication features
Add user login with JWT
Add password reset flow

# API features
Add rate limiting to endpoints
""")
    return features_file


# =============================================================================
# SECTION 1: Flag Parsing Tests (10 tests)
# =============================================================================

class TestFlagParsing:
    """Test command-line flag parsing for unified /implement command."""

    def test_parse_no_flags_returns_full_pipeline_mode(self):
        """Verify default mode is full pipeline when no flags provided."""
        try:
            from batch_orchestrator import parse_implement_flags
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["add user authentication"]
        result = parse_implement_flags(args)

        assert result["mode"] == "full_pipeline"
        assert result["feature"] == "add user authentication"
        assert result["quick"] is False
        assert result["batch_file"] is None
        assert result["issues"] is None
        assert result["resume_id"] is None

    def test_parse_quick_flag(self):
        """Verify --quick flag sets quick mode."""
        try:
            from batch_orchestrator import parse_implement_flags
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["--quick", "fix typo in readme"]
        result = parse_implement_flags(args)

        assert result["mode"] == "quick"
        assert result["feature"] == "fix typo in readme"
        assert result["quick"] is True

    def test_parse_batch_flag_with_file(self):
        """Verify --batch flag with file path sets batch file mode."""
        try:
            from batch_orchestrator import parse_implement_flags
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["--batch", "features.txt"]
        result = parse_implement_flags(args)

        assert result["mode"] == "batch_file"
        assert result["batch_file"] == "features.txt"
        assert result["feature"] is None

    def test_parse_issues_flag_with_numbers(self):
        """Verify --issues flag with issue numbers sets batch issues mode."""
        try:
            from batch_orchestrator import parse_implement_flags
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["--issues", "72", "73", "74"]
        result = parse_implement_flags(args)

        assert result["mode"] == "batch_issues"
        assert result["issues"] == [72, 73, 74]
        assert result["feature"] is None

    def test_parse_resume_flag_with_batch_id(self):
        """Verify --resume flag with batch ID sets resume mode."""
        try:
            from batch_orchestrator import parse_implement_flags
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["--resume", "batch-20260110-123456"]
        result = parse_implement_flags(args)

        assert result["mode"] == "resume"
        assert result["resume_id"] == "batch-20260110-123456"
        assert result["feature"] is None

    def test_parse_conflicting_flags_raises_error(self):
        """Verify conflicting flags (--quick + --batch) raise error."""
        try:
            from batch_orchestrator import parse_implement_flags, FlagConflictError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["--quick", "--batch", "features.txt"]

        with pytest.raises(FlagConflictError) as exc_info:
            parse_implement_flags(args)

        assert "Cannot use --quick with batch mode" in str(exc_info.value)

    def test_parse_empty_args_raises_error(self):
        """Verify empty arguments raise helpful error."""
        try:
            from batch_orchestrator import parse_implement_flags, MissingArgumentError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = []

        with pytest.raises(MissingArgumentError) as exc_info:
            parse_implement_flags(args)

        assert "feature description" in str(exc_info.value).lower()

    def test_parse_batch_without_file_raises_error(self):
        """Verify --batch without file path raises error."""
        try:
            from batch_orchestrator import parse_implement_flags, MissingArgumentError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["--batch"]

        with pytest.raises(MissingArgumentError) as exc_info:
            parse_implement_flags(args)

        assert "file path" in str(exc_info.value).lower()

    def test_parse_issues_without_numbers_raises_error(self):
        """Verify --issues without issue numbers raises error."""
        try:
            from batch_orchestrator import parse_implement_flags, MissingArgumentError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["--issues"]

        with pytest.raises(MissingArgumentError) as exc_info:
            parse_implement_flags(args)

        assert "issue number" in str(exc_info.value).lower()

    def test_parse_issues_with_invalid_numbers_raises_error(self):
        """Verify --issues with non-integer values raises error."""
        try:
            from batch_orchestrator import parse_implement_flags, InvalidArgumentError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        args = ["--issues", "72", "abc", "74"]

        with pytest.raises(InvalidArgumentError) as exc_info:
            parse_implement_flags(args)

        assert "invalid issue number" in str(exc_info.value).lower()


# =============================================================================
# SECTION 2: Auto-Worktree Creation Tests (8 tests)
# =============================================================================

class TestAutoWorktreeCreation:
    """Test auto-worktree creation for batch modes."""

    def test_batch_mode_creates_worktree(self, temp_project_root, monkeypatch):
        """Verify batch mode creates worktree automatically."""
        try:
            from batch_orchestrator import create_batch_worktree
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_project_root)
        batch_id = "batch-20260110-143022"

        # Mock worktree_manager via lazy import function
        mock_wm = MagicMock()
        mock_wm.create_worktree.return_value = {
            "success": True,
            "path": str(temp_project_root / ".worktrees" / batch_id),
        }

        with patch("batch_orchestrator._get_worktree_manager", return_value=mock_wm):
            result = create_batch_worktree(batch_id)

            assert result["success"] is True
            assert batch_id in result["path"]
            mock_wm.create_worktree.assert_called_once()

    def test_batch_worktree_path_format(self, temp_project_root, monkeypatch):
        """Verify worktree path follows .worktrees/{batch-id}/ format."""
        try:
            from batch_orchestrator import get_batch_worktree_path
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_project_root)
        batch_id = "batch-20260110-143022"

        path = get_batch_worktree_path(batch_id)

        assert path == temp_project_root / ".worktrees" / batch_id

    def test_batch_worktree_collision_appends_timestamp(self, temp_project_root, monkeypatch):
        """Verify batch-id collision appends timestamp to avoid conflict."""
        try:
            from batch_orchestrator import create_batch_worktree
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_project_root)
        batch_id = "batch-20260110-143022"

        # Create existing worktree directory
        existing_path = temp_project_root / ".worktrees" / batch_id
        existing_path.mkdir(parents=True)

        mock_wm = MagicMock()
        mock_wm.create_worktree.return_value = {"success": True, "path": ""}

        with patch("batch_orchestrator._get_worktree_manager", return_value=mock_wm):
            result = create_batch_worktree(batch_id)

            # Should have appended timestamp to avoid collision
            # The batch_id in result should be different from original
            assert result["batch_id"] != batch_id

    def test_batch_worktree_failure_graceful_fallback(self, temp_project_root, monkeypatch):
        """Verify graceful fallback when worktree creation fails."""
        try:
            from batch_orchestrator import create_batch_worktree
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_project_root)
        batch_id = "batch-20260110-143022"

        mock_wm = MagicMock()
        mock_wm.create_worktree.return_value = {
            "success": False,
            "error": "Disk full",
        }

        with patch("batch_orchestrator._get_worktree_manager", return_value=mock_wm):
            result = create_batch_worktree(batch_id)

            # Should return fallback info, not raise
            assert result["success"] is False
            assert result["fallback"] is True
            assert "warning" in result

    def test_batch_mode_uses_worktree_state_file(self, temp_project_root, monkeypatch):
        """Verify batch mode uses per-worktree state file."""
        try:
            from batch_orchestrator import get_batch_state_path_for_worktree
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_project_root)
        worktree_path = temp_project_root / ".worktrees" / "batch-123"

        state_path = get_batch_state_path_for_worktree(worktree_path)

        # Should be in worktree's .claude/ directory
        assert state_path == worktree_path / ".claude" / "batch_state.json"

    def test_issues_mode_creates_worktree(self, temp_project_root, monkeypatch):
        """Verify --issues mode creates worktree automatically."""
        try:
            from batch_orchestrator import start_batch_issues_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_project_root)
        issues = [72, 73, 74]

        with patch("batch_orchestrator.create_batch_worktree") as mock_create:
            mock_create.return_value = {
                "success": True,
                "path": "/tmp/worktree",
                "batch_id": "batch-issues-72-73-74-20260110",
                "fallback": False,
            }
            with patch("batch_orchestrator.fetch_issue_titles") as mock_fetch:
                mock_fetch.return_value = ["Add feature A", "Fix bug B", "Update docs C"]

                result = start_batch_issues_mode(issues)

                mock_create.assert_called_once()
                assert result["worktree_created"] is True

    def test_resume_mode_finds_correct_worktree(self, temp_project_root, monkeypatch):
        """Verify --resume finds the correct worktree for batch-id."""
        try:
            from batch_orchestrator import find_batch_worktree
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_project_root)
        batch_id = "batch-20260110-143022"

        # Create worktree directory with state file
        worktree_path = temp_project_root / ".worktrees" / batch_id
        worktree_path.mkdir(parents=True)
        state_dir = worktree_path / ".claude"
        state_dir.mkdir()
        state_file = state_dir / "batch_state.json"
        state_file.write_text(json.dumps({"batch_id": batch_id, "status": "in_progress"}))

        result = find_batch_worktree(batch_id)

        assert result["found"] is True
        assert result["path"] == worktree_path

    def test_resume_mode_not_found_raises_error(self, temp_project_root, monkeypatch):
        """Verify --resume raises error when batch-id not found."""
        try:
            from batch_orchestrator import find_batch_worktree, BatchNotFoundError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_project_root)
        batch_id = "batch-nonexistent"

        with pytest.raises(BatchNotFoundError) as exc_info:
            find_batch_worktree(batch_id)

        assert batch_id in str(exc_info.value)


# =============================================================================
# SECTION 3: Mode Routing Tests (5 tests)
# =============================================================================

class TestModeRouting:
    """Test mode detection and routing logic."""

    def test_route_to_full_pipeline(self):
        """Verify default routing goes to full pipeline."""
        try:
            from batch_orchestrator import route_implement_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        flags = {
            "mode": "full_pipeline",
            "feature": "add user auth",
            "quick": False,
            "batch_file": None,
            "issues": None,
            "resume_id": None,
        }

        with patch("batch_orchestrator.run_full_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {"success": True}

            result = route_implement_mode(flags)

            mock_pipeline.assert_called_once_with("add user auth")
            assert result["success"] is True

    def test_route_to_quick_mode(self):
        """Verify --quick routes to implementer-only mode."""
        try:
            from batch_orchestrator import route_implement_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        flags = {
            "mode": "quick",
            "feature": "fix typo",
            "quick": True,
            "batch_file": None,
            "issues": None,
            "resume_id": None,
        }

        with patch("batch_orchestrator.run_quick_mode") as mock_quick:
            mock_quick.return_value = {"success": True}

            result = route_implement_mode(flags)

            mock_quick.assert_called_once_with("fix typo")
            assert result["success"] is True

    def test_route_to_batch_file_mode(self):
        """Verify --batch routes to batch file mode with auto-worktree."""
        try:
            from batch_orchestrator import route_implement_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        flags = {
            "mode": "batch_file",
            "feature": None,
            "quick": False,
            "batch_file": "features.txt",
            "issues": None,
            "resume_id": None,
        }

        with patch("batch_orchestrator.run_batch_file_mode") as mock_batch:
            mock_batch.return_value = {"success": True, "worktree_created": True}

            result = route_implement_mode(flags)

            mock_batch.assert_called_once_with("features.txt")
            assert result["success"] is True

    def test_route_to_batch_issues_mode(self):
        """Verify --issues routes to batch issues mode with auto-worktree."""
        try:
            from batch_orchestrator import route_implement_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        flags = {
            "mode": "batch_issues",
            "feature": None,
            "quick": False,
            "batch_file": None,
            "issues": [72, 73, 74],
            "resume_id": None,
        }

        with patch("batch_orchestrator.run_batch_issues_mode") as mock_issues:
            mock_issues.return_value = {"success": True, "worktree_created": True}

            result = route_implement_mode(flags)

            mock_issues.assert_called_once_with([72, 73, 74])
            assert result["success"] is True

    def test_route_to_resume_mode(self):
        """Verify --resume routes to resume mode."""
        try:
            from batch_orchestrator import route_implement_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        flags = {
            "mode": "resume",
            "feature": None,
            "quick": False,
            "batch_file": None,
            "issues": None,
            "resume_id": "batch-20260110-143022",
        }

        with patch("batch_orchestrator.run_resume_mode") as mock_resume:
            mock_resume.return_value = {"success": True}

            result = route_implement_mode(flags)

            mock_resume.assert_called_once_with("batch-20260110-143022")
            assert result["success"] is True


# =============================================================================
# SECTION 4: Security Validation Tests (5 tests)
# =============================================================================

class TestSecurityValidation:
    """Test security validations for batch orchestrator."""

    def test_batch_id_rejects_path_traversal(self):
        """Verify batch-id with path traversal is rejected (CWE-22)."""
        try:
            from batch_orchestrator import validate_batch_id, SecurityError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        malicious_ids = [
            "../../../etc/passwd",
            "batch-../secret",
            "batch/../../root",
            "..\\..\\windows",
        ]

        for batch_id in malicious_ids:
            with pytest.raises(SecurityError) as exc_info:
                validate_batch_id(batch_id)

            assert "path traversal" in str(exc_info.value).lower()

    def test_batch_id_rejects_command_injection(self):
        """Verify batch-id with shell metacharacters is rejected (CWE-78)."""
        try:
            from batch_orchestrator import validate_batch_id, SecurityError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        malicious_ids = [
            "batch-$(whoami)",
            "batch-`rm -rf /`",
            "batch-; cat /etc/passwd",
            "batch-| ls -la",
        ]

        for batch_id in malicious_ids:
            with pytest.raises(SecurityError) as exc_info:
                validate_batch_id(batch_id)

            assert "invalid character" in str(exc_info.value).lower()

    def test_batch_id_allows_valid_characters(self):
        """Verify valid batch-id characters are allowed."""
        try:
            from batch_orchestrator import validate_batch_id
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        valid_ids = [
            "batch-20260110-143022",
            "batch_feature_auth",
            "batch-issue-72-73-74",
            "BATCH-UPPERCASE",
            "batch123",
        ]

        for batch_id in valid_ids:
            # Should not raise
            result = validate_batch_id(batch_id)
            assert result is True

    def test_features_file_path_validated(self):
        """Verify features file path is validated for traversal."""
        try:
            from batch_orchestrator import validate_features_file, SecurityError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        malicious_paths = [
            "../../../etc/passwd",
            "/etc/shadow",
            "features/../../../secret.txt",
        ]

        for path in malicious_paths:
            with pytest.raises(SecurityError):
                validate_features_file(path)

    def test_issue_numbers_validated_range(self):
        """Verify issue numbers are validated for reasonable range."""
        try:
            from batch_orchestrator import validate_issue_numbers, InvalidArgumentError
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        # Too many issues
        with pytest.raises(InvalidArgumentError) as exc_info:
            validate_issue_numbers(list(range(1, 200)))  # 199 issues

        assert "too many" in str(exc_info.value).lower() or "max" in str(exc_info.value).lower()

        # Negative issue number
        with pytest.raises(InvalidArgumentError):
            validate_issue_numbers([-1, 72, 73])

        # Zero issue number
        with pytest.raises(InvalidArgumentError):
            validate_issue_numbers([0, 72, 73])


# =============================================================================
# SECTION 5: Deprecation Shim Tests (4 tests)
# =============================================================================

class TestDeprecationShims:
    """Test deprecation shim behavior for old commands."""

    def test_auto_implement_shim_shows_deprecation_notice(self):
        """Verify /auto-implement shim shows deprecation notice."""
        try:
            from batch_orchestrator import get_deprecation_notice
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        notice = get_deprecation_notice("auto-implement")

        assert "deprecated" in notice.lower()
        assert "/implement" in notice
        assert "full pipeline" in notice.lower() or "default" in notice.lower()

    def test_batch_implement_shim_shows_deprecation_notice(self):
        """Verify /batch-implement shim shows deprecation notice."""
        try:
            from batch_orchestrator import get_deprecation_notice
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        notice = get_deprecation_notice("batch-implement")

        assert "deprecated" in notice.lower()
        assert "/implement" in notice
        assert "--batch" in notice or "--issues" in notice

    def test_auto_implement_args_converted_correctly(self):
        """Verify /auto-implement args converted to /implement args."""
        try:
            from batch_orchestrator import convert_legacy_args
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        # Old: /auto-implement "add auth"
        # New: /implement "add auth" (full pipeline is default)
        old_args = ["add auth"]
        new_args = convert_legacy_args("auto-implement", old_args)

        assert new_args == ["add auth"]  # Same args, different command name

    def test_batch_implement_args_converted_correctly(self):
        """Verify /batch-implement args converted to /implement args."""
        try:
            from batch_orchestrator import convert_legacy_args
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        # Old: /batch-implement features.txt
        # New: /implement --batch features.txt
        old_args = ["features.txt"]
        new_args = convert_legacy_args("batch-implement", old_args)
        assert new_args == ["--batch", "features.txt"]

        # Old: /batch-implement --issues 72 73
        # New: /implement --issues 72 73
        old_args = ["--issues", "72", "73"]
        new_args = convert_legacy_args("batch-implement", old_args)
        assert new_args == ["--issues", "72", "73"]

        # Old: /batch-implement --resume batch-123
        # New: /implement --resume batch-123
        old_args = ["--resume", "batch-123"]
        new_args = convert_legacy_args("batch-implement", old_args)
        assert new_args == ["--resume", "batch-123"]


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (32 unit tests for Issue #203):

SECTION 1: Flag Parsing (10 tests)
- test_parse_no_flags_returns_full_pipeline_mode
- test_parse_quick_flag
- test_parse_batch_flag_with_file
- test_parse_issues_flag_with_numbers
- test_parse_resume_flag_with_batch_id
- test_parse_conflicting_flags_raises_error
- test_parse_empty_args_raises_error
- test_parse_batch_without_file_raises_error
- test_parse_issues_without_numbers_raises_error
- test_parse_issues_with_invalid_numbers_raises_error

SECTION 2: Auto-Worktree Creation (8 tests)
- test_batch_mode_creates_worktree
- test_batch_worktree_path_format
- test_batch_worktree_collision_appends_timestamp
- test_batch_worktree_failure_graceful_fallback
- test_batch_mode_uses_worktree_state_file
- test_issues_mode_creates_worktree
- test_resume_mode_finds_correct_worktree
- test_resume_mode_not_found_raises_error

SECTION 3: Mode Routing (5 tests)
- test_route_to_full_pipeline
- test_route_to_quick_mode
- test_route_to_batch_file_mode
- test_route_to_batch_issues_mode
- test_route_to_resume_mode

SECTION 4: Security Validation (5 tests)
- test_batch_id_rejects_path_traversal
- test_batch_id_rejects_command_injection
- test_batch_id_allows_valid_characters
- test_features_file_path_validated
- test_issue_numbers_validated_range

SECTION 5: Deprecation Shims (4 tests)
- test_auto_implement_shim_shows_deprecation_notice
- test_batch_implement_shim_shows_deprecation_notice
- test_auto_implement_args_converted_correctly
- test_batch_implement_args_converted_correctly

TOTAL: 32 unit tests (all FAILING - TDD red phase)

Coverage Target: 95%+ for batch_orchestrator module
Security: CWE-22 (path traversal), CWE-78 (command injection)
"""


# =============================================================================
# SECTION 6: Batch Auto-Approve Tests (Issue #323)
# =============================================================================

class TestBatchAutoApprove:
    """Test batch auto-approval for permission prompts (Issue #323)."""

    def test_enable_batch_auto_approve_sets_env_var(self):
        """Test that enable_batch_auto_approve sets BATCH_AUTO_APPROVE env var."""
        from batch_orchestrator import enable_batch_auto_approve, disable_batch_auto_approve

        # Clean up any existing value
        if 'BATCH_AUTO_APPROVE' in os.environ:
            del os.environ['BATCH_AUTO_APPROVE']
        if 'MCP_AUTO_APPROVE' in os.environ:
            del os.environ['MCP_AUTO_APPROVE']

        try:
            result = enable_batch_auto_approve()
            assert result is True
            assert os.environ.get('BATCH_AUTO_APPROVE') == 'true'
        finally:
            disable_batch_auto_approve()

    def test_enable_batch_auto_approve_respects_mcp_auto_approve_true(self):
        """Test that enable_batch_auto_approve respects MCP_AUTO_APPROVE=true."""
        from batch_orchestrator import enable_batch_auto_approve, disable_batch_auto_approve

        # Clean up
        if 'BATCH_AUTO_APPROVE' in os.environ:
            del os.environ['BATCH_AUTO_APPROVE']

        os.environ['MCP_AUTO_APPROVE'] = 'true'
        try:
            result = enable_batch_auto_approve()
            assert result is True
            assert os.environ.get('BATCH_AUTO_APPROVE') == 'true'
        finally:
            disable_batch_auto_approve()
            del os.environ['MCP_AUTO_APPROVE']

    def test_enable_batch_auto_approve_respects_mcp_auto_approve_false(self):
        """Test that enable_batch_auto_approve respects MCP_AUTO_APPROVE=false."""
        from batch_orchestrator import enable_batch_auto_approve, disable_batch_auto_approve

        # Clean up
        if 'BATCH_AUTO_APPROVE' in os.environ:
            del os.environ['BATCH_AUTO_APPROVE']

        os.environ['MCP_AUTO_APPROVE'] = 'false'
        try:
            result = enable_batch_auto_approve()
            assert result is False
            assert os.environ.get('BATCH_AUTO_APPROVE') is None
        finally:
            if 'BATCH_AUTO_APPROVE' in os.environ:
                disable_batch_auto_approve()
            del os.environ['MCP_AUTO_APPROVE']

    def test_enable_batch_auto_approve_respects_existing_batch_env(self):
        """Test that existing BATCH_AUTO_APPROVE env var is respected."""
        from batch_orchestrator import enable_batch_auto_approve

        os.environ['BATCH_AUTO_APPROVE'] = 'false'
        try:
            result = enable_batch_auto_approve()
            assert result is False
        finally:
            del os.environ['BATCH_AUTO_APPROVE']

    def test_disable_batch_auto_approve_removes_env_var(self):
        """Test that disable_batch_auto_approve removes env var."""
        from batch_orchestrator import disable_batch_auto_approve

        os.environ['BATCH_AUTO_APPROVE'] = 'true'
        disable_batch_auto_approve()
        assert 'BATCH_AUTO_APPROVE' not in os.environ

    @patch('batch_orchestrator.create_batch_worktree')
    @patch('batch_orchestrator.validate_features_file')
    def test_run_batch_file_mode_enables_auto_approve(self, mock_validate, mock_worktree):
        """Test that run_batch_file_mode enables batch auto-approve."""
        from batch_orchestrator import run_batch_file_mode, disable_batch_auto_approve

        mock_worktree.return_value = {
            'success': True,
            'batch_id': 'batch-123',
            'path': '/tmp/worktree'
        }

        # Clean up
        if 'BATCH_AUTO_APPROVE' in os.environ:
            del os.environ['BATCH_AUTO_APPROVE']
        if 'MCP_AUTO_APPROVE' in os.environ:
            del os.environ['MCP_AUTO_APPROVE']

        try:
            result = run_batch_file_mode('/tmp/features.txt')
            assert 'batch_auto_approve' in result
            assert result['batch_auto_approve'] is True
        finally:
            disable_batch_auto_approve()

    @patch('batch_orchestrator.create_batch_worktree')
    @patch('batch_orchestrator.validate_issue_numbers')
    @patch('batch_orchestrator.fetch_issue_titles')
    def test_run_batch_issues_mode_enables_auto_approve(
        self, mock_fetch, mock_validate, mock_worktree
    ):
        """Test that run_batch_issues_mode enables batch auto-approve."""
        from batch_orchestrator import run_batch_issues_mode, disable_batch_auto_approve

        mock_worktree.return_value = {
            'success': True,
            'batch_id': 'batch-issues-1-2-3',
            'path': '/tmp/worktree'
        }
        mock_fetch.return_value = ['Feature 1', 'Feature 2', 'Feature 3']

        # Clean up
        if 'BATCH_AUTO_APPROVE' in os.environ:
            del os.environ['BATCH_AUTO_APPROVE']
        if 'MCP_AUTO_APPROVE' in os.environ:
            del os.environ['MCP_AUTO_APPROVE']

        try:
            result = run_batch_issues_mode([1, 2, 3])
            assert 'batch_auto_approve' in result
            assert result['batch_auto_approve'] is True
        finally:
            disable_batch_auto_approve()
