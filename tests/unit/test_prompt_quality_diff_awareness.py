"""Diff-aware prompt-quality regression tests (Issue #1038).

The Layer-6 prompt-quality gate previously blocked any Edit to an agent /
command Markdown file whose post-edit content contained any oversized
section — even when the oversized section pre-existed and was untouched by
the edit.  Issue #1038 makes the density check diff-aware: only NEW or
WORSENED sections are flagged.  Persona / casual-register patterns that
already existed in the file are likewise exempted via set-difference at
the call site in unified_pre_tool.py.

These tests lock the new ``check_constraint_density_diff`` helper.
"""

import sys
from pathlib import Path

import pytest

# Portable project-root detection.
# tests/unit/test_prompt_quality_diff_awareness.py -> parents[2] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LIB_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))

from prompt_quality_rules import (  # noqa: E402  (sys.path mutation above)
    CONSTRAINT_DENSITY_THRESHOLD,
    check_constraint_density,
    check_constraint_density_diff,
)


def _section(name: str, n_bullets: int) -> str:
    """Build a ``## {name}`` section with ``n_bullets`` bullet items."""
    lines = [f"## {name}", ""]
    for i in range(n_bullets):
        lines.append(f"- bullet {i + 1}")
    return "\n".join(lines) + "\n"


class TestConstraintDensityDiff:
    """Issue #1038: density check must exempt pre-existing oversized sections."""

    def test_diff_exempts_pre_existing_oversized_section(self) -> None:
        """An edit that does NOT touch a pre-existing oversized section must
        not flag that section.

        Scenario: existing file has a 17-bullet section (already over the
        default threshold of 8). The edit appends a small, well-formed
        section. The diff-aware check must return NO violations.
        """
        threshold = CONSTRAINT_DENSITY_THRESHOLD
        old = _section("Pre-existing Oversized", 17) + _section("Other", 3)
        # Edit appends a small section, doesn't touch the oversized one.
        new = old + _section("Newly Added", 4)

        # Sanity: the non-diff check WOULD flag the pre-existing section.
        baseline = check_constraint_density(new, threshold=threshold)
        assert any(
            "Pre-existing Oversized" in v for v in baseline
        ), "fixture invalid: non-diff check should still flag pre-existing"

        # Diff-aware check must exempt the untouched pre-existing section.
        violations = check_constraint_density_diff(old, new, threshold=threshold)
        assert violations == [], (
            f"diff-aware check should be empty (pre-existing section "
            f"unchanged), got: {violations}"
        )

    def test_diff_flags_new_oversized_section(self) -> None:
        """An edit that ADDS a new oversized section must be flagged."""
        threshold = CONSTRAINT_DENSITY_THRESHOLD
        old = _section("Existing Small", 3)
        # Edit adds a brand new section with 20 bullets (well over threshold).
        new = old + _section("Brand New Big", 20)

        violations = check_constraint_density_diff(old, new, threshold=threshold)
        assert len(violations) == 1, (
            f"expected exactly one violation for new big section, got {violations}"
        )
        assert "Brand New Big" in violations[0]
        assert "20" in violations[0]

    def test_diff_flags_worsened_section(self) -> None:
        """A section that grew across the threshold must be flagged."""
        threshold = 8
        # Pre-edit: 10 bullets — already over threshold (but we'd exempt it).
        old = _section("Will Grow", 10)
        # Post-edit: 15 bullets — INCREASED across threshold; flag it.
        new = _section("Will Grow", 15)

        violations = check_constraint_density_diff(old, new, threshold=threshold)
        assert len(violations) == 1, (
            f"expected exactly one violation for worsened section, got {violations}"
        )
        assert "Will Grow" in violations[0]
        assert "15" in violations[0]
        assert "10" in violations[0]  # mentions the prior count

    def test_diff_full_write_uses_standard_check(self) -> None:
        """When old_content is empty (Write tool, full overwrite), the
        diff-aware check must behave like the standard check — every section
        is effectively 'new'.
        """
        threshold = CONSTRAINT_DENSITY_THRESHOLD
        old = ""  # No prior content — caller treats this as a fresh Write.
        new = _section("Fresh Oversized", 20) + _section("Fresh Small", 3)

        violations = check_constraint_density_diff(old, new, threshold=threshold)
        assert len(violations) == 1, (
            f"Write semantics: fresh oversized section must be flagged, "
            f"got: {violations}"
        )
        assert "Fresh Oversized" in violations[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
