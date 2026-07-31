#!/usr/bin/env python3
"""Tests for cloud_drain_telemetry hook (Issue #1437)."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import sys

sys.path.insert(0, "plugins/autonomous-dev/hooks")
from cloud_drain_telemetry import (
    should_emit_telemetry_commit,
    append_to_cloud_runs_jsonl,
    create_telemetry_commit,
)


class TestShouldEmitTelemetryCommit:
    """Test the decision logic for telemetry commit suppression."""
    
    def test_no_drainable_cluster_suppressed(self):
        """no_drainable_cluster should NOT emit a telemetry commit."""
        assert not should_emit_telemetry_commit("no_drainable_cluster")
    
    def test_queue_empty_suppressed(self):
        """queue_empty should NOT emit a telemetry commit."""
        assert not should_emit_telemetry_commit("queue_empty")
    
    def test_all_clusters_high_severity_suppressed(self):
        """all_clusters_high_severity should NOT emit a telemetry commit."""
        assert not should_emit_telemetry_commit("all_clusters_high_severity")
    
    def test_commit_landed_emitted(self):
        """commit_landed SHOULD emit a telemetry commit (real event)."""
        assert should_emit_telemetry_commit("commit_landed")
    
    def test_implementer_error_emitted(self):
        """implementer_error SHOULD emit a telemetry commit (real event)."""
        assert should_emit_telemetry_commit("implementer_error")
    
    def test_slash_command_tool_unavailable_emitted(self):
        """slash_command_tool_unavailable SHOULD emit a telemetry commit."""
        assert should_emit_telemetry_commit("slash_command_tool_unavailable")
    
    def test_gh_cli_unavailable_emitted(self):
        """gh_cli_unavailable SHOULD emit a telemetry commit."""
        assert should_emit_telemetry_commit("gh_cli_unavailable")
    
    def test_unknown_reason_emitted(self):
        """Unknown exit reasons should emit commits (fail-open)."""
        assert should_emit_telemetry_commit("some_new_reason")


class TestAppendToCloudRunsJsonl:
    """Test JSONL logging (always happens regardless of commit decision)."""
    
    def test_jsonl_created_for_no_drainable_cluster(self):
        """JSONL should be updated even when commit is suppressed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            append_to_cloud_runs_jsonl(
                fire_type="FIRE_END",
                exit_reason="no_drainable_cluster",
                repo_root=repo_root,
            )
            
            log_path = repo_root / ".claude" / "logs" / "cloud-runs.jsonl"
            assert log_path.exists()
            
            with open(log_path) as f:
                entry = json.loads(f.read().strip())
            
            assert entry["fire_type"] == "FIRE_END"
            assert entry["exit_reason"] == "no_drainable_cluster"
            assert entry["suppressed_commit"] is True
    
    def test_jsonl_created_for_commit_landed(self):
        """JSONL should be updated when commit is emitted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            append_to_cloud_runs_jsonl(
                fire_type="FIRE_END",
                cluster="1234,5678",
                exit_reason="commit_landed",
                repo_root=repo_root,
            )
            
            log_path = repo_root / ".claude" / "logs" / "cloud-runs.jsonl"
            assert log_path.exists()
            
            with open(log_path) as f:
                entry = json.loads(f.read().strip())
            
            assert entry["fire_type"] == "FIRE_END"
            assert entry["cluster"] == "1234,5678"
            assert entry["exit_reason"] == "commit_landed"
            assert entry["suppressed_commit"] is False


class TestCreateTelemetryCommit:
    """Test the full telemetry commit creation flow."""
    
    @patch("subprocess.run")
    def test_no_drainable_cluster_no_commit(self, mock_run):
        """no_drainable_cluster should update JSONL but NOT create git commit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            result = create_telemetry_commit(
                fire_type="FIRE_END",
                exit_reason="no_drainable_cluster",
                repo_root=repo_root,
            )
            
            # Should return False (commit suppressed)
            assert result is False
            
            # Should NOT call git commands
            mock_run.assert_not_called()
            
            # Should still update JSONL
            log_path = repo_root / ".claude" / "logs" / "cloud-runs.jsonl"
            assert log_path.exists()
    
    @patch("subprocess.run")
    def test_commit_landed_creates_commit(self, mock_run):
        """commit_landed should update JSONL AND create git commit."""
        mock_run.return_value = MagicMock(returncode=0)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            result = create_telemetry_commit(
                fire_type="FIRE_END",
                cluster="1234,5678",
                exit_reason="commit_landed",
                repo_root=repo_root,
            )
            
            # Should return True (commit created)
            assert result is True
            
            # Should call git add and git commit
            assert mock_run.call_count == 2
            
            # First call: git add
            add_call = mock_run.call_args_list[0]
            assert add_call[0][0][0] == "git"
            assert add_call[0][0][1] == "add"
            assert ".claude/logs/cloud-runs.jsonl" in add_call[0][0][2]
            
            # Second call: git commit
            commit_call = mock_run.call_args_list[1]
            assert commit_call[0][0][0] == "git"
            assert commit_call[0][0][1] == "commit"
            assert "telemetry(cloud-drain): FIRE_END" in commit_call[0][0][3]
            assert "cluster=1234,5678" in commit_call[0][0][3]
            
            # Should also update JSONL
            log_path = repo_root / ".claude" / "logs" / "cloud-runs.jsonl"
            assert log_path.exists()
    
    @patch("subprocess.run")
    def test_git_failure_returns_false(self, mock_run):
        """Git command failure should return False but still update JSONL."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            result = create_telemetry_commit(
                fire_type="FIRE_END",
                exit_reason="commit_landed",
                repo_root=repo_root,
            )
            
            # Should return False (git failed)
            assert result is False
            
            # Should still update JSONL
            log_path = repo_root / ".claude" / "logs" / "cloud-runs.jsonl"
            assert log_path.exists()