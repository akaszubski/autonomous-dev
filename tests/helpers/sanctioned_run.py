"""Construct a SANCTIONED /implement run for tests (Issue #1807).

Before #1807 any hand-written dict carrying ``explicitly_invoked`` was accepted
by ``unified_pre_tool._is_pipeline_active`` and ``_has_alignment_passed``, so
dozens of fixtures modelled "an active pipeline" as exactly the shape the #1807
forgery uses. A state now authorizes the current run only when TWO carriers
agree: an owner-bound MAC (``pipeline_state.sign_state``) and the run-start
receipt written before any agent ran
(``pipeline_completion_state.record_run_start``). This builds both, so existing
assertions keep their ORIGINAL meaning instead of being rewritten to expect a
refusal — which would have quietly deleted the coverage.

ISOLATION IS NOT IMPLEMENTED HERE. Creating a run touches two ambient stores
(``$HOME/.claude/pipeline_secrets/<run_id>.key`` and the ``/tmp`` completion
ledger), and ``state_isolation.redirect_pipeline_state`` is the ONE mechanism
that redirects them. This module only REFUSES to write when that mechanism is
not in force — measured need: the first draft wrote and then deleted the real
``~/.claude/pipeline_secrets/test-verdict-1467.key``.

These functions are the PERMIT arm. The refusal arm writes the unsigned /
ownerless / receiptless shape directly, as
``tests/security/test_issue_1807_authority_boundary.py`` does.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple, Union

from tests.helpers.state_isolation import active_pipeline_state_redirect

__all__ = ["sanctioned_state", "write_sanctioned_sentinel", "clear_run_artifacts"]

#: ``(session_id, run_id)`` pairs this module created. Cleanup unlinks ONLY
#: registered pairs: reaping a guessed path is how a probe deletes the wrong file.
_CREATED: Set[Tuple[str, str]] = set()


def _lib_on_path() -> None:
    """Ensure the plugin lib directory is importable."""
    lib = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


def _verify_isolated(session_id: str, run_id: str) -> None:
    """Refuse to create run artifacts outside the active redirect.

    Args:
        session_id: Owner whose ledger would be written.
        run_id: Run whose secret key would be written.

    Raises:
        RuntimeError: If no redirect is active, if either library-resolved path
            falls outside it, or if the key already exists and this module did
            not create it — reuse is how a stale or forged key masquerades as a
            sanctioned run.
    """
    _lib_on_path()
    from pipeline_completion_state import _state_file_path
    from pipeline_state import _get_pipeline_secret_path

    redirect = active_pipeline_state_redirect()
    if redirect is None:
        raise RuntimeError(
            "sanctioned_run: no isolation active — building a run would write "
            "the operator's real ~/.claude/pipeline_secrets/ and /tmp ledger. "
            "REQUIRED NEXT ACTION: call state_isolation.redirect_pipeline_state("
            "monkeypatch, tmp_path, pipeline_state, pipeline_completion_state, "
            "<hook module>) first (Issue #1807)."
        )

    key = _get_pipeline_secret_path(run_id)
    for label, path in (("secret key", key), ("ledger", _state_file_path(session_id))):
        if redirect.root not in Path(path).parents:
            raise RuntimeError(
                f"sanctioned_run: the {label} resolved to {path}, outside the "
                f"active isolation root {redirect.root} — refusing to touch an "
                "ambient store (Issue #1807)."
            )
    if key.exists() and (session_id, run_id) not in _CREATED:
        raise RuntimeError(
            f"sanctioned_run: {key} already exists and this helper did not "
            "create it; REUSING a key would let a stale one pass as sanctioned."
        )


def sanctioned_state(
    session_id: str,
    run_id: str,
    *,
    record_receipt: bool = True,
    issue_number: Optional[int] = None,
    **fields: Any,
) -> Dict[str, Any]:
    """Build a signed, receipt-backed pipeline state dict.

    Args:
        session_id: Owning session; must be determinate (not ``""``/``unknown``).
        run_id: Base run id — a unique suffix is appended so parallel workers
            cannot share a key.
        record_receipt: ``False`` builds the A3/A7 forgery shape (signed, but no
            run-start corroborates it), which consumers must refuse.
        issue_number: Issue scope for the receipt, when the test needs one.
        **fields: Extra state fields merged over the defaults.

    Returns:
        The signed state dict.

    Raises:
        ValueError: If *session_id* cannot own a run.
        RuntimeError: If isolation is absent (see :func:`_verify_isolated`) or the
            receipt write FAILED — a fixture that swallows either reports a
            sanctioned run it never built.
    """
    if not isinstance(session_id, str) or session_id.strip().lower() in ("", "unknown"):
        raise ValueError(
            f"sanctioned_state needs a determinate owner, got {session_id!r}; an "
            "unavailable owner fails closed by design (Issue #1807)."
        )

    unique_run_id = f"{run_id}-{uuid.uuid4().hex[:8]}"[-64:]
    _verify_isolated(session_id, unique_run_id)

    _lib_on_path()
    from pipeline_completion_state import record_run_start
    from pipeline_state import sign_state

    state: Dict[str, Any] = {
        "session_start": datetime.now().isoformat(),
        "mode": "full",
        "explicitly_invoked": True,
    }
    state.update(fields)
    state["session_id"] = session_id
    state["run_id"] = unique_run_id

    if record_receipt and not record_run_start(
        session_id, unique_run_id, issue_number=issue_number
    ):
        raise RuntimeError(
            f"record_run_start({session_id!r}, {unique_run_id!r}) FAILED: this "
            "state has no run-start receipt, so it is not a sanctioned run."
        )
    _CREATED.add((session_id, unique_run_id))
    return sign_state(state, session_id)


def write_sanctioned_sentinel(
    path: Union[str, Path], session_id: str, run_id: str, **kwargs: Any
) -> Dict[str, Any]:
    """Write a sanctioned state to *path* and return it.

    Args:
        path: Sentinel path the test points ``PIPELINE_STATE_FILE`` at.
        session_id: Owning session.
        run_id: Base run id.
        **kwargs: Forwarded to :func:`sanctioned_state`.

    Returns:
        The state that was written.
    """
    state = sanctioned_state(session_id, run_id, **kwargs)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state), encoding="utf-8")
    return state


def clear_run_artifacts(session_id: str, run_id: Optional[str] = None) -> None:
    """Reap the ledger and secret-key artifacts this module created.

    Under the canonical redirect both live inside ``tmp_path``; reaping them
    per-test keeps a later call in the same process from seeing state it did not
    create (Issue #1184). Paths come from the LIBRARY, and only registered pairs
    are unlinked, so a caller cannot reap a live run's key by passing its id.

    Args:
        session_id: Session whose artifacts to remove.
        run_id: Restrict to one run; ``None`` reaps every run for the session.
    """
    _lib_on_path()
    from pipeline_completion_state import _state_file_path
    from pipeline_state import cleanup_pipeline_secret

    pairs = [
        p for p in list(_CREATED)
        if p[0] == session_id and (run_id is None or p[1] == run_id)
    ]
    if not pairs:
        return
    try:
        ledger = _state_file_path(session_id)
        for candidate in (ledger, Path(str(ledger) + ".lock")):
            candidate.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
    for pair in pairs:
        try:
            cleanup_pipeline_secret(pair[1])
        except OSError:
            pass
        _CREATED.discard(pair)
