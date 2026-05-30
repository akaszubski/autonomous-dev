"""Prompt quality anti-pattern rules for agent prompts (Issue #842).

Shared library used by:
- tests/unit/test_prompt_quality.py (static inspection)
- unified_pre_tool.py Layer 6 (write-time validation)
"""
import re
from typing import Dict, List

# Persona pattern: catches "You are an expert", "You are a world-class",
# but NOT "You are the **implementer** agent" (legitimate role assignment).
PERSONA_PATTERN = re.compile(
    r"(?i)(?:^|\n)\s*you are (?:an? )?(?:expert|senior|world[- ]class|renowned|leading|top)"
)

# Casual register phrases that weaken enforcement prompts.
CASUAL_REGISTER_PATTERNS = [
    re.compile(r"(?i)\bcheck for\b"),
    re.compile(r"(?i)\blook for\b"),
    re.compile(r"(?i)\bmake sure\b"),
    re.compile(r"(?i)\btry to\b"),
    re.compile(r"(?i)\byou should\b"),
    re.compile(r"(?i)\bfeel free\b"),
]

# Maximum bullet items per ## section before flagging as oversized.
CONSTRAINT_DENSITY_THRESHOLD = 8

# Issue #1119: ##-section headers containing any of these tokens (case-insensitive)
# are exempt from bullet-density counting.  These sections are load-bearing
# enforcement text (FORBIDDEN lists, HARD GATE policies, REQUIRED steps) — not
# prose bullets — so capping their length forces agents to adopt symbol-prefix
# workarounds (e.g. "❌ ") that defeat the lint rule and drift list formatting
# across files.
EXEMPT_HEADER_TOKENS = ("FORBIDDEN", "HARD GATE", "HARD-GATE", "REQUIRED", "MUST NOT")


def _is_exempt_section(header: str) -> bool:
    """Return True if a ``## `` header denotes an exempt enforcement section.

    Matching is case-insensitive and substring-based: a header is exempt if
    any token in :data:`EXEMPT_HEADER_TOKENS` appears anywhere in the header
    text (after stripping the leading ``## ``).  Examples that match:

      - ``## FORBIDDEN``
      - ``## HARD GATE: Test Coverage``
      - ``## REQUIRED: Steps``
      - ``## MUST NOT skip``

    Args:
        header: Section header text WITHOUT the leading ``## `` (the form
            already produced by callers via ``stripped.lstrip("# ").strip()``).

    Returns:
        True if the header contains any exempt token, False otherwise.
    """
    upper = header.upper()
    return any(token in upper for token in EXEMPT_HEADER_TOKENS)


def check_persona(content: str) -> List[str]:
    """Check for banned persona patterns.

    Catches opener phrases like "You are an expert" or "You are a senior"
    which are anti-patterns in enforcement prompts.  Legitimate role
    assignments like "You are the **implementer** agent" are allowed.

    Args:
        content: Full text content to check.

    Returns:
        List of violation descriptions (empty if no violations).
    """
    violations: List[str] = []
    for match in PERSONA_PATTERN.finditer(content):
        line_num = content[:match.start()].count("\n") + 1
        matched_text = match.group().strip()
        violations.append(
            f"Line {line_num}: Banned persona opener '{matched_text}'. "
            f"Use role assignment (e.g. 'You are the **agent** agent') instead."
        )
    return violations


def check_casual_register(content: str) -> List[str]:
    """Check for casual register phrases.

    Phrases like 'make sure', 'try to', 'feel free' weaken enforcement.
    Use 'MUST', 'REQUIRED', 'FORBIDDEN' instead.

    Args:
        content: Full text content to check.

    Returns:
        List of violation descriptions with line numbers.
    """
    violations: List[str] = []
    for pattern in CASUAL_REGISTER_PATTERNS:
        for match in pattern.finditer(content):
            line_num = content[:match.start()].count("\n") + 1
            matched_text = match.group().strip()
            violations.append(
                f"Line {line_num}: Casual register phrase '{matched_text}'. "
                f"Use formal directive language (MUST, REQUIRED, FORBIDDEN) instead."
            )
    return violations


def check_constraint_density(
    content: str, threshold: int = CONSTRAINT_DENSITY_THRESHOLD
) -> List[str]:
    """Check for oversized constraint sections.

    Counts bullet items (lines starting with - or *) per ## section.
    Sections exceeding the threshold are flagged.

    Issue #1119: ``## `` sections whose headers contain enforcement tokens
    (FORBIDDEN, HARD GATE, REQUIRED, MUST NOT — see
    :data:`EXEMPT_HEADER_TOKENS`) are exempt from this check.  These sections
    are load-bearing enforcement text, not prose.

    Args:
        content: Full text content to check.
        threshold: Maximum allowed bullet items per section.

    Returns:
        List of violation descriptions (empty if no violations).
    """
    violations: List[str] = []
    lines = content.split("\n")

    current_section: str = "(top-level)"
    section_start_line: int = 1
    bullet_count: int = 0
    # Issue #1119: when True, the current section is exempt — do not count
    # bullets and do not emit a violation when the section closes.
    section_exempt: bool = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Detect ## section headers (not # or ###)
        if stripped.startswith("## ") and not stripped.startswith("### "):
            # Check previous section before moving to next — but skip the
            # check entirely if the previous section was exempt.
            if not section_exempt and bullet_count > threshold:
                violations.append(
                    f"Section '{current_section}' (line {section_start_line}): "
                    f"{bullet_count} bullet items exceeds threshold of {threshold}."
                )
            current_section = stripped.lstrip("# ").strip()
            section_start_line = i + 1
            bullet_count = 0
            section_exempt = _is_exempt_section(current_section)
        elif not section_exempt and (
            stripped.startswith("- ") or stripped.startswith("* ")
        ):
            bullet_count += 1

    # Check final section — same exemption rule applies.
    if not section_exempt and bullet_count > threshold:
        violations.append(
            f"Section '{current_section}' (line {section_start_line}): "
            f"{bullet_count} bullet items exceeds threshold of {threshold}."
        )

    return violations


def _section_bullet_counts(content: str) -> Dict[str, int]:
    """Parse content into a {section_name: bullet_count} map.

    Used by diff-aware checks (Issue #1038) to compare pre-edit and
    post-edit content section-by-section.  Sections are identified by
    ``## `` headers (level 2, not level 1 or level 3+).

    If the same section header appears multiple times, the LAST occurrence
    wins — this matches the conservative diff-awareness semantics: the
    "current state" of a section is what the section looks like at end of
    file.  Sections with duplicate names are rare in practice.

    Issue #1119: exempt enforcement sections (see :func:`_is_exempt_section`)
    are OMITTED from the returned mapping.  Bullets inside an exempt section
    are not counted, and the section itself never appears as a key.  This
    means :func:`check_constraint_density_diff` will never flag an exempt
    section regardless of bullet count.

    Args:
        content: Full text content to parse.

    Returns:
        Mapping of non-exempt section name (header text without leading
        ``## ``) to bullet count within that section.  Top-level bullets
        (before any ``## `` header) are collected under the key
        ``"(top-level)"``.
    """
    counts: Dict[str, int] = {}
    lines = content.split("\n")

    current_section: str = "(top-level)"
    bullet_count: int = 0
    section_exempt: bool = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            # Record previous section's count before moving on — but only if
            # that section was not exempt.
            if not section_exempt:
                counts[current_section] = bullet_count
            current_section = stripped.lstrip("# ").strip()
            bullet_count = 0
            section_exempt = _is_exempt_section(current_section)
        elif not section_exempt and (
            stripped.startswith("- ") or stripped.startswith("* ")
        ):
            bullet_count += 1

    # Record the final section — same exemption rule.
    if not section_exempt:
        counts[current_section] = bullet_count
    return counts


def check_constraint_density_diff(
    old_content: str,
    new_content: str,
    threshold: int = CONSTRAINT_DENSITY_THRESHOLD,
) -> List[str]:
    """Diff-aware constraint-density check (Issue #1038).

    Only flags sections in ``new_content`` that are:
      (a) NEW (not present in ``old_content``) AND oversized, OR
      (b) WORSENED (bullet count increased over the prior count) AND oversized.

    Sections that existed before with the same-or-fewer bullets are exempted
    even if they exceed the threshold.  This prevents pre-existing oversized
    sections from blocking edits that don't touch those sections.

    Args:
        old_content: Pre-edit file content.
        new_content: Post-edit file content (after applying the edit).
        threshold: Maximum allowed bullet items per section.

    Returns:
        List of violation descriptions for sections that are new-or-worsened
        AND exceed the threshold.  Empty if no qualifying violations.
    """
    old_counts = _section_bullet_counts(old_content)
    new_counts = _section_bullet_counts(new_content)

    violations: List[str] = []
    for section, new_count in new_counts.items():
        if new_count <= threshold:
            continue
        old_count = old_counts.get(section)
        # Exempt if section existed before with same-or-fewer bullets.
        if old_count is not None and new_count <= old_count:
            continue
        if old_count is None:
            reason = f"new section with {new_count} bullets"
        else:
            reason = (
                f"{old_count} -> {new_count} bullets (increase exceeds threshold)"
            )
        violations.append(
            f"Section '{section}': {reason} exceeds threshold of {threshold}."
        )
    return violations


def check_all(content: str) -> List[str]:
    """Run all prompt quality checks.

    Args:
        content: Full text content to check.

    Returns:
        Combined list of violations from all checks (empty = pass).
    """
    violations: List[str] = []
    violations.extend(check_persona(content))
    violations.extend(check_casual_register(content))
    violations.extend(check_constraint_density(content))
    return violations
