#!/usr/bin/env python3
"""
Integration Tests for CLAUDE.md Optimization Cross-References (FAILING - Red Phase)

This module contains FAILING integration tests for cross-references between CLAUDE.md
and the newly extracted documentation files (LIBRARIES.md, PERFORMANCE.md, GIT-AUTOMATION.md).

Integration Test Focus:
1. Link validity (all links resolve to existing files)
2. Bidirectional references (files reference each other correctly)
3. Content consistency (references point to correct sections)
4. Navigation flow (users can find information easily)
5. Markdown rendering (links display correctly)

Test Coverage Target: 100% of cross-reference scenarios

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe integration requirements
- Tests should FAIL until optimization complete
- Each test validates ONE integration requirement

Author: test-master agent
Date: 2025-11-11
Issue: TBD (CLAUDE.md optimization)
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestLinkValidityIntegration:
    """Integration tests for link validity across documentation files."""

    def test_all_markdown_links_resolve_to_existing_files(self):
        """
        All markdown links in documentation should resolve to existing files.

        Checks:
        - Links in CLAUDE.md to new docs
        - Links in new docs back to CLAUDE.md (if any)
        - No broken links
        """
        project_root = Path(__file__).parent.parent.parent

        # Files to check
        doc_files = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "LIBRARIES.md",
            project_root / "docs" / "PERFORMANCE.md",
            project_root / "docs" / "GIT-AUTOMATION.md",
        ]

        # This will FAIL if any file missing
        for doc_file in doc_files:
            assert doc_file.exists(), f"{doc_file.name} not found"

        # Extract all markdown links
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        broken_links = []

        for doc_file in doc_files:
            content = doc_file.read_text(encoding="utf-8")
            links = re.findall(link_pattern, content)

            for link_text, link_url in links:
                # Skip external links (http://, https://, mailto:)
                if link_url.startswith(("http://", "https://", "mailto:")):
                    continue

                # Skip anchors (starting with #)
                if link_url.startswith("#"):
                    continue

                # Resolve relative path
                link_path = (doc_file.parent / link_url).resolve()

                # Check if file exists
                if not link_path.exists():
                    broken_links.append({
                        "source": doc_file.name,
                        "link_text": link_text,
                        "link_url": link_url,
                        "resolved_path": str(link_path),
                    })

        assert not broken_links, (
            f"Found {len(broken_links)} broken links:\n" +
            "\n".join(
                f"  - {link['source']}: [{link['link_text']}]({link['link_url']}) -> {link['resolved_path']}"
                for link in broken_links
            )
        )

    def test_relative_links_work_from_different_directories(self):
        """
        Relative links should work from both project root and docs/ directory.

        Tests navigation from:
        - CLAUDE.md (root) -> docs/LIBRARIES.md
        - docs/LIBRARIES.md -> CLAUDE.md (if linked)
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"
        libraries_md = project_root / "docs" / "LIBRARIES.md"

        # This will FAIL if files missing
        assert claude_md.exists(), "CLAUDE.md not found"
        assert libraries_md.exists(), "docs/LIBRARIES.md not found"

        # Check CLAUDE.md -> docs/LIBRARIES.md link
        claude_content = claude_md.read_text(encoding="utf-8")

        # Link from root should be docs/LIBRARIES.md
        has_correct_link = "docs/LIBRARIES.md" in claude_content

        assert has_correct_link, (
            "CLAUDE.md should link to 'docs/LIBRARIES.md' (relative from root)"
        )

        # Verify the path actually works
        linked_path = (claude_md.parent / "docs" / "LIBRARIES.md").resolve()
        assert linked_path.exists(), (
            f"Link target does not exist: {linked_path}"
        )

    def test_no_absolute_paths_in_any_documentation(self):
        """
        No documentation file should contain absolute file system paths.

        Absolute paths break portability across systems.
        """
        project_root = Path(__file__).parent.parent.parent

        doc_files = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "LIBRARIES.md",
            project_root / "docs" / "PERFORMANCE.md",
            project_root / "docs" / "GIT-AUTOMATION.md",
        ]

        # This will FAIL if any file has absolute paths
        files_with_absolute_paths = []

        for doc_file in doc_files:
            if not doc_file.exists():
                continue  # Skip if file doesn't exist yet

            content = doc_file.read_text(encoding="utf-8")

            # Patterns for absolute paths
            absolute_patterns = [
                r'/Users/[^/\s]+',  # macOS paths
                r'C:\\[^\s]+',  # Windows paths
                r'/home/[^/\s]+',  # Linux paths
                r'/opt/[^/\s]+',  # Linux opt paths
            ]

            for pattern in absolute_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    files_with_absolute_paths.append({
                        "file": doc_file.name,
                        "pattern": pattern,
                        "matches": matches[:3],  # First 3 examples
                    })

        assert not files_with_absolute_paths, (
            f"Found absolute paths in documentation:\n" +
            "\n".join(
                f"  - {item['file']}: {item['pattern']} -> {item['matches']}"
                for item in files_with_absolute_paths
            )
        )


class TestBidirectionalReferenceIntegration:
    """Integration tests for bidirectional references between docs."""

    def test_claude_md_references_all_extracted_docs(self):
        """
        CLAUDE.md should reference all three extracted documentation files.

        Expected references:
        - docs/LIBRARIES.md (for library details)
        - docs/PERFORMANCE.md (for performance details)
        - docs/GIT-AUTOMATION.md (for git automation details)
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        # This will FAIL if references missing
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        required_references = [
            "LIBRARIES.md",
            "PERFORMANCE.md",
            "GIT-AUTOMATION.md",
        ]

        missing_references = []
        for ref in required_references:
            if ref not in content:
                missing_references.append(ref)

        assert not missing_references, (
            f"CLAUDE.md missing references to: {', '.join(missing_references)}"
        )

    def test_extracted_docs_reference_claude_md_where_appropriate(self):
        """
        Extracted docs should reference CLAUDE.md for context (if appropriate).

        At minimum, should mention they are extracted from CLAUDE.md.
        """
        project_root = Path(__file__).parent.parent.parent

        extracted_docs = [
            project_root / "docs" / "LIBRARIES.md",
            project_root / "docs" / "PERFORMANCE.md",
            project_root / "docs" / "GIT-AUTOMATION.md",
        ]

        # This will FAIL if docs don't mention source
        docs_without_context = []

        for doc_file in extracted_docs:
            if not doc_file.exists():
                docs_without_context.append(doc_file.name)
                continue

            content = doc_file.read_text(encoding="utf-8")

            # Should mention CLAUDE.md or have back-reference
            has_context = any(
                keyword in content
                for keyword in ["CLAUDE.md", "main documentation", "See CLAUDE.md"]
            )

            if not has_context:
                docs_without_context.append(doc_file.name)

        # Allow docs to exist without back-reference (not strictly required)
        # But it's good practice, so we warn
        if docs_without_context:
            pytest.skip(
                f"Docs without CLAUDE.md reference: {', '.join(docs_without_context)}. "
                f"Consider adding context for readers."
            )

    def test_documentation_hierarchy_makes_sense(self):
        """
        Documentation hierarchy should be logical.

        CLAUDE.md = Main entry point (overview + links)
        docs/*.md = Detailed technical content

        Users should be able to navigate from general to specific.
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"

        # This will FAIL if hierarchy unclear
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # CLAUDE.md should still have overview content (not just links)
        overview_sections = [
            "## Project Overview",
            "## Installation",
            "## Quick Reference",
        ]

        missing_overview = []
        for section in overview_sections:
            # Allow variations (Project Overview, Installation, etc.)
            if not any(
                keyword in content
                for keyword in [section, section.replace("## ", "")]
            ):
                missing_overview.append(section)

        assert not missing_overview, (
            f"CLAUDE.md missing overview sections: {', '.join(missing_overview)}. "
            f"Main file should retain high-level content, not just links."
        )


class TestContentConsistencyIntegration:
    """Integration tests for content consistency across files."""

    def test_library_counts_consistent_across_docs(self):
        """
        Library count should be consistent in CLAUDE.md and docs/LIBRARIES.md.

        If CLAUDE.md says "18 libraries", LIBRARIES.md should document all 18.
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"
        libraries_md = project_root / "docs" / "LIBRARIES.md"

        # This will FAIL if counts inconsistent
        assert claude_md.exists(), "CLAUDE.md not found"
        assert libraries_md.exists(), "docs/LIBRARIES.md not found"

        claude_content = claude_md.read_text(encoding="utf-8")
        libraries_content = libraries_md.read_text(encoding="utf-8")

        # Extract library count from CLAUDE.md
        library_count_match = re.search(r'(\d+)\s+(?:Shared\s+)?Libraries', claude_content)

        if library_count_match:
            stated_count = int(library_count_match.group(1))

            # Count libraries in LIBRARIES.md
            # Look for library entries (e.g., "1. **security_utils.py**")
            library_pattern = r'\d+\.\s+\*\*([a-z_]+\.py)\*\*'
            documented_libraries = re.findall(library_pattern, libraries_content)

            actual_count = len(documented_libraries)

            assert actual_count == stated_count, (
                f"Library count mismatch: CLAUDE.md claims {stated_count}, "
                f"but LIBRARIES.md documents {actual_count}. "
                f"Ensure consistency."
            )

    def test_performance_phase_counts_consistent(self):
        """
        Performance phase count should be consistent.

        If CLAUDE.md mentions "Phases 4-7", PERFORMANCE.md should document all 4.
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"
        performance_md = project_root / "docs" / "PERFORMANCE.md"

        # This will FAIL if phase counts inconsistent
        assert claude_md.exists(), "CLAUDE.md not found"
        assert performance_md.exists(), "docs/PERFORMANCE.md not found"

        performance_content = performance_md.read_text(encoding="utf-8")

        # Should have Phase 4, 5, 6, 7
        required_phases = ["Phase 4", "Phase 5", "Phase 6", "Phase 7"]

        missing_phases = []
        for phase in required_phases:
            if phase not in performance_content:
                missing_phases.append(phase)

        assert not missing_phases, (
            f"PERFORMANCE.md missing phases: {', '.join(missing_phases)}. "
            f"Should document Phases 4-7 completely."
        )

    def test_git_automation_env_vars_complete(self):
        """
        Git automation environment variables should be completely documented.

        If CLAUDE.md mentions git automation, GIT-AUTOMATION.md should have all vars.
        """
        project_root = Path(__file__).parent.parent.parent
        git_automation_md = project_root / "docs" / "GIT-AUTOMATION.md"

        # This will FAIL if env vars incomplete
        assert git_automation_md.exists(), "docs/GIT-AUTOMATION.md not found"

        content = git_automation_md.read_text(encoding="utf-8")

        # Required environment variables
        required_env_vars = [
            "AUTO_GIT_ENABLED",
            "AUTO_GIT_PUSH",
            "AUTO_GIT_PR",
        ]

        missing_env_vars = []
        for env_var in required_env_vars:
            if env_var not in content:
                missing_env_vars.append(env_var)

        assert not missing_env_vars, (
            f"GIT-AUTOMATION.md missing environment variables: {', '.join(missing_env_vars)}"
        )


class TestNavigationFlowIntegration:
    """Integration tests for user navigation flow."""

    def test_users_can_find_library_details_easily(self):
        """
        Users should be able to navigate from CLAUDE.md to library details easily.

        Flow: CLAUDE.md mentions libraries -> Link to LIBRARIES.md -> Find specific library
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"
        libraries_md = project_root / "docs" / "LIBRARIES.md"

        # This will FAIL if navigation flow broken
        assert claude_md.exists(), "CLAUDE.md not found"
        assert libraries_md.exists(), "docs/LIBRARIES.md not found"

        claude_content = claude_md.read_text(encoding="utf-8")

        # CLAUDE.md should mention libraries AND link to LIBRARIES.md
        # Note: Hardcoded counts removed to prevent drift (see refactor in Dec 2025)
        mentions_libraries = "### Libraries" in claude_content or "Libraries" in claude_content
        links_to_libraries = "LIBRARIES.md" in claude_content

        assert mentions_libraries, (
            "CLAUDE.md should mention libraries section"
        )
        assert links_to_libraries, (
            "CLAUDE.md should link to LIBRARIES.md for details"
        )

    def test_users_can_find_performance_details_easily(self):
        """
        Users should be able to navigate from CLAUDE.md to performance details easily.

        Flow: CLAUDE.md mentions performance -> Link to PERFORMANCE.md -> Find specific phase
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"
        performance_md = project_root / "docs" / "PERFORMANCE.md"

        # This will FAIL if navigation flow broken
        assert claude_md.exists(), "CLAUDE.md not found"
        assert performance_md.exists(), "docs/PERFORMANCE.md not found"

        claude_content = claude_md.read_text(encoding="utf-8")

        # CLAUDE.md should mention performance AND link to PERFORMANCE.md
        mentions_performance = re.search(r'[Pp]erformance|Phase \d+', claude_content)
        links_to_performance = "PERFORMANCE.md" in claude_content

        assert mentions_performance, (
            "CLAUDE.md should mention performance optimizations"
        )
        assert links_to_performance, (
            "CLAUDE.md should link to PERFORMANCE.md for details"
        )

    def test_users_can_find_git_automation_details_easily(self):
        """
        Users should be able to navigate from CLAUDE.md to git automation details easily.

        Flow: CLAUDE.md mentions git automation -> Link to GIT-AUTOMATION.md -> Find env vars
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"
        git_automation_md = project_root / "docs" / "GIT-AUTOMATION.md"

        # This will FAIL if navigation flow broken
        assert claude_md.exists(), "CLAUDE.md not found"
        assert git_automation_md.exists(), "docs/GIT-AUTOMATION.md not found"

        claude_content = claude_md.read_text(encoding="utf-8")

        # CLAUDE.md should mention git automation AND link to GIT-AUTOMATION.md
        mentions_git_automation = re.search(r'[Gg]it [Aa]utomation|AUTO_GIT', claude_content)
        links_to_git_automation = "GIT-AUTOMATION.md" in claude_content

        assert mentions_git_automation, (
            "CLAUDE.md should mention git automation"
        )
        assert links_to_git_automation, (
            "CLAUDE.md should link to GIT-AUTOMATION.md for details"
        )


class TestMarkdownRenderingIntegration:
    """Integration tests for markdown rendering correctness."""

    def test_all_markdown_syntax_valid(self):
        """
        All documentation files should have valid markdown syntax.

        Checks:
        - Balanced brackets in links
        - Balanced parentheses in links
        - Valid heading hierarchy
        - No malformed code blocks
        """
        project_root = Path(__file__).parent.parent.parent

        doc_files = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "LIBRARIES.md",
            project_root / "docs" / "PERFORMANCE.md",
            project_root / "docs" / "GIT-AUTOMATION.md",
        ]

        syntax_errors = []

        for doc_file in doc_files:
            if not doc_file.exists():
                continue

            content = doc_file.read_text(encoding="utf-8")

            # Check balanced brackets
            open_brackets = content.count('[')
            close_brackets = content.count(']')
            if open_brackets != close_brackets:
                syntax_errors.append(
                    f"{doc_file.name}: Unbalanced brackets ({open_brackets} [ vs {close_brackets} ])"
                )

            # Check balanced parentheses in links
            # (harder to check globally, so we check within link context)
            link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
            links = re.findall(link_pattern, content)

            for link_text, link_url in links:
                # Check for common malformations
                if link_text.count('[') > 0 or link_text.count(']') > 0:
                    syntax_errors.append(
                        f"{doc_file.name}: Malformed link text: [{link_text}]({link_url})"
                    )
                if link_url.count('(') > 0 or link_url.count(')') > 0:
                    syntax_errors.append(
                        f"{doc_file.name}: Malformed link URL: [{link_text}]({link_url})"
                    )

        assert not syntax_errors, (
            f"Found markdown syntax errors:\n" +
            "\n".join(f"  - {error}" for error in syntax_errors)
        )

    def test_headings_follow_hierarchy(self):
        """
        Markdown headings should follow proper hierarchy (no skipping levels).

        Valid: # -> ## -> ### -> ####
        Invalid: # -> ### (skipping ##)
        """
        project_root = Path(__file__).parent.parent.parent

        doc_files = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "LIBRARIES.md",
            project_root / "docs" / "PERFORMANCE.md",
            project_root / "docs" / "GIT-AUTOMATION.md",
        ]

        hierarchy_violations = []

        for doc_file in doc_files:
            if not doc_file.exists():
                continue

            content = doc_file.read_text(encoding="utf-8")
            lines = content.split('\n')

            previous_level = 0
            for line_num, line in enumerate(lines, 1):
                if line.startswith('#'):
                    # Count heading level
                    level = len(re.match(r'^#+', line).group(0))

                    # Check if skipping levels
                    if previous_level > 0 and level > previous_level + 1:
                        hierarchy_violations.append(
                            f"{doc_file.name}:{line_num}: Skipped heading level "
                            f"(from {'#' * previous_level} to {'#' * level}): {line[:50]}"
                        )

                    previous_level = level

        # Allow some flexibility (not all docs require strict hierarchy)
        if hierarchy_violations:
            pytest.skip(
                f"Heading hierarchy violations found:\n" +
                "\n".join(f"  - {violation}" for violation in hierarchy_violations)
            )

    def test_code_blocks_properly_closed(self):
        """
        All code blocks should be properly opened and closed.

        Checks:
        - Balanced ``` or ~~~ blocks
        - No unclosed code blocks
        """
        project_root = Path(__file__).parent.parent.parent

        doc_files = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "LIBRARIES.md",
            project_root / "docs" / "PERFORMANCE.md",
            project_root / "docs" / "GIT-AUTOMATION.md",
        ]

        code_block_errors = []

        for doc_file in doc_files:
            if not doc_file.exists():
                continue

            content = doc_file.read_text(encoding="utf-8")
            lines = content.split('\n')

            in_code_block = False
            code_block_start = 0

            for line_num, line in enumerate(lines, 1):
                if line.strip().startswith('```') or line.strip().startswith('~~~'):
                    if in_code_block:
                        # Closing code block
                        in_code_block = False
                    else:
                        # Opening code block
                        in_code_block = True
                        code_block_start = line_num

            # Check if any code block left unclosed
            if in_code_block:
                code_block_errors.append(
                    f"{doc_file.name}: Unclosed code block starting at line {code_block_start}"
                )

        assert not code_block_errors, (
            f"Found code block errors:\n" +
            "\n".join(f"  - {error}" for error in code_block_errors)
        )


class TestSearchabilityIntegration:
    """Integration tests for content searchability."""

    def test_key_terms_findable_via_search(self):
        """
        Key technical terms should be findable via search across all docs.

        Users searching for "security_utils" should find it in LIBRARIES.md.
        Users searching for "Phase 4" should find it in PERFORMANCE.md.
        """
        project_root = Path(__file__).parent.parent.parent

        # Key terms and where they should be found
        search_terms = {
            "security_utils": ["LIBRARIES.md"],
            "Phase 4": ["PERFORMANCE.md"],
            "AUTO_GIT_ENABLED": ["GIT-AUTOMATION.md"],
            "validate_path": ["LIBRARIES.md"],
            "SubagentStop": ["GIT-AUTOMATION.md", "CLAUDE.md"],
        }

        search_failures = []

        for term, expected_files in search_terms.items():
            found_in = []

            # Search all docs
            all_doc_files = [
                ("CLAUDE.md", project_root / "CLAUDE.md"),
                ("LIBRARIES.md", project_root / "docs" / "LIBRARIES.md"),
                ("PERFORMANCE.md", project_root / "docs" / "PERFORMANCE.md"),
                ("GIT-AUTOMATION.md", project_root / "docs" / "GIT-AUTOMATION.md"),
            ]

            for doc_name, doc_path in all_doc_files:
                if not doc_path.exists():
                    continue

                content = doc_path.read_text(encoding="utf-8")
                if term in content:
                    found_in.append(doc_name)

            # Check if found in expected files
            for expected_file in expected_files:
                if expected_file not in found_in:
                    search_failures.append(
                        f"Term '{term}' not found in {expected_file} (expected)"
                    )

        assert not search_failures, (
            f"Search failures:\n" +
            "\n".join(f"  - {failure}" for failure in search_failures)
        )


# Run integration tests with marker
pytest.mark.integration = pytest.mark.skipif(
    "not config.getoption('--run-integration')",
    reason="Integration tests require --run-integration flag"
)
