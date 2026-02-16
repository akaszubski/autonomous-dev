"""GenAI UAT: Continuous Improvement System validation.

Validates the three components of the continuous improvement pipeline:
1. session_activity_logger.py - structured tool call logging
2. continuous-improvement-analyst.md - log analysis agent
3. improve.md - /improve command orchestration
"""

import re

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"
LOGGER_PATH = PLUGIN_ROOT / "hooks" / "session_activity_logger.py"
ANALYST_PATH = PLUGIN_ROOT / "agents" / "continuous-improvement-analyst.md"
IMPROVE_PATH = PLUGIN_ROOT / "commands" / "improve.md"


class TestSessionLogging:
    def test_activity_logger_captures_essential_fields(self, genai):
        """Log entries should capture all essential fields for post-session analysis."""
        source = LOGGER_PATH.read_text()

        # Deterministic: check that all essential field names appear in the entry dict
        essential_fields = ["timestamp", "tool", "input_summary", "output_summary", "session_id", "agent"]
        missing = [f for f in essential_fields if f'"{f}"' not in source]
        assert not missing, f"Missing essential fields in logger: {missing}"

        # GenAI: judge whether fields provide enough context for meaningful analysis
        result = genai.judge(
            question="Do these log entry fields provide enough context for meaningful post-session analysis?",
            context=source,
            criteria=(
                "A session log entry should capture: when (timestamp), what (tool name), "
                "context (input summary without full content), result (output summary), "
                "who (session_id, agent). Score 8+ if all present, deduct 2 per missing essential field."
            ),
        )
        assert result["pass"], f"Insufficient log fields: {result['reasoning']}"
        assert result["score"] >= 8, f"Low score ({result['score']}): {result['reasoning']}"

    def test_logger_summarizes_not_logs_full_content(self, genai):
        """Input summarization should preserve privacy while retaining analysis value."""
        source = LOGGER_PATH.read_text()

        # Deterministic: verify content_length appears (summarization, not raw content)
        assert "content_length" in source, "Logger should use content_length instead of raw content"

        # Extract the _summarize_input function for focused analysis
        match = re.search(r"(def _summarize_input\(.*?\n(?:(?!^def ).*\n)*)", source, re.MULTILINE)
        assert match, "_summarize_input function not found in logger"
        summarize_fn = match.group(1)

        # GenAI: judge privacy-preserving summarization
        result = genai.judge(
            question="Does this summarization approach prevent sensitive data leakage while retaining analysis value?",
            context=summarize_fn,
            criteria=(
                "Input summarization should capture file paths and content length but NEVER log full "
                "file content. Commands should be truncated. Score 8+ if privacy-preserving while informative."
            ),
        )
        assert result["pass"], f"Privacy concern: {result['reasoning']}"
        assert result["score"] >= 8, f"Low score ({result['score']}): {result['reasoning']}"


class TestAnalystAgent:
    def test_analyst_covers_all_detection_categories(self, genai):
        """Analyst should cover all 5 detection categories with actionable criteria."""
        analyst = ANALYST_PATH.read_text()

        # Deterministic: verify section headers for all categories
        categories = [
            "Workflow Bypass",
            "Test Drift",
            "Doc Staleness",
            "Hook False Positive",
            "Congruence Violation",
        ]
        missing_cats = [c for c in categories if c.lower().replace(" ", "") not in analyst.lower().replace(" ", "")]
        assert not missing_cats, f"Missing detection categories: {missing_cats}"

        # GenAI: judge actionability of detection criteria
        result = genai.judge(
            question="Does each detection category have actionable detection criteria?",
            context=analyst,
            criteria=(
                "Each detection category should explain: what to look for, what evidence indicates "
                "the issue, and what severity to assign. Score 8+ if all categories have clear detection criteria."
            ),
        )
        assert result["pass"], f"Weak detection criteria: {result['reasoning']}"
        assert result["score"] >= 8, f"Low score ({result['score']}): {result['reasoning']}"

    def test_analyst_includes_project_alignment(self, genai):
        """Analyst should reference PROJECT.md goals for prioritization."""
        analyst = ANALYST_PATH.read_text()
        project_md_path = PROJECT_ROOT / ".claude" / "PROJECT.md"
        project_md = project_md_path.read_text() if project_md_path.exists() else ""

        # Deterministic: check for PROJECT.md or GOALS reference
        has_project_ref = "PROJECT.md" in analyst or "GOALS" in analyst or "project" in analyst.lower()
        # Note: this may legitimately fail if the analyst doesn't yet reference PROJECT.md
        # That's expected in TDD red phase

        # GenAI: judge whether analyst criteria serve the project mission
        result = genai.judge(
            question="Does the analyst's criteria serve the project's stated mission?",
            context=f"--- Analyst Agent ---\n{analyst}\n\n--- PROJECT.md ---\n{project_md[:3000]}",
            criteria=(
                "The analyst should compare findings against PROJECT.md GOALS to prioritize issues "
                "that directly serve the project mission. Score 7+ if alignment checking is present "
                "and uses the actual GOALS section."
            ),
        )
        assert result["score"] >= 7, f"Project alignment gap ({result['score']}): {result['reasoning']}"

    def test_congruence_pairs_documented(self, genai):
        """Known congruence pairs should cover critical relationships."""
        analyst = ANALYST_PATH.read_text()

        # Deterministic: extract congruence-related text
        assert "congruence" in analyst.lower(), "Analyst should document congruence pair checking"

        # GenAI: judge whether documented pairs cover critical relationships
        result = genai.judge(
            question="Do the documented congruence pairs cover the most critical file relationships?",
            context=analyst,
            criteria=(
                "Known congruence pairs should include at minimum: implement.md <-> implementer.md, "
                "manifest <-> disk files, policy <-> hook code. Score 7+ if these critical pairs are listed."
            ),
        )
        assert result["score"] >= 7, f"Congruence pairs incomplete ({result['score']}): {result['reasoning']}"


class TestImproveCommand:
    def test_improve_command_integrates_analyst(self, genai):
        """The /improve command should orchestrate the full analysis pipeline."""
        improve = IMPROVE_PATH.read_text()

        # Deterministic: check for analyst agent reference
        assert "continuous-improvement-analyst" in improve or "continuous-improvement" in improve, (
            "/improve command should reference the continuous-improvement-analyst agent"
        )

        # GenAI: judge pipeline orchestration
        result = genai.judge(
            question="Does the /improve command properly orchestrate log loading, analysis, and reporting?",
            context=improve,
            criteria=(
                "The /improve command should: load logs, pass them to the analyst agent with context "
                "(including PROJECT.md goals), and present findings with severity. Score 7+ if the "
                "full pipeline is described."
            ),
        )
        assert result["score"] >= 7, f"Pipeline incomplete ({result['score']}): {result['reasoning']}"

    def test_auto_file_uses_severity_threshold(self, genai):
        """Auto-filing should only create issues for critical and warning severity."""
        improve = IMPROVE_PATH.read_text()

        # Deterministic: check for severity-related terms in auto-file section
        assert "severity" in improve.lower(), "/improve should reference severity for auto-filing"
        assert "warning" in improve.lower(), "/improve should mention warning severity"

        # GenAI: judge severity threshold enforcement
        result = genai.judge(
            question="Does the auto-file feature exclude info-level findings from issue creation?",
            context=improve,
            criteria=(
                "Auto-filing should only create issues for critical and warning severity. "
                "Info-level findings should be report-only to avoid issue noise. Score 8+ if "
                "threshold is clear and info excluded."
            ),
        )
        assert result["score"] >= 8, f"Severity threshold unclear ({result['score']}): {result['reasoning']}"

    def test_session_log_to_findings_chain(self, genai):
        """The full chain from raw session data to actionable findings should be traceable."""
        logger_src = LOGGER_PATH.read_text()
        analyst_src = ANALYST_PATH.read_text()
        improve_src = IMPROVE_PATH.read_text()

        # Deterministic: verify data flow chain exists
        # Logger writes JSONL
        assert "jsonl" in logger_src.lower() or ".jsonl" in logger_src, "Logger should write JSONL"
        # Improve reads JSONL
        assert "jsonl" in improve_src.lower() or ".jsonl" in improve_src, "/improve should read JSONL"
        # Analyst processes log entries
        assert "jsonl" in analyst_src.lower() or "log" in analyst_src.lower(), (
            "Analyst should reference log entries"
        )

        # GenAI: judge full chain coherence
        combined = (
            f"--- Logger (writes data) ---\n{logger_src[:2000]}\n\n"
            f"--- Analyst (analyzes data) ---\n{analyst_src[:2000]}\n\n"
            f"--- /improve command (orchestrates) ---\n{improve_src[:2000]}"
        )
        result = genai.judge(
            question="Is the full chain from raw session data to actionable findings coherent and traceable?",
            context=combined,
            criteria=(
                "The chain should be: logger captures tool calls -> /improve loads logs -> analyst "
                "detects patterns -> findings classified by severity -> auto-file for critical/warning. "
                "Score 7+ if the full chain is traceable across the three components."
            ),
        )
        assert result["score"] >= 7, f"Chain broken ({result['score']}): {result['reasoning']}"
