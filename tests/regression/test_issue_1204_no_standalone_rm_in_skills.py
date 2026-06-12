"""Regression tests for Issue #1204: no standalone `rm` calls in skill bash blocks.

Background: Skills emitted standalone `rm` cleanup calls after their
temp-file-consuming commands (e.g., after `gh issue create`). Because `rm` is
never auto-allowed by Claude Code (destructive, always prompts), every
planning/filing flow surfaced a permission prompt to the user. The fix is to
chain the `rm` onto the consuming command using `;` so a single create
approval covers the cleanup, AND the cleanup runs even on failure paths.

Hard constraint preserved (#1203): The context-file WRITE (the python heredoc
that creates `/tmp/autonomous_dev_cmd_context.json`) MUST remain a STANDALONE
prior Bash call before any `gh issue create`. Only the trailing `rm` cleanup
gets bundled with the consuming command.

These tests scan the 6 in-scope skill files for standalone `rm` patterns in
fenced ```bash blocks and fail if any are found outside the allowed
exclusion-marker contexts (anti-pattern examples, error-exit paths with no
preceding consuming Bash call to chain onto).

Issue: #1204
Date: 2026-06-12
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "commands"

# The 6 in-scope skill files (4 spec + 2 defense-in-depth).
IN_SCOPE_FILES = [
    COMMANDS_DIR / "create-issue.md",
    COMMANDS_DIR / "plan.md",
    COMMANDS_DIR / "plan-to-issues.md",
    COMMANDS_DIR / "improve.md",
    COMMANDS_DIR / "refactor.md",
    COMMANDS_DIR / "retrospective.md",
]

# Markers that, when found in the prose context around a bash block, exempt
# the block from the standalone-rm prohibition. Used for explicit
# anti-pattern examples and unavoidable error-exit paths.
EXCLUSION_MARKERS = (
    "WRONG:",
    "DO NOT:",
    "<details>",
    "ANTI-PATTERN",
    "unavoidable: no preceding",
)

# Regex: a line whose first non-whitespace token is `rm` (the standalone form).
STANDALONE_RM_RE = re.compile(r"^\s*rm\s")

# Regex: a fenced ```bash ... ``` block (non-greedy, multi-line).
BASH_BLOCK_RE = re.compile(r"```bash\n(.*?)```", re.DOTALL)


def _iter_bash_blocks(content: str):
    """Yield (block_body, start_offset, end_offset) for each ```bash block."""
    for m in BASH_BLOCK_RE.finditer(content):
        yield m.group(1), m.start(), m.end()


def _context_window(content: str, block_start: int, lookback_chars: int = 400) -> str:
    """Return the prose immediately preceding a bash block (for exclusion-marker lookup)."""
    start = max(0, block_start - lookback_chars)
    return content[start:block_start]


def _block_has_exclusion_marker(block_body: str, preceding_prose: str) -> bool:
    """Check if a block (or its preceding prose) carries an exclusion marker."""
    haystack = block_body + "\n" + preceding_prose
    return any(marker in haystack for marker in EXCLUSION_MARKERS)


def _find_standalone_rm_lines(block_body: str) -> list[str]:
    """Return lines in the block body that are standalone `rm` invocations.

    A line is standalone if its first non-whitespace token is `rm` (i.e., the
    line is not chained from a preceding command via `;` or `&&` on the same
    line). Chained `rm` is fine (it inherits the parent command's approval).
    """
    standalone = []
    for line in block_body.splitlines():
        # Skip comment-only lines.
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Check if the line begins with `rm` (standalone form).
        if STANDALONE_RM_RE.match(line):
            # Inline-comment carve-out: if the rm line carries an inline
            # exclusion marker (e.g., "# unavoidable: no preceding ..."), the
            # standalone form is acceptable for that specific line.
            if any(marker in line for marker in EXCLUSION_MARKERS):
                continue
            standalone.append(line)
    return standalone


@pytest.mark.parametrize("file_path", IN_SCOPE_FILES, ids=lambda p: p.name)
def test_no_standalone_rm_in_skill_bash_blocks(file_path: Path) -> None:
    """Each in-scope skill file MUST NOT contain standalone `rm` lines in its
    ```bash blocks, except where an exclusion marker is present.

    This is the primary regression test for #1204: a standalone `rm` would
    re-introduce the user-facing permission prompt the fix eliminated.
    """
    assert file_path.exists(), f"In-scope file missing: {file_path}"
    content = file_path.read_text()

    offenders: list[tuple[int, str]] = []
    for block_body, block_start, _block_end in _iter_bash_blocks(content):
        preceding_prose = _context_window(content, block_start)
        if _block_has_exclusion_marker(block_body, preceding_prose):
            continue
        standalone_rms = _find_standalone_rm_lines(block_body)
        for line in standalone_rms:
            offenders.append((block_start, line.rstrip()))

    assert not offenders, (
        f"{file_path.name} contains standalone `rm` lines in bash blocks "
        f"(re-introduces user-visible permission prompts; see #1204):\n"
        + "\n".join(f"  at offset {offset}: {line!r}" for offset, line in offenders)
        + "\n\nFix: chain the `rm` onto the consuming command via `;` "
        "(e.g., `gh issue create ...; rm -f /tmp/file`). "
        "If the rm has no preceding consuming Bash call (true error-exit path), "
        "add an inline comment marker: `# unavoidable: no preceding Bash call to chain onto`."
    )


def test_chained_rm_pattern_is_allowed() -> None:
    """Negative case: properly chained `rm` (`...; rm ...`) MUST NOT be flagged.

    Proves the detection regex does not false-fire on the correct pattern.
    """
    # Synthetic block content matching the post-fix pattern.
    chained_block = (
        "gh issue create --title \"x\" --body-file /tmp/issue.md; "
        "rm -f /tmp/autonomous_dev_cmd_context.json /tmp/issue.md\n"
    )
    standalone_rms = _find_standalone_rm_lines(chained_block)
    assert standalone_rms == [], (
        f"Detector false-fired on chained `rm`: {standalone_rms!r}. "
        "The regex must require `rm` at the START of a line (after whitespace), "
        "not anywhere on the line."
    )

    # Also verify multi-line block where rm follows gh on the SAME line.
    multi_line_block = (
        "python3 -c \"...context write...\"\n"
        "gh issue create --title \"x\" --body \"...\"; rm -f /tmp/ctx.json\n"
    )
    standalone_rms = _find_standalone_rm_lines(multi_line_block)
    assert standalone_rms == [], (
        f"Detector false-fired on same-line chained `rm`: {standalone_rms!r}"
    )


@pytest.mark.parametrize("file_path", IN_SCOPE_FILES, ids=lambda p: p.name)
def test_no_create_then_standalone_rm_in_same_block(file_path: Path) -> None:
    """Co-occurrence guard: any ```bash block containing BOTH `gh issue create`
    AND a standalone `rm` line on a SUBSEQUENT line is forbidden.

    Rationale: even if the block is well-intentioned, multi-line bash blocks
    in skill files are rendered as a single tool call. A standalone `rm` on
    a later line within the SAME block fails because the `rm` line is its own
    statement (not chained onto the create), and would surface a prompt.
    """
    assert file_path.exists(), f"In-scope file missing: {file_path}"
    content = file_path.read_text()

    offending_blocks: list[str] = []
    for block_body, block_start, _block_end in _iter_bash_blocks(content):
        preceding_prose = _context_window(content, block_start)
        if _block_has_exclusion_marker(block_body, preceding_prose):
            continue
        if "gh issue create" not in block_body:
            continue
        standalone_rms = _find_standalone_rm_lines(block_body)
        if standalone_rms:
            offending_blocks.append(
                f"at offset {block_start}:\n{block_body.rstrip()}"
            )

    assert not offending_blocks, (
        f"{file_path.name} has bash block(s) containing BOTH `gh issue create` "
        f"AND a standalone `rm` (see #1204):\n\n"
        + "\n---\n".join(offending_blocks)
        + "\n\nFix: chain the `rm` onto the `gh issue create` line via `;`, "
        "or split the block so the `rm` rides the same Bash tool call as the create."
    )
