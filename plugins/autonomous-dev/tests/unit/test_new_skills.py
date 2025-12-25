"""
Tests for new skills: database-design, api-design, observability.

Validates skill structure, frontmatter, keywords, and content quality.
"""

from pathlib import Path

import pytest


class TestNewSkillsStructure:
    """Validate new skills are structured correctly."""

    @pytest.fixture
    def skills_dir(self):
        return Path(__file__).parent.parent.parent / "skills"

    def test_database_design_skill_exists(self, skills_dir):
        """Test database-design skill file exists."""
        skill_path = skills_dir / "database-design" / "SKILL.md"
        assert skill_path.exists(), "database-design/SKILL.md not found"

    def test_api_design_skill_exists(self, skills_dir):
        """Test api-design skill file exists."""
        skill_path = skills_dir / "api-design" / "SKILL.md"
        assert skill_path.exists(), "api-design/SKILL.md not found"

    def test_observability_skill_exists(self, skills_dir):
        """Test observability skill file exists."""
        skill_path = skills_dir / "observability" / "SKILL.md"
        assert skill_path.exists(), "observability/SKILL.md not found"


class TestDatabaseDesignSkill:
    """Validate database-design skill."""

    @pytest.fixture
    def skill_content(self):
        skill_path = Path(__file__).parent.parent.parent / "skills" / "database-design" / "SKILL.md"
        return skill_path.read_text()

    def test_has_frontmatter(self, skill_content):
        """Test database-design has YAML frontmatter."""
        assert skill_content.startswith("---"), "Missing frontmatter start"
        assert "name: database-design" in skill_content, "Missing name field"
        assert "type: knowledge" in skill_content, "Missing type field"
        assert "description:" in skill_content, "Missing description field"
        assert "keywords:" in skill_content, "Missing keywords field"
        assert "auto_activate: true" in skill_content, "Missing auto_activate field"

    def test_has_required_keywords(self, skill_content):
        """Test database-design has relevant keywords."""
        required_keywords = [
            "database",
            "schema",
            "migration",
            "query",
            "sql",
            "orm",
            "postgres",
            "mysql",
            "index",
        ]

        for keyword in required_keywords:
            assert keyword in skill_content.lower(), f"Missing keyword: {keyword}"

    def test_covers_schema_design(self, skill_content):
        """Test database-design covers schema design patterns."""
        schema_topics = [
            "normalization",
            "denormalization",
            "primary key",
            "foreign key",
            "data types",
        ]

        for topic in schema_topics:
            assert topic.lower() in skill_content.lower(), f"Missing schema topic: {topic}"

    def test_covers_indexing(self, skill_content):
        """Test database-design covers indexing strategies."""
        indexing_topics = ["index", "b-tree", "composite index", "performance"]

        for topic in indexing_topics:
            assert topic.lower() in skill_content.lower(), f"Missing indexing topic: {topic}"

    def test_covers_migrations(self, skill_content):
        """Test database-design covers migrations."""
        migration_topics = ["migration", "alembic", "rollback"]

        for topic in migration_topics:
            assert topic.lower() in skill_content.lower(), f"Missing migration topic: {topic}"

    def test_covers_orms(self, skill_content):
        """Test database-design covers ORM patterns."""
        orm_topics = ["sqlalchemy", "django orm", "relationship", "query"]

        for topic in orm_topics:
            assert topic.lower() in skill_content.lower(), f"Missing ORM topic: {topic}"

    def test_covers_query_optimization(self, skill_content):
        """Test database-design covers query optimization."""
        optimization_topics = ["n+1", "explain analyze", "eager loading", "query optimization"]

        for topic in optimization_topics:
            assert topic.lower() in skill_content.lower(), f"Missing optimization topic: {topic}"

    def test_has_code_examples(self, skill_content):
        """Test database-design includes code examples."""
        # Should have SQL examples
        assert "CREATE TABLE" in skill_content or "create table" in skill_content.lower()
        assert "SELECT" in skill_content or "select" in skill_content.lower()

        # Should have Python examples
        assert "```python" in skill_content, "Missing Python code examples"

    def test_has_best_practices_section(self, skill_content):
        """Test database-design has best practices guidance."""
        assert "best practice" in skill_content.lower() or "✅" in skill_content


class TestAPIDesignSkill:
    """Validate api-design skill."""

    @pytest.fixture
    def skill_content(self):
        skill_path = Path(__file__).parent.parent.parent / "skills" / "api-design" / "SKILL.md"
        return skill_path.read_text()

    def test_has_frontmatter(self, skill_content):
        """Test api-design has YAML frontmatter."""
        assert skill_content.startswith("---"), "Missing frontmatter start"
        assert "name: api-design" in skill_content, "Missing name field"
        assert "type: knowledge" in skill_content, "Missing type field"
        assert "description:" in skill_content, "Missing description field"
        assert "keywords:" in skill_content, "Missing keywords field"
        assert "auto_activate: true" in skill_content, "Missing auto_activate field"

    def test_has_required_keywords(self, skill_content):
        """Test api-design has relevant keywords."""
        required_keywords = [
            "api",
            "rest",
            "endpoint",
            "http",
            "json",
            "openapi",
            "swagger",
        ]

        for keyword in required_keywords:
            assert keyword in skill_content.lower(), f"Missing keyword: {keyword}"

    def test_covers_rest_principles(self, skill_content):
        """Test api-design covers REST principles."""
        rest_topics = [
            "get",
            "post",
            "put",
            "delete",
            "resource",
            "http method",
        ]

        for topic in rest_topics:
            assert topic.lower() in skill_content.lower(), f"Missing REST topic: {topic}"

    def test_covers_http_status_codes(self, skill_content):
        """Test api-design covers HTTP status codes."""
        status_codes = ["200", "201", "204", "400", "401", "404", "500"]

        for code in status_codes:
            assert code in skill_content, f"Missing status code: {code}"

    def test_covers_error_handling(self, skill_content):
        """Test api-design covers error handling."""
        error_topics = ["error", "rfc 7807", "error response", "validation"]

        for topic in error_topics:
            assert topic.lower() in skill_content.lower(), f"Missing error topic: {topic}"

    def test_covers_pagination(self, skill_content):
        """Test api-design covers pagination patterns."""
        pagination_topics = ["pagination", "offset", "cursor", "limit", "page"]

        for topic in pagination_topics:
            assert topic.lower() in skill_content.lower(), f"Missing pagination topic: {topic}"

    def test_covers_versioning(self, skill_content):
        """Test api-design covers API versioning."""
        versioning_topics = ["versioning", "/v1", "/v2", "breaking change"]

        for topic in versioning_topics:
            assert topic.lower() in skill_content.lower(), f"Missing versioning topic: {topic}"

    def test_covers_authentication(self, skill_content):
        """Test api-design covers authentication methods."""
        auth_topics = ["authentication", "api key", "jwt", "bearer", "authorization"]

        for topic in auth_topics:
            assert topic.lower() in skill_content.lower(), f"Missing auth topic: {topic}"

    def test_covers_rate_limiting(self, skill_content):
        """Test api-design covers rate limiting."""
        rate_limit_topics = ["rate limit", "x-ratelimit", "429"]

        for topic in rate_limit_topics:
            assert topic.lower() in skill_content.lower(), f"Missing rate limit topic: {topic}"

    def test_has_code_examples(self, skill_content):
        """Test api-design includes code examples."""
        # Should have HTTP examples
        assert "GET" in skill_content and "POST" in skill_content

        # Should have Python examples
        assert "```python" in skill_content, "Missing Python code examples"

        # Should have JSON examples
        assert "```json" in skill_content or "```bash" in skill_content


class TestObservabilitySkill:
    """Validate observability skill."""

    @pytest.fixture
    def skill_content(self):
        skill_path = Path(__file__).parent.parent.parent / "skills" / "observability" / "SKILL.md"
        return skill_path.read_text()

    def test_has_frontmatter(self, skill_content):
        """Test observability has YAML frontmatter."""
        assert skill_content.startswith("---"), "Missing frontmatter start"
        assert "name: observability" in skill_content, "Missing name field"
        assert "type: knowledge" in skill_content, "Missing type field"
        assert "description:" in skill_content, "Missing description field"
        assert "keywords:" in skill_content, "Missing keywords field"
        assert "auto_activate: true" in skill_content, "Missing auto_activate field"

    def test_has_required_keywords(self, skill_content):
        """Test observability has relevant keywords."""
        required_keywords = [
            "logging",
            "debug",
            "profiling",
            "performance",
            "trace",
            "pdb",
        ]

        for keyword in required_keywords:
            assert keyword in skill_content.lower(), f"Missing keyword: {keyword}"

    def test_covers_logging(self, skill_content):
        """Test observability covers logging patterns."""
        logging_topics = [
            "logging",
            "logger",
            "log level",
            "debug",
            "info",
            "warning",
            "error",
            "critical",
        ]

        for topic in logging_topics:
            assert topic.lower() in skill_content.lower(), f"Missing logging topic: {topic}"

    def test_covers_structured_logging(self, skill_content):
        """Test observability covers structured logging."""
        structured_topics = ["json", "structured", "extra"]

        for topic in structured_topics:
            assert topic.lower() in skill_content.lower(), f"Missing structured logging topic: {topic}"

    def test_covers_debugging(self, skill_content):
        """Test observability covers debugging techniques."""
        debug_topics = [
            "pdb",
            "breakpoint",
            "debugger",
            "ipdb",
            "stack trace",
        ]

        for topic in debug_topics:
            assert topic.lower() in skill_content.lower(), f"Missing debug topic: {topic}"

    def test_covers_profiling(self, skill_content):
        """Test observability covers profiling tools."""
        profiling_topics = [
            "cProfile",
            "profiling",
            "memory_profiler",
            "line_profiler",
            "py-spy",
        ]

        for topic in profiling_topics:
            assert topic.lower() in skill_content.lower(), f"Missing profiling topic: {topic}"

    def test_covers_performance_monitoring(self, skill_content):
        """Test observability covers performance monitoring."""
        performance_topics = ["timer", "performance", "timing", "benchmark"]

        for topic in performance_topics:
            assert topic.lower() in skill_content.lower(), f"Missing performance topic: {topic}"

    def test_has_code_examples(self, skill_content):
        """Test observability includes code examples."""
        # Should have Python examples
        assert "```python" in skill_content, "Missing Python code examples"

        # Should show logging examples
        assert "logger." in skill_content, "Missing logger usage examples"

        # Should show profiling examples
        assert "profiler" in skill_content.lower(), "Missing profiler examples"

    def test_security_no_sensitive_logging(self, skill_content):
        """Test observability warns against logging sensitive data."""
        security_warnings = [
            "password",
            "api key",
            "secret",
            "sensitive",
        ]

        # Should mention NOT logging these things
        warning_count = sum(1 for warning in security_warnings if warning in skill_content.lower())
        assert warning_count >= 2, "Should warn about logging sensitive data"


class TestSkillConsistency:
    """Test that new skills follow plugin conventions."""

    @pytest.fixture
    def skills_dir(self):
        return Path(__file__).parent.parent.parent / "skills"

    def test_all_skills_in_subdirectories(self, skills_dir):
        """Test all skills are in their own subdirectories."""
        new_skills = ["database-design", "api-design", "observability"]

        for skill in new_skills:
            skill_dir = skills_dir / skill
            assert skill_dir.exists(), f"Skill directory not found: {skill}"
            assert skill_dir.is_dir(), f"Skill path is not a directory: {skill}"

    def test_all_skills_have_skill_md(self, skills_dir):
        """Test all skills have SKILL.md file."""
        new_skills = ["database-design", "api-design", "observability"]

        for skill in new_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            assert skill_file.exists(), f"SKILL.md not found for {skill}"

    def test_skills_have_version_footer(self, skills_dir):
        """Test all skills document their version."""
        new_skills = ["database-design", "api-design", "observability"]

        for skill in new_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            # Should have version info
            assert "version" in content.lower(), f"{skill} missing version information"

    def test_skills_reference_related_skills(self, skills_dir):
        """Test skills reference related skills (See Also)."""
        new_skills = ["database-design", "api-design", "observability"]

        for skill in new_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            # Should reference other skills
            assert "see also" in content.lower(), f"{skill} should reference related skills"

    def test_skills_have_key_takeaways(self, skills_dir):
        """Test skills have key takeaways section."""
        new_skills = ["database-design", "api-design", "observability"]

        for skill in new_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            # Should have takeaways
            assert "key takeaway" in content.lower() or "takeaway" in content.lower(), \
                f"{skill} should have key takeaways section"


class TestSkillQuality:
    """Test quality and completeness of new skills."""

    @pytest.fixture
    def skills_dir(self):
        return Path(__file__).parent.parent.parent / "skills"

    def test_skills_have_sufficient_content(self, skills_dir):
        """Test skills have substantial content (not stubs)."""
        new_skills = ["database-design", "api-design", "observability"]

        for skill in new_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            # Should have substantial content (> 500 lines)
            line_count = len(content.splitlines())
            assert line_count > 500, f"{skill} content too short: {line_count} lines"

    def test_skills_have_good_bad_examples(self, skills_dir):
        """Test skills show good vs bad examples."""
        new_skills = ["database-design", "api-design", "observability"]

        for skill in new_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            # Should have good/bad indicators
            has_indicators = ("✅" in content and "❌" in content) or \
                           ("GOOD" in content.upper() and "BAD" in content.upper())

            assert has_indicators, f"{skill} should show good vs bad examples"

    def test_skills_have_tables(self, skills_dir):
        """Test skills use tables for comparisons."""
        new_skills = ["database-design", "api-design", "observability"]

        for skill in new_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            # Should have markdown tables
            assert "|" in content and "---" in content, f"{skill} should use tables for comparisons"

    def test_skills_are_developer_focused(self, skills_dir):
        """Test skills focus on development, not operations."""
        new_skills = ["database-design", "api-design", "observability"]

        # These are ops-focused terms that should be minimal or absent
        ops_terms = ["kubernetes", "docker", "terraform", "jenkins", "incident response"]

        for skill in new_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text().lower()

            ops_count = sum(1 for term in ops_terms if term in content)

            # Should have minimal ops terminology (< 2 mentions)
            assert ops_count < 2, f"{skill} appears too ops-focused (found {ops_count} ops terms)"
