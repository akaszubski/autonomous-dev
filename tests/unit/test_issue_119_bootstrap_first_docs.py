#!/usr/bin/env python3
"""
TDD Tests for Issue #119: Bootstrap-First Architecture Documentation (FAILING - Red Phase)

This module contains FAILING tests that verify comprehensive documentation exists
for the bootstrap-first installation architecture.

Requirements (from Issue #119):
1. docs/BOOTSTRAP_PARADOX_SOLUTION.md - Architecture explanation document
2. README.md - Update "Quick Start" and rename "Why Not Just Use the Marketplace?" to "Install Options"
3. CLAUDE.md - Strengthen bootstrap-first messaging
4. PROJECT.md - Update distribution section with "primary method" language
5. install.sh - Update header comments to describe "PRIMARY install method"
6. CHANGELOG.md - Add v3.41.0 entry
7. Messaging consistency - Same terminology across all files
8. Link validation - All internal links to BOOTSTRAP_PARADOX_SOLUTION.md resolve

Test Coverage Target: 100% of documentation requirements

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe what documentation MUST exist
- Tests should FAIL until documentation is created
- Each test validates ONE specific documentation requirement

Author: test-master agent
Date: 2025-12-13
Related: GitHub Issue #119 - Bootstrap-First Architecture Documentation
"""

import os
import re
from pathlib import Path
from typing import List, Optional

import pytest


# Constants
REPO_ROOT = Path(__file__).parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
BOOTSTRAP_PARADOX_DOC = DOCS_DIR / "BOOTSTRAP_PARADOX_SOLUTION.md"
README_MD = REPO_ROOT / "README.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
PROJECT_MD = REPO_ROOT / ".claude" / "PROJECT.md"
INSTALL_SH = REPO_ROOT / "install.sh"
CHANGELOG_MD = REPO_ROOT / "CHANGELOG.md"


class TestBootstrapParadoxDocumentationExists:
    """Test BOOTSTRAP_PARADOX_SOLUTION.md exists with required sections."""

    def test_bootstrap_paradox_doc_exists(self):
        """Verify BOOTSTRAP_PARADOX_SOLUTION.md file exists.

        REQUIREMENT: New architecture documentation file.
        Expected: File exists at docs/BOOTSTRAP_PARADOX_SOLUTION.md.
        """
        assert BOOTSTRAP_PARADOX_DOC.exists(), (
            f"BOOTSTRAP_PARADOX_SOLUTION.md not found at {BOOTSTRAP_PARADOX_DOC}\n"
            "This file should explain the bootstrap-first architecture."
        )

    def test_bootstrap_doc_has_problem_section(self):
        """Verify document has 'The Problem' section explaining the paradox.

        REQUIREMENT: Clear explanation of why marketplace alone doesn't work.
        Expected: Section explaining the chicken-and-egg problem.
        """
        content = BOOTSTRAP_PARADOX_DOC.read_text()

        # Look for "The Problem" or "Problem" section heading
        assert re.search(r'##\s+(?:The\s+)?Problem', content), (
            "Missing 'The Problem' section in BOOTSTRAP_PARADOX_SOLUTION.md\n"
            "Should explain the chicken-and-egg paradox of marketplace installation."
        )

    def test_bootstrap_doc_has_solution_section(self):
        """Verify document has 'The Solution' section explaining install.sh approach.

        REQUIREMENT: Clear explanation of the bootstrap approach.
        Expected: Section explaining install.sh as primary method.
        """
        content = BOOTSTRAP_PARADOX_DOC.read_text()

        # Look for "The Solution" or "Solution" section heading
        assert re.search(r'##\s+(?:The\s+)?Solution', content), (
            "Missing 'The Solution' section in BOOTSTRAP_PARADOX_SOLUTION.md\n"
            "Should explain install.sh as the bootstrap approach."
        )

    def test_bootstrap_doc_has_architecture_section(self):
        """Verify document has 'Architecture' section explaining two-tier installation.

        REQUIREMENT: Technical explanation of installation architecture.
        Expected: Section detailing global vs project-specific installation.
        """
        content = BOOTSTRAP_PARADOX_DOC.read_text()

        # Look for "Architecture" or "Installation Architecture" section
        assert re.search(r'##\s+(?:Installation\s+)?Architecture', content), (
            "Missing 'Architecture' section in BOOTSTRAP_PARADOX_SOLUTION.md\n"
            "Should explain two-tier installation (global + project-specific)."
        )

    def test_bootstrap_doc_explains_global_infrastructure(self):
        """Verify document explains global ~/.claude/ infrastructure.

        REQUIREMENT: Clear explanation of global infrastructure requirement.
        Expected: Mentions ~/.claude/hooks/, ~/.claude/lib/, ~/.claude/settings.json.
        """
        content = BOOTSTRAP_PARADOX_DOC.read_text()

        # Check for global infrastructure mentions
        assert "~/.claude/hooks" in content or "~/.claude/lib" in content, (
            "BOOTSTRAP_PARADOX_SOLUTION.md should explain global infrastructure\n"
            "Must mention ~/.claude/hooks/, ~/.claude/lib/, or ~/.claude/settings.json"
        )

    def test_bootstrap_doc_explains_marketplace_limitations(self):
        """Verify document explains marketplace limitations.

        REQUIREMENT: Clear explanation of what marketplace cannot do.
        Expected: Explains marketplace can download but can't configure global infrastructure.
        """
        content = BOOTSTRAP_PARADOX_DOC.read_text()
        lower_content = content.lower()

        # Check for marketplace limitation explanation
        assert any(phrase in lower_content for phrase in [
            "marketplace can",
            "marketplace cannot",
            "marketplace limitation",
            "can't configure global"
        ]), (
            "BOOTSTRAP_PARADOX_SOLUTION.md should explain marketplace limitations\n"
            "Must mention what marketplace can and cannot do."
        )

    def test_bootstrap_doc_has_workflow_diagram_or_steps(self):
        """Verify document has installation workflow explanation.

        REQUIREMENT: Clear workflow showing installation process.
        Expected: Either diagram or step-by-step process explanation.
        """
        content = BOOTSTRAP_PARADOX_DOC.read_text()

        # Look for workflow indicators (steps, diagram, or numbered list)
        has_workflow = any([
            re.search(r'```(?:mermaid|diagram)', content),  # Diagram
            re.search(r'\d+\.\s+', content),  # Numbered steps
            "workflow" in content.lower(),
            "process" in content.lower()
        ])

        assert has_workflow, (
            "BOOTSTRAP_PARADOX_SOLUTION.md should include installation workflow\n"
            "Expected: Diagram or step-by-step process explanation."
        )


class TestReadmeBootstrapFirstMessaging:
    """Test README.md positions bootstrap as primary, marketplace as supplement."""

    def test_readme_exists(self):
        """Verify README.md file exists."""
        assert README_MD.exists(), f"README.md not found at {README_MD}"

    def test_readme_has_quick_start_section(self):
        """Verify README.md has 'Quick Start' section.

        REQUIREMENT: Installation instructions at top of README.
        Expected: Section titled 'Quick Start'.
        """
        content = README_MD.read_text()

        assert re.search(r'##\s+Quick\s+Start', content), (
            "Missing 'Quick Start' section in README.md"
        )

    def test_readme_quick_start_shows_install_sh_first(self):
        """Verify Quick Start section shows install.sh as primary method.

        REQUIREMENT: Bootstrap method comes first, not marketplace.
        Expected: install.sh command appears before any marketplace mention.
        """
        content = README_MD.read_text()

        # Extract Quick Start section
        quick_start_match = re.search(
            r'##\s+Quick\s+Start(.*?)(?=##|\Z)',
            content,
            re.DOTALL
        )
        assert quick_start_match, "Quick Start section not found"
        quick_start_content = quick_start_match.group(1)

        # Check install.sh appears
        assert "install.sh" in quick_start_content, (
            "Quick Start section should show install.sh installation command"
        )

        # Check install.sh appears before marketplace mention
        install_sh_pos = quick_start_content.find("install.sh")
        marketplace_pos = quick_start_content.lower().find("marketplace")

        if marketplace_pos != -1:  # If marketplace is mentioned
            assert install_sh_pos < marketplace_pos, (
                "Quick Start should show install.sh BEFORE marketplace option\n"
                "Bootstrap is the primary method, marketplace is supplement."
            )

    def test_readme_has_install_options_section(self):
        """Verify README.md has renamed 'Install Options' section (not 'Why Not Just Use Marketplace').

        REQUIREMENT: Rename section to reflect both options, not just marketplace.
        Expected: Section titled 'Install Options' or similar neutral name.
        """
        content = README_MD.read_text()

        # Should have "Install Options" or similar neutral section
        has_install_options = re.search(
            r'##\s+Install(?:ation)?\s+(?:Options|Methods)',
            content,
            re.IGNORECASE
        )

        assert has_install_options, (
            "README.md should have 'Install Options' or 'Installation Methods' section\n"
            "This replaces the old 'Why Not Just Use the Marketplace?' section."
        )

    def test_readme_install_options_describes_bootstrap_as_primary(self):
        """Verify Install Options section describes bootstrap as primary method.

        REQUIREMENT: Clear messaging that bootstrap is recommended.
        Expected: Language like 'primary', 'recommended', or 'main method'.
        """
        content = README_MD.read_text()

        # Extract Install Options section
        install_options_match = re.search(
            r'##\s+Install(?:ation)?\s+(?:Options|Methods)(.*?)(?=##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if install_options_match:
            install_options_content = install_options_match.group(1).lower()

            # Check for primary/recommended language
            assert any(word in install_options_content for word in [
                "primary",
                "recommended",
                "main method",
                "preferred",
                "default"
            ]), (
                "Install Options section should describe bootstrap as primary method\n"
                "Use language like 'primary', 'recommended', or 'main method'."
            )

    def test_readme_install_options_describes_marketplace_as_supplement(self):
        """Verify Install Options section describes marketplace as supplemental.

        REQUIREMENT: Clear messaging that marketplace is optional/supplemental.
        Expected: Language like 'optional', 'supplement', or 'alternative'.
        """
        content = README_MD.read_text()

        # Extract Install Options section
        install_options_match = re.search(
            r'##\s+Install(?:ation)?\s+(?:Options|Methods)(.*?)(?=##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if install_options_match:
            install_options_content = install_options_match.group(1).lower()

            # Check for supplemental language
            assert any(word in install_options_content for word in [
                "optional",
                "supplement",
                "alternative",
                "additional"
            ]), (
                "Install Options section should describe marketplace as supplemental\n"
                "Use language like 'optional', 'supplement', or 'alternative'."
            )

    def test_readme_links_to_bootstrap_paradox_doc(self):
        """Verify README.md links to BOOTSTRAP_PARADOX_SOLUTION.md.

        REQUIREMENT: Cross-reference to architecture documentation.
        Expected: Link to docs/BOOTSTRAP_PARADOX_SOLUTION.md.
        """
        content = README_MD.read_text()

        # Check for link to bootstrap paradox doc
        assert "BOOTSTRAP_PARADOX_SOLUTION" in content, (
            "README.md should link to docs/BOOTSTRAP_PARADOX_SOLUTION.md\n"
            "Users should be able to learn about the architecture."
        )


class TestClaudeMdBootstrapMessaging:
    """Test CLAUDE.md strengthens bootstrap-first messaging."""

    def test_claude_md_exists(self):
        """Verify CLAUDE.md file exists."""
        assert CLAUDE_MD.exists(), f"CLAUDE.md not found at {CLAUDE_MD}"

    def test_claude_md_has_installation_section(self):
        """Verify CLAUDE.md has installation section with bootstrap-first messaging.

        REQUIREMENT: Installation instructions in project-level CLAUDE.md.
        Expected: Section with installation commands.
        """
        content = CLAUDE_MD.read_text()

        # Look for installation section
        assert re.search(r'##\s+.*Install', content, re.IGNORECASE), (
            "CLAUDE.md should have installation section"
        )

    def test_claude_md_describes_bootstrap_as_development_system(self):
        """Verify CLAUDE.md describes autonomous-dev as development system, not simple plugin.

        REQUIREMENT: Correct positioning of what autonomous-dev is.
        Expected: Language emphasizing system/infrastructure vs simple plugin.
        """
        content = CLAUDE_MD.read_text().lower()

        # Check for development system positioning
        assert any(phrase in content for phrase in [
            "development system",
            "not a simple plugin",
            "requires global infrastructure",
            "bootstrap"
        ]), (
            "CLAUDE.md should emphasize autonomous-dev is a development system\n"
            "Not just a simple plugin that can be marketplace-only."
        )

    def test_claude_md_install_shows_install_sh_first(self):
        """Verify CLAUDE.md installation section shows install.sh first.

        REQUIREMENT: Bootstrap method is primary in all documentation.
        Expected: install.sh command appears before marketplace mention.
        """
        content = CLAUDE_MD.read_text()

        # Extract installation section - match first code block after "## Installation"
        install_match = re.search(
            r'##\s+Installation[^\n]*\n+```(?:bash)?\n(.*?)```',
            content,
            re.DOTALL
        )

        if install_match:
            install_content = install_match.group(1)

            # Should show install.sh
            assert "install.sh" in install_content, (
                "CLAUDE.md installation section should show install.sh command"
            )

    def test_claude_md_explains_why_not_marketplace_alone(self):
        """Verify CLAUDE.md explains why marketplace alone doesn't work.

        REQUIREMENT: Clear explanation of bootstrap requirement.
        Expected: Explains global infrastructure requirement.
        """
        content = CLAUDE_MD.read_text().lower()

        # Check for explanation
        assert any(phrase in content for phrase in [
            "marketplace can't",
            "can't configure global",
            "global infrastructure",
            "~/.claude/"
        ]), (
            "CLAUDE.md should explain why marketplace alone doesn't work\n"
            "Must mention global infrastructure or marketplace limitations."
        )


class TestProjectMdDistributionSection:
    """Test PROJECT.md distribution section updated with primary method language."""

    def test_project_md_exists(self):
        """Verify PROJECT.md file exists."""
        assert PROJECT_MD.exists(), f"PROJECT.md not found at {PROJECT_MD}"

    def test_project_md_has_distribution_section(self):
        """Verify PROJECT.md has distribution section.

        REQUIREMENT: Distribution strategy documented.
        Expected: Section about distribution/installation.
        """
        content = PROJECT_MD.read_text()

        # Look for distribution section
        assert re.search(r'##.*Distribution', content, re.IGNORECASE), (
            "PROJECT.md should have distribution section"
        )

    def test_project_md_describes_install_sh_as_primary_method(self):
        """Verify PROJECT.md distribution section describes install.sh as primary method.

        REQUIREMENT: Strategic alignment on distribution approach.
        Expected: Language indicating install.sh is primary distribution method.
        """
        content = PROJECT_MD.read_text()

        # Extract distribution section
        dist_match = re.search(
            r'##.*Distribution(.*?)(?=##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if dist_match:
            dist_content = dist_match.group(1).lower()

            # Check for primary method language
            assert any(phrase in dist_content for phrase in [
                "primary method",
                "primary install",
                "main distribution",
                "bootstrap-first",
                "install.sh is primary"
            ]), (
                "PROJECT.md distribution section should describe install.sh as primary method\n"
                "Use language like 'primary method' or 'bootstrap-first'."
            )

    def test_project_md_describes_marketplace_role(self):
        """Verify PROJECT.md clarifies marketplace role as supplemental.

        REQUIREMENT: Clear distinction between primary and supplemental methods.
        Expected: Marketplace described as optional/supplement to install.sh.
        """
        content = PROJECT_MD.read_text()

        # Extract distribution section
        dist_match = re.search(
            r'##.*Distribution(.*?)(?=##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if dist_match:
            dist_content = dist_match.group(1).lower()

            # Check for marketplace supplemental language
            assert any(phrase in dist_content for phrase in [
                "marketplace",
                "supplement",
                "optional",
                "additional"
            ]), (
                "PROJECT.md should clarify marketplace as supplemental to install.sh"
            )


class TestInstallShHeaderComments:
    """Test install.sh header describes it as PRIMARY install method."""

    def test_install_sh_exists(self):
        """Verify install.sh file exists."""
        assert INSTALL_SH.exists(), f"install.sh not found at {INSTALL_SH}"

    def test_install_sh_header_describes_primary_method(self):
        """Verify install.sh header comments describe it as PRIMARY install method.

        REQUIREMENT: Self-documenting script with clear purpose.
        Expected: Header comment mentioning 'primary' or 'main' install method.
        """
        content = INSTALL_SH.read_text()

        # Extract header (first 30 lines should have it)
        header = '\n'.join(content.split('\n')[:30]).lower()

        # Check for primary method language in header
        assert any(phrase in header for phrase in [
            "primary install",
            "primary method",
            "main install",
            "primary installation",
            "bootstrap install"
        ]), (
            "install.sh header comments should describe it as PRIMARY install method\n"
            "Add comment like '# Primary installation method for autonomous-dev'."
        )

    def test_install_sh_header_explains_what_it_does(self):
        """Verify install.sh header explains what the script does.

        REQUIREMENT: Clear documentation of script behavior.
        Expected: Header mentions global infrastructure setup.
        """
        content = INSTALL_SH.read_text()

        # Extract header (first 30 lines)
        header = '\n'.join(content.split('\n')[:30]).lower()

        # Check for explanation of behavior
        assert any(phrase in header for phrase in [
            "global infrastructure",
            "~/.claude/",
            "hooks",
            "creates",
            "configures"
        ]), (
            "install.sh header should explain what it does\n"
            "Should mention global infrastructure setup or ~/.claude/ configuration."
        )

    def test_install_sh_header_contrasts_with_marketplace(self):
        """Verify install.sh header contrasts with marketplace approach.

        REQUIREMENT: Clear distinction between install.sh and marketplace.
        Expected: Header mentions what marketplace can't do.
        """
        content = INSTALL_SH.read_text()

        # Extract header (first 30 lines)
        header = '\n'.join(content.split('\n')[:30]).lower()

        # Check for marketplace contrast
        assert "marketplace" in header, (
            "install.sh header should mention marketplace\n"
            "Should explain what marketplace can't do that install.sh handles."
        )


class TestChangelogEntry:
    """Test CHANGELOG.md has v3.41.0 entry for Issue #119."""

    def test_changelog_exists(self):
        """Verify CHANGELOG.md file exists."""
        assert CHANGELOG_MD.exists(), f"CHANGELOG.md not found at {CHANGELOG_MD}"

    def test_changelog_has_v3_41_0_entry(self):
        """Verify CHANGELOG.md has v3.41.0 version entry.

        REQUIREMENT: Version tracking for documentation changes.
        Expected: ## [3.41.0] or ## v3.41.0 heading.
        """
        content = CHANGELOG_MD.read_text()

        # Check for version heading
        assert re.search(r'##\s+\[?v?3\.41\.0\]?', content), (
            "CHANGELOG.md should have v3.41.0 entry\n"
            "Add heading like '## [3.41.0] - YYYY-MM-DD'."
        )

    def test_changelog_v3_41_0_mentions_bootstrap_first(self):
        """Verify v3.41.0 entry mentions bootstrap-first documentation.

        REQUIREMENT: Clear changelog entry for Issue #119.
        Expected: Mentions bootstrap-first or Issue #119.
        """
        content = CHANGELOG_MD.read_text()

        # Extract v3.41.0 section
        version_match = re.search(
            r'##\s+\[?v?3\.41\.0\]?(.*?)(?=##\s+\[?v?|\Z)',
            content,
            re.DOTALL
        )

        assert version_match, "v3.41.0 section not found"
        version_content = version_match.group(1).lower()

        # Check for bootstrap-first mention
        assert any(phrase in version_content for phrase in [
            "bootstrap",
            "issue #119",
            "issue 119",
            "#119",
            "primary install",
            "installation architecture"
        ]), (
            "v3.41.0 changelog entry should mention bootstrap-first documentation\n"
            "Should reference Issue #119 or describe the change."
        )

    def test_changelog_v3_41_0_mentions_new_doc_file(self):
        """Verify v3.41.0 entry mentions BOOTSTRAP_PARADOX_SOLUTION.md.

        REQUIREMENT: Document new file creation in changelog.
        Expected: Mentions the new documentation file.
        """
        content = CHANGELOG_MD.read_text()

        # Extract v3.41.0 section
        version_match = re.search(
            r'##\s+\[?v?3\.41\.0\]?(.*?)(?=##\s+\[?v?|\Z)',
            content,
            re.DOTALL
        )

        if version_match:
            version_content = version_match.group(1)

            # Check for new doc file mention
            assert "BOOTSTRAP_PARADOX_SOLUTION" in version_content, (
                "v3.41.0 changelog should mention new BOOTSTRAP_PARADOX_SOLUTION.md file"
            )


class TestMessagingConsistency:
    """Test consistent terminology across all documentation files."""

    def test_all_docs_use_consistent_terminology_for_bootstrap(self):
        """Verify all docs use consistent language for bootstrap method.

        REQUIREMENT: Consistent messaging across documentation.
        Expected: Same terminology (e.g., 'primary method', 'bootstrap-first').
        """
        docs_to_check = [
            README_MD,
            CLAUDE_MD,
            PROJECT_MD
        ]

        if BOOTSTRAP_PARADOX_DOC.exists():
            docs_to_check.append(BOOTSTRAP_PARADOX_DOC)

        # Collect terminology from all docs
        terminology_usage = {}

        for doc in docs_to_check:
            if not doc.exists():
                continue

            content = doc.read_text().lower()
            terminology_usage[doc.name] = {
                'primary': 'primary method' in content or 'primary install' in content,
                'bootstrap': 'bootstrap' in content,
                'recommended': 'recommended' in content
            }

        # At least one consistent term should appear in all docs
        # (We don't enforce WHICH term, just that there's consistency)
        if terminology_usage:
            # Check if at least one term is used consistently
            for term in ['primary', 'bootstrap', 'recommended']:
                usage_count = sum(1 for doc_terms in terminology_usage.values() if doc_terms[term])

                # If used in multiple docs, should be used in most/all
                if usage_count > 0:
                    docs_count = len(terminology_usage)
                    # Allow some flexibility, but most should use same term
                    assert usage_count >= (docs_count * 0.6), (
                        f"Inconsistent terminology: '{term}' used in {usage_count}/{docs_count} docs\n"
                        f"Usage: {terminology_usage}\n"
                        "Use consistent terminology across all documentation files."
                    )

    def test_all_docs_use_consistent_terminology_for_marketplace(self):
        """Verify all docs use consistent language for marketplace role.

        REQUIREMENT: Consistent messaging about marketplace.
        Expected: Same terminology (e.g., 'optional', 'supplement').
        """
        docs_to_check = [
            README_MD,
            CLAUDE_MD,
            PROJECT_MD
        ]

        if BOOTSTRAP_PARADOX_DOC.exists():
            docs_to_check.append(BOOTSTRAP_PARADOX_DOC)

        # Collect marketplace terminology
        marketplace_terms = {}

        for doc in docs_to_check:
            if not doc.exists():
                continue

            content = doc.read_text().lower()
            marketplace_terms[doc.name] = {
                'optional': 'optional' in content,
                'supplement': 'supplement' in content,
                'alternative': 'alternative' in content
            }

        # Similar check as above - consistent usage of marketplace terms
        if marketplace_terms:
            for term in ['optional', 'supplement', 'alternative']:
                usage_count = sum(1 for doc_terms in marketplace_terms.values() if doc_terms[term])

                if usage_count > 0:
                    docs_count = len(marketplace_terms)
                    # Most docs should use same term
                    assert usage_count >= (docs_count * 0.5), (
                        f"Inconsistent marketplace terminology: '{term}' used in {usage_count}/{docs_count} docs\n"
                        f"Usage: {marketplace_terms}\n"
                        "Use consistent terminology for marketplace role."
                    )


class TestLinkValidation:
    """Test all internal links to BOOTSTRAP_PARADOX_SOLUTION.md resolve correctly."""

    def test_readme_link_to_bootstrap_doc_is_valid(self):
        """Verify README.md link to BOOTSTRAP_PARADOX_SOLUTION.md is valid.

        REQUIREMENT: Working cross-references.
        Expected: Link uses correct relative path.
        """
        if not README_MD.exists():
            pytest.skip("README.md doesn't exist yet")

        content = README_MD.read_text()

        # Extract markdown links to bootstrap doc
        links = re.findall(
            r'\[([^\]]+)\]\(([^)]+BOOTSTRAP_PARADOX[^)]+)\)',
            content
        )

        if links:
            for link_text, link_path in links:
                # Resolve relative path from README.md location
                target = (README_MD.parent / link_path).resolve()

                assert target == BOOTSTRAP_PARADOX_DOC.resolve(), (
                    f"README.md link to bootstrap doc is incorrect\n"
                    f"Link path: {link_path}\n"
                    f"Expected: docs/BOOTSTRAP_PARADOX_SOLUTION.md\n"
                    f"Resolved to: {target}\n"
                    f"Should resolve to: {BOOTSTRAP_PARADOX_DOC}"
                )

    def test_claude_md_link_to_bootstrap_doc_is_valid(self):
        """Verify CLAUDE.md link to BOOTSTRAP_PARADOX_SOLUTION.md is valid.

        REQUIREMENT: Working cross-references.
        Expected: Link uses correct relative path.
        """
        if not CLAUDE_MD.exists():
            pytest.skip("CLAUDE.md doesn't exist yet")

        content = CLAUDE_MD.read_text()

        # Extract markdown links to bootstrap doc
        links = re.findall(
            r'\[([^\]]+)\]\(([^)]+BOOTSTRAP_PARADOX[^)]+)\)',
            content
        )

        if links:
            for link_text, link_path in links:
                # Resolve relative path from CLAUDE.md location
                target = (CLAUDE_MD.parent / link_path).resolve()

                assert target == BOOTSTRAP_PARADOX_DOC.resolve(), (
                    f"CLAUDE.md link to bootstrap doc is incorrect\n"
                    f"Link path: {link_path}\n"
                    f"Expected: docs/BOOTSTRAP_PARADOX_SOLUTION.md\n"
                    f"Resolved to: {target}\n"
                    f"Should resolve to: {BOOTSTRAP_PARADOX_DOC}"
                )

    def test_project_md_link_to_bootstrap_doc_is_valid(self):
        """Verify PROJECT.md link to BOOTSTRAP_PARADOX_SOLUTION.md is valid (if exists).

        REQUIREMENT: Working cross-references.
        Expected: Link uses correct relative path.
        """
        if not PROJECT_MD.exists():
            pytest.skip("PROJECT.md doesn't exist yet")

        content = PROJECT_MD.read_text()

        # Extract markdown links to bootstrap doc
        links = re.findall(
            r'\[([^\]]+)\]\(([^)]+BOOTSTRAP_PARADOX[^)]+)\)',
            content
        )

        if links:
            for link_text, link_path in links:
                # Resolve relative path from PROJECT.md location
                target = (PROJECT_MD.parent / link_path).resolve()

                # PROJECT.md is in .claude/, so link should be ../docs/BOOTSTRAP_PARADOX_SOLUTION.md
                assert target == BOOTSTRAP_PARADOX_DOC.resolve(), (
                    f"PROJECT.md link to bootstrap doc is incorrect\n"
                    f"Link path: {link_path}\n"
                    f"Expected: ../docs/BOOTSTRAP_PARADOX_SOLUTION.md (from .claude/)\n"
                    f"Resolved to: {target}\n"
                    f"Should resolve to: {BOOTSTRAP_PARADOX_DOC}"
                )


class TestBootstrapFirstArchitectureCompleteness:
    """Test overall completeness of bootstrap-first architecture documentation."""

    def test_all_required_files_updated(self):
        """Verify all required files exist and have been updated.

        REQUIREMENT: Complete documentation coverage.
        Expected: All 6 files exist and contain relevant updates.
        """
        required_files = {
            'BOOTSTRAP_PARADOX_SOLUTION.md': BOOTSTRAP_PARADOX_DOC,
            'README.md': README_MD,
            'CLAUDE.md': CLAUDE_MD,
            'PROJECT.md': PROJECT_MD,
            'install.sh': INSTALL_SH,
            'CHANGELOG.md': CHANGELOG_MD
        }

        missing_files = []
        for name, path in required_files.items():
            if not path.exists():
                missing_files.append(name)

        assert not missing_files, (
            f"Missing required files for Issue #119:\n{', '.join(missing_files)}\n"
            "All files should be created/updated for bootstrap-first architecture."
        )

    def test_bootstrap_paradox_doc_is_comprehensive(self):
        """Verify BOOTSTRAP_PARADOX_SOLUTION.md is comprehensive (not a stub).

        REQUIREMENT: Thorough architecture documentation.
        Expected: Document has substantial content (> 50 lines, multiple sections).
        """
        if not BOOTSTRAP_PARADOX_DOC.exists():
            pytest.skip("BOOTSTRAP_PARADOX_SOLUTION.md doesn't exist yet")

        content = BOOTSTRAP_PARADOX_DOC.read_text()
        lines = content.split('\n')

        # Should be substantial (more than a stub)
        assert len(lines) > 50, (
            f"BOOTSTRAP_PARADOX_SOLUTION.md appears to be a stub ({len(lines)} lines)\n"
            "Should be comprehensive documentation (> 50 lines)."
        )

        # Should have multiple sections (at least 3 headings)
        headings = re.findall(r'^##\s+', content, re.MULTILINE)
        assert len(headings) >= 3, (
            f"BOOTSTRAP_PARADOX_SOLUTION.md should have at least 3 sections (found {len(headings)})\n"
            "Expected: Problem, Solution, Architecture, etc."
        )

    def test_no_old_marketplace_first_language_remains(self):
        """Verify no old 'marketplace-first' language remains in documentation.

        REQUIREMENT: Complete migration to bootstrap-first messaging.
        Expected: No contradictory language suggesting marketplace is primary.
        """
        docs_to_check = [README_MD, CLAUDE_MD, PROJECT_MD]

        problematic_phrases = [
            "use the marketplace",
            "marketplace install",
            "install from marketplace",
            "marketplace is primary",
            "marketplace first"
        ]

        for doc in docs_to_check:
            if not doc.exists():
                continue

            content = doc.read_text().lower()

            # Check context around marketplace mentions
            for phrase in problematic_phrases:
                # Allow "use the marketplace" if it's describing optional/supplement
                if phrase in content:
                    # Get surrounding context (100 chars before and after)
                    index = content.find(phrase)
                    context = content[max(0, index-100):min(len(content), index+100)]

                    # If context doesn't indicate optional/supplement, flag it
                    has_qualifier = any(qual in context for qual in [
                        'optional',
                        'supplement',
                        'alternative',
                        'also',
                        'can also',
                        'or'
                    ])

                    if not has_qualifier and phrase in ['marketplace is primary', 'marketplace first']:
                        pytest.fail(
                            f"{doc.name} contains old marketplace-first language: '{phrase}'\n"
                            f"Context: ...{context}...\n"
                            "All documentation should position bootstrap as primary, marketplace as supplement."
                        )


# Edge Cases and Error Handling

class TestBootstrapDocumentationEdgeCases:
    """Test edge cases and error handling in bootstrap documentation."""

    def test_bootstrap_doc_handles_existing_installation(self):
        """Verify BOOTSTRAP_PARADOX_SOLUTION.md addresses existing installations.

        REQUIREMENT: Complete user guidance.
        Expected: Mentions upgrade path or existing installation handling.
        """
        if not BOOTSTRAP_PARADOX_DOC.exists():
            pytest.skip("BOOTSTRAP_PARADOX_SOLUTION.md doesn't exist yet")

        content = BOOTSTRAP_PARADOX_DOC.read_text().lower()

        # Should address existing installations or upgrades
        assert any(phrase in content for phrase in [
            'existing install',
            'upgrade',
            'already installed',
            'migration',
            'update'
        ]), (
            "BOOTSTRAP_PARADOX_SOLUTION.md should address existing installations\n"
            "Users may already have marketplace install and need guidance."
        )

    def test_install_sh_header_has_usage_example(self):
        """Verify install.sh header has usage example.

        REQUIREMENT: Self-documenting script.
        Expected: Header shows how to run the script.
        """
        if not INSTALL_SH.exists():
            pytest.skip("install.sh doesn't exist yet")

        content = INSTALL_SH.read_text()
        header = '\n'.join(content.split('\n')[:30])

        # Should show usage example
        assert any(phrase in header for phrase in [
            'bash <(',
            'curl',
            'install.sh',
            'Usage:',
            'Example:'
        ]), (
            "install.sh header should include usage example\n"
            "Show users how to run the script."
        )

    def test_documentation_cross_references_are_bidirectional(self):
        """Verify documentation files cross-reference each other appropriately.

        REQUIREMENT: Discoverable documentation.
        Expected: README links to BOOTSTRAP_PARADOX_SOLUTION, which may link back.
        """
        if not BOOTSTRAP_PARADOX_DOC.exists():
            pytest.skip("BOOTSTRAP_PARADOX_SOLUTION.md doesn't exist yet")

        readme_content = README_MD.read_text()
        bootstrap_content = BOOTSTRAP_PARADOX_DOC.read_text()

        # README should link to BOOTSTRAP_PARADOX_SOLUTION
        assert "BOOTSTRAP_PARADOX_SOLUTION" in readme_content, (
            "README.md should link to BOOTSTRAP_PARADOX_SOLUTION.md"
        )

        # BOOTSTRAP_PARADOX_SOLUTION might link back to README (optional but good practice)
        # This is a soft check - we don't fail if it's not there
        if "README" not in bootstrap_content:
            # Just a warning, not a failure
            pass  # Could add a pytest.warn here if available


# Integration Tests

class TestBootstrapFirstWorkflow:
    """Test bootstrap-first workflow from user perspective."""

    def test_user_can_discover_install_method_from_readme(self):
        """Verify user reading README.md can discover install.sh as primary method.

        REQUIREMENT: Clear user journey from README to installation.
        Expected: README Quick Start clearly shows install.sh command.
        """
        if not README_MD.exists():
            pytest.skip("README.md doesn't exist yet")

        content = README_MD.read_text()

        # Extract Quick Start section
        quick_start_match = re.search(
            r'##\s+Quick\s+Start(.*?)(?=##|\Z)',
            content,
            re.DOTALL
        )

        assert quick_start_match, "Quick Start section not found"
        quick_start = quick_start_match.group(1)

        # Should have clear install.sh command
        assert "bash <(curl" in quick_start or "install.sh" in quick_start, (
            "Quick Start should show clear install.sh command\n"
            "User should immediately see how to install."
        )

    def test_user_can_understand_why_bootstrap_needed_from_docs(self):
        """Verify user can understand bootstrap requirement from documentation.

        REQUIREMENT: Educational documentation.
        Expected: Clear explanation exists and is linked from README.
        """
        if not README_MD.exists() or not BOOTSTRAP_PARADOX_DOC.exists():
            pytest.skip("Required docs don't exist yet")

        readme_content = README_MD.read_text()

        # README should link to explanation
        assert "BOOTSTRAP_PARADOX_SOLUTION" in readme_content, (
            "README should link to architecture explanation"
        )

        # Explanation should exist and be clear
        bootstrap_content = BOOTSTRAP_PARADOX_DOC.read_text()
        assert len(bootstrap_content) > 500, (
            "BOOTSTRAP_PARADOX_SOLUTION.md should have substantial explanation"
        )

    def test_documentation_provides_complete_installation_path(self):
        """Verify documentation provides complete path from discovery to installation.

        REQUIREMENT: Complete user journey.
        Expected: README → BOOTSTRAP_PARADOX_SOLUTION → install.sh is clear.
        """
        if not README_MD.exists():
            pytest.skip("README.md doesn't exist yet")

        content = README_MD.read_text()

        # Should have both install command AND explanation link
        has_install_command = "install.sh" in content
        has_explanation_link = "BOOTSTRAP_PARADOX_SOLUTION" in content

        assert has_install_command and has_explanation_link, (
            "README should have both install command AND link to explanation\n"
            f"Has install command: {has_install_command}\n"
            f"Has explanation link: {has_explanation_link}"
        )
