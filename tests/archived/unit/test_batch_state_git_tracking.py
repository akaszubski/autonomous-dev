#!/usr/bin/env python3
"""
Unit tests for batch state git tracking functionality (Issue #93).

Tests the git_operations field in BatchState schema for tracking per-feature
git operation status during batch processing.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (missing git_operations field).

Test Strategy:
- Test git_operations field initialization
- Test git operation tracking (commit, push, PR creation)
- Test git status persistence (save/load roundtrip)
- Test git failure tracking
- Test git operation updates
- Test schema validation for git_operations
- Test backward compatibility (old state files without git_operations)
- Test git_operations serialization/deserialization

Date: 2025-12-06
Issue: #93 (Add auto-commit to batch workflow)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected - no implementation yet)
"""

import json
import sys
import pytest
from pathlib import Path
from typing import Dict, Any
from dataclasses import asdict
from datetime import datetime

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

# Import will fail - implementation doesn't exist yet (TDD!)
try:
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        load_batch_state,
        save_batch_state,
        update_batch_progress,
        record_git_operation,
        get_feature_git_status,
        BatchStateError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary directory for state files."""
    state_dir = tmp_path / ".claude"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@pytest.fixture
def sample_features():
    """Sample feature list for testing."""
    return [
        "Add user authentication",
        "Implement password reset",
        "Add email verification",
    ]


# =============================================================================
# Test BatchState git_operations Field Initialization
# =============================================================================

class TestGitOperationsFieldInitialization:
    """Test git_operations field in BatchState dataclass."""

    def test_batch_state_has_git_operations_field(self, temp_state_dir, sample_features):
        """Test BatchState dataclass includes git_operations field."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Should have git_operations field
        assert hasattr(state, 'git_operations')

    def test_git_operations_field_initializes_as_empty_dict(self, temp_state_dir, sample_features):
        """Test git_operations field initializes as empty dictionary."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Should be empty dict initially
        assert state.git_operations == {}

    def test_git_operations_field_type_is_dict(self, temp_state_dir, sample_features):
        """Test git_operations field type is Dict[int, Dict[str, Any]]."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Should be dictionary type
        assert isinstance(state.git_operations, dict)


# =============================================================================
# Test Git Operation Tracking
# =============================================================================

class TestGitOperationTracking:
    """Test recording git operations for features."""

    def test_record_commit_operation(self, temp_state_dir, sample_features):
        """Test recording successful commit operation."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record commit for feature index 0
        updated_state = record_git_operation(
            state,
            feature_index=0,
            operation='commit',
            success=True,
            commit_sha='abc123def456',
            branch='feature/user-auth'
        )

        # Should have git operation recorded
        assert 0 in updated_state.git_operations
        assert updated_state.git_operations[0]['commit']['success'] is True
        assert updated_state.git_operations[0]['commit']['sha'] == 'abc123def456'
        assert updated_state.git_operations[0]['commit']['branch'] == 'feature/user-auth'

    def test_record_push_operation(self, temp_state_dir, sample_features):
        """Test recording successful push operation."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record push for feature index 0
        updated_state = record_git_operation(
            state,
            feature_index=0,
            operation='push',
            success=True,
            remote='origin',
            branch='feature/user-auth'
        )

        # Should have push operation recorded
        assert 0 in updated_state.git_operations
        assert updated_state.git_operations[0]['push']['success'] is True
        assert updated_state.git_operations[0]['push']['remote'] == 'origin'
        assert updated_state.git_operations[0]['push']['branch'] == 'feature/user-auth'

    def test_record_pr_creation(self, temp_state_dir, sample_features):
        """Test recording successful PR creation."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record PR creation for feature index 0
        updated_state = record_git_operation(
            state,
            feature_index=0,
            operation='pr',
            success=True,
            pr_number=123,
            pr_url='https://github.com/user/repo/pull/123'
        )

        # Should have PR creation recorded
        assert 0 in updated_state.git_operations
        assert updated_state.git_operations[0]['pr']['success'] is True
        assert updated_state.git_operations[0]['pr']['number'] == 123
        assert updated_state.git_operations[0]['pr']['url'] == 'https://github.com/user/repo/pull/123'

    def test_record_multiple_operations_same_feature(self, temp_state_dir, sample_features):
        """Test recording multiple git operations for same feature."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record commit
        state = record_git_operation(
            state,
            feature_index=0,
            operation='commit',
            success=True,
            commit_sha='abc123'
        )

        # Record push
        state = record_git_operation(
            state,
            feature_index=0,
            operation='push',
            success=True,
            remote='origin'
        )

        # Record PR
        state = record_git_operation(
            state,
            feature_index=0,
            operation='pr',
            success=True,
            pr_number=123
        )

        # Should have all three operations
        assert 'commit' in state.git_operations[0]
        assert 'push' in state.git_operations[0]
        assert 'pr' in state.git_operations[0]


# =============================================================================
# Test Git Failure Tracking
# =============================================================================

class TestGitFailureTracking:
    """Test tracking git operation failures."""

    def test_record_commit_failure(self, temp_state_dir, sample_features):
        """Test recording commit failure with error message."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record failed commit
        updated_state = record_git_operation(
            state,
            feature_index=0,
            operation='commit',
            success=False,
            error_message='No changes to commit'
        )

        # Should have failure recorded
        assert updated_state.git_operations[0]['commit']['success'] is False
        assert 'No changes to commit' in updated_state.git_operations[0]['commit']['error']

    def test_record_push_failure_network_error(self, temp_state_dir, sample_features):
        """Test recording push failure due to network error."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record failed push
        updated_state = record_git_operation(
            state,
            feature_index=0,
            operation='push',
            success=False,
            error_message='Network unreachable'
        )

        # Should have network failure recorded
        assert updated_state.git_operations[0]['push']['success'] is False
        assert 'Network unreachable' in updated_state.git_operations[0]['push']['error']

    def test_record_pr_failure_merge_conflict(self, temp_state_dir, sample_features):
        """Test recording PR creation failure due to merge conflict."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record failed PR creation
        updated_state = record_git_operation(
            state,
            feature_index=0,
            operation='pr',
            success=False,
            error_message='Merge conflict detected'
        )

        # Should have merge conflict recorded
        assert updated_state.git_operations[0]['pr']['success'] is False
        assert 'Merge conflict' in updated_state.git_operations[0]['pr']['error']


# =============================================================================
# Test Git Status Persistence
# =============================================================================

class TestGitStatusPersistence:
    """Test git_operations field persists across save/load."""

    def test_save_load_roundtrip_with_git_operations(self, temp_state_dir, sample_features):
        """Test git_operations field survives save/load roundtrip."""
        state_file = temp_state_dir / "batch_state.json"

        # Create state with git operations
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(state_file)
        )

        # Record git operations
        state = record_git_operation(
            state,
            feature_index=0,
            operation='commit',
            success=True,
            commit_sha='abc123'
        )

        state = record_git_operation(
            state,
            feature_index=0,
            operation='push',
            success=True,
            remote='origin'
        )

        # Save state
        save_batch_state(str(state_file), state)

        # Load state
        loaded_state = load_batch_state(str(state_file))

        # Git operations should match
        assert loaded_state.git_operations == state.git_operations
        assert loaded_state.git_operations[0]['commit']['sha'] == 'abc123'
        assert loaded_state.git_operations[0]['push']['remote'] == 'origin'

    def test_json_serialization_preserves_git_operations(self, temp_state_dir, sample_features):
        """Test JSON serialization/deserialization preserves git_operations."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record git operation
        state = record_git_operation(
            state,
            feature_index=0,
            operation='commit',
            success=True,
            commit_sha='def456'
        )

        # Convert to dict and JSON
        state_dict = state.to_dict()
        json_str = json.dumps(state_dict)

        # Parse back
        parsed = json.loads(json_str)

        # Git operations should be present
        assert 'git_operations' in parsed
        assert '0' in parsed['git_operations'] or 0 in parsed['git_operations']


# =============================================================================
# Test Backward Compatibility
# =============================================================================

class TestBackwardCompatibility:
    """Test loading old state files without git_operations field."""

    def test_load_state_without_git_operations_field(self, temp_state_dir):
        """Test loading old state file without git_operations field."""
        state_file = temp_state_dir / "batch_state.json"

        # Create old-format state (no git_operations)
        old_state = {
            "batch_id": "batch-123",
            "features_file": "/path/to/features.txt",
            "total_features": 3,
            "features": ["feature 1", "feature 2", "feature 3"],
            "current_index": 1,
            "completed_features": [0],
            "failed_features": [],
            "status": "in_progress"
        }

        # Write old-format state
        state_file.write_text(json.dumps(old_state))

        # Should load without error and initialize git_operations as empty dict
        loaded_state = load_batch_state(str(state_file))
        assert hasattr(loaded_state, 'git_operations')
        assert loaded_state.git_operations == {}


# =============================================================================
# Test Git Status Queries
# =============================================================================

class TestGitStatusQueries:
    """Test querying git operation status for features."""

    def test_get_feature_git_status_successful_commit(self, temp_state_dir, sample_features):
        """Test retrieving git status for feature with successful commit."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Record commit
        state = record_git_operation(
            state,
            feature_index=0,
            operation='commit',
            success=True,
            commit_sha='xyz789'
        )

        # Get status
        status = get_feature_git_status(state, feature_index=0)

        assert status is not None
        assert status['commit']['success'] is True
        assert status['commit']['sha'] == 'xyz789'

    def test_get_feature_git_status_no_operations(self, temp_state_dir, sample_features):
        """Test retrieving git status for feature with no operations."""
        state = create_batch_state(
            features_file=str(temp_state_dir / "features.txt"),
            features=sample_features,
            state_file=str(temp_state_dir / "batch_state.json")
        )

        # Get status for feature with no git operations
        status = get_feature_git_status(state, feature_index=0)

        # Should return None or empty dict
        assert status is None or status == {}
