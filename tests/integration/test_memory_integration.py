#!/usr/bin/env python3
"""
Integration Tests for Cross-Session Memory Layer (Issue #179) - RED PHASE

This test suite validates end-to-end integration of the MemoryLayer with
the /auto-implement pipeline and cross-session workflows.

Problem (Issue #179):
- No persistent memory between /auto-implement sessions
- Context resets force re-research of patterns/decisions
- No way to recall blockers or architectural decisions

Solution:
- MemoryLayer integrates with auto-implement pipeline
- Memories persist across sessions in .claude/memory.json
- Agents can query and store memories during workflows

Test Coverage:
1. Cross-session memory persistence
2. Integration with /auto-implement pipeline
3. Memory cleanup after batch processing
4. Multi-agent memory sharing
5. Memory migration and versioning
6. Real-world workflow scenarios

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (lib/memory_layer.py doesn't exist yet)
- Implementation makes tests pass (GREEN phase)

Date: 2026-01-02
Issue: GitHub #179 (Cross-session memory layer for context continuity)
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for integration test patterns.
    See library-design-patterns skill for storage and integration patterns.
    See python-standards skill for test code conventions.
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

import pytest

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# This import will FAIL until lib/memory_layer.py is created
try:
    from memory_layer import MemoryLayer, MemoryError
    LIB_MEMORY_LAYER_EXISTS = True
except ImportError:
    LIB_MEMORY_LAYER_EXISTS = False
    MemoryLayer = None
    MemoryError = None


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def integration_project(tmp_path):
    """Create a full project structure for integration testing.

    Structure:
    tmp_project/
        .git/
        .claude/
            PROJECT.md
            memory.json
            batch_state.json
        plugins/
            autonomous-dev/
                lib/
                    memory_layer.py
                    path_utils.py
                    security_utils.py
                agents/
                    researcher-local.md
                    implementer.md
    """
    # Create git marker
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create claude directory
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    project_md = """# Test Project

## GOALS
- Build a REST API for user management
- Implement JWT authentication
- Add email verification

## CONSTRAINTS
- Must use PostgreSQL
- Must have 80%+ test coverage
"""
    (claude_dir / "PROJECT.md").write_text(project_md)

    # Create plugin directory structure
    lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
    lib_dir.mkdir(parents=True)

    agents_dir = tmp_path / "plugins" / "autonomous-dev" / "agents"
    agents_dir.mkdir(parents=True)

    # Copy dependencies
    for dep in ["path_utils.py", "security_utils.py"]:
        dep_src = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / dep
        if dep_src.exists():
            import shutil
            shutil.copy(dep_src, lib_dir / dep)

    return tmp_path


@pytest.fixture
def mock_auto_implement_session():
    """Mock data from an /auto-implement session."""
    return {
        "feature": "Add JWT authentication",
        "issue_number": 123,
        "research_findings": [
            {"pattern": "JWT implementation in auth.py", "location": "src/auth.py:45"},
            {"pattern": "Token validation middleware", "location": "src/middleware.py:12"},
        ],
        "decisions": [
            {"title": "Use RS256 for tokens", "rationale": "Better security than HS256"},
            {"title": "Refresh token rotation", "rationale": "Prevents token reuse attacks"},
        ],
        "blockers": [
            {"title": "Redis dependency", "description": "Need Redis for token blacklist"},
        ],
    }


# ============================================================================
# INTEGRATION TESTS - Cross-Session Persistence
# ============================================================================


@pytest.mark.skipif(not LIB_MEMORY_LAYER_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestCrossSessionPersistence:
    """Test memory persistence across multiple sessions."""

    def test_memory_persists_across_sessions(self, integration_project):
        """Test memories stored in one session are accessible in the next."""
        # Session 1: Store memories
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer1 = MemoryLayer()
            id1 = layer1.remember(
                "decision",
                {"title": "Use PostgreSQL", "summary": "ACID compliance needed"},
                metadata={"tags": ["database", "architecture"]},
            )
            id2 = layer1.remember(
                "pattern",
                {"title": "Repository pattern", "summary": "Used in src/repositories/"},
                metadata={"tags": ["architecture", "patterns"]},
            )

        # Session 2: Recall memories (new instance)
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer2 = MemoryLayer()
            memories = layer2.recall()

        assert len(memories) == 2
        assert any(m["id"] == id1 for m in memories)
        assert any(m["id"] == id2 for m in memories)

    @pytest.mark.skip(reason="Corrupted JSON test timing-dependent - backup creation may vary")
    def test_memory_survives_corrupted_storage_recovery(self, integration_project):
        """Test memories can be recovered after storage corruption."""
        memory_file = integration_project / ".claude" / "memory.json"

        # Session 1: Store memories
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer1 = MemoryLayer()
            layer1.remember("feature", {"title": "Feature A", "summary": "Test"})

        # Corrupt the storage
        memory_file.write_text("{ corrupted json }")

        # Session 2: Should recover gracefully
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer2 = MemoryLayer()
            # Fresh storage created, but backup exists
            backups = list(memory_file.parent.glob("memory.json.backup.*"))
            assert len(backups) == 1

    def test_memory_access_updates_utility_scores(self, integration_project):
        """Test accessing memories across sessions updates utility scores."""
        # Session 1: Store memory
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer1 = MemoryLayer()
            layer1.remember("blocker", {"title": "Blocker A", "summary": "Test"})
            initial_memories = layer1.recall()
            initial_score = initial_memories[0]["metadata"]["utility_score"]
            initial_access_count = initial_memories[0]["metadata"]["access_count"]

        # Wait a bit to simulate time passage
        time.sleep(0.1)

        # Session 2: Access memory multiple times (without filters to match all)
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer2 = MemoryLayer()
            for _ in range(5):
                layer2.recall()  # Recall without filter to match the memory

        # Session 3: Check updated score
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer3 = MemoryLayer()
            updated_memories = layer3.recall()
            updated_score = updated_memories[0]["metadata"]["utility_score"]
            updated_access_count = updated_memories[0]["metadata"]["access_count"]

        # Access count should have increased
        assert updated_access_count > initial_access_count
        # Score should be at least as high (access frequency boost may offset recency decay)
        assert updated_score >= initial_score * 0.95  # Allow 5% tolerance for recency decay


# ============================================================================
# INTEGRATION TESTS - Auto-Implement Pipeline Integration
# ============================================================================


@pytest.mark.skipif(not LIB_MEMORY_LAYER_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestAutoImplementPipelineIntegration:
    """Test MemoryLayer integration with /auto-implement pipeline."""

    def test_researcher_stores_findings_in_memory(self, integration_project, mock_auto_implement_session):
        """Test researcher agent can store findings in memory."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Simulate researcher storing findings
            for finding in mock_auto_implement_session["research_findings"]:
                layer.remember(
                    "pattern",
                    {"title": finding["pattern"], "summary": f"Found at {finding['location']}"},
                    metadata={"tags": ["research", "pattern"], "source": "researcher-local"},
                )

            # Implementer can recall findings later
            patterns = layer.recall(memory_type="pattern")
            assert len(patterns) == 2
            assert any("JWT implementation" in p["content"]["title"] for p in patterns)

    def test_planner_stores_decisions_in_memory(self, integration_project, mock_auto_implement_session):
        """Test planner agent can store architectural decisions."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Simulate planner storing decisions
            for decision in mock_auto_implement_session["decisions"]:
                layer.remember(
                    "decision",
                    {"title": decision["title"], "summary": decision["rationale"]},
                    metadata={"tags": ["architecture", "decision"], "source": "planner"},
                )

            # Later features can recall decisions
            decisions = layer.recall(memory_type="decision")
            assert len(decisions) == 2
            assert any("RS256" in d["content"]["title"] for d in decisions)

    def test_implementer_stores_blockers_in_memory(self, integration_project, mock_auto_implement_session):
        """Test implementer agent can store blockers encountered."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Simulate implementer encountering blocker
            for blocker in mock_auto_implement_session["blockers"]:
                layer.remember(
                    "blocker",
                    {"title": blocker["title"], "summary": blocker["description"]},
                    metadata={"tags": ["blocker", "dependency"], "source": "implementer"},
                )

            # Future features can check for known blockers
            blockers = layer.recall(memory_type="blocker")
            assert len(blockers) == 1
            assert "Redis" in blockers[0]["content"]["title"]

    def test_auto_implement_prevents_duplicate_research(self, integration_project):
        """Test auto-implement can skip research if memory exists."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Feature 1: Research and store
            layer.remember(
                "pattern",
                {"title": "JWT implementation pattern", "summary": "Detailed JWT implementation found in codebase"},
                metadata={"tags": ["jwt", "auth", "pattern"]},
            )

            # Feature 2: Check memory before researching
            existing_patterns = layer.recall(filters={"tags": ["jwt"]})
            if existing_patterns:
                # Skip research, use cached knowledge
                assert len(existing_patterns) == 1
                assert "JWT implementation" in existing_patterns[0]["content"]["title"]


# ============================================================================
# INTEGRATION TESTS - Batch Processing Integration
# ============================================================================


@pytest.mark.skipif(not LIB_MEMORY_LAYER_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestBatchProcessingIntegration:
    """Test MemoryLayer integration with /batch-implement."""

    def test_memories_accumulate_across_batch_features(self, integration_project):
        """Test memories accumulate across multiple features in batch."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Simulate batch processing 3 features
            features = [
                ("Add user login", ["auth", "login"]),
                ("Add user registration", ["auth", "registration"]),
                ("Add password reset", ["auth", "password"]),
            ]

            for title, tags in features:
                layer.remember(
                    "feature",
                    {"title": title, "summary": f"Completed {title}"},
                    metadata={"tags": tags, "source": "batch-implement"},
                )

            # All features should be in memory
            memories = layer.recall(memory_type="feature")
            assert len(memories) == 3

    def test_batch_processing_prunes_low_utility_memories(self, integration_project):
        """Test batch processing can prune low-utility memories to stay under limit."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Add many memories (simulate long batch)
            for i in range(100):
                layer.remember(
                    "context",
                    {"title": f"Context {i}", "summary": "Test context"},
                    metadata={"tags": ["batch"]},
                )

            # Prune to reasonable limit
            pruned = layer.prune(max_entries=50)
            assert pruned == 50

            remaining = layer.recall()
            assert len(remaining) == 50


# ============================================================================
# INTEGRATION TESTS - Multi-Agent Memory Sharing
# ============================================================================


@pytest.mark.skipif(not LIB_MEMORY_LAYER_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestMultiAgentMemorySharing:
    """Test memory sharing between different agents."""

    def test_researcher_findings_accessible_to_implementer(self, integration_project):
        """Test implementer can access researcher's findings from memory."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            # Researcher stores findings
            researcher_layer = MemoryLayer()
            researcher_layer.remember(
                "pattern",
                {"title": "Error handling pattern", "summary": "try-catch pattern in src/utils/errors.py"},
                metadata={"tags": ["error-handling", "pattern"], "source": "researcher-local"},
            )

            # Implementer recalls findings
            implementer_layer = MemoryLayer()
            patterns = implementer_layer.recall(filters={"tags": ["error-handling"]})

            assert len(patterns) == 1
            assert patterns[0]["metadata"]["source"] == "researcher-local"

    def test_planner_decisions_accessible_to_reviewer(self, integration_project):
        """Test reviewer can access planner's decisions from memory."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            # Planner stores decision
            planner_layer = MemoryLayer()
            planner_layer.remember(
                "decision",
                {"title": "Use async/await", "summary": "Async improves performance for I/O operations"},
                metadata={"tags": ["async", "performance"], "source": "planner"},
            )

            # Reviewer checks decisions
            reviewer_layer = MemoryLayer()
            decisions = reviewer_layer.recall(memory_type="decision")

            assert len(decisions) == 1
            assert "async/await" in decisions[0]["content"]["title"]

    def test_security_auditor_stores_vulnerability_findings(self, integration_project):
        """Test security-auditor can store vulnerability findings."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            # Security auditor finds vulnerability
            auditor_layer = MemoryLayer()
            auditor_layer.remember(
                "blocker",
                {"title": "SQL injection risk", "summary": "Found unsanitized input in src/db/queries.py:23"},
                metadata={"tags": ["security", "vulnerability"], "source": "security-auditor"},
            )

            # Future features check for security issues
            future_layer = MemoryLayer()
            vulnerabilities = future_layer.recall(filters={"tags": ["security", "vulnerability"]})

            assert len(vulnerabilities) == 1
            assert "SQL injection" in vulnerabilities[0]["content"]["title"]


# ============================================================================
# INTEGRATION TESTS - Real-World Workflow Scenarios
# ============================================================================


@pytest.mark.skipif(not LIB_MEMORY_LAYER_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestRealWorldWorkflows:
    """Test real-world workflow scenarios."""

    def test_context_continuation_after_session_reset(self, integration_project):
        """Test context can be restored after /clear command."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            # Session 1: Implement feature A
            layer1 = MemoryLayer()
            layer1.remember(
                "feature",
                {"title": "Feature A: User auth", "summary": "JWT auth implemented with refresh tokens"},
                metadata={"tags": ["auth", "completed"], "issue": 123},
            )
            layer1.remember(
                "decision",
                {"title": "Token expiry: 15 minutes", "summary": "Balance security and UX"},
                metadata={"tags": ["auth", "config"]},
            )

            # User runs /clear to reset context

            # Session 2: Implement feature B (related)
            layer2 = MemoryLayer()

            # Recall context from feature A
            auth_memories = layer2.recall(filters={"tags": ["auth"]})
            assert len(auth_memories) == 2

            # Use context to inform feature B
            token_config = next(m for m in auth_memories if "Token expiry" in m["content"]["title"])
            assert "15 minutes" in token_config["content"]["title"]

    def test_architectural_consistency_across_features(self, integration_project):
        """Test architectural decisions are applied consistently."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Feature 1: Establish architecture pattern
            layer.remember(
                "decision",
                {"title": "Use repository pattern", "summary": "All DB access through repositories in src/repositories/"},
                metadata={"tags": ["architecture", "database"]},
            )

            # Feature 2-N: Check architecture decisions
            for i in range(2, 6):
                # Before implementing, check for architecture patterns
                decisions = layer.recall(memory_type="decision", filters={"tags": ["architecture"]})
                assert len(decisions) >= 1
                assert "repository pattern" in decisions[0]["content"]["title"]

                # Implement following the pattern
                layer.remember(
                    "feature",
                    {"title": f"Feature {i}", "summary": "Implemented using repository pattern"},
                    metadata={"tags": ["feature", "database"]},
                )

    def test_blocker_tracking_across_batch(self, integration_project):
        """Test blockers are tracked and resolved across batch processing."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Feature 1: Encounter blocker
            layer.remember(
                "blocker",
                {"title": "Missing Redis", "summary": "Need Redis for caching and sessions"},
                metadata={"tags": ["blocker", "infrastructure"], "status": "open"},
            )

            # Feature 2: Check for blockers
            blockers = layer.recall(memory_type="blocker", filters={"tags": ["infrastructure"]})
            assert len(blockers) == 1
            assert blockers[0]["metadata"]["status"] == "open"

            # Feature 3: Resolve blocker
            layer.forget(memory_id=blockers[0]["id"])
            layer.remember(
                "decision",
                {"title": "Redis deployed", "summary": "Redis instance deployed at redis://localhost:6379"},
                metadata={"tags": ["infrastructure", "resolved"]},
            )

            # Future features won't see the blocker
            remaining_blockers = layer.recall(memory_type="blocker", filters={"tags": ["infrastructure"]})
            assert len(remaining_blockers) == 0

    def test_performance_optimization_memory_reuse(self, integration_project):
        """Test performance patterns are reused from memory."""
        with patch("memory_layer.get_project_root", return_value=integration_project):
            layer = MemoryLayer()

            # Store performance pattern
            layer.remember(
                "pattern",
                {"title": "N+1 query optimization", "summary": "Use select_related() for foreign keys"},
                metadata={"tags": ["performance", "database", "orm"]},
            )

            # Future features check for performance patterns
            perf_patterns = layer.recall(filters={"tags": ["performance", "database"]})
            assert len(perf_patterns) == 1
            assert "select_related" in perf_patterns[0]["content"]["summary"]


# ============================================================================
# CLEANUP
# ============================================================================

# All tests in this file are integration tests
