"""
Unit tests for CLAUDE.md size reduction (Issue TBD)

Tests validate that CLAUDE.md has been condensed from 832 lines to under 300 lines
by moving detailed sections to separate documentation files while preserving
essential content and maintaining valid cross-references.

These tests follow TDD - they should FAIL until implementation is complete.

Run with: pytest tests/unit/test_claude_md_reduction.py --tb=line -q
"""

import re
from pathlib import Path
from typing import List, Set, Tuple

import pytest


class TestClaudeMdLineCount:
    """Test suite for CLAUDE.md line count constraints."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"
    MAX_LINES = 300
    MIN_LINES = 200  # Sanity check - shouldn't be too minimal

    def test_claude_md_exists(self):
        """
        GIVEN: Project root directory
        WHEN: Checking for CLAUDE.md file
        THEN: File exists at expected location
        """
        assert self.CLAUDE_MD.exists(), f"CLAUDE.md not found at {self.CLAUDE_MD}"

    def test_claude_md_line_count_under_maximum(self):
        """
        GIVEN: CLAUDE.md file
        WHEN: Counting total lines
        THEN: Line count is under 300 lines (reduced from 832)
        """
        content = self.CLAUDE_MD.read_text()
        lines = content.splitlines()
        line_count = len(lines)

        assert (
            line_count <= self.MAX_LINES
        ), f"CLAUDE.md has {line_count} lines, must be <= {self.MAX_LINES}"

    def test_claude_md_line_count_within_target_range(self):
        """
        GIVEN: CLAUDE.md file
        WHEN: Counting total lines
        THEN: Line count is between 200-300 lines (target: 250-300)
        """
        content = self.CLAUDE_MD.read_text()
        lines = content.splitlines()
        line_count = len(lines)

        assert (
            self.MIN_LINES <= line_count <= self.MAX_LINES
        ), f"CLAUDE.md has {line_count} lines, should be between {self.MIN_LINES}-{self.MAX_LINES}"

    def test_claude_md_reduction_percentage(self):
        """
        GIVEN: CLAUDE.md original size of 832 lines
        WHEN: Measuring reduction after refactor
        THEN: At least 64% reduction achieved (832 -> 300 = 64% reduction)
        """
        content = self.CLAUDE_MD.read_text()
        lines = content.splitlines()
        current_count = len(lines)
        original_count = 832

        reduction_percentage = ((original_count - current_count) / original_count) * 100

        assert (
            reduction_percentage >= 64.0
        ), f"Reduction is {reduction_percentage:.1f}%, should be >= 64%"


class TestClaudeMdEssentialSections:
    """Test suite for essential CLAUDE.md sections that must be preserved."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"

    REQUIRED_SECTIONS = [
        "Installation (Bootstrap-First)",
        "Project Overview",
        "Commands",
        "Quick Reference",
        "Philosophy",
        "Component Versions",
    ]

    REQUIRED_SUBSECTIONS = [
        # Installation section
        "What install.sh does",
        # Commands section
        "/advise",
        "/auto-implement",
        "/batch-implement",
        "/create-issue",
        "/align",
        "/setup",
        "/sync",
        "/health-check",
        "/worktree",
        # Quick Reference
        "Updating",
        "Daily Workflow",
        # Philosophy
        "Automation > Reminders > Hope",
        "Research First, Test Coverage Required",
        "Context is Precious",
    ]

    def test_required_sections_preserved(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for required top-level sections
        THEN: All essential sections are preserved
        """
        content = self.CLAUDE_MD.read_text()

        for section in self.REQUIRED_SECTIONS:
            # Match section header with optional markdown prefix
            pattern = rf"^##\s+{re.escape(section)}"
            assert re.search(
                pattern, content, re.MULTILINE
            ), f"Required section '{section}' not found in CLAUDE.md"

    def test_required_subsections_preserved(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for required subsections and key content
        THEN: All essential subsections are preserved
        """
        content = self.CLAUDE_MD.read_text()

        for subsection in self.REQUIRED_SUBSECTIONS:
            # Check if subsection exists as header or bold text
            header_pattern = rf"^###?\s+.*{re.escape(subsection)}"
            bold_pattern = rf"\*\*{re.escape(subsection)}\*\*"
            code_pattern = rf"`{re.escape(subsection)}`"

            found = (
                re.search(header_pattern, content, re.MULTILINE)
                or re.search(bold_pattern, content)
                or re.search(code_pattern, content)
            )

            assert (
                found
            ), f"Required subsection/content '{subsection}' not found in CLAUDE.md"

    def test_installation_bootstrap_content_preserved(self):
        """
        GIVEN: CLAUDE.md installation section
        WHEN: Checking for bootstrap installation command
        THEN: curl installation command is preserved
        """
        content = self.CLAUDE_MD.read_text()

        # Check for the bootstrap installation command
        assert (
            "bash <(curl -sSL" in content
        ), "Bootstrap installation command not found"
        assert (
            "install.sh" in content
        ), "install.sh reference not found in installation section"

    def test_command_descriptions_preserved(self):
        """
        GIVEN: CLAUDE.md commands section
        WHEN: Checking for command descriptions
        THEN: Each command has a brief description
        """
        content = self.CLAUDE_MD.read_text()

        # Each command should have a description after it
        commands = [
            "/advise",
            "/auto-implement",
            "/batch-implement",
            "/create-issue",
            "/align",
            "/setup",
            "/sync",
            "/health-check",
            "/worktree",
        ]

        for command in commands:
            # Look for command followed by description (- or :)
            pattern = rf"{re.escape(command)}\s*[-:]"
            assert re.search(
                pattern, content
            ), f"Command {command} missing description"


class TestNewDocumentationFiles:
    """Test suite for new documentation files created during refactoring."""

    DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

    NEW_FILES = [
        "WORKFLOW-DISCIPLINE.md",
        "CONTEXT-MANAGEMENT.md",
        "ARCHITECTURE-OVERVIEW.md",
    ]

    TROUBLESHOOTING_FILE = (
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "docs"
        / "TROUBLESHOOTING.md"
    )

    def test_new_documentation_files_created(self):
        """
        GIVEN: docs/ directory
        WHEN: Checking for new documentation files
        THEN: All three new files exist
        """
        for filename in self.NEW_FILES:
            filepath = self.DOCS_DIR / filename
            assert filepath.exists(), f"New documentation file {filename} not created"

    def test_new_files_have_content(self):
        """
        GIVEN: New documentation files
        WHEN: Checking file size
        THEN: Each file has substantial content (>500 chars)
        """
        for filename in self.NEW_FILES:
            filepath = self.DOCS_DIR / filename
            if filepath.exists():
                content = filepath.read_text()
                assert (
                    len(content) > 500
                ), f"{filename} has insufficient content ({len(content)} chars)"

    def test_troubleshooting_file_expanded(self):
        """
        GIVEN: TROUBLESHOOTING.md in plugins/autonomous-dev/docs/
        WHEN: Checking file size
        THEN: File has been expanded with additional content
        """
        assert (
            self.TROUBLESHOOTING_FILE.exists()
        ), f"TROUBLESHOOTING.md not found at {self.TROUBLESHOOTING_FILE}"

        content = self.TROUBLESHOOTING_FILE.read_text()
        assert (
            len(content) > 1000
        ), f"TROUBLESHOOTING.md should be expanded (current: {len(content)} chars)"

    def test_workflow_discipline_content(self):
        """
        GIVEN: WORKFLOW-DISCIPLINE.md file
        WHEN: Checking content sections
        THEN: Contains workflow discipline topics from CLAUDE.md
        """
        filepath = self.DOCS_DIR / "WORKFLOW-DISCIPLINE.md"
        if not filepath.exists():
            pytest.skip("WORKFLOW-DISCIPLINE.md not yet created")

        content = filepath.read_text()

        # Should contain topics from CLAUDE.md workflow section
        expected_topics = [
            "auto-implement",
            "pipeline",
            "quality",
            "enforcement",
        ]

        for topic in expected_topics:
            assert (
                topic.lower() in content.lower()
            ), f"WORKFLOW-DISCIPLINE.md missing topic: {topic}"

    def test_context_management_content(self):
        """
        GIVEN: CONTEXT-MANAGEMENT.md file
        WHEN: Checking content sections
        THEN: Contains context management topics from CLAUDE.md
        """
        filepath = self.DOCS_DIR / "CONTEXT-MANAGEMENT.md"
        if not filepath.exists():
            pytest.skip("CONTEXT-MANAGEMENT.md not yet created")

        content = filepath.read_text()

        # Should contain context management topics
        expected_topics = [
            "/clear",
            "context",
            "session",
            "token",
        ]

        for topic in expected_topics:
            assert (
                topic.lower() in content.lower()
            ), f"CONTEXT-MANAGEMENT.md missing topic: {topic}"

    def test_architecture_overview_content(self):
        """
        GIVEN: ARCHITECTURE-OVERVIEW.md file
        WHEN: Checking content sections
        THEN: Contains architecture topics from CLAUDE.md
        """
        filepath = self.DOCS_DIR / "ARCHITECTURE-OVERVIEW.md"
        if not filepath.exists():
            pytest.skip("ARCHITECTURE-OVERVIEW.md not yet created")

        content = filepath.read_text()

        # Should contain architecture topics
        expected_topics = [
            "agents",
            "skills",
            "hooks",
            "libraries",
        ]

        for topic in expected_topics:
            assert (
                topic.lower() in content.lower()
            ), f"ARCHITECTURE-OVERVIEW.md missing topic: {topic}"


class TestMarkdownLinkValidation:
    """Test suite for markdown link validation in CLAUDE.md."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"
    PROJECT_ROOT = Path(__file__).parent.parent.parent

    def _extract_markdown_links(self, content: str) -> List[Tuple[str, str]]:
        """Extract all markdown links [text](path) from content."""
        # Pattern: [text](path)
        pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        return re.findall(pattern, content)

    def _resolve_link_path(self, link_path: str) -> Path:
        """Resolve a markdown link path to absolute path."""
        # Remove anchor fragments (#section)
        link_path = link_path.split("#")[0]

        # Skip external URLs
        if link_path.startswith(("http://", "https://", "mailto:")):
            return None

        # Resolve relative to project root
        if link_path.startswith("/"):
            return self.PROJECT_ROOT / link_path.lstrip("/")
        else:
            return self.PROJECT_ROOT / link_path

    def test_all_markdown_links_valid(self):
        """
        GIVEN: CLAUDE.md with markdown links
        WHEN: Checking all [text](path) links
        THEN: All file paths point to existing files
        """
        content = self.CLAUDE_MD.read_text()
        links = self._extract_markdown_links(content)

        broken_links = []
        for text, path in links:
            resolved_path = self._resolve_link_path(path)

            # Skip external URLs
            if resolved_path is None:
                continue

            if not resolved_path.exists():
                broken_links.append((text, path, resolved_path))

        assert (
            not broken_links
        ), f"Broken links found:\n" + "\n".join(
            f"  [{text}]({path}) -> {resolved}" for text, path, resolved in broken_links
        )

    def test_new_docs_referenced_in_claude_md(self):
        """
        GIVEN: New documentation files created
        WHEN: Checking CLAUDE.md for cross-references
        THEN: New docs are referenced using standard pattern
        """
        content = self.CLAUDE_MD.read_text()

        new_files = [
            "WORKFLOW-DISCIPLINE.md",
            "CONTEXT-MANAGEMENT.md",
            "ARCHITECTURE-OVERVIEW.md",
        ]

        for filename in new_files:
            # Check for reference using standard pattern
            # Pattern: See [docs/FILE.md](docs/FILE.md) for complete details
            pattern = rf"\[docs/{filename}\]\(docs/{filename}\)"
            assert re.search(
                pattern, content
            ), f"Missing cross-reference to docs/{filename} in CLAUDE.md"

    def test_cross_reference_pattern_consistency(self):
        """
        GIVEN: CLAUDE.md with cross-references to docs
        WHEN: Checking reference patterns
        THEN: All use consistent format: See [docs/FILE.md](docs/FILE.md)
        """
        content = self.CLAUDE_MD.read_text()

        # Find all references to docs/ files
        doc_refs = re.findall(r"\[docs/([^\]]+\.md)\]\(docs/([^)]+\.md)\)", content)

        for link_text, link_path in doc_refs:
            # Link text and path should match
            assert (
                link_text == link_path
            ), f"Inconsistent link: [{link_text}]({link_path})"

    def test_no_absolute_paths_in_links(self):
        """
        GIVEN: CLAUDE.md markdown links
        WHEN: Checking link paths
        THEN: No absolute file system paths are used (only relative or URLs)
        """
        content = self.CLAUDE_MD.read_text()
        links = self._extract_markdown_links(content)

        absolute_path_links = []
        for text, path in links:
            # Skip URLs
            if path.startswith(("http://", "https://", "mailto:")):
                continue

            # Check for absolute filesystem paths (starting with / or drive letter)
            if path.startswith("/") and not path.startswith("/Users"):
                # /docs is ok (relative to repo root)
                continue

            if re.match(r"^[A-Za-z]:\\", path) or path.startswith("/Users"):
                absolute_path_links.append((text, path))

        assert (
            not absolute_path_links
        ), f"Absolute paths found (should use relative):\n" + "\n".join(
            f"  [{text}]({path})" for text, path in absolute_path_links
        )


class TestContentMigrationCompleteness:
    """Test suite for ensuring content was properly migrated to new docs."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"
    DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

    def test_workflow_discipline_section_migrated(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for workflow discipline content
        THEN: Detailed content moved to WORKFLOW-DISCIPLINE.md with reference
        """
        claude_content = self.CLAUDE_MD.read_text()

        # Should have brief mention + reference, not full content
        assert "workflow" in claude_content.lower(), "No workflow mention in CLAUDE.md"

        # Should reference the new file
        assert (
            "WORKFLOW-DISCIPLINE.md" in claude_content
        ), "No reference to WORKFLOW-DISCIPLINE.md"

        # Should NOT have the full workflow discipline table (indicates migration)
        # The original has a large table comparing metrics
        full_table_pattern = r"\|\s+Metric\s+\|\s+Direct Implementation\s+\|\s+/auto-implement"
        if re.search(full_table_pattern, claude_content):
            pytest.fail(
                "Full workflow discipline table still in CLAUDE.md (should be migrated)"
            )

    def test_context_management_section_migrated(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for context management content
        THEN: Detailed content moved to CONTEXT-MANAGEMENT.md with reference
        """
        claude_content = self.CLAUDE_MD.read_text()

        # Should have brief mention + reference
        assert "context" in claude_content.lower(), "No context mention in CLAUDE.md"

        # Should reference the new file
        assert (
            "CONTEXT-MANAGEMENT.md" in claude_content
        ), "No reference to CONTEXT-MANAGEMENT.md"

    def test_architecture_section_migrated(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for architecture content
        THEN: Detailed content moved to ARCHITECTURE-OVERVIEW.md with reference
        """
        claude_content = self.CLAUDE_MD.read_text()

        # Should have brief mention + reference
        assert (
            "architecture" in claude_content.lower()
            or "agents" in claude_content.lower()
        ), "No architecture mention in CLAUDE.md"

        # Should reference the new file
        assert (
            "ARCHITECTURE-OVERVIEW.md" in claude_content
        ), "No reference to ARCHITECTURE-OVERVIEW.md"

    def test_migrated_sections_have_headers(self):
        """
        GIVEN: New documentation files
        WHEN: Checking file structure
        THEN: Each file has proper markdown headers and organization
        """
        files_to_check = [
            "WORKFLOW-DISCIPLINE.md",
            "CONTEXT-MANAGEMENT.md",
            "ARCHITECTURE-OVERVIEW.md",
        ]

        for filename in files_to_check:
            filepath = self.DOCS_DIR / filename
            if not filepath.exists():
                continue

            content = filepath.read_text()

            # Should have at least one h1 header
            assert re.search(
                r"^# ", content, re.MULTILINE
            ), f"{filename} missing h1 header"

            # Should have at least one h2 header
            assert re.search(
                r"^## ", content, re.MULTILINE
            ), f"{filename} missing h2 headers (needs organization)"


class TestDocumentationQuality:
    """Test suite for documentation quality standards."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"
    DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

    def test_no_orphaned_sections(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for section headers
        THEN: No orphaned headers without content
        """
        content = self.CLAUDE_MD.read_text()
        lines = content.splitlines()

        orphaned_headers = []
        for i, line in enumerate(lines):
            # Check if line is a header
            if re.match(r"^#{1,3}\s+", line):
                # Check if next non-empty line is also a header (orphaned)
                next_content = None
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip():
                        next_content = lines[j]
                        break

                if next_content and re.match(r"^#{1,3}\s+", next_content):
                    orphaned_headers.append(line)

        assert (
            not orphaned_headers
        ), f"Orphaned headers found:\n" + "\n".join(orphaned_headers)

    def test_consistent_cross_reference_phrasing(self):
        """
        GIVEN: CLAUDE.md with cross-references
        WHEN: Checking reference phrasing
        THEN: Uses consistent phrasing like "See [file](path) for complete details"
        """
        content = self.CLAUDE_MD.read_text()

        # Find all references to docs/ files
        doc_refs = re.findall(
            r"(.*\[docs/[^\]]+\.md\]\(docs/[^)]+\.md\).*)", content
        )

        inconsistent_refs = []
        for ref_line in doc_refs:
            # Check for common phrasings
            valid_patterns = [
                r"See\s+\[",  # See [file](path)
                r"see\s+\[",  # see [file](path)
                r"documented in\s+\[",  # documented in [file](path)
                r"Details:\s+\[",  # Details: [file](path)
            ]

            if not any(re.search(pattern, ref_line) for pattern in valid_patterns):
                inconsistent_refs.append(ref_line.strip())

        # This is a warning, not a failure (style preference)
        if inconsistent_refs:
            print(
                "\nNote: Some cross-references use non-standard phrasing:\n"
                + "\n".join(f"  {ref}" for ref in inconsistent_refs[:5])
            )

    def test_new_docs_have_metadata(self):
        """
        GIVEN: New documentation files
        WHEN: Checking file headers
        THEN: Each file has proper metadata (title, description, last updated)
        """
        files_to_check = [
            "WORKFLOW-DISCIPLINE.md",
            "CONTEXT-MANAGEMENT.md",
            "ARCHITECTURE-OVERVIEW.md",
        ]

        for filename in files_to_check:
            filepath = self.DOCS_DIR / filename
            if not filepath.exists():
                continue

            content = filepath.read_text()

            # Should have a title (h1 header)
            assert re.search(
                r"^# .+", content, re.MULTILINE
            ), f"{filename} missing title header"

            # Optional: Check for last updated date (good practice)
            # This is informational, not required
            if not re.search(r"last updated|updated:", content, re.IGNORECASE):
                print(f"\nNote: {filename} doesn't have 'Last Updated' metadata")


class TestBackwardCompatibility:
    """Test suite for ensuring backward compatibility after refactoring."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"

    def test_command_usage_examples_preserved(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for command usage examples
        THEN: Quick reference examples still present
        """
        content = self.CLAUDE_MD.read_text()

        # Should have code blocks with commands
        assert "```bash" in content, "No bash code blocks found"

        # Should have key commands in examples
        key_commands = ["/auto-implement", "/clear", "/sync"]
        for cmd in key_commands:
            assert (
                cmd in content
            ), f"Key command {cmd} not found in examples or references"

    def test_version_information_preserved(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for version information
        THEN: Component versions section preserved
        """
        content = self.CLAUDE_MD.read_text()

        # Should have component versions
        assert "Component Versions" in content, "Component Versions section missing"

        # Should mention version numbers
        assert re.search(
            r"v?\d+\.\d+\.\d+", content
        ), "No version numbers found in CLAUDE.md"

    def test_links_to_detailed_docs_preserved(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for links to existing detailed docs
        THEN: All existing doc references preserved (AGENTS.md, HOOKS.md, etc.)
        """
        content = self.CLAUDE_MD.read_text()

        # Existing documentation files that should still be referenced
        existing_docs = [
            "AGENTS.md",
            "HOOKS.md",
            "LIBRARIES.md",
            "BATCH-PROCESSING.md",
            "GIT-AUTOMATION.md",
            "PERFORMANCE.md",
        ]

        for doc in existing_docs:
            assert (
                doc in content
            ), f"Reference to existing documentation {doc} was removed"


class TestEdgeCases:
    """Test suite for edge cases and error conditions."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"
    DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

    def test_no_duplicate_content_between_files(self):
        """
        GIVEN: CLAUDE.md and new documentation files
        WHEN: Checking for content duplication
        THEN: No substantial duplicate paragraphs exist
        """
        claude_content = self.CLAUDE_MD.read_text()

        # Check each new doc file
        new_files = [
            "WORKFLOW-DISCIPLINE.md",
            "CONTEXT-MANAGEMENT.md",
            "ARCHITECTURE-OVERVIEW.md",
        ]

        for filename in new_files:
            filepath = self.DOCS_DIR / filename
            if not filepath.exists():
                continue

            doc_content = filepath.read_text()

            # Extract paragraphs (3+ sentences) from both
            claude_paragraphs = [
                p.strip()
                for p in re.split(r"\n\s*\n", claude_content)
                if len(p.strip()) > 200
            ]
            doc_paragraphs = [
                p.strip()
                for p in re.split(r"\n\s*\n", doc_content)
                if len(p.strip()) > 200
            ]

            # Check for exact duplicates
            duplicates = []
            for doc_para in doc_paragraphs:
                # Check if substantial portion appears in CLAUDE.md
                if any(doc_para[:100] in claude_para for claude_para in claude_paragraphs):
                    duplicates.append(doc_para[:100] + "...")

            # Allow some duplication (cross-references, examples), but not excessive
            assert (
                len(duplicates) <= 2
            ), f"Excessive content duplication found in {filename}"

    def test_no_broken_formatting_after_migration(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking markdown formatting
        THEN: No broken formatting (unclosed code blocks, malformed lists)
        """
        content = self.CLAUDE_MD.read_text()

        # Check for unclosed code blocks
        code_blocks = re.findall(r"```", content)
        assert (
            len(code_blocks) % 2 == 0
        ), f"Unclosed code blocks found ({len(code_blocks)} ``` markers)"

        # Check for malformed list items (lines starting with - not followed by space)
        malformed_lists = re.findall(r"^-[^\s]", content, re.MULTILINE)
        assert (
            not malformed_lists
        ), f"Malformed list items found: {malformed_lists[:3]}"

    def test_readability_preserved(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking content structure
        THEN: File remains readable with clear sections and navigation
        """
        content = self.CLAUDE_MD.read_text()

        # Should have clear top-level sections (##)
        top_level_sections = re.findall(r"^## (.+)$", content, re.MULTILINE)
        assert (
            len(top_level_sections) >= 8
        ), f"Too few top-level sections ({len(top_level_sections)}), may impact navigation"

        # Should have table of contents or clear structure
        # (Not required, but good practice for readability)
        has_toc = "## Table of Contents" in content or "## Contents" in content
        has_clear_headers = len(top_level_sections) >= 10

        assert (
            has_toc or has_clear_headers
        ), "CLAUDE.md may lack clear navigation structure"

    def test_no_file_size_bloat_in_new_docs(self):
        """
        GIVEN: New documentation files
        WHEN: Checking file sizes
        THEN: Each file is reasonably sized (not bloated)
        """
        new_files = [
            "WORKFLOW-DISCIPLINE.md",
            "CONTEXT-MANAGEMENT.md",
            "ARCHITECTURE-OVERVIEW.md",
        ]

        max_size = 50_000  # 50KB max per doc file

        for filename in new_files:
            filepath = self.DOCS_DIR / filename
            if not filepath.exists():
                continue

            file_size = filepath.stat().st_size
            assert (
                file_size <= max_size
            ), f"{filename} is too large ({file_size} bytes), should be <= {max_size}"


class TestRegressionPrevention:
    """Test suite for preventing regression after future changes."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"

    def test_line_count_does_not_creep_back(self):
        """
        GIVEN: CLAUDE.md at reduced size
        WHEN: Future changes are made
        THEN: Line count stays under 300 (with 10% buffer = 330 lines max)
        """
        content = self.CLAUDE_MD.read_text()
        lines = content.splitlines()
        line_count = len(lines)

        max_with_buffer = 330  # 10% buffer for minor additions

        assert (
            line_count <= max_with_buffer
        ), f"CLAUDE.md has grown to {line_count} lines (max: {max_with_buffer})"

    def test_no_detailed_sections_re_added(self):
        """
        GIVEN: CLAUDE.md after refactoring
        WHEN: Checking for detailed content patterns
        THEN: Detailed sections remain in separate docs (not re-added to CLAUDE.md)
        """
        content = self.CLAUDE_MD.read_text()

        # Patterns that indicate detailed content that should be in separate docs
        detailed_patterns = [
            r"(?:^|\n)#{2,3}\s+.{100,}",  # Very long section titles
            r"\|\s+\w+\s+\|\s+\w+\s+\|\s+\w+\s+\|\s+\w+\s+\|",  # Large tables (4+ columns)
        ]

        for pattern in detailed_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            # Some tables are OK (component versions), but not excessive
            assert (
                len(matches) <= 5
            ), f"Too many detailed content patterns found ({len(matches)}), consider moving to docs/"
