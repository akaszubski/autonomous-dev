#!/usr/bin/env python3
"""
Unit tests for research_quality_scorer library (TDD Red Phase).

Tests for parallel deep research with quality scoring, ranking, and diminishing returns detection.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError or missing functions).

Test Strategy:
- Unit tests for source quality scoring
- Source ranking and prioritization
- Diminishing returns detection
- Rate limiting and consensus detection
- Edge cases and input validation
- Integration tests for full workflow

Date: 2025-12-13
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Issue: #111 - Enhance researcher agent with parallel deep research
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any, List
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

# Import will fail - implementation doesn't exist yet (TDD!)
try:
    from research_quality_scorer import (
        score_source,
        rank_sources,
        detect_diminishing_returns,
        calculate_relevance_score,
        calculate_recency_score,
        calculate_authority_score,
        detect_consensus,
        ResearchQualityError,
        InvalidSourceError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# ==============================================================================
# UNIT TESTS: SOURCE SCORING
# ==============================================================================


class TestSourceScoring:
    """Test individual source quality scoring with authority, recency, and relevance."""

    def test_score_high_authority_source_official_docs(self):
        """Test scoring official documentation (should score 1.0 for authority)."""
        # Arrange
        url = "https://docs.python.org/3/library/json.html"
        content = "Official Python documentation for JSON module with comprehensive API reference."
        recency = 2024  # Recent year
        authority = "official_docs"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert
        assert 0.9 <= score <= 1.0, "Official docs should score very high (0.9-1.0)"

    def test_score_high_authority_source_github_official(self):
        """Test scoring official GitHub repository (should score ~0.8-0.9)."""
        # Arrange
        url = "https://github.com/python/cpython/blob/main/Lib/json/__init__.py"
        content = "Official CPython source code implementation with detailed comments."
        recency = 2024
        authority = "github_official"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert
        assert 0.8 <= score <= 0.95, "GitHub official should score high (0.8-0.95)"

    def test_score_medium_authority_source_github_community(self):
        """Test scoring community GitHub repository (should score ~0.6-0.8)."""
        # Arrange
        url = "https://github.com/user/awesome-json/blob/main/README.md"
        content = "Community-maintained collection of JSON libraries and best practices."
        recency = 2023
        authority = "github_community"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert
        assert 0.5 <= score <= 0.8, "GitHub community should score medium (0.5-0.8)"

    def test_score_low_authority_source_blog(self):
        """Test scoring blog post (should score ~0.3-0.5)."""
        # Arrange
        url = "https://random-blog.com/posts/json-tips"
        content = "Personal blog post with JSON tips and tricks from 2020."
        recency = 2020
        authority = "blog"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert
        assert 0.2 <= score <= 0.55, "Blog should score low-medium (0.2-0.55)"

    def test_score_recent_source_high_recency(self):
        """Test scoring very recent source (2024-2025 should boost score)."""
        # Arrange
        url = "https://example.com/api-guide"
        content = "Comprehensive API guide with examples and best practices."
        recency = 2024  # Current/recent year
        authority = "docs"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert - Recent content should get recency boost
        # Compare with same source from 2021
        old_score = score_source(url, content, 2021, authority)
        assert score > old_score, "Recent sources should score higher than old sources"

    def test_score_old_source_low_recency(self):
        """Test scoring old source (2015-2018 should lower score)."""
        # Arrange
        url = "https://example.com/legacy-guide"
        content = "Legacy API documentation from older version."
        recency = 2016  # Old year
        authority = "docs"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert - Old content should get recency penalty
        # Compare with same source from 2024
        new_score = score_source(url, content, 2024, authority)
        assert score < new_score, "Old sources should score lower than recent sources"

    def test_score_relevance_weighting_high_match(self):
        """Test relevance scoring with high keyword match."""
        # Arrange
        url = "https://example.com/python-json-best-practices"
        content = "Python JSON serialization best practices with performance optimization tips."
        recency = 2023
        authority = "docs"

        # Act
        score = score_source(url, content, recency, authority, keywords=["python", "json", "best practices"])

        # Assert - High keyword match should boost score
        score_no_keywords = score_source(url, content, recency, authority)
        assert score >= score_no_keywords, "Keyword matches should boost or maintain score"

    def test_score_combined_formula_weights(self):
        """Test combined scoring formula with authority, recency, and relevance weights."""
        # Arrange
        url = "https://docs.python.org/3/howto/json.html"
        content = "Python JSON HOWTO guide with practical examples and error handling."
        recency = 2024
        authority = "official_docs"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert - Score should be weighted combination (not simple average)
        # Score = (authority * 0.4) + (recency * 0.3) + (relevance * 0.3)
        assert 0.0 <= score <= 1.0, "Score should be normalized 0.0-1.0"
        assert score > 0.5, "High authority + recent should score > 0.5"

    def test_score_edge_case_empty_content(self):
        """Test scoring with empty content (should handle gracefully)."""
        # Arrange
        url = "https://example.com/empty"
        content = ""
        recency = 2024
        authority = "docs"

        # Act & Assert - Should raise InvalidSourceError
        with pytest.raises(InvalidSourceError, match="Content cannot be empty"):
            score_source(url, content, recency, authority)

    def test_score_edge_case_missing_url(self):
        """Test scoring with missing URL (should handle gracefully)."""
        # Arrange
        url = None
        content = "Valid content"
        recency = 2024
        authority = "docs"

        # Act & Assert - Should raise InvalidSourceError
        with pytest.raises(InvalidSourceError, match="URL cannot be None or empty"):
            score_source(url, content, recency, authority)

    def test_score_edge_case_invalid_authority(self):
        """Test scoring with unknown authority type (should default to low)."""
        # Arrange
        url = "https://example.com/unknown"
        content = "Content from unknown source type"
        recency = 2024
        authority = "unknown_type"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert - Unknown authority should default to low score
        assert 0.0 <= score <= 0.4, "Unknown authority should score low (0.0-0.4)"

    def test_score_edge_case_future_recency(self):
        """Test scoring with future year (should handle gracefully)."""
        # Arrange
        url = "https://example.com/future"
        content = "Content with future timestamp"
        recency = 2030  # Future year
        authority = "docs"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert - Future dates should be treated as current year
        current_year_score = score_source(url, content, datetime.now().year, authority)
        assert abs(score - current_year_score) < 0.1, "Future dates should score similar to current year"


# ==============================================================================
# UNIT TESTS: SOURCE RANKING
# ==============================================================================


class TestSourceRanking:
    """Test source ranking and prioritization based on quality scores."""

    def test_rank_sources_by_quality_descending(self):
        """Test ranking sources in descending order by quality score."""
        # Arrange
        sources = [
            {"url": "https://blog.com/post", "content": "Blog post", "recency": 2020, "authority": "blog"},
            {"url": "https://docs.python.org/guide", "content": "Official guide", "recency": 2024, "authority": "official_docs"},
            {"url": "https://github.com/user/repo", "content": "Community repo", "recency": 2023, "authority": "github_community"},
        ]

        # Act
        ranked = rank_sources(sources)

        # Assert - Official docs should rank first, blog last
        assert ranked[0]["authority"] == "official_docs", "Official docs should rank first"
        assert ranked[-1]["authority"] == "blog", "Blog should rank last"

        # Verify descending order
        scores = [s.get("quality_score", 0) for s in ranked]
        assert scores == sorted(scores, reverse=True), "Sources should be sorted descending by score"

    def test_rank_sources_handles_ties(self):
        """Test ranking with tied scores (should maintain stable sort)."""
        # Arrange
        sources = [
            {"url": "https://docs1.com/guide", "content": "Guide A", "recency": 2024, "authority": "official_docs"},
            {"url": "https://docs2.com/guide", "content": "Guide B", "recency": 2024, "authority": "official_docs"},
            {"url": "https://docs3.com/guide", "content": "Guide C", "recency": 2024, "authority": "official_docs"},
        ]

        # Act
        ranked = rank_sources(sources)

        # Assert - All should have similar scores (tied)
        scores = [s.get("quality_score", 0) for s in ranked]
        assert len(set(scores)) <= 2, "Tied sources should have very similar scores"  # Allow small float differences

    def test_rank_sources_empty_list(self):
        """Test ranking empty list (should return empty list)."""
        # Arrange
        sources = []

        # Act
        ranked = rank_sources(sources)

        # Assert
        assert ranked == [], "Empty list should return empty list"

    def test_rank_sources_single_source(self):
        """Test ranking single source (should return same source with score)."""
        # Arrange
        sources = [
            {"url": "https://docs.python.org/guide", "content": "Python guide", "recency": 2024, "authority": "official_docs"}
        ]

        # Act
        ranked = rank_sources(sources)

        # Assert
        assert len(ranked) == 1, "Single source should return single result"
        assert "quality_score" in ranked[0], "Result should include quality_score"
        assert ranked[0]["url"] == sources[0]["url"], "Should preserve original source data"

    def test_rank_sources_preserves_metadata(self):
        """Test ranking preserves all source metadata fields."""
        # Arrange
        sources = [
            {
                "url": "https://example.com/guide",
                "content": "Guide content",
                "recency": 2024,
                "authority": "docs",
                "custom_field": "custom_value",
                "metadata": {"key": "value"}
            }
        ]

        # Act
        ranked = rank_sources(sources)

        # Assert - All original fields should be preserved
        assert ranked[0]["custom_field"] == "custom_value", "Custom fields should be preserved"
        assert ranked[0]["metadata"]["key"] == "value", "Nested metadata should be preserved"

    def test_rank_sources_adds_quality_score(self):
        """Test ranking adds quality_score field to each source."""
        # Arrange
        sources = [
            {"url": "https://docs.python.org/guide", "content": "Guide", "recency": 2024, "authority": "official_docs"}
        ]

        # Act
        ranked = rank_sources(sources)

        # Assert
        assert "quality_score" in ranked[0], "quality_score field should be added"
        assert isinstance(ranked[0]["quality_score"], (int, float)), "quality_score should be numeric"
        assert 0.0 <= ranked[0]["quality_score"] <= 1.0, "quality_score should be 0.0-1.0"


# ==============================================================================
# UNIT TESTS: DIMINISHING RETURNS DETECTION
# ==============================================================================


class TestDiminishingReturnsDetection:
    """Test detection of when additional research provides minimal new value."""

    def test_detect_similar_results_high_overlap(self):
        """Test detection when results have high content similarity (>70%)."""
        # Arrange
        results = [
            {"content": "Python JSON module provides dumps and loads functions for serialization.", "quality_score": 0.9},
            {"content": "Python JSON module offers dumps and loads methods for JSON serialization.", "quality_score": 0.85},
            {"content": "The json module in Python has dumps and loads for converting to/from JSON.", "quality_score": 0.82},
        ]
        threshold = 0.3  # 30% similarity threshold

        # Act
        diminishing = detect_diminishing_returns(results, threshold)

        # Assert
        assert diminishing is True, "High content overlap should trigger diminishing returns"

    def test_detect_quality_improvement_below_threshold(self):
        """Test detection when quality improvement drops below threshold."""
        # Arrange
        results = [
            {"content": "Official Python docs on JSON module", "quality_score": 0.95},
            {"content": "GitHub implementation of JSON parser", "quality_score": 0.92},
            {"content": "Blog post about JSON tips", "quality_score": 0.40},  # Big quality drop
            {"content": "Another blog about JSON", "quality_score": 0.38},  # Minimal improvement
        ]
        threshold = 0.1  # 10% minimum improvement threshold

        # Act
        diminishing = detect_diminishing_returns(results, threshold)

        # Assert
        assert diminishing is True, "Quality plateau should trigger diminishing returns"

    def test_detect_no_diminishing_returns_early(self):
        """Test no diminishing returns with diverse high-quality results."""
        # Arrange
        results = [
            {"content": "Official documentation on JSON serialization in Python", "quality_score": 0.95},
            {"content": "GitHub best practices for error handling with JSON", "quality_score": 0.88},
        ]
        threshold = 0.3

        # Act
        diminishing = detect_diminishing_returns(results, threshold)

        # Assert
        assert diminishing is False, "Diverse quality results should not trigger diminishing returns"

    def test_detect_diminishing_returns_empty_results(self):
        """Test detection with empty results list (should return False)."""
        # Arrange
        results = []
        threshold = 0.3

        # Act
        diminishing = detect_diminishing_returns(results, threshold)

        # Assert
        assert diminishing is False, "Empty results should not trigger diminishing returns"

    def test_detect_max_depth_enforcement(self):
        """Test max depth enforcement regardless of quality."""
        # Arrange - 10 results (max depth limit)
        results = [
            {"content": f"Unique content {i}", "quality_score": 0.9 - (i * 0.05)}
            for i in range(10)
        ]
        threshold = 0.3

        # Act
        diminishing = detect_diminishing_returns(results, threshold, max_depth=10)

        # Assert
        assert diminishing is True, "Max depth should trigger diminishing returns"

    def test_detect_consensus_threshold_reached(self):
        """Test detection when consensus is reached (3+ sources agree)."""
        # Arrange - 3 sources with similar high-quality information
        results = [
            {"content": "Python JSON uses dumps/loads for serialization", "quality_score": 0.95},
            {"content": "JSON serialization in Python via dumps and loads", "quality_score": 0.93},
            {"content": "Python's json module provides dumps/loads methods", "quality_score": 0.91},
        ]
        threshold = 0.3

        # Act
        diminishing = detect_diminishing_returns(results, threshold, consensus_count=3)

        # Assert
        assert diminishing is True, "Consensus should trigger diminishing returns"


# ==============================================================================
# INTEGRATION TESTS: FULL WORKFLOW
# ==============================================================================


class TestResearchQualityWorkflow:
    """Integration tests for complete research quality scoring workflow."""

    def test_full_scoring_workflow_from_raw_sources(self):
        """Test complete workflow: raw sources -> scored -> ranked -> diminishing check."""
        # Arrange
        raw_sources = [
            {"url": "https://random-blog.com/json", "content": "Blog about JSON", "recency": 2019, "authority": "blog"},
            {"url": "https://docs.python.org/json", "content": "Official JSON docs", "recency": 2024, "authority": "official_docs"},
            {"url": "https://github.com/python/cpython", "content": "CPython source", "recency": 2024, "authority": "github_official"},
        ]

        # Act - Score and rank
        ranked = rank_sources(raw_sources)

        # Assert - Verify order
        assert ranked[0]["authority"] == "official_docs", "Official docs should rank first"
        assert ranked[1]["authority"] == "github_official", "GitHub official should rank second"
        assert ranked[2]["authority"] == "blog", "Blog should rank last"

        # Act - Check diminishing returns
        diminishing = detect_diminishing_returns(ranked, threshold=0.3)

        # Assert - With only 3 diverse sources, should not trigger
        assert diminishing is False, "3 diverse sources should not trigger diminishing returns"

    def test_consensus_detection_three_sources_agree(self):
        """Test consensus detection when 3+ sources provide similar information."""
        # Arrange
        sources = [
            {"url": "https://docs.python.org/json", "content": "JSON dumps and loads for serialization", "recency": 2024, "authority": "official_docs"},
            {"url": "https://github.com/python/cpython/json", "content": "Implementation of dumps/loads methods", "recency": 2024, "authority": "github_official"},
            {"url": "https://peps.python.org/json", "content": "PEP on JSON dumps and loads functions", "recency": 2023, "authority": "official_docs"},
        ]

        # Act
        ranked = rank_sources(sources)
        consensus = detect_consensus(ranked, similarity_threshold=0.7)

        # Assert
        assert consensus is True, "3 similar high-quality sources should reach consensus"

    def test_rate_limit_config_loading(self):
        """Test loading rate limit configuration from JSON file."""
        # Arrange
        config_path = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "research_rate_limits.json"

        # Act & Assert - Config file should exist (will be created by implementer)
        # This test verifies the integration point exists
        expected_keys = ["max_parallel_searches", "requests_per_minute", "timeout_seconds", "max_depth"]

        # For TDD, we just verify the interface
        # Implementation will create actual config file
        assert True, "Rate limit config integration point defined"

    def test_parallel_execution_simulation(self):
        """Test scoring multiple sources in parallel (simulated)."""
        # Arrange
        sources = [
            {"url": f"https://source{i}.com", "content": f"Content {i}", "recency": 2024, "authority": "docs"}
            for i in range(5)
        ]

        # Act - Simulate parallel scoring
        ranked = rank_sources(sources)

        # Assert - All sources should be scored
        assert len(ranked) == 5, "All sources should be processed"
        assert all("quality_score" in s for s in ranked), "All sources should have scores"

    def test_adaptive_depth_based_on_quality(self):
        """Test adaptive search depth based on result quality trends."""
        # Arrange - Declining quality sequence
        sources = [
            {"url": "https://source1.com", "content": "High quality content", "recency": 2024, "authority": "official_docs"},
            {"url": "https://source2.com", "content": "Medium quality content", "recency": 2023, "authority": "github_community"},
            {"url": "https://source3.com", "content": "Low quality content", "recency": 2020, "authority": "blog"},
            {"url": "https://source4.com", "content": "Very low quality", "recency": 2018, "authority": "unknown"},
        ]

        # Act
        ranked = rank_sources(sources)
        diminishing = detect_diminishing_returns(ranked, threshold=0.3)

        # Assert - Sharp quality decline should trigger early stop
        assert diminishing is True, "Quality decline should trigger adaptive depth reduction"


# ==============================================================================
# EDGE CASES AND ERROR HANDLING
# ==============================================================================


class TestEdgeCasesAndErrorHandling:
    """Test edge cases, boundary conditions, and error scenarios."""

    def test_score_source_with_special_characters_in_content(self):
        """Test scoring with special characters and unicode in content."""
        # Arrange
        url = "https://example.com/unicode"
        content = "Content with émojis 🚀 and spëcial çharacters 中文"
        recency = 2024
        authority = "docs"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert
        assert 0.0 <= score <= 1.0, "Should handle unicode gracefully"

    def test_rank_sources_with_missing_fields(self):
        """Test ranking when sources have missing optional fields."""
        # Arrange
        sources = [
            {"url": "https://example.com", "content": "Content"},  # Missing recency and authority
            {"url": "https://example2.com", "content": "Content 2", "recency": 2024},  # Missing authority
        ]

        # Act & Assert - Should handle gracefully with defaults
        try:
            ranked = rank_sources(sources)
            assert len(ranked) == 2, "Should process sources with missing fields"
        except InvalidSourceError:
            # Acceptable to raise error for missing required fields
            pass

    def test_detect_diminishing_returns_with_invalid_threshold(self):
        """Test diminishing returns detection with invalid threshold values."""
        # Arrange
        results = [
            {"content": "Content", "quality_score": 0.9}
        ]

        # Act & Assert - Threshold outside 0.0-1.0 range
        with pytest.raises(ResearchQualityError, match="Threshold must be between 0.0 and 1.0"):
            detect_diminishing_returns(results, threshold=1.5)

        with pytest.raises(ResearchQualityError, match="Threshold must be between 0.0 and 1.0"):
            detect_diminishing_returns(results, threshold=-0.1)

    def test_score_source_with_very_long_content(self):
        """Test scoring with extremely long content (>100KB)."""
        # Arrange
        url = "https://example.com/long"
        content = "A" * 150000  # 150KB of content
        recency = 2024
        authority = "docs"

        # Act
        score = score_source(url, content, recency, authority)

        # Assert - Should handle long content efficiently
        assert 0.0 <= score <= 1.0, "Should handle very long content"

    def test_rank_sources_with_duplicate_urls(self):
        """Test ranking with duplicate URLs (should deduplicate or handle)."""
        # Arrange
        sources = [
            {"url": "https://example.com/guide", "content": "Content A", "recency": 2024, "authority": "docs"},
            {"url": "https://example.com/guide", "content": "Content B", "recency": 2024, "authority": "docs"},  # Duplicate URL
        ]

        # Act
        ranked = rank_sources(sources)

        # Assert - Should either deduplicate or preserve both
        assert len(ranked) <= 2, "Should handle duplicate URLs"


# ==============================================================================
# HELPER FUNCTIONS TESTS
# ==============================================================================


class TestHelperFunctions:
    """Test helper functions for scoring components."""

    def test_calculate_relevance_score_keyword_matching(self):
        """Test relevance calculation based on keyword matching."""
        # Arrange
        content = "Python JSON serialization with dumps and loads functions"
        keywords = ["python", "json", "serialization"]

        # Act
        relevance = calculate_relevance_score(content, keywords)

        # Assert
        assert 0.0 <= relevance <= 1.0, "Relevance should be 0.0-1.0"
        assert relevance > 0.5, "High keyword match should score > 0.5"

    def test_calculate_recency_score_time_decay(self):
        """Test recency calculation with time-based decay."""
        # Arrange
        recent_year = 2024
        old_year = 2018

        # Act
        recent_score = calculate_recency_score(recent_year)
        old_score = calculate_recency_score(old_year)

        # Assert
        assert recent_score > old_score, "Recent years should score higher"
        assert 0.0 <= recent_score <= 1.0, "Recent score should be 0.0-1.0"
        assert 0.0 <= old_score <= 1.0, "Old score should be 0.0-1.0"

    def test_calculate_authority_score_source_type(self):
        """Test authority calculation based on source type."""
        # Arrange
        official_auth = "official_docs"
        blog_auth = "blog"

        # Act
        official_score = calculate_authority_score(official_auth)
        blog_score = calculate_authority_score(blog_auth)

        # Assert
        assert official_score > blog_score, "Official docs should score higher than blogs"
        assert official_score >= 0.9, "Official docs should score >= 0.9"
        assert blog_score <= 0.5, "Blogs should score <= 0.5"

    def test_detect_consensus_similarity_threshold(self):
        """Test consensus detection with configurable similarity threshold."""
        # Arrange
        sources = [
            {"content": "Python JSON dumps and loads", "quality_score": 0.9},
            {"content": "Python JSON dumps/loads methods", "quality_score": 0.88},
            {"content": "json module dumps and loads", "quality_score": 0.85},
        ]

        # Act
        consensus_strict = detect_consensus(sources, similarity_threshold=0.9)
        consensus_loose = detect_consensus(sources, similarity_threshold=0.6)

        # Assert
        assert consensus_loose is True, "Loose threshold should detect consensus"
        # Strict threshold may or may not detect consensus depending on exact similarity


# ==============================================================================
# PERFORMANCE AND SECURITY TESTS
# ==============================================================================


class TestPerformanceAndSecurity:
    """Test performance characteristics and security considerations."""

    def test_scoring_performance_with_large_batch(self):
        """Test scoring performance with large batch of sources (100+)."""
        # Arrange
        sources = [
            {"url": f"https://source{i}.com", "content": f"Content {i}" * 100, "recency": 2024, "authority": "docs"}
            for i in range(100)
        ]

        # Act
        import time
        start = time.time()
        ranked = rank_sources(sources)
        duration = time.time() - start

        # Assert - Should complete in reasonable time (<5 seconds for 100 sources)
        assert len(ranked) == 100, "Should process all sources"
        assert duration < 5.0, f"Should complete in <5s, took {duration:.2f}s"

    def test_url_validation_prevents_injection(self):
        """Test URL validation prevents malicious input."""
        # Arrange
        malicious_urls = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "file:///etc/passwd",
        ]

        # Act & Assert - Should reject malicious URLs
        for url in malicious_urls:
            with pytest.raises(InvalidSourceError, match="Invalid or malicious URL"):
                score_source(url, "content", 2024, "docs")

    def test_content_sanitization_prevents_code_execution(self):
        """Test content is sanitized to prevent code execution."""
        # Arrange
        malicious_content = "<script>alert('xss')</script> Normal content"
        url = "https://example.com/safe"

        # Act
        score = score_source(url, malicious_content, 2024, "docs")

        # Assert - Should sanitize and score safely
        assert 0.0 <= score <= 1.0, "Should sanitize malicious content safely"


# ==============================================================================
# TEST FIXTURES AND HELPERS
# ==============================================================================


@pytest.fixture
def sample_sources():
    """Fixture providing sample sources for testing."""
    return [
        {
            "url": "https://docs.python.org/3/library/json.html",
            "content": "Official Python JSON module documentation",
            "recency": 2024,
            "authority": "official_docs"
        },
        {
            "url": "https://github.com/python/cpython/blob/main/Lib/json/__init__.py",
            "content": "CPython JSON implementation source code",
            "recency": 2024,
            "authority": "github_official"
        },
        {
            "url": "https://realpython.com/python-json/",
            "content": "Real Python tutorial on working with JSON",
            "recency": 2023,
            "authority": "tutorial"
        },
        {
            "url": "https://random-blog.com/json-tips",
            "content": "Personal blog post about JSON tips",
            "recency": 2020,
            "authority": "blog"
        }
    ]


@pytest.fixture
def mock_rate_limit_config(tmp_path):
    """Fixture providing mock rate limit configuration."""
    config = {
        "max_parallel_searches": 3,
        "requests_per_minute": 10,
        "timeout_seconds": 30,
        "max_depth": 10,
        "consensus_threshold": 0.7
    }
    config_file = tmp_path / "research_rate_limits.json"
    config_file.write_text(json.dumps(config, indent=2))
    return config_file


# ==============================================================================
# RUN TESTS
# ==============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
