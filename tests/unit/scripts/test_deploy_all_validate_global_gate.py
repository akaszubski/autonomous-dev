"""
Tests for deploy-all.sh validate_global() gating on DO_GLOBAL (Issue #1313).

Root cause: post-deploy validation block at line 504-518 ran unconditionally
inside `if $DO_LOCAL && ! $DRY_RUN && ! $SKIP_VALIDATE`, even when
`--no-global` was passed (DO_GLOBAL=false). The fix wraps the "Validate
global" block in `if $DO_GLOBAL; then ... fi`, mirroring the deploy-side
pattern at line 479.

Static inspection only — no subprocess execution.
"""
import re
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[3]
DEPLOY_SCRIPT = WORKTREE / "scripts" / "deploy-all.sh"


def test_deploy_script_exists() -> None:
    """Path sanity check: deploy-all.sh must exist at the expected location."""
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh not found at: {DEPLOY_SCRIPT}"
    assert DEPLOY_SCRIPT.is_file(), f"Expected file, got: {DEPLOY_SCRIPT}"


def test_validate_global_block_is_gated_by_do_global() -> None:
    """The "# Validate global" comment MUST be immediately followed by `if $DO_GLOBAL; then`.

    This is the Issue #1313 fix: the validation block runs only when global was deployed.
    """
    lines = DEPLOY_SCRIPT.read_text().splitlines()

    # Find the "# Validate global" comment line
    comment_idx = None
    for i, line in enumerate(lines):
        if re.match(r"\s*#\s*Validate global", line):
            comment_idx = i
            break

    assert comment_idx is not None, (
        "Could not find '# Validate global' comment in deploy-all.sh. "
        "Either the comment was removed/renamed or the validation block was deleted."
    )

    # Find the next non-blank line
    next_idx = comment_idx + 1
    while next_idx < len(lines) and not lines[next_idx].strip():
        next_idx += 1

    assert next_idx < len(lines), "EOF immediately after '# Validate global' comment"

    next_line = lines[next_idx].strip()
    # Accept both `if $DO_GLOBAL; then` and `if "$DO_GLOBAL"; then`
    pattern = r'^if\s+"?\$DO_GLOBAL"?\s*;\s*then\s*$'
    assert re.match(pattern, next_line), (
        f"Line after '# Validate global' comment must be `if $DO_GLOBAL; then` "
        f"(Issue #1313 gate). Got: {next_line!r}"
    )


def test_no_global_flag_still_sets_do_global_false() -> None:
    """Regression guard on the --no-global argument parser.

    Removing or breaking this case would render the new gate inert.
    """
    content = DEPLOY_SCRIPT.read_text()

    # Find the --no-global case branch — must set DO_GLOBAL=false
    pattern = r"--no-global\)\s*DO_GLOBAL=false"
    assert re.search(pattern, content), (
        "The --no-global flag must set DO_GLOBAL=false. "
        "Without this, the Issue #1313 gate is never triggered."
    )


def test_validate_local_loop_remains_outside_global_gate() -> None:
    """The per-repo validate_local loop MUST stay OUTSIDE the new $DO_GLOBAL gate.

    Per-repo validation runs unconditionally when DO_LOCAL is true. The new
    gate only wraps the global-hook validation block.
    """
    lines = DEPLOY_SCRIPT.read_text().splitlines()

    # Locate the "# Validate global" comment
    comment_idx = None
    for i, line in enumerate(lines):
        if re.match(r"\s*#\s*Validate global", line):
            comment_idx = i
            break
    assert comment_idx is not None, "Could not find '# Validate global' comment"

    # From the comment, find the closing `fi` that ends the `if $DO_GLOBAL` block.
    # The block opens on the next non-blank line; track depth as we scan.
    open_idx = comment_idx + 1
    while open_idx < len(lines) and not lines[open_idx].strip():
        open_idx += 1

    # Now walk forward tracking nested `if`/`fi` until depth returns to 0.
    depth = 0
    closing_fi_idx = None
    for i in range(open_idx, len(lines)):
        stripped = lines[i].strip()
        # Match `if <cond>; then` or bare `if` at start of statement
        if re.match(r"^if\s+.*;\s*then\s*$", stripped) or re.match(r"^if\s+.*\bthen\s*$", stripped):
            depth += 1
        elif stripped == "fi":
            depth -= 1
            if depth == 0:
                closing_fi_idx = i
                break

    assert closing_fi_idx is not None, (
        "Could not find closing `fi` for the `if $DO_GLOBAL` block. "
        "Bash syntax may be malformed."
    )

    # Now find the `for repo_name in $LOCAL_REPOS` loop that follows the closing fi.
    # NOTE: there are two such loops in deploy-all.sh — one in the deploy section
    # (before the comment) and one in the validation section (after closing fi).
    # We want the validation-section loop, which is the first occurrence AFTER
    # the closing fi of the gated block.
    for_loop_idx = None
    for i in range(closing_fi_idx + 1, len(lines)):
        if re.search(r"for\s+repo_name\s+in\s+\$LOCAL_REPOS", lines[i]):
            for_loop_idx = i
            break

    assert for_loop_idx is not None, (
        "Could not find `for repo_name in $LOCAL_REPOS` loop. "
        "Per-repo validation may have been removed."
    )

    assert for_loop_idx > closing_fi_idx, (
        f"The `for repo_name in $LOCAL_REPOS` loop (line {for_loop_idx + 1}) "
        f"must appear AFTER the closing `fi` of the `if $DO_GLOBAL` block "
        f"(line {closing_fi_idx + 1}). Otherwise per-repo validation gets "
        f"gated on --no-global, which is wrong."
    )
