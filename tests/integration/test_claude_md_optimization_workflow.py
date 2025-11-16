#!/usr/bin/env python3
"""
Integration Tests for CLAUDE.md Optimization Workflow - Issue #78 (FAILING - Red Phase)

This module contains FAILING integration tests that validate the complete optimization
workflow across multiple documentation files and validation systems.

Integration test coverage:
1. End-to-end content extraction workflow
2. Cross-document link resolution
3. Alignment validation integration
4. Documentation search integration
5. Version control integration

These tests ensure that all components work together correctly after optimization.

Author: test-master agent
Date: 2025-11-16
Issue: #78 (CLAUDE.md optimization)
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestEndToEndContentExtraction:
    """Test complete content extraction workflow."""

    def test_performance_content_fully_extracted(self):
        """
        Verify performance content fully extracted from CLAUDE.md to PERFORMANCE-HISTORY.md.

        Workflow:
        1. CLAUDE.md has condensed performance summary
        2. PERFORMANCE-HISTORY.md has detailed phase information
        3. Link from CLAUDE.md to PERFORMANCE-HISTORY.md works
        4. All phase details accessible via navigation
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        performance_history = project_root / "docs" / "PERFORMANCE-HISTORY.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert performance_history.exists(), "PERFORMANCE-HISTORY.md not created"

        claude_content = claude_md.read_text(encoding="utf-8")
        perf_content = performance_history.read_text(encoding="utf-8")

        # CLAUDE.md should have summary (not details)
        # Detailed phase info should be in PERFORMANCE-HISTORY.md
        phases_in_claude = len(re.findall(r"Phase \d+", claude_content))
        phases_in_perf = len(re.findall(r"Phase \d+", perf_content))

        # PERFORMANCE-HISTORY.md should have MORE phase mentions than CLAUDE.md
        assert phases_in_perf > phases_in_claude, (
            f"Performance details not properly extracted. "
            f"CLAUDE.md has {phases_in_claude} phase mentions, "
            f"PERFORMANCE-HISTORY.md has {phases_in_perf}. "
            f"Detailed content should be in PERFORMANCE-HISTORY.md."
        )

        # CLAUDE.md should link to PERFORMANCE-HISTORY.md
        assert "PERFORMANCE-HISTORY.md" in claude_content, (
            "CLAUDE.md missing link to PERFORMANCE-HISTORY.md"
        )

    def test_batch_processing_content_fully_extracted(self):
        """
        Verify batch processing content fully extracted to BATCH-PROCESSING.md.

        Workflow:
        1. CLAUDE.md has brief batch processing overview
        2. BATCH-PROCESSING.md has complete workflow guide
        3. Link from CLAUDE.md to BATCH-PROCESSING.md works
        4. All workflow details accessible via navigation
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        batch_processing = project_root / "docs" / "BATCH-PROCESSING.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert batch_processing.exists(), "BATCH-PROCESSING.md not created"

        claude_content = claude_md.read_text(encoding="utf-8")
        batch_content = batch_processing.read_text(encoding="utf-8")

        # BATCH-PROCESSING.md should have MORE /batch-implement details
        batch_mentions_claude = claude_content.count("/batch-implement")
        batch_mentions_batch = batch_content.count("/batch-implement")

        assert batch_mentions_batch >= batch_mentions_claude, (
            f"Batch processing details not properly extracted. "
            f"CLAUDE.md has {batch_mentions_claude} mentions, "
            f"BATCH-PROCESSING.md has {batch_mentions_batch}."
        )

        # CLAUDE.md should link to BATCH-PROCESSING.md
        assert "BATCH-PROCESSING.md" in claude_content, (
            "CLAUDE.md missing link to BATCH-PROCESSING.md"
        )

    def test_agent_architecture_fully_extracted(self):
        """
        Verify agent architecture fully extracted to AGENTS.md.

        Workflow:
        1. CLAUDE.md has agent count and brief overview
        2. AGENTS.md has complete agent descriptions
        3. Link from CLAUDE.md to AGENTS.md works
        4. All agent details accessible via navigation
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        agents_md = project_root / "docs" / "AGENTS.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert agents_md.exists(), "AGENTS.md not created"

        claude_content = claude_md.read_text(encoding="utf-8")
        agents_content = agents_md.read_text(encoding="utf-8")

        # AGENTS.md should have MORE agent mentions (individual descriptions)
        # Count lines mentioning specific agents
        agent_names = [
            "researcher", "planner", "test-master", "implementer", "reviewer",
            "security-auditor", "doc-master", "advisor", "quality-validator"
        ]

        agents_in_claude = sum(1 for agent in agent_names if agent in claude_content)
        agents_in_agents = sum(1 for agent in agent_names if agent in agents_content)

        assert agents_in_agents >= agents_in_claude, (
            f"Agent details not properly extracted. "
            f"CLAUDE.md mentions {agents_in_claude} agents, "
            f"AGENTS.md mentions {agents_in_agents}."
        )

        # CLAUDE.md should link to AGENTS.md
        assert "AGENTS.md" in claude_content, (
            "CLAUDE.md missing link to AGENTS.md"
        )

    def test_hooks_reference_fully_extracted(self):
        """
        Verify hooks reference fully extracted to HOOKS.md.

        Workflow:
        1. CLAUDE.md has hook count and brief overview
        2. HOOKS.md has complete hook listings
        3. Link from CLAUDE.md to HOOKS.md works
        4. All hook details accessible via navigation
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        hooks_md = project_root / "docs" / "HOOKS.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert hooks_md.exists(), "HOOKS.md not created"

        claude_content = claude_md.read_text(encoding="utf-8")
        hooks_content = hooks_md.read_text(encoding="utf-8")

        # HOOKS.md should have MORE hook mentions
        hook_names = [
            "auto_format", "auto_test", "security_scan",
            "validate_project_alignment", "enforce_pipeline_complete"
        ]

        hooks_in_claude = sum(1 for hook in hook_names if hook in claude_content)
        hooks_in_hooks = sum(1 for hook in hook_names if hook in hooks_content)

        assert hooks_in_hooks >= hooks_in_claude, (
            f"Hook details not properly extracted. "
            f"CLAUDE.md mentions {hooks_in_claude} hooks, "
            f"HOOKS.md mentions {hooks_in_hooks}."
        )

        # CLAUDE.md should link to HOOKS.md
        assert "HOOKS.md" in claude_content, (
            "CLAUDE.md missing link to HOOKS.md"
        )


class TestCrossDocumentLinkResolution:
    """Test that all cross-document links resolve correctly."""

    def test_all_documentation_links_resolve(self):
        """
        Verify all markdown links in all documentation files resolve correctly.

        Checks:
        - CLAUDE.md links to new docs work
        - New docs links to CLAUDE.md work
        - New docs links to other docs work
        - No broken relative paths
        """
        project_root = Path(__file__).parent.parent.parent

        docs_to_check = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "PERFORMANCE-HISTORY.md",
            project_root / "docs" / "BATCH-PROCESSING.md",
            project_root / "docs" / "AGENTS.md",
            project_root / "docs" / "HOOKS.md",
        ]

        broken_links = []

        for doc_path in docs_to_check:
            if not doc_path.exists():
                broken_links.append(f"{doc_path.name} does not exist")
                continue

            content = doc_path.read_text(encoding="utf-8")

            # Find all markdown links to .md files
            link_pattern = r'\[([^\]]+)\]\(([^\)]+\.md)\)'
            links = re.findall(link_pattern, content)

            for link_text, link_url in links:
                # Skip external links
                if link_url.startswith("http"):
                    continue

                # Resolve relative path
                target_path = (doc_path.parent / link_url).resolve()

                if not target_path.exists():
                    broken_links.append(
                        f"{doc_path.name}: [{link_text}]({link_url}) -> {target_path}"
                    )

        assert not broken_links, (
            f"Broken documentation links found:\n" +
            "\n".join(f"  - {link}" for link in broken_links)
        )

    def test_bidirectional_navigation_works(self):
        """
        Verify bidirectional navigation between CLAUDE.md and extracted docs.

        Each extracted doc should link back to CLAUDE.md, and CLAUDE.md should
        link forward to each extracted doc.
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        new_docs = {
            "PERFORMANCE-HISTORY.md": project_root / "docs" / "PERFORMANCE-HISTORY.md",
            "BATCH-PROCESSING.md": project_root / "docs" / "BATCH-PROCESSING.md",
            "AGENTS.md": project_root / "docs" / "AGENTS.md",
            "HOOKS.md": project_root / "docs" / "HOOKS.md",
        }

        assert claude_md.exists(), "CLAUDE.md not found"
        claude_content = claude_md.read_text(encoding="utf-8")

        missing_forward_links = []
        missing_back_links = []

        for doc_name, doc_path in new_docs.items():
            assert doc_path.exists(), f"{doc_name} not created"

            doc_content = doc_path.read_text(encoding="utf-8")

            # Check forward link (CLAUDE.md -> new doc)
            if doc_name not in claude_content:
                missing_forward_links.append(f"CLAUDE.md -> {doc_name}")

            # Check back link (new doc -> CLAUDE.md)
            if "CLAUDE.md" not in doc_content:
                missing_back_links.append(f"{doc_name} -> CLAUDE.md")

        assert not missing_forward_links, (
            f"Missing forward links from CLAUDE.md:\n" +
            "\n".join(f"  - {link}" for link in missing_forward_links)
        )

        assert not missing_back_links, (
            f"Missing back links to CLAUDE.md:\n" +
            "\n".join(f"  - {link}" for link in missing_back_links)
        )


class TestAlignmentValidationIntegration:
    """Test integration with alignment validation systems."""

    def test_validate_claude_alignment_hook_passes(self):
        """
        Verify validate_claude_alignment.py passes after optimization.

        This is an integration test that runs the actual validation hook
        to ensure optimization doesn't break alignment checks.
        """
        project_root = Path(__file__).parent.parent.parent
        validator = project_root / "plugins" / "autonomous-dev" / "hooks" / "validate_claude_alignment.py"

        if not validator.exists():
            pytest.skip("validate_claude_alignment.py not found")

        # Run validator
        result = subprocess.run(
            ["python3", str(validator)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, (
            f"Alignment validation failed:\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    def test_documentation_parity_maintained(self):
        """
        Verify documentation parity across CLAUDE.md and PROJECT.md.

        After optimization, key metadata should still be synchronized:
        - Agent counts
        - Command counts
        - Skills counts
        - Version numbers
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        project_md = project_root / "PROJECT.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert project_md.exists(), "PROJECT.md not found"

        claude_content = claude_md.read_text(encoding="utf-8")
        project_content = project_md.read_text(encoding="utf-8")

        # Check agent count parity (both should mention 20 agents)
        claude_has_20_agents = re.search(r"20\s+(?:AI\s+)?agents", claude_content, re.IGNORECASE)
        project_has_20_agents = re.search(r"20\s+agents", project_content, re.IGNORECASE)

        if claude_has_20_agents and project_has_20_agents:
            # Both documents agree on agent count - good!
            pass
        else:
            pytest.fail(
                "Agent count mismatch between CLAUDE.md and PROJECT.md. "
                "Optimization may have broken parity."
            )

    def test_all_validation_hooks_pass(self):
        """
        Verify all validation hooks pass after optimization.

        Runs multiple validation systems to ensure no regressions:
        - CLAUDE.md alignment
        - Documentation parity
        - Project alignment
        """
        project_root = Path(__file__).parent.parent.parent

        validators = [
            project_root / "plugins" / "autonomous-dev" / "hooks" / "validate_claude_alignment.py",
            project_root / "plugins" / "autonomous-dev" / "lib" / "validate_documentation_parity.py",
        ]

        failures = []

        for validator in validators:
            if not validator.exists():
                continue

            result = subprocess.run(
                ["python3", str(validator)],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                failures.append(
                    f"{validator.name}:\n"
                    f"  STDOUT: {result.stdout[:200]}\n"
                    f"  STDERR: {result.stderr[:200]}"
                )

        assert not failures, (
            f"Validation hooks failed after optimization:\n" +
            "\n\n".join(failures)
        )


class TestDocumentationSearchIntegration:
    """Test that search functionality works across all documentation."""

    def test_global_search_finds_all_agent_names(self):
        """
        Verify all 20 agent names are findable via global search.

        Simulates user searching for an agent name and finding it in
        either CLAUDE.md or AGENTS.md.
        """
        project_root = Path(__file__).parent.parent.parent

        # All searchable documentation
        search_paths = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "AGENTS.md",
        ]

        # Combine all searchable content
        combined_content = ""
        for path in search_paths:
            if path.exists():
                combined_content += path.read_text(encoding="utf-8")

        # All 20 agents should be findable
        agent_names = [
            "researcher", "planner", "test-master", "implementer", "reviewer",
            "security-auditor", "doc-master", "advisor", "quality-validator",
            "alignment-validator", "commit-message-generator", "pr-description-generator",
            "issue-creator", "brownfield-analyzer", "project-progress-tracker",
            "alignment-analyzer", "project-bootstrapper", "setup-wizard",
            "project-status-analyzer", "sync-validator"
        ]

        missing_agents = [
            agent for agent in agent_names
            if agent not in combined_content
        ]

        assert not missing_agents, (
            f"Agents not findable via search: {', '.join(missing_agents)}"
        )

    def test_global_search_finds_all_core_hooks(self):
        """
        Verify all 11 core hooks are findable via global search.

        Simulates user searching for a hook name and finding it in
        either CLAUDE.md or HOOKS.md.
        """
        project_root = Path(__file__).parent.parent.parent

        search_paths = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "HOOKS.md",
        ]

        combined_content = ""
        for path in search_paths:
            if path.exists():
                combined_content += path.read_text(encoding="utf-8")

        core_hooks = [
            "auto_format", "auto_test", "security_scan",
            "validate_project_alignment", "validate_claude_alignment",
            "enforce_file_organization", "enforce_pipeline_complete",
            "enforce_tdd", "detect_feature_request",
            "auto_git_workflow", "auto_approve_tool"
        ]

        missing_hooks = [
            hook for hook in core_hooks
            if hook not in combined_content
        ]

        assert not missing_hooks, (
            f"Hooks not findable via search: {', '.join(missing_hooks)}"
        )

    def test_global_search_finds_performance_phases(self):
        """
        Verify all performance phases are findable via global search.

        Simulates user searching for "Phase 4" and finding it in
        CLAUDE.md or PERFORMANCE-HISTORY.md.
        """
        project_root = Path(__file__).parent.parent.parent

        search_paths = [
            project_root / "CLAUDE.md",
            project_root / "docs" / "PERFORMANCE-HISTORY.md",
        ]

        combined_content = ""
        for path in search_paths:
            if path.exists():
                combined_content += path.read_text(encoding="utf-8")

        phases = ["Phase 4", "Phase 5", "Phase 6", "Phase 7", "Phase 8"]

        missing_phases = [
            phase for phase in phases
            if phase not in combined_content
        ]

        assert not missing_phases, (
            f"Performance phases not findable via search: {', '.join(missing_phases)}"
        )


class TestVersionControlIntegration:
    """Test that optimization works correctly with version control."""

    def test_all_new_docs_tracked_by_git(self):
        """
        Verify all new documentation files are tracked by git.

        After optimization, new docs should be committed to version control.
        """
        project_root = Path(__file__).parent.parent.parent

        new_docs = [
            "docs/PERFORMANCE-HISTORY.md",
            "docs/BATCH-PROCESSING.md",
            "docs/AGENTS.md",
            "docs/HOOKS.md",
        ]

        # Check git status
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch"] + new_docs,
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            # Files not tracked yet
            untracked = []
            for doc in new_docs:
                doc_path = project_root / doc
                if doc_path.exists():
                    untracked.append(doc)

            if untracked:
                pytest.fail(
                    f"New documentation files not tracked by git: {', '.join(untracked)}. "
                    f"Files should be added to version control."
                )

    def test_claude_md_modifications_preserve_git_history(self):
        """
        Verify CLAUDE.md optimization preserves git history.

        After optimization, git should show CLAUDE.md as modified (not deleted/recreated).
        """
        project_root = Path(__file__).parent.parent.parent

        # Check if CLAUDE.md exists in current commit
        result = subprocess.run(
            ["git", "log", "-1", "--name-only", "--", "CLAUDE.md"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        # CLAUDE.md should have git history
        assert result.returncode == 0, (
            "CLAUDE.md has no git history. "
            "File may have been deleted and recreated instead of modified."
        )

    def test_git_diff_shows_size_reduction(self):
        """
        Verify git diff shows CLAUDE.md size reduction.

        After optimization, git diff should show net deletion of lines.
        """
        project_root = Path(__file__).parent.parent.parent

        # Get current CLAUDE.md size
        claude_md = project_root / "CLAUDE.md"
        if not claude_md.exists():
            pytest.skip("CLAUDE.md not found")

        current_size = len(claude_md.read_text(encoding="utf-8"))

        # Check if CLAUDE.md was modified
        result = subprocess.run(
            ["git", "diff", "--cached", "--numstat", "CLAUDE.md"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            # No staged changes - check working tree
            result = subprocess.run(
                ["git", "diff", "--numstat", "CLAUDE.md"],
                cwd=str(project_root),
                capture_output=True,
                text=True
            )

        if result.stdout.strip():
            # Parse numstat: <added> <deleted> <filename>
            parts = result.stdout.strip().split()
            if len(parts) >= 2:
                added = int(parts[0]) if parts[0] != '-' else 0
                deleted = int(parts[1]) if parts[1] != '-' else 0

                # Should have more deletions than additions (net reduction)
                assert deleted > added, (
                    f"CLAUDE.md not reduced in size. "
                    f"Added {added} lines, deleted {deleted} lines. "
                    f"Should have net deletion."
                )


class TestEndToEndOptimizationWorkflow:
    """Test complete end-to-end optimization workflow."""

    def test_complete_optimization_workflow_succeeds(self):
        """
        Verify complete optimization workflow succeeds.

        This is the ultimate integration test that validates:
        1. CLAUDE.md reduced to <35K characters
        2. All 4 new docs created
        3. All content preserved and accessible
        4. All links resolve correctly
        5. All validation hooks pass
        6. Search functionality works
        7. Version control integration works

        This test will FAIL until ALL implementation phases complete.
        """
        project_root = Path(__file__).parent.parent.parent

        # Phase 1: Verify file existence
        claude_md = project_root / "CLAUDE.md"
        new_docs = [
            project_root / "docs" / "PERFORMANCE-HISTORY.md",
            project_root / "docs" / "BATCH-PROCESSING.md",
            project_root / "docs" / "AGENTS.md",
            project_root / "docs" / "HOOKS.md",
        ]

        assert claude_md.exists(), "CLAUDE.md not found"
        for doc in new_docs:
            assert doc.exists(), f"{doc.name} not created"

        # Phase 2: Verify size reduction
        claude_size = len(claude_md.read_text(encoding="utf-8"))
        assert claude_size < 35000, (
            f"CLAUDE.md not reduced: {claude_size:,} chars (target: <35,000)"
        )

        # Phase 3: Verify content preservation
        total_size = sum(
            len(path.read_text(encoding="utf-8"))
            for path in [claude_md] + new_docs
        )
        baseline = 41847
        assert total_size >= baseline * 0.9, (
            f"Content lost: {total_size:,} < {baseline:,} baseline"
        )

        # Phase 4: Verify links work
        for doc in [claude_md] + new_docs:
            content = doc.read_text(encoding="utf-8")
            links = re.findall(r'\[([^\]]+)\]\(([^\)]+\.md)\)', content)

            for link_text, link_url in links:
                if not link_url.startswith("http"):
                    target = (doc.parent / link_url).resolve()
                    assert target.exists(), f"Broken link in {doc.name}: {link_url}"

        # Phase 5: Verify validation passes
        validator = project_root / "plugins" / "autonomous-dev" / "hooks" / "validate_claude_alignment.py"
        if validator.exists():
            result = subprocess.run(
                ["python3", str(validator)],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30
            )
            assert result.returncode == 0, f"Validation failed: {result.stderr}"

        print("\n✅ Complete optimization workflow succeeded!")
        print(f"   CLAUDE.md: {claude_size:,} chars (<35,000 ✓)")
        print(f"   Total docs: {total_size:,} chars (preserved ✓)")
        print(f"   New docs: {len(new_docs)} created ✓")
        print(f"   Validation: passed ✓")


# Test execution summary
if __name__ == "__main__":
    print("=" * 80)
    print("CLAUDE.md Optimization - Integration Tests (Issue #78)")
    print("=" * 80)
    print()
    print("These tests validate the complete optimization workflow.")
    print()
    print("Integration Coverage:")
    print("  - End-to-end content extraction")
    print("  - Cross-document link resolution")
    print("  - Alignment validation integration")
    print("  - Documentation search integration")
    print("  - Version control integration")
    print("  - Complete workflow validation")
    print()
    print("Run with: pytest -xvs tests/integration/test_claude_md_optimization_workflow.py")
    print("=" * 80)
