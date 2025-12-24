"""Tests for search utilities module."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from plugins.autonomous_dev.lib.search_utils import (
    WebFetchCache,
    check_knowledge_freshness,
    extract_keywords,
    parse_index_entry,
    score_pattern,
    score_source,
)


class TestWebFetchCache:
    """Tests for WebFetchCache class."""

    def test_cache_miss(self):
        """Test cache miss returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = WebFetchCache(Path(tmpdir))
            result = cache.get("https://example.com")
            assert result is None

    def test_cache_hit(self):
        """Test cache hit returns content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = WebFetchCache(Path(tmpdir))
            url = "https://example.com"
            content = "Test content"

            # Set cache
            cache.set(url, content)

            # Get from cache
            result = cache.get(url)
            assert result == content

    def test_cache_expiration(self):
        """Test expired cache entries return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = WebFetchCache(Path(tmpdir), ttl_days=0)  # Immediate expiration
            url = "https://example.com"
            content = "Test content"

            # Set cache
            cache.set(url, content)

            # Manually set expiry to past
            cache_file = cache._get_cache_path(url)
            cached_content = cache_file.read_text()

            # Replace expiry with yesterday
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            cached_content = cached_content.replace(
                "**Expires**:",
                f"**Expires**: {yesterday}\n# Old:",
                1
            )
            cache_file.write_text(cached_content)

            # Should be None now
            result = cache.get(url)
            assert result is None

    def test_clear_expired(self):
        """Test clearing expired cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = WebFetchCache(Path(tmpdir), ttl_days=7)

            # Create some cache entries
            urls = [f"https://example.com/{i}" for i in range(5)]
            for url in urls:
                cache.set(url, f"Content {url}")

            # Manually expire 2 entries
            for i in range(2):
                cache_file = cache._get_cache_path(urls[i])
                cached_content = cache_file.read_text()
                yesterday = (datetime.now() - timedelta(days=1)).isoformat()
                cached_content = cached_content.replace(
                    "**Expires**:",
                    f"**Expires**: {yesterday}\n# Old:",
                    1
                )
                cache_file.write_text(cached_content)

            # Clear expired
            removed = cache.clear_expired()
            assert removed == 2

            # Check remaining
            assert cache.get(urls[0]) is None  # Expired
            assert cache.get(urls[1]) is None  # Expired
            assert cache.get(urls[2]) is not None  # Still valid
            assert cache.get(urls[3]) is not None  # Still valid


class TestScoreSource:
    """Tests for score_source function."""

    def test_high_authority_source(self):
        """Test high authority sources get high scores."""
        score = score_source(
            "https://docs.python.org/guide",
            "Python Guide 2025",
            "Official Python tutorial"
        )
        assert score >= 0.7  # High authority + recent + quality content

    def test_medium_authority_source(self):
        """Test medium authority sources get medium scores."""
        score = score_source(
            "https://stackoverflow.com/questions/123",
            "How to Python",
            "Tutorial from 2024"
        )
        assert 0.3 <= score < 0.7  # Medium authority

    def test_low_authority_old_source(self):
        """Test low authority old sources get low scores."""
        score = score_source(
            "https://random.com/post",
            "Old post",
            "Content from 2020"
        )
        assert score < 0.3  # Low authority + old

    def test_recency_bonus(self):
        """Test recent content gets recency bonus."""
        current_year = datetime.now().year

        score_recent = score_source(
            "https://example.com",
            f"Guide {current_year}",
            f"Published in {current_year}"
        )

        score_old = score_source(
            "https://example.com",
            "Guide 2020",
            "Published in 2020"
        )

        assert score_recent > score_old

    def test_quality_indicators(self):
        """Test content quality indicators increase score."""
        score_tutorial = score_source(
            "https://example.com",
            "Tutorial: Best Practices Guide",
            "Official tutorial with code examples"
        )

        score_plain = score_source(
            "https://example.com",
            "Article",
            "Some content"
        )

        assert score_tutorial > score_plain


class TestScorePattern:
    """Tests for score_pattern function."""

    def test_high_quality_pattern(self):
        """Test high quality pattern gets high score."""
        score = score_pattern(
            file_path="src/auth/jwt.py",
            content='"""Docstring"""\ncode...',
            keyword_relevance=0.9,
            has_tests=True,
            has_docstrings=True,
            line_count=200,
            last_modified_days=10
        )
        assert score >= 0.7

    def test_low_quality_pattern(self):
        """Test low quality pattern gets low score."""
        score = score_pattern(
            file_path="src/utils/helpers.py",
            content="code",
            keyword_relevance=0.2,
            has_tests=False,
            has_docstrings=False,
            line_count=15,
            last_modified_days=365
        )
        assert score < 0.4

    def test_has_tests_bonus(self):
        """Test having tests increases score."""
        score_with_tests = score_pattern(
            "test.py", "content", 0.5, has_tests=True, line_count=50
        )

        score_without_tests = score_pattern(
            "test.py", "content", 0.5, has_tests=False, line_count=50
        )

        assert score_with_tests > score_without_tests

    def test_substantial_code_bonus(self):
        """Test substantial code (>50 lines) increases score."""
        score_large = score_pattern(
            "test.py", "content", 0.5, line_count=100
        )

        score_small = score_pattern(
            "test.py", "content", 0.5, line_count=20
        )

        assert score_large > score_small

    def test_recently_modified_bonus(self):
        """Test recently modified code increases score."""
        score_recent = score_pattern(
            "test.py", "content", 0.5, last_modified_days=10
        )

        score_old = score_pattern(
            "test.py", "content", 0.5, last_modified_days=365
        )

        assert score_recent > score_old


class TestCheckKnowledgeFreshness:
    """Tests for check_knowledge_freshness function."""

    def test_fresh_knowledge(self):
        """Test fresh knowledge is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create knowledge file with recent date
            knowledge_file = Path(tmpdir) / "knowledge.md"
            today = datetime.now().strftime("%Y-%m-%d")

            knowledge_file.write_text(f"""# Topic

**Date Researched**: {today}

Content...
""")

            is_fresh, age_days, message = check_knowledge_freshness(knowledge_file, max_age_days=180)

            assert is_fresh is True
            assert age_days == 0
            assert "Fresh" in message

    def test_stale_knowledge(self):
        """Test stale knowledge is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create knowledge file with old date
            knowledge_file = Path(tmpdir) / "knowledge.md"
            old_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")

            knowledge_file.write_text(f"""# Topic

**Date Researched**: {old_date}

Content...
""")

            is_fresh, age_days, message = check_knowledge_freshness(knowledge_file, max_age_days=180)

            assert is_fresh is False
            assert age_days == 200
            assert "Stale" in message

    def test_no_date_found(self):
        """Test handling of file without date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_file = Path(tmpdir) / "knowledge.md"
            knowledge_file.write_text("# Topic\n\nNo date here")

            is_fresh, age_days, message = check_knowledge_freshness(knowledge_file)

            assert is_fresh is False
            assert age_days == -1
            assert "No date found" in message

    def test_file_not_exists(self):
        """Test handling of non-existent file."""
        knowledge_file = Path("/tmp/nonexistent.md")

        is_fresh, age_days, message = check_knowledge_freshness(knowledge_file)

        assert is_fresh is False
        assert age_days == -1
        assert "does not exist" in message


class TestExtractKeywords:
    """Tests for extract_keywords function."""

    def test_extract_keywords(self):
        """Test keyword extraction from text."""
        text = "implement user authentication with JWT tokens for secure API access"
        keywords = extract_keywords(text, max_keywords=10)

        assert "authentication" in keywords
        assert "jwt" in keywords
        assert "tokens" in keywords
        assert "secure" in keywords
        assert "api" in keywords
        assert "access" in keywords

        # Stop words should be excluded
        assert "with" not in keywords
        assert "for" not in keywords

    def test_keyword_limit(self):
        """Test max keyword limit is respected."""
        text = "one two three four five six seven eight nine ten eleven twelve"
        keywords = extract_keywords(text, max_keywords=5)

        assert len(keywords) <= 5

    def test_min_length_filter(self):
        """Test minimum keyword length filter."""
        text = "a ab abc abcd abcde"
        keywords = extract_keywords(text, min_length=4)

        assert "a" not in keywords
        assert "ab" not in keywords
        assert "abc" not in keywords
        assert "abcd" in keywords
        assert "abcde" in keywords

    def test_frequency_ordering(self):
        """Test keywords ordered by frequency."""
        text = "python python python java java javascript"
        keywords = extract_keywords(text, max_keywords=3)

        # Python appears 3 times, should be first
        assert keywords[0] == "python"
        # Java appears 2 times, should be second
        assert keywords[1] == "java"


class TestParseIndexEntry:
    """Tests for parse_index_entry function."""

    def test_parse_existing_entry(self):
        """Test parsing an existing entry from INDEX."""
        index_content = """# Knowledge Base Index

## Best Practices

### Authentication Patterns
**File**: `best-practices/authentication.md`
**Date**: 2025-10-24
**Description**: JWT and OAuth patterns

## Research

### MCP Servers
**File**: `research/mcp-servers.md`
**Date**: 2025-10-23
**Description**: MCP server integration options
"""

        entry = parse_index_entry(index_content, "authentication")

        assert entry is not None
        assert entry["file"] == "best-practices/authentication.md"
        assert entry["date"] == "2025-10-24"
        assert "JWT" in entry["description"]

    def test_parse_nonexistent_entry(self):
        """Test parsing a non-existent entry."""
        index_content = """# Knowledge Base Index

## Best Practices

### Something Else
**File**: `best-practices/other.md`
**Date**: 2025-10-24
"""

        entry = parse_index_entry(index_content, "nonexistent")

        assert entry is None

    def test_parse_multiple_matches(self):
        """Test parsing returns first match when multiple exist."""
        index_content = """# Knowledge Base Index

## Research

### Python Testing
**File**: `research/python-testing.md`
**Date**: 2025-10-23

### Python Packaging
**File**: `research/python-packaging.md`
**Date**: 2025-10-22
"""

        entry = parse_index_entry(index_content, "python")

        assert entry is not None
        # Should return first match
        assert "testing" in entry["file"].lower() or "packaging" in entry["file"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
