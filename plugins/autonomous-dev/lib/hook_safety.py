"""Hook safety helpers — graceful degradation for hook failures.

This module formalises a pattern that has accreted ad-hoc across the hook
suite: "never let the hook itself become the reason Claude Code is blocked."
See ``unified_session_tracker.py`` (>20 ``try``/``except`` blocks wrapping
non-critical work) and ``enforce_prunable_threshold.py`` (lib-path resolver
with installed-location fallback at lines 23-45) for the prior art that this
module formalises.

Two failure modes motivate this module (Issue #953, supersedes #946 + #947):

1. **Hook script missing or its imports broken.** Python raises out of the
   hook process; Claude Code surfaces the traceback as a hook-block message
   like ``UserPromptSubmit operation blocked by hook: [Errno 2] No such file
   or directory``. There is no in-product recovery path for the user.

2. **Hook tells the user to run a slash command that is not registered.**
   The user is in a deadlock between a hook demanding command X and command
   X not existing on disk.

Mode 1 is addressed by :func:`safe_main`, which wraps a hook's ``main()``
function and converts any unhandled exception into ``SystemExit(0)`` plus a
``[hook warning] ...`` line on stderr. The hook's success path (including
explicit ``int`` return values and explicit ``SystemExit``) is preserved
verbatim — the wrap is a pure outer safety net.

Mode 2 is addressed by :func:`command_registered`, which probes the standard
slash-command lookup paths. Hooks that would otherwise issue a
``deny`` decision telling the user to run ``/foo`` MUST first call
``command_registered("foo")`` and downgrade the deny to a soft warning when
the command is missing — otherwise the user is wedged.

Shebang note: this fix also requires every hook to use
``#!/usr/bin/env python3`` rather than ``#!/usr/bin/env -S uv run --script``.
A pinned interpreter (``uv``) is itself a deadlock cause: if ``uv`` is not on
PATH, the hook never reaches the safe_main wrap. The standard
``python3`` shebang falls over to whatever interpreter PATH provides.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable, Optional


# Hooks that issue deny decisions referencing a slash command MUST consult
# this module to ensure the command exists. The fail-mode for the lookup
# itself is *fail-CLOSED* (return True): if we cannot decide whether the
# command is registered, assume it IS registered so the existing security
# barrier still fires. This avoids a downgrade-via-error attack where a
# malformed plugins manifest causes the deny path to be silently disabled.


def safe_main(fn: Callable[[], Optional[int]]) -> None:
    """Run a hook's ``main()`` function with a graceful-failure outer wrap.

    Behaviour:

    * **Success path preserved.** If ``fn`` returns ``None`` the process exits
      with status 0. If ``fn`` returns an ``int`` the process exits with that
      status (preserves block/warn semantics for hooks that already use
      ``return 1``/``return 2`` patterns).
    * **Explicit ``SystemExit`` propagates.** If ``fn`` raises ``SystemExit``
      it passes through unchanged — this is a deliberate exit, not a crash.
    * **``KeyboardInterrupt`` propagates.** ``Ctrl+C`` MUST NOT be silently
      swallowed (debugging UX).
    * **Other exceptions are converted to exit 0 + stderr warning.** This is
      the core of the safety net: a missing import, a typo, or a runtime
      bug in the hook itself MUST NOT block Claude Code. A warning line of
      the form ``[hook warning] <hook_name>: <ExceptionType>: <message>`` is
      written to stderr so operators can detect failures.

    Args:
        fn: The hook's ``main`` function. Conventionally takes no arguments
            and returns either ``None`` or an ``int`` exit code.

    Raises:
        SystemExit: Always raised at exit (caught by the Python runtime).

    Example::

        def main() -> int:
            ...
            return 0

        if __name__ == "__main__":
            safe_main(main)
    """
    # Identify the calling hook for the warning message. We walk one frame
    # up so the warning names the hook file, not this library.
    try:
        caller_file = sys._getframe(1).f_globals.get("__file__", "<unknown>")
        hook_name = Path(caller_file).name
    except Exception:
        hook_name = "<unknown hook>"

    try:
        result = fn()
    except SystemExit:
        # Explicit SystemExit (including from sys.exit(N)) is not a crash —
        # the hook chose its exit code deliberately. Preserve it.
        raise
    except KeyboardInterrupt:
        # Never swallow Ctrl+C. Operators interrupting a hook deserve to
        # see the interrupt propagate.
        raise
    except BaseException as exc:  # noqa: BLE001 — deliberately broad for safety net
        # Convert any other failure into a warning + exit 0. The hook MUST
        # NOT become the reason Claude Code is blocked.
        warning = (
            f"[hook warning] {hook_name}: "
            f"{type(exc).__name__}: {exc}\n"
            f"[hook warning] Hook failed but did not block. "
            f"See plugins/autonomous-dev/lib/hook_safety.py for rationale."
        )
        print(warning, file=sys.stderr)
        sys.exit(0)

    # Preserve int return semantics (return 1 / return 2 patterns).
    if isinstance(result, int):
        sys.exit(result)
    sys.exit(0)


def _strip_leading_slash(name: str) -> str:
    """Return ``name`` without a leading ``/``."""
    return name[1:] if name.startswith("/") else name


def _check_command_dir(directory: Path, command_name: str) -> bool:
    """Return True iff ``directory`` contains ``<command_name>.md``.

    Defense-in-depth (Issue #954, M-01): ``command_name`` is a slash-command
    identifier, never a path. Reject any input containing path separators or
    ``..`` traversal segments outright, then use ``Path.resolve()`` as a
    backstop against symlink-based escapes. Without these guards a caller
    that ever passes user-controlled input could read arbitrary files
    relative to ``directory`` (e.g. ``"../../../etc/passwd"`` would resolve
    to ``/etc/passwd.md`` and ``.is_file()`` would happily report on it).
    """
    # Primary guard: slash-command names MUST NOT contain path components.
    if "/" in command_name or "\\" in command_name or ".." in command_name:
        return False
    try:
        if not directory.exists() or not directory.is_dir():
            return False
        candidate = directory / f"{command_name}.md"
        # Backstop: symlinks inside ``directory`` could still escape. Resolve
        # both paths (non-strict so non-existent files don't raise) and verify
        # the candidate remains inside ``directory``.
        try:
            candidate_resolved = candidate.resolve(strict=False)
            dir_resolved = directory.resolve(strict=False)
        except (OSError, RuntimeError):
            # Resolution failure (e.g. symlink loop) — treat as unknown.
            return False
        dir_prefix = str(dir_resolved) + os.sep
        if (
            not str(candidate_resolved).startswith(dir_prefix)
            and candidate_resolved != dir_resolved
        ):
            return False
        return candidate.is_file()
    except OSError:
        # Permission denied, broken symlink, etc. Treat as "unknown" — the
        # caller is responsible for its own fail-CLOSED policy via the outer
        # try/except in command_registered.
        return False


def _check_installed_plugins(plugins_manifest: Path, command_name: str) -> bool:
    """Return True iff ``plugins_manifest`` declares ``command_name``.

    The manifest format is the standard Claude Code installed-plugins JSON:
    a top-level dict with a ``commands`` array of entries that have a
    ``name`` field. Bad JSON or missing keys return False (caller's outer
    handler will fail-CLOSED on a true exception).
    """
    if not plugins_manifest.is_file():
        return False
    try:
        data = json.loads(plugins_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # Corrupt manifest is treated as "no info" rather than crashing. The
        # outer try/except in command_registered() will fail-CLOSED.
        return False

    # Search a few plausible shapes — the spec is loose about manifest format.
    if isinstance(data, dict):
        commands = data.get("commands", [])
        if isinstance(commands, list):
            for entry in commands:
                if isinstance(entry, dict) and entry.get("name") == command_name:
                    return True
                if isinstance(entry, str) and entry == command_name:
                    return True
        # Some manifests may store commands under an installed_plugins map.
        installed = data.get("installed_plugins") or data.get("plugins") or {}
        if isinstance(installed, dict):
            for plugin_data in installed.values():
                if not isinstance(plugin_data, dict):
                    continue
                plugin_commands = plugin_data.get("commands", [])
                if not isinstance(plugin_commands, list):
                    continue
                for entry in plugin_commands:
                    if isinstance(entry, dict) and entry.get("name") == command_name:
                        return True
                    if isinstance(entry, str) and entry == command_name:
                        return True
    return False


def command_registered(name: str) -> bool:
    """Return True iff slash command ``name`` is registered on this machine.

    Lookup order (first match wins):

    1. **Project-local commands**: ``./.claude/commands/<name>.md`` relative
       to ``os.getcwd()``.
    2. **User-global commands**: ``~/.claude/commands/<name>.md``.
    3. **Installed plugins manifest**: ``~/.claude/installed_plugins.json``,
       ``~/.claude/plugins/installed_plugins.json`` — entries are searched
       under ``commands``, ``installed_plugins``, or ``plugins`` keys.

    The leading ``/`` on ``name`` is optional — ``"create-issue"`` and
    ``"/create-issue"`` are equivalent.

    **Fail-mode is CLOSED.** If any unexpected exception bubbles out of the
    lookup, this function returns ``True`` (assume the command IS registered).
    Rationale: callers use this to decide whether to issue a ``deny``
    decision. Returning ``True`` on lookup error preserves the existing
    security barrier rather than letting a malformed manifest silently
    disable the deny path. See module docstring.

    Args:
        name: Slash command name, with or without a leading ``/``.

    Returns:
        ``True`` if the command is registered (or if the lookup itself
        failed); ``False`` only when we are confident the command is
        genuinely missing.
    """
    try:
        command_name = _strip_leading_slash(name)
        if not command_name:
            return True  # Empty name → can't say it's missing.

        # Defense-in-depth chokepoint (Issue #954, M-01): slash-command names
        # are NEVER paths. Reject any name containing path separators or
        # ``..`` traversal segments before *any* filesystem or manifest
        # lookup. This is fail-OPEN (returning False) on purpose — the
        # caller asked about an obviously invalid command name, so we are
        # confident it does not exist as a real registered command.
        if "/" in command_name or "\\" in command_name or ".." in command_name:
            return False

        # 1. Project-local commands.
        try:
            cwd = Path(os.getcwd())
        except (FileNotFoundError, OSError):
            cwd = None
        if cwd is not None:
            project_dir = cwd / ".claude" / "commands"
            if _check_command_dir(project_dir, command_name):
                return True

        # 2. User-global commands.
        try:
            home = Path.home()
        except (RuntimeError, OSError):
            home = None
        if home is not None:
            global_dir = home / ".claude" / "commands"
            if _check_command_dir(global_dir, command_name):
                return True

            # 3. Installed plugins manifest — try standard locations.
            for manifest_path in (
                home / ".claude" / "installed_plugins.json",
                home / ".claude" / "plugins" / "installed_plugins.json",
            ):
                if _check_installed_plugins(manifest_path, command_name):
                    return True

        return False
    except BaseException:  # noqa: BLE001 — fail-CLOSED on any unexpected error
        # Fail-CLOSED: assume command IS registered so the deny path fires.
        return True
