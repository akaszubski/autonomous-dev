"""Unit tests for drain_regression_check.py orchestration script."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch, mock_open

import pytest

# Add scripts to path
_SCRIPTS = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# Add lib to path for drain_queue_state import
_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import drain_regression_check
from drain_queue_state import _iso, _utc_now


class TestShouldCheckRegression:
    """Tests for should_check_regression function."""
    
    def test_skips_non_pending_status(self):
        """Records without pending status are skipped."""
        record = {
            "revert_status": "reverted",
            "timestamp": _iso(_utc_now() - timedelta(hours=1))
        }
        assert drain_regression_check.should_check_regression(record) is False
        
        record["revert_status"] = "not_needed"
        assert drain_regression_check.should_check_regression(record) is False
        
        # Missing revert_status (legacy record)
        del record["revert_status"]
        assert drain_regression_check.should_check_regression(record) is False
    
    def test_skips_recent_records_within_grace_period(self):
        """Records newer than 30 minutes are skipped."""
        record = {
            "revert_status": "pending",
            "timestamp": _iso(_utc_now() - timedelta(minutes=15))
        }
        assert drain_regression_check.should_check_regression(record) is False
        
        # At 29 minutes - still in grace period
        record["timestamp"] = _iso(_utc_now() - timedelta(minutes=29))
        assert drain_regression_check.should_check_regression(record) is False
    
    def test_checks_old_pending_records(self):
        """Records older than 30 minutes with pending status are checked."""
        record = {
            "revert_status": "pending",
            "timestamp": _iso(_utc_now() - timedelta(minutes=31))
        }
        assert drain_regression_check.should_check_regression(record) is True
        
        # Much older
        record["timestamp"] = _iso(_utc_now() - timedelta(hours=2))
        assert drain_regression_check.should_check_regression(record) is True
    
    def test_skips_invalid_timestamp(self):
        """Records with invalid or missing timestamp are skipped."""
        record = {
            "revert_status": "pending",
            "timestamp": "invalid"
        }
        assert drain_regression_check.should_check_regression(record) is False
        
        record["timestamp"] = None
        assert drain_regression_check.should_check_regression(record) is False
        
        del record["timestamp"]
        assert drain_regression_check.should_check_regression(record) is False


class TestProcessPendingRecord:
    """Tests for process_pending_record function."""
    
    def test_marks_not_needed_for_invalid_sha(self, tmp_path: Path):
        """Records with invalid SHA are marked not_needed."""
        record = {
            "revert_status": "pending",
            "commit_sha": "invalid",
            "before_metrics": {},
            "after_metrics": {}
        }
        
        updated = drain_regression_check.process_pending_record(record, tmp_path, {})
        
        assert updated["revert_status"] == "not_needed"
        assert updated["revert_reason"] == "invalid_or_missing_sha"
    
    def test_marks_not_needed_when_fix_commits_found(self, tmp_path: Path):
        """Records are marked not_needed when fix commits exist."""
        record = {
            "revert_status": "pending",
            "commit_sha": "a" * 40,
            "before_metrics": {"failing_tests": []},
            "after_metrics": {"failing_tests": ["test_broken"]}
        }
        
        with patch("drain_regression_check.find_fix_commits") as mock_find:
            mock_find.return_value = ["b" * 40, "c" * 40]
            
            updated = drain_regression_check.process_pending_record(record, tmp_path, {})
            
            assert updated["revert_status"] == "not_needed"
            assert "fix_commits_found" in updated["revert_reason"]
            assert "bbb" in updated["revert_reason"]  # First 3 chars of first commit
    
    def test_marks_not_needed_when_no_regression(self, tmp_path: Path):
        """Records are marked not_needed when no regression detected."""
        record = {
            "revert_status": "pending",
            "commit_sha": "a" * 40,
            "before_metrics": {"failing_tests": ["test_a"]},
            "after_metrics": {"failing_tests": ["test_a"]}
        }
        
        with patch("drain_regression_check.find_fix_commits") as mock_find:
            mock_find.return_value = []
            
            with patch("drain_regression_check.detect_regression") as mock_detect:
                mock_detect.return_value = False
                
                updated = drain_regression_check.process_pending_record(record, tmp_path, {})
                
                assert updated["revert_status"] == "not_needed"
                assert updated["revert_reason"] == "no_regression_detected"
    
    def test_successful_revert(self, tmp_path: Path):
        """Successfully reverts and reopens issues."""
        record = {
            "revert_status": "pending",
            "commit_sha": "a" * 40,
            "issues": [123, 456],
            "before_metrics": {"failing_tests": []},
            "after_metrics": {"failing_tests": ["test_broken"]}
        }
        
        with patch("drain_regression_check.find_fix_commits") as mock_find:
            mock_find.return_value = []
            
            with patch("drain_regression_check.detect_regression") as mock_detect:
                mock_detect.return_value = True
                
                with patch("drain_regression_check.revert_drain_commit") as mock_revert:
                    mock_revert.return_value = (True, "b" * 40)
                    
                    with patch("drain_regression_check.reopen_issues_with_label") as mock_reopen:
                        mock_reopen.return_value = 2
                        
                        updated = drain_regression_check.process_pending_record(
                            record, tmp_path, {}
                        )
                        
                        assert updated["revert_status"] == "reverted"
                        assert updated["revert_sha"] == "b" * 40
                        assert "revert_timestamp" in updated
                        assert updated["issues_reopened"] == 2
    
    def test_revert_failure_marks_not_needed(self, tmp_path: Path):
        """Failed revert marks record as not_needed to avoid thrashing."""
        record = {
            "revert_status": "pending",
            "commit_sha": "a" * 40,
            "before_metrics": {"failing_tests": []},
            "after_metrics": {"failing_tests": ["test_broken"]}
        }
        
        with patch("drain_regression_check.find_fix_commits") as mock_find:
            mock_find.return_value = []
            
            with patch("drain_regression_check.detect_regression") as mock_detect:
                mock_detect.return_value = True
                
                with patch("drain_regression_check.revert_drain_commit") as mock_revert:
                    mock_revert.return_value = (False, "merge conflict")
                    
                    updated = drain_regression_check.process_pending_record(
                        record, tmp_path, {}
                    )
                    
                    assert updated["revert_status"] == "not_needed"
                    assert "revert_failed" in updated["revert_reason"]
                    assert "merge conflict" in updated["revert_reason"]


class TestAtomicUpdateHistory:
    """Tests for atomic_update_history function."""
    
    def test_atomic_write_via_tempfile(self, tmp_path: Path):
        """Verifies atomic write using tempfile + os.replace."""
        history_path = tmp_path / "drain_log.jsonl"
        
        records = [
            {"id": 1, "status": "success"},
            {"id": 2, "status": "reverted"}
        ]
        
        # Mock tempfile.mkstemp to track temp file creation
        temp_fd = 999
        temp_path = str(tmp_path / ".drain_log_test.tmp")
        
        with patch("drain_regression_check.tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.return_value = (temp_fd, temp_path)
            
            # Mock os.fdopen to capture what's written
            written_lines = []
            
            def fake_fdopen(fd, mode, encoding):
                assert fd == temp_fd
                assert mode == 'w'
                assert encoding == 'utf-8'
                
                class FakeFile:
                    def write(self, data):
                        written_lines.append(data)
                    def __enter__(self):
                        return self
                    def __exit__(self, *args):
                        pass
                
                return FakeFile()
            
            with patch("drain_regression_check.os.fdopen", side_effect=fake_fdopen):
                with patch("drain_regression_check.os.replace") as mock_replace:
                    drain_regression_check.atomic_update_history(history_path, records)
                    
                    # Verify mkstemp called with correct params
                    mock_mkstemp.assert_called_once()
                    call_kwargs = mock_mkstemp.call_args[1]
                    assert call_kwargs["dir"] == history_path.parent
                    assert call_kwargs["prefix"] == ".drain_log_"
                    assert call_kwargs["suffix"] == ".tmp"
                    
                    # Verify os.replace called
                    mock_replace.assert_called_once_with(temp_path, history_path)
                    
                    # Verify correct content written
                    assert len(written_lines) == 2
                    assert '"id": 1' in written_lines[0]
                    assert '"id": 2' in written_lines[1]
    
    def test_cleans_up_tempfile_on_error(self, tmp_path: Path):
        """Temp file is cleaned up if write fails."""
        history_path = tmp_path / "drain_log.jsonl"
        temp_path = str(tmp_path / ".drain_log_test.tmp")
        
        with patch("drain_regression_check.tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.return_value = (999, temp_path)
            
            # Make fdopen fail
            with patch("drain_regression_check.os.fdopen", side_effect=OSError("write failed")):
                with patch("drain_regression_check.os.unlink") as mock_unlink:
                    with pytest.raises(OSError):
                        drain_regression_check.atomic_update_history(history_path, [])
                    
                    # Verify cleanup attempted
                    mock_unlink.assert_called_once_with(temp_path)


class TestNoThrashBehavior:
    """Test that reverted/not_needed records are never re-processed."""
    
    def test_skips_already_reverted_records(self):
        """Records with revert_status=reverted are never rechecked."""
        record = {
            "revert_status": "reverted",
            "revert_sha": "b" * 40,
            "timestamp": _iso(_utc_now() - timedelta(hours=2))  # Old enough
        }
        
        # should_check_regression must return False
        assert drain_regression_check.should_check_regression(record) is False
    
    def test_skips_not_needed_records(self):
        """Records marked not_needed are never rechecked."""
        record = {
            "revert_status": "not_needed",
            "revert_reason": "no_regression",
            "timestamp": _iso(_utc_now() - timedelta(hours=2))  # Old enough
        }
        
        assert drain_regression_check.should_check_regression(record) is False
    
    def test_only_processes_pending_records(self):
        """Only pending status records are eligible for processing."""
        statuses = ["reverted", "not_needed", "completed", None, ""]
        
        for status in statuses:
            record = {
                "timestamp": _iso(_utc_now() - timedelta(hours=1))
            }
            if status is not None:
                record["revert_status"] = status
            
            assert drain_regression_check.should_check_regression(record) is False
        
        # Only pending should return True (after grace period)
        pending_record = {
            "revert_status": "pending",
            "timestamp": _iso(_utc_now() - timedelta(hours=1))
        }
        assert drain_regression_check.should_check_regression(pending_record) is True