"""Test isolation of the two production state trees (Issue #1779, AC1).

One topic, three mechanisms, measured contaminated on 2026-09-12:

* :func:`hook_subprocess_env` — the ONE way to build an environment for a test
  that spawns a hook. A subprocess inherits conftest's redirects only when its
  ``env=`` derives from ``os.environ``; ``env={**hook_env}`` in
  ``test_issue_1357_general_purpose_warning.py`` threw both away, putting six
  ``session_id="test-session"`` records into the real activity log and deleting
  the live sentinel.
* :func:`activity_root_inference_is_the_subject` — the opt-out for the few tests
  whose SUBJECT is the resolution itself.
* :func:`snapshot_tree` / :func:`describe_tree_leak` — the session-finish guard.
  Whole tree, SHA-256 (an append landing on the same byte count is still
  contamination), ``None`` normalising to ``{}`` so a suite that CREATES the tree
  is still reported. Aimed at the wrong root it reports clean, which is why a
  ``None`` verdict is never evidence on its own; both arms and that control are
  in ``tests/regression/test_issue_1779_connected_core.py``. The trees are
  process-GLOBAL, so :func:`session_is_nested` keeps the verdict OUTERMOST.

Exemptions are keyed on IDENTITY, never on a path carve-out, and every derivation
FAILS CLOSED. Context: ``docs/PIPELINE-EVIDENCE-INTEGRITY.md``.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple, Union

import pytest

#: Only names with a measured consumer. ``_OVERRIDING_VARS`` and
#: ``_VALIDATOR_ARTIFACT_SUBDIR`` are deliberately absent: both had 0 importers,
#: so exporting them advertised surface nothing consumed.
__all__ = [
    "ISOLATION_VARS",
    "SESSION_DEPTH_ENV",
    "HookEnvIsolationError",
    "hook_subprocess_env",
    "activity_root_inference_is_the_subject",
    "snapshot_tree",
    "describe_tree_leak",
    "live_run_artifact_dir",
    "next_session_depth",
    "session_is_nested",
]

#: Variables that must reach every hook subprocess, in conftest's spelling.
ISOLATION_VARS = ("AUTONOMOUS_DEV_ACTIVITY_LOG_DIR", "PIPELINE_STATE_FILE")

#: How many pytest sessions enclose this one, exported to every child process.
SESSION_DEPTH_ENV = "AUTONOMOUS_DEV_PYTEST_SESSION_DEPTH"

#: Variables that outrank an inferred activity root, in resolver order.
_OVERRIDING_VARS = ("AUTONOMOUS_DEV_ACTIVITY_LOG_DIR", "CLAUDE_PROJECT_DIR")

#: The subdirectory the coordinator writes validator artifacts to and
#: ``pipeline_completion_state._missing_validator_artifacts`` reads from.
_VALIDATOR_ARTIFACT_SUBDIR = "validators"

#: Run-id allowlist, identical to ``pipeline_completion_state._RUN_ID_RE``: a
#: value that resolver would refuse must never become an exemption.
_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# tests/helpers/<this file> -> helpers -> tests -> repo root
_LIVE_CLAUDE_DIR = Path(__file__).resolve().parents[2] / ".claude"


class HookEnvIsolationError(RuntimeError):
    """The environment would let a hook subprocess reach production state."""


def _reaches_live_state(value: str) -> bool:
    """Whether *value* names a path inside the live repository's ``.claude/``."""
    try:
        candidate = Path(value).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return True  # Unresolvable cannot be shown safe. Fail closed.
    return candidate == _LIVE_CLAUDE_DIR or _LIVE_CLAUDE_DIR in candidate.parents


def hook_subprocess_env(
    overlay: Optional[Mapping[str, object]] = None,
) -> Dict[str, str]:
    """Build a hook subprocess environment that inherits the test isolation.

    Args:
        overlay: Variables the test controls, applied on top of ``os.environ``.

    Returns:
        A fresh environment dict carrying both isolation variables.

    Raises:
        HookEnvIsolationError: If either isolation variable ends up blank or
            resolves inside the live ``.claude/`` tree. A refusal, not a warning:
            a hook that writes production state cannot be un-written.
    """
    env = os.environ.copy()
    for key, value in (overlay or {}).items():
        env[key] = str(value)

    blank = [name for name in ISOLATION_VARS if not env.get(name, "").strip()]
    if blank:
        raise HookEnvIsolationError(
            f"hook subprocess environment is missing {blank}; the hook would "
            f"resolve the REAL {_LIVE_CLAUDE_DIR} tree (Issue #1779, AC1).\n"
            "REQUIRED NEXT ACTION: do not build an env from a bare dict; call "
            "hook_subprocess_env() and put your variables in `overlay`."
        )

    escaping = sorted(name for name in ISOLATION_VARS if _reaches_live_state(env[name]))
    if escaping:
        raise HookEnvIsolationError(
            f"{escaping} point inside the live {_LIVE_CLAUDE_DIR} tree, so a hook "
            "subprocess would append to the production activity log or overwrite "
            "the live pipeline sentinel (Issue #1779, AC1).\n"
            "REQUIRED NEXT ACTION: point them at tmp_path, not the repository."
        )
    return env


@pytest.fixture(autouse=True)
def activity_root_inference_is_the_subject(monkeypatch):
    """Clear the variables that outrank an inferred activity root.

    Autouse within the importing module only. Safe because every such test
    supplies its own ``tmp_path`` root, which the session-finish guard verifies.
    """
    for name in _OVERRIDING_VARS:
        monkeypatch.delenv(name, raising=False)


def next_session_depth(inherited: Optional[str]) -> str:
    """The marker to export to children; anything but a positive int reads as 0."""
    if not isinstance(inherited, str):
        return "1"
    try:
        depth = int(inherited.strip())
    except ValueError:
        return "1"
    return str(depth + 1) if depth > 0 else "1"


def session_is_nested(inherited: Optional[str]) -> bool:
    """Whether an enclosing pytest session already watches the shared trees.

    Derived FROM :func:`next_session_depth`, so the exported value and this
    verdict cannot disagree. Absent, blank, zero, negative or unparseable reads
    as OUTERMOST, which keeps the leak guard ACTIVE — fail closed.
    """
    return next_session_depth(inherited) != "1"


def snapshot_tree(directory: Union[str, Path]) -> Optional[Dict[str, str]]:
    """SHA-256 every regular file under *directory*, keyed by relative path.

    Returns ``None`` when the directory does not exist or cannot be read;
    :func:`describe_tree_leak` treats ``None`` and ``{}`` identically.
    """
    root = Path(directory)
    if not root.is_dir():
        return None
    out: Dict[str, str] = {}
    try:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                out[str(path.relative_to(root))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
            except OSError:
                # Recorded, not dropped: an unreadable file must not later
                # masquerade as a deletion.
                out[str(path.relative_to(root))] = "<unreadable>"
    except OSError:
        return None
    return out


def live_run_artifact_dir(run_id: Optional[str]) -> Optional[str]:
    """The one directory a LIVE ``/implement`` run owns, or ``None``.

    Validator artifacts land under ``validators/$RUN_ID/`` — the operator's
    pipeline writing its own evidence, not the suite mutating the tree. Strict:
    anything that is not a single safe path segment yields NO exemption.
    """
    if not isinstance(run_id, str):
        return None
    candidate = run_id.strip()
    if not _RUN_ID_RE.match(candidate):
        return None
    return f"{_VALIDATOR_ARTIFACT_SUBDIR}/{candidate}"


def _path_segments(relative_path: str) -> Tuple[str, ...]:
    """Split a snapshot key into segments, accepting either separator.

    Matching one spelling would make every directory exemption silently inert on
    the other platform.
    """
    return tuple(
        segment
        for segment in relative_path.replace("\\", "/").split("/")
        if segment not in ("", ".")
    )


def _is_exempt(
    relative_path: str,
    live_session_id: str,
    exempt_prefixes: Iterable[str],
    exempt_dirs: Iterable[str] = (),
) -> bool:
    """Whether *relative_path* belongs to the LIVE run rather than the suite.

    Two identity-keyed shapes only: a file NAMED ``<prefix><live session id>``,
    and a file nested INSIDE one of *exempt_dirs*. Containment is segment-wise, so
    ``validators/<id>-evil/x`` does not inherit ``validators/<id>``'s exemption.
    """
    if live_session_id and any(
        relative_path == f"{prefix}{live_session_id}" for prefix in exempt_prefixes
    ):
        return True

    segments = _path_segments(relative_path)
    for exempt_dir in exempt_dirs:
        dir_segments = _path_segments(exempt_dir)
        if not dir_segments:
            continue  # An empty exemption would match every path.
        if len(segments) > len(dir_segments) and (
            segments[: len(dir_segments)] == dir_segments
        ):
            return True
    return False


def describe_tree_leak(
    baseline: Optional[Dict[str, str]],
    current: Optional[Dict[str, str]],
    directory: Union[str, Path],
    *,
    label: str,
    remedy: str,
    live_session_id: str = "",
    exempt_prefixes: Iterable[str] = (),
    exempt_dirs: Iterable[str] = (),
) -> Optional[str]:
    """Describe how a watched production tree changed, or ``None`` if clean.

    Args:
        baseline: Snapshot at session start (``None`` = tree absent).
        current: Snapshot at session finish (``None`` = tree absent).
        directory: The tree being watched, for the message.
        label: Short name of the subject, e.g. ``"PRODUCTION ACTIVITY LOG"``.
        remedy: The REQUIRED NEXT ACTION text for this subject.
        live_session_id: The real Claude session id, when known.
        exempt_prefixes: Filename prefixes that, suffixed with
            *live_session_id*, belong to the live session.
        exempt_dirs: Relative directories the LIVE run owns. Empty exempts
            NOTHING — the fail-closed default.

    Returns:
        A finding naming the created, modified and removed paths, or ``None``.
    """
    base = baseline or {}
    cur = current or {}
    exempt_dirs = tuple(exempt_dirs)

    def _relevant(paths: set) -> list:
        return sorted(
            p
            for p in paths
            if not _is_exempt(p, live_session_id, exempt_prefixes, exempt_dirs)
        )

    added = _relevant(set(cur) - set(base))
    removed = _relevant(set(base) - set(cur))
    changed = _relevant({p for p in set(base) & set(cur) if base[p] != cur[p]})

    if not (added or removed or changed):
        return None

    lines = [
        f"{label} CONTAMINATED: {directory}",
        "",
        "A test changed the repository's real state tree. Synthetic records are "
        "indistinguishable from runtime evidence, and destroyed gating state is "
        "indistinguishable from a pipeline that never ran (Issue #1779, AC1).",
    ]
    if added:
        lines.append(f"  created: {added}")
    if changed:
        lines.append(f"  modified: {changed}")
    if removed:
        lines.append(f"  removed: {removed}")
    lines += ["", f"REQUIRED NEXT ACTION: {remedy}"]
    return "\n".join(lines)
