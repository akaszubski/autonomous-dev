"""
Unit tests for auto_inject_memory.py - SessionStart hook for memory injection

Tests the SessionStart hook that:
- Detects session start events
- Loads relevant memories from storage
- Injects formatted memories into prompt
- Respects token budget constraints
- Gracefully degrades on errors

TDD Phase: RED - Tests written before implementation
Expected: All tests FAIL until auto_inject_memory.py is implemented
"""

import pytest
import json
from unittest import mock
from pathlib import Path
from autonomous_dev.lib.auto_inject_memory import (
    should_inject_memories,
    load_relevant_memories,
    inject_memories_into_prompt,
)


class TestShouldInjectMemories:
    """Test memory injection enablement logic"""

    def test_injection_disabled_by_default(self):
        """Should be disabled if MEMORY_INJECTION_ENABLED not set"""
        with mock.patch.dict('os.environ', {}, clear=True):
            assert should_inject_memories() is False

    def test_injection_enabled_via_env_var(self):
        """Should enable when MEMORY_INJECTION_ENABLED=true"""
        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            assert should_inject_memories() is True

    def test_injection_disabled_via_env_var(self):
        """Should disable when MEMORY_INJECTION_ENABLED=false"""
        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'false'}):
            assert should_inject_memories() is False

    def test_injection_case_insensitive(self):
        """Should handle case-insensitive values"""
        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'TRUE'}):
            assert should_inject_memories() is True

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'False'}):
            assert should_inject_memories() is False


class TestLoadRelevantMemories:
    """Test loading and ranking memories from storage"""

    def test_load_memories_from_file(self, tmp_path):
        """Should load memories from .claude/memories/session_memories.json"""
        memory_file = tmp_path / ".claude" / "memories" / "session_memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        memories_data = [
            {
                "id": "mem_1",
                "content": "Implemented JWT authentication",
                "timestamp": "2026-01-01T10:00:00"
            },
            {
                "id": "mem_2",
                "content": "Added bcrypt hashing",
                "timestamp": "2026-01-01T11:00:00"
            }
        ]
        memory_file.write_text(json.dumps(memories_data))

        query = "JWT authentication"
        memories = load_relevant_memories(query, project_root=tmp_path)

        assert len(memories) > 0
        assert any("JWT" in mem["content"] for mem in memories)

    def test_load_memories_filters_by_relevance(self, tmp_path):
        """Should filter out low-relevance memories"""
        memory_file = tmp_path / ".claude" / "memories" / "session_memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        memories_data = [
            {
                "id": "mem_1",
                "content": "Implemented JWT authentication with bcrypt",
                "timestamp": "2026-01-01T10:00:00"
            },
            {
                "id": "mem_2",
                "content": "Fixed CSS styling on homepage",
                "timestamp": "2026-01-01T11:00:00"
            }
        ]
        memory_file.write_text(json.dumps(memories_data))

        query = "JWT authentication"
        memories = load_relevant_memories(query, project_root=tmp_path, threshold=0.3)

        # Low-relevance CSS memory should be filtered
        assert all("CSS" not in mem["content"] for mem in memories)

    def test_load_memories_returns_empty_if_no_file(self, tmp_path):
        """Should return empty list if memory file doesn't exist"""
        query = "JWT authentication"
        memories = load_relevant_memories(query, project_root=tmp_path)

        assert memories == []

    def test_load_memories_handles_corrupted_json(self, tmp_path):
        """Should handle corrupted JSON gracefully"""
        memory_file = tmp_path / ".claude" / "memories" / "session_memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)
        memory_file.write_text("{ invalid json }")

        query = "JWT authentication"
        memories = load_relevant_memories(query, project_root=tmp_path)

        # Should return empty list, not crash
        assert memories == []

    def test_load_memories_sorts_by_relevance(self, tmp_path):
        """Should return memories sorted by relevance score"""
        memory_file = tmp_path / ".claude" / "memories" / "session_memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        memories_data = [
            {"id": "1", "content": "Fixed minor bug", "timestamp": "2026-01-01T10:00:00"},
            {"id": "2", "content": "Implemented JWT authentication with bcrypt hashing", "timestamp": "2026-01-01T11:00:00"},
            {"id": "3", "content": "Added user model", "timestamp": "2026-01-01T12:00:00"},
        ]
        memory_file.write_text(json.dumps(memories_data))

        query = "JWT authentication bcrypt"
        memories = load_relevant_memories(query, project_root=tmp_path, threshold=0.0)

        # First memory should have highest relevance
        if len(memories) > 1:
            assert memories[0]["relevance_score"] >= memories[1]["relevance_score"]


class TestInjectMemoriesIntoPrompt:
    """Test injecting formatted memories into prompt"""

    def test_injection_disabled_returns_original(self):
        """Should return original prompt if injection disabled"""
        original_prompt = "Implement JWT authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'false'}):
            result = inject_memories_into_prompt(original_prompt)
            assert result == original_prompt

    def test_injection_enabled_injects_memories(self, tmp_path):
        """Should inject memories when enabled"""
        memory_file = tmp_path / ".claude" / "memories" / "session_memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        memories_data = [
            {
                "id": "mem_1",
                "content": "Previously implemented bcrypt hashing",
                "timestamp": "2026-01-01T10:00:00"
            }
        ]
        memory_file.write_text(json.dumps(memories_data))

        original_prompt = "Implement JWT authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(
                original_prompt,
                project_root=tmp_path
            )

            # Should include both original prompt and memory context
            assert "Implement JWT authentication" in result
            assert "bcrypt" in result or "memory" in result.lower()
            assert len(result) > len(original_prompt)

    def test_no_memories_returns_original(self, tmp_path):
        """Should return original prompt if no relevant memories found"""
        original_prompt = "Implement JWT authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(
                original_prompt,
                project_root=tmp_path
            )

            # No memories file exists, should return original
            assert result == original_prompt

    def test_custom_token_budget(self, tmp_path):
        """Should respect custom token budget"""
        memory_file = tmp_path / ".claude" / "memories" / "session_memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        # Create many memories
        memories_data = [
            {
                "id": f"mem_{i}",
                "content": f"Memory {i}: " + "Long content " * 20,
                "timestamp": "2026-01-01T10:00:00"
            }
            for i in range(10)
        ]
        memory_file.write_text(json.dumps(memories_data))

        original_prompt = "Continue working on authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(
                original_prompt,
                project_root=tmp_path,
                max_tokens=100
            )

            # Should not exceed budget significantly
            from autonomous_dev.lib.memory_formatter import count_tokens
            total_tokens = count_tokens(result)
            # Allow some overhead for structure
            assert total_tokens < count_tokens(original_prompt) + 150


class TestGracefulDegradation:
    """Test error handling and graceful degradation"""

    def test_graceful_degradation_import_error(self):
        """Should not crash if memory libraries unavailable"""
        original_prompt = "Implement JWT authentication"

        # Mock import error
        with mock.patch('autonomous_dev.lib.auto_inject_memory.load_relevant_memories',
                       side_effect=ImportError("Module not found")):
            with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
                result = inject_memories_into_prompt(original_prompt)

                # Should return original prompt, not crash
                assert result == original_prompt

    def test_graceful_degradation_file_error(self, tmp_path):
        """Should handle file read errors gracefully"""
        # Create directory without read permissions (simulate permission error)
        memory_dir = tmp_path / ".claude" / "memories"
        memory_dir.mkdir(parents=True, exist_ok=True)

        original_prompt = "Implement JWT authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            # Mock file read error
            with mock.patch('pathlib.Path.read_text', side_effect=PermissionError()):
                result = inject_memories_into_prompt(
                    original_prompt,
                    project_root=tmp_path
                )

                # Should return original prompt
                assert result == original_prompt

    def test_graceful_degradation_ranking_error(self, tmp_path):
        """Should handle ranking errors gracefully"""
        memory_file = tmp_path / ".claude" / "memories" / "session_memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)
        memory_file.write_text(json.dumps([{"content": "Test"}]))

        original_prompt = "Implement JWT authentication"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            # Mock ranking error
            with mock.patch('autonomous_dev.lib.memory_relevance.rank_memories',
                          side_effect=Exception("Ranking failed")):
                result = inject_memories_into_prompt(
                    original_prompt,
                    project_root=tmp_path
                )

                # Should return original prompt
                assert result == original_prompt


class TestHookIntegration:
    """Test hook integration with SessionStart lifecycle"""

    def test_hook_triggered_on_session_start(self):
        """Should trigger on SessionStart lifecycle event"""
        # This is tested in integration tests
        # Unit test verifies the hook entry point exists
        from autonomous_dev.hooks import auto_inject_memory as hook_module

        assert hasattr(hook_module, 'handle_session_start')

    def test_hook_returns_modified_prompt(self, tmp_path):
        """Should return modified prompt with injected memories"""
        memory_file = tmp_path / ".claude" / "memories" / "session_memories.json"
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        memories_data = [
            {
                "id": "mem_1",
                "content": "Context from previous session",
                "timestamp": "2026-01-01T10:00:00"
            }
        ]
        memory_file.write_text(json.dumps(memories_data))

        original_prompt = "Continue previous work"

        with mock.patch.dict('os.environ', {'MEMORY_INJECTION_ENABLED': 'true'}):
            result = inject_memories_into_prompt(
                original_prompt,
                project_root=tmp_path
            )

            assert result != original_prompt
            assert "previous session" in result.lower() or "context" in result.lower()
