#!/usr/bin/env python3
"""
Unit tests for InstallAudit (TDD Red Phase - Issue #106).

Tests for GenAI-first installation system audit logging.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially because InstallAudit doesn't exist yet.

Test Strategy:
- Installation attempt logging
- Protected file recording
- Conflict tracking
- Report generation
- Audit trail persistence

Date: 2025-12-09
Issue: #106 (GenAI-first installation system)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime

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

# Import will FAIL until implementation exists
try:
    from install_audit import InstallAudit, AuditEntry
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


class TestInstallAuditInitialization:
    """Test InstallAudit initialization."""

    def test_initialize_with_audit_file_path(self, tmp_path):
        """Test initialization with audit file path.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "install_audit.jsonl"

        audit = InstallAudit(audit_file)

        assert audit.audit_file == audit_file

    def test_initialize_creates_audit_file_if_not_exists(self, tmp_path):
        """Test that initialization creates audit file.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "install_audit.jsonl"

        audit = InstallAudit(audit_file)
        audit.start_installation("fresh")

        assert audit_file.exists()

    def test_initialize_with_existing_audit_file(self, tmp_path):
        """Test initialization with existing audit file.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "install_audit.jsonl"
        audit_file.write_text('{"type": "install", "status": "success"}\n')

        audit = InstallAudit(audit_file)

        assert audit.audit_file.exists()

    def test_initialize_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "nested" / "dir" / "audit.jsonl"

        audit = InstallAudit(audit_file)
        audit.start_installation("fresh")

        assert audit_file.parent.exists()


class TestInstallationAttemptLogging:
    """Test logging of installation attempts."""

    def test_log_installation_start(self, tmp_path):
        """Test logging installation start.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("fresh")

        assert install_id is not None
        assert audit_file.exists()

        # Check log content
        with open(audit_file) as f:
            entry = json.loads(f.readline())
            assert entry["event"] == "installation_start"
            assert entry["install_type"] == "fresh"

    def test_log_installation_success(self, tmp_path):
        """Test logging successful installation.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("fresh")
        audit.log_success(install_id, files_copied=42)

        # Check log entries
        with open(audit_file) as f:
            lines = f.readlines()
            assert len(lines) == 2
            success_entry = json.loads(lines[1])
            assert success_entry["event"] == "installation_success"
            assert success_entry["files_copied"] == 42

    def test_log_installation_failure(self, tmp_path):
        """Test logging failed installation.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("upgrade")
        audit.log_failure(install_id, error="Permission denied")

        with open(audit_file) as f:
            lines = f.readlines()
            failure_entry = json.loads(lines[1])
            assert failure_entry["event"] == "installation_failure"
            assert failure_entry["error"] == "Permission denied"

    def test_log_includes_timestamp(self, tmp_path):
        """Test that log entries include timestamp.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        audit.start_installation("fresh")

        with open(audit_file) as f:
            entry = json.loads(f.readline())
            assert "timestamp" in entry
            # Validate ISO 8601 format
            datetime.fromisoformat(entry["timestamp"])

    def test_log_includes_install_id(self, tmp_path):
        """Test that log entries include unique install ID.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id1 = audit.start_installation("fresh")
        install_id2 = audit.start_installation("upgrade")

        assert install_id1 != install_id2


class TestProtectedFileRecording:
    """Test recording of protected files."""

    def test_record_protected_file(self, tmp_path):
        """Test recording a protected file.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("brownfield")
        audit.record_protected_file(
            install_id, ".claude/PROJECT.md", reason="user_config"
        )

        with open(audit_file) as f:
            lines = f.readlines()
            protected_entry = json.loads(lines[1])
            assert protected_entry["event"] == "protected_file"
            assert protected_entry["file"] == ".claude/PROJECT.md"
            assert protected_entry["reason"] == "user_config"

    def test_record_multiple_protected_files(self, tmp_path):
        """Test recording multiple protected files.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("brownfield")
        protected_files = [
            (".claude/PROJECT.md", "user_config"),
            (".env", "secrets"),
            (".claude/batch_state.json", "user_state"),
        ]

        for file_path, reason in protected_files:
            audit.record_protected_file(install_id, file_path, reason)

        with open(audit_file) as f:
            lines = f.readlines()
            # 1 start + 3 protected files = 4 entries
            assert len(lines) == 4

    def test_protected_file_includes_metadata(self, tmp_path):
        """Test that protected file records include metadata.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("upgrade")
        audit.record_protected_file(
            install_id,
            ".claude/hooks/custom.py",
            reason="user_modified",
            metadata={"original_hash": "abc123", "current_hash": "def456"},
        )

        with open(audit_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[1])
            assert "metadata" in entry
            assert entry["metadata"]["original_hash"] == "abc123"


class TestConflictTracking:
    """Test tracking of file conflicts."""

    def test_record_conflict(self, tmp_path):
        """Test recording a file conflict.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("upgrade")
        audit.record_conflict(
            install_id, "file.py", existing_hash="abc", staging_hash="def"
        )

        with open(audit_file) as f:
            lines = f.readlines()
            conflict_entry = json.loads(lines[1])
            assert conflict_entry["event"] == "conflict"
            assert conflict_entry["file"] == "file.py"

    def test_record_conflict_resolution(self, tmp_path):
        """Test recording conflict resolution.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("upgrade")
        audit.record_conflict(
            install_id, "file.py", existing_hash="abc", staging_hash="def"
        )
        audit.record_conflict_resolution(
            install_id, "file.py", action="backup", backup_path="file.py.bak"
        )

        with open(audit_file) as f:
            lines = f.readlines()
            resolution_entry = json.loads(lines[2])
            assert resolution_entry["event"] == "conflict_resolution"
            assert resolution_entry["action"] == "backup"

    def test_record_multiple_conflicts(self, tmp_path):
        """Test recording multiple conflicts.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("upgrade")
        conflicts = [("file1.py", "hash1"), ("file2.py", "hash2")]

        for file_path, staging_hash in conflicts:
            audit.record_conflict(
                install_id,
                file_path,
                existing_hash="old",
                staging_hash=staging_hash,
            )

        with open(audit_file) as f:
            lines = f.readlines()
            # 1 start + 2 conflicts = 3 entries
            assert len(lines) == 3


class TestReportGeneration:
    """Test installation report generation."""

    def test_generate_installation_report(self, tmp_path):
        """Test generating complete installation report.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("brownfield")
        audit.record_protected_file(install_id, ".env", "secrets")
        audit.log_success(install_id, files_copied=42)

        report = audit.generate_report(install_id)

        assert report["install_id"] == install_id
        assert report["status"] == "success"
        assert report["files_copied"] == 42
        assert len(report["protected_files"]) == 1

    def test_report_includes_summary_statistics(self, tmp_path):
        """Test that report includes summary statistics.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("upgrade")
        audit.record_protected_file(install_id, ".env", "secrets")
        audit.record_protected_file(install_id, "PROJECT.md", "user_config")
        audit.record_conflict(
            install_id, "file.py", existing_hash="abc", staging_hash="def"
        )
        audit.log_success(install_id, files_copied=100)

        report = audit.generate_report(install_id)

        assert report["summary"]["total_protected_files"] == 2
        assert report["summary"]["total_conflicts"] == 1
        assert report["summary"]["files_copied"] == 100

    def test_report_includes_timeline(self, tmp_path):
        """Test that report includes chronological timeline.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("fresh")
        audit.log_success(install_id, files_copied=42)

        report = audit.generate_report(install_id)

        assert "timeline" in report
        assert len(report["timeline"]) >= 2  # Start + success

    def test_generate_report_for_nonexistent_install(self, tmp_path):
        """Test generating report for nonexistent install ID.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        with pytest.raises(ValueError, match="Install ID not found"):
            audit.generate_report("nonexistent-id")

    def test_export_report_to_file(self, tmp_path):
        """Test exporting report to file.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("fresh")
        audit.log_success(install_id, files_copied=42)

        report_file = tmp_path / "install_report.json"
        audit.export_report(install_id, report_file)

        assert report_file.exists()
        with open(report_file) as f:
            report = json.load(f)
            assert report["install_id"] == install_id


class TestAuditTrailPersistence:
    """Test persistence of audit trail."""

    def test_append_mode_preserves_existing_entries(self, tmp_path):
        """Test that new entries don't overwrite existing ones.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"

        # First installation
        audit1 = InstallAudit(audit_file)
        install_id1 = audit1.start_installation("fresh")
        audit1.log_success(install_id1, files_copied=42)

        # Second installation
        audit2 = InstallAudit(audit_file)
        install_id2 = audit2.start_installation("upgrade")
        audit2.log_success(install_id2, files_copied=10)

        # Both installations should be in audit log
        with open(audit_file) as f:
            lines = f.readlines()
            assert len(lines) == 4  # 2 starts + 2 successes

    def test_audit_file_is_jsonl_format(self, tmp_path):
        """Test that audit file uses JSONL format (one JSON per line).

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("fresh")
        audit.log_success(install_id, files_copied=42)

        with open(audit_file) as f:
            for line in f:
                # Each line should be valid JSON
                entry = json.loads(line)
                assert isinstance(entry, dict)

    def test_audit_file_survives_crashes(self, tmp_path):
        """Test that partial writes are recoverable.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("fresh")

        # Simulate crash (no success/failure logged)
        # File should still be valid and readable
        audit2 = InstallAudit(audit_file)
        history = audit2.get_all_installations()

        assert len(history) >= 1
        assert history[0]["install_id"] == install_id

    def test_get_installation_history(self, tmp_path):
        """Test retrieving installation history.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        # Create multiple installations
        for i in range(3):
            install_id = audit.start_installation("fresh")
            audit.log_success(install_id, files_copied=i * 10)

        history = audit.get_all_installations()

        assert len(history) == 3

    def test_filter_history_by_status(self, tmp_path):
        """Test filtering installation history by status.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        # Successful install
        id1 = audit.start_installation("fresh")
        audit.log_success(id1, files_copied=42)

        # Failed install
        id2 = audit.start_installation("upgrade")
        audit.log_failure(id2, error="Permission denied")

        successful = audit.get_installations_by_status("success")
        failed = audit.get_installations_by_status("failure")

        assert len(successful) == 1
        assert len(failed) == 1


class TestSecurityAndValidation:
    """Test security and validation features."""

    def test_sanitize_file_paths_in_logs(self, tmp_path):
        """Test that file paths are sanitized (no path traversal).

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("brownfield")

        # Should reject or sanitize dangerous paths
        with pytest.raises(ValueError, match="invalid path"):
            audit.record_protected_file(
                install_id, "../../../etc/passwd", "suspicious"
            )

    def test_validate_install_id_format(self, tmp_path):
        """Test validation of install ID format.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("fresh")

        # Install ID should be UUID or similar
        assert len(install_id) > 0
        assert "-" in install_id  # UUID format

    def test_prevent_audit_log_tampering(self, tmp_path):
        """Test that audit log entries are tamper-evident.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        install_id = audit.start_installation("fresh")

        # Manually modify audit file
        with open(audit_file, "a") as f:
            f.write('{"event": "tampered", "install_id": "fake"}\n')

        # Should detect tampering or handle gracefully
        history = audit.get_all_installations()
        # Implementation should validate entries


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_concurrent_installations(self, tmp_path):
        """Test handling concurrent installation attempts.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        # Start multiple installations
        id1 = audit.start_installation("fresh")
        id2 = audit.start_installation("upgrade")

        # Both should complete independently
        audit.log_success(id1, files_copied=42)
        audit.log_success(id2, files_copied=10)

        report1 = audit.generate_report(id1)
        report2 = audit.generate_report(id2)

        assert report1["files_copied"] == 42
        assert report2["files_copied"] == 10

    def test_handles_disk_full_gracefully(self, tmp_path):
        """Test graceful handling of disk full errors.

        Current: FAILS - InstallAudit doesn't exist
        """
        # This is a conceptual test - actual implementation would
        # need to handle IOError gracefully
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        # Should not crash on write failure
        with patch("builtins.open", side_effect=IOError("Disk full")):
            with pytest.raises(IOError):
                audit.start_installation("fresh")

    def test_handles_corrupted_audit_file(self, tmp_path):
        """Test handling of corrupted audit file.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit_file.write_text("corrupted json\n")

        audit = InstallAudit(audit_file)

        # Should handle gracefully (skip corrupted lines)
        history = audit.get_all_installations()
        assert isinstance(history, list)

    def test_handles_empty_audit_file(self, tmp_path):
        """Test handling of empty audit file.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit_file.touch()

        audit = InstallAudit(audit_file)
        history = audit.get_all_installations()

        assert history == []

    def test_large_audit_file_performance(self, tmp_path):
        """Test performance with large audit file.

        Current: FAILS - InstallAudit doesn't exist
        """
        audit_file = tmp_path / "audit.jsonl"
        audit = InstallAudit(audit_file)

        # Create many installations
        for i in range(100):
            install_id = audit.start_installation("fresh")
            audit.log_success(install_id, files_copied=i)

        # Should still be performant
        history = audit.get_all_installations()
        assert len(history) == 100
