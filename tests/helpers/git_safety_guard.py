"""Refuse git-mutating subprocess calls that could land in the real repository.

Issue #1638. The integration tier isolates git operations with a process-global
``os.chdir()`` and then invokes ``subprocess.run(['git', 'commit', ...])`` with no
explicit working directory. When the ``chdir`` does not hold -- an exception before
the restore, fixture ordering, or xdist workers sharing a process -- git runs
wherever the interpreter actually is, which is the real autonomous-dev checkout.

Four commits titled from a test fixture ("feat(docs): add user authentication with
JWT tokens") swept ~485 files and ~205,000 insertions of the real working tree this
way. The hazard erases its own evidence: ``git status`` reports *clean* afterwards,
because everything got committed.

This module answers one question -- "could this subprocess call mutate the real
repository?" -- and is deliberately separate from the conftest that installs it so
that the classification logic can be unit-tested directly.

Policy:
    * A git subcommand is MUTATING unless it appears in the read-only allowlist.
      Default-deny solves the class; an allowlist of "dangerous" verbs would only
      ever cover the members someone remembered to enumerate.
    * A mutating git call is REFUSED when it names no explicit directory (no
      ``cwd=`` kwarg, no ``git -C``/``--git-dir``/``--work-tree``), because such a
      call resolves against the process CWD and is therefore chdir-dependent.
    * A mutating git call is REFUSED when the directory it names resolves inside
      the real repository root.
    * Read-only git (``status``, ``log``, ``rev-parse``, ``diff``, ``show``,
      ``stash list``, ``config --get``, ...) is always PERMITTED. Several tests
      legitimately inspect real repo state, and a guard that blocks ``git status``
      is worse than useless.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

__all__ = [
    "UnsafeGitInvocation",
    "REAL_REPO_ROOT",
    "assess_git_invocation",
    "enforce_git_safety",
]

#: Root of the real autonomous-dev checkout (``tests/helpers/`` -> repo root).
REAL_REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: Shells whose ``-c`` payload is unwrapped and re-inspected.
_SHELL_BINARIES = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish"})

#: Git global options that consume a following value before the subcommand.
_GIT_GLOBAL_OPTS_WITH_VALUE = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
)

#: Git global options that name a working directory.
_GIT_DIR_OPTS = frozenset({"-C", "--git-dir", "--work-tree"})

#: Subcommands whose target directory is a POSITIONAL operand rather than a
#: ``-C``/``--git-dir``/``--work-tree`` flag. ``git init /abs/path`` initialises
#: that path regardless of where the interpreter is chdir'd, so it is not
#: chdir-dependent and refusing it is a false positive -- one that cost 64
#: failures in ``tests/regression/test_protect_sensitive_regression.py``, which
#: passes 76/76 alone and fails only when this tier's session-scoped guard is
#: already installed.
#:
#: A table, not an ``if``: the value is the 0-based index of the target among the
#: non-flag operands, so adding a subcommand is a one-line edit here rather than a
#: condition buried in the classifier.
#:
#: This does NOT weaken the guard. The value found here is fed back through the
#: SAME absolute-path and real-repo checks as an explicit ``-C``: a relative
#: positional target is still refused (it remains chdir-dependent), and
#: ``git init <REAL_REPO_ROOT>`` is still refused.
_POSITIONAL_TARGET_SUBCOMMANDS: Mapping[str, int] = {
    "init": 0,  # git init [<directory>]
    "clone": 1,  # git clone <repository> [<directory>]
}


def _positional_target_dir(subcommand: str, args: Sequence[str]) -> Optional[str]:
    """Return the positional target directory named by ``subcommand``, if any.

    Args:
        subcommand: The git subcommand, e.g. ``"init"``.
        args: The arguments following the subcommand.

    Returns:
        The operand naming the target directory, or None when this subcommand
        takes no positional target or the operand is absent. The result is NOT
        asserted to be safe -- the caller re-checks it exactly as it checks an
        explicit ``-C`` directory.
    """
    index = _POSITIONAL_TARGET_SUBCOMMANDS.get(subcommand)
    if index is None:
        return None
    operands = [token for token in args if not token.startswith("-")]
    if index >= len(operands):
        return None
    return operands[index]

#: Git subcommands that cannot mutate repository state. Everything else is
#: treated as mutating (default-deny). See ``_READ_ONLY_WHEN`` for verbs that are
#: read-only only in a particular form (``stash list``, ``config --get``, ...).
_READ_ONLY_SUBCOMMANDS = frozenset(
    {
        "annotate",
        "bisect",  # inspection driver; `bisect` alone does not write the worktree
        "blame",
        "cat-file",
        "check-attr",
        "check-ignore",
        "check-ref-format",
        "cherry",
        "count-objects",
        "describe",
        "diff",
        "diff-files",
        "diff-index",
        "diff-tree",
        "for-each-ref",
        "fsck",
        "grep",
        "help",
        "log",
        "ls-files",
        "ls-remote",
        "ls-tree",
        "merge-base",
        "name-rev",
        "rev-list",
        "rev-parse",
        "shortlog",
        "show",
        "show-branch",
        "show-ref",
        "status",
        "var",
        "verify-commit",
        "verify-tag",
        "version",
        "whatchanged",
    }
)

#: Verbs that are read-only only in specific forms. Maps subcommand -> a callable
#: taking the argument list after the subcommand and returning True when read-only.
_READ_ONLY_WHEN = {
    "stash": lambda args: bool(args) and args[0] in {"list", "show"},
    "config": lambda args: any(
        a in {"--get", "--get-all", "--get-regexp", "--list", "-l"} for a in args
    ),
    "worktree": lambda args: bool(args) and args[0] == "list",
    "remote": lambda args: not args or args[0] in {"-v", "--verbose", "show"},
    "branch": lambda args: not args or all(a in {"-l", "--list", "-a", "-r", "-v"} for a in args),
    "tag": lambda args: not args or all(a in {"-l", "--list", "-n"} for a in args),
    "reflog": lambda args: not args or args[0] in {"show", "exists"},
    "submodule": lambda args: bool(args) and args[0] == "status",
    "notes": lambda args: bool(args) and args[0] in {"list", "show"},
}


class UnsafeGitInvocation(RuntimeError):
    """A git-mutating subprocess call could have landed in the real repository.

    Raised instead of executing the call. Carries the offending argv and the
    required fix so the failure names its own remedy.
    """


def _tokenise(command: Any, *, shell: bool) -> Optional[list[str]]:
    """Return ``command`` as a token list, or None when it cannot be inspected.

    Args:
        command: The ``args`` value handed to ``subprocess.run``/``Popen``.
        shell: Whether the call requested shell interpretation.

    Returns:
        A list of string tokens, or None when the command is not inspectable
        (for example a file descriptor or an opaque non-string sequence).
    """
    if isinstance(command, (str, bytes)):
        text = command.decode() if isinstance(command, bytes) else command
        try:
            return shlex.split(text)
        except ValueError:
            # Unbalanced quotes: fall back to a whitespace split rather than
            # silently declining to inspect the call.
            return text.split()
    if isinstance(command, Path):
        return [str(command)]
    if isinstance(command, Iterable):
        tokens: list[str] = []
        for item in command:
            if isinstance(item, bytes):
                tokens.append(item.decode())
            elif isinstance(item, (str, Path, int)):
                tokens.append(str(item))
            else:
                return None
        return tokens
    return None


def _unwrap_shell(tokens: Sequence[str]) -> Optional[list[str]]:
    """Return the git argv hidden inside ``bash -c "git commit ..."``, if any."""
    if len(tokens) < 3:
        return None
    if Path(tokens[0]).name not in _SHELL_BINARIES:
        return None
    for index, token in enumerate(tokens[1:], start=1):
        if token == "-c" and index + 1 < len(tokens):
            try:
                inner = shlex.split(tokens[index + 1])
            except ValueError:
                inner = tokens[index + 1].split()
            return inner or None
    return None


def _parse_git(tokens: Sequence[str]) -> Optional[tuple[str, list[str], Optional[str]]]:
    """Split a git argv into ``(subcommand, remaining_args, explicit_directory)``.

    Returns None when ``tokens`` is not a git invocation. Returns a subcommand of
    ``""`` for bare ``git``/``git --version``, which carry no repository effect.
    """
    if not tokens:
        return None
    if Path(tokens[0]).name != "git":
        return None

    explicit_dir: Optional[str] = None
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("-"):
            break
        if "=" in token and token.split("=", 1)[0] in _GIT_GLOBAL_OPTS_WITH_VALUE:
            name, value = token.split("=", 1)
            if name in _GIT_DIR_OPTS:
                explicit_dir = value
            index += 1
            continue
        if token in _GIT_GLOBAL_OPTS_WITH_VALUE:
            if index + 1 < len(tokens):
                if token in _GIT_DIR_OPTS:
                    explicit_dir = tokens[index + 1]
                index += 2
                continue
            index += 1
            continue
        index += 1

    if index >= len(tokens):
        return "", [], explicit_dir
    return tokens[index], list(tokens[index + 1 :]), explicit_dir


def _is_mutating(subcommand: str, args: Sequence[str]) -> bool:
    """Return True when this git subcommand can modify repository state."""
    if not subcommand:
        return False
    if subcommand in _READ_ONLY_SUBCOMMANDS:
        return False
    conditional = _READ_ONLY_WHEN.get(subcommand)
    if conditional is not None and conditional(list(args)):
        return False
    return True


def _resolve(directory: str) -> Path:
    """Resolve ``directory`` against the process CWD without touching the disk."""
    path = Path(directory)
    if not path.is_absolute():
        path = Path(os.getcwd()) / path
    # ``resolve()`` on a non-existent path is fine on Python 3.6+ (strict=False).
    return path.resolve()


def _inside_real_repo(path: Path) -> bool:
    """Return True when ``path`` is the real repo root or lives beneath it."""
    try:
        return path == REAL_REPO_ROOT or path.is_relative_to(REAL_REPO_ROOT)
    except (OSError, ValueError):  # pragma: no cover - defensive
        return False


def assess_git_invocation(
    command: Any,
    kwargs: Mapping[str, Any],
    *,
    caller: str = "subprocess.run",
) -> Optional[str]:
    """Judge one subprocess invocation.

    Args:
        command: The ``args`` value passed to ``subprocess.run``/``Popen``.
        kwargs: The keyword arguments of that call (``cwd``, ``shell``, ...).
        caller: Name of the intercepted callable, used in the refusal message.

    Returns:
        None when the call is safe to execute, otherwise a refusal message
        naming the offending call and the required fix.
    """
    tokens = _tokenise(command, shell=bool(kwargs.get("shell")))
    if not tokens:
        return None

    parsed = _parse_git(tokens)
    if parsed is None:
        inner = _unwrap_shell(tokens)
        if inner is None:
            return None
        parsed = _parse_git(inner)
        if parsed is None:
            return None

    subcommand, args, explicit_dir = parsed
    if explicit_dir is None:
        # ``git init <dir>`` / ``git clone <repo> <dir>`` name their target
        # positionally. Treated identically to ``-C`` from here on, including the
        # relative-path and real-repo refusals below.
        explicit_dir = _positional_target_dir(subcommand, args)
    if not _is_mutating(subcommand, args):
        return None

    rendered = " ".join(shlex.quote(token) for token in tokens)
    cwd_kwarg = kwargs.get("cwd")

    if cwd_kwarg is None and explicit_dir is None:
        return (
            f"Refusing git '{subcommand}' with no explicit working directory.\n"
            f"  Call    : {caller}({rendered})\n"
            f"  Problem : this mutating git call resolves against the process CWD, so it\n"
            f"            runs in whatever directory os.chdir() last left the interpreter.\n"
            f"            When that chdir does not hold it commits the REAL repository at\n"
            f"            {REAL_REPO_ROOT}.\n"
            f"  Fix     : pass cwd=<tmpdir> to {caller}(...), e.g.\n"
            f"            {caller}([...], cwd=tmp_path, ...)\n"
            f"  Context : Issue #1638 -- four fixture-titled commits swept ~485 files of the\n"
            f"            real working tree this way. git status reports clean afterwards."
        )

    named = explicit_dir if cwd_kwarg is None else cwd_kwarg
    resolved = _resolve(str(named))

    if cwd_kwarg is None and explicit_dir is not None and not Path(explicit_dir).is_absolute():
        return (
            f"Refusing git '{subcommand}': directory '{explicit_dir}' is relative.\n"
            f"  Call    : {caller}({rendered})\n"
            f"  Problem : a relative -C/--git-dir path still resolves against the process\n"
            f"            CWD, so the call remains chdir-dependent (resolved: {resolved}).\n"
            f"  Fix     : pass cwd=<tmpdir> to {caller}(...) or use an absolute directory."
        )

    if _inside_real_repo(resolved):
        return (
            f"Refusing git '{subcommand}' targeting the real repository.\n"
            f"  Call    : {caller}({rendered})\n"
            f"  Target  : {resolved}\n"
            f"  Problem : this mutating git call would run inside the real autonomous-dev\n"
            f"            checkout at {REAL_REPO_ROOT}.\n"
            f"  Fix     : pass cwd=<tmpdir> to {caller}(...) so the call targets a scratch\n"
            f"            repository created by the test.\n"
            f"  Context : Issue #1638."
        )

    return None


def enforce_git_safety(
    command: Any,
    kwargs: Mapping[str, Any],
    *,
    caller: str = "subprocess.run",
) -> None:
    """Raise :class:`UnsafeGitInvocation` when the call could hit the real repo.

    Args:
        command: The ``args`` value passed to ``subprocess.run``/``Popen``.
        kwargs: The keyword arguments of that call.
        caller: Name of the intercepted callable, used in the refusal message.

    Raises:
        UnsafeGitInvocation: If the invocation mutates git state without naming a
            safe explicit working directory.
    """
    reason = assess_git_invocation(command, kwargs, caller=caller)
    if reason is not None:
        raise UnsafeGitInvocation(reason)
