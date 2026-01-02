"""
Unit tests for memory_formatter.py - Format memories with token budget

Tests the memory formatting system that:
- Counts tokens using tiktoken (cl100k_base encoding)
- Formats memories with markdown structure
- Respects token budget constraints
- Truncates gracefully when budget exceeded

TDD Phase: RED - Tests written before implementation
Expected: All tests FAIL until memory_formatter.py is implemented
"""

import pytest
from datetime import datetime
from autonomous_dev.lib.memory_formatter import (
    count_tokens,
    format_memory_block,
    format_memories_with_budget,
)


class TestCountTokens:
    """Test token counting using tiktoken"""

    def test_count_tokens_basic(self):
        """Should count tokens for simple text"""
        text = "Hello world"
        token_count = count_tokens(text)

        assert isinstance(token_count, int)
        assert token_count > 0
        assert token_count < 10  # Simple text should be few tokens

    def test_count_tokens_empty_string(self):
        """Should return 0 for empty string"""
        assert count_tokens("") == 0

    def test_count_tokens_long_text(self):
        """Should accurately count tokens for longer text"""
        text = "Implemented JWT authentication with bcrypt hashing. " * 10
        token_count = count_tokens(text)

        # Rough estimate: should be proportional to word count
        assert token_count > 50
        assert token_count < 200

    def test_count_tokens_code_snippet(self):
        """Should count tokens for code snippets"""
        code = """
def authenticate(username, password):
    user = User.query.filter_by(username=username).first()
    if user and bcrypt.check_password_hash(user.password, password):
        return jwt.encode({'user_id': user.id}, SECRET_KEY)
    return None
"""
        token_count = count_tokens(code)
        assert token_count > 0

    def test_count_tokens_special_characters(self):
        """Should handle special characters"""
        text = "JWT! @authentication #bcrypt $hashing 🔒"
        token_count = count_tokens(text)
        assert token_count > 0


class TestFormatMemoryBlock:
    """Test formatting individual memory blocks"""

    def test_format_memory_block_structure(self):
        """Should format memory with markdown structure"""
        memory = {
            "content": "Implemented JWT authentication",
            "timestamp": "2026-01-01T10:00:00",
            "relevance_score": 0.85,
            "id": "mem_123"
        }

        formatted = format_memory_block(memory)

        assert isinstance(formatted, str)
        assert "Implemented JWT authentication" in formatted
        assert len(formatted) > 0

    def test_format_includes_timestamp(self):
        """Should include timestamp in formatted output"""
        memory = {
            "content": "Added bcrypt hashing",
            "timestamp": "2026-01-01T10:00:00",
            "relevance_score": 0.75
        }

        formatted = format_memory_block(memory)
        assert "2026-01-01" in formatted or "Jan" in formatted or "10:00" in formatted

    def test_format_includes_relevance_score(self):
        """Should include relevance score in formatted output"""
        memory = {
            "content": "Fixed authentication bug",
            "timestamp": "2026-01-01T10:00:00",
            "relevance_score": 0.65
        }

        formatted = format_memory_block(memory)
        # Score should be included (as percentage or decimal)
        assert "0.65" in formatted or "65" in formatted or "relevance" in formatted.lower()

    def test_format_handles_missing_fields(self):
        """Should gracefully handle missing optional fields"""
        memory = {
            "content": "Basic memory"
        }

        formatted = format_memory_block(memory)
        assert "Basic memory" in formatted
        assert isinstance(formatted, str)

    def test_format_multiline_content(self):
        """Should preserve multiline content"""
        memory = {
            "content": "Step 1: Research\nStep 2: Implement\nStep 3: Test",
            "timestamp": "2026-01-01T10:00:00"
        }

        formatted = format_memory_block(memory)
        assert "Step 1" in formatted
        assert "Step 2" in formatted
        assert "Step 3" in formatted


class TestFormatMemoriesWithBudget:
    """Test formatting multiple memories with token budget"""

    def test_format_respects_budget(self):
        """Should not exceed specified token budget"""
        memories = [
            {
                "content": "Implemented JWT authentication with bcrypt hashing and secure token generation",
                "timestamp": "2026-01-01T10:00:00",
                "relevance_score": 0.9
            },
            {
                "content": "Added user session management with cookie-based storage",
                "timestamp": "2026-01-01T11:00:00",
                "relevance_score": 0.8
            },
            {
                "content": "Fixed authentication bug in login endpoint",
                "timestamp": "2026-01-01T12:00:00",
                "relevance_score": 0.7
            },
        ]

        formatted = format_memories_with_budget(memories, max_tokens=100)
        token_count = count_tokens(formatted)

        assert token_count <= 100

    def test_format_includes_at_least_one_memory(self):
        """Should include at least one memory even if budget is tight"""
        memories = [
            {
                "content": "Implemented JWT authentication",
                "timestamp": "2026-01-01T10:00:00",
                "relevance_score": 0.9
            },
        ]

        # Very small budget
        formatted = format_memories_with_budget(memories, max_tokens=50)

        # Should include at least the content or truncated version
        assert len(formatted) > 0
        assert "JWT" in formatted or "authentication" in formatted

    def test_format_prioritizes_high_relevance(self):
        """Should prioritize higher relevance memories"""
        memories = [
            {
                "content": "Low relevance memory",
                "timestamp": "2026-01-01T10:00:00",
                "relevance_score": 0.3
            },
            {
                "content": "High relevance memory",
                "timestamp": "2026-01-01T11:00:00",
                "relevance_score": 0.9
            },
        ]

        formatted = format_memories_with_budget(memories, max_tokens=100)

        # High relevance should be included
        assert "High relevance" in formatted

    def test_format_empty_list(self):
        """Should handle empty memory list gracefully"""
        formatted = format_memories_with_budget([], max_tokens=500)
        assert formatted == "" or "No memories" in formatted

    def test_format_adds_header(self):
        """Should include section header for context"""
        memories = [
            {
                "content": "Implemented JWT authentication",
                "timestamp": "2026-01-01T10:00:00",
                "relevance_score": 0.9
            },
        ]

        formatted = format_memories_with_budget(memories, max_tokens=500)

        # Should have some kind of header or structure
        assert "##" in formatted or "Memory" in formatted or "Context" in formatted

    def test_format_large_budget_includes_all(self):
        """Should include all memories if budget allows"""
        memories = [
            {"content": f"Memory {i}", "relevance_score": 0.8}
            for i in range(5)
        ]

        formatted = format_memories_with_budget(memories, max_tokens=5000)

        # All memories should be included
        for i in range(5):
            assert f"Memory {i}" in formatted


class TestTokenBudgetEdgeCases:
    """Test edge cases in token budget handling"""

    def test_zero_budget(self):
        """Should handle zero token budget gracefully"""
        memories = [
            {"content": "Test memory", "relevance_score": 0.9}
        ]

        formatted = format_memories_with_budget(memories, max_tokens=0)
        assert formatted == "" or len(formatted) == 0

    def test_negative_budget(self):
        """Should handle negative budget (treat as zero)"""
        memories = [
            {"content": "Test memory", "relevance_score": 0.9}
        ]

        formatted = format_memories_with_budget(memories, max_tokens=-100)
        assert formatted == "" or len(formatted) == 0

    def test_very_large_budget(self):
        """Should handle very large budget efficiently"""
        memories = [
            {"content": f"Memory {i} " * 100, "relevance_score": 0.8}
            for i in range(50)
        ]

        # Should not crash with large budget
        formatted = format_memories_with_budget(memories, max_tokens=100000)
        assert isinstance(formatted, str)

    def test_single_memory_exceeds_budget(self):
        """Should truncate single memory if it exceeds budget"""
        memories = [
            {
                "content": "Very long memory content " * 100,
                "timestamp": "2026-01-01T10:00:00",
                "relevance_score": 0.9
            }
        ]

        formatted = format_memories_with_budget(memories, max_tokens=50)
        token_count = count_tokens(formatted)

        # Should be truncated or summarized
        assert token_count <= 50 or len(formatted) == 0

    def test_unicode_affects_token_count(self):
        """Should accurately count tokens with unicode"""
        memories = [
            {
                "content": "Authentication 🔒 security 🔐 tokens 🎫",
                "relevance_score": 0.9
            }
        ]

        formatted = format_memories_with_budget(memories, max_tokens=100)
        token_count = count_tokens(formatted)

        assert token_count <= 100


class TestFormattingConsistency:
    """Test consistent formatting across edge cases"""

    def test_consistent_format_structure(self):
        """Should maintain consistent format structure"""
        memories_a = [
            {"content": "Memory A", "relevance_score": 0.9}
        ]
        memories_b = [
            {"content": "Memory B", "relevance_score": 0.8}
        ]

        formatted_a = format_memories_with_budget(memories_a, max_tokens=500)
        formatted_b = format_memories_with_budget(memories_b, max_tokens=500)

        # Should have similar structure (headers, formatting)
        assert formatted_a.count("##") == formatted_b.count("##") or \
               abs(formatted_a.count("##") - formatted_b.count("##")) <= 1

    def test_markdown_safe(self):
        """Should escape or handle markdown special characters"""
        memories = [
            {
                "content": "Use **bold** and *italic* and # headers",
                "relevance_score": 0.9
            }
        ]

        formatted = format_memories_with_budget(memories, max_tokens=500)

        # Should not break markdown structure
        assert isinstance(formatted, str)
        assert len(formatted) > 0
