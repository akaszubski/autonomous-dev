"""
Unit tests for memory_relevance.py - TF-IDF-based relevance scoring

Tests the memory relevance scoring system that ranks memories by:
- TF-IDF keyword matching
- Recency boost for recent memories
- Threshold filtering for low-relevance results

TDD Phase: RED - Tests written before implementation
Expected: All tests FAIL until memory_relevance.py is implemented
"""

import pytest
from datetime import datetime, timedelta
from autonomous_dev.lib.memory_relevance import (
    extract_keywords,
    calculate_relevance,
    rank_memories,
)


class TestExtractKeywords:
    """Test keyword extraction with stopword removal and normalization"""

    def test_extract_keywords_basic(self):
        """Should extract meaningful keywords from text"""
        text = "implement JWT authentication with bcrypt hashing"
        keywords = extract_keywords(text)

        assert "implement" in keywords or "jwt" in keywords
        assert "authentication" in keywords
        assert "bcrypt" in keywords or "hashing" in keywords
        assert len(keywords) >= 3

    def test_extract_keywords_removes_stopwords(self):
        """Should remove common stopwords (the, and, is, etc.)"""
        text = "the user is authenticated and the token is valid"
        keywords = extract_keywords(text)

        assert "the" not in keywords
        assert "is" not in keywords
        assert "and" not in keywords
        assert "user" in keywords or "authenticated" in keywords

    def test_extract_keywords_handles_punctuation(self):
        """Should normalize punctuation and special characters"""
        text = "JWT! authentication, bcrypt-hashing (secure)"
        keywords = extract_keywords(text)

        # Keywords should not contain punctuation
        for keyword in keywords:
            assert not any(char in keyword for char in "!,().-")

    def test_extract_keywords_case_insensitive(self):
        """Should normalize to lowercase for matching"""
        text = "JWT Authentication BCRYPT Hashing"
        keywords = extract_keywords(text)

        # All keywords should be lowercase
        for keyword in keywords:
            assert keyword == keyword.lower()

    def test_extract_keywords_empty_string(self):
        """Should handle empty input gracefully"""
        keywords = extract_keywords("")
        assert keywords == []


class TestCalculateRelevance:
    """Test TF-IDF relevance scoring between query and memory"""

    def test_calculate_relevance_exact_match(self):
        """Should return high score for exact keyword matches"""
        query = "JWT authentication bcrypt"
        memory_text = "Implemented JWT authentication with bcrypt hashing"

        score = calculate_relevance(query, memory_text)
        assert score > 0.5  # High relevance
        assert 0.0 <= score <= 1.0  # Normalized score

    def test_calculate_relevance_partial_match(self):
        """Should return moderate score for partial matches"""
        query = "JWT authentication"
        memory_text = "Added user session management with cookies"

        score = calculate_relevance(query, memory_text)
        assert score < 0.5  # Lower relevance
        assert score >= 0.0

    def test_calculate_relevance_no_match(self):
        """Should return zero or very low score for no matches"""
        query = "JWT authentication"
        memory_text = "Fixed CSS styling on homepage"

        score = calculate_relevance(query, memory_text)
        assert score < 0.2  # Very low relevance

    def test_calculate_relevance_empty_query(self):
        """Should handle empty query gracefully"""
        score = calculate_relevance("", "Some memory text")
        assert score == 0.0

    def test_calculate_relevance_empty_memory(self):
        """Should handle empty memory text gracefully"""
        score = calculate_relevance("JWT authentication", "")
        assert score == 0.0


class TestRecencyBoost:
    """Test recency boosting for recent memories"""

    def test_recency_boost_recent_memory(self):
        """Should boost score for memories from today"""
        query = "JWT authentication"
        memory = {
            "content": "Implemented JWT authentication",
            "timestamp": datetime.now().isoformat()
        }

        score_with_recency = calculate_relevance(
            query,
            memory["content"],
            timestamp=memory["timestamp"]
        )
        score_without_recency = calculate_relevance(query, memory["content"])

        assert score_with_recency > score_without_recency

    def test_recency_boost_old_memory(self):
        """Should not boost score for old memories (30+ days)"""
        query = "JWT authentication"
        old_timestamp = (datetime.now() - timedelta(days=35)).isoformat()
        memory = {
            "content": "Implemented JWT authentication",
            "timestamp": old_timestamp
        }

        score_with_recency = calculate_relevance(
            query,
            memory["content"],
            timestamp=memory["timestamp"]
        )
        score_without_recency = calculate_relevance(query, memory["content"])

        # Old memories should have minimal or no boost
        assert score_with_recency <= score_without_recency * 1.1


class TestRankMemories:
    """Test memory ranking with filtering and sorting"""

    def test_rank_memories_filters_threshold(self):
        """Should filter out memories below relevance threshold"""
        query = "JWT authentication"
        memories = [
            {"content": "Implemented JWT authentication", "id": "1"},
            {"content": "Fixed CSS styling", "id": "2"},
            {"content": "Added bcrypt hashing", "id": "3"},
        ]

        ranked = rank_memories(query, memories, threshold=0.3)

        # Low-relevance memories should be filtered out
        assert len(ranked) < len(memories)
        assert all(mem["relevance_score"] >= 0.3 for mem in ranked)

    def test_rank_memories_sorts_descending(self):
        """Should sort memories by relevance score (highest first)"""
        query = "JWT authentication bcrypt"
        memories = [
            {"content": "Fixed CSS styling", "id": "1"},
            {"content": "Implemented JWT authentication with bcrypt", "id": "2"},
            {"content": "Added user model", "id": "3"},
        ]

        ranked = rank_memories(query, memories, threshold=0.0)

        # Should be sorted descending by relevance
        for i in range(len(ranked) - 1):
            assert ranked[i]["relevance_score"] >= ranked[i + 1]["relevance_score"]

    def test_rank_memories_includes_scores(self):
        """Should add relevance_score field to each memory"""
        query = "JWT authentication"
        memories = [
            {"content": "Implemented JWT authentication", "id": "1"},
        ]

        ranked = rank_memories(query, memories)

        assert all("relevance_score" in mem for mem in ranked)
        assert all(isinstance(mem["relevance_score"], float) for mem in ranked)

    def test_rank_memories_empty_list(self):
        """Should handle empty memory list gracefully"""
        ranked = rank_memories("JWT authentication", [])
        assert ranked == []

    def test_rank_memories_custom_threshold(self):
        """Should respect custom threshold parameter"""
        query = "JWT authentication"
        memories = [
            {"content": "Implemented JWT with bcrypt", "id": "1"},
            {"content": "Fixed minor bug", "id": "2"},
        ]

        # High threshold should filter more aggressively
        ranked_strict = rank_memories(query, memories, threshold=0.7)
        ranked_lenient = rank_memories(query, memories, threshold=0.1)

        assert len(ranked_strict) <= len(ranked_lenient)


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_special_characters_in_query(self):
        """Should handle special characters in query"""
        query = "JWT! @authentication #bcrypt $hashing"
        memory_text = "Implemented JWT authentication with bcrypt"

        # Should not crash
        score = calculate_relevance(query, memory_text)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_unicode_characters(self):
        """Should handle unicode characters"""
        query = "JWT authentication 🔒"
        memory_text = "Implemented JWT authentication with bcrypt 🔐"

        score = calculate_relevance(query, memory_text)
        assert isinstance(score, float)

    def test_very_long_text(self):
        """Should handle very long memory text efficiently"""
        query = "JWT authentication"
        memory_text = "Implemented JWT authentication. " * 1000  # 3000+ words

        # Should complete in reasonable time
        score = calculate_relevance(query, memory_text)
        assert isinstance(score, float)

    def test_malformed_timestamp(self):
        """Should handle malformed timestamps gracefully"""
        query = "JWT authentication"
        memory_text = "Implemented JWT authentication"

        # Invalid timestamp should not crash
        score = calculate_relevance(
            query,
            memory_text,
            timestamp="not-a-valid-timestamp"
        )
        assert isinstance(score, float)
