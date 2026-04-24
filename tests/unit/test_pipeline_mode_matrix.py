"""Unit tests for PIPELINE-MODES.md agent matrix consistency.

Parses docs/PIPELINE-MODES.md matrix and commands/implement*.md step sections,
asserts consistency so future drift fails the test immediately.

Issue #905: ROOT-CAUSE consolidation — spec-validator and security-auditor
must be represented correctly in the --fix mode matrix.

These tests do NOT duplicate assertions already covered in:
  tests/spec_validation/test_spec_issue845_security_auditor_fix_mode.py
  (which validates SECURITY_SENSITIVE_PATTERNS membership and pattern matching)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_MODES_MD = REPO_ROOT / "docs" / "PIPELINE-MODES.md"
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
IMPLEMENT_FIX_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-fix.md"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _parse_mode_matrix(markdown_text: str) -> dict[str, dict[str, str]]:
    """Parse the agent matrix table into nested dict[agent_name, dict[mode, cell_value]].

    Handles whitespace liberally; strict about ✓ vs ✗.
    Returns {agent_name: {mode_name: cell_text}}.
    """
    # Find the Agent Matrix table — starts with the header row containing "Agent"
    lines = markdown_text.splitlines()
    table_start = None
    for i, line in enumerate(lines):
        if re.match(r"\|\s*Agent\s*\|", line):
            table_start = i
            break

    if table_start is None:
        return {}

    # Extract header columns
    header_line = lines[table_start]
    header_cols = [col.strip() for col in header_line.strip("|").split("|")]

    # Skip separator row
    result: dict[str, dict[str, str]] = {}
    for line in lines[table_start + 2:]:
        if not line.strip().startswith("|"):
            break  # End of table
        cols = [col.strip() for col in line.strip("|").split("|")]
        if len(cols) < 2:
            continue
        agent_name = cols[0].strip()
        if not agent_name:
            continue
        row: dict[str, str] = {}
        for col_idx, header in enumerate(header_cols[1:], start=1):
            if col_idx < len(cols):
                row[header] = cols[col_idx].strip()
            else:
                row[header] = ""
        result[agent_name] = row

    return result


def _parse_minimum_agents_per_mode(markdown_text: str) -> dict[str, tuple[int, int]]:
    """Parse 'Minimum agents per mode' bullet list.

    Returns dict[mode_key, (min_count, max_count)].
    max_count == min_count when no conditional range is present.

    Bullet format examples:
        - Full (default, acceptance-first): 8 — ...
        - `--fix`: 5 (6 if security-sensitive) — ...
        - `--light`: 4 — ...
    """
    result: dict[str, tuple[int, int]] = {}
    # Find the section
    in_section = False
    for line in markdown_text.splitlines():
        if "Minimum agents per mode" in line:
            in_section = True
            continue
        if in_section:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                break  # Next section header
            if not stripped.startswith("-"):
                continue

            # Extract mode key: content inside backticks or the first word before ':'
            mode_match = re.search(r"`([^`]+)`", stripped)
            if mode_match:
                mode_key = mode_match.group(1)
            else:
                # e.g., "Full (default, acceptance-first): 8 —"
                mode_key_match = re.match(r"-\s+([A-Za-z][^:]*?):", stripped)
                if mode_key_match:
                    mode_key = mode_key_match.group(1).strip()
                else:
                    continue

            # Extract digits — first number after the colon is min, parenthetical is max
            after_colon = stripped[stripped.index(":") + 1:]
            # Pattern: "5 (6 if ...)" or just "8"
            range_match = re.search(r"(\d+)\s*\((\d+)", after_colon)
            if range_match:
                min_count = int(range_match.group(1))
                max_count = int(range_match.group(2))
            else:
                single_match = re.search(r"(\d+)", after_colon)
                if single_match:
                    min_count = max_count = int(single_match.group(1))
                else:
                    continue

            result[mode_key] = (min_count, max_count)

    return result


def _count_agents_for_mode(
    matrix: dict[str, dict[str, str]],
    mode: str,
    *,
    include_bg: bool = False,
) -> int:
    """Count matrix cells for `mode` that start with ✓.

    By default excludes agents whose cell contains '(bg)' — background agents
    are not counted toward the foreground minimum. Set include_bg=True to count them.
    """
    count = 0
    for agent_name, row in matrix.items():
        cell = row.get(mode, "")
        if not cell.startswith("✓"):
            continue
        if not include_bg and "(bg)" in cell:
            continue
        count += 1
    return count


def _extract_step_headings(markdown_text: str) -> set[str]:
    """Extract STEP identifiers like 'STEP 1', 'STEP 3.5', 'STEP F3.5' from markdown.

    Matches heading banners and inline references of the form STEP <N>[.<sub>].
    """
    return set(re.findall(r"STEP\s+[A-Z]?\d+(?:\.\d+)?", markdown_text))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMatrixParsing:
    """Sanity-check the parser itself."""

    @pytest.fixture
    def matrix(self) -> dict[str, dict[str, str]]:
        return _parse_mode_matrix(PIPELINE_MODES_MD.read_text())

    def test_matrix_parses(self, matrix: dict[str, dict[str, str]]):
        """Parser produces non-empty rows for the required agents."""
        required_agents = [
            "researcher-local",
            "planner",
            "implementer",
            "spec-validator",
            "reviewer",
            "security-auditor",
            "doc-master",
            "continuous-improvement-analyst",
        ]
        for agent in required_agents:
            assert agent in matrix, (
                f"Agent '{agent}' not found in PIPELINE-MODES.md matrix. "
                f"Found agents: {list(matrix.keys())}"
            )
        assert len(matrix) >= len(required_agents), (
            f"Expected at least {len(required_agents)} agents, got {len(matrix)}"
        )


class TestFixModeAgents:
    """Verify --fix mode agent matrix entries are correct."""

    @pytest.fixture
    def matrix(self) -> dict[str, dict[str, str]]:
        return _parse_mode_matrix(PIPELINE_MODES_MD.read_text())

    @pytest.fixture
    def fix_md_text(self) -> str:
        return IMPLEMENT_FIX_MD.read_text()

    def test_fix_mode_includes_spec_validator(
        self, matrix: dict[str, dict[str, str]], fix_md_text: str
    ):
        """spec-validator cell for --fix starts with ✓ AND implement-fix.md has STEP F3.5."""
        fix_col = "`--fix`"
        spec_cell = matrix.get("spec-validator", {}).get(fix_col, "")
        assert spec_cell.startswith("✓"), (
            f"PIPELINE-MODES.md matrix spec-validator[--fix] must start with ✓. "
            f"Got: {spec_cell!r}"
        )
        assert "STEP F3.5" in fix_md_text, (
            "implement-fix.md must contain 'STEP F3.5' for spec-blind validation"
        )

    def test_fix_mode_includes_conditional_security_auditor(
        self, matrix: dict[str, dict[str, str]], fix_md_text: str
    ):
        """security-auditor cell for --fix starts with ✓, contains 'conditional', AND implement-fix.md has Security-Sensitivity Detection."""
        fix_col = "`--fix`"
        sec_cell = matrix.get("security-auditor", {}).get(fix_col, "")
        assert sec_cell.startswith("✓"), (
            f"PIPELINE-MODES.md matrix security-auditor[--fix] must start with ✓. "
            f"Got: {sec_cell!r}"
        )
        assert "conditional" in sec_cell.lower(), (
            f"security-auditor[--fix] cell must contain 'conditional'. Got: {sec_cell!r}"
        )
        assert "Security-Sensitivity Detection" in fix_md_text, (
            "implement-fix.md must contain 'Security-Sensitivity Detection' section"
        )


class TestMinimumAgentCounts:
    """Verify minimum-agent count bullets agree with matrix ✓ counts."""

    @pytest.fixture
    def md_text(self) -> str:
        return PIPELINE_MODES_MD.read_text()

    @pytest.fixture
    def matrix(self, md_text: str) -> dict[str, dict[str, str]]:
        return _parse_mode_matrix(md_text)

    @pytest.fixture
    def minimums(self, md_text: str) -> dict[str, tuple[int, int]]:
        return _parse_minimum_agents_per_mode(md_text)

    def test_fix_minimum_agent_count_matches_matrix(
        self,
        matrix: dict[str, dict[str, str]],
        minimums: dict[str, tuple[int, int]],
    ):
        """--fix bullet range must bracket the matrix ✓ count (incl. bg, excl. conditional security-auditor).

        The minimum-agent bullets count background agents (CI analyst) as part of the
        pipeline, so we use include_bg=True. The conditional security-auditor is NOT
        counted in the minimum (it only runs when Security-Sensitivity Detection fires).
        """
        fix_key = "--fix"
        assert fix_key in minimums, (
            f"Could not parse --fix entry from 'Minimum agents per mode' bullets. "
            f"Found: {list(minimums.keys())}"
        )
        min_count, max_count = minimums[fix_key]
        fix_col = "`--fix`"
        # Count all ✓ agents including bg (bullets count bg in the minimum)
        count_all = _count_agents_for_mode(matrix, fix_col, include_bg=True)
        # Exclude security-auditor since it's conditional (not always present)
        sec_cell = matrix.get("security-auditor", {}).get(fix_col, "")
        count_without_sec = count_all
        if sec_cell.startswith("✓") and "conditional" in sec_cell.lower():
            count_without_sec -= 1

        assert min_count <= count_without_sec <= max_count, (
            f"--fix matrix ✓ count (incl. bg, excl. conditional security-auditor) = "
            f"{count_without_sec}, but bullet says range [{min_count}, {max_count}]. "
            f"Update one to match the other."
        )

    def test_full_mode_minimum_agent_count_matches_matrix(
        self,
        matrix: dict[str, dict[str, str]],
        minimums: dict[str, tuple[int, int]],
    ):
        """Full mode bullet count must be <= matrix ✓ count (bg excluded)."""
        # Full mode key may be "Full (default, acceptance-first)" or similar
        full_key = next(
            (k for k in minimums if "full" in k.lower() or "default" in k.lower()), None
        )
        assert full_key is not None, (
            f"Could not find Full mode entry in minimums. Keys: {list(minimums.keys())}"
        )
        min_count, max_count = minimums[full_key]
        full_col = "Full"
        count = _count_agents_for_mode(matrix, full_col, include_bg=False)
        assert min_count <= count, (
            f"Full mode bullet says min {min_count} agents but matrix only shows "
            f"{count} foreground ✓ entries. Update bullet or matrix."
        )

    def test_light_mode_minimum_agent_count_matches_matrix(
        self,
        matrix: dict[str, dict[str, str]],
        minimums: dict[str, tuple[int, int]],
    ):
        """--light bullet count must match matrix ✓ count (bg excluded, since bullet uses '+CI analyst bg' notation)."""
        light_key = next((k for k in minimums if "light" in k.lower()), None)
        assert light_key is not None, (
            f"Could not find --light mode entry in minimums. Keys: {list(minimums.keys())}"
        )
        min_count, max_count = minimums[light_key]
        light_col = "`--light`"
        # Bullets list bg separately ("+ CI analyst bg"), so exclude bg from count
        count = _count_agents_for_mode(matrix, light_col, include_bg=False)
        assert min_count <= count <= max_count, (
            f"--light mode bullet says range [{min_count}, {max_count}] but matrix "
            f"shows {count} foreground ✓ entries. Update bullet or matrix."
        )


class TestStepSequenceConsistency:
    """Verify step IDs mentioned in PIPELINE-MODES.md actually exist in the command files."""

    def test_full_pipeline_steps_present_in_implement_md(self):
        """Steps referenced in PIPELINE-MODES.md Step-by-Step Sequence appear in implement.md."""
        modes_text = PIPELINE_MODES_MD.read_text()
        implement_text = IMPLEMENT_MD.read_text()

        # These are the anchoring steps that must exist — a representative set
        # that would break if the step sequence in implement.md were restructured
        required_steps = ["STEP 1", "STEP 4", "STEP 8", "STEP 10", "STEP 15"]
        for step in required_steps:
            assert step in implement_text, (
                f"'{step}' referenced in PIPELINE-MODES.md but not found in implement.md"
            )

    def test_fix_pipeline_steps_present_in_implement_fix_md(self):
        """Steps referenced in PIPELINE-MODES.md Fix Pipeline Sequence appear in implement-fix.md."""
        fix_text = IMPLEMENT_FIX_MD.read_text()

        # F3.5 is the newly required gate — its presence is the regression lock
        required_steps = ["F1", "F2", "F3", "F3.5", "F4", "F5"]
        for step in required_steps:
            assert step in fix_text, (
                f"Fix pipeline step '{step}' referenced in PIPELINE-MODES.md "
                f"but not found in implement-fix.md"
            )
