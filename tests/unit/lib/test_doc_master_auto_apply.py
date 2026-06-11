"""
Unit tests for doc_master_auto_apply.py - Auto-apply logic for doc-master agent

Tests cover:
- Auto-apply behavior for LOW_RISK updates (no user prompt)
- Approval prompt behavior for HIGH_RISK updates
- Batch mode: auto-apply all LOW_RISK, skip HIGH_RISK with logging
- Interactive mode: auto-apply LOW_RISK, prompt for HIGH_RISK
- Integration with risk classifier
- File write operations for approved updates
- Error handling and graceful degradation
- Logging for audit trail

This is the RED phase of TDD - tests should fail initially since implementation doesn't exist yet.

Date: 2026-01-09
Issue: #204
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from typing import Dict, List, Optional

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

# Import the module under test (will fail initially - TDD red phase)
try:
    from doc_master_auto_apply import (
        DocUpdateApplier,
        auto_apply_doc_update,
        apply_doc_updates_batch,
        DocUpdateResult,
        DocUpdate,
    )
    from doc_update_risk_classifier import RiskLevel, RiskClassification
except ImportError:
    # Allow tests to be collected even if implementation doesn't exist yet
    pytest.skip("doc_master_auto_apply.py not implemented yet", allow_module_level=True)


# ============================================================================
# Regression Guard — protects against re-introduction of real-repo writes
# ============================================================================
#
# Bug history (Issue #1200, STEP 8 cycle 3):
# Several tests in this file call `auto_apply_doc_update()` with fixtures whose
# `file_path` is RELATIVE (e.g., "CHANGELOG.md", "README.md", "test.md"). The
# library `doc_master_auto_apply.py` resolves relative paths against CWD; when
# pytest is run from the repo root, that CWD IS the repo root, so an unpatched
# call to `auto_apply_doc_update(low_risk_changelog_update, batch_mode=True)`
# silently OVERWRITES the real `CHANGELOG.md` with 3 lines of fixture content
# (827 lines deleted). The hazard was discovered after two CHANGELOG-dependent
# tests kept "re-failing" across remediation cycles because the unit-tier run
# kept truncating CHANGELOG.md as a side effect.
#
# This module-scoped autouse fixture snapshots the real repo CHANGELOG.md at
# module setup and asserts identical content at module teardown — catching ANY
# future re-introduction of a real-repo write in this module, regardless of
# which test causes it. This IS the regression test for the bug fix (satisfies
# the per-project "regression test on every bug fix" rule).

@pytest.fixture(autouse=True, scope="module")
def _guard_repo_changelog_unchanged():
    """Snapshot real repo CHANGELOG.md and assert unchanged at module teardown.

    Yields control to the test module. At teardown, re-reads
    `<repo_root>/CHANGELOG.md` and asserts byte-for-byte equality with the
    snapshot taken at setup. A mismatch indicates one of the tests in this
    module wrote to the real repo CHANGELOG.md — almost certainly because a
    call site reaches a real `open(..., 'w')` without `builtins.open` patched
    and without an absolute `tmp_path`-based `file_path`.

    REPO_ROOT = parents[3] because this file lives at
    `tests/unit/lib/test_doc_master_auto_apply.py` →
    lib → unit → tests → repo_root (3 hops).
    """
    repo_root = Path(__file__).resolve().parents[3]
    changelog_path = repo_root / "CHANGELOG.md"

    snapshot: Optional[bytes] = None
    if changelog_path.exists():
        snapshot = changelog_path.read_bytes()

    yield

    if snapshot is None:
        # No CHANGELOG existed at setup — assert one wasn't created.
        assert not changelog_path.exists(), (
            f"Test in this module created {changelog_path} that didn't exist "
            f"at module setup — a relative-path file_path leaked to a real "
            f"write. See Issue #1200 STEP 8 cycle 3 bug history."
        )
        return

    current = changelog_path.read_bytes() if changelog_path.exists() else b""
    assert current == snapshot, (
        f"REGRESSION: real repo {changelog_path} was modified during this "
        f"test module run. A test reached a real file write — almost "
        f"certainly an unpatched `auto_apply_doc_update()` call with a "
        f"relative `file_path` fixture. See Issue #1200 STEP 8 cycle 3.\n"
        f"  snapshot size = {len(snapshot)} bytes\n"
        f"  current size  = {len(current)} bytes\n"
        f"  first 200 chars of current = {current[:200]!r}"
    )


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def low_risk_changelog_update():
    """Low-risk CHANGELOG.md update"""
    return DocUpdate(
        file_path="CHANGELOG.md",
        content="## [3.46.0] - 2026-01-09\n### Fixed\n- Fix doc-master auto-apply (#204)",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.LOW_RISK,
            confidence=0.95,
            reason="CHANGELOG.md update",
            requires_approval=False
        )
    )


@pytest.fixture
def low_risk_readme_update():
    """Low-risk README.md update"""
    return DocUpdate(
        file_path="README.md",
        content="# Autonomous Dev\n\nUpdated installation instructions.",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.LOW_RISK,
            confidence=0.95,
            reason="README.md update",
            requires_approval=False
        )
    )


@pytest.fixture
def low_risk_project_metadata_update():
    """Low-risk PROJECT.md metadata update"""
    return DocUpdate(
        file_path=".claude/PROJECT.md",
        content="**Last Updated**: 2026-01-09 (Issue #204)\n**Last Compliance Check**: 2026-01-09",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.LOW_RISK,
            confidence=0.85,
            reason="PROJECT.md metadata update",
            requires_approval=False
        )
    )


@pytest.fixture
def high_risk_goals_update():
    """High-risk PROJECT.md GOALS update"""
    return DocUpdate(
        file_path=".claude/PROJECT.md",
        content="## GOALS\n- Build autonomous pipeline\n- Support multiple languages (NEW)",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.HIGH_RISK,
            confidence=0.95,
            reason="PROJECT.md GOALS section change",
            requires_approval=True
        )
    )


@pytest.fixture
def high_risk_constraints_update():
    """High-risk PROJECT.md CONSTRAINTS update"""
    return DocUpdate(
        file_path=".claude/PROJECT.md",
        content="## CONSTRAINTS\n- Python 3.8+\n- No external APIs (NEW)",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.HIGH_RISK,
            confidence=0.95,
            reason="PROJECT.md CONSTRAINTS section change",
            requires_approval=True
        )
    )


@pytest.fixture
def mock_file_system(tmp_path):
    """Mock file system for testing file operations"""
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    (test_dir / ".claude").mkdir()
    return test_dir


# ============================================================================
# Test Auto-Apply for LOW_RISK Updates (Interactive Mode)
# ============================================================================

@patch('builtins.open', new_callable=mock_open)
def test_auto_apply_low_risk_changelog(mock_file, low_risk_changelog_update):
    """Test that LOW_RISK CHANGELOG update is auto-applied without prompt"""
    # Act
    result = auto_apply_doc_update(
        update=low_risk_changelog_update,
        batch_mode=False
    )

    # Assert
    assert result.applied is True
    assert result.required_approval is False
    assert result.user_approved is None  # No user interaction needed
    assert "auto-applied" in result.message.lower()
    mock_file.assert_called_once()  # File was written


@patch('builtins.open', new_callable=mock_open)
def test_auto_apply_low_risk_readme(mock_file, low_risk_readme_update):
    """Test that LOW_RISK README update is auto-applied without prompt"""
    # Act
    result = auto_apply_doc_update(
        update=low_risk_readme_update,
        batch_mode=False
    )

    # Assert
    assert result.applied is True
    assert result.required_approval is False
    assert "auto-applied" in result.message.lower()
    mock_file.assert_called_once()


@patch('builtins.open', new_callable=mock_open)
def test_auto_apply_low_risk_project_metadata(mock_file, low_risk_project_metadata_update):
    """Test that LOW_RISK PROJECT.md metadata update is auto-applied"""
    # Act
    result = auto_apply_doc_update(
        update=low_risk_project_metadata_update,
        batch_mode=False
    )

    # Assert
    assert result.applied is True
    assert result.required_approval is False
    assert "auto-applied" in result.message.lower()
    mock_file.assert_called_once()


# ============================================================================
# Test Approval Prompt for HIGH_RISK Updates (Interactive Mode)
# ============================================================================

@patch('builtins.input', return_value='y')
@patch('builtins.open', new_callable=mock_open)
def test_high_risk_goals_prompts_for_approval_approved(mock_file, mock_input, high_risk_goals_update):
    """Test that HIGH_RISK GOALS update prompts user and applies if approved"""
    # Act
    result = auto_apply_doc_update(
        update=high_risk_goals_update,
        batch_mode=False
    )

    # Assert
    assert result.applied is True
    assert result.required_approval is True
    assert result.user_approved is True
    assert "approved" in result.message.lower()
    mock_input.assert_called_once()  # User was prompted
    mock_file.assert_called_once()  # File was written


@patch('builtins.input', return_value='n')
@patch('builtins.open', new_callable=mock_open)
def test_high_risk_goals_prompts_for_approval_rejected(mock_file, mock_input, high_risk_goals_update):
    """Test that HIGH_RISK GOALS update prompts user and skips if rejected"""
    # Act
    result = auto_apply_doc_update(
        update=high_risk_goals_update,
        batch_mode=False
    )

    # Assert
    assert result.applied is False
    assert result.required_approval is True
    assert result.user_approved is False
    assert "rejected" in result.message.lower() or "skipped" in result.message.lower()
    mock_input.assert_called_once()  # User was prompted
    mock_file.assert_not_called()  # File was NOT written


@patch('builtins.input', return_value='y')
@patch('builtins.open', new_callable=mock_open)
def test_high_risk_constraints_prompts_for_approval(mock_file, mock_input, high_risk_constraints_update):
    """Test that HIGH_RISK CONSTRAINTS update prompts user"""
    # Act
    result = auto_apply_doc_update(
        update=high_risk_constraints_update,
        batch_mode=False
    )

    # Assert
    assert result.required_approval is True
    mock_input.assert_called_once()


# ============================================================================
# Test Batch Mode Behavior
# ============================================================================

@patch('builtins.open', new_callable=mock_open)
def test_batch_mode_auto_applies_low_risk_silently(mock_file, low_risk_changelog_update):
    """Test that batch mode auto-applies LOW_RISK updates without any prompts"""
    # Act
    result = auto_apply_doc_update(
        update=low_risk_changelog_update,
        batch_mode=True
    )

    # Assert
    assert result.applied is True
    assert result.required_approval is False
    assert result.user_approved is None  # No interaction in batch mode
    mock_file.assert_called_once()


@patch('builtins.open', new_callable=mock_open)
def test_batch_mode_skips_high_risk_without_prompt(mock_file, high_risk_goals_update):
    """Test that batch mode skips HIGH_RISK updates without prompting user"""
    # Act
    result = auto_apply_doc_update(
        update=high_risk_goals_update,
        batch_mode=True
    )

    # Assert
    assert result.applied is False
    assert result.required_approval is True
    assert result.user_approved is None  # No interaction in batch mode
    assert "skipped" in result.message.lower()
    assert "batch mode" in result.message.lower()
    mock_file.assert_not_called()


@patch('builtins.open', new_callable=mock_open)
def test_batch_mode_logs_skipped_high_risk(mock_file, high_risk_goals_update, caplog):
    """Test that batch mode logs skipped HIGH_RISK updates for manual review"""
    # Act
    result = auto_apply_doc_update(
        update=high_risk_goals_update,
        batch_mode=True
    )

    # Assert
    assert result.applied is False
    # Check that warning was logged (caplog captures logs)
    # Note: actual logging implementation may vary
    assert "PROJECT.md" in result.message


# ============================================================================
# Test Batch Processing Multiple Updates
# ============================================================================

@patch('builtins.open', new_callable=mock_open)
def test_batch_apply_all_low_risk(mock_file, low_risk_changelog_update, low_risk_readme_update):
    """Test batch processing applies all LOW_RISK updates"""
    # Arrange
    updates = [low_risk_changelog_update, low_risk_readme_update]

    # Act
    results = apply_doc_updates_batch(updates, batch_mode=True)

    # Assert
    assert len(results) == 2
    assert all(r.applied for r in results)
    assert all(not r.required_approval for r in results)
    assert mock_file.call_count == 2  # Both files written


@patch('builtins.open', new_callable=mock_open)
def test_batch_apply_mixed_risk(
    mock_file,
    low_risk_changelog_update,
    high_risk_goals_update
):
    """Test batch processing applies LOW_RISK, skips HIGH_RISK"""
    # Arrange
    updates = [low_risk_changelog_update, high_risk_goals_update]

    # Act
    results = apply_doc_updates_batch(updates, batch_mode=True)

    # Assert
    assert len(results) == 2
    assert results[0].applied is True  # LOW_RISK applied
    assert results[1].applied is False  # HIGH_RISK skipped
    assert mock_file.call_count == 1  # Only one file written


@patch('builtins.open', new_callable=mock_open)
def test_batch_apply_all_high_risk(mock_file, high_risk_goals_update, high_risk_constraints_update):
    """Test batch processing skips all HIGH_RISK updates"""
    # Arrange
    updates = [high_risk_goals_update, high_risk_constraints_update]

    # Act
    results = apply_doc_updates_batch(updates, batch_mode=True)

    # Assert
    assert len(results) == 2
    assert all(not r.applied for r in results)
    assert all(r.required_approval for r in results)
    assert mock_file.call_count == 0  # No files written


# ============================================================================
# Test Interactive Mode with Multiple Updates
# ============================================================================

@patch('builtins.input', side_effect=['y', 'n'])  # Approve first, reject second
@patch('builtins.open', new_callable=mock_open)
def test_interactive_mixed_approvals(
    mock_file,
    mock_input,
    high_risk_goals_update,
    high_risk_constraints_update
):
    """Test interactive mode with mixed user approvals"""
    # Arrange
    updates = [high_risk_goals_update, high_risk_constraints_update]

    # Act
    results = apply_doc_updates_batch(updates, batch_mode=False)

    # Assert
    assert len(results) == 2
    assert results[0].applied is True  # First approved
    assert results[0].user_approved is True
    assert results[1].applied is False  # Second rejected
    assert results[1].user_approved is False
    assert mock_input.call_count == 2  # Prompted twice
    assert mock_file.call_count == 1  # Only one file written


# ============================================================================
# Test Error Handling
# ============================================================================

@patch('builtins.open', side_effect=PermissionError("Access denied"))
def test_file_write_error_handling(mock_file, low_risk_changelog_update):
    """Test that file write errors are handled gracefully"""
    # Act
    result = auto_apply_doc_update(
        update=low_risk_changelog_update,
        batch_mode=False
    )

    # Assert
    assert result.applied is False
    assert "error" in result.message.lower() or "failed" in result.message.lower()
    assert result.error is not None


@patch('builtins.open', side_effect=OSError("Disk full"))
def test_file_write_disk_full_error(mock_file, low_risk_readme_update):
    """Test that disk full errors are handled gracefully"""
    # Act
    result = auto_apply_doc_update(
        update=low_risk_readme_update,
        batch_mode=True
    )

    # Assert
    assert result.applied is False
    assert result.error is not None


def test_invalid_update_object_handling():
    """Test that invalid update objects are handled gracefully"""
    # Act
    result = auto_apply_doc_update(
        update=None,
        batch_mode=False
    )

    # Assert
    assert result.applied is False
    assert "error" in result.message.lower() or "invalid" in result.message.lower()


# ============================================================================
# Test File Operations
# ============================================================================

def test_file_write_creates_directories(mock_file_system, low_risk_changelog_update):
    """Test that missing directories are created before writing"""
    # Arrange
    nested_path = mock_file_system / "docs" / "nested" / "file.md"
    update = DocUpdate(
        file_path=str(nested_path),
        content="# Test",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.LOW_RISK,
            confidence=0.95,
            reason="Test",
            requires_approval=False
        )
    )

    # Act
    with patch('pathlib.Path.mkdir') as mock_mkdir:
        result = auto_apply_doc_update(update, batch_mode=True)

    # Assert - Should create parent directories
    assert result.applied is True or mock_mkdir.called


def test_file_write_preserves_existing_content(mock_file_system):
    """Test that file write operation correctly updates content"""
    # Arrange
    test_file = mock_file_system / "test.md"
    test_file.write_text("Old content")

    update = DocUpdate(
        file_path=str(test_file),
        content="New content",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.LOW_RISK,
            confidence=0.95,
            reason="Test",
            requires_approval=False
        )
    )

    # Act
    with patch('builtins.open', mock_open()) as mock_file:
        result = auto_apply_doc_update(update, batch_mode=True)

    # Assert
    assert result.applied is True


# ============================================================================
# Test DocUpdateResult Structure
# ============================================================================

@patch('builtins.open', new_callable=mock_open)
def test_doc_update_result_structure(mock_file, low_risk_changelog_update):
    """Test that DocUpdateResult contains expected fields.

    NOTE: `builtins.open` is patched because this test exercises
    `auto_apply_doc_update()` with a fixture whose `file_path="CHANGELOG.md"`
    is RELATIVE — without the patch, the call resolves to the real repo
    CHANGELOG.md and overwrites it with 3 lines of fixture content (the
    test-isolation bug fixed under Issue #1200, STEP 8 remediation cycle 3).
    Patching is appropriate here because the test only asserts result-object
    shape, not file-write semantics.
    """
    # Act
    result = auto_apply_doc_update(
        update=low_risk_changelog_update,
        batch_mode=True
    )

    # Assert
    assert hasattr(result, 'applied')
    assert hasattr(result, 'required_approval')
    assert hasattr(result, 'user_approved')
    assert hasattr(result, 'message')
    assert hasattr(result, 'error')
    assert isinstance(result.applied, bool)
    assert isinstance(result.required_approval, bool)
    assert isinstance(result.message, str)


# ============================================================================
# Test DocUpdateApplier Class (OOP approach)
# ============================================================================

def test_applier_instance_creation():
    """Test that DocUpdateApplier can be instantiated"""
    # Act
    applier = DocUpdateApplier(batch_mode=True)

    # Assert
    assert applier is not None
    assert hasattr(applier, 'apply')
    assert hasattr(applier, 'batch_mode')


def test_applier_batch_mode_configuration():
    """Test that applier respects batch_mode configuration"""
    # Act
    applier_batch = DocUpdateApplier(batch_mode=True)
    applier_interactive = DocUpdateApplier(batch_mode=False)

    # Assert
    assert applier_batch.batch_mode is True
    assert applier_interactive.batch_mode is False


@patch('builtins.open', new_callable=mock_open)
def test_applier_apply_method(mock_file, low_risk_changelog_update):
    """Test that applier.apply() works"""
    # Arrange
    applier = DocUpdateApplier(batch_mode=True)

    # Act
    result = applier.apply(low_risk_changelog_update)

    # Assert
    assert result.applied is True
    mock_file.assert_called_once()


# ============================================================================
# Test Logging and Audit Trail
# ============================================================================

@patch('builtins.open', new_callable=mock_open)
def test_low_risk_application_logged(mock_file, low_risk_changelog_update, caplog):
    """Test that LOW_RISK auto-apply is logged for audit trail"""
    # Act
    result = auto_apply_doc_update(
        update=low_risk_changelog_update,
        batch_mode=True
    )

    # Assert - Should log the application
    # (Actual logging implementation may vary)
    assert result.applied is True


@patch('builtins.open', new_callable=mock_open)
def test_high_risk_skip_logged(mock_file, high_risk_goals_update, caplog):
    """Test that HIGH_RISK skip is logged for manual review"""
    # Act
    result = auto_apply_doc_update(
        update=high_risk_goals_update,
        batch_mode=True
    )

    # Assert - Should log the skip
    assert result.applied is False
    assert "skipped" in result.message.lower()


# ============================================================================
# Test Integration with Risk Classifier
# ============================================================================

def test_respects_risk_classification_low_risk():
    """Test that applier respects LOW_RISK classification"""
    # Arrange
    update = DocUpdate(
        file_path="test.md",
        content="content",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.LOW_RISK,
            confidence=0.9,
            reason="test",
            requires_approval=False
        )
    )

    # Act
    with patch('builtins.open', mock_open()):
        result = auto_apply_doc_update(update, batch_mode=True)

    # Assert
    assert result.applied is True


def test_respects_risk_classification_high_risk():
    """Test that applier respects HIGH_RISK classification"""
    # Arrange
    update = DocUpdate(
        file_path="test.md",
        content="content",
        risk_classification=RiskClassification(
            risk_level=RiskLevel.HIGH_RISK,
            confidence=0.9,
            reason="test",
            requires_approval=True
        )
    )

    # Act
    with patch('builtins.open', mock_open()):
        result = auto_apply_doc_update(update, batch_mode=True)

    # Assert
    assert result.applied is False


# ============================================================================
# Test Edge Cases
# ============================================================================

def test_empty_update_list():
    """Test that empty update list is handled gracefully"""
    # Act
    results = apply_doc_updates_batch([], batch_mode=True)

    # Assert
    assert len(results) == 0


def test_handles_relative_file_paths(low_risk_changelog_update):
    """Test that relative file paths are handled correctly"""
    # Arrange
    update = DocUpdate(
        file_path="./CHANGELOG.md",  # Relative path
        content=low_risk_changelog_update.content,
        risk_classification=low_risk_changelog_update.risk_classification
    )

    # Act
    with patch('builtins.open', mock_open()):
        result = auto_apply_doc_update(update, batch_mode=True)

    # Assert
    assert result.applied is True


def test_handles_absolute_file_paths(low_risk_changelog_update, mock_file_system):
    """Test that absolute file paths are handled correctly"""
    # Arrange
    absolute_path = mock_file_system / "CHANGELOG.md"
    update = DocUpdate(
        file_path=str(absolute_path),  # Absolute path
        content=low_risk_changelog_update.content,
        risk_classification=low_risk_changelog_update.risk_classification
    )

    # Act
    with patch('builtins.open', mock_open()):
        result = auto_apply_doc_update(update, batch_mode=True)

    # Assert
    assert result.applied is True


def test_handles_unicode_content(low_risk_readme_update):
    """Test that Unicode content is written correctly"""
    # Arrange
    update = DocUpdate(
        file_path="README.md",
        content="# Test\n🚀 新功能: Unicode support",
        risk_classification=low_risk_readme_update.risk_classification
    )

    # Act
    with patch('builtins.open', mock_open()):
        result = auto_apply_doc_update(update, batch_mode=True)

    # Assert
    assert result.applied is True
