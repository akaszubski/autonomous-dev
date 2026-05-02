#!/usr/bin/env python3
"""Hook Path Validator — verify every hook command path declared in settings.

Walks the global (`~/.claude/settings.json`) and local
(`<project>/.claude/settings.local.json`) settings files, parses every
`hooks.<event>[].hooks[].command` string, and emits findings for four issue
categories:

1. **Missing scripts**   — the script referenced by the command does not exist.
2. **Non-executable**     — a `.sh`/`.bash`/`.zsh` script lacks the execute bit.
3. **Global+local dupes** — the same canonical hook path is registered in both
                             scopes (subtle source of double-firing hooks).
4. **Unresolved env vars** — the command references an env var that is not
                              defined and would expand to an empty string.

Findings reuse :class:`sync_validator.ValidationIssue` so downstream tooling
(``/health-check``, ``/sync``, GitHub Actions reports) can render a single
unified shape.

CLI usage::

    python -m hook_path_validator \\
        --global-settings ~/.claude/settings.json \\
        --local-settings .claude/settings.local.json \\
        --project-root .

Exit code is ``1`` when any error severity issue is detected (or when any
warning is detected and ``--strict`` was passed), ``0`` otherwise.

Issue: #950
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Iterator, Optional

# Reuse the sync_validator data shape so all post-sync tooling speaks the same
# language. Mirror the dual-import pattern used elsewhere in this codebase
# (sync_validator.py:31-42) so the module works both in dev and in installed
# environments.
try:  # pragma: no cover - import path selection
    from plugins.autonomous_dev.lib.sync_validator import ValidationIssue
except ImportError:  # pragma: no cover - import path selection
    try:
        from sync_validator import ValidationIssue
    except ImportError:  # pragma: no cover - import path selection
        # Last-resort fallback: define a compatible shim so the module remains
        # importable even when sync_validator is unavailable. This mirrors the
        # public attributes used downstream.
        from dataclasses import dataclass

        @dataclass
        class ValidationIssue:  # type: ignore[no-redef]
            severity: str
            category: str
            message: str
            file_path: Optional[str] = None
            line_number: Optional[int] = None
            auto_fixable: bool = False
            fix_action: Optional[str] = None


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Recognised script extensions. ``.py`` is the most common, followed by shell
# variants. Order matters when scanning interpreters.
SCRIPT_EXTENSIONS: tuple[str, ...] = (".py", ".sh", ".bash", ".zsh")

# Shell-script extensions that require the execute bit on POSIX.
SHELL_EXTENSIONS: tuple[str, ...] = (".sh", ".bash", ".zsh")

# Known interpreters whose first script-like argument is the actual hook target.
INTERPRETERS: tuple[str, ...] = (
    "python3",
    "python",
    "bash",
    "sh",
    "zsh",
)

# Path-style substrings that are no longer permitted in hook commands. The
# canonical form (Issue #996, Phase B) is
# ``"$(git rev-parse --show-toplevel)/.claude/hooks/<NAME>.<py|sh>"`` which
# resolves to the project-local hook directory populated by
# ``scripts/deploy-all.sh`` / ``sync_settings_hooks.py``. The two patterns
# below are explicitly disallowed because they either bypass the worktree
# (``--git-common-dir`` resolves to the main repo's git dir, breaking
# project-local hook deployments) or hardcode the global cache path
# (``~/.claude/`` was the v3.x default but cannot be project-scoped).
DISALLOWED_PATH_SUBSTRINGS: tuple[tuple[str, str, str], ...] = (
    (
        "~/.claude/",
        "error",
        "use $(git rev-parse --show-toplevel)/.claude/hooks/",
    ),
    (
        "--git-common-dir",
        "error",
        "use --show-toplevel for project-local resolution",
    ),
)

# Pattern: `VAR=value` style env prefix tokens that shlex emits before argv.
_ENV_PREFIX_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")

# Pattern: any remaining ``$VAR`` or ``${VAR}`` token after expansion. If this
# survives :func:`expand_path`, the variable was not defined anywhere.
_UNRESOLVED_VAR_RE = re.compile(r"\$\{?([A-Z_][A-Z0-9_]*)\}?")


# --------------------------------------------------------------------------
# Command parsing
# --------------------------------------------------------------------------


def parse_hook_command(command: str) -> tuple[dict[str, str], list[str]]:
    """Split a hook command into env-var prefix and remaining argv tokens.

    Args:
        command: The raw command string from settings (e.g.
            ``"FOO=bar python3 /path/hook.py"``).

    Returns:
        A two-tuple ``(env_vars, tokens)`` where ``env_vars`` maps any leading
        ``VAR=value`` assignments (per POSIX shell convention) and ``tokens``
        is the remaining argv list.
    """
    if not command or not command.strip():
        return {}, []

    try:
        raw_tokens = shlex.split(command, posix=True)
    except ValueError:
        # shlex chokes on unbalanced quotes; treat the whole command as
        # un-parseable and let the caller surface "unable to parse" findings
        # via the absence of a script path.
        return {}, []

    env_vars: dict[str, str] = {}
    idx = 0
    while idx < len(raw_tokens):
        match = _ENV_PREFIX_RE.match(raw_tokens[idx])
        if not match:
            break
        env_vars[match.group(1)] = match.group(2)
        idx += 1

    return env_vars, raw_tokens[idx:]


def extract_script_path(tokens: list[str]) -> Optional[str]:
    """Pick the script path out of argv tokens.

    Strategy:
        1. If the first token is a known interpreter (``python3``, ``bash``…),
           skip flag-tokens (``-c``, ``-u``, ``-m``…) and return the first
           non-flag argument.
        2. Otherwise, return the first token whose suffix is in
           :data:`SCRIPT_EXTENSIONS`.
        3. As a final fallback, return the first non-flag token (covers
           direct invocations of executable scripts without an extension).

    Args:
        tokens: Argv tokens after env-prefix stripping.

    Returns:
        The script path string or ``None`` if no script-like token exists.
    """
    if not tokens:
        return None

    first = tokens[0]
    first_basename = os.path.basename(first)

    if first_basename in INTERPRETERS:
        # Skip the interpreter and any flag tokens (e.g. ``-u``, ``-m foo``).
        for tok in tokens[1:]:
            if tok.startswith("-"):
                continue
            return tok
        return None

    # Heuristic: return the first token with a recognised script extension.
    for tok in tokens:
        if tok.startswith("-"):
            continue
        if any(tok.endswith(ext) for ext in SCRIPT_EXTENSIONS):
            return tok

    # Fallback: first non-flag token (e.g. a direct binary invocation).
    for tok in tokens:
        if not tok.startswith("-"):
            return tok
    return None


# --------------------------------------------------------------------------
# Path expansion / resolution
# --------------------------------------------------------------------------


def expand_path(raw: str, project_root: Path) -> tuple[Path, list[str]]:
    """Expand env vars and home shorthand in a path string.

    Substitution order:
        1. ``$CLAUDE_PROJECT_DIR`` / ``${CLAUDE_PROJECT_DIR}`` -> ``project_root``
        2. ``$CLAUDE_PLUGIN_ROOT`` / ``${CLAUDE_PLUGIN_ROOT}`` ->
           ``project_root / 'plugins' / 'autonomous-dev'``
        3. :func:`os.path.expanduser` (handles ``~``)
        4. :func:`os.path.expandvars` (handles remaining ``$VAR`` references)
        5. Re-scan for any surviving ``$VAR`` tokens — those are unresolved.

    Args:
        raw: Raw path string from a hook command.
        project_root: Project root used to substitute ``CLAUDE_PROJECT_DIR``.

    Returns:
        ``(expanded_path, unresolved_vars)`` — the second element is the list
        of variable names that could not be resolved.
    """
    if not raw:
        return Path(""), []

    # Step 1: project-scoped substitutions (these win over ambient env so a
    # user-set CLAUDE_PROJECT_DIR can't accidentally point us elsewhere).
    project_root_str = str(project_root)
    plugin_root_str = str(project_root / "plugins" / "autonomous-dev")
    expanded = raw
    expanded = expanded.replace("${CLAUDE_PROJECT_DIR}", project_root_str)
    expanded = expanded.replace("$CLAUDE_PROJECT_DIR", project_root_str)
    expanded = expanded.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root_str)
    expanded = expanded.replace("$CLAUDE_PLUGIN_ROOT", plugin_root_str)

    # Step 2: home and remaining env vars.
    expanded = os.path.expanduser(expanded)
    expanded = os.path.expandvars(expanded)

    # Step 3: detect leftover $VAR — these are unresolved.
    unresolved = sorted({m.group(1) for m in _UNRESOLVED_VAR_RE.finditer(expanded)})
    return Path(expanded), unresolved


def safe_resolve(
    path: Path, allowed_roots: list[Path]
) -> tuple[Optional[Path], Optional[str]]:
    """Canonicalise ``path`` while defending against symlink traversal.

    Implements the dual-symlink defence pattern from
    ``archived/sync_to_installed.py``:

    1. ``is_symlink()`` BEFORE ``resolve()`` — catches obvious symlink attacks
       early so we never follow a hostile link in the first place.
    2. ``resolve()`` — canonicalise the path.
    3. ``is_symlink()`` AFTER ``resolve()`` on each parent — catches symlinks
       that were introduced via a parent component.
    4. Whitelist check against ``allowed_roots`` — final containment guard.

    Do NOT use :func:`security_utils.validate_path`: its whitelist rejects
    ``/bin/bash`` and other legitimate shell interpreters. We do
    traversal-only defence here, intentionally permissive about what targets
    are allowed (since the user has already declared them in settings) but
    strict about preventing ``..``-style escapes through symlinks.

    Args:
        path: Pre-expanded path to resolve.
        allowed_roots: Roots within which the canonical target may live. The
            check passes if the canonical path is inside ANY of these roots.
            Pass an empty list to skip whitelist enforcement.

    Returns:
        ``(canonical_path, None)`` on success, ``(None, error_message)`` on
        rejection.
    """
    if not path or str(path) in ("", "."):
        return None, "empty path"

    # Layer 1: pre-resolve symlink check.
    try:
        if path.is_symlink():
            target = path.resolve()
            if allowed_roots and not _is_under_any(target, allowed_roots):
                return None, (
                    f"symlink {path} -> {target} escapes allowed roots "
                    f"({', '.join(str(r) for r in allowed_roots)})"
                )
    except OSError as exc:
        return None, f"cannot stat {path}: {exc}"

    # Layer 2: canonicalise.
    try:
        canonical = path.resolve()
    except (OSError, RuntimeError) as exc:
        return None, f"cannot resolve {path}: {exc}"

    # Layer 3: post-resolve symlink check on parents (a parent may itself be
    # a symlink that resolve() followed transparently).
    for parent in canonical.parents:
        try:
            if parent.is_symlink():
                deeper = parent.resolve()
                if allowed_roots and not _is_under_any(deeper, allowed_roots):
                    return None, (
                        f"parent symlink {parent} -> {deeper} escapes allowed roots"
                    )
        except OSError:
            # Non-fatal: if we can't stat a parent, assume it's fine and let
            # the existence check downstream report a more useful error.
            break

    # Layer 4: whitelist containment.
    if allowed_roots and not _is_under_any(canonical, allowed_roots):
        return None, (
            f"{canonical} is outside allowed roots "
            f"({', '.join(str(r) for r in allowed_roots)})"
        )

    return canonical, None


def _is_under_any(path: Path, roots: list[Path]) -> bool:
    """Return True if ``path`` is inside any of ``roots`` (after resolution)."""
    try:
        path_resolved = path.resolve()
    except (OSError, RuntimeError):
        return False
    for root in roots:
        try:
            root_resolved = root.resolve()
        except (OSError, RuntimeError):
            continue
        try:
            path_resolved.relative_to(root_resolved)
            return True
        except ValueError:
            continue
    return False


# --------------------------------------------------------------------------
# Settings traversal
# --------------------------------------------------------------------------


def iter_hook_commands(
    settings: dict, settings_path: Optional[Path] = None
) -> Iterator[tuple[str, str, str, int]]:
    """Walk a settings dict yielding every ``(event, matcher, command, line)``.

    Args:
        settings: Parsed settings JSON.
        settings_path: Path to the settings file on disk. When provided, the
            file is re-read as text so we can attempt a best-effort line
            number lookup for each command.

    Yields:
        Tuples of ``(event_name, matcher_pattern, command_string,
        line_number)``. ``line_number`` is ``0`` when it cannot be determined.
    """
    raw_text = ""
    if settings_path is not None:
        try:
            raw_text = settings_path.read_text(encoding="utf-8")
        except OSError:
            raw_text = ""

    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return

    for event_name, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher", "")
            hook_list = entry.get("hooks", [])
            if not isinstance(hook_list, list):
                continue
            for hook_def in hook_list:
                if not isinstance(hook_def, dict):
                    continue
                command = hook_def.get("command", "")
                if not isinstance(command, str) or not command.strip():
                    continue

                line_no = 0
                if raw_text:
                    needle = json.dumps(command)[1:-1]  # JSON-escaped form
                    pos = raw_text.find(needle)
                    if pos == -1:
                        pos = raw_text.find(command)
                    if pos != -1:
                        line_no = raw_text.count("\n", 0, pos) + 1

                yield event_name, str(matcher), command, line_no


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def validate_hook_paths(
    global_settings_path: Optional[Path],
    local_settings_path: Optional[Path],
    project_root: Path,
) -> list[ValidationIssue]:
    """Validate hook command paths in the supplied settings files.

    Args:
        global_settings_path: Optional path to ``~/.claude/settings.json``.
        local_settings_path: Optional path to project-local
            ``.claude/settings.local.json``.
        project_root: Project root used for ``$CLAUDE_PROJECT_DIR`` expansion
            and as one of the allowed roots for symlink containment.

    Returns:
        A list of :class:`ValidationIssue` ordered by file then line. Empty
        list means everything is healthy.
    """
    project_root = Path(project_root).expanduser()
    home_claude = (Path.home() / ".claude").resolve()
    allowed_roots = [project_root, home_claude]

    issues: list[ValidationIssue] = []

    # Maps canonical_path -> list of (settings_path, line_no, command).
    # Used to detect global+local duplicate registrations.
    registrations: dict[str, list[tuple[Path, int, str]]] = {}

    for scope_label, settings_path in (
        ("global", global_settings_path),
        ("local", local_settings_path),
    ):
        if settings_path is None:
            continue

        settings_path = Path(settings_path).expanduser()
        if not settings_path.is_file():
            continue

        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="hook",
                    message=f"Invalid JSON in {scope_label} settings: {exc.msg}",
                    file_path=str(settings_path),
                    line_number=exc.lineno,
                    auto_fixable=False,
                    fix_action=f"# fix JSON syntax at {settings_path}:{exc.lineno}",
                )
            )
            continue
        except OSError as exc:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="hook",
                    message=f"Cannot read {scope_label} settings: {exc}",
                    file_path=str(settings_path),
                )
            )
            continue

        for event, matcher, command, line_no in iter_hook_commands(
            settings, settings_path
        ):
            issues.extend(
                _validate_one_command(
                    command=command,
                    event=event,
                    matcher=matcher,
                    settings_path=settings_path,
                    line_no=line_no,
                    project_root=project_root,
                    allowed_roots=allowed_roots,
                    registrations=registrations,
                )
            )

    # Cross-scope duplicate detection.
    for canonical, regs in registrations.items():
        if len(regs) < 2:
            continue
        # Only emit a duplicate finding when the same canonical path appears
        # in two distinct settings files (global + local).
        distinct_files = {str(reg[0]) for reg in regs}
        if len(distinct_files) < 2:
            continue
        first_settings, first_line, _ = regs[0]
        other_settings_list = sorted(distinct_files - {str(first_settings)})
        other = other_settings_list[0]
        # Find the line number on the "other" side too.
        other_line = next(
            (line for path, line, _ in regs if str(path) == other),
            0,
        )
        issues.append(
            ValidationIssue(
                severity="warning",
                category="hook",
                message=(
                    f"Hook {canonical} is registered in both "
                    f"{first_settings} and {other} (will fire twice)"
                ),
                file_path=other,
                line_number=other_line,
                auto_fixable=False,
                fix_action=(
                    f"# remove duplicate hook command at {other}:{other_line} "
                    f"(also registered at {first_settings}:{first_line})"
                ),
            )
        )

    return issues


def _validate_path_style(
    *,
    command: str,
    raw_script: Optional[str],
    event: str,
    matcher: str,
    settings_path: Path,
    line_no: int,
) -> list[ValidationIssue]:
    """Flag hook commands using disallowed path styles (Issue #996).

    The canonical pattern is
    ``"$(git rev-parse --show-toplevel)/.claude/hooks/<NAME>.<py|sh>"``.
    Two legacy patterns are now rejected:

    * ``~/.claude/...`` — hardcodes the global cache path; cannot be
      project-scoped per Issue #944's deduplication rationale.
    * ``--git-common-dir`` — resolves to the *main* repository's git dir,
      which breaks worktree-local hook deployments.

    Args:
        command: Full raw hook command string.
        raw_script: Path-shaped argv token extracted by
            :func:`extract_script_path`. ``None`` skips the check.
        event: Hook event name (e.g. ``PreToolUse``).
        matcher: Hook matcher pattern.
        settings_path: Path to the settings file containing this command.
        line_no: Best-effort line number for the command in the file.

    Returns:
        A list of :class:`ValidationIssue` (one per disallowed substring
        match). Empty list when the path style is canonical.
    """
    issues: list[ValidationIssue] = []
    if not raw_script:
        return issues

    # Restrict the check to script-shaped tokens. Some commands (e.g. plain
    # ``echo``) intentionally have no script suffix and should not trip
    # path-style heuristics.
    suffix = Path(raw_script).suffix.lower()
    if suffix not in SCRIPT_EXTENSIONS:
        return issues

    for substring, severity, hint in DISALLOWED_PATH_SUBSTRINGS:
        if substring in command:
            issues.append(
                ValidationIssue(
                    severity=severity,
                    category="hook",
                    message=(
                        f"[{event}/{matcher}] Hook command uses disallowed "
                        f"path style ({substring!r}): {raw_script}"
                    ),
                    file_path=str(settings_path),
                    line_number=line_no,
                    auto_fixable=False,
                    fix_action=f"# {hint}",
                )
            )
    return issues


def _validate_one_command(
    *,
    command: str,
    event: str,
    matcher: str,
    settings_path: Path,
    line_no: int,
    project_root: Path,
    allowed_roots: list[Path],
    registrations: dict[str, list[tuple[Path, int, str]]],
) -> list[ValidationIssue]:
    """Validate a single hook command string. Internal helper."""
    issues: list[ValidationIssue] = []

    _env_vars, tokens = parse_hook_command(command)
    if not tokens:
        issues.append(
            ValidationIssue(
                severity="error",
                category="hook",
                message=(
                    f"[{event}/{matcher}] Cannot parse hook command "
                    f"(unbalanced quotes?): {command!r}"
                ),
                file_path=str(settings_path),
                line_number=line_no,
                auto_fixable=False,
                fix_action=f"# fix command syntax at {settings_path}:{line_no}",
            )
        )
        return issues

    raw_script = extract_script_path(tokens)

    # Path-style policy check (Issue #996, Phase B). Runs even when the
    # script does not exist on disk so policy violations surface in clean
    # checkouts, but only flags script-shaped tokens (``echo`` lines and
    # other builtins are intentionally exempt).
    issues.extend(
        _validate_path_style(
            command=command,
            raw_script=raw_script,
            event=event,
            matcher=matcher,
            settings_path=settings_path,
            line_no=line_no,
        )
    )

    if not raw_script:
        # No script-like token: nothing more to validate (could be a builtin
        # like ``true`` — we don't flag this).
        return issues

    expanded_path, unresolved_vars = expand_path(raw_script, project_root)

    # Unresolved env vars: 1 issue per distinct variable.
    for var in unresolved_vars:
        issues.append(
            ValidationIssue(
                severity="error",
                category="hook",
                message=(
                    f"[{event}/{matcher}] Hook command references "
                    f"unresolved environment variable ${var}: {raw_script}"
                ),
                file_path=str(settings_path),
                line_number=line_no,
                auto_fixable=False,
                fix_action=(
                    f"# define ${var} in shell or settings env block, "
                    f"or hardcode the path at {settings_path}:{line_no}"
                ),
            )
        )

    # If there are unresolved vars, skip the existence check — the path is
    # not yet meaningful.
    if unresolved_vars:
        return issues

    canonical, sym_err = safe_resolve(expanded_path, allowed_roots=allowed_roots)
    if canonical is None:
        # Path might simply not exist — distinguish missing vs traversal.
        if not expanded_path.exists():
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="hook",
                    message=(
                        f"[{event}/{matcher}] Hook script does not exist: "
                        f"{expanded_path}"
                    ),
                    file_path=str(settings_path),
                    line_number=line_no,
                    auto_fixable=False,
                    fix_action=(
                        f"# create file at {expanded_path} or remove hook "
                        f"entry at {settings_path}:{line_no}"
                    ),
                )
            )
        else:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="hook",
                    message=(
                        f"[{event}/{matcher}] Hook script failed traversal "
                        f"defence: {sym_err}"
                    ),
                    file_path=str(settings_path),
                    line_number=line_no,
                    auto_fixable=False,
                    fix_action=(
                        f"# resolve symlink or path traversal at "
                        f"{settings_path}:{line_no}"
                    ),
                )
            )
        return issues

    # Existence check (defensive — safe_resolve sometimes succeeds on a
    # missing path because resolve() is permissive about non-existent files).
    if not canonical.is_file():
        issues.append(
            ValidationIssue(
                severity="error",
                category="hook",
                message=(
                    f"[{event}/{matcher}] Hook script does not exist: "
                    f"{canonical}"
                ),
                file_path=str(settings_path),
                line_number=line_no,
                auto_fixable=False,
                fix_action=(
                    f"# create file at {canonical} or remove hook entry "
                    f"at {settings_path}:{line_no}"
                ),
            )
        )
        return issues

    # Executable bit on shell scripts (POSIX only — no chmod semantics on
    # Windows, so we skip the check there).
    suffix = canonical.suffix.lower()
    if os.name != "nt" and suffix in SHELL_EXTENSIONS:
        if not os.access(canonical, os.X_OK):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="hook",
                    message=(
                        f"[{event}/{matcher}] Shell script is not executable: "
                        f"{canonical}"
                    ),
                    file_path=str(settings_path),
                    line_number=line_no,
                    auto_fixable=True,
                    fix_action=f"chmod +x {canonical}",
                )
            )

    # Track this registration for cross-scope duplicate detection.
    registrations.setdefault(str(canonical), []).append(
        (settings_path, line_no, command)
    )

    return issues


# --------------------------------------------------------------------------
# Output formatting
# --------------------------------------------------------------------------


def format_findings(issues: list[ValidationIssue]) -> str:
    """Render a list of :class:`ValidationIssue` as human-readable text."""
    if not issues:
        return "Hook path validation: OK (0 issues)"

    lines: list[str] = []
    lines.append(f"Hook path validation: {len(issues)} issue(s) found")
    lines.append("=" * 60)

    # Group by severity for readability: errors first, then warnings.
    severity_order = {"error": 0, "warning": 1, "info": 2}
    sorted_issues = sorted(
        issues,
        key=lambda i: (
            severity_order.get(i.severity, 99),
            i.file_path or "",
            i.line_number or 0,
        ),
    )

    for issue in sorted_issues:
        location = issue.file_path or "<unknown>"
        if issue.line_number:
            location += f":{issue.line_number}"
        lines.append(f"{issue.severity.upper()}: {location} - {issue.message}")
        if issue.fix_action:
            lines.append(f"  Suggested fix: {issue.fix_action}")

    return "\n".join(lines)


def _findings_as_json(issues: list[ValidationIssue]) -> str:
    """Serialise findings to JSON for machine consumers."""
    return json.dumps(
        {
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "file_path": i.file_path,
                    "line_number": i.line_number,
                    "auto_fixable": i.auto_fixable,
                    "fix_action": i.fix_action,
                }
                for i in issues
            ],
            "error_count": sum(1 for i in issues if i.severity == "error"),
            "warning_count": sum(1 for i in issues if i.severity == "warning"),
        },
        indent=2,
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argv override (useful in tests). When ``None``,
            :data:`sys.argv` is used.

    Returns:
        Exit code: ``0`` on success, ``1`` when any error severity issue
        exists (or when ``--strict`` is set and any warning exists).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Validate every hook command path declared in Claude settings."
        ),
    )
    parser.add_argument(
        "--global-settings",
        default=str(Path.home() / ".claude" / "settings.json"),
        help="Path to the global settings file (default: %(default)s).",
    )
    parser.add_argument(
        "--local-settings",
        default=str(Path(".claude") / "settings.local.json"),
        help="Path to the project-local settings file (default: %(default)s).",
    )
    parser.add_argument(
        "--project-root",
        default=str(Path.cwd()),
        help="Project root for $CLAUDE_PROJECT_DIR expansion (default: cwd).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (changes exit code only).",
    )
    args = parser.parse_args(argv)

    global_path: Optional[Path] = (
        Path(args.global_settings) if args.global_settings else None
    )
    local_path: Optional[Path] = (
        Path(args.local_settings) if args.local_settings else None
    )
    project_root = Path(args.project_root)

    issues = validate_hook_paths(
        global_settings_path=global_path,
        local_settings_path=local_path,
        project_root=project_root,
    )

    if args.json:
        print(_findings_as_json(issues))
    else:
        print(format_findings(issues))

    has_error = any(i.severity == "error" for i in issues)
    has_warning = any(i.severity == "warning" for i in issues)
    if has_error or (args.strict and has_warning):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
