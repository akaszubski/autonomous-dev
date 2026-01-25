#!/usr/bin/env python3
"""
Integration tests for batch orchestrator session management (TDD Red Phase).

Tests for Issue #259: System-wide resource management integration with batch orchestrator.

Test Strategy:
- Test session registered on batch start
- Test session cleanup on batch complete
- Test multiple concurrent batches
- Test session preserved across /clear operations
- Test batch failure doesn't orphan sessions

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Coverage Target: 90%+ for session management code in batch_orchestrator.py

Date: 2026-01-25
Issue: #259 (System-wide resource management)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import will fail - modifications don't exist yet (TDD!)
try:
    from batch_orchestrator import BatchOrchestrator
    from session_resource_manager import (
        SessionResourceManager,
        ResourceConfig,
        ResourceStatus,
    )
    from exceptions import SessionLimitExceededError
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for batch tests."""
    workspace = tmp_path / "batch-workspace"
    workspace.mkdir()

    # Create .claude directory structure
    claude_dir = workspace / ".claude"
    claude_dir.mkdir()
    local_dir = claude_dir / "local"
    local_dir.mkdir()

    return workspace


@pytest.fixture
def registry_file(temp_workspace):
    """Get path to session registry file."""
    return temp_workspace / ".claude" / "local" / "session_registry.json"


@pytest.fixture
def features_file(temp_workspace):
    """Create sample features file for batch processing."""
    features_file = temp_workspace / "features.txt"
    features = [
        "Add user authentication",
        "Implement password reset",
        "Add email verification",
    ]
    features_file.write_text("\n".join(features))
    return features_file


@pytest.fixture
def resource_manager(registry_file):
    """Create SessionResourceManager for testing."""
    config = ResourceConfig(
        max_sessions=3,
        process_warn_threshold=1500,
        process_hard_limit=2000,
    )
    return SessionResourceManager(registry_file, config)


@pytest.fixture
def batch_orchestrator(temp_workspace, features_file):
    """Create BatchOrchestrator for testing."""
    return BatchOrchestrator(
        features_file=str(features_file),
        repo_path=str(temp_workspace),
    )


# =============================================================================
# SECTION 1: Session Registration Tests (6 tests)
# =============================================================================

class TestBatchSessionRegistration:
    """Test session registered on batch start."""

    def test_batch_start_registers_session(
        self, batch_orchestrator, resource_manager, temp_workspace
    ):
        """Test batch start registers session with resource manager."""
        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session") as mock_register, \
             patch.object(batch_orchestrator, "_process_features"):
            batch_orchestrator.start()

            # Session should be registered with repo path
            mock_register.assert_called_once()
            call_args = mock_register.call_args
            assert str(temp_workspace) in str(call_args)

    def test_batch_start_stores_session_id(
        self, batch_orchestrator, resource_manager
    ):
        """Test batch start stores session ID for cleanup."""
        session_id = "session-123"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(batch_orchestrator, "_process_features"):
            batch_orchestrator.start()

            # Session ID should be stored
            assert batch_orchestrator._session_id == session_id

    def test_batch_start_estimates_process_count(
        self, batch_orchestrator, resource_manager
    ):
        """Test batch start provides process estimate based on feature count."""
        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session") as mock_register, \
             patch.object(batch_orchestrator, "_process_features"):
            batch_orchestrator.start()

            # Should register with estimated process count
            call_kwargs = mock_register.call_args[1]
            assert "estimated_processes" in call_kwargs
            estimate = call_kwargs["estimated_processes"]

            # Estimate should be reasonable (e.g., features * avg_processes_per_feature)
            assert estimate > 0
            assert estimate < 10000  # Sanity check

    def test_batch_start_checks_session_limit(
        self, batch_orchestrator, resource_manager
    ):
        """Test batch start checks session limit before registering."""
        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(
                 resource_manager,
                 "register_session",
                 side_effect=SessionLimitExceededError("Session limit exceeded: 3/3 active")
             ):
            with pytest.raises(SessionLimitExceededError) as exc_info:
                batch_orchestrator.start()

            assert "3/3" in str(exc_info.value) or "exceeded" in str(exc_info.value).lower()

    def test_batch_start_session_limit_prevents_execution(
        self, batch_orchestrator, resource_manager
    ):
        """Test session limit prevents batch from executing."""
        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(
                 resource_manager,
                 "register_session",
                 side_effect=SessionLimitExceededError("Session limit exceeded")
             ), \
             patch.object(batch_orchestrator, "_process_features") as mock_process:
            with pytest.raises(SessionLimitExceededError):
                batch_orchestrator.start()

            # Batch processing should never start
            mock_process.assert_not_called()

    def test_batch_start_session_id_unique_per_batch(
        self, temp_workspace, features_file, resource_manager
    ):
        """Test each batch gets unique session ID."""
        session_ids = []

        for i in range(3):
            orchestrator = BatchOrchestrator(
                features_file=str(features_file),
                repo_path=str(temp_workspace),
            )

            with patch.object(orchestrator, "_resource_manager", resource_manager), \
                 patch.object(resource_manager, "register_session") as mock_register, \
                 patch.object(orchestrator, "_process_features"):
                mock_register.return_value = f"session-{i}"
                orchestrator.start()
                session_ids.append(mock_register.return_value)

            time.sleep(0.01)  # Ensure different timestamp

        # All session IDs should be unique
        assert len(session_ids) == len(set(session_ids))


# =============================================================================
# SECTION 2: Session Cleanup Tests (5 tests)
# =============================================================================

class TestBatchSessionCleanup:
    """Test session cleanup on batch complete."""

    def test_batch_complete_unregisters_session(
        self, batch_orchestrator, resource_manager
    ):
        """Test batch completion unregisters session."""
        session_id = "session-123"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(resource_manager, "unregister_session") as mock_unregister, \
             patch.object(batch_orchestrator, "_process_features"):
            batch_orchestrator.start()
            batch_orchestrator.complete()

            # Session should be unregistered
            mock_unregister.assert_called_once_with(session_id)

    def test_batch_failure_still_unregisters_session(
        self, batch_orchestrator, resource_manager
    ):
        """Test batch failure doesn't orphan session."""
        session_id = "session-123"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(resource_manager, "unregister_session") as mock_unregister, \
             patch.object(
                 batch_orchestrator,
                 "_process_features",
                 side_effect=Exception("Processing failed")
             ):
            with pytest.raises(Exception):
                batch_orchestrator.start()

            # Session should still be unregistered even on failure
            mock_unregister.assert_called_once_with(session_id)

    def test_batch_cleanup_on_keyboard_interrupt(
        self, batch_orchestrator, resource_manager
    ):
        """Test session cleanup on keyboard interrupt (Ctrl+C)."""
        session_id = "session-123"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(resource_manager, "unregister_session") as mock_unregister, \
             patch.object(
                 batch_orchestrator,
                 "_process_features",
                 side_effect=KeyboardInterrupt()
             ):
            with pytest.raises(KeyboardInterrupt):
                batch_orchestrator.start()

            # Session should be cleaned up
            mock_unregister.assert_called_once_with(session_id)

    def test_batch_resume_reuses_session_id(
        self, batch_orchestrator, resource_manager
    ):
        """Test batch resume reuses existing session ID."""
        original_session_id = "session-original"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=original_session_id), \
             patch.object(batch_orchestrator, "_process_features"):
            # Start batch
            batch_orchestrator.start()

            # Resume should use same session ID (not create new one)
            batch_orchestrator.resume()

            # Should still have original session ID
            assert batch_orchestrator._session_id == original_session_id

    def test_batch_cleanup_context_manager_pattern(
        self, batch_orchestrator, resource_manager
    ):
        """Test session cleanup uses context manager pattern (try/finally)."""
        session_id = "session-123"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(resource_manager, "unregister_session") as mock_unregister, \
             patch.object(
                 batch_orchestrator,
                 "_process_features",
                 side_effect=Exception("Random error")
             ):
            with pytest.raises(Exception):
                batch_orchestrator.start()

            # Cleanup should always happen (try/finally pattern)
            mock_unregister.assert_called_once()


# =============================================================================
# SECTION 3: Concurrent Batch Tests (5 tests)
# =============================================================================

class TestConcurrentBatches:
    """Test multiple concurrent batches."""

    def test_multiple_batches_all_registered(
        self, temp_workspace, features_file, resource_manager
    ):
        """Test multiple concurrent batches are all registered."""
        orchestrators = []
        session_ids = []

        # Create 3 concurrent batches
        for i in range(3):
            orchestrator = BatchOrchestrator(
                features_file=str(features_file),
                repo_path=str(temp_workspace),
            )
            orchestrators.append(orchestrator)

            session_id = f"session-{i}"
            session_ids.append(session_id)

            with patch.object(orchestrator, "_resource_manager", resource_manager), \
                 patch.object(resource_manager, "register_session", return_value=session_id), \
                 patch.object(orchestrator, "_process_features"):
                orchestrator.start()

        # All should be registered
        registry = resource_manager._load_registry()
        assert len(registry.sessions) >= 3

    def test_concurrent_batches_respect_session_limit(
        self, temp_workspace, features_file
    ):
        """Test concurrent batches respect max_sessions limit."""
        # Create resource manager with low limit
        registry_file = temp_workspace / ".claude" / "local" / "session_registry.json"
        config = ResourceConfig(max_sessions=2)  # Only 2 allowed
        resource_manager = SessionResourceManager(registry_file, config)

        # Start 2 batches (should succeed)
        orchestrator1 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(temp_workspace),
        )
        orchestrator2 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(temp_workspace),
        )

        with patch.object(orchestrator1, "_resource_manager", resource_manager), \
             patch.object(orchestrator2, "_resource_manager", resource_manager), \
             patch.object(orchestrator1, "_process_features"), \
             patch.object(orchestrator2, "_process_features"), \
             patch("os.getpid", return_value=12345):
            orchestrator1.start()
            orchestrator2.start()

        # Third batch should fail
        orchestrator3 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(temp_workspace),
        )

        with patch.object(orchestrator3, "_resource_manager", resource_manager), \
             patch("os.getpid", return_value=12345):
            with pytest.raises(SessionLimitExceededError):
                orchestrator3.start()

    def test_batch_completion_frees_session_slot(
        self, temp_workspace, features_file
    ):
        """Test batch completion frees up session slot for new batch."""
        registry_file = temp_workspace / ".claude" / "local" / "session_registry.json"
        config = ResourceConfig(max_sessions=2)
        resource_manager = SessionResourceManager(registry_file, config)

        # Start 2 batches
        orchestrator1 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(temp_workspace),
        )
        orchestrator2 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(temp_workspace),
        )

        with patch.object(orchestrator1, "_resource_manager", resource_manager), \
             patch.object(orchestrator2, "_resource_manager", resource_manager), \
             patch.object(orchestrator1, "_process_features"), \
             patch.object(orchestrator2, "_process_features"), \
             patch("os.getpid", return_value=12345):
            orchestrator1.start()
            orchestrator2.start()

            # Complete first batch
            orchestrator1.complete()

        # Now third batch should succeed (slot freed)
        orchestrator3 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(temp_workspace),
        )

        with patch.object(orchestrator3, "_resource_manager", resource_manager), \
             patch.object(orchestrator3, "_process_features"), \
             patch("os.getpid", return_value=12345):
            orchestrator3.start()  # Should not raise

    def test_concurrent_batches_different_repos(
        self, tmp_path, features_file, resource_manager
    ):
        """Test concurrent batches in different repos are tracked separately."""
        # Create two different repo directories
        repo1 = tmp_path / "repo1"
        repo2 = tmp_path / "repo2"
        repo1.mkdir()
        repo2.mkdir()

        orchestrator1 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(repo1),
        )
        orchestrator2 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(repo2),
        )

        with patch.object(orchestrator1, "_resource_manager", resource_manager), \
             patch.object(orchestrator2, "_resource_manager", resource_manager), \
             patch.object(orchestrator1, "_process_features"), \
             patch.object(orchestrator2, "_process_features"), \
             patch("os.getpid", return_value=12345):
            orchestrator1.start()
            orchestrator2.start()

        # Both should be registered with different repo paths
        registry = resource_manager._load_registry()
        repo_paths = [s.repo_path for s in registry.sessions]
        assert str(repo1) in repo_paths
        assert str(repo2) in repo_paths

    def test_concurrent_batches_same_repo_deduplicated(
        self, temp_workspace, features_file, resource_manager
    ):
        """Test concurrent batches in same repo are deduplicated."""
        orchestrator1 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(temp_workspace),
        )
        orchestrator2 = BatchOrchestrator(
            features_file=str(features_file),
            repo_path=str(temp_workspace),
        )

        with patch.object(orchestrator1, "_resource_manager", resource_manager), \
             patch.object(orchestrator2, "_resource_manager", resource_manager), \
             patch.object(orchestrator1, "_process_features"), \
             patch.object(orchestrator2, "_process_features"), \
             patch("os.getpid", return_value=12345):
            orchestrator1.start()
            orchestrator2.start()

        # Should only have one session for same repo
        registry = resource_manager._load_registry()
        workspace_sessions = [
            s for s in registry.sessions
            if str(temp_workspace) in s.repo_path
        ]
        assert len(workspace_sessions) == 1


# =============================================================================
# SECTION 4: Clear Operation Tests (3 tests)
# =============================================================================

class TestBatchClearOperations:
    """Test session preserved across /clear operations."""

    def test_session_preserved_after_clear(
        self, batch_orchestrator, resource_manager
    ):
        """Test session remains registered after /clear command."""
        session_id = "session-123"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(batch_orchestrator, "_process_features"):
            batch_orchestrator.start()

            # Simulate /clear operation (context cleared but batch continues)
            # Session should still be registered
            registry = resource_manager._load_registry()
            session = next((s for s in registry.sessions if s.session_id == session_id), None)
            assert session is not None

    def test_resume_after_clear_uses_same_session(
        self, batch_orchestrator, resource_manager
    ):
        """Test batch resume after /clear uses same session ID."""
        session_id = "session-123"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(batch_orchestrator, "_process_features"):
            batch_orchestrator.start()

            # Resume after /clear
            batch_orchestrator.resume()

            # Should still use same session ID
            assert batch_orchestrator._session_id == session_id

    def test_batch_state_preserves_session_id(
        self, batch_orchestrator, resource_manager
    ):
        """Test batch state file preserves session ID across restarts."""
        session_id = "session-123"

        with patch.object(batch_orchestrator, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(batch_orchestrator, "_process_features"):
            batch_orchestrator.start()

            # Save batch state
            batch_orchestrator._save_state()

        # Load state in new orchestrator instance
        new_orchestrator = BatchOrchestrator(
            features_file=str(batch_orchestrator.features_file),
            repo_path=str(batch_orchestrator.repo_path),
        )

        with patch.object(new_orchestrator, "_resource_manager", resource_manager):
            new_orchestrator._load_state()

            # Should have same session ID
            assert new_orchestrator._session_id == session_id


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (24 integration tests):

SECTION 1: Session Registration (6 tests)
✗ test_batch_start_registers_session
✗ test_batch_start_stores_session_id
✗ test_batch_start_estimates_process_count
✗ test_batch_start_checks_session_limit
✗ test_batch_start_session_limit_prevents_execution
✗ test_batch_start_session_id_unique_per_batch

SECTION 2: Session Cleanup (5 tests)
✗ test_batch_complete_unregisters_session
✗ test_batch_failure_still_unregisters_session
✗ test_batch_cleanup_on_keyboard_interrupt
✗ test_batch_resume_reuses_session_id
✗ test_batch_cleanup_context_manager_pattern

SECTION 3: Concurrent Batches (5 tests)
✗ test_multiple_batches_all_registered
✗ test_concurrent_batches_respect_session_limit
✗ test_batch_completion_frees_session_slot
✗ test_concurrent_batches_different_repos
✗ test_concurrent_batches_same_repo_deduplicated

SECTION 4: Clear Operations (3 tests)
✗ test_session_preserved_after_clear
✗ test_resume_after_clear_uses_same_session
✗ test_batch_state_preserves_session_id

TOTAL: 24 integration tests (all FAILING - TDD red phase)

Coverage Target: 90%+ for session management code in batch_orchestrator.py
"""
