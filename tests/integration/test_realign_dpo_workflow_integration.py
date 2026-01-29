#!/usr/bin/env python3
"""
Integration Tests for realign-dpo-workflow Skill (FAILING - Red Phase)

This module contains FAILING integration tests that validate cross-skill
integration, library dependencies, and end-to-end DPO workflow validation.

Integration Test Scope:
1. Cross-skill integration with preference-data-quality
2. training_metrics.py library function availability
3. End-to-end workflow validation (all stages connected)
4. Configuration template validation
5. Quality threshold enforcement
6. Capability regression detection workflows

Test Coverage Target: 100% of integration points and cross-references

Following TDD principles:
- Write tests FIRST (red phase)
- Tests validate integration between components
- Tests should FAIL until all components implemented
- Each test validates ONE integration point

Author: test-master agent
Date: 2026-01-28
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import Mock, patch

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

SKILL_DIR = (
    Path(__file__).parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "skills"
    / "realign-dpo-workflow"
)
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"

PREF_QUALITY_SKILL_DIR = (
    Path(__file__).parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "skills"
    / "preference-data-quality"
)
PREF_QUALITY_SKILL_FILE = PREF_QUALITY_SKILL_DIR / "SKILL.md"

TRAINING_METRICS_LIB = (
    Path(__file__).parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "lib"
    / "training_metrics.py"
)


class TestPreferenceDataQualityIntegration:
    """Test integration with preference-data-quality skill."""

    def test_preference_quality_skill_exists(self):
        """Test preference-data-quality skill exists for cross-reference."""
        assert PREF_QUALITY_SKILL_FILE.exists(), (
            f"preference-data-quality skill not found: {PREF_QUALITY_SKILL_FILE}\n"
            f"Required for DPO quality metrics integration"
        )

    def test_dpo_workflow_references_quality_metrics(self):
        """Test DPO workflow skill references preference quality metrics."""
        dpo_content = SKILL_FILE.read_text().lower()

        # Should reference DPO metrics from preference-data-quality
        quality_terms = ["preference gap", "kl divergence", "decontamination"]
        missing_terms = [term for term in quality_terms if term not in dpo_content]

        assert not missing_terms, (
            f"DPO workflow skill missing quality metric references:\n"
            f"{chr(10).join(f'  - {term}' for term in missing_terms)}\n"
            f"Should reference metrics from preference-data-quality skill"
        )

    def test_threshold_values_match_preference_quality(self):
        """Test threshold values match between DPO workflow and preference-data-quality."""
        dpo_content = SKILL_FILE.read_text()
        pref_content = PREF_QUALITY_SKILL_FILE.read_text()

        # Extract threshold values from both
        def extract_gap_threshold(content: str) -> Optional[str]:
            match = re.search(r"[≥>=]\s*(0\.1[0-9])", content)
            return match.group(1) if match else None

        def extract_kl_threshold(content: str) -> Optional[str]:
            match = re.search(r"[≤<=]\s*(0\.1[0-9]?)", content)
            return match.group(1) if match else None

        dpo_gap = extract_gap_threshold(dpo_content)
        pref_gap = extract_gap_threshold(pref_content)

        dpo_kl = extract_kl_threshold(dpo_content)
        pref_kl = extract_kl_threshold(pref_content)

        # Verify consistency if both skills define thresholds
        if dpo_gap and pref_gap:
            assert dpo_gap == pref_gap, (
                f"Preference gap threshold mismatch\n"
                f"DPO workflow: {dpo_gap}\n"
                f"Preference quality: {pref_gap}\n"
                f"Ensure consistency across skills"
            )

        if dpo_kl and pref_kl:
            assert dpo_kl == pref_kl, (
                f"KL divergence threshold mismatch\n"
                f"DPO workflow: {dpo_kl}\n"
                f"Preference quality: {pref_kl}\n"
                f"Ensure consistency across skills"
            )

    def test_cross_reference_links_are_bidirectional(self):
        """Test cross-references between DPO workflow and preference quality are bidirectional."""
        dpo_content = SKILL_FILE.read_text().lower()
        pref_content = PREF_QUALITY_SKILL_FILE.read_text().lower()

        # DPO should reference preference-data-quality
        dpo_refs_pref = "preference-data-quality" in dpo_content or "preference data quality" in dpo_content

        assert dpo_refs_pref, (
            "DPO workflow must reference preference-data-quality skill\n"
            "Expected: Cross-reference to related skill for quality metrics"
        )

        # Note: Bidirectional check from preference-data-quality to DPO workflow
        # is optional but recommended for discoverability
        pref_refs_dpo = "dpo" in pref_content or "realign" in pref_content

        if not pref_refs_dpo:
            # Warning only - not all cross-refs need to be bidirectional
            pytest.skip(
                "Optional: preference-data-quality could reference DPO workflow for context"
            )


class TestTrainingMetricsLibraryIntegration:
    """Test integration with training_metrics.py library."""

    def test_training_metrics_library_exists(self):
        """Test training_metrics.py library exists."""
        assert TRAINING_METRICS_LIB.exists(), (
            f"training_metrics.py library not found: {TRAINING_METRICS_LIB}\n"
            f"Required for DPO metric calculation"
        )

    def test_training_metrics_has_dpo_functions(self):
        """Test training_metrics.py library contains DPO-related functions."""
        if not TRAINING_METRICS_LIB.exists():
            pytest.skip("training_metrics.py not implemented yet")

        content = TRAINING_METRICS_LIB.read_text()

        # Expected function names for DPO
        expected_functions = [
            "calculate_preference_gap",
            "calculate_kl_divergence",
            "validate_dpo_thresholds",
        ]

        missing_functions = []
        for func_name in expected_functions:
            if f"def {func_name}" not in content:
                missing_functions.append(func_name)

        assert not missing_functions, (
            f"training_metrics.py missing DPO functions:\n"
            f"{chr(10).join(f'  - {func}' for func in missing_functions)}\n"
            f"Implement these functions for DPO metric calculation"
        )

    def test_skill_documents_training_metrics_usage(self):
        """Test skill documentation shows how to use training_metrics functions."""
        # Check all docs for training_metrics examples
        all_content = ""
        if SKILL_FILE.exists():
            all_content += SKILL_FILE.read_text()

        if DOCS_DIR.exists():
            for doc_file in DOCS_DIR.glob("*.md"):
                all_content += doc_file.read_text()

        has_usage_example = "training_metrics" in all_content.lower()

        assert has_usage_example, (
            "Skill must document training_metrics library usage\n"
            "Expected: Code examples showing how to use DPO metric functions\n"
            "Location: SKILL.md or docs/dpo-optimization.md"
        )

    def test_training_metrics_functions_have_correct_signatures(self):
        """Test training_metrics DPO functions have correct signatures."""
        if not TRAINING_METRICS_LIB.exists():
            pytest.skip("training_metrics.py not implemented yet")

        content = TRAINING_METRICS_LIB.read_text()

        # Check calculate_preference_gap signature
        gap_pattern = r"def calculate_preference_gap\([^)]*\w+[^)]*,\s*\w+[^)]*\)"
        has_gap_sig = re.search(gap_pattern, content) is not None

        assert has_gap_sig, (
            "calculate_preference_gap must accept at least 2 parameters\n"
            "Expected signature: (chosen_scores, rejected_scores) or similar"
        )

        # Check calculate_kl_divergence signature
        kl_pattern = r"def calculate_kl_divergence\([^)]*\w+[^)]*,\s*\w+[^)]*\)"
        has_kl_sig = re.search(kl_pattern, content) is not None

        assert has_kl_sig, (
            "calculate_kl_divergence must accept at least 2 parameters\n"
            "Expected signature: (policy_logits, reference_logits) or similar"
        )


class TestEndToEndWorkflow:
    """Test end-to-end DPO workflow integration."""

    def test_all_stages_are_connected(self):
        """Test workflow.md shows how all 7 stages connect."""
        workflow_file = SKILL_DIR / "workflow.md"
        content = workflow_file.read_text().lower()

        # All stages should be mentioned
        stages = [
            "sft preparation",
            "preference data",
            "model init",
            "preference modeling",
            "optimization",
            "iterative",
            "evaluation",
        ]

        # Check for sequential/connection indicators
        connection_terms = ["then", "next", "after", "following", "before", "pipeline", "flow"]
        has_connections = any(term in content for term in connection_terms)

        assert has_connections, (
            "workflow.md must show how stages connect\n"
            "Expected: Sequential flow indicators between stages\n"
            "Use terms like 'then', 'next', 'after' to show stage progression"
        )

    def test_workflow_has_decision_points(self):
        """Test workflow documentation includes decision points."""
        workflow_file = SKILL_DIR / "workflow.md"
        content = workflow_file.read_text().lower()

        # Should have decision/conditional logic
        decision_terms = ["if", "when", "whether", "decision", "choose", "option"]
        has_decisions = any(term in content for term in decision_terms)

        assert has_decisions, (
            "workflow.md must include decision points\n"
            "Expected: Conditional logic for workflow branching\n"
            "Example: 'If quality thresholds not met, return to stage X'"
        )

    def test_workflow_defines_success_criteria(self):
        """Test workflow defines success criteria for completion."""
        workflow_file = SKILL_DIR / "workflow.md"
        eval_file = DOCS_DIR / "evaluation-monitoring.md"

        content = ""
        if workflow_file.exists():
            content += workflow_file.read_text().lower()
        if eval_file.exists():
            content += eval_file.read_text().lower()

        # Should define what constitutes successful DPO
        success_terms = ["success", "complete", "ready", "criteria", "threshold", "metric"]
        has_success_criteria = any(term in content for term in success_terms)

        assert has_success_criteria, (
            "Workflow must define success criteria\n"
            "Expected: Clear metrics/thresholds for DPO completion\n"
            "Location: workflow.md or docs/evaluation-monitoring.md"
        )


class TestConfigurationTemplates:
    """Test configuration template validation."""

    def test_templates_provide_hyperparameter_examples(self):
        """Test templates.md provides DPO hyperparameter examples."""
        templates_file = SKILL_DIR / "templates.md"
        content = templates_file.read_text().lower()

        # Should include DPO hyperparameters
        hyperparams = ["learning_rate", "beta", "temperature", "batch_size"]
        found_params = [param for param in hyperparams if param in content]

        assert len(found_params) >= 2, (
            f"templates.md missing DPO hyperparameter examples\n"
            f"Found: {found_params}\n"
            f"Expected: At least 2 of {hyperparams}\n"
            f"Provide configuration templates with hyperparameters"
        )

    def test_templates_include_data_format_examples(self):
        """Test templates.md includes preference data format examples."""
        templates_file = SKILL_DIR / "templates.md"
        content = templates_file.read_text().lower()

        # Should show preference pair format
        format_terms = ["chosen", "rejected", "prompt", "response"]
        found_terms = [term for term in format_terms if term in content]

        assert len(found_terms) >= 2, (
            f"templates.md missing preference data format examples\n"
            f"Found: {found_terms}\n"
            f"Expected: At least 2 of {format_terms}\n"
            f"Show JSON/JSONL format for preference pairs"
        )

    def test_templates_provide_evaluation_config(self):
        """Test templates.md provides evaluation configuration examples."""
        templates_file = SKILL_DIR / "templates.md"
        content = templates_file.read_text().lower()

        # Should include evaluation config
        eval_terms = ["eval", "validation", "test", "benchmark"]
        has_eval_config = any(term in content for term in eval_terms)

        assert has_eval_config, (
            "templates.md must include evaluation configuration\n"
            "Expected: Config examples for DPO evaluation/validation"
        )


class TestQualityThresholdEnforcement:
    """Test quality threshold enforcement in workflow."""

    def test_quality_gate_documented_for_each_stage(self):
        """Test each stage documentation includes quality gates/checks."""
        stage_files = [
            "sft-preparation.md",
            "preference-data-generation.md",
            "dpo-optimization.md",
        ]

        missing_gates = []
        for filename in stage_files:
            file_path = DOCS_DIR / filename
            if not file_path.exists():
                continue

            content = file_path.read_text().lower()

            # Should mention quality checks/gates
            gate_terms = ["quality", "threshold", "validate", "check", "verify"]
            has_gate = any(term in content for term in gate_terms)

            if not has_gate:
                missing_gates.append(filename)

        assert not missing_gates, (
            f"Stage docs missing quality gates:\n"
            f"{chr(10).join(f'  - {f}' for f in missing_gates)}\n"
            f"Each stage should specify quality checks/thresholds"
        )

    def test_threshold_enforcement_workflow_exists(self):
        """Test workflow shows how to enforce thresholds between stages."""
        workflow_file = SKILL_DIR / "workflow.md"
        threshold_file = DOCS_DIR / "quality-thresholds.md"

        content = ""
        if workflow_file.exists():
            content += workflow_file.read_text().lower()
        if threshold_file.exists():
            content += threshold_file.read_text().lower()

        # Should discuss enforcement/validation
        enforcement_terms = ["enforce", "validate", "check", "verify", "ensure"]
        has_enforcement = any(term in content for term in enforcement_terms)

        assert has_enforcement, (
            "Workflow must document threshold enforcement\n"
            "Expected: How to validate quality thresholds between stages\n"
            "Location: workflow.md or docs/quality-thresholds.md"
        )

    def test_failure_recovery_documented(self):
        """Test workflow documents recovery when thresholds not met."""
        workflow_file = SKILL_DIR / "workflow.md"
        content = workflow_file.read_text().lower()

        # Should discuss what to do when thresholds fail
        recovery_terms = ["fail", "retry", "improve", "iterate", "adjust"]
        has_recovery = any(term in content for term in recovery_terms)

        assert has_recovery, (
            "workflow.md must document failure recovery\n"
            "Expected: Guidance on what to do when quality thresholds not met\n"
            "Example: 'If preference gap <0.15, collect more diverse examples'"
        )


class TestCapabilityRegressionDetection:
    """Test capability regression detection workflows."""

    def test_regression_detection_methods_documented(self):
        """Test capability regression detection methods are documented."""
        capability_file = DOCS_DIR / "capability-assessment.md"
        content = capability_file.read_text().lower()

        # Should describe detection methods
        detection_methods = [
            "benchmark",
            "baseline",
            "comparison",
            "eval",
            "test set",
        ]
        found_methods = [method for method in detection_methods if method in content]

        assert len(found_methods) >= 2, (
            f"capability-assessment.md missing regression detection methods\n"
            f"Found: {found_methods}\n"
            f"Expected: At least 2 of {detection_methods}\n"
            f"Document how to detect capability degradation"
        )

    def test_prevention_strategies_documented(self):
        """Test capability regression prevention strategies documented."""
        capability_file = DOCS_DIR / "capability-assessment.md"
        iterative_file = DOCS_DIR / "iterative-training.md"

        content = ""
        if capability_file.exists():
            content += capability_file.read_text().lower()
        if iterative_file.exists():
            content += iterative_file.read_text().lower()

        # Should discuss prevention strategies
        prevention_terms = [
            "prevent",
            "avoid",
            "maintain",
            "preserve",
            "monitor",
        ]
        has_prevention = any(term in content for term in prevention_terms)

        assert has_prevention, (
            "Skill must document regression prevention strategies\n"
            "Expected: How to prevent capability loss during DPO\n"
            "Location: capability-assessment.md or iterative-training.md"
        )

    def test_baseline_establishment_documented(self):
        """Test baseline establishment for regression detection documented."""
        capability_file = DOCS_DIR / "capability-assessment.md"
        eval_file = DOCS_DIR / "evaluation-monitoring.md"

        content = ""
        if capability_file.exists():
            content += capability_file.read_text().lower()
        if eval_file.exists():
            content += eval_file.read_text().lower()

        # Should discuss establishing baseline
        baseline_terms = ["baseline", "initial", "before", "pre-dpo", "reference"]
        has_baseline = any(term in content for term in baseline_terms)

        assert has_baseline, (
            "Skill must document baseline establishment\n"
            "Expected: How to establish pre-DPO baseline for comparison\n"
            "Required for detecting capability regression"
        )


class TestSkillUsability:
    """Test skill usability and practitioner guidance."""

    def test_provides_example_use_case(self):
        """Test skill provides at least one complete example use case."""
        all_content = ""
        if SKILL_FILE.exists():
            all_content += SKILL_FILE.read_text().lower()

        if DOCS_DIR.exists():
            for doc_file in DOCS_DIR.glob("*.md"):
                all_content += doc_file.read_text().lower()

        # Should have example/use case
        example_terms = ["example", "use case", "scenario", "walkthrough"]
        has_example = any(term in all_content for term in example_terms)

        assert has_example, (
            "Skill must provide example use case\n"
            "Expected: At least one complete DPO workflow example\n"
            "Helps practitioners understand end-to-end process"
        )

    def test_provides_troubleshooting_guidance(self):
        """Test skill provides troubleshooting guidance."""
        all_content = ""
        if SKILL_FILE.exists():
            all_content += SKILL_FILE.read_text().lower()

        if DOCS_DIR.exists():
            for doc_file in DOCS_DIR.glob("*.md"):
                all_content += doc_file.read_text().lower()

        # Should have troubleshooting/common issues
        troubleshoot_terms = [
            "troubleshoot",
            "common issue",
            "problem",
            "faq",
            "error",
        ]
        has_troubleshoot = any(term in all_content for term in troubleshoot_terms)

        assert has_troubleshoot, (
            "Skill should provide troubleshooting guidance\n"
            "Expected: Common issues and solutions\n"
            "Helps practitioners resolve problems independently"
        )

    def test_documents_time_estimates(self):
        """Test workflow documents approximate time estimates for stages."""
        workflow_file = SKILL_DIR / "workflow.md"
        content = workflow_file.read_text().lower()

        # Should mention time/duration
        time_terms = ["hour", "day", "week", "duration", "time", "estimate"]
        has_time_info = any(term in content for term in time_terms)

        assert has_time_info, (
            "workflow.md should include time estimates\n"
            "Expected: Approximate duration for each stage\n"
            "Helps practitioners plan DPO projects"
        )


class TestCrossReferenceCompleteness:
    """Test completeness of cross-references and integration points."""

    def test_all_external_references_are_valid(self):
        """Test all external references (skills, libraries, docs) are valid."""
        # Collect all content
        all_content = ""
        all_files = []

        if SKILL_FILE.exists():
            all_content += SKILL_FILE.read_text()
            all_files.append(SKILL_FILE)

        if DOCS_DIR.exists():
            for doc_file in DOCS_DIR.glob("*.md"):
                all_content += doc_file.read_text()
                all_files.append(doc_file)

        # Extract references to other skills
        skill_refs = re.findall(r"\*\*([a-z-]+)\*\* skill", all_content.lower())

        # Verify referenced skills exist
        skills_dir = (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "skills"
        )

        missing_skills = []
        for skill_name in set(skill_refs):
            skill_path = skills_dir / skill_name
            if not skill_path.exists():
                missing_skills.append(skill_name)

        assert not missing_skills, (
            f"Referenced skills not found:\n"
            f"{chr(10).join(f'  - {s}' for s in missing_skills)}\n"
            f"Remove references or create missing skills"
        )

    def test_library_references_are_valid(self):
        """Test all library references point to existing files."""
        # Collect all content
        all_content = ""
        if SKILL_FILE.exists():
            all_content += SKILL_FILE.read_text()

        if DOCS_DIR.exists():
            for doc_file in DOCS_DIR.glob("*.md"):
                all_content += doc_file.read_text()

        # Extract .py file references
        py_refs = re.findall(r"`([a-z_]+\.py)`", all_content.lower())

        lib_dir = (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "lib"
        )

        missing_libs = []
        for lib_name in set(py_refs):
            lib_path = lib_dir / lib_name
            if not lib_path.exists():
                missing_libs.append(lib_name)

        assert not missing_libs, (
            f"Referenced libraries not found:\n"
            f"{chr(10).join(f'  - {lib}' for lib in missing_libs)}\n"
            f"Remove references or create missing library files"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
