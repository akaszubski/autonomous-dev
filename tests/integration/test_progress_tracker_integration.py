"""
Integration tests for project-progress-tracker agent integration with /auto-implement pipeline

Tests cover:
- project-progress-tracker invoked after doc-master in pipeline
- Progress tracker updates PROJECT.md Stage status
- Progress tracker updates Issue references
- Progress tracker updates Last Updated timestamp
- Graceful degradation if progress tracker fails
- Integration with doc-master auto-apply workflow
- Batch mode behavior (no blocking)
- Pipeline flow: doc-master → project-progress-tracker

This is the RED phase of TDD - tests should fail initially since implementation doesn't exist yet.

Date: 2026-01-09
Issue: #204
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import hashlib
import json
import os
import sys
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from typing import Dict, Any, List, Optional, Sequence

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - integration module doesn't exist yet (TDD!)
try:
    from auto_implement_pipeline import (
        execute_step8_parallel_validation,
        invoke_progress_tracker,
        ProgressTrackerResult,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# ============================================================================
# Live-repo isolation + digest tripwire (Issue #1821)
# ============================================================================
#
# ``invoke_progress_tracker()`` is a REAL file writer. ``_find_project_md()``
# resolves its target against the PROCESS WORKING DIRECTORY: ``.claude/PROJECT.md``
# first (skipped when it is a symlink, which it is here) then ``PROJECT.md``. Under
# pytest the cwd is the live repo root, so any test reaching the tracker rewrote the
# tracked ``PROJECT.md`` -- the alignment gate's own input -- and still reported PASS.
#
# Per-test mocking was the failed control: it names the I/O API rather than the path
# resolution, it is opt-in, and enumerating the writer tests UNDER-COUNTED TWICE.
# The census is treated as incomplete. Both controls below are therefore autouse and
# categorical -- they cover every test in this file, direct calls and
# ``execute_step8_parallel_validation`` pipeline calls alike:
#
#   1. ``temp_project_root`` moves the resolution target into ``tmp_path``.
#   2. ``live_repo_digest_guard`` fails any test that changes a live control file,
#      so a real-root write reappearing by ANY future route turns the suite RED.

LIVE_REPO_ROOT = Path(__file__).resolve().parents[2]  # integration -> tests -> root
LIVE_PROJECT_MD = LIVE_REPO_ROOT / "PROJECT.md"
LIVE_CLAUDE_PROJECT_MD = LIVE_REPO_ROOT / ".claude" / "PROJECT.md"
LIVE_CLAUDE_MD = LIVE_REPO_ROOT / "CLAUDE.md"
GUARDED_LIVE_FILES = (LIVE_PROJECT_MD, LIVE_CLAUDE_PROJECT_MD, LIVE_CLAUDE_MD)

# Minimal PROJECT.md replica carrying every marker the tracker updates, plus two
# lines it must NOT touch, so temp-consumer tests prove a real write and real
# selectivity instead of mocking the effect away.
REPLICA_PROJECT_MD = """# Temp Project (test replica, Issue #1821)

**Last Updated**: 2026-01-08 (Issue #203)
**Last Compliance Check**: 2026-01-08

## Stage

Current stage: Planning

## Issues

In progress:
- #203: Previous feature
"""


def _digest(path: Path) -> Optional[str]:
    """Return sha256 of ``path``, or None when unreadable/absent (symlinks followed)."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


class FileDigestGuard:
    """Refuse any content change to a fixed set of files across a test.

    Kept independent of pytest so BOTH arms can be exercised directly
    (``test_digest_guard_refuses_and_permits``): an unchanged file must pass, and a
    changed, created or deleted file must raise ``AssertionError`` naming the path.
    """

    def __init__(self, paths: Sequence[Path]) -> None:
        self.paths = [Path(p) for p in paths]
        self.before: Optional[Dict[Path, Optional[str]]] = None

    def snapshot(self) -> None:
        """Record the current digest of every guarded path."""
        self.before = {p: _digest(p) for p in self.paths}

    def assert_unchanged(self) -> None:
        """Raise AssertionError if any guarded path's digest moved since snapshot()."""
        if self.before is None:
            raise AssertionError("FileDigestGuard.snapshot() was never called")

        changed = [
            (path, before, _digest(path))
            for path, before in self.before.items()
            if _digest(path) != before
        ]
        if changed:
            detail = "\n".join(
                f"  {path}: {before} -> {after}" for path, before, after in changed
            )
            raise AssertionError(
                "Guarded file(s) changed during the test -- a test wrote a file it "
                f"does not own (Issue #1821):\n{detail}"
            )


@pytest.fixture(autouse=True)
def live_repo_digest_guard():
    """Fail any test in this file that changes a live repo control file.

    Yields:
        The armed FileDigestGuard, so tests can assert on the guard itself.
    """
    guard = FileDigestGuard(GUARDED_LIVE_FILES)
    guard.snapshot()
    # Anti-fail-open: a guard watching a path that does not exist guards nothing and
    # would pass forever. Refuse to arm unless the primary subject was really read.
    assert guard.before[LIVE_PROJECT_MD] is not None, (
        f"digest guard is not wired to a real file: {LIVE_PROJECT_MD} is unreadable "
        "(check LIVE_REPO_ROOT parents[] depth)"
    )
    yield guard
    guard.assert_unchanged()


@pytest.fixture(autouse=True)
def temp_project_root(tmp_path, monkeypatch):
    """Point ``_find_project_md()`` at a temp replica for EVERY test in this file.

    The replica reproduces the live layout's ``.claude/PROJECT.md -> ../PROJECT.md``
    symlink so production still takes its real symlink-skip branch.

    Returns:
        Replica repo root; its ``PROJECT.md`` is the only file the tracker may write.
    """
    root = tmp_path / "replica_repo"
    (root / ".claude").mkdir(parents=True)
    (root / "PROJECT.md").write_text(REPLICA_PROJECT_MD, encoding="utf-8")
    (root / ".claude" / "PROJECT.md").symlink_to(Path("..") / "PROJECT.md")
    monkeypatch.chdir(root)
    return root


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def pipeline_context():
    """Simulated /auto-implement pipeline context"""
    return {
        "workflow_id": "test-workflow-123",
        "issue_number": 204,
        "feature_request": "Fix doc-master auto-apply and integrate progress tracker",
        "changed_files": [
            ".claude/agents/doc-master.md",
            ".claude/commands/auto-implement.md",
            "plugins/autonomous-dev/lib/doc_update_risk_classifier.py"
        ],
        "stage": "implementation_complete",
        "batch_mode": False
    }


@pytest.fixture
def batch_mode_context(pipeline_context):
    """Batch mode pipeline context"""
    return {**pipeline_context, "batch_mode": True}


@pytest.fixture
def doc_master_success_output():
    """Simulated doc-master successful output"""
    return {
        "success": True,
        "updates_applied": [
            {"file": "CHANGELOG.md", "status": "applied"},
            {"file": ".claude/PROJECT.md", "status": "applied"}
        ],
        "error": None
    }


@pytest.fixture
def mock_project_md_content():
    """Mock PROJECT.md content before update"""
    return """# Project

**Last Updated**: 2026-01-08 (Issue #203)
**Last Compliance Check**: 2026-01-08

## Component Versions

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Skills | 1.0.0 | 28 | ✅ Compliant |

## Stage

Current stage: Planning

## Issues

In progress:
- #203: Previous feature
"""


@pytest.fixture
def expected_project_md_content():
    """Expected PROJECT.md content after progress tracker update"""
    return """# Project

**Last Updated**: 2026-01-09 (Issue #204)
**Last Compliance Check**: 2026-01-09

## Component Versions

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Skills | 1.0.0 | 28 | ✅ Compliant |

## Stage

Current stage: Implementation Complete

## Issues

In progress:
- #204: Fix doc-master auto-apply and integrate progress tracker

Completed:
- #203: Previous feature
"""


# ============================================================================
# Test Progress Tracker Invocation in Pipeline
# ============================================================================

def test_progress_tracker_invoked_in_pipeline(pipeline_context):
    """Test that project-progress-tracker is invoked in execute_step8_parallel_validation"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker result is included
    assert "progress_tracker" in result
    assert result["progress_tracker"] is not None


def test_progress_tracker_receives_correct_context(pipeline_context):
    """Test that progress tracker receives pipeline context values"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker was invoked and result returned
    assert result["progress_tracker"] is not None
    progress_result = result["progress_tracker"]
    # Verify it's a ProgressTrackerResult
    assert hasattr(progress_result, 'success')
    assert hasattr(progress_result, 'project_md_updated')


# ============================================================================
# Test Progress Tracker Updates PROJECT.md
# ============================================================================

@patch('builtins.open', new_callable=mock_open, read_data="**Last Updated**: 2026-01-08")
def test_progress_tracker_updates_last_updated_timestamp(mock_file, pipeline_context):
    """Test that progress tracker updates Last Updated timestamp in PROJECT.md"""
    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage=pipeline_context["stage"],
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert result.success is True
    assert result.project_md_updated is True
    # Should write to PROJECT.md with new timestamp
    mock_file.assert_called()


@patch('builtins.open', new_callable=mock_open)
def test_progress_tracker_updates_stage_status(mock_file, pipeline_context):
    """Test that progress tracker updates Stage status in PROJECT.md"""
    # Arrange
    mock_file.return_value.read.return_value = "Current stage: Planning"

    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage="implementation_complete",
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert result.success is True
    # Should update stage to "Implementation Complete"
    mock_file.assert_called()


@patch('builtins.open', new_callable=mock_open)
def test_progress_tracker_updates_issue_references(mock_file, pipeline_context):
    """Test that progress tracker updates Issue references in PROJECT.md"""
    # Act
    result = invoke_progress_tracker(
        issue_number=204,
        stage="implementation_complete",
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert result.success is True
    # Should add/update #204 in Issues section
    mock_file.assert_called()


@patch('builtins.open', new_callable=mock_open)
def test_progress_tracker_updates_component_count(mock_file, pipeline_context):
    """Test that progress tracker updates component count in PROJECT.md"""
    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage=pipeline_context["stage"],
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert result.success is True
    # Should update component count if new components added
    mock_file.assert_called()


# ============================================================================
# Test Integration with Doc-Master Auto-Apply
# ============================================================================

def test_progress_tracker_integration_with_pipeline(pipeline_context):
    """Test progress tracker runs in pipeline and returns result"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker executed
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    # Should have success status
    assert progress_result.success is True or progress_result.error is not None


@patch('auto_implement_pipeline.invoke_progress_tracker')
@patch('auto_implement_pipeline.invoke_doc_master')
def test_progress_tracker_after_doc_master_approval_prompt(
    mock_doc_master,
    mock_progress_tracker,
    pipeline_context
):
    """Test progress tracker runs after doc-master prompts for HIGH_RISK approval"""
    # Arrange - doc-master prompts user for HIGH_RISK change
    mock_doc_master.return_value = {
        "success": True,
        "auto_applied": False,
        "required_approval": True,
        "user_approved": True
    }
    mock_progress_tracker.return_value = ProgressTrackerResult(
        success=True,
        project_md_updated=True,
        error=None
    )

    # Act
    result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker still runs
    assert mock_progress_tracker.called


# ============================================================================
# Test Batch Mode Behavior
# ============================================================================

def test_batch_mode_progress_tracker_no_blocking(batch_mode_context):
    """Test that progress tracker doesn't block in batch mode"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(batch_mode_context)

    # Assert - Should complete without blocking (no user prompts)
    assert "progress_tracker" in result
    # Pipeline should return (not block on prompts)
    assert result is not None


def test_batch_mode_progress_tracker_silent_updates(batch_mode_context):
    """Test that progress tracker updates PROJECT.md silently in batch mode"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(batch_mode_context)

    # Assert - Updates applied without user interaction
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    # Should complete (success or graceful failure)
    assert progress_result is not None


# ============================================================================
# Test Graceful Degradation
# ============================================================================

def test_pipeline_continues_if_progress_tracker_fails(pipeline_context):
    """Test that pipeline continues if progress tracker fails (graceful degradation)"""
    # Arrange - Progress tracker will fail because PROJECT.md not found
    with patch('auto_implement_pipeline._find_project_md', return_value=None):
        # Act
        result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Pipeline should return even with progress tracker failure
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    # Progress tracker should fail gracefully (not raise exception)
    assert progress_result.success is False
    assert progress_result.error is not None


def test_pipeline_handles_file_errors_gracefully(pipeline_context):
    """Test that pipeline handles file errors gracefully"""
    # Arrange - File open raises exception
    with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
        with patch('builtins.open', side_effect=IOError("Disk error")):
            # Act
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Should catch exception and return result
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    # Should fail gracefully
    assert progress_result.success is False
    assert progress_result.error is not None


def test_progress_tracker_failure_returns_result_with_error(pipeline_context):
    """Test that progress tracker failure returns result with error details"""
    # Arrange - File write fails
    with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
        with patch('builtins.open', side_effect=PermissionError("Write permission denied")):
            # Act
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Should return result with error
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    assert progress_result.success is False
    assert "denied" in progress_result.error.lower() or "permission" in progress_result.error.lower()


# ============================================================================
# Test Progress Tracker File Operations
# ============================================================================

def test_progress_tracker_uses_write_tool(pipeline_context):
    """Test that progress tracker uses Write tool (not just Read)"""
    # Act
    with patch('builtins.open', mock_open()) as mock_file:
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert - Should open file in write mode
    assert mock_file.called
    # Should call with write mode ('w' or 'a')


def test_progress_tracker_uses_edit_tool_for_updates(temp_project_root, pipeline_context):
    """Test that progress tracker performs SELECTIVE updates (unrelated lines survive).

    Previously this patched ``pathlib.Path.read_text``/``write_text``, which production
    never calls (it writes through ``builtins.open``), so the patches intercepted
    nothing, the test asserted nothing, and the live PROJECT.md was rewritten instead
    (Issue #1821). It now runs against the temp replica and asserts real selectivity.
    """
    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage=pipeline_context["stage"],
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert - tracked lines change, untracked lines survive byte-for-byte
    assert result.success is True
    updated = (temp_project_root / "PROJECT.md").read_text(encoding="utf-8")
    assert "**Last Updated**: 2026-01-08" not in updated
    assert "**Last Compliance Check**: 2026-01-08" in updated
    assert "- #203: Previous feature" in updated
    assert updated.startswith("# Temp Project (test replica, Issue #1821)")


# ============================================================================
# Test Progress Tracker Result Structure
# ============================================================================

def test_progress_tracker_result_structure(pipeline_context):
    """Test that ProgressTrackerResult contains expected fields"""
    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage=pipeline_context["stage"],
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert hasattr(result, 'success')
    assert hasattr(result, 'project_md_updated')
    assert hasattr(result, 'error')
    assert isinstance(result.success, bool)
    assert isinstance(result.project_md_updated, bool)


# ============================================================================
# Test Pipeline Step Ordering
# ============================================================================

def test_progress_tracker_result_structure_in_pipeline(pipeline_context):
    """Test that progress tracker result is properly structured in pipeline output"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker result has expected structure
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    assert hasattr(progress_result, 'success')
    assert hasattr(progress_result, 'project_md_updated')
    assert hasattr(progress_result, 'error')


# ============================================================================
# Test Progress Tracker with Different Stages
# ============================================================================

@pytest.mark.parametrize("stage,expected_status", [
    ("research_complete", "Research Complete"),
    ("planning_complete", "Planning Complete"),
    ("tests_written", "Tests Written"),
    ("implementation_complete", "Implementation Complete"),
    ("validation_complete", "Validation Complete"),
])
def test_progress_tracker_updates_different_stages(stage, expected_status, pipeline_context):
    """Test that progress tracker correctly updates different pipeline stages"""
    # Act
    with patch('builtins.open', mock_open()):
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=stage,
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert
    assert result.success is True


# ============================================================================
# Test Progress Tracker Error Cases
# ============================================================================

def test_progress_tracker_handles_missing_project_md(pipeline_context):
    """Test that progress tracker handles missing PROJECT.md gracefully"""
    # Arrange - PROJECT.md doesn't exist
    with patch('pathlib.Path.exists', return_value=False):
        # Act
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert - Should fail gracefully
    assert result.success is False
    assert "PROJECT.md" in result.error or "not found" in result.error


def test_progress_tracker_handles_malformed_project_md(pipeline_context):
    """Test that progress tracker handles malformed PROJECT.md"""
    # Arrange - Malformed PROJECT.md content
    with patch('builtins.open', mock_open(read_data="Invalid content\n\n\n")):
        # Act
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert - Should handle gracefully
    # (May succeed with warning or fail cleanly)
    assert isinstance(result.success, bool)


def test_progress_tracker_handles_permission_error(pipeline_context):
    """Test that progress tracker handles file permission errors"""
    # Arrange - Permission denied
    with patch('builtins.open', side_effect=PermissionError("Access denied")):
        # Act
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert
    assert result.success is False
    assert "permission" in result.error.lower() or "denied" in result.error.lower()


# ============================================================================
# Test Integration with Git Workflow
# ============================================================================

def test_pipeline_returns_complete_results_dict(pipeline_context):
    """Test that pipeline returns dict with all expected keys"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Result dict has expected keys
    assert isinstance(result, dict)
    assert "progress_tracker" in result
    # Progress tracker result should be ProgressTrackerResult
    assert result["progress_tracker"] is not None


# ============================================================================
# Test Multiple Issues Tracking
# ============================================================================

def test_progress_tracker_tracks_multiple_issues(pipeline_context):
    """Test that progress tracker can track multiple issues simultaneously"""
    # Act
    with patch('builtins.open', mock_open()):
        result1 = invoke_progress_tracker(issue_number=204, stage="implementation_complete", workflow_id="wf1")
        result2 = invoke_progress_tracker(issue_number=205, stage="planning_complete", workflow_id="wf2")

    # Assert - Both issues tracked
    assert result1.success is True
    assert result2.success is True


# ============================================================================
# Test Concurrent Safety
# ============================================================================

def test_progress_tracker_handles_concurrent_updates(pipeline_context):
    """Test that progress tracker handles concurrent PROJECT.md updates safely"""
    # Note: This is a smoke test - actual concurrency testing would be more complex
    # Act
    with patch('builtins.open', mock_open()):
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert - Should complete successfully
    assert result.success is True


# ============================================================================
# Isolation regression tests (Issue #1821)
# ============================================================================

def test_find_project_md_resolves_inside_the_temp_replica(temp_project_root):
    """Positive control for the isolation fixture: the route really is redirected.

    If ``_find_project_md()`` ever stops honouring cwd (absolute paths, a repo-root
    walk), this fails loudly instead of the digest guard catching a live write after
    the fact.
    """
    import auto_implement_pipeline

    resolved = auto_implement_pipeline._find_project_md()

    assert resolved is not None
    assert Path(resolved).resolve() == (temp_project_root / "PROJECT.md").resolve()
    assert Path(resolved).resolve() != LIVE_PROJECT_MD.resolve()


def test_progress_tracker_writes_the_temp_replica_not_the_live_file(
    temp_project_root, pipeline_context
):
    """REAL write positive: isolation must not be achieved by mocking the write away.

    A genuine write happens, it lands in ``tmp_path``, and the assertions are on the
    written bytes.
    """
    # Act
    result = invoke_progress_tracker(
        issue_number=204,
        stage="implementation_complete",
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert - real update, correct date and issue marker, in the temp file
    assert result.success is True
    assert result.project_md_updated is True
    today = datetime.now().strftime("%Y-%m-%d")
    updated = (temp_project_root / "PROJECT.md").read_text(encoding="utf-8")
    assert f"**Last Updated**: {today} (Issue #204)" in updated
    assert "Current stage: implementation_complete" in updated
    assert "Last Updated timestamp" in result.updates_made


def test_pipeline_step8_writes_the_temp_replica_not_the_live_file(temp_project_root):
    """Pipeline-integration route (not just direct calls) resolves to the replica.

    ``execute_step8_parallel_validation`` calls the tracker itself, so isolating only
    direct ``invoke_progress_tracker`` calls would leave this route on the live file.
    Deliberately runs with NO mocks: the real resolution path executes.
    """
    # Act
    result = execute_step8_parallel_validation({
        "workflow_id": "wf-1821",
        "issue_number": 204,
        "stage": "implementation_complete",
        "batch_mode": False,
    })

    # Assert
    assert result["progress_tracker"].success is True
    assert result["progress_tracker"].project_md_updated is True
    today = datetime.now().strftime("%Y-%m-%d")
    assert f"**Last Updated**: {today} (Issue #204)" in (
        temp_project_root / "PROJECT.md"
    ).read_text(encoding="utf-8")


def test_live_digest_guard_fixture_is_armed_on_the_real_project_md(
    live_repo_digest_guard
):
    """Wiring check (Q1 connected): the autouse guard watches the REAL control files.

    ``FileDigestGuard`` being correct is worthless if the fixture points it at a path
    that does not exist -- that is a probe which cannot fail. This asserts the live
    paths exist, are covered, and were actually digested.
    """
    assert LIVE_PROJECT_MD.exists(), f"path depth wrong: {LIVE_PROJECT_MD}"
    assert LIVE_PROJECT_MD in live_repo_digest_guard.paths
    assert LIVE_CLAUDE_PROJECT_MD in live_repo_digest_guard.paths
    assert live_repo_digest_guard.before is not None
    assert live_repo_digest_guard.before[LIVE_PROJECT_MD] is not None


def test_digest_guard_refuses_and_permits(tmp_path):
    """Both arms of FileDigestGuard, on a subject unrelated to PROJECT.md.

    Permit arm: unchanged file -> no raise. Refuse arms: content edit -> raise,
    deletion -> raise, never-armed -> raise. Deliberately a DIFFERENT shape from the
    bug that prompted the guard (a plain text file, no tracker, no symlink, no cwd
    dependency), so the guard is proven against the category "file changed" rather
    than the single instance that was caught.
    """
    subject = tmp_path / "control.md"
    subject.write_text("original\n", encoding="utf-8")
    guard = FileDigestGuard([subject])
    guard.snapshot()

    # Permit arm - nothing changed
    guard.assert_unchanged()

    # Refuse arm 1 - content mutated
    subject.write_text("mutated\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="control.md"):
        guard.assert_unchanged()

    # Refuse arm 2 - file removed
    guard.snapshot()
    subject.unlink()
    with pytest.raises(AssertionError, match="control.md"):
        guard.assert_unchanged()

    # Refuse arm 3 - an un-armed guard must not silently pass (fail-open)
    with pytest.raises(AssertionError, match="snapshot"):
        FileDigestGuard([subject]).assert_unchanged()


def test_digest_guard_catches_a_live_shaped_unisolated_write(tmp_path, monkeypatch):
    """Counterfactual: reproduce the #1821 defect and observe the guard REFUSING.

    Builds a byte-for-byte clone of the live layout that caused the defect (root
    ``PROJECT.md`` copied from the live file plus the ``.claude/PROJECT.md ->
    ../PROJECT.md`` symlink), then runs the tracker the way the broken tests ran it:
    no redirection, no mocks. Production skips the symlink, rewrites the root file,
    and the guard raises.

    The subject is the CLONE, never the live file, so the tripwire is proven without
    putting the tracked PROJECT.md at risk.
    """
    live_bytes = LIVE_PROJECT_MD.read_bytes()
    assert b"**Last Updated**:" in live_bytes, (
        "live PROJECT.md no longer carries the marker this counterfactual depends on"
    )

    clone = tmp_path / "live_shaped_repo"
    (clone / ".claude").mkdir(parents=True)
    (clone / "PROJECT.md").write_bytes(live_bytes)
    (clone / ".claude" / "PROJECT.md").symlink_to(Path("..") / "PROJECT.md")

    guard = FileDigestGuard([
        clone / "PROJECT.md",
        clone / ".claude" / "PROJECT.md",
    ])
    guard.snapshot()
    guard.assert_unchanged()  # negative control: armed, quiet, nothing done yet

    # Act - the exact unisolated call shape that passed while mutating the repo
    monkeypatch.chdir(clone)
    result = invoke_progress_tracker(
        issue_number=204, stage="implementation_complete", workflow_id="wf-1821"
    )

    # Assert - the write really happened, and the guard refuses it
    assert result.project_md_updated is True
    with pytest.raises(AssertionError, match="PROJECT.md"):
        guard.assert_unchanged()
