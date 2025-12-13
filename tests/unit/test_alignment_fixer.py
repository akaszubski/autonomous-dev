#!/usr/bin/env python3
"""
Unit tests for alignment_fixer.py library (Issue #129).

Tests bidirectional alignment sync between PROJECT.md, documentation, and code.

Test Strategy:
- Test section protection (GOALS, CONSTRAINTS, Out of Scope)
- Test proposable sections (SCOPE In Scope, ARCHITECTURE)
- Test consent workflow integration
- Test backup creation before modification
- Test atomic updates
- Test security validation (CWE-22 path traversal)
- Test proposal formatting and display
- Test approval/decline workflow
- Test PROJECT.md parsing and updates

Date: 2025-12-13
Issue: #129 (Bidirectional alignment sync)
Agent: test-master
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

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

from alignment_fixer import (
    AlignmentFixer,
    AlignmentFixerError,
    ProposedUpdate,
    PROTECTED_SECTIONS,
    PROPOSABLE_SECTIONS,
    PROTECTED_SCOPE_SUBSECTIONS,
    BIDIRECTIONAL_SYNC_CONSENT_KEY,
    check_bidirectional_sync_consent,
    record_bidirectional_sync_consent,
    propose_scope_addition,
    is_section_protected,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_project_dir(tmp_path):
    """Create temporary project directory with PROJECT.md."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create minimal PROJECT.md
    project_md = project_dir / "PROJECT.md"
    project_md.write_text("""# Project Context

## GOALS ⭐

**Primary Mission**: Test project for alignment fixer testing.

## SCOPE

**What's IN Scope** ✅ (Features we build):

- ✅ **Feature A** - First feature
- ✅ **Feature B** - Second feature

**What's OUT of Scope** ❌ (Features we avoid):

- ❌ **Feature X** - Explicitly excluded

## CONSTRAINTS

- **Constraint 1**: Some constraint
- **Constraint 2**: Another constraint

## ARCHITECTURE

**Agents**: 5 total
**Commands**: 3 active
**Hooks**: 10 total
""")

    return project_dir


@pytest.fixture
def temp_state_file(tmp_path):
    """Create temporary state file."""
    state_dir = tmp_path / ".autonomous-dev"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "user_state.json"


@pytest.fixture
def alignment_fixer(temp_project_dir, temp_state_file):
    """Create AlignmentFixer instance with temp directories."""
    return AlignmentFixer(temp_project_dir, temp_state_file)


# =============================================================================
# Test Protected Sections
# =============================================================================

class TestProtectedSections:
    """Test that protected sections cannot be auto-updated."""

    def test_goals_is_protected(self):
        """Test GOALS section is protected."""
        assert "GOALS" in PROTECTED_SECTIONS
        assert is_section_protected("GOALS")

    def test_constraints_is_protected(self):
        """Test CONSTRAINTS section is protected."""
        assert "CONSTRAINTS" in PROTECTED_SECTIONS
        assert is_section_protected("CONSTRAINTS")

    def test_out_of_scope_is_protected(self):
        """Test Out of Scope subsection is protected."""
        assert "Out of Scope" in PROTECTED_SCOPE_SUBSECTIONS
        assert is_section_protected("SCOPE", "Out of Scope")

    def test_scope_in_scope_is_not_protected(self):
        """Test SCOPE (In Scope) is not protected."""
        assert not is_section_protected("SCOPE", "In Scope")
        assert not is_section_protected("SCOPE")

    def test_architecture_is_not_protected(self):
        """Test ARCHITECTURE section is not protected."""
        assert not is_section_protected("ARCHITECTURE")


# =============================================================================
# Test Proposable Sections
# =============================================================================

class TestProposableSections:
    """Test that proposable sections can be updated with approval."""

    def test_scope_is_proposable(self):
        """Test SCOPE section is proposable."""
        assert "SCOPE" in PROPOSABLE_SECTIONS

    def test_architecture_is_proposable(self):
        """Test ARCHITECTURE section is proposable."""
        assert "ARCHITECTURE" in PROPOSABLE_SECTIONS

    def test_goals_not_proposable(self):
        """Test GOALS section is not proposable."""
        assert "GOALS" not in PROPOSABLE_SECTIONS

    def test_constraints_not_proposable(self):
        """Test CONSTRAINTS section is not proposable."""
        assert "CONSTRAINTS" not in PROPOSABLE_SECTIONS


# =============================================================================
# Test Proposal Creation
# =============================================================================

class TestProposalCreation:
    """Test creating proposals for PROJECT.md updates."""

    def test_propose_scope_addition(self, alignment_fixer):
        """Test proposing addition to SCOPE In Scope."""
        update = alignment_fixer.propose_update(
            section="SCOPE",
            subsection="In Scope",
            action="add",
            proposed_value="New Feature",
            reason="Implemented in this sprint",
        )

        assert update.section == "SCOPE"
        assert update.subsection == "In Scope"
        assert update.action == "add"
        assert update.proposed_value == "New Feature"
        assert update.reason == "Implemented in this sprint"
        assert not update.approved
        assert not update.declined

    def test_propose_architecture_update(self, alignment_fixer):
        """Test proposing update to ARCHITECTURE counts."""
        update = alignment_fixer.propose_update(
            section="ARCHITECTURE",
            subsection="Commands",
            action="update",
            current_value="3",
            proposed_value="4",
            reason="Added new command",
        )

        assert update.section == "ARCHITECTURE"
        assert update.action == "update"
        assert update.current_value == "3"
        assert update.proposed_value == "4"

    def test_cannot_propose_goals_update(self, alignment_fixer):
        """Test that GOALS updates are rejected."""
        with pytest.raises(AlignmentFixerError) as exc_info:
            alignment_fixer.propose_update(
                section="GOALS",
                action="update",
                proposed_value="New goal",
                reason="Want to change direction",
            )

        assert "GOALS" in str(exc_info.value)
        assert "cannot be proposed" in str(exc_info.value)

    def test_cannot_propose_constraints_update(self, alignment_fixer):
        """Test that CONSTRAINTS updates are rejected."""
        with pytest.raises(AlignmentFixerError) as exc_info:
            alignment_fixer.propose_update(
                section="CONSTRAINTS",
                action="add",
                proposed_value="New constraint",
                reason="Adding boundary",
            )

        assert "CONSTRAINTS" in str(exc_info.value)

    def test_cannot_propose_out_of_scope_update(self, alignment_fixer):
        """Test that Out of Scope updates are rejected."""
        with pytest.raises(AlignmentFixerError) as exc_info:
            alignment_fixer.propose_update(
                section="SCOPE",
                subsection="Out of Scope",
                action="remove",
                current_value="Feature X",
                proposed_value="",
                reason="Want to build it now",
            )

        assert "Out of Scope" in str(exc_info.value)
        assert "protected" in str(exc_info.value)


# =============================================================================
# Test Proposal Display
# =============================================================================

class TestProposalDisplay:
    """Test formatting proposals for user display."""

    def test_format_single_proposal(self, alignment_fixer):
        """Test formatting a single proposal."""
        alignment_fixer.propose_update(
            section="SCOPE",
            subsection="In Scope",
            action="add",
            proposed_value="New Feature",
            reason="Implemented",
        )

        display = alignment_fixer.format_proposals_for_display()

        assert "Proposed PROJECT.md updates:" in display
        assert "SCOPE (In Scope)" in display
        assert "add" in display
        assert "New Feature" in display

    def test_format_multiple_proposals(self, alignment_fixer):
        """Test formatting multiple proposals."""
        alignment_fixer.propose_update(
            section="SCOPE",
            subsection="In Scope",
            action="add",
            proposed_value="Feature 1",
            reason="First feature",
        )
        alignment_fixer.propose_update(
            section="ARCHITECTURE",
            subsection="Commands",
            action="update",
            current_value="3",
            proposed_value="4",
            reason="Added command",
        )

        display = alignment_fixer.format_proposals_for_display()

        assert "1." in display
        assert "2." in display
        assert "Feature 1" in display
        assert "Commands" in display

    def test_format_empty_proposals(self, alignment_fixer):
        """Test formatting when no proposals exist."""
        display = alignment_fixer.format_proposals_for_display()
        assert "No pending PROJECT.md updates" in display


# =============================================================================
# Test Approval/Decline Workflow
# =============================================================================

class TestApprovalWorkflow:
    """Test approval and decline workflow."""

    def test_mark_approved(self, alignment_fixer):
        """Test marking proposals as approved."""
        alignment_fixer.propose_update(
            section="SCOPE",
            action="add",
            proposed_value="Feature 1",
            reason="Reason 1",
        )
        alignment_fixer.propose_update(
            section="SCOPE",
            action="add",
            proposed_value="Feature 2",
            reason="Reason 2",
        )

        count = alignment_fixer.mark_approved([1])

        assert count == 1
        assert alignment_fixer.pending_updates[0].approved
        assert not alignment_fixer.pending_updates[1].approved

    def test_mark_declined(self, alignment_fixer):
        """Test marking proposals as declined."""
        alignment_fixer.propose_update(
            section="SCOPE",
            action="add",
            proposed_value="Feature 1",
            reason="Reason 1",
        )

        count = alignment_fixer.mark_declined([1])

        assert count == 1
        assert alignment_fixer.pending_updates[0].declined

    def test_mark_all_approved(self, alignment_fixer):
        """Test marking all proposals as approved."""
        for i in range(3):
            alignment_fixer.propose_update(
                section="SCOPE",
                action="add",
                proposed_value=f"Feature {i}",
                reason=f"Reason {i}",
            )

        count = alignment_fixer.mark_approved([1, 2, 3])

        assert count == 3
        assert all(u.approved for u in alignment_fixer.pending_updates)


# =============================================================================
# Test Backup Creation
# =============================================================================

class TestBackupCreation:
    """Test backup creation before modification."""

    def test_backup_created(self, alignment_fixer):
        """Test that backup is created before applying updates."""
        backup_path = alignment_fixer.create_backup()

        assert backup_path.exists()
        assert "PROJECT.md" in backup_path.name
        assert ".backup" in backup_path.name

    def test_backup_content_matches(self, alignment_fixer):
        """Test backup content matches original."""
        original_content = alignment_fixer.project_md_path.read_text()
        backup_path = alignment_fixer.create_backup()

        backup_content = backup_path.read_text()
        assert backup_content == original_content

    def test_backup_permissions(self, alignment_fixer):
        """Test backup has secure permissions."""
        backup_path = alignment_fixer.create_backup()

        mode = backup_path.stat().st_mode & 0o777
        assert mode == 0o600


# =============================================================================
# Test Consent Workflow
# =============================================================================

class TestConsentWorkflow:
    """Test consent workflow integration."""

    def test_consent_not_yet_given(self, temp_state_file):
        """Test consent returns None when not yet asked."""
        consent = check_bidirectional_sync_consent(temp_state_file)
        assert consent is None

    def test_record_consent_enabled(self, temp_state_file):
        """Test recording consent as enabled."""
        record_bidirectional_sync_consent(True, temp_state_file)

        consent = check_bidirectional_sync_consent(temp_state_file)
        assert consent is True

    def test_record_consent_disabled(self, temp_state_file):
        """Test recording consent as disabled."""
        record_bidirectional_sync_consent(False, temp_state_file)

        consent = check_bidirectional_sync_consent(temp_state_file)
        assert consent is False

    def test_env_variable_override_enabled(self, alignment_fixer):
        """Test environment variable overrides consent."""
        with patch.dict(os.environ, {"BIDIRECTIONAL_SYNC_ENABLED": "true"}):
            assert alignment_fixer.is_consent_enabled() is True

    def test_env_variable_override_disabled(self, alignment_fixer):
        """Test environment variable can disable consent."""
        with patch.dict(os.environ, {"BIDIRECTIONAL_SYNC_ENABLED": "false"}):
            assert alignment_fixer.is_consent_enabled() is False


# =============================================================================
# Test Security (CWE-22 Path Traversal)
# =============================================================================

class TestSecurity:
    """Test security validation."""

    def test_path_traversal_blocked(self, tmp_path, temp_state_file):
        """Test path traversal is blocked."""
        with pytest.raises(AlignmentFixerError) as exc_info:
            AlignmentFixer(tmp_path / ".." / "etc", temp_state_file)

        assert "Path traversal" in str(exc_info.value)

    def test_invalid_project_root(self, tmp_path, temp_state_file):
        """Test invalid project root raises error."""
        with pytest.raises(AlignmentFixerError) as exc_info:
            AlignmentFixer(tmp_path / "nonexistent", temp_state_file)

        assert "not a directory" in str(exc_info.value)

    def test_missing_project_md(self, tmp_path, temp_state_file):
        """Test missing PROJECT.md raises error."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with pytest.raises(AlignmentFixerError) as exc_info:
            AlignmentFixer(empty_dir, temp_state_file)

        assert "PROJECT.md not found" in str(exc_info.value)


# =============================================================================
# Test ProposedUpdate Class
# =============================================================================

class TestProposedUpdate:
    """Test ProposedUpdate dataclass."""

    def test_to_dict(self):
        """Test ProposedUpdate serialization to dict."""
        update = ProposedUpdate(
            section="SCOPE",
            subsection="In Scope",
            action="add",
            current_value=None,
            proposed_value="New Feature",
            reason="Testing",
        )

        d = update.to_dict()

        assert d["section"] == "SCOPE"
        assert d["subsection"] == "In Scope"
        assert d["action"] == "add"
        assert d["proposed_value"] == "New Feature"
        assert d["approved"] is False
        assert d["declined"] is False

    def test_repr(self):
        """Test ProposedUpdate string representation."""
        update = ProposedUpdate(
            section="SCOPE",
            subsection="In Scope",
            action="add",
            current_value=None,
            proposed_value="Feature",
            reason="Test",
        )

        repr_str = repr(update)

        assert "ProposedUpdate" in repr_str
        assert "SCOPE" in repr_str


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_propose_scope_addition_convenience(self, temp_project_dir):
        """Test propose_scope_addition convenience function."""
        update = propose_scope_addition(
            project_root=temp_project_dir,
            feature_name="New Command",
            reason="Added /new-cmd",
        )

        assert update.section == "SCOPE"
        assert update.subsection == "In Scope"
        assert update.action == "add"
        assert update.proposed_value == "New Command"

    def test_is_section_protected_function(self):
        """Test is_section_protected function."""
        assert is_section_protected("GOALS") is True
        assert is_section_protected("CONSTRAINTS") is True
        assert is_section_protected("SCOPE", "Out of Scope") is True
        assert is_section_protected("SCOPE", "In Scope") is False
        assert is_section_protected("ARCHITECTURE") is False


# =============================================================================
# Test Apply Updates
# =============================================================================

class TestApplyUpdates:
    """Test applying approved updates to PROJECT.md."""

    def test_apply_no_approved_updates(self, alignment_fixer):
        """Test applying when nothing is approved."""
        alignment_fixer.propose_update(
            section="SCOPE",
            action="add",
            proposed_value="Feature",
            reason="Test",
        )
        # Don't approve it

        count, descriptions = alignment_fixer.apply_approved_updates()

        assert count == 0
        assert descriptions == []

    def test_apply_creates_backup(self, alignment_fixer):
        """Test that applying updates creates backup first."""
        alignment_fixer.propose_update(
            section="SCOPE",
            action="add",
            proposed_value="New Feature",
            reason="Test",
        )
        alignment_fixer.mark_approved([1])

        alignment_fixer.apply_approved_updates()

        assert alignment_fixer.backup_path is not None
        assert alignment_fixer.backup_path.exists()

    def test_applied_updates_removed_from_pending(self, alignment_fixer):
        """Test that applied updates are removed from pending list."""
        alignment_fixer.propose_update(
            section="SCOPE",
            action="add",
            proposed_value="Feature 1",
            reason="Test 1",
        )
        alignment_fixer.propose_update(
            section="SCOPE",
            action="add",
            proposed_value="Feature 2",
            reason="Test 2",
        )
        alignment_fixer.mark_approved([1])  # Only approve first

        count, _ = alignment_fixer.apply_approved_updates()

        assert count == 1
        # Only unapproved update should remain
        assert len(alignment_fixer.pending_updates) == 1
        assert alignment_fixer.pending_updates[0].proposed_value == "Feature 2"
