"""Regression tests for Issue #1119: exempt enforcement sections from bullet density.

The prompt-quality hook enforced a maximum of 8 bullets per ``##`` section.
Agents that needed to write longer FORBIDDEN / HARD GATE / REQUIRED lists
adopted symbol-prefix workarounds (e.g. ``❌ `` lines instead of ``- ``) to
slip past the line-prefix detector, drifting list formatting across files.

Fix: sections whose ``##`` header (case-insensitive) contains any of
``FORBIDDEN``, ``HARD GATE``, ``HARD-GATE``, ``REQUIRED``, ``MUST NOT`` are
exempt from bullet counting in both :func:`check_constraint_density` and
:func:`_section_bullet_counts` (the latter feeds the diff-aware path used
by ``unified_pre_tool.py`` at write time).

Evidence: Session #932 (batch-20260524-174212) implementer used ``❌`` prefix
instead of ``- `` on FORBIDDEN-list items in
``plugins/autonomous-dev/commands/implement.md`` to avoid the bullet
threshold.

These tests fail against the pre-fix code and pass with the exemption in
place.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Portable project-root detection.
# tests/unit/test_prompt_quality_rules.py -> parents[2] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LIB_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))

from prompt_quality_rules import (  # noqa: E402  (sys.path mutation above)
    CONSTRAINT_DENSITY_THRESHOLD,
    EXEMPT_HEADER_TOKENS,
    _is_exempt_section,
    _section_bullet_counts,
    check_constraint_density,
    check_constraint_density_diff,
)


def _bullets(n: int) -> str:
    """Return ``n`` ``- bullet K`` lines joined by newlines."""
    return "\n".join(f"- bullet {i + 1}" for i in range(n))


class TestIssue1119ExemptionsForConstraintDensity:
    """Issue #1119 regression: exempt sections must not be flagged.

    Four required scenarios (per issue spec):

      1. ``## FORBIDDEN`` with 12 bullets    -> no violation (exempt)
      2. ``## HARD GATE: Test Coverage`` 10  -> no violation (exempt)
      3. ``## Notes`` with 12 bullets        -> one violation (control)
      4. ``## REQUIRED: Steps`` with 9       -> no violation (exempt)
    """

    def test_forbidden_section_with_12_bullets_is_exempt(self) -> None:
        """A ``## FORBIDDEN`` section with 12 bullets MUST NOT be flagged.

        Without the Issue #1119 fix, this section would trigger a violation
        because 12 > CONSTRAINT_DENSITY_THRESHOLD (8).  The exemption is the
        whole point of the fix.
        """
        content = "## FORBIDDEN\n\n" + _bullets(12) + "\n"
        violations = check_constraint_density(content)
        assert violations == [], (
            f"FORBIDDEN section must be exempt from density check; "
            f"got: {violations}"
        )

    def test_hard_gate_section_with_10_bullets_is_exempt(self) -> None:
        """A ``## HARD GATE: Test Coverage`` section with 10 bullets is exempt."""
        content = "## HARD GATE: Test Coverage\n\n" + _bullets(10) + "\n"
        violations = check_constraint_density(content)
        assert violations == [], (
            f"HARD GATE section must be exempt from density check; "
            f"got: {violations}"
        )

    def test_non_exempt_notes_section_with_12_bullets_is_flagged(self) -> None:
        """Control: a ``## Notes`` section with 12 bullets MUST still be flagged.

        This proves the exemption only applies to sections whose header
        contains an exempt token — non-exempt sections continue to enforce
        the bullet threshold.
        """
        content = "## Notes\n\n" + _bullets(12) + "\n"
        violations = check_constraint_density(content)
        assert len(violations) == 1, (
            f"Non-exempt Notes section with 12 bullets must produce exactly "
            f"one violation; got: {violations}"
        )
        assert "Notes" in violations[0]
        assert "12 bullet items" in violations[0]

    def test_required_steps_section_with_9_bullets_is_exempt(self) -> None:
        """A ``## REQUIRED: Steps`` section with 9 bullets is exempt.

        9 is over the default threshold of 8, so without the exemption this
        would trip. The ``REQUIRED`` token in the header opts out.
        """
        content = "## REQUIRED: Steps\n\n" + _bullets(9) + "\n"
        violations = check_constraint_density(content)
        assert violations == [], (
            f"REQUIRED section must be exempt from density check; "
            f"got: {violations}"
        )


class TestIsExemptSectionHelper:
    """Sanity tests for the :func:`_is_exempt_section` predicate."""

    @pytest.mark.parametrize(
        "header",
        [
            "FORBIDDEN",
            "FORBIDDEN: New Skips",
            "forbidden",  # case-insensitive
            "Forbidden Behaviors",
            "HARD GATE",
            "HARD GATE: Test Coverage",
            "hard gate",
            "HARD-GATE: Hyphenated Form",
            "REQUIRED",
            "REQUIRED: Steps",
            "required next action",
            "MUST NOT",
            "Things You MUST NOT Do",
        ],
    )
    def test_exempt_headers_match(self, header: str) -> None:
        assert _is_exempt_section(header), (
            f"header {header!r} should be exempt (contains an exempt token "
            f"from {EXEMPT_HEADER_TOKENS!r})"
        )

    @pytest.mark.parametrize(
        "header",
        [
            "Notes",
            "Mission",
            "Quality Standards",
            "Workflow",
            "Output Format",
            "Process",
        ],
    )
    def test_non_exempt_headers_do_not_match(self, header: str) -> None:
        assert not _is_exempt_section(header), (
            f"header {header!r} must NOT be treated as exempt"
        )


class TestSectionBulletCountsHonorsExemptions:
    """Issue #1119: :func:`_section_bullet_counts` must omit exempt sections.

    This is the path used by the diff-aware check in
    :func:`check_constraint_density_diff`, which feeds the write-time hook in
    ``unified_pre_tool.py``.  If exempt sections leaked into the counts map,
    the diff-aware check could still flag them — defeating the fix.
    """

    def test_exempt_section_omitted_from_counts(self) -> None:
        content = (
            "## FORBIDDEN\n\n"
            + _bullets(20)
            + "\n\n## Notes\n\n"
            + _bullets(3)
            + "\n"
        )
        counts = _section_bullet_counts(content)
        # FORBIDDEN must NOT appear in the map; Notes MUST.
        assert "FORBIDDEN" not in counts, (
            f"exempt FORBIDDEN section must be omitted from counts; got: {counts}"
        )
        assert counts.get("Notes") == 3, (
            f"non-exempt Notes section must be counted; got: {counts}"
        )

    def test_diff_aware_check_does_not_flag_exempt_section(self) -> None:
        """An edit adding a NEW oversized exempt section MUST NOT be flagged.

        Without the fix, ``check_constraint_density_diff`` would see "Brand
        New FORBIDDEN" as a new section with > threshold bullets and emit a
        violation.  With the fix, the exempt section never enters the counts
        map, so the diff path can't report it.
        """
        old = "## Existing\n\n" + _bullets(2) + "\n"
        new = (
            old
            + "\n## FORBIDDEN: Brand New\n\n"
            + _bullets(15)
            + "\n"
        )
        violations = check_constraint_density_diff(
            old, new, threshold=CONSTRAINT_DENSITY_THRESHOLD
        )
        assert violations == [], (
            f"new exempt FORBIDDEN section must not be flagged by diff check; "
            f"got: {violations}"
        )

    def test_diff_aware_check_still_flags_new_non_exempt_section(self) -> None:
        """Control: diff-aware check still flags new non-exempt oversized
        sections.  Proves the exemption is targeted, not a blanket bypass.
        """
        old = "## Existing\n\n" + _bullets(2) + "\n"
        new = (
            old
            + "\n## Brand New Prose\n\n"
            + _bullets(15)
            + "\n"
        )
        violations = check_constraint_density_diff(
            old, new, threshold=CONSTRAINT_DENSITY_THRESHOLD
        )
        assert len(violations) == 1, (
            f"new non-exempt section must still be flagged; got: {violations}"
        )
        assert "Brand New Prose" in violations[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
