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
