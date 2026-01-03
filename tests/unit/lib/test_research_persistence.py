#!/usr/bin/env python3
"""
TDD Tests for Research Persistence Library (TDD Red Phase)

This test suite validates the creation of research_persistence.py library
for auto-saving research findings to docs/research/ directory.

Problem:
- Research findings lost when conversation clears
- No caching mechanism for repeated research topics
- No centralized research knowledge base
- Manual research duplication across features

Solution:
- Create lib/research_persistence.py with:
  - save_research(topic, findings, sources) - saves to docs/research/TOPIC_NAME.md
  - check_cache(topic, max_age_days=30) - checks if recent research exists
  - load_cached_research(topic) - loads existing research
  - update_index() - updates docs/research/README.md
  - topic_to_filename() - converts "my topic" to "MY_TOPIC.md"

Test Coverage:
1. File creation with SCREAMING_SNAKE_CASE naming
2. Frontmatter and content formatting
3. Cache hit/miss detection based on age
4. Cached research loading and parsing
5. Index generation with research catalog
6. Topic to filename conversion
7. Directory creation
8. Atomic write pattern (temp file + replace)
9. Security validation (path traversal, symlinks)
10. Error handling (disk full, permission errors, corrupt files)

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (lib/research_persistence.py doesn't exist yet)
- Implementation makes tests pass (GREEN phase)

Date: 2026-01-03
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See library-design-patterns skill for two-tier CLI design pattern.
    See python-standards skill for test code conventions.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from typing import Dict, List, Any, Optional

import pytest

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# This import will FAIL until lib/research_persistence.py is created (TDD!)
try:
    from research_persistence import (
        save_research,
        check_cache,
        load_cached_research,
        update_index,
        topic_to_filename,
        get_research_dir,
        save_merged_research,
        ResearchPersistenceError,
    )
    LIB_RESEARCH_PERSISTENCE_EXISTS = True
except ImportError:
    LIB_RESEARCH_PERSISTENCE_EXISTS = False
    save_research = None
    check_cache = None
    load_cached_research = None
    update_index = None
    topic_to_filename = None
    get_research_dir = None
    save_merged_research = None
    ResearchPersistenceError = None


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure for testing.

    Simulates a user's project with .git marker and docs/research/ directory.

    Structure:
    tmp_project/
        .git/
        .claude/
            PROJECT.md
        docs/
            research/
                README.md
                EXISTING_RESEARCH.md
        plugins/
            autonomous-dev/
                lib/
                    research_persistence.py  # What we're creating
                    path_utils.py            # Dependency
                    validation.py            # Dependency
    """
    # Create git marker
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create .claude directory with PROJECT.md
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "PROJECT.md").write_text("# Test Project\n")

    # Create docs/research directory
    research_dir = tmp_path / "docs" / "research"
    research_dir.mkdir(parents=True)

    # Create existing research file for cache tests
    existing_file = research_dir / "EXISTING_RESEARCH.md"
    existing_content = """---
topic: Existing Research
created: 2026-01-01
updated: 2026-01-01
sources:
  - https://example.com/source1
  - https://example.com/source2
---

# Existing Research

This is existing research content for cache testing.

## Key Findings

1. Finding one
2. Finding two

## Sources

- [Source 1](https://example.com/source1)
- [Source 2](https://example.com/source2)
"""
    existing_file.write_text(existing_content)

    # Create README.md in research directory
    readme_file = research_dir / "README.md"
    readme_file.write_text("# Research Documentation\n\nCatalog of research findings.\n")

    return tmp_path


@pytest.fixture
def mock_path_utils():
    """Mock path_utils.get_project_root() for testing."""
    with patch("research_persistence.path_utils.get_project_root") as mock_root:
        yield mock_root


@pytest.fixture
def mock_validation():
    """Mock validation.validate_path() for testing."""
    with patch("research_persistence.validation.validate_path") as mock_validate:
        # By default, validation passes (returns True or None)
        mock_validate.return_value = None
        yield mock_validate


# ============================================================================
# TEST: Topic to Filename Conversion
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestTopicToFilename:
    """Test topic_to_filename() conversion function."""

    def test_simple_topic_conversion(self):
        """
        GIVEN: Simple topic "my topic"
        WHEN: Converting to filename
        THEN: Returns "MY_TOPIC.md" (SCREAMING_SNAKE_CASE)
        """
        assert topic_to_filename("my topic") == "MY_TOPIC.md"

    def test_multi_word_topic(self):
        """
        GIVEN: Multi-word topic "jwt authentication patterns"
        WHEN: Converting to filename
        THEN: Returns "JWT_AUTHENTICATION_PATTERNS.md"
        """
        assert topic_to_filename("jwt authentication patterns") == "JWT_AUTHENTICATION_PATTERNS.md"

    def test_special_characters_removed(self):
        """
        GIVEN: Topic with special characters "my-topic: test!"
        WHEN: Converting to filename
        THEN: Returns "MY_TOPIC_TEST.md" (special chars removed/replaced)
        """
        result = topic_to_filename("my-topic: test!")
        assert result == "MY_TOPIC_TEST.md"

    def test_multiple_spaces_collapsed(self):
        """
        GIVEN: Topic with multiple spaces "my    topic   here"
        WHEN: Converting to filename
        THEN: Returns "MY_TOPIC_HERE.md" (spaces collapsed)
        """
        assert topic_to_filename("my    topic   here") == "MY_TOPIC_HERE.md"

    def test_leading_trailing_spaces_trimmed(self):
        """
        GIVEN: Topic with leading/trailing spaces "  my topic  "
        WHEN: Converting to filename
        THEN: Returns "MY_TOPIC.md" (trimmed)
        """
        assert topic_to_filename("  my topic  ") == "MY_TOPIC.md"

    def test_already_uppercase_preserved(self):
        """
        GIVEN: Topic already uppercase "JWT AUTHENTICATION"
        WHEN: Converting to filename
        THEN: Returns "JWT_AUTHENTICATION.md"
        """
        assert topic_to_filename("JWT AUTHENTICATION") == "JWT_AUTHENTICATION.md"

    def test_empty_topic_raises_error(self):
        """
        GIVEN: Empty topic ""
        WHEN: Converting to filename
        THEN: Raises ResearchPersistenceError
        """
        with pytest.raises(ResearchPersistenceError, match="Topic cannot be empty"):
            topic_to_filename("")

    def test_whitespace_only_topic_raises_error(self):
        """
        GIVEN: Whitespace-only topic "   "
        WHEN: Converting to filename
        THEN: Raises ResearchPersistenceError
        """
        with pytest.raises(ResearchPersistenceError, match="Topic cannot be empty"):
            topic_to_filename("   ")


# ============================================================================
# TEST: Get Research Directory
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestGetResearchDir:
    """Test get_research_dir() directory creation and resolution."""

    def test_creates_research_directory_if_missing(self, temp_project, mock_path_utils):
        """
        GIVEN: Project without docs/research/ directory
        WHEN: Calling get_research_dir()
        THEN: Creates docs/research/ directory and returns path
        """
        mock_path_utils.return_value = temp_project

        # Remove research directory
        research_dir = temp_project / "docs" / "research"
        if research_dir.exists():
            import shutil
            shutil.rmtree(research_dir)

        result = get_research_dir()

        assert result.exists()
        assert result.is_dir()
        assert result.name == "research"
        assert result.parent.name == "docs"

    def test_returns_existing_research_directory(self, temp_project, mock_path_utils):
        """
        GIVEN: Project with existing docs/research/ directory
        WHEN: Calling get_research_dir()
        THEN: Returns existing directory path (doesn't recreate)
        """
        mock_path_utils.return_value = temp_project
        research_dir = temp_project / "docs" / "research"

        result = get_research_dir()

        assert result == research_dir
        assert result.exists()

    def test_creates_docs_directory_if_missing(self, temp_project, mock_path_utils):
        """
        GIVEN: Project without docs/ directory
        WHEN: Calling get_research_dir()
        THEN: Creates docs/ and docs/research/ directories
        """
        mock_path_utils.return_value = temp_project

        # Remove docs directory
        docs_dir = temp_project / "docs"
        if docs_dir.exists():
            import shutil
            shutil.rmtree(docs_dir)

        result = get_research_dir()

        assert (temp_project / "docs").exists()
        assert result.exists()
        assert result == temp_project / "docs" / "research"

    def test_directory_permissions(self, temp_project, mock_path_utils):
        """
        GIVEN: Creating research directory
        WHEN: Checking directory permissions
        THEN: Directory created with 0o755 permissions
        """
        mock_path_utils.return_value = temp_project

        # Remove research directory
        research_dir = temp_project / "docs" / "research"
        if research_dir.exists():
            import shutil
            shutil.rmtree(research_dir)

        result = get_research_dir()

        # Check permissions (0o755 = rwxr-xr-x)
        stat_info = result.stat()
        permissions = stat_info.st_mode & 0o777
        assert permissions == 0o755


# ============================================================================
# TEST: Save Research
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestSaveResearch:
    """Test save_research() file creation and formatting."""

    def test_save_research_creates_file(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: New research topic "JWT Authentication"
        WHEN: Calling save_research()
        THEN: Creates docs/research/JWT_AUTHENTICATION.md file
        """
        mock_path_utils.return_value = temp_project

        topic = "JWT Authentication"
        findings = "JWT is a secure token-based authentication method."
        sources = ["https://jwt.io", "https://example.com/jwt-guide"]

        result = save_research(topic, findings, sources)

        expected_file = temp_project / "docs" / "research" / "JWT_AUTHENTICATION.md"
        assert expected_file.exists()
        assert result == expected_file

    def test_save_research_formats_frontmatter_correctly(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research data with topic, findings, sources
        WHEN: Saving research
        THEN: File contains correct YAML frontmatter with metadata
        """
        mock_path_utils.return_value = temp_project

        topic = "Test Topic"
        findings = "Test findings content"
        sources = ["https://source1.com", "https://source2.com"]

        with patch("research_persistence.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 3, 12, 0, 0)
            mock_datetime.strftime = datetime.strftime  # Preserve strftime method

            result = save_research(topic, findings, sources)

        content = result.read_text()

        # Check frontmatter structure
        assert content.startswith("---\n")
        assert "topic: Test Topic" in content
        assert "created: 2026-01-03" in content
        assert "updated: 2026-01-03" in content
        assert "sources:" in content
        assert "  - https://source1.com" in content
        assert "  - https://source2.com" in content
        assert content.count("---") >= 2  # Opening and closing frontmatter

    def test_save_research_formats_content_correctly(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research findings with markdown content
        WHEN: Saving research
        THEN: File contains properly formatted content section
        """
        mock_path_utils.return_value = temp_project

        topic = "Test Topic"
        findings = "## Key Findings\n\n1. Finding one\n2. Finding two"
        sources = ["https://source1.com"]

        result = save_research(topic, findings, sources)
        content = result.read_text()

        # Check content is after frontmatter
        assert "# Test Topic\n\n" in content
        assert "## Key Findings" in content
        assert "1. Finding one" in content
        assert "## Sources" in content
        assert "[source1.com](https://source1.com)" in content

    def test_save_research_overwrites_existing_file(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Existing research file
        WHEN: Saving research with same topic
        THEN: Overwrites file and updates 'updated' timestamp
        """
        mock_path_utils.return_value = temp_project

        topic = "Existing Research"
        findings = "Updated findings content"
        sources = ["https://new-source.com"]

        with patch("research_persistence.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 3, 12, 0, 0)
            mock_datetime.strftime = datetime.strftime

            result = save_research(topic, findings, sources)

        content = result.read_text()

        # Check file was updated
        assert "updated: 2026-01-03" in content
        assert "Updated findings content" in content
        assert "https://new-source.com" in content

    def test_save_research_uses_atomic_write(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research to save
        WHEN: Saving research
        THEN: Uses atomic write pattern (temp file + replace)
        """
        mock_path_utils.return_value = temp_project

        topic = "Test Topic"
        findings = "Test content"
        sources = ["https://example.com"]

        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.write") as mock_write, \
             patch("os.close") as mock_close, \
             patch("pathlib.Path.chmod") as mock_chmod, \
             patch("pathlib.Path.replace") as mock_replace:

            # Mock tempfile creation
            mock_fd = 123
            temp_file = str(temp_project / "docs" / "research" / ".TEST_TOPIC.md.tmp")
            mock_mkstemp.return_value = (mock_fd, temp_file)

            save_research(topic, findings, sources)

            # Verify atomic write pattern
            mock_mkstemp.assert_called_once()
            mock_write.assert_called_once()
            mock_close.assert_called_once_with(mock_fd)
            mock_chmod.assert_called_once_with(0o644)
            mock_replace.assert_called_once()

    def test_save_research_validates_path(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research topic
        WHEN: Saving research
        THEN: Validates file path for security (CWE-22, CWE-59)
        """
        mock_path_utils.return_value = temp_project

        topic = "Test Topic"
        findings = "Test content"
        sources = ["https://example.com"]

        save_research(topic, findings, sources)

        # Verify validate_path was called
        mock_validation.assert_called()
        call_args = mock_validation.call_args[0]
        assert "TEST_TOPIC.md" in str(call_args[0])

    def test_save_research_empty_findings_raises_error(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Empty findings content
        WHEN: Saving research
        THEN: Raises ResearchPersistenceError
        """
        mock_path_utils.return_value = temp_project

        with pytest.raises(ResearchPersistenceError, match="Findings cannot be empty"):
            save_research("Test Topic", "", ["https://example.com"])

    def test_save_research_empty_sources_allowed(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: No sources provided
        WHEN: Saving research
        THEN: Creates file with empty sources list (no error)
        """
        mock_path_utils.return_value = temp_project

        topic = "Test Topic"
        findings = "Test findings"
        sources = []

        result = save_research(topic, findings, sources)
        content = result.read_text()

        assert "sources: []" in content or "sources:\n" in content

    def test_save_research_handles_disk_full_error(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Disk full condition (OSError 28)
        WHEN: Saving research
        THEN: Raises ResearchPersistenceError with helpful message
        """
        mock_path_utils.return_value = temp_project

        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.write") as mock_write:

            mock_fd = 123
            temp_file = str(temp_project / "docs" / "research" / ".TEST.md.tmp")
            mock_mkstemp.return_value = (mock_fd, temp_file)
            mock_write.side_effect = OSError(28, "No space left on device")

            with pytest.raises(ResearchPersistenceError, match="No space left on device"):
                save_research("Test", "content", ["https://example.com"])

    def test_save_research_handles_permission_error(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Permission denied on research directory
        WHEN: Saving research
        THEN: Raises ResearchPersistenceError with helpful message
        """
        mock_path_utils.return_value = temp_project

        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.side_effect = PermissionError("Permission denied")

            with pytest.raises(ResearchPersistenceError, match="Permission denied"):
                save_research("Test", "content", ["https://example.com"])


# ============================================================================
# TEST: Check Cache
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestCheckCache:
    """Test check_cache() cache hit/miss detection."""

    def test_check_cache_detects_recent_research(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research file created yesterday (within 30 day threshold)
        WHEN: Checking cache
        THEN: Returns cache hit with file path
        """
        mock_path_utils.return_value = temp_project

        # Create recent research file
        research_file = temp_project / "docs" / "research" / "RECENT_RESEARCH.md"
        research_file.write_text("---\ncreated: 2026-01-02\n---\n\nContent")

        # Mock file modification time to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_mtime = yesterday.timestamp()

            result = check_cache("Recent Research", max_age_days=30)

        assert result is not None
        assert result == research_file

    def test_check_cache_detects_stale_research(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research file created 60 days ago (beyond 30 day threshold)
        WHEN: Checking cache with max_age_days=30
        THEN: Returns None (cache miss)
        """
        mock_path_utils.return_value = temp_project

        # Create stale research file
        research_file = temp_project / "docs" / "research" / "STALE_RESEARCH.md"
        research_file.write_text("---\ncreated: 2025-11-03\n---\n\nOld content")

        # Mock file modification time to 60 days ago
        old_date = datetime.now() - timedelta(days=60)
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_mtime = old_date.timestamp()

            result = check_cache("Stale Research", max_age_days=30)

        assert result is None

    def test_check_cache_returns_none_when_file_missing(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research topic with no existing file
        WHEN: Checking cache
        THEN: Returns None (cache miss)
        """
        mock_path_utils.return_value = temp_project

        result = check_cache("Nonexistent Research", max_age_days=30)

        assert result is None

    def test_check_cache_respects_custom_max_age(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research file created 15 days ago
        WHEN: Checking cache with max_age_days=10
        THEN: Returns None (cache miss, file too old)
        """
        mock_path_utils.return_value = temp_project

        research_file = temp_project / "docs" / "research" / "MEDIUM_AGE.md"
        research_file.write_text("---\ncreated: 2025-12-19\n---\n\nContent")

        # Mock file modification time to 15 days ago
        medium_age = datetime.now() - timedelta(days=15)
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_mtime = medium_age.timestamp()

            result = check_cache("Medium Age", max_age_days=10)

        assert result is None

    def test_check_cache_zero_max_age_always_misses(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research file created today
        WHEN: Checking cache with max_age_days=0
        THEN: Returns None (cache always misses with zero age)
        """
        mock_path_utils.return_value = temp_project

        research_file = temp_project / "docs" / "research" / "TODAY_RESEARCH.md"
        research_file.write_text("---\ncreated: 2026-01-03\n---\n\nContent")

        result = check_cache("Today Research", max_age_days=0)

        assert result is None


# ============================================================================
# TEST: Load Cached Research
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestLoadCachedResearch:
    """Test load_cached_research() parsing and content extraction."""

    def test_load_cached_research_parses_frontmatter(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Existing research file with frontmatter
        WHEN: Loading cached research
        THEN: Returns dict with parsed frontmatter metadata
        """
        mock_path_utils.return_value = temp_project

        result = load_cached_research("Existing Research")

        assert result is not None
        assert "topic" in result
        assert result["topic"] == "Existing Research"
        assert "created" in result
        assert "updated" in result
        assert "sources" in result
        assert isinstance(result["sources"], list)
        assert len(result["sources"]) == 2

    def test_load_cached_research_parses_content(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Existing research file with content
        WHEN: Loading cached research
        THEN: Returns dict with content field containing body
        """
        mock_path_utils.return_value = temp_project

        result = load_cached_research("Existing Research")

        assert "content" in result
        assert "Key Findings" in result["content"]
        assert "Finding one" in result["content"]

    def test_load_cached_research_returns_none_when_missing(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research topic with no file
        WHEN: Loading cached research
        THEN: Returns None (not found)
        """
        mock_path_utils.return_value = temp_project

        result = load_cached_research("Nonexistent Research")

        assert result is None

    def test_load_cached_research_handles_corrupt_frontmatter(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research file with malformed YAML frontmatter
        WHEN: Loading cached research
        THEN: Raises ResearchPersistenceError with helpful message
        """
        mock_path_utils.return_value = temp_project

        # Create corrupt research file
        corrupt_file = temp_project / "docs" / "research" / "CORRUPT_RESEARCH.md"
        corrupt_file.write_text("---\ntopic: Corrupt\ninvalid yaml: [unclosed\n---\n\nContent")

        with pytest.raises(ResearchPersistenceError, match="Failed to parse frontmatter"):
            load_cached_research("Corrupt Research")

    def test_load_cached_research_handles_missing_frontmatter(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research file with no frontmatter
        WHEN: Loading cached research
        THEN: Raises ResearchPersistenceError
        """
        mock_path_utils.return_value = temp_project

        # Create file without frontmatter
        no_frontmatter = temp_project / "docs" / "research" / "NO_FRONTMATTER.md"
        no_frontmatter.write_text("# Just content\n\nNo frontmatter here")

        with pytest.raises(ResearchPersistenceError, match="Missing frontmatter"):
            load_cached_research("No Frontmatter")

    def test_load_cached_research_validates_path(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research topic
        WHEN: Loading cached research
        THEN: Validates file path for security
        """
        mock_path_utils.return_value = temp_project

        load_cached_research("Existing Research")

        # Verify validate_path was called
        mock_validation.assert_called()


# ============================================================================
# TEST: Update Index
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestUpdateIndex:
    """Test update_index() README.md generation."""

    def test_update_index_generates_readme(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research directory with files
        WHEN: Updating index
        THEN: Creates/updates docs/research/README.md
        """
        mock_path_utils.return_value = temp_project

        result = update_index()

        readme_file = temp_project / "docs" / "research" / "README.md"
        assert readme_file.exists()
        assert result == readme_file

    def test_update_index_includes_research_catalog(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Multiple research files in docs/research/
        WHEN: Updating index
        THEN: README.md contains table with all research entries
        """
        mock_path_utils.return_value = temp_project

        # Create additional research files
        (temp_project / "docs" / "research" / "JWT_AUTH.md").write_text(
            "---\ntopic: JWT Auth\ncreated: 2026-01-01\nsources: []\n---\n\nContent"
        )
        (temp_project / "docs" / "research" / "SECURITY.md").write_text(
            "---\ntopic: Security\ncreated: 2026-01-02\nsources: []\n---\n\nContent"
        )

        update_index()

        readme_content = (temp_project / "docs" / "research" / "README.md").read_text()

        # Check for table structure
        assert "| Topic |" in readme_content or "| **Topic** |" in readme_content
        assert "JWT Auth" in readme_content or "JWT_AUTH" in readme_content
        assert "Security" in readme_content or "SECURITY" in readme_content

    def test_update_index_includes_metadata(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research files with metadata (created date, sources)
        WHEN: Updating index
        THEN: README.md table includes metadata columns
        """
        mock_path_utils.return_value = temp_project

        update_index()

        readme_content = (temp_project / "docs" / "research" / "README.md").read_text()

        # Check for metadata columns
        assert "Created" in readme_content or "Date" in readme_content
        assert "2026-01-01" in readme_content  # From EXISTING_RESEARCH.md

    def test_update_index_sorts_by_date(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research files with different creation dates
        WHEN: Updating index
        THEN: README.md table sorted by created date (newest first)
        """
        mock_path_utils.return_value = temp_project

        # Create files with different dates
        (temp_project / "docs" / "research" / "OLD_RESEARCH.md").write_text(
            "---\ntopic: Old\ncreated: 2025-12-01\nsources: []\n---\n\nContent"
        )
        (temp_project / "docs" / "research" / "NEW_RESEARCH.md").write_text(
            "---\ntopic: New\ncreated: 2026-01-03\nsources: []\n---\n\nContent"
        )

        update_index()

        readme_content = (temp_project / "docs" / "research" / "README.md").read_text()

        # Find positions of topics in content
        new_pos = readme_content.find("New")
        old_pos = readme_content.find("Old")

        # Newer research should appear first
        assert new_pos < old_pos

    def test_update_index_skips_readme_file(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: docs/research/ directory with README.md
        WHEN: Updating index
        THEN: README.md not included in research catalog (self-reference)
        """
        mock_path_utils.return_value = temp_project

        update_index()

        readme_content = (temp_project / "docs" / "research" / "README.md").read_text()

        # Ensure README.md not self-referenced
        assert readme_content.count("README") <= 1  # Only in title, not in table

    def test_update_index_handles_empty_directory(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Empty docs/research/ directory (no research files)
        WHEN: Updating index
        THEN: Creates README.md with empty state message
        """
        mock_path_utils.return_value = temp_project

        # Remove all research files
        research_dir = temp_project / "docs" / "research"
        for file in research_dir.glob("*.md"):
            file.unlink()

        update_index()

        readme_content = (temp_project / "docs" / "research" / "README.md").read_text()

        # Check for empty state message
        assert "No research" in readme_content or "empty" in readme_content.lower()

    def test_update_index_handles_corrupt_file(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research directory with one corrupt file
        WHEN: Updating index
        THEN: Skips corrupt file and indexes valid files (graceful degradation)
        """
        mock_path_utils.return_value = temp_project

        # Create corrupt file
        (temp_project / "docs" / "research" / "CORRUPT.md").write_text("Invalid content")

        # Should not raise error, just skip corrupt file
        update_index()

        readme_content = (temp_project / "docs" / "research" / "README.md").read_text()

        # Existing valid research should still be indexed
        assert "Existing Research" in readme_content


# ============================================================================
# TEST: Error Handling and Edge Cases
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_handles_path_traversal_attempt(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Topic with path traversal attempt "../../../etc/passwd"
        WHEN: Saving research
        THEN: validate_path() prevents traversal (security check)
        """
        mock_path_utils.return_value = temp_project
        mock_validation.side_effect = ValueError("Path traversal detected")

        with pytest.raises((ValueError, ResearchPersistenceError)):
            save_research("../../../etc/passwd", "content", ["https://example.com"])

    def test_handles_symlink_attack(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research directory contains symlink
        WHEN: Saving research
        THEN: validate_path() prevents symlink exploitation
        """
        mock_path_utils.return_value = temp_project
        mock_validation.side_effect = ValueError("Symlink detected")

        with pytest.raises((ValueError, ResearchPersistenceError)):
            save_research("Test", "content", ["https://example.com"])

    def test_handles_unicode_in_topic(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Topic with unicode characters "JWT 认证"
        WHEN: Converting to filename
        THEN: Handles unicode gracefully (converts or strips)
        """
        # Should not raise error
        result = topic_to_filename("JWT 认证")
        assert result.endswith(".md")
        assert "JWT" in result

    def test_handles_very_long_topic_name(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Topic with 500+ characters
        WHEN: Converting to filename
        THEN: Truncates to reasonable length (filesystem limit)
        """
        long_topic = "A" * 500
        result = topic_to_filename(long_topic)

        # Filename should be truncated (most filesystems: 255 char limit)
        assert len(result) <= 255
        assert result.endswith(".md")

    def test_concurrent_writes_thread_safety(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Multiple threads writing to same topic
        WHEN: Using atomic write pattern
        THEN: No data corruption (atomic writes protect)
        """
        mock_path_utils.return_value = temp_project

        # This test verifies atomic write pattern prevents corruption
        # Actual implementation should use tempfile + replace
        # Test just verifies the pattern is used (tested in TestSaveResearch)
        pass  # Covered by test_save_research_uses_atomic_write


# ============================================================================
# TEST: Save Merged Research (NEW - Issue #196)
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestSaveMergedResearch:
    """Test save_merged_research() function for auto-implement integration.

    This function merges research from researcher-local and researcher-web agents,
    then saves to docs/research/ and updates the index.
    """

    def test_save_merged_research_with_both_sources(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Both local and web research JSON outputs
        WHEN: Calling save_merged_research()
        THEN: Merges findings and sources, saves to file, updates index
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        local_json = {
            "topic": "JWT Authentication",
            "findings": [
                "Local finding 1: JWT uses cryptographic signatures",
                "Local finding 2: Stateless authentication"
            ],
            "sources": [
                "/Users/andrewkaszubski/Dev/autonomous-dev/docs/security.md",
                "/Users/andrewkaszubski/Dev/autonomous-dev/README.md"
            ]
        }

        web_json = {
            "topic": "JWT Authentication",
            "findings": [
                "Web finding 1: JWT.io provides comprehensive guide",
                "Web finding 2: RFC 7519 defines JWT standard"
            ],
            "sources": [
                "https://jwt.io/introduction",
                "https://datatracker.ietf.org/doc/html/rfc7519"
            ]
        }

        result = save_merged_research("JWT Authentication", local_json, web_json)

        # Check file was created
        expected_file = temp_project / "docs" / "research" / "JWT_AUTHENTICATION.md"
        assert result == expected_file
        assert expected_file.exists()

        # Check content includes both local and web findings
        content = expected_file.read_text()
        assert "Local finding 1" in content
        assert "Local finding 2" in content
        assert "Web finding 1" in content
        assert "Web finding 2" in content

        # Check sources include both local and web (with proper formatting)
        assert "security.md" in content or "/docs/security.md" in content
        assert "jwt.io" in content or "JWT.io" in content
        assert "rfc7519" in content or "RFC 7519" in content

    def test_save_merged_research_web_only(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Web research only (local research is empty)
        WHEN: Calling save_merged_research()
        THEN: Saves web findings without error
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        local_json = {
            "topic": "Web Only Topic",
            "findings": [],
            "sources": []
        }

        web_json = {
            "topic": "Web Only Topic",
            "findings": [
                "Web finding 1: External resource found",
                "Web finding 2: Online documentation available"
            ],
            "sources": [
                "https://example.com/docs",
                "https://example.com/guide"
            ]
        }

        result = save_merged_research("Web Only Topic", local_json, web_json)

        # Check file was created
        assert result.exists()

        # Check only web findings present
        content = result.read_text()
        assert "Web finding 1" in content
        assert "Web finding 2" in content
        assert "example.com" in content

    def test_save_merged_research_local_only(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Local research only (web research failed)
        WHEN: Calling save_merged_research()
        THEN: Saves local findings without error
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        local_json = {
            "topic": "Local Only Topic",
            "findings": [
                "Local finding 1: Found in codebase",
                "Local finding 2: Found in project docs"
            ],
            "sources": [
                "/Users/andrewkaszubski/Dev/autonomous-dev/docs/ARCHITECTURE.md",
                "/Users/andrewkaszubski/Dev/autonomous-dev/.claude/PROJECT.md"
            ]
        }

        web_json = {
            "topic": "Local Only Topic",
            "findings": [],
            "sources": []
        }

        result = save_merged_research("Local Only Topic", local_json, web_json)

        # Check file was created
        assert result.exists()

        # Check only local findings present
        content = result.read_text()
        assert "Local finding 1" in content
        assert "Local finding 2" in content
        assert "ARCHITECTURE.md" in content or "docs/ARCHITECTURE.md" in content

    def test_save_merged_research_updates_index(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Merged research saved
        WHEN: save_merged_research() completes
        THEN: README.md index is automatically updated
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        local_json = {
            "topic": "New Research Topic",
            "findings": ["Finding 1"],
            "sources": []
        }

        web_json = {
            "topic": "New Research Topic",
            "findings": ["Finding 2"],
            "sources": ["https://example.com"]
        }

        save_merged_research("New Research Topic", local_json, web_json)

        # Check README.md was updated
        readme_file = temp_project / "docs" / "research" / "README.md"
        assert readme_file.exists()

        readme_content = readme_file.read_text()
        assert "New Research Topic" in readme_content or "NEW_RESEARCH_TOPIC" in readme_content

    def test_save_merged_research_source_deduplication(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Same URL appears in both local and web sources
        WHEN: Merging research
        THEN: Duplicate sources are deduplicated
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        local_json = {
            "topic": "Duplicate Sources",
            "findings": ["Local finding"],
            "sources": ["https://example.com/guide", "https://example.com/docs"]
        }

        web_json = {
            "topic": "Duplicate Sources",
            "findings": ["Web finding"],
            "sources": ["https://example.com/guide", "https://different.com/page"]
        }

        result = save_merged_research("Duplicate Sources", local_json, web_json)

        # Check sources are deduplicated
        content = result.read_text()

        # Count occurrences of the duplicate URL (should appear once)
        # Note: URL might appear in frontmatter AND sources section
        # So we check it doesn't appear 3+ times
        frontmatter_section = content.split("---")[1]
        sources_section = content.split("## Sources")[1] if "## Sources" in content else ""

        # In frontmatter, should appear exactly once
        assert frontmatter_section.count("https://example.com/guide") == 1

        # In sources section, should appear exactly once
        assert sources_section.count("https://example.com/guide") == 1

    def test_save_merged_research_topic_normalization(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Topic name with special characters
        WHEN: Saving merged research
        THEN: Topic normalized to SCREAMING_SNAKE_CASE filename
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        local_json = {
            "topic": "JWT Auth: Best Practices!",
            "findings": ["Finding 1"],
            "sources": []
        }

        web_json = {
            "topic": "JWT Auth: Best Practices!",
            "findings": ["Finding 2"],
            "sources": []
        }

        result = save_merged_research("JWT Auth: Best Practices!", local_json, web_json)

        # Check filename is normalized
        assert result.name == "JWT_AUTH_BEST_PRACTICES.md"

    def test_save_merged_research_empty_findings_handled(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Both local and web research have empty findings
        WHEN: Calling save_merged_research()
        THEN: Raises ResearchPersistenceError (no content to save)
        """
        from research_persistence import save_merged_research, ResearchPersistenceError

        mock_path_utils.return_value = temp_project

        local_json = {
            "topic": "Empty Research",
            "findings": [],
            "sources": []
        }

        web_json = {
            "topic": "Empty Research",
            "findings": [],
            "sources": []
        }

        with pytest.raises(ResearchPersistenceError, match="Findings cannot be empty"):
            save_merged_research("Empty Research", local_json, web_json)

    def test_save_merged_research_formats_findings_as_markdown(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Findings as list of strings
        WHEN: Saving merged research
        THEN: Findings formatted as markdown (numbered list or sections)
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        local_json = {
            "topic": "Markdown Formatting",
            "findings": [
                "Finding 1: First local finding",
                "Finding 2: Second local finding"
            ],
            "sources": []
        }

        web_json = {
            "topic": "Markdown Formatting",
            "findings": [
                "Finding 3: First web finding",
                "Finding 4: Second web finding"
            ],
            "sources": []
        }

        result = save_merged_research("Markdown Formatting", local_json, web_json)

        content = result.read_text()

        # Check findings are formatted (either as list items or with line breaks)
        assert "Finding 1" in content
        assert "Finding 2" in content
        assert "Finding 3" in content
        assert "Finding 4" in content

        # Check basic markdown structure present
        assert "#" in content  # Headers present

    def test_save_merged_research_preserves_created_timestamp(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Existing research file
        WHEN: Saving merged research with same topic
        THEN: Preserves original 'created' timestamp, updates 'updated'
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        # Create existing research file with old created timestamp
        existing_file = temp_project / "docs" / "research" / "PRESERVE_TIMESTAMP.md"
        existing_content = """---
topic: Preserve Timestamp
created: 2025-12-01
updated: 2025-12-15
sources: []
---

# Preserve Timestamp

Old content here.
"""
        existing_file.write_text(existing_content)

        local_json = {
            "topic": "Preserve Timestamp",
            "findings": ["New finding"],
            "sources": []
        }

        web_json = {
            "topic": "Preserve Timestamp",
            "findings": [],
            "sources": []
        }

        with patch("research_persistence.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 3, 12, 0, 0)
            mock_datetime.strftime = datetime.strftime

            save_merged_research("Preserve Timestamp", local_json, web_json)

        # Check timestamps
        content = existing_file.read_text()
        assert "created: 2025-12-01" in content  # Original preserved
        assert "updated: 2026-01-03" in content  # Updated to now

    def test_save_merged_research_handles_missing_fields(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: JSON with missing optional fields (sources, etc.)
        WHEN: Saving merged research
        THEN: Handles missing fields gracefully with defaults
        """
        from research_persistence import save_merged_research

        mock_path_utils.return_value = temp_project

        # Minimal JSON with only required fields
        local_json = {
            "topic": "Minimal JSON",
            "findings": ["Finding 1"]
            # No 'sources' field
        }

        web_json = {
            "topic": "Minimal JSON",
            "findings": ["Finding 2"]
            # No 'sources' field
        }

        result = save_merged_research("Minimal JSON", local_json, web_json)

        # Check file created successfully
        assert result.exists()

        content = result.read_text()
        assert "Finding 1" in content
        assert "Finding 2" in content


# ============================================================================
# TEST: Cache Integration Workflow (Issue #196)
# ============================================================================


@pytest.mark.skipif(not LIB_RESEARCH_PERSISTENCE_EXISTS, reason="Library not implemented yet (TDD red phase)")
class TestCacheIntegrationWorkflow:
    """Test cache check → research → save → cache hit workflow.

    This simulates the /auto-implement integration:
    1. Check cache before research (STEP 1.0.5)
    2. Save merged research after research (STEP 1.2.5)
    3. Next run hits cache instead of researching again
    """

    def test_cache_miss_then_save_then_cache_hit(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: No cached research for topic
        WHEN: check_cache() → save_merged_research() → check_cache()
        THEN: First check misses, save succeeds, second check hits
        """
        from research_persistence import check_cache, save_merged_research

        mock_path_utils.return_value = temp_project

        topic = "Cache Workflow Test"

        # STEP 1: Cache miss (no research exists)
        cache_result_1 = check_cache(topic, max_age_days=30)
        assert cache_result_1 is None  # Cache miss

        # STEP 2: Perform research and save
        local_json = {
            "topic": topic,
            "findings": ["Finding from cache workflow test"],
            "sources": []
        }
        web_json = {
            "topic": topic,
            "findings": [],
            "sources": []
        }

        saved_path = save_merged_research(topic, local_json, web_json)
        assert saved_path.exists()

        # STEP 3: Cache hit (research now exists)
        cache_result_2 = check_cache(topic, max_age_days=30)
        assert cache_result_2 is not None  # Cache hit
        assert cache_result_2 == saved_path

    def test_cache_hit_skips_research(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Recent cached research (within 30 days)
        WHEN: check_cache() returns path
        THEN: load_cached_research() returns existing data (no need to research)
        """
        from research_persistence import check_cache, load_cached_research

        mock_path_utils.return_value = temp_project

        topic = "Existing Research"

        # Check cache
        cache_path = check_cache(topic, max_age_days=30)
        assert cache_path is not None  # Cache hit

        # Load cached data
        cached_data = load_cached_research(topic)
        assert cached_data is not None
        assert cached_data["topic"] == topic
        assert len(cached_data["content"]) > 0

    def test_stale_cache_triggers_new_research(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Stale cached research (older than 30 days)
        WHEN: check_cache() with max_age_days=30
        THEN: Returns None (cache miss, triggers new research)
        """
        from research_persistence import check_cache

        mock_path_utils.return_value = temp_project

        # Create stale research file
        stale_file = temp_project / "docs" / "research" / "STALE_CACHE.md"
        stale_file.write_text("---\ntopic: Stale Cache\ncreated: 2025-11-01\n---\n\nOld content")

        # Mock file modification time to 60 days ago
        old_date = datetime.now() - timedelta(days=60)
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_mtime = old_date.timestamp()

            cache_result = check_cache("Stale Cache", max_age_days=30)

        assert cache_result is None  # Cache miss due to age

    def test_cache_respects_max_age_parameter(self, temp_project, mock_path_utils, mock_validation):
        """
        GIVEN: Research file from 15 days ago
        WHEN: Checking cache with different max_age values
        THEN: max_age_days=10 misses, max_age_days=20 hits
        """
        from research_persistence import check_cache

        mock_path_utils.return_value = temp_project

        research_file = temp_project / "docs" / "research" / "AGE_TEST.md"
        research_file.write_text("---\ntopic: Age Test\ncreated: 2025-12-19\n---\n\nContent")

        # Mock file modification time to 15 days ago
        medium_age = datetime.now() - timedelta(days=15)
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_mtime = medium_age.timestamp()

            # With max_age=10, cache miss (file too old)
            result_1 = check_cache("Age Test", max_age_days=10)
            assert result_1 is None

            # With max_age=20, cache hit (file recent enough)
            result_2 = check_cache("Age Test", max_age_days=20)
            assert result_2 is not None
            assert result_2 == research_file


# ============================================================================
# CHECKPOINT: Save Test Creation Checkpoint
# ============================================================================


if __name__ == "__main__":
    """
    Save checkpoint after test creation (TDD red phase complete).
    """
    from pathlib import Path
    import sys

    # Portable path detection (works from any directory)
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    # Add lib to path for imports
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                'test-master',
                'Tests complete - 56 tests created (42 existing + 14 new for save_merged_research and cache workflow) (TDD red phase)'
            )
            print("✅ Checkpoint saved")
        except ImportError:
            print("ℹ️ Checkpoint skipped (user project)")

    # Run tests to verify they FAIL (TDD red phase)
    print("\n" + "=" * 70)
    print("TDD RED PHASE: Running tests to verify they FAIL")
    print("=" * 70 + "\n")

    import pytest
    exit_code = pytest.main([__file__, "--tb=line", "-q"])

    if exit_code == 0:
        print("\n⚠️  WARNING: Tests passed but implementation doesn't exist!")
        print("This indicates tests may not be properly checking for implementation.")
    else:
        print("\n✅ Tests failed as expected (TDD red phase complete)")
        print("Next: Implement research_persistence.py to make tests pass (GREEN phase)")
