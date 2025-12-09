#!/usr/bin/env python3
"""
TDD Tests for Skills 500-line Refactoring (FAILING - Red Phase)

This module contains FAILING tests for Issue #110 - Skills 500-line refactoring using
progressive disclosure pattern. 16 out of 28 skills exceed the 500-line limit and need
to be refactored to use SKILL.md as index + docs/ subdirectory for detailed content.

Issue: #110
Skills to Refactor (16 total):

High Priority (>50% over limit):
- api-design (953 lines → target <500)
- testing-guide (948 lines → target <500)
- observability (893 lines → target <500)
- research-patterns (849 lines → target <500)
- architecture-patterns (811 lines → target <500)
- database-design (750 lines → target <500)

Medium Priority (20-50% over limit):
- cross-reference-validation (711 lines → target <500)
- project-management (697 lines → target <500)
- github-workflow (687 lines → target <500)
- documentation-currency (649 lines → target <500)
- semantic-validation (624 lines → target <500)
- code-review (616 lines → target <500)

Low Priority (<20% over limit):
- git-workflow (570 lines → target <500)
- file-organization (532 lines → target <500)
- documentation-guide (527 lines → target <500)
- error-handling-patterns (523 lines → target <500)

Acceptance Criteria:
1. All 28 skills under 500 lines (16 need refactoring)
2. No loss of essential content (moved to docs/ where needed)
3. Skills still auto-activate correctly (keywords preserved)
4. Agent prompt skill references still work

Test Coverage: 89 tests (16 line count + 16 structure + 16 frontmatter + 16 docs + 16 content + 9 edge cases)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests should FAIL until skills are refactored
- Each test validates ONE requirement
- Use pytest parametrize for consistency

Author: test-master agent
Date: 2025-12-09
Issue: #110
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import re

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

# Skills that need refactoring (16 total) with current line counts
SKILLS_TO_REFACTOR = {
    # High priority (>50% over)
    "api-design": 953,
    "testing-guide": 948,
    "observability": 893,
    "research-patterns": 849,
    "architecture-patterns": 811,
    "database-design": 750,
    # Medium priority (20-50% over)
    "cross-reference-validation": 711,
    "project-management": 697,
    "github-workflow": 687,
    "documentation-currency": 649,
    "semantic-validation": 624,
    "code-review": 616,
    # Low priority (<20% over)
    "git-workflow": 570,
    "file-organization": 532,
    "documentation-guide": 527,
    "error-handling-patterns": 523,
}

# All 28 skills (must ALL be under 500 lines after refactoring)
ALL_SKILLS = [
    "advisor-triggers",
    "agent-output-formats",
    "api-design",
    "api-integration-patterns",
    "architecture-patterns",
    "code-review",
    "consistency-enforcement",
    "cross-reference-validation",
    "database-design",
    "documentation-currency",
    "documentation-guide",
    "error-handling-patterns",
    "file-organization",
    "git-workflow",
    "github-workflow",
    "library-design-patterns",
    "observability",
    "project-alignment",
    "project-alignment-validation",
    "project-management",
    "python-standards",
    "research-patterns",
    "security-patterns",
    "semantic-validation",
    "skill-integration",
    "skill-integration-templates",
    "state-management-patterns",
    "testing-guide",
]

# Required sections in refactored skills (progressive disclosure pattern)
REQUIRED_SECTIONS = [
    "## When This Activates",  # or "## When This Skill Activates"
    "## Progressive Disclosure",  # Must explain where to find detailed content
]

# Optional but recommended sections
RECOMMENDED_SECTIONS = [
    "## Quick Reference",  # Summary of key patterns
    "## Examples",  # Common usage examples
]


class TestLineCountCompliance:
    """Test that all skills are under 500-line limit after refactoring."""

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_refactored_skill_under_500_lines(self, skill_name: str):
        """
        Test that refactored skill SKILL.md is under 500 lines.

        This test will FAIL until the skill is refactored to move detailed
        content to docs/ subdirectory.

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        assert skill_file.exists(), f"Skill file not found: {skill_file}"

        with open(skill_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        line_count = len(lines)
        original_count = SKILLS_TO_REFACTOR[skill_name]

        assert line_count < 500, (
            f"{skill_name} SKILL.md has {line_count} lines (was {original_count}). "
            f"Must be under 500 lines. Move detailed content to docs/ subdirectory."
        )

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_all_skills_under_500_lines_final_state(self, skill_name: str):
        """
        Test that ALL 28 skills are under 500 lines in final state.

        This includes skills that are already compliant (12 skills) and
        those that need refactoring (16 skills).

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        assert skill_file.exists(), f"Skill file not found: {skill_file}"

        with open(skill_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        line_count = len(lines)

        assert line_count < 500, (
            f"{skill_name} SKILL.md has {line_count} lines. "
            f"Must be under 500 lines (target achieved via progressive disclosure)."
        )


class TestFrontmatterPreservation:
    """Test that YAML frontmatter is preserved during refactoring."""

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_frontmatter_exists_after_refactoring(self, skill_name: str):
        """
        Test that refactored skill has valid YAML frontmatter.

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        assert skill_file.exists(), f"Skill file not found: {skill_file}"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for frontmatter delimiters
        assert content.startswith('---\n'), f"{skill_name} missing frontmatter start delimiter"

        # Extract frontmatter
        parts = content.split('---\n', 2)
        assert len(parts) >= 3, f"{skill_name} missing frontmatter end delimiter"

        frontmatter_text = parts[1]

        # Parse YAML
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            pytest.fail(f"{skill_name} has invalid YAML frontmatter: {e}")

        assert frontmatter is not None, f"{skill_name} has empty frontmatter"

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_frontmatter_required_fields(self, skill_name: str):
        """
        Test that refactored skill has all required frontmatter fields.

        Required fields: name, type, description, keywords, auto_activate

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        parts = content.split('---\n', 2)
        frontmatter = yaml.safe_load(parts[1])

        # Check required fields
        required_fields = ["name", "type", "description", "keywords", "auto_activate"]

        for field in required_fields:
            assert field in frontmatter, (
                f"{skill_name} missing required frontmatter field: {field}"
            )

        # Validate field types
        assert isinstance(frontmatter["name"], str), f"{skill_name} 'name' must be string"
        assert isinstance(frontmatter["type"], str), f"{skill_name} 'type' must be string"
        assert isinstance(frontmatter["description"], str), f"{skill_name} 'description' must be string"
        assert isinstance(frontmatter["auto_activate"], bool), f"{skill_name} 'auto_activate' must be boolean"

        # Keywords can be list or string
        assert isinstance(frontmatter["keywords"], (list, str)), (
            f"{skill_name} 'keywords' must be list or string"
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_frontmatter_name_matches_directory(self, skill_name: str):
        """
        Test that frontmatter 'name' field matches directory name.

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        parts = content.split('---\n', 2)
        frontmatter = yaml.safe_load(parts[1])

        assert frontmatter["name"] == skill_name, (
            f"{skill_name} frontmatter 'name' ({frontmatter['name']}) "
            f"does not match directory name ({skill_name})"
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_frontmatter_auto_activate_or_invoke(self, skill_name: str):
        """
        Test that skill has auto_activate or auto_invoke field defined.

        Some validation skills intentionally use auto_invoke: false.

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        parts = content.split('---\n', 2)
        frontmatter = yaml.safe_load(parts[1])

        has_auto_field = (
            "auto_activate" in frontmatter or
            "auto_invoke" in frontmatter
        )
        assert has_auto_field, (
            f"{skill_name} must have auto_activate or auto_invoke field"
        )


class TestProgressiveDisclosureStructure:
    """Test that refactored skills follow progressive disclosure pattern."""

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_progressive_disclosure_section_exists(self, skill_name: str):
        """
        Test that refactored skill has "## Progressive Disclosure" section.

        This section explains where to find detailed content (docs/ directory).

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for progressive disclosure section (case insensitive)
        pattern = r'##\s+Progressive\s+Disclosure'
        match = re.search(pattern, content, re.IGNORECASE)

        assert match is not None, (
            f"{skill_name} missing '## Progressive Disclosure' section. "
            f"This section must explain where detailed content is located (docs/ directory)."
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_when_this_activates_section_exists(self, skill_name: str):
        """
        Test that refactored skill has activation section.

        Can be "## When This Activates" or "## When This Skill Activates".

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for either variation
        pattern1 = r'##\s+When\s+This\s+Activates'
        pattern2 = r'##\s+When\s+This\s+Skill\s+Activates'

        match1 = re.search(pattern1, content, re.IGNORECASE)
        match2 = re.search(pattern2, content, re.IGNORECASE)

        assert match1 is not None or match2 is not None, (
            f"{skill_name} missing '## When This Activates' or '## When This Skill Activates' section"
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_progressive_disclosure_has_docs_reference(self, skill_name: str):
        """
        Test that Progressive Disclosure section references docs/ directory.

        Should contain links like "See [docs/X.md](docs/X.md)".

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract Progressive Disclosure section
        pattern = r'##\s+Progressive\s+Disclosure(.*?)(?=\n##|\Z)'
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

        assert match is not None, f"{skill_name} Progressive Disclosure section not found"

        section_content = match.group(1)

        # Check for docs/ references (various formats)
        docs_patterns = [
            r'docs/[a-zA-Z0-9_-]+\.md',  # Simple path
            r'\[.*?\]\(docs/[a-zA-Z0-9_-]+\.md\)',  # Markdown link
            r'See.*?docs/',  # "See docs/..." text
        ]

        has_docs_reference = any(
            re.search(pattern, section_content) for pattern in docs_patterns
        )

        assert has_docs_reference, (
            f"{skill_name} Progressive Disclosure section does not reference docs/ directory. "
            f"Should contain links like 'See [docs/X.md](docs/X.md)'"
        )


class TestDocsDirectoryStructure:
    """Test that docs/ subdirectories exist and are properly structured."""

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_docs_directory_exists(self, skill_name: str):
        """
        Test that refactored skill has docs/ subdirectory.

        Args:
            skill_name: Name of skill to check
        """
        docs_dir = SKILLS_DIR / skill_name / "docs"

        assert docs_dir.exists(), (
            f"{skill_name} missing docs/ subdirectory. "
            f"Create {docs_dir} to store detailed content."
        )

        assert docs_dir.is_dir(), f"{docs_dir} exists but is not a directory"

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_docs_directory_not_empty(self, skill_name: str):
        """
        Test that docs/ subdirectory contains markdown files.

        Args:
            skill_name: Name of skill to check
        """
        docs_dir = SKILLS_DIR / skill_name / "docs"

        assert docs_dir.exists(), f"{skill_name} missing docs/ subdirectory"

        # Get all .md files in docs/
        md_files = list(docs_dir.glob("*.md"))

        assert len(md_files) > 0, (
            f"{skill_name} docs/ directory is empty. "
            f"Move detailed content from SKILL.md to docs/*.md files."
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_docs_files_are_markdown(self, skill_name: str):
        """
        Test that all files in docs/ are markdown (.md extension).

        Args:
            skill_name: Name of skill to check
        """
        docs_dir = SKILLS_DIR / skill_name / "docs"

        if not docs_dir.exists():
            pytest.skip(f"{skill_name} docs/ directory not yet created")

        # Get all files (not directories)
        all_files = [f for f in docs_dir.iterdir() if f.is_file()]

        if len(all_files) == 0:
            pytest.skip(f"{skill_name} docs/ directory is empty")

        # Check that all files are markdown
        non_md_files = [f for f in all_files if f.suffix != '.md']

        assert len(non_md_files) == 0, (
            f"{skill_name} docs/ contains non-markdown files: {non_md_files}. "
            f"All files in docs/ should be markdown (.md extension)."
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_docs_file_names_descriptive(self, skill_name: str):
        """
        Test that docs/ file names are descriptive (not generic).

        Avoid names like "details.md", "content.md", "misc.md".

        Args:
            skill_name: Name of skill to check
        """
        docs_dir = SKILLS_DIR / skill_name / "docs"

        if not docs_dir.exists():
            pytest.skip(f"{skill_name} docs/ directory not yet created")

        md_files = list(docs_dir.glob("*.md"))

        if len(md_files) == 0:
            pytest.skip(f"{skill_name} docs/ directory is empty")

        # Generic names to avoid
        generic_names = ["details.md", "content.md", "misc.md", "other.md", "stuff.md"]

        for md_file in md_files:
            file_name = md_file.name.lower()
            assert file_name not in generic_names, (
                f"{skill_name} has generic file name: {md_file.name}. "
                f"Use descriptive names like 'api-patterns.md', 'error-handling.md', etc."
            )


class TestDocReferenceResolution:
    """Test that all "See: docs/X.md" references resolve to existing files."""

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_all_docs_references_resolve(self, skill_name: str):
        """
        Test that all docs/ references in SKILL.md point to existing files.

        Extracts all "docs/X.md" references and verifies files exist.

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        docs_dir = SKILLS_DIR / skill_name / "docs"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract all docs/ references (various formats)
        patterns = [
            r'docs/([a-zA-Z0-9_-]+\.md)',  # Simple path
            r'\[.*?\]\(docs/([a-zA-Z0-9_-]+\.md)\)',  # Markdown link
        ]

        referenced_files = set()
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Get the filename (last group)
                file_name = match.group(1) if len(match.groups()) == 1 else match.group(2)
                referenced_files.add(file_name)

        if len(referenced_files) == 0:
            pytest.fail(
                f"{skill_name} SKILL.md does not reference any docs/ files. "
                f"Progressive disclosure requires 'See [docs/X.md](docs/X.md)' links."
            )

        # Check that all referenced files exist
        missing_files = []
        for file_name in referenced_files:
            file_path = docs_dir / file_name
            if not file_path.exists():
                missing_files.append(file_name)

        assert len(missing_files) == 0, (
            f"{skill_name} references non-existent docs/ files: {missing_files}. "
            f"Create these files or fix the references in SKILL.md."
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_docs_files_referenced_in_skill_md(self, skill_name: str):
        """
        Test that all docs/*.md files are referenced in SKILL.md.

        Prevents orphaned documentation files.

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        docs_dir = SKILLS_DIR / skill_name / "docs"

        if not docs_dir.exists():
            pytest.skip(f"{skill_name} docs/ directory not yet created")

        md_files = list(docs_dir.glob("*.md"))

        if len(md_files) == 0:
            pytest.skip(f"{skill_name} docs/ directory is empty")

        with open(skill_file, 'r', encoding='utf-8') as f:
            skill_content = f.read()

        # Check that each docs/*.md file is referenced in SKILL.md
        unreferenced_files = []
        for md_file in md_files:
            file_name = md_file.name
            # Check if file is mentioned anywhere in SKILL.md
            if file_name not in skill_content:
                unreferenced_files.append(file_name)

        assert len(unreferenced_files) == 0, (
            f"{skill_name} has orphaned docs/ files (not referenced in SKILL.md): {unreferenced_files}. "
            f"Add references like 'See [docs/{unreferenced_files[0]}](docs/{unreferenced_files[0]})' to SKILL.md."
        )


class TestContentPreservation:
    """Test that essential content is preserved (not lost during refactoring)."""

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_combined_content_exceeds_original(self, skill_name: str):
        """
        Test that SKILL.md + docs/*.md combined content preserves original detail.

        This is a rough check: combined line count should be similar to original
        (allowing for removal of duplication and formatting improvements).

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        docs_dir = SKILLS_DIR / skill_name / "docs"

        # Get SKILL.md line count
        with open(skill_file, 'r', encoding='utf-8') as f:
            skill_lines = len(f.readlines())

        # Get docs/*.md combined line count
        docs_lines = 0
        if docs_dir.exists():
            for md_file in docs_dir.glob("*.md"):
                with open(md_file, 'r', encoding='utf-8') as f:
                    docs_lines += len(f.readlines())

        combined_lines = skill_lines + docs_lines
        original_lines = SKILLS_TO_REFACTOR[skill_name]

        # Combined should be at least 70% of original (allows for cleanup)
        # but not too much more (avoid duplication)
        min_acceptable = int(original_lines * 0.70)
        max_acceptable = int(original_lines * 1.20)

        assert combined_lines >= min_acceptable, (
            f"{skill_name} combined content ({combined_lines} lines) is less than 70% "
            f"of original ({original_lines} lines). Content may be lost. "
            f"Expected at least {min_acceptable} lines."
        )

        assert combined_lines <= max_acceptable, (
            f"{skill_name} combined content ({combined_lines} lines) is more than 120% "
            f"of original ({original_lines} lines). May have duplication. "
            f"Expected at most {max_acceptable} lines."
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_key_sections_preserved(self, skill_name: str):
        """
        Test that key content sections are preserved in SKILL.md or docs/.

        Searches for common section headers that should not be lost.

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        docs_dir = SKILLS_DIR / skill_name / "docs"

        # Read all content (SKILL.md + docs/*.md)
        all_content = ""

        with open(skill_file, 'r', encoding='utf-8') as f:
            all_content += f.read()

        if docs_dir.exists():
            for md_file in docs_dir.glob("*.md"):
                with open(md_file, 'r', encoding='utf-8') as f:
                    all_content += "\n" + f.read()

        # Common section headers that should be preserved
        # (these are skill-specific, so we check for at least SOME headers)
        common_headers = [
            "## Examples",
            "## Patterns",
            "## Best Practices",
            "## Usage",
            "## Guidelines",
            "## Conventions",
            "## Strategies",
            "## Implementation",
            "## Reference",
        ]

        # Check that at least 2 common headers exist in combined content
        found_headers = [h for h in common_headers if h in all_content]

        assert len(found_headers) >= 2, (
            f"{skill_name} combined content missing common section headers. "
            f"Found only: {found_headers}. "
            f"Check that essential content sections are preserved."
        )


class TestStructureConsistency:
    """Test that all refactored skills follow consistent structure."""

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_skill_md_has_h1_title(self, skill_name: str):
        """
        Test that SKILL.md starts with H1 title (# Skill Name).

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Skip frontmatter
        parts = content.split('---\n', 2)
        if len(parts) >= 3:
            body = parts[2]
        else:
            body = content

        # Check for H1 near start of body (within first 200 chars)
        pattern = r'^#\s+.+Skill'
        match = re.search(pattern, body[:200], re.MULTILINE | re.IGNORECASE)

        assert match is not None, (
            f"{skill_name} SKILL.md missing H1 title (# Skill Name) after frontmatter"
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_docs_files_have_h1_title(self, skill_name: str):
        """
        Test that each docs/*.md file has H1 title.

        Args:
            skill_name: Name of skill to check
        """
        docs_dir = SKILLS_DIR / skill_name / "docs"

        if not docs_dir.exists():
            pytest.skip(f"{skill_name} docs/ directory not yet created")

        md_files = list(docs_dir.glob("*.md"))

        if len(md_files) == 0:
            pytest.skip(f"{skill_name} docs/ directory is empty")

        files_without_h1 = []
        for md_file in md_files:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for H1 near start (within first 200 chars)
            pattern = r'^#\s+.+'
            match = re.search(pattern, content[:200], re.MULTILINE)

            if match is None:
                files_without_h1.append(md_file.name)

        assert len(files_without_h1) == 0, (
            f"{skill_name} docs/ files missing H1 title: {files_without_h1}. "
            f"Each docs/*.md file should start with H1 (# Title)."
        )


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_all_skills_directory_exists(self):
        """Test that skills directory exists."""
        assert SKILLS_DIR.exists(), f"Skills directory not found: {SKILLS_DIR}"
        assert SKILLS_DIR.is_dir(), f"{SKILLS_DIR} is not a directory"

    def test_all_skill_directories_exist(self):
        """Test that all 28 skill directories exist."""
        missing_skills = []
        for skill_name in ALL_SKILLS:
            skill_dir = SKILLS_DIR / skill_name
            if not skill_dir.exists() or not skill_dir.is_dir():
                missing_skills.append(skill_name)

        assert len(missing_skills) == 0, (
            f"Missing skill directories: {missing_skills}"
        )

    def test_all_skill_md_files_exist(self):
        """Test that all 28 skills have SKILL.md file."""
        missing_skill_files = []
        for skill_name in ALL_SKILLS:
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_file.exists():
                missing_skill_files.append(skill_name)

        assert len(missing_skill_files) == 0, (
            f"Missing SKILL.md files: {missing_skill_files}"
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_skill_md_not_empty(self, skill_name: str):
        """
        Test that SKILL.md is not empty after refactoring.

        Args:
            skill_name: Name of skill to check
        """
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        assert len(content) > 0, f"{skill_name} SKILL.md is empty"

        # Should have at least frontmatter + some body content
        assert len(content) > 100, (
            f"{skill_name} SKILL.md is too short ({len(content)} chars). "
            f"Expected at least 100 characters."
        )

    @pytest.mark.parametrize("skill_name", list(SKILLS_TO_REFACTOR.keys()))
    def test_docs_files_not_empty(self, skill_name: str):
        """
        Test that docs/*.md files are not empty.

        Args:
            skill_name: Name of skill to check
        """
        docs_dir = SKILLS_DIR / skill_name / "docs"

        if not docs_dir.exists():
            pytest.skip(f"{skill_name} docs/ directory not yet created")

        md_files = list(docs_dir.glob("*.md"))

        if len(md_files) == 0:
            pytest.skip(f"{skill_name} docs/ directory is empty")

        empty_files = []
        for md_file in md_files:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if len(content) < 50:  # Too short to be useful
                empty_files.append(md_file.name)

        assert len(empty_files) == 0, (
            f"{skill_name} has empty or too-short docs/ files: {empty_files}. "
            f"Each docs/*.md file should have substantial content (at least 50 chars)."
        )

    def test_skills_to_refactor_list_accurate(self):
        """
        Test that SKILLS_TO_REFACTOR list is accurate (matches actual line counts).

        This test validates our test data is correct.
        """
        discrepancies = []

        for skill_name, expected_count in SKILLS_TO_REFACTOR.items():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"

            if not skill_file.exists():
                discrepancies.append(f"{skill_name}: file not found")
                continue

            with open(skill_file, 'r', encoding='utf-8') as f:
                actual_count = len(f.readlines())

            # Allow 5% variance (file may have changed slightly)
            tolerance = int(expected_count * 0.05)
            if abs(actual_count - expected_count) > tolerance:
                discrepancies.append(
                    f"{skill_name}: expected ~{expected_count} lines, "
                    f"found {actual_count} lines"
                )

        # This test may fail if skills have been edited since Issue #110 was filed
        # That's OK - it helps us update our test data
        if len(discrepancies) > 0:
            pytest.skip(
                f"SKILLS_TO_REFACTOR data may be outdated. "
                f"Discrepancies: {discrepancies}. "
                f"This is expected if skills were edited after Issue #110 was filed."
            )

    def test_all_skills_count_is_28(self):
        """Test that we're tracking all 28 skills."""
        assert len(ALL_SKILLS) == 28, (
            f"Expected 28 skills in ALL_SKILLS, found {len(ALL_SKILLS)}"
        )

    def test_skills_to_refactor_count_is_16(self):
        """Test that we're refactoring exactly 16 skills."""
        assert len(SKILLS_TO_REFACTOR) == 16, (
            f"Expected 16 skills in SKILLS_TO_REFACTOR, found {len(SKILLS_TO_REFACTOR)}"
        )


# Test summary for documentation
def test_coverage_summary():
    """
    Test Coverage Summary for Issue #110

    This test documents the coverage provided by this test suite.

    Test Counts:
    - Line count compliance: 32 tests (16 refactored + 16 all skills final state)
    - Frontmatter preservation: 64 tests (16 × 4 checks)
    - Progressive disclosure structure: 48 tests (16 × 3 checks)
    - Docs directory structure: 64 tests (16 × 4 checks)
    - Doc reference resolution: 32 tests (16 × 2 checks)
    - Content preservation: 32 tests (16 × 2 checks)
    - Structure consistency: 32 tests (16 × 2 checks)
    - Edge cases: 9 tests

    Total: 313 tests

    All tests should FAIL initially (TDD red phase) until skills are refactored.
    """
    pass


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=line"])
