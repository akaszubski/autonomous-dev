#!/usr/bin/env python3
"""
TDD Tests for state-management-patterns Skill (FAILING - Red Phase)

This module contains FAILING tests for the state-management-patterns skill that will
extract duplicated state management code from libraries with persistent state
(Issue #78 Phase 8.8).

Skill Requirements:
1. YAML frontmatter with name, type, description, keywords, auto_activate
2. Progressive disclosure architecture (metadata in frontmatter, content loads on-demand)
3. Standardized state management patterns:
   - JSON persistence with atomic writes
   - File locking for concurrent access
   - State validation and recovery
   - Migration/upgrade paths
   - Crash recovery
4. Example state managers and patterns (examples/ directory)
5. Token reduction: ~40-50 tokens per library × 10 libraries = ~400-500 tokens

Test Coverage Target: 25 tests (SKILL.md format, patterns, examples, library integration)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and library integration
- Tests should FAIL until skill file and library updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-16
Issue: #78 Phase 8.8
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import re

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "state-management-patterns"
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"
EXAMPLES_DIR = SKILL_DIR / "examples"
TEMPLATES_DIR = SKILL_DIR / "templates"
LIB_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"


class TestSkillCreation:
    """Test state-management-patterns skill file structure and metadata."""

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in skills/state-management-patterns/ directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create skills/state-management-patterns/SKILL.md\n"
            f"See: Issue #78 Phase 8.8"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: state-management-patterns\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Validate required fields
        assert frontmatter.get("name") == "state-management-patterns", (
            "Skill name must be 'state-management-patterns'"
        )
        assert frontmatter.get("type") == "knowledge", (
            "Skill type must be 'knowledge'"
        )
        assert "description" in frontmatter, (
            "Skill must have 'description' field"
        )
        assert "keywords" in frontmatter, (
            "Skill must have 'keywords' field for auto-activation"
        )
        assert frontmatter.get("auto_activate") is True, (
            "Skill must have 'auto_activate: true' for progressive disclosure"
        )

    def test_skill_keywords_cover_state_terms(self):
        """Test skill keywords include state management terms."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", "")
        if isinstance(keywords, list):
            keywords = " ".join(keywords)

        expected_keywords = [
            "state", "persistence", "json", "atomic",
            "file lock", "recovery", "migration", "crash"
        ]

        for keyword in expected_keywords:
            assert keyword.lower() in keywords.lower(), (
                f"Skill keywords must include '{keyword}' for auto-activation\n"
                f"Current keywords: {keywords}"
            )

    def test_skill_defines_json_persistence(self):
        """Test skill defines JSON persistence pattern."""
        content = SKILL_FILE.read_text()

        assert "json" in content.lower() and "persist" in content.lower(), (
            "Skill must define JSON persistence pattern\n"
            "Expected: Save/load state to JSON files\n"
            "Example: batch_state.json, user_state.json\n"
            "Benefits: Human-readable, schema validation"
        )

    def test_skill_defines_atomic_writes(self):
        """Test skill defines atomic write pattern."""
        content = SKILL_FILE.read_text()

        assert "atomic" in content.lower(), (
            "Skill must define atomic write pattern\n"
            "Expected: Write to temp file → rename to target\n"
            "Example: write to .tmp → os.replace() → atomic\n"
            "Benefits: Prevents corruption on crash/interrupt"
        )

    def test_skill_defines_file_locking(self):
        """Test skill defines file locking pattern."""
        content = SKILL_FILE.read_text()

        assert "lock" in content.lower() or "concurrent" in content.lower(), (
            "Skill must define file locking pattern\n"
            "Expected: fcntl.flock() or portalocker for concurrent access\n"
            "Example: Lock before read/modify/write cycle\n"
            "Benefits: Prevents race conditions in multi-process scenarios"
        )

    def test_skill_defines_state_validation(self):
        """Test skill defines state validation pattern."""
        content = SKILL_FILE.read_text()

        assert "validation" in content.lower() or "schema" in content.lower(), (
            "Skill must define state validation pattern\n"
            "Expected: Validate state structure before loading\n"
            "Example: Required fields, type checking, version compatibility\n"
            "Benefits: Detect corruption, prevent invalid state"
        )

    def test_skill_defines_crash_recovery(self):
        """Test skill defines crash recovery pattern."""
        content = SKILL_FILE.read_text()

        assert "crash" in content.lower() or "recovery" in content.lower(), (
            "Skill must define crash recovery pattern\n"
            "Expected: Resume from last known good state\n"
            "Example: batch_state_manager.py --resume\n"
            "Benefits: Resilience, resume interrupted operations"
        )

    def test_skill_defines_migration_paths(self):
        """Test skill defines state migration pattern."""
        content = SKILL_FILE.read_text()

        assert "migration" in content.lower() or "upgrade" in content.lower(), (
            "Skill must define state migration pattern\n"
            "Expected: Versioned state with upgrade logic\n"
            "Example: v1 state → v2 state transformation\n"
            "Benefits: Backward compatibility, schema evolution"
        )


class TestSkillDocumentation:
    """Test state-management-patterns skill documentation structure."""

    def test_docs_directory_exists(self):
        """Test docs/ directory exists with detailed pattern documentation."""
        assert DOCS_DIR.exists(), (
            f"Documentation directory not found: {DOCS_DIR}\n"
            f"Expected: Create skills/state-management-patterns/docs/\n"
            f"Purpose: Detailed pattern documentation"
        )

    def test_json_persistence_doc_exists(self):
        """Test json-persistence.md documentation exists."""
        doc_file = DOCS_DIR / "json-persistence.md"
        assert doc_file.exists(), (
            f"JSON persistence doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of JSON state management\n"
            f"Should include: Save/load patterns, schema validation, examples"
        )

    def test_atomic_writes_doc_exists(self):
        """Test atomic-writes.md documentation exists."""
        doc_file = DOCS_DIR / "atomic-writes.md"
        assert doc_file.exists(), (
            f"Atomic writes doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of atomic write pattern\n"
            f"Should include: Temp file strategy, os.replace(), error handling"
        )

    def test_file_locking_doc_exists(self):
        """Test file-locking.md documentation exists."""
        doc_file = DOCS_DIR / "file-locking.md"
        assert doc_file.exists(), (
            f"File locking doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of concurrent access patterns\n"
            f"Should include: fcntl.flock(), portalocker, deadlock prevention"
        )

    def test_crash_recovery_doc_exists(self):
        """Test crash-recovery.md documentation exists."""
        doc_file = DOCS_DIR / "crash-recovery.md"
        assert doc_file.exists(), (
            f"Crash recovery doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of recovery strategies\n"
            f"Should include: Resume patterns, state validation, rollback"
        )


class TestSkillTemplates:
    """Test state-management-patterns skill provides code templates."""

    def test_templates_directory_exists(self):
        """Test templates/ directory exists with reusable templates."""
        assert TEMPLATES_DIR.exists(), (
            f"Templates directory not found: {TEMPLATES_DIR}\n"
            f"Expected: Create skills/state-management-patterns/templates/\n"
            f"Purpose: Reusable state manager templates"
        )

    def test_state_manager_template_exists(self):
        """Test state-manager-template.py exists with full implementation."""
        template_file = TEMPLATES_DIR / "state-manager-template.py"
        assert template_file.exists(), (
            f"State manager template not found: {template_file}\n"
            f"Expected: Template showing load/save/validate/resume methods\n"
            f"Should include: JSON persistence, atomic writes, validation"
        )

    def test_atomic_write_template_exists(self):
        """Test atomic-write-template.py exists with atomic write pattern."""
        template_file = TEMPLATES_DIR / "atomic-write-template.py"
        assert template_file.exists(), (
            f"Atomic write template not found: {template_file}\n"
            f"Expected: Template showing temp file + os.replace() pattern\n"
            f"Should include: Error handling, cleanup, permissions"
        )

    def test_file_lock_template_exists(self):
        """Test file-lock-template.py exists with locking pattern."""
        template_file = TEMPLATES_DIR / "file-lock-template.py"
        assert template_file.exists(), (
            f"File lock template not found: {template_file}\n"
            f"Expected: Template showing fcntl.flock() or portalocker usage\n"
            f"Should include: Context manager, timeout, error handling"
        )


class TestSkillExamples:
    """Test state-management-patterns skill provides example implementations."""

    def test_examples_directory_exists(self):
        """Test examples/ directory exists with real-world examples."""
        assert EXAMPLES_DIR.exists(), (
            f"Examples directory not found: {EXAMPLES_DIR}\n"
            f"Expected: Create skills/state-management-patterns/examples/\n"
            f"Purpose: Real-world state management examples"
        )

    def test_batch_state_example_exists(self):
        """Test batch-state-example.py shows batch state management."""
        example_file = EXAMPLES_DIR / "batch-state-example.py"
        assert example_file.exists(), (
            f"Batch state example not found: {example_file}\n"
            f"Expected: Example based on batch_state_manager.py\n"
            f"Should include: Load, save, resume, auto-clear logic"
        )

    def test_user_state_example_exists(self):
        """Test user-state-example.py shows user preferences persistence."""
        example_file = EXAMPLES_DIR / "user-state-example.py"
        assert example_file.exists(), (
            f"User state example not found: {example_file}\n"
            f"Expected: Example based on user_state_manager.py\n"
            f"Should include: Consent tracking, preferences, migration"
        )

    def test_crash_recovery_example_exists(self):
        """Test crash-recovery-example.py shows resume logic."""
        example_file = EXAMPLES_DIR / "crash-recovery-example.py"
        assert example_file.exists(), (
            f"Crash recovery example not found: {example_file}\n"
            f"Expected: Example showing --resume flag implementation\n"
            f"Should include: State validation, index tracking, retry logic"
        )


class TestLibraryIntegration:
    """Test libraries with persistent state reference skill."""

    LIBRARIES_USING_SKILL = [
        "batch_state_manager.py",
        "user_state_manager.py",
        "checkpoint.py",
        "session_tracker.py",
        "performance_profiler.py",
        "agent_invoker.py",  # If it has state
        "artifacts.py",  # If it has state
        "auto_approval_consent.py",  # If it has state
        "plugin_updater.py",  # Backup state
        "migration_planner.py",  # Migration state
    ]

    @pytest.mark.parametrize("library_file", LIBRARIES_USING_SKILL)
    def test_library_has_skill_reference(self, library_file):
        """Test library has comment referencing state-management-patterns skill."""
        library_path = LIB_DIR / library_file

        # Skip if library doesn't exist yet
        if not library_path.exists():
            pytest.skip(f"Library {library_file} not yet created")

        content = library_path.read_text()

        # Check for skill reference in module docstring
        assert "state-management-patterns" in content.lower(), (
            f"Library {library_file} must reference 'state-management-patterns' skill\n"
            f"Expected: Add to module docstring or state manager class\n"
            f"Format: See state-management-patterns skill for JSON persistence patterns\n"
            f"See: Issue #78 Phase 8.8"
        )

    def test_total_library_count_using_skill(self):
        """Test at least 10 libraries use state-management-patterns skill."""
        count = 0
        for library_file in self.LIBRARIES_USING_SKILL:
            library_path = LIB_DIR / library_file
            if library_path.exists():
                content = library_path.read_text()
                if "state-management-patterns" in content.lower():
                    count += 1

        assert count >= 10, (
            f"Expected at least 10 libraries to reference state-management-patterns skill, found {count}\n"
            f"Target: All libraries with persistent state\n"
            f"See: Issue #78 Phase 8.8"
        )


class TestStateManagementPatterns:
    """Test specific state management patterns defined in skill."""

    def test_skill_documents_state_versioning(self):
        """Test skill documents state versioning pattern."""
        content = SKILL_FILE.read_text()

        assert "version" in content.lower(), (
            "Skill must document state versioning pattern\n"
            "Expected: Version field in state JSON\n"
            "Example: {\"version\": \"1.0.0\", \"data\": {...}}\n"
            "Benefits: Schema evolution, migration paths"
        )

    def test_skill_documents_required_fields(self):
        """Test skill documents required fields validation."""
        content = SKILL_FILE.read_text()

        assert "required" in content.lower() or "mandatory" in content.lower(), (
            "Skill must document required fields validation\n"
            "Expected: Check for mandatory fields before using state\n"
            "Example: Validate 'batch_id', 'features', 'current_index' exist\n"
            "Benefits: Prevent errors from incomplete state"
        )

    def test_skill_documents_default_values(self):
        """Test skill documents default value pattern."""
        content = SKILL_FILE.read_text()

        assert "default" in content.lower(), (
            "Skill must document default value pattern\n"
            "Expected: Provide sensible defaults for missing fields\n"
            "Example: current_index defaults to 0 if not found\n"
            "Benefits: Graceful handling of incomplete state"
        )

    def test_skill_documents_state_cleanup(self):
        """Test skill documents state cleanup pattern."""
        content = SKILL_FILE.read_text()

        assert "cleanup" in content.lower() or "delete" in content.lower(), (
            "Skill must document state cleanup pattern\n"
            "Expected: Remove state files after successful completion\n"
            "Example: Delete batch_state.json when all features done\n"
            "Benefits: Prevent stale state accumulation"
        )


class TestTokenSavings:
    """Test token reduction from skill extraction."""

    def test_token_reduction_per_library(self):
        """Test each library saves ~40-50 tokens by using skill reference."""
        # Expected savings calculation:
        # Before: ~80-100 tokens for inline state management docs
        # After: ~30-40 tokens for skill reference
        # Savings: ~40-50 tokens per library

        pytest.skip(
            "Token counting requires implementation\n"
            "Expected: Use tiktoken or similar to count tokens\n"
            "Baseline: Measure tokens before/after skill extraction\n"
            "Target: 40-50 tokens saved per library"
        )

    def test_total_token_reduction(self):
        """Test total token savings across all state-management libraries."""
        # Expected total savings: 45 tokens × 10 libraries = 450 tokens

        pytest.skip(
            "Token counting requires implementation\n"
            "Expected: Aggregate token savings across all libraries\n"
            "Target: 400-500 tokens total reduction\n"
            "See: Issue #78 Phase 8.8"
        )


class TestProgressiveDisclosure:
    """Test progressive disclosure functionality."""

    def test_skill_metadata_small_for_context(self):
        """Test skill metadata (frontmatter) is small enough to keep in context."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = parts[1]

        # Frontmatter should be < 200 tokens (very rough estimate: ~4 chars per token)
        assert len(frontmatter) < 800, (
            f"Skill frontmatter too large: {len(frontmatter)} chars\n"
            f"Expected: < 800 chars (~200 tokens) for efficient context usage\n"
            f"Progressive disclosure keeps metadata small, loads full content on-demand"
        )

    def test_skill_full_content_loads_on_demand(self):
        """Test skill full content (after frontmatter) is available when needed."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)

        assert len(parts) >= 3, "Skill must have content after frontmatter"

        full_content = parts[2]

        # Full content should have detailed state management patterns
        assert len(full_content) > 1500, (
            f"Skill content too small: {len(full_content)} chars\n"
            f"Expected: Detailed state management patterns, examples, templates\n"
            f"Progressive disclosure: Metadata always loaded, content loaded when keywords match"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
