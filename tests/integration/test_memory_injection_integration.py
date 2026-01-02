"""
Integration tests for memory injection system (Issue #192)

Tests the complete end-to-end flow:
1. Session memories stored in .claude/memories/
2. SessionStart hook triggers
3. Memories ranked by relevance
4. Formatted memories injected into prompt
5. Token budget respected
6. Performance < 1 second

TDD Phase: RED - Tests written before implementation
Expected: All tests FAIL until full integration is complete
"""

import pytest
import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest import mock


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create temporary project directory with .claude structure"""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create .claude directory structure
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()

    memories_dir = claude_dir / "memories"
    memories_dir.mkdir()

    return project_dir


@pytest.fixture
def sample_memories():
    """Sample memories for testing"""
    now = datetime.now()
    return [
        {
            "id": "mem_1",
            "content": "Implemented JWT authentication with bcrypt password hashing for secure user login",
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "session_id": "session_1"
        },
        {
            "id": "mem_2",
            "content": "Added user session management with Redis for distributed caching",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "session_id": "session_1"
        },
        {
            "id": "mem_3",
            "content": "Fixed CSS styling on homepage header navigation",
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "session_id": "session_2"
        },
        {
            "id": "mem_4",
            "content": "Implemented OAuth2 authorization flow with refresh tokens",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "session_id": "session_3"
        },
        {
            "id": "mem_5",
            "content": "Added security audit logging for authentication attempts",
            "timestamp": (now - timedelta(hours=3)).isoformat(),
            "session_id": "session_1"
        },
    ]


class TestFullInjectionPipeline:
    """Test complete end-to-end memory injection"""

    def test_full_injection_pipeline(self, tmp_project_dir, sample_memories):
        """Should complete full injection pipeline successfully"""
        # Setup: Write memories to file
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(sample_memories))

        # Simulate SessionStart hook
        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        original_prompt = "Implement token refresh mechanism for JWT authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(
                original_prompt,
                project_root=tmp_project_dir
            )

            # Verify injection occurred
            assert len(result) > len(original_prompt)
            assert original_prompt in result

            # Verify relevant memories included
            assert "JWT" in result or "authentication" in result.lower()

            # Verify irrelevant memories excluded (CSS styling)
            # (May be included if relevance is high enough, but should rank lower)
            result_lower = result.lower()
            jwt_mentions = result_lower.count("jwt") + result_lower.count("authentication")
            css_mentions = result_lower.count("css") + result_lower.count("styling")
            assert jwt_mentions > css_mentions or css_mentions == 0

    def test_continuing_feature_work(self, tmp_project_dir, sample_memories):
        """Should provide context when continuing feature work across sessions"""
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(sample_memories))

        # User continues work on authentication
        prompt = "Continue working on authentication system"

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)

            # Should include authentication-related memories
            assert "JWT" in result or "bcrypt" in result or "OAuth" in result
            assert len(result) > len(prompt)

    def test_security_context_recalled(self, tmp_project_dir, sample_memories):
        """Should recall security-related context for security tasks"""
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(sample_memories))

        prompt = "Add security audit logging for failed login attempts"

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)

            # Should include security audit memory
            assert "security audit" in result.lower() or "logging" in result.lower()


class TestFirstSessionBehavior:
    """Test behavior when no memories exist yet"""

    def test_first_session_no_memories(self, tmp_project_dir):
        """Should handle first session with no memories gracefully"""
        # No memory file exists
        prompt = "Implement JWT authentication"

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)

            # Should return original prompt unchanged
            assert result == prompt

    def test_empty_memory_file(self, tmp_project_dir):
        """Should handle empty memory file gracefully"""
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps([]))

        prompt = "Implement JWT authentication"

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)

            # Should return original prompt
            assert result == prompt


class TestPerformanceRequirements:
    """Test performance requirements (< 1 second)"""

    def test_injection_under_1_second(self, tmp_project_dir, sample_memories):
        """Should complete injection in under 1 second"""
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(sample_memories))

        prompt = "Implement JWT authentication"

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            start_time = time.time()
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)
            elapsed_time = time.time() - start_time

            assert elapsed_time < 1.0  # Must complete in under 1 second
            assert len(result) > len(prompt)  # Verify injection occurred

    def test_large_memory_set_handled(self, tmp_project_dir):
        """Should handle large memory sets efficiently"""
        # Create 100 memories
        large_memory_set = [
            {
                "id": f"mem_{i}",
                "content": f"Memory {i}: Implemented feature X with details about authentication, security, and performance optimization",
                "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
            }
            for i in range(100)
        ]

        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(large_memory_set))

        prompt = "Implement authentication system"

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            start_time = time.time()
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)
            elapsed_time = time.time() - start_time

            # Should still complete quickly even with large dataset
            assert elapsed_time < 2.0  # Allow 2 seconds for large dataset
            assert len(result) > len(prompt)


class TestTokenBudgetRespected:
    """Test token budget constraints"""

    def test_token_budget_prevents_bloat(self, tmp_project_dir, sample_memories):
        """Should not inject excessive tokens that bloat context"""
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(sample_memories))

        prompt = "Implement JWT authentication"

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt
        from autonomous_dev.lib.memory_formatter import count_tokens

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(
                prompt,
                project_root=tmp_project_dir,
                max_tokens=200  # Strict budget
            )

            memory_tokens = count_tokens(result) - count_tokens(prompt)

            # Should respect budget (allow small overhead for structure)
            assert memory_tokens <= 250

    def test_default_token_budget(self, tmp_project_dir, sample_memories):
        """Should use reasonable default token budget"""
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(sample_memories))

        prompt = "Implement JWT authentication"

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt
        from autonomous_dev.lib.memory_formatter import count_tokens

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)

            memory_tokens = count_tokens(result) - count_tokens(prompt)

            # Default budget should be reasonable (500-1000 tokens)
            assert memory_tokens < 1200  # Allow overhead


class TestMultiSessionState:
    """Test state preservation across multiple sessions"""

    def test_multiple_sessions_preserve_state(self, tmp_project_dir):
        """Should preserve and accumulate memories across sessions"""
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"

        # Session 1: Initial implementation
        session1_memories = [
            {
                "id": "mem_1",
                "content": "Implemented JWT authentication",
                "timestamp": datetime.now().isoformat(),
                "session_id": "session_1"
            }
        ]
        memory_file.write_text(json.dumps(session1_memories))

        # Session 2: Add more features
        session2_memories = session1_memories + [
            {
                "id": "mem_2",
                "content": "Added bcrypt password hashing",
                "timestamp": datetime.now().isoformat(),
                "session_id": "session_2"
            }
        ]
        memory_file.write_text(json.dumps(session2_memories))

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        prompt = "Add refresh token support"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)

            # Should include context from both sessions
            assert "JWT" in result or "authentication" in result.lower()
            assert "bcrypt" in result or "password" in result.lower()

    def test_old_memories_lower_priority(self, tmp_project_dir):
        """Should deprioritize old memories (recency decay)"""
        now = datetime.now()
        memories = [
            {
                "id": "mem_recent",
                "content": "Recent: Implemented JWT authentication",
                "timestamp": (now - timedelta(hours=1)).isoformat(),
            },
            {
                "id": "mem_old",
                "content": "Old: Implemented JWT authentication",
                "timestamp": (now - timedelta(days=30)).isoformat(),
            }
        ]

        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(memories))

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        prompt = "Update JWT implementation"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(
                prompt,
                project_root=tmp_project_dir,
                max_tokens=100  # Tight budget forces prioritization
            )

            # Recent memory should be prioritized
            assert "Recent:" in result or result.index("JWT") < len(result) // 2


class TestEdgeCasesIntegration:
    """Test edge cases in full integration"""

    def test_malformed_memory_structure(self, tmp_project_dir):
        """Should handle malformed memory objects gracefully"""
        malformed_memories = [
            {"content": "No ID or timestamp"},  # Missing fields
            {"id": "mem_1"},  # Missing content
            {"id": "mem_2", "content": "Valid memory", "timestamp": "invalid-date"},
            None,  # Null entry
        ]

        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(malformed_memories))

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        prompt = "Implement JWT authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            # Should not crash
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)

            assert isinstance(result, str)
            # May or may not include valid memory, but should not crash

    def test_unicode_and_special_characters(self, tmp_project_dir):
        """Should handle unicode and special characters in memories"""
        unicode_memories = [
            {
                "id": "mem_1",
                "content": "Implemented authentication 🔒 with JWT tokens 🎫",
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "mem_2",
                "content": "Added security measures: SQL injection → prevented",
                "timestamp": datetime.now().isoformat()
            }
        ]

        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(unicode_memories))

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        prompt = "Continue authentication work"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)

            # Should handle unicode without crashing
            assert isinstance(result, str)
            assert "authentication" in result.lower()

    def test_concurrent_access_safe(self, tmp_project_dir, sample_memories):
        """Should handle concurrent read access safely"""
        memory_file = tmp_project_dir / ".claude" / "memories" / "session_memories.json"
        memory_file.write_text(json.dumps(sample_memories))

        from autonomous_dev.lib.auto_inject_memory import inject_memories_into_prompt

        prompt = "Implement JWT authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            # Simulate multiple concurrent reads
            results = []
            for _ in range(5):
                result = inject_memories_into_prompt(prompt, project_root=tmp_project_dir)
                results.append(result)

            # All reads should succeed and return consistent results
            assert all(len(r) > len(prompt) for r in results)
            assert all(r == results[0] for r in results)  # Consistent output
