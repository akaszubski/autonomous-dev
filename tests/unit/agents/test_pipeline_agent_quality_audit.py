"""Tests for Issue #366: Pipeline agent quality audit fixes.

Validates that all pipeline agents have proper HARD GATEs, correct models,
structured output, and quality enforcement.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENTS_DIR = PROJECT_ROOT / "plugins/autonomous-dev/agents"


class TestResearcherAgent:
    """researcher.md: haiku→sonnet, structured output, HARD GATE."""

    def setup_method(self):
        self.content = (AGENTS_DIR / "researcher.md").read_text()

    def test_model_is_sonnet(self):
        """Researcher must use sonnet model (not haiku)."""
        assert "model: sonnet" in self.content
        assert "model: haiku" not in self.content

    def test_structured_json_output(self):
        """Researcher must output structured JSON."""
        assert '"findings"' in self.content or "```json" in self.content

    def test_hard_gate_on_websearch(self):
        """Researcher MUST use WebSearch — HARD GATE."""
        content_lower = self.content.lower()
        assert "hard gate" in content_lower
        assert "WebSearch" in self.content

    def test_forbidden_list_exists(self):
        """Researcher must have FORBIDDEN behaviors."""
        assert "FORBIDDEN" in self.content


class TestReviewerAgent:
    """reviewer.md: FORBIDDEN to APPROVE if tests fail."""

    def setup_method(self):
        self.content = (AGENTS_DIR / "reviewer.md").read_text()

    def test_forbidden_approve_on_test_failure(self):
        """Reviewer FORBIDDEN to APPROVE if tests fail."""
        assert "FORBIDDEN" in self.content
        # Must mention not approving when tests fail
        assert "APPROVE" in self.content
        assert "fail" in self.content.lower()

    def test_must_cite_lines(self):
        """Reviewer must cite specific file:line locations."""
        assert "file:" in self.content.lower() or "line" in self.content.lower()

    def test_hard_gate_exists(self):
        """Reviewer must have HARD GATE."""
        assert "HARD GATE" in self.content

    def test_minimum_file_read_requirement_section(self):
        """Reviewer must have Minimum File Read Requirement HARD GATE (Issue #659)."""
        assert "Minimum File Read Requirement" in self.content

    def test_required_tool_actions_language(self):
        """Reviewer must have REQUIRED TOOL ACTIONS section (Issue #659)."""
        assert "REQUIRED TOOL ACTIONS" in self.content

    def test_forbidden_zero_tool_uses(self):
        """Reviewer FORBIDDEN to issue verdict with 0 tool uses (Issue #659)."""
        assert "0 tool uses" in self.content

    def test_minimum_tool_use_thresholds(self):
        """Reviewer must define minimum tool use thresholds (Issue #659)."""
        assert "Minimum tool use thresholds" in self.content
        # Verify specific thresholds exist
        assert "1-50 lines changed" in self.content
        assert "51-200 lines changed" in self.content
        assert "200+ lines changed" in self.content

    def test_forbidden_ghost_review(self):
        """Reviewer FORBIDDEN to issue APPROVE with 0 tool uses in main FORBIDDEN list (Issue #659)."""
        # This checks the entry in the main FORBIDDEN list (not just the section-local one)
        assert "MUST NOT issue any verdict (APPROVE or REQUEST_CHANGES) with 0 tool uses" in self.content

    def test_1010_write_path_completeness_section_present(self):
        """Reviewer must have Write-Path Completeness section (Issue #1010).

        New Pydantic schema fields must be traced through API route → service
        layer → ORM model to prevent silent-discard bugs.
        """
        assert "Write-Path Completeness" in self.content, (
            "reviewer.md must include the Write-Path Completeness section so "
            "reviewers explicitly check API handler → service → ORM wiring "
            "for new schema fields (#1010)."
        )
        # The 4 numbered steps must all be present.
        assert "Identify the API route handler" in self.content
        assert "Identify the service layer method" in self.content
        assert "Identify the ORM model" in self.content
        assert "one-line proof" in self.content

    def test_1010_silent_discard_blocking_severity(self):
        """Write-Path Completeness gaps must be marked as BLOCKING findings (#1010).

        If a field reaches validation but never makes it to a service-layer
        write, the field is silently discarded — that is a behavioral bug,
        not a style nit, so it MUST be BLOCKING severity.
        """
        assert "silent discard" in self.content, (
            "reviewer.md must call out 'silent discard' so reviewers recognise "
            "the field-validated-but-not-persisted bug class (#1010)."
        )
        assert "BLOCKING finding" in self.content, (
            "reviewer.md must mark write-path gaps as BLOCKING severity (#1010)."
        )

    def test_1108_missing_pytest_artifact_finding_category(self):
        """Reviewer must define a missing-pytest-artifact finding category (Issue #1108).

        When REQUEST_CHANGES is issued solely because the coordinator did not
        embed pytest output, the finding must be structured so the coordinator
        can detect the process-gap and re-dispatch with test results rather
        than spinning up the implementer remediation loop.
        """
        assert "missing-pytest-artifact" in self.content, (
            "reviewer.md must define the 'missing-pytest-artifact' finding "
            "category so the coordinator can distinguish process-gap from "
            "code-defect REQUEST_CHANGES verdicts (#1108)."
        )
        assert "Coordinator must embed pytest output" in self.content, (
            "reviewer.md must specify the coordinator's required corrective "
            "action when test artifact is missing (#1108)."
        )
        assert "process-gap" in self.content, (
            "reviewer.md must label missing-artifact findings as a process-gap "
            "signal so the coordinator can route them appropriately (#1108)."
        )


class TestDocMasterAgent:
    """doc-master.md: haiku→sonnet, semantic guidance, GenAI gate."""

    def setup_method(self):
        self.content = (AGENTS_DIR / "doc-master.md").read_text()

    def test_model_is_sonnet(self):
        """Doc-master must use sonnet model (not haiku)."""
        assert "model: sonnet" in self.content
        assert "model: haiku" not in self.content

    def test_semantic_readme_guidance(self):
        """Doc-master must have semantic update guidance."""
        content_lower = self.content.lower()
        assert "semantic" in content_lower

    def test_genai_validation_hard_gate(self):
        """Doc-master must have GenAI validation HARD GATE."""
        assert "HARD GATE" in self.content
        content_lower = self.content.lower()
        assert "genai" in content_lower or "congruence" in content_lower


class TestSecurityAuditorAgent:
    """security-auditor.md: systematic OWASP checklist, FORBIDDEN."""

    def setup_method(self):
        self.content = (AGENTS_DIR / "security-auditor.md").read_text()

    def test_forbidden_pass_without_owasp(self):
        """Security auditor FORBIDDEN to PASS without OWASP check."""
        assert "FORBIDDEN" in self.content
        assert "OWASP" in self.content

    def test_systematic_checklist(self):
        """Must have systematic OWASP checklist (not just mention)."""
        # Should have multiple OWASP categories listed
        owasp_categories = [
            "Injection", "Authentication", "Access Control",
            "Cryptographic", "Security Misconfiguration"
        ]
        found = sum(1 for cat in owasp_categories if cat in self.content)
        assert found >= 3, f"Only {found}/5 OWASP categories found in checklist"

    def test_hard_gate_exists(self):
        """Security auditor must have HARD GATE."""
        assert "HARD GATE" in self.content


class TestPlannerAgent:
    """planner.md: FORBIDDEN Out of Scope, acceptance criteria output."""

    def setup_method(self):
        self.content = (AGENTS_DIR / "planner.md").read_text()

    def test_forbidden_out_of_scope(self):
        """Planner FORBIDDEN to proceed with Out of Scope features."""
        assert "FORBIDDEN" in self.content
        assert "Out of Scope" in self.content or "out of scope" in self.content.lower()

    def test_acceptance_criteria_output(self):
        """Planner must output acceptance criteria."""
        content_lower = self.content.lower()
        assert "acceptance criteria" in content_lower

    def test_hard_gate_exists(self):
        """Planner must have HARD GATE for scope."""
        assert "HARD GATE" in self.content

    def test_minimum_scope_hard_gate_exists(self):
        """Planner must have HARD GATE: Minimum Scope section (Issue #1006)."""
        assert "HARD GATE: Minimum Scope" in self.content

    def test_minimum_scope_forbidden_over_build(self):
        """Planner must FORBID adding components beyond AC scope (Issue #1006)."""
        assert "FORBIDDEN" in self.content
        assert "minimum" in self.content.lower()
        assert "acceptance criterion" in self.content or "acceptance criteria" in self.content.lower()


class TestImplementerAgent:
    """implementer.md: HARD GATEs for skips, stubs, hooks, and path depth."""

    def setup_method(self):
        self.content = (AGENTS_DIR / "implementer.md").read_text()

    def test_hard_gate_path_depth_verification_exists(self):
        """Implementer must have Path Depth Verification HARD GATE (Issue #694)."""
        assert "HARD GATE: Path Depth Verification" in self.content

    def test_path_depth_verification_method(self):
        """Path depth section must include verification method with examples."""
        assert "parents[1]" in self.content
        assert "parents[2]" in self.content
        assert "parents[3]" in self.content

    def test_path_depth_forbidden_list(self):
        """Path depth section must forbid using parents[N] without counting."""
        assert "without counting directory levels" in self.content

    def test_path_depth_double_nested_forbidden(self):
        """Path depth section must forbid double-nested directories (Issue #694)."""
        assert "double-nested directories" in self.content

    def test_hard_gate_no_new_skips(self):
        """Implementer must have No New Skips HARD GATE."""
        assert "HARD GATE: No New Skips" in self.content

    def test_hard_gate_regression_test_for_bug_fixes(self):
        """Implementer must have Regression Test for Bug Fixes HARD GATE."""
        assert "HARD GATE: Regression Test for Bug Fixes" in self.content

    def test_hard_gate_hook_registration(self):
        """Implementer must have Hook Registration Verification HARD GATE."""
        assert "HARD GATE: Hook Registration Verification" in self.content

    def test_forbidden_list_exists(self):
        """Implementer must have FORBIDDEN behaviors."""
        assert "FORBIDDEN" in self.content


class TestResearcherLocalAgent:
    """researcher-local.md: HARD GATE on empty results."""

    def setup_method(self):
        self.content = (AGENTS_DIR / "researcher-local.md").read_text()

    def test_hard_gate_on_empty_results(self):
        """Researcher-local HARD GATE on empty/no results."""
        assert "HARD GATE" in self.content
        content_lower = self.content.lower()
        assert "empty" in content_lower or "no results" in content_lower or "0 patterns" in content_lower

    def test_forbidden_list_exists(self):
        """Researcher-local must have FORBIDDEN behaviors."""
        assert "FORBIDDEN" in self.content
