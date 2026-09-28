"""Pipeline state machine for /implement command.

Tracks pipeline step progression, enforces gate conditions, and persists
state to JSON. Zero external dependencies (stdlib only).

Usage:
    state = create_pipeline("run-001", "Add user auth")
    state = advance(state, Step.ALIGNMENT)
    state = complete_step(state, Step.ALIGNMENT, passed=True)
    trace = get_trace(state)
"""

import fcntl
import hashlib
import hmac as _hmac
import json
import os
import re as _re
import secrets
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    # Normal package-style import (preferred when invoked from production code).
    from .path_utils import find_project_root  # type: ignore
except ImportError:  # pragma: no cover - fallback for scripts that load module by path
    try:
        from path_utils import find_project_root  # type: ignore
    except ImportError:
        # Last-resort no-op fallback: callers will hit the cwd-based fallback below.
        def find_project_root(*_args: Any, **_kwargs: Any) -> Path:  # type: ignore
            raise FileNotFoundError("path_utils.find_project_root unavailable")


# =============================================================================
# CONSTANTS
# =============================================================================

# Legacy sentinel file name (Issue #1206). The full path is now per-repo:
# <repo_root>/.claude/local/implement_pipeline_state.json. Resolve via
# get_legacy_sentinel_path() — DO NOT hardcode the old /tmp/... literal.
#
# The sentinel is touched on every hook invocation during active pipeline runs,
# making its mtime a reliable indicator of recent pipeline activity. It is
# distinct from the HMAC-signed per-run state file created by
# get_state_path(run_id) at /tmp/pipeline_state_{run_id}.json.
#
# Used by verify_state_hmac() for stale-state fail-open detection (Issue #753):
# if this sentinel's mtime is >1 hour old, the pipeline is considered stale and
# HMAC verification fails open to avoid blocking subsequent sessions.
#
# Cross-reference: unified_pre_tool.py PIPELINE_STATE_FILE env var,
#                  pre_compact_batch_saver.sh, implement-fix.md.
#
# Issue #1206: relocated from machine-global /tmp/implement_pipeline_state.json
# to per-repo path so concurrent /implement sessions in different repos no
# longer clobber each other's sentinels.
LEGACY_SENTINEL_FILENAME: str = "implement_pipeline_state.json"


def get_legacy_sentinel_path(repo_root: Optional[Path] = None) -> Path:
    """Resolve the per-repo legacy sentinel file path.

    Returns ``<repo_root>/.claude/local/implement_pipeline_state.json`` where
    ``repo_root`` is determined by (in order):

    1. The explicit ``repo_root`` argument if provided.
    2. :func:`path_utils.find_project_root` (walks for ``.git`` or ``.claude``).
    3. ``Path.cwd().resolve()`` if no marker file is found.

    The parent directory is created with mode 0o700 if missing. The created
    directory is owner-only because it can contain run-scoped state with
    HMAC-signed content.

    Args:
        repo_root: Optional explicit repo root. When provided, the marker-file
            walk is skipped and the path is computed directly under this root.

    Returns:
        The fully-qualified sentinel path. The file itself MAY or MAY NOT
        exist; only the parent directory is created.

    Issue #1206: per-repo isolation eliminates cross-repo collisions on the
    machine-global ``/tmp/implement_pipeline_state.json`` location.
    """
    if repo_root is not None:
        root = Path(repo_root).resolve()
    else:
        try:
            root = find_project_root()
        except FileNotFoundError:
            root = Path.cwd().resolve()

    sentinel_dir = root / ".claude" / "local"
    try:
        sentinel_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # mkdir() honors mode only when creating; force 0o700 on existing dirs too.
        try:
            sentinel_dir.chmod(0o700)
        except OSError:
            # Best effort; caller will still get a usable path.
            pass
    except OSError:
        # Best effort: parent dir creation may fail (read-only FS, permissions);
        # callers using the path for read operations still get a valid object.
        pass

    return sentinel_dir / LEGACY_SENTINEL_FILENAME


def atomic_write_json(
    path: Path,
    data: dict,
    *,
    indent: Optional[int] = None,
) -> None:
    """Atomically write a JSON dict to ``path`` using a temp file + rename.

    Uses ``tempfile.mkstemp`` in the destination's parent directory so the
    rename is on the same filesystem (atomic on POSIX). The temp file is
    chmod'd to 0o600 BEFORE the rename so the destination inherits restrictive
    permissions even if the directory has a permissive umask.

    On exception, the temp file is unlinked and the exception re-raised so the
    caller can decide how to handle persistence failure.

    Args:
        path: Destination file path. Parent directory MUST exist.
        data: JSON-serialisable dict.
        indent: Optional JSON pretty-print indent (passed through to
            ``json.dump``). ``None`` produces the most compact form.

    Raises:
        OSError: From ``tempfile.mkstemp``, ``os.replace``, or ``os.chmod``.
        TypeError: If ``data`` is not JSON-serialisable.
    """
    parent = path.parent
    fd, tmp = tempfile.mkstemp(
        dir=str(parent), suffix=".tmp", prefix=f".{path.name}_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=indent)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            # Non-fatal: permission tightening is best-effort on platforms
            # like Windows or FUSE mounts that ignore chmod.
            pass
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# Backward-compat alias — external callers that imported the private name continue to work.
_atomic_write_json = atomic_write_json


# =============================================================================
# ENUMS
# =============================================================================


class Step(Enum):
    """Pipeline steps in execution order."""

    ALIGNMENT = "alignment"
    RESEARCH_CACHE = "research_cache"
    RESEARCH = "research"
    PLAN = "plan"
    ACCEPTANCE_TESTS = "acceptance_tests"
    TDD_TESTS = "tdd_tests"
    IMPLEMENT = "implement"
    HOOK_CHECK = "hook_check"
    VALIDATE = "validate"
    VERIFY = "verify"
    REPORT = "report"
    CONGRUENCE = "congruence"
    CI_ANALYSIS = "ci_analysis"


class StepStatus(Enum):
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# CONSTANTS
# =============================================================================

STEP_SEQUENCE: List[Step] = list(Step)

SKIPPABLE_STEPS: Set[Step] = {
    Step.RESEARCH_CACHE,
    Step.ACCEPTANCE_TESTS,
    Step.TDD_TESTS,
    Step.HOOK_CHECK,
}

GATE_CONDITIONS: Dict[Step, Set[Step]] = {
    Step.IMPLEMENT: {Step.TDD_TESTS},
    Step.VALIDATE: {Step.IMPLEMENT},
    Step.REPORT: {Step.VERIFY},
    Step.CONGRUENCE: {Step.REPORT},
    Step.CI_ANALYSIS: {Step.CONGRUENCE},
}


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class StepRecord:
    """Record for a single pipeline step."""

    status: StepStatus = StepStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PipelineState:
    """Full pipeline state including all steps and metadata.

    The steps dict uses string keys (step values) mapping to plain dicts
    with keys: status, started_at, completed_at, error. This keeps the
    state JSON-serializable and compatible with various access patterns.
    """

    run_id: str
    mode: str
    feature: str
    steps: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    redispatch_agents: Dict[str, bool] = field(default_factory=dict)

    remediation_occurred: bool = False  # Issue #1271: Track if STEP 11 remediation was triggered

# =============================================================================
# HELPERS
# =============================================================================


def _now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _make_step_dict(
    status: str = "pending",
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a step record dict."""
    return {
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "error": error,
    }


def _get_step(state: PipelineState, step: Step) -> Dict[str, Any]:
    """Get step record dict from state, looking up by step value string."""
    return state.steps[step.value]


def _get_status(state: PipelineState, step: Step) -> StepStatus:
    """Get the StepStatus for a step in the pipeline."""
    record = state.steps.get(step.value)
    if record is None:
        return StepStatus.PENDING
    return StepStatus(record["status"])




def _get_pipeline_secret_path(run_id: str) -> Path:
    """Return the filesystem path for a pipeline secret key file.

    The secret is stored separately from the state file so an attacker who
    controls the state file cannot forge the HMAC without also accessing the
    secret file (which has restricted permissions).

    Args:
        run_id: The pipeline run identifier.

    Returns:
        Path to the secret key file (~/.claude/pipeline_secrets/<run_id>.key).
    """
    import re as _re

    secrets_dir = Path.home() / ".claude" / "pipeline_secrets"
    safe_id = _re.sub(r"[^a-zA-Z0-9_-]", "_", run_id)[:128] if run_id else "unknown"
    return secrets_dir / f"{safe_id}.key"


def _get_or_create_pipeline_secret(run_id: str) -> str:
    """Get existing pipeline secret or create a new one.

    Creates the secret file with 0o600 permissions. The secret is a 32-byte
    hex string that is NOT stored in the pipeline state file.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        The hex-encoded secret string.
    """
    import os as _os

    secret_path = _get_pipeline_secret_path(run_id)
    if secret_path.exists():
        return secret_path.read_text().strip()

    secret = secrets.token_hex(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = _os.open(str(secret_path), _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o600)
    try:
        _os.write(fd, secret.encode("utf-8"))
    finally:
        _os.close(fd)
    return secret


def _read_pipeline_secret(run_id: str) -> "Optional[str]":
    """Read a pipeline secret from the secrets directory.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        The secret string, or None if the secret file does not exist.
    """
    secret_path = _get_pipeline_secret_path(run_id)
    if not secret_path.exists():
        return None
    try:
        return secret_path.read_text().strip()
    except OSError:
        return None


def cleanup_pipeline_secret(run_id: str) -> None:
    """Remove the pipeline secret file from disk.

    Args:
        run_id: The pipeline run identifier.

    Does not raise if the file does not exist.
    """
    secret_path = _get_pipeline_secret_path(run_id)
    try:
        secret_path.unlink()
    except FileNotFoundError:
        pass


# =============================================================================
# STATE MAC VERSIONS (Issue #1807)
# =============================================================================
#
# v1 is the pre-#1807 message: session_start | mode | run_id |
# explicitly_invoked | alignment_passed | alignment_verdict | nonce. It does NOT
# bind ``session_id``, so a wrong-owner, rewritten-owner or deleted-owner state
# all verified True (MEASURED at ac3e04c3, see
# tests/security/test_issue_1807_authority_boundary.py).
#
# v2 appends the message version and an OWNER TOKEN. Both are inside the signed
# message, so a caller cannot downgrade a v2 state to v1 verification by
# deleting the unsigned ``hmac_version`` field: v1 recomputation over a v2
# signature simply fails.
#
# v3 (Issue #1807, all-six binding) additionally appends ``issue_number``,
# ``subject`` and ``base_commit``. v2 already bound session_id, run_id and mode;
# v3 closes the remaining tamper-evidence gap so ALL six run bindings are signed.
# base_commit in particular is written to the sentinel AFTER signing by
# set_pipeline_base_commit(), which now RE-SIGNS so the stored MAC keeps covering
# it. The v2 message is left BYTE-IDENTICAL for version < v3, so states signed at
# v1/v2 still verify unchanged.
#
# The v1 message is left BYTE-IDENTICAL on purpose. A pipeline run that was
# already in flight when this change landed carries a v1 signature, and the
# alternative to verifying it is hard-failing every gate of a live run
# mid-flight. v1 states are still recognized, but they are classified
# EXPLICITLY as legacy-unbound by classify_current_run_authority(), which
# requires the independent run-start receipt regardless of MAC version.
_STATE_MAC_V1 = 1
_STATE_MAC_V2 = 2
_STATE_MAC_V3 = 3
_STATE_MAC_CURRENT = _STATE_MAC_V3

#: Signed fields that MUST be ``str`` when present (Issue #1807). A PRESENT value of
#: any other type cannot be a genuine binding, so verify_state_hmac refuses such a
#: state UP FRONT, in BOTH strict modes, BEFORE secret resolution / MAC computation
#: / the #753 stale branch. This closes the hole the exception catch cannot: on a v3
#: state ``json.dumps(123)`` does NOT raise (unlike the v1/v2 ``"|".join``), so a
#: non-str field would otherwise compute a mismatching MAC, fall through the
#: compare, and hit the #753 stale fail-open — returning True under ``strict=False``.
#:
#: Every field below is always-str in a genuine state; two overlapping reasons:
#:   * session_start, mode, run_id, alignment_verdict, nonce, session_id —
#:     semantically string, and they feed the v1/v2 ``"|".join``, the v2/v3 owner
#:     token and/or the secret-path ``re.sub`` (run_id), so a non-str also RAISES in
#:     the v1/v2 path.
#:   * subject, base_commit — v3-only free-form, but ALWAYS str in production
#:     (``subject`` = ``os.environ.get('FEATURE_DESCRIPTION', '')``; ``base_commit``
#:     = ``set_pipeline_base_commit(base_commit: str)`` git SHA) with NO int
#:     counter-case, so a non-str there is malformed — not a legitimate JSON-native
#:     value — and must fail closed in BOTH modes.
#:
#: DELIBERATELY EXCLUDED, left to the normal MAC path (a wrong value there is a
#: value-mismatch — the bounded #753 domain — not a type reject):
#:   * ``issue_number`` — v3-only and INTENTIONALLY JSON-native int: 1807 (int) and
#:     "1807" (str) are DISTINCT signed tokens, and a genuine v3 state carries the
#:     int (see _compute_state_hmac's TYPE POLICY note and the golden freeze).
#:     Str-requiring it would REJECT a valid state.
#:   * ``explicitly_invoked``, ``alignment_passed`` — coerced (``bool(...)`` in v3,
#:     ``str(...)`` in v1/v2) inside _compute_state_hmac, so any type is accepted
#:     by construction.
#: ``hmac`` is guarded separately; ``hmac_version`` is validated by
#: _declared_mac_version. Keep this tuple in lockstep with _compute_state_hmac.
_STR_REQUIRED_SIGNED_FIELDS = (
    "session_start",
    "mode",
    "run_id",
    "alignment_verdict",
    "nonce",
    "session_id",
    "subject",
    "base_commit",
)

#: Session-id values that identify nobody. A state whose owner is one of these
#: makes no ownership claim that could be verified, and INV-7 reads an
#: unverifiable claim as "not passed" rather than "passed".
_INDETERMINATE_SESSION_IDS = frozenset({"", "unknown", "none", "null"})


def _is_determinate_session_id(value: Any) -> bool:
    """Whether *value* names a specific session.

    Args:
        value: Candidate session id from state or from a caller.

    Returns:
        True when *value* is a non-blank string that is not one of the
        placeholder spellings in :data:`_INDETERMINATE_SESSION_IDS`.
    """
    if not isinstance(value, str):
        return False
    return value.strip().lower() not in _INDETERMINATE_SESSION_IDS


def _synthetic_identity_predicate() -> Any:
    """Return the canonical synthetic-id predicate, or ``None`` when unavailable.

    ONE import seam for it, so "is the instrument present?" is asked in a single
    place and every consumer fails closed the same way. The predicate itself lives
    in ``pipeline_completion_state`` and is NOT restated here — a second copy of
    the spellings is how the ``stop-N`` gap arose in the first place.

    Returns:
        The callable, or ``None`` if the module cannot be imported.
    """
    try:
        try:
            from .pipeline_completion_state import is_synthetic_session_id  # type: ignore
        except ImportError:
            from pipeline_completion_state import is_synthetic_session_id  # type: ignore
    except ImportError:
        return None
    return is_synthetic_session_id


def _is_usable_owner_identity(value: Any) -> bool:
    """Whether *value* may OWN or CLAIM a run at the authority boundary.

    Strictly stronger than :func:`_is_determinate_session_id`, and the two are
    deliberately separate because they answer different questions:

    * :func:`_is_determinate_session_id` — "is this string capable of naming
      somebody?" It guards MAC binding, where ``"test-session"`` is a perfectly
      good owner VALUE to sign and compare. Narrowing it would silently unbind
      the owner for every state signed under a test-shaped id.
    * this function — "may this identity be current-run AUTHORITY?" Here a
      ``stop-N`` id (minted by the SubagentStop heartbeat when the real id was
      unresolvable) or a ``test-*`` id (leaked in from hook-subprocess tests)
      must refuse, exactly as ``ensure_sentinel_heartbeat`` already refuses to
      WRITE them.

    The synthetic list is NOT re-implemented here: it delegates to
    ``pipeline_completion_state.is_synthetic_session_id``, which is its canonical
    home. MEASURED defect this closes (isolated HOME + ledger, 2026-09-27): a
    signed state with a matching run-start receipt and owner ``stop-7`` or
    ``test-7`` classified AUTHORIZED, while ``unknown`` already refused and a
    UUID-shaped id authorized — so the hole was exactly the synthetic-but-not-
    blank band.

    Args:
        value: Candidate owner or presented caller identity.

    Returns:
        True only when the identity is determinate AND non-synthetic.

    Issues: #1481, #1807
    """
    if not _is_determinate_session_id(value):
        return False
    predicate = _synthetic_identity_predicate()
    if predicate is None:
        # FAIL CLOSED. Returning True here would authorize an identity precisely
        # when the check that judges it is UNAVAILABLE — the inverse of INV-7. The
        # earlier draft reasoned that the receipt lookup would catch it anyway;
        # that is an assumption about another branch, not a guarantee, and a
        # caller-injected `receipt_lookup` bypasses it entirely.
        return False
    try:
        return not predicate(value)
    except Exception:  # noqa: BLE001 - a predicate must not raise into a gate
        return False


def _owner_token(state: dict) -> str:
    """Encode the state's declared owner for the v2 signed message.

    ABSENCE is encoded as a distinct value rather than as ``""``. A
    ``state.get("session_id", "")`` style binding would cover the rewrite shape
    (A1b) while still colliding an ABSENT owner with an empty one (A1c), which
    is exactly the shape ``commands/implement-fix.md`` used to write.

    Args:
        state: Pipeline state dict.

    Returns:
        ``"owner:absent"`` when no owner is declared, else
        ``"owner:present:<value>"`` — an owner whose literal value is
        ``"absent"`` therefore cannot collide with the absent encoding.
    """
    owner = state.get("session_id")
    if owner is None:
        return "owner:absent"
    return f"owner:present:{owner}"


def _declared_mac_version(state: dict) -> Optional[int]:
    """Return the MAC message version the state claims.

    Args:
        state: Pipeline state dict.

    Returns:
        :data:`_STATE_MAC_V1` when no version is declared (pre-#1807 state),
        the declared version when it is one this module can compute, or
        ``None`` for an unrecognized version — which callers MUST treat as a
        verification failure rather than guessing a message shape.
    """
    raw = state.get("hmac_version")
    if raw is None:
        return _STATE_MAC_V1
    try:
        version = int(raw)
    except (TypeError, ValueError):
        return None
    return (
        version
        if version in (_STATE_MAC_V1, _STATE_MAC_V2, _STATE_MAC_V3)
        else None
    )


def _compute_state_hmac(
    state: dict, secret: str, *, version: int = _STATE_MAC_V1
) -> str:
    """Compute HMAC-SHA256 over critical pipeline state fields.

    Uses an external secret (NOT stored in the state file) as the HMAC key,
    combined with the nonce. This prevents forgery even if an attacker
    controls the state file contents.

    Args:
        state: Pipeline state dict (must contain 'nonce' key).
        secret: The pipeline secret from a separate restricted-permission file.
        version: Message version — :data:`_STATE_MAC_V1` reproduces the
            pre-#1807 message byte for byte; :data:`_STATE_MAC_V2` additionally
            binds the version and the declared owner; :data:`_STATE_MAC_V3`
            additionally binds ``issue_number``, ``subject`` and ``base_commit``
            so all six run bindings are tamper-evident, and switches to an
            INJECTIVE JSON-array serialization so an unescaped delimiter in a
            free-form value cannot slide between fields (Issue #1807). v1/v2 keep
            the pipe-joined message byte-for-byte. Defaults to v1 so a caller that
            does not know about versions cannot silently change the meaning of an
            existing signature.

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    nonce = state.get("nonce", "")
    key = (secret + nonce).encode("utf-8")
    # Deterministic message from critical fields
    parts = [
        state.get("session_start", ""),
        state.get("mode", ""),
        state.get("run_id", ""),
        str(state.get("explicitly_invoked", False)),
        str(state.get("alignment_passed", False)),
        str(state.get("alignment_verdict", "")),   # Issue #1467: verdict co-signed; default "" keeps legacy states byte-identical
        nonce,
    ]
    if version >= _STATE_MAC_V2:
        # Issue #1807: the owner is signed DATA, and the version is signed with
        # it so stripping `hmac_version` cannot select the weaker message.
        parts.append(f"mac_version:{version}")
        parts.append(_owner_token(state))
    if version >= _STATE_MAC_V3:
        # Issue #1807 (all-six binding, INJECTIVE encoding): v3 binds the three
        # remaining run identity fields (issue_number, subject, base_commit). It
        # MUST NOT reuse the "field:value" + "|".join scheme above — those values
        # are free-form and unescaped, so a '|' or ':' inside one (subject in
        # particular) slides the delimiter and makes two DISTINCT field tuples
        # collide to the SAME message. CONFIRMED collision under the old scheme:
        #   subject="a|base_commit:b", base_commit="c"   ==   (same MAC)
        #   subject="a", base_commit="b|base_commit:c"
        # v3 therefore serializes the FULL signed field set as a JSON array. JSON
        # string-escaping renders '|', ':', '"', '\\' and unicode injective, and
        # the fixed element order keeps it deterministic (INV-6).
        #
        # TYPE POLICY: flags are coerced to bool and the version to int for a
        # canonical, unambiguous form; free-form fields keep their JSON-native
        # type, so 1807 (int) and "1807" (str) serialize to DISTINCT tokens
        # (1807 vs "1807") — no cross-type collision. json.dumps is applied
        # identically at sign and verify time, and the sentinel's JSON storage
        # preserves each field's type across the write/read roundtrip, so
        # sign-time == verify-time (no drift). NOTE: str-coercing the free-form
        # fields (an alternative here) would instead MAKE 1807 and "1807" collide,
        # violating the no-cross-type-collision goal, so it is deliberately NOT
        # used. V1/V2 are untouched — their message is still the "|".join below.
        message = json.dumps(
            [
                state.get("session_start", ""),
                state.get("mode", ""),
                state.get("run_id", ""),
                bool(state.get("explicitly_invoked", False)),
                bool(state.get("alignment_passed", False)),
                state.get("alignment_verdict", ""),
                nonce,
                int(version),
                _owner_token(state),
                state.get("issue_number", ""),
                state.get("subject", ""),
                state.get("base_commit", ""),
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
    else:
        message = "|".join(parts).encode("utf-8")
    return _hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_state_hmac(state: dict, session_id: str, *, strict: bool = False) -> bool:
    """Verify the HMAC on a pipeline state dict.

    Reads the secret from a separate pipeline secrets file. ``session_id`` is
    the PRESENTED caller identity: since Issue #1807 a state that declares a
    different owner does not verify for it, so the argument is an authorization
    input and no longer only a legacy key fallback.

    When the secret file has been cleaned up between sessions (common in
    batch/worktree workflows after /clear), stale states older than 1 hour
    are treated as expired rather than tampered to avoid generating repeated
    HMAC failures (Issue #753).

    STRICT MODE (Issue #1807, ``strict=True``) — the AUTHORITY path MUST use this.
    It disables the #753 stale fail-open entirely: ANY invalid or unverifiable MAC
    returns ``False`` regardless of the legacy sentinel's mtime. Without it, a
    current-slice fail-open exists — tamper a signed field OTHER than run_id/owner,
    let ``get_legacy_sentinel_path()`` go stale (mtime > 3600s), and the stale
    branch below returns ``True`` (MAC treated valid), so
    :func:`classify_current_run_authority` would AUTHORIZE a tampered state whose
    run-start receipt still matches. ``classify_current_run_authority`` is the ONLY
    caller that passes ``strict=True``. Legacy (``strict=False``) callers keep the
    #753 behavior; see the named non-authority caller below.

    Non-authority caller retaining the legacy #753 fail-open (``strict=False``):
    ``unified_pre_tool._is_explicit_implement_active`` — the #557 integrity check
    for the ``explicitly_invoked`` flag, whose #753 stale convenience exists for
    batch/worktree runs after ``/clear``. It is NOT the current-run authority
    decision (that is :func:`classify_current_run_authority`, now strict, which
    every guarded consumer route calls); its residual is bounded — a tampered flag
    on a stale sentinel only affects the secondary #528 coordinator-block signal,
    while the strict classifier, the run-bearing-transition chokepoint and the
    protected-infra hard floor still gate every protected mutation.

    Issue #1807 — three failures this refuses that it used to accept:

    1. A foreign caller presenting another run's signed state (A1a).
    2. ``state['session_id']`` rewritten after signing (A1b).
    3. ``state['session_id']`` DELETED after signing (A1c).

    Integrity is NOT authority. An unsigned state still returns ``True`` here
    (legacy RECOGNITION, unchanged), and the #753 stale fail-open still returns
    ``True`` for an abandoned run. Neither is a licence to act as the current
    run — that question belongs to :func:`classify_current_run_authority`, which
    every guarded consumer route calls.

    Args:
        state: Pipeline state dict with 'hmac' and 'nonce' fields.
        session_id: The session presenting this state (fallback key when the
            secret file is missing).

    Returns:
        True if the HMAC is valid, False if tampered, missing nonce, or
        presented by a session that is not the declared owner. Returns True if
        there is no 'hmac' field (backward compatibility).

        MALFORMED INPUT always fails closed BY RETURN (never raises), in BOTH
        strict modes: a non-dict state, a non-str 'hmac', or a present-but-non-str
        str-required signed field (:data:`_STR_REQUIRED_SIGNED_FIELDS` —
        session_start, mode, run_id, alignment_verdict, nonce, session_id, subject,
        base_commit) all return False. This is what lets
        :func:`classify_current_run_authority` honour its "NEVER raises" contract.

        A WELL-TYPED value-mismatch is a different case: under ``strict=True`` (the
        authority path) it is fully fail-closed (False), while under
        ``strict=False`` it follows the pre-existing, bounded #753 stale
        fail-open — a non-authority nudge path only — and MAY return True for an
        abandoned run whose legacy sentinel is >1h old. Type errors never take that
        path; only well-typed value tampering does.
    """
    if not isinstance(state, dict):
        # Malformed input (Issue #1807): a non-dict state carries no verifiable
        # claim. Fail closed by RETURN — never by raise — so the documented bool
        # contract holds for BOTH strict and legacy callers, and
        # classify_current_run_authority's "NEVER raises" is not bypassed by a
        # TypeError leaking out of the first ``.get`` below.
        return False

    stored_hmac = state.get("hmac")
    if stored_hmac is None:
        # Backward compatibility: old state files without HMAC are accepted
        return True
    if not isinstance(stored_hmac, str):
        # Malformed input (Issue #1807): a stored MAC that is not a string (int,
        # dict, float, ...) is not a genuine hexdigest and would raise inside
        # hmac.compare_digest on BOTH the strict and the legacy paths. Refuse by
        # return, UP FRONT, so neither branch can reach the raising compare.
        return False

    # Up-front SIGNED-SCHEMA TYPE validation (Issue #1807). A str-required signed
    # field that is PRESENT but not a str fails closed in BOTH strict modes here,
    # BEFORE secret resolution, MAC computation and the #753 stale branch. This is
    # the ONLY thing that closes the v3 hole: json.dumps(123) does NOT raise, so a
    # v3 state with e.g. mode=123 would compute a (mismatching) MAC, fall through
    # the compare, and hit the #753 stale fail-open — returning True under
    # strict=False. The exception catch below cannot see that (nothing raised).
    # Only PRESENT fields are checked; an ABSENT field defaults inside
    # _compute_state_hmac and is not a type error. A WELL-TYPED wrong VALUE (e.g.
    # mode="WRONGSTR") is deliberately NOT rejected — value-mismatch keeps the
    # pre-existing bounded #753 non-strict fail-open. Only issue_number (JSON-native
    # int by design) and the coerced flags (explicitly_invoked/alignment_passed) are
    # excluded on purpose; subject/base_commit ARE str-required (always-str in
    # production). See _STR_REQUIRED_SIGNED_FIELDS.
    for _field in _STR_REQUIRED_SIGNED_FIELDS:
        if _field in state and not isinstance(state[_field], str):
            return False

    if not state.get("nonce"):
        # HMAC present but no nonce means tampering
        return False

    # Issue #1807 (A1a): bind the PRESENTED caller to the declared owner.
    # Checked BEFORE the signature so it can never be reached by the #753
    # stale fail-open below — a foreign caller must not inherit a stale run's
    # authority just because the sentinel went quiet for an hour.
    declared_owner = state.get("session_id")
    if (
        _is_determinate_session_id(declared_owner)
        and _is_determinate_session_id(session_id)
        and declared_owner.strip() != session_id.strip()
    ):
        return False

    version = _declared_mac_version(state)
    if version is None:
        # Unrecognized message version: refuse rather than guess a shape.
        return False

    # BACKSTOP fail-closed guard (Issue #1807). The up-front schema check above
    # already refuses a non-str str-required field (mode, run_id, nonce, ...), so
    # the v1/v2 ``"|".join``, the ``secret + nonce`` key concat and the secret-path
    # ``re.sub`` can no longer be reached with a raising input from those fields.
    # What this try/except still catches is the RESIDUAL: a stored MAC that is a
    # str but NON-ASCII raises inside ``compare_digest`` ("comparing strings with
    # non-ASCII characters is not supported"), plus any unforeseen stdlib raise.
    # It wraps the ENTIRE remaining verification — secret-path resolution, MAC
    # computation AND comparison, across BOTH the strict per-run-secret path and
    # the strict=False secret-missing session-id fallback — and fails closed BY
    # RETURN without reaching the #753 stale branch, upholding the bool contract
    # that classify_current_run_authority's documented "NEVER raises" depends on.
    # NOTE ON SCOPE: this closes malformed-TYPE input in both modes; a WELL-TYPED
    # value-mismatch under strict=False still follows the deliberate, bounded #753
    # non-strict fail-open below (a non-authority nudge path) — the strict authority
    # path short-circuits before it and is fully fail-closed.
    try:
        run_id = state.get("run_id", "")
        secret = _read_pipeline_secret(run_id) if run_id else None

        if secret is not None:
            expected = _compute_state_hmac(state, secret, version=version)
            if _hmac.compare_digest(stored_hmac, expected):
                return True

        # STRICT authority path (Issue #1807): satisfiable ONLY by the per-run
        # SECRET-keyed MAC checked immediately above. This short-circuit runs
        # BEFORE the session-id fallback AND the #753 stale branch, so under
        # strict BOTH are unreachable. CRITICAL (F4 remediation): the session-id
        # fallback keys the MAC on the PRESENTED session_id, which is
        # MODEL-KNOWABLE (CLAUDE_CODE_SESSION_ID). If the fallback ran under
        # strict, a caller could mint _compute_state_hmac(state, own_session_id,
        # version=2) with NO access to ~/.claude/pipeline_secrets/ and be
        # AUTHORIZED with legacy_mac=False — a secret-free v2 forgery
        # indistinguishable from a genuine secret-signed run. Requiring the
        # per-run secret closes that public-key/secret-free forgery. (It is NOT
        # "unforgeable" and NOT native provenance: the per-run secret is still
        # model-mintable via legitimate sign_state()/record_run_start() Bash
        # calls — the dual-carrier residual is the still-open A9 gap, #1807 OPEN.)
        if strict:
            return False

        # Session-id fallback for backward compat with states signed before
        # the secret-file approach was introduced. LEGACY (strict=False) ONLY now.
        fallback_key = session_id
        expected = _compute_state_hmac(state, fallback_key, version=version)
        if _hmac.compare_digest(stored_hmac, expected):
            return True
    except (TypeError, ValueError):
        # RESIDUAL raises only (the str-required fields are pre-empted by the
        # up-front schema check): a str-but-NON-ASCII stored MAC raises inside
        # ``compare_digest``, and any unforeseen stdlib raise lands here too. Fails
        # closed in BOTH branches, WITHOUT falling through to the #753 stale
        # fail-open below — so malformed input never fails OPEN.
        return False

    # Stale state fail-open (Issue #753): checks the LEGACY SENTINEL file
    # (<repo>/.claude/local/implement_pipeline_state.json — was
    # /tmp/implement_pipeline_state.json before Issue #1206), NOT the HMAC-
    # signed per-run state file (/tmp/pipeline_state_{run_id}.json). The legacy
    # sentinel is touched on every hook invocation during active pipeline runs
    # (see unified_pre_tool.py PIPELINE_STATE_FILE env var). Its mtime is used
    # as a proxy for "was the pipeline recently active?" — if >1 hour old, the
    # pipeline is considered stale and HMAC verification fails open. This
    # coupling is intentional: the sentinel mtime cannot be forged by editing
    # JSON content (unlike session_start in the state dict).
    # Cross-reference: get_legacy_sentinel_path() (this module).
    import time as _time

    state_path = get_legacy_sentinel_path()
    if state_path.exists():
        try:
            mtime = state_path.stat().st_mtime
            age_seconds = _time.time() - mtime
            if age_seconds > 3600:  # > 1 hour old
                return True  # fail-open for stale state files
        except OSError:
            pass

    return False


def sign_state(state: dict, session_id: str) -> dict:
    """Add HMAC signature, nonce and owner binding to a pipeline state dict.

    Generates a per-run secret stored in a separate file with restricted
    permissions. The HMAC key is derived from this secret, not from
    session_id (which may be absent or guessable).

    Issue #1807: the signature now covers ``state['session_id']``, so signing
    is where the owner claim is made. When the state declares no owner and
    *session_id* names one, it is written into the state first — otherwise
    ``sign_state(state, sid)`` would silently produce a state that belongs to
    nobody, which is the shape fix-mode F1 used to write. A state that already
    declares an owner keeps it: the artifact, not the argument, is what
    downstream consumers read.

    Args:
        state: Pipeline state dict to sign (mutated in place).
        session_id: The owning session. Bound into the MAC via
            ``state['session_id']``.

    Returns:
        The same dict with 'nonce', 'hmac_version' and 'hmac' fields set.
    """
    if not state.get("nonce"):
        state["nonce"] = secrets.token_hex(16)

    if not _is_determinate_session_id(state.get("session_id")) and (
        _is_determinate_session_id(session_id)
    ):
        state["session_id"] = session_id.strip()

    state["hmac_version"] = _STATE_MAC_CURRENT
    run_id = state.get("run_id", "unknown")
    secret = _get_or_create_pipeline_secret(run_id)
    state["hmac"] = _compute_state_hmac(state, secret, version=_STATE_MAC_CURRENT)
    return state


# =============================================================================
# CURRENT-RUN AUTHORITY (Issue #1807)
# =============================================================================


class RunAuthority(str, Enum):
    """Why a pipeline state may or may not act as the CURRENT RUN.

    Integrity (:func:`verify_state_hmac`) answers "were these bytes signed?".
    Authority answers "may this state authorize the current run?". They are
    different questions, and collapsing them is Issue #1807: the principal the
    gate constrains holds the signing capability (``sign_state`` CREATES the
    per-run secret), so a valid MAC over correct bindings is something the
    constrained caller can mint in two public calls.

    Every non-:attr:`AUTHORIZED` member is a REFUSAL with a distinct cause, so
    an operator reading a hook log can tell "no pipeline here" from "a state
    that tried to authorize itself".
    """

    AUTHORIZED = "authorized"
    NO_STATE = "no_state"
    NO_RUN_IDENTITY = "no_run_identity"
    OWNER_UNAVAILABLE = "owner_unavailable"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    PREDICATE_UNAVAILABLE = "predicate_unavailable"
    UNSIGNED_LEGACY = "unsigned_legacy"
    MAC_INVALID = "mac_invalid"
    UNQUALIFIED_OWNER = "unqualified_owner"
    RECEIPT_UNAVAILABLE = "receipt_unavailable"


class RunOrigin(str, Enum):
    """WHO initiated the run — a question authority does not answer.

    :class:`RunAuthority` answers "may this state authorize the current run?" and
    both its carriers are written by the principal the gate constrains. Origin
    answers "did a NATIVE hook process witness this run starting, and which kind?"
    It is STRICTLY ADDITIVE: a run with no witness keeps exactly the authority it
    had before Issue #1807's origin work, so the model-owned bootstrap path stays
    the compatibility route rather than becoming a refusal.

    The two witnessed classes are NOT interchangeable, and collapsing them would
    undo the point. A user-typed ``/implement`` fires ``UserPromptExpansion`` — a
    human chose it, so it can carry user authorization. A ``Skill`` tool call
    fires ``PreToolUse`` — the MODEL chose it, so it is a native EVENT that confers
    no user authorization and is never promotable to the typed class. There is
    deliberately NO code path that upgrades one to the other.

    Every non-witnessed member is a NON-PASS with a distinct cause, so an operator
    can tell "no witness at all" (the bootstrap path, or a hook the harness
    discarded on timeout) from "a witness that failed verification".

    Issues: #1802, #1807
    """

    TYPED_USER_WITNESSED = "typed_user_witnessed"
    MODEL_SKILL_WITNESSED = "model_skill_witnessed"
    MODEL_BOOTSTRAP = "model_bootstrap"
    WITNESS_REFUSED = "witness_refused"
    WITNESS_UNAVAILABLE = "witness_unavailable"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class AuthorityVerdict:
    """The outcome of :func:`classify_current_run_authority`.

    Attributes:
        authority: The classification.
        legacy_mac: True when integrity was established from the pre-#1807
            v1 message, which does NOT bind the owner. Such a state is
            authorized only because its owner claim is corroborated by the
            independent run-start receipt; callers SHOULD log it.
        detail: Operator-facing explanation naming the seam.
        origin: Which principal's native event witnessed this run starting.
            Defaults to :attr:`RunOrigin.NOT_EVALUATED`, which is what every
            REFUSAL carries: an unauthorized run has no origin to attribute, and
            saying so beats guessing. Only the AUTHORIZED path evaluates it.
        origin_detail: Operator-facing explanation of the origin verdict.
    """

    authority: RunAuthority
    legacy_mac: bool
    detail: str
    origin: RunOrigin = RunOrigin.NOT_EVALUATED
    origin_detail: str = ""

    @property
    def authorized(self) -> bool:
        """Whether this state may act as the current run."""
        return self.authority is RunAuthority.AUTHORIZED

    @property
    def native_origin(self) -> bool:
        """Whether a NATIVE hook process witnessed this run's initiation.

        True for both witnessed classes. It says the event was native; it does
        NOT say a user authorized the run — for that, read
        :attr:`typed_user_origin`.
        """
        return self.origin in (
            RunOrigin.TYPED_USER_WITNESSED,
            RunOrigin.MODEL_SKILL_WITNESSED,
        )

    @property
    def typed_user_origin(self) -> bool:
        """Whether a USER-TYPED slash command witnessed this run's initiation.

        The only origin class that may stand for user authorization (#1802). A
        model-invoked Skill origin returns False here, always.
        """
        return self.origin is RunOrigin.TYPED_USER_WITNESSED


def _run_start_receipt(session_id: str) -> Optional[str]:
    """Read the run-start receipt for *session_id*, or ``None``.

    Lazily imports ``pipeline_completion_state`` — that module imports THIS one
    at module scope, so a top-level import here would be a cycle.

    Args:
        session_id: The owner whose receipt to read.

    Returns:
        The recorded run id, or ``None`` when there is no receipt (including
        when the ledger module is unavailable).
    """
    try:
        try:
            from .pipeline_completion_state import get_run_start_receipt  # type: ignore
        except ImportError:
            from pipeline_completion_state import get_run_start_receipt  # type: ignore
    except ImportError:
        return None
    try:
        return get_run_start_receipt(session_id)
    except Exception:  # noqa: BLE001 - a probe must not raise into a gate
        return None


def _native_origin_check(session_id: str, state: dict) -> Any:
    """Read the native-origin witness for *session_id*, or ``None``.

    Extracts the run bindings from *state* using the ledger module's OWN key
    tuple, so the set of bindings a witness covers has one home. Lazily imported
    for the same reason :func:`_run_start_receipt` is: the ledger module imports
    THIS one at module scope.

    Args:
        session_id: The owner presenting the run.
        state: The sentinel contents whose bindings the witness must match.

    Returns:
        A ``pipeline_completion_state.NativeOriginCheck``, or ``None`` when the
        reader is unavailable — which callers MUST treat as "cannot tell", not as
        a verdict about the witness.
    """
    try:
        try:
            from .pipeline_completion_state import (  # type: ignore
                NATIVE_ORIGIN_BINDING_KEYS,
                check_native_origin,
            )
        except ImportError:
            from pipeline_completion_state import (  # type: ignore
                NATIVE_ORIGIN_BINDING_KEYS,
                check_native_origin,
            )
    except ImportError:
        return None
    bindings = {key: state.get(key, "") for key in NATIVE_ORIGIN_BINDING_KEYS}
    return check_native_origin(session_id, bindings)


def _classify_run_origin(
    owner: str, state: dict, origin_lookup: Any = None
) -> Tuple[RunOrigin, str]:
    """Map the witness check onto the single origin vocabulary.

    This is the ONLY place a native EVENT NAME becomes an origin CLASS. The ledger
    module reports facts (present / valid / event) and never names a class, so the
    typed-versus-Skill distinction cannot drift between two homes.

    Fails closed in every direction: a raising or absent reader is
    :attr:`RunOrigin.WITNESS_UNAVAILABLE` (an instrument failure, reported as
    such), an absent witness is :attr:`RunOrigin.MODEL_BOOTSTRAP` (the
    compatibility path — a NON-PASS for origin, not a refusal of the run), and
    anything else is :attr:`RunOrigin.WITNESS_REFUSED`.

    Args:
        owner: The verified run owner.
        state: The sentinel contents.
        origin_lookup: Callable ``(owner, state)``, for tests. Defaults to
            :func:`_native_origin_check`.

    Returns:
        ``(origin, detail)``.
    """
    lookup = origin_lookup or _native_origin_check
    try:
        check = lookup(owner, state)
    except Exception as exc:  # noqa: BLE001 - a probe must not raise into a gate
        return (
            RunOrigin.WITNESS_UNAVAILABLE,
            f"the native-origin reader raised {type(exc).__name__}: {exc}. "
            "'cannot tell' is not 'native' (INV-7)",
        )

    if check is None or not getattr(check, "instrument_ok", False):
        return (
            RunOrigin.WITNESS_UNAVAILABLE,
            getattr(check, "detail", None)
            or "the native-origin reader is unavailable, so no origin can be judged",
        )
    if not getattr(check, "present", False):
        return RunOrigin.MODEL_BOOTSTRAP, check.detail
    if not getattr(check, "valid", False):
        return RunOrigin.WITNESS_REFUSED, check.detail
    if check.event == "UserPromptExpansion":
        return RunOrigin.TYPED_USER_WITNESSED, check.detail
    if check.event == "PreToolUse":
        return (
            RunOrigin.MODEL_SKILL_WITNESSED,
            f"{check.detail} — a MODEL-invoked Skill call: native event, NOT user "
            "authorization",
        )
    return (
        RunOrigin.WITNESS_REFUSED,
        f"witness reports event {check.event!r}, which maps to no origin class",
    )


def classify_current_run_authority(
    state: Any,
    presented_session_id: str,
    *,
    receipt_lookup: Any = None,
    origin_lookup: Any = None,
) -> AuthorityVerdict:
    """Classify whether *state* may authorize the CURRENT pipeline run.

    Two independent carriers must agree, and NEITHER is sufficient alone:

    1. The signed sentinel — an owner-bound MAC over the run bindings
       (:func:`sign_state`). Alone it is mintable by the constrained caller,
       which is Issue #1807's A3/A7.
    2. The run-start receipt — ``current_run_id`` stamped by
       ``pipeline_completion_state.record_run_start`` at STEP 0, BEFORE any
       agent ran. Alone it is an UNSIGNED ledger, which is A4: a retained run
       id must never rebuild authority for a run whose sentinel is gone.

    EVIDENCE LIMIT — read before quoting any green from this function.
    Both carriers are ordinary files, and BOTH are writable by the principal
    this gate constrains: ``sign_state`` creates the secret it signs with, and
    ``record_run_start`` is reachable from model-controlled Bash. The two-carrier
    conjunction therefore removes the SINGLE-artifact forgery (a lone self-minted
    sentinel, a lone retained ledger run id) and is SELF-MINTABLE by a caller
    willing to write both. What would make it provenance is the ORIGIN split —
    model-controlled Bash/Write/Edit/MCP refused on the sentinel, the secret
    store AND the ledger while native hook processes still write them. That is
    acceptance case A9, evidence class ``native-boundary``, currently OPEN and
    UNMEASURED. This function closes the in-process route only; it does not make
    the carriers trustworthy. See ``pipeline_completion_state.get_run_start_receipt``
    for the same caveat at the reading seam.

    Args:
        state: Parsed sentinel contents (any type; non-dicts are refused).
        presented_session_id: The caller identity, supplied by the call site
            from its native transport. REQUIRED, and an indeterminate value
            (``""``, ``"unknown"``) is a REFUSAL
            (:attr:`RunAuthority.IDENTITY_UNAVAILABLE`), never a wildcard that
            skips owner verification: an unavailable or synthetic caller is
            precisely the case #1807 requires to fail closed. This function
            deliberately does NOT fall back to the state's own ``session_id`` —
            that would let the artifact under examination nominate its own
            examiner.
        receipt_lookup: Callable taking the owner and returning the recorded
            run id, for tests. Defaults to :func:`_run_start_receipt`.

    Returns:
        An :class:`AuthorityVerdict`. NEVER raises — every malformed shape
        (a non-dict ``state``, a non-str/malformed ``hmac``, or a non-str signed
        field such as ``mode=123``) yields an unauthorized verdict, not an
        exception. This depends on :func:`verify_state_hmac` returning a bool for
        malformed input rather than propagating a ``TypeError`` (Issue #1807);
        the bare call below is the only site that would otherwise raise here.
    """
    if not isinstance(state, dict) or not state:
        return AuthorityVerdict(
            RunAuthority.NO_STATE,
            False,
            "no pipeline state: nothing to authorize",
        )

    if _synthetic_identity_predicate() is None:
        # INSTRUMENT failure, reported as such rather than as a judgment about
        # the identity: without the canonical synthetic-id predicate this
        # function cannot tell a real owner from one the pipeline minted for
        # itself, and "cannot tell" is "not passed" (INV-7).
        return AuthorityVerdict(
            RunAuthority.PREDICATE_UNAVAILABLE,
            False,
            "pipeline_completion_state.is_synthetic_session_id is unavailable, "
            "so no identity can be judged. This is a DEPENDENCY failure, not a "
            "verdict about the state. REQUIRED NEXT ACTION: run "
            "`bash scripts/deploy-all.sh` — the deployed lib/ is incomplete",
        )

    run_id = state.get("run_id")
    if not isinstance(run_id, str) or not _re.match(r"^[a-zA-Z0-9_-]{1,64}$", run_id):
        return AuthorityVerdict(
            RunAuthority.NO_RUN_IDENTITY,
            False,
            "state carries no usable run_id, so it identifies no run to "
            "authorize (Issue #1807: 'exists and parses' is not 'identifies a "
            f"run'); keys={sorted(state)}",
        )

    owner = state.get("session_id")
    if not _is_usable_owner_identity(owner):
        return AuthorityVerdict(
            RunAuthority.OWNER_UNAVAILABLE,
            False,
            f"state owner {owner!r} is absent, placeholder or SYNTHETIC "
            "(stop-N / test-* / unknown), so its ownership claim is "
            "unverifiable and INV-7 reads that as 'not passed'",
        )
    owner = owner.strip()

    if not _is_usable_owner_identity(presented_session_id):
        # Issue #1807: an absent, placeholder or SYNTHETIC caller identity is the
        # "unavailable/synthetic owner" the issue requires to fail closed. The
        # pre-review draft treated it as "cannot tell" and skipped the owner
        # comparison, which made every indeterminate caller a wildcard.
        return AuthorityVerdict(
            RunAuthority.IDENTITY_UNAVAILABLE,
            False,
            f"the caller presented no usable identity ({presented_session_id!r} "
            f"is absent, placeholder or synthetic), so the owner claim {owner!r} "
            "cannot be checked against anybody. REQUIRED NEXT ACTION: supply the "
            "caller identity from the native transport; do NOT default it from "
            "the state being examined",
        )
    if presented_session_id.strip() != owner:
        return AuthorityVerdict(
            RunAuthority.UNQUALIFIED_OWNER,
            False,
            f"state is owned by {owner!r} but presented by "
            f"{presented_session_id.strip()!r}",
        )

    if state.get("hmac") is None:
        # Legacy RECOGNITION is defensible; silent promotion to AUTHORIZATION
        # is not (Issue #1807 A8). This is the shape fix-mode F1 used to write.
        return AuthorityVerdict(
            RunAuthority.UNSIGNED_LEGACY,
            True,
            "state carries no MAC: recognized as legacy/unsigned, which is "
            "never current-run authority (Issue #1807 A8)",
        )

    # STRICT verification (Issue #1807): the authority decision MUST NOT inherit
    # the #753 stale-mtime fail-open. A tampered signed field (even one outside
    # run_id/owner) on a state whose legacy sentinel has gone stale would
    # otherwise verify True here and — with a still-matching receipt — AUTHORIZE a
    # tampered state. strict=True refuses any unverifiable MAC regardless of mtime.
    if not verify_state_hmac(state, presented_session_id, strict=True):
        return AuthorityVerdict(
            RunAuthority.MAC_INVALID,
            False,
            "state MAC did not verify for its declared owner (strict: no stale "
            "fail-open in the authority path)",
        )

    legacy_mac = _declared_mac_version(state) not in (_STATE_MAC_V2, _STATE_MAC_V3)

    lookup = receipt_lookup or _run_start_receipt
    try:
        receipt = lookup(owner)
    except Exception:  # noqa: BLE001 - a probe must not raise into a gate
        receipt = None
    if not isinstance(receipt, str) or not receipt.strip():
        return AuthorityVerdict(
            RunAuthority.RECEIPT_UNAVAILABLE,
            legacy_mac,
            f"no run-start receipt exists for owner {owner!r}: a self-minted "
            "MAC is not provenance (Issue #1807 A3/A7). REQUIRED NEXT ACTION: "
            "start a fresh /implement run — do NOT reconstruct run identity by "
            "hand, from chat, or from the completion ledger",
        )
    if receipt.strip() != run_id:
        return AuthorityVerdict(
            RunAuthority.UNQUALIFIED_OWNER,
            legacy_mac,
            f"run-start receipt for {owner!r} names run {receipt.strip()!r}, "
            f"not {run_id!r}",
        )

    # ORIGIN is evaluated ONLY here, on the authorized path (Issue #1807 A7/A9).
    # An unauthorized run has no origin to attribute, and a WITNESS_REFUSED
    # verdict deliberately does NOT demote `authority`: the origin level is
    # strictly additive, so a corrupt or forged witness must not become a
    # denial-of-service lever that kills a legitimate live run. It refuses the
    # ORIGIN CLAIM and nothing else.
    origin, origin_detail = _classify_run_origin(owner, state, origin_lookup)
    return AuthorityVerdict(
        RunAuthority.AUTHORIZED,
        legacy_mac,
        f"run {run_id} authorized for owner {owner}"
        + (" (legacy v1 MAC: owner corroborated by receipt only)" if legacy_mac else ""),
        origin,
        origin_detail,
    )


# =============================================================================
# PUBLIC API
# =============================================================================


def create_pipeline(
    run_id: str,
    feature: str,
    *,
    mode: str = "full",
) -> PipelineState:
    """Create a new pipeline with all steps in PENDING status.

    Args:
        run_id: Unique identifier for this pipeline run.
        feature: Description of the feature being implemented.
        mode: Pipeline mode (e.g., "full", "quick", "batch").

    Returns:
        PipelineState with all 13 steps initialized to PENDING.
    """
    now = _now()
    steps = {step.value: _make_step_dict() for step in STEP_SEQUENCE}
    return PipelineState(
        run_id=run_id,
        mode=mode,
        feature=feature,
        steps=steps,
        created_at=now,
        updated_at=now,
    )


def get_state_path(run_id: str) -> Path:
    """Return the filesystem path for a pipeline state file.

    Args:
        run_id: The pipeline run identifier (alphanumeric, dashes, underscores).

    Returns:
        Path to the JSON state file in /tmp.

    Raises:
        ValueError: If run_id contains path traversal characters.
    """
    import re

    if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", run_id):
        raise ValueError(
            f"run_id must be alphanumeric with dashes/underscores (1-128 chars): {run_id!r}"
        )
    return Path(f"/tmp/pipeline_state_{run_id}.json")


def load_pipeline(run_id: str) -> Optional[PipelineState]:
    """Load a pipeline state from disk.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        PipelineState if found, None otherwise (backward compatible).
    """
    path = get_state_path(run_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return PipelineState(
            run_id=data["run_id"],
            mode=data["mode"],
            feature=data["feature"],
            steps=data.get("steps", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            redispatch_agents=data.get("redispatch_agents", {}),
            remediation_occurred=data.get("remediation_occurred", False),  # Issue #1271: Default False for old state files
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_pipeline(state: PipelineState) -> Path:
    """Write pipeline state to disk as JSON.

    Args:
        state: The pipeline state to persist.

    Returns:
        Path to the written state file.
    """
    state.updated_at = _now()
    path = get_state_path(state.run_id)
    data = {
        "run_id": state.run_id,
        "mode": state.mode,
        "feature": state.feature,
        "steps": state.steps,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "redispatch_agents": state.redispatch_agents,
        "remediation_occurred": state.remediation_occurred,  # Issue #1271
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def can_advance(state: PipelineState, step: Step) -> Tuple[bool, str]:
    """Check whether the pipeline can advance to the given step.

    Gate logic:
    1. Step must not already be PASSED (can't re-enter completed steps).
    2. All prior steps in STEP_SEQUENCE must be resolved (not PENDING).
    3. GATE_CONDITIONS prerequisites must be PASSED or SKIPPED.

    Args:
        state: Current pipeline state.
        step: The step to check advancement for.

    Returns:
        Tuple of (allowed, reason). If allowed, reason is empty string.
    """
    current_status = _get_status(state, step)
    if current_status == StepStatus.PASSED:
        return False, f"Step {step.value} is already PASSED and cannot be re-entered"

    # Check all prior steps are resolved (not PENDING)
    step_idx = STEP_SEQUENCE.index(step)
    for prior_step in STEP_SEQUENCE[:step_idx]:
        prior_status = _get_status(state, prior_step)
        if prior_status == StepStatus.PENDING:
            return False, (
                f"Step {prior_step.value} is still PENDING. "
                f"All prior steps must be resolved before advancing to {step.value}"
            )

    # Check gate conditions
    if step in GATE_CONDITIONS:
        for prereq in GATE_CONDITIONS[step]:
            prereq_status = _get_status(state, prereq)
            if prereq_status not in (StepStatus.PASSED, StepStatus.SKIPPED):
                return False, (
                    f"Gate condition not met: {prereq.value} must be PASSED or SKIPPED "
                    f"before advancing to {step.value} "
                    f"(current: {prereq_status.value})"
                )

    return True, ""


def advance(
    state: PipelineState,
    step: Step,
    *,
    status: StepStatus = StepStatus.RUNNING,
    error: Optional[str] = None,
) -> PipelineState:
    """Advance a step to a new status (default: RUNNING).

    Args:
        state: Current pipeline state.
        step: The step to advance.
        status: Target status (default RUNNING).
        error: Optional error message.

    Returns:
        Updated PipelineState.

    Raises:
        ValueError: If the step cannot be advanced (already PASSED).
    """
    current_status = _get_status(state, step)
    if current_status == StepStatus.PASSED:
        raise ValueError(
            f"Step {step.value} is already PASSED and cannot be re-entered"
        )

    now = _now()
    record = state.steps.get(step.value)
    if record is None:
        record = _make_step_dict()
        state.steps[step.value] = record

    record["status"] = status.value
    if status == StepStatus.RUNNING and record.get("started_at") is None:
        record["started_at"] = now
    if error is not None:
        record["error"] = error
    if status in (StepStatus.PASSED, StepStatus.FAILED, StepStatus.SKIPPED):
        record["completed_at"] = now

    state.updated_at = now
    save_pipeline(state)
    return state


def complete_step(
    state: PipelineState,
    step: Step,
    *,
    passed: bool = True,
    error: Optional[str] = None,
) -> PipelineState:
    """Convenience function to mark a step as PASSED or FAILED.

    Args:
        state: Current pipeline state.
        step: The step to complete.
        passed: True for PASSED, False for FAILED.
        error: Optional error message (typically set when passed=False).

    Returns:
        Updated PipelineState.
    """
    target_status = StepStatus.PASSED if passed else StepStatus.FAILED
    return advance(state, step, status=target_status, error=error)


def skip_step(
    state: PipelineState,
    step: Step,
    *,
    reason: str,
) -> PipelineState:
    """Skip a step (only allowed for SKIPPABLE_STEPS).

    Args:
        state: Current pipeline state.
        step: The step to skip.
        reason: Why this step is being skipped.

    Returns:
        Updated PipelineState.

    Raises:
        ValueError: If the step is not in SKIPPABLE_STEPS.
    """
    if step not in SKIPPABLE_STEPS:
        raise ValueError(
            f"Step {step.value} is not skippable. "
            f"Only these steps can be skipped: {[s.value for s in SKIPPABLE_STEPS]}"
        )
    return advance(state, step, status=StepStatus.SKIPPED, error=reason)


def get_trace(state: PipelineState) -> List[Dict[str, Any]]:
    """Get an ordered list of step records with timing information.

    Only includes steps that have been started (not PENDING).

    Args:
        state: Current pipeline state.

    Returns:
        List of dicts with step name, status, timestamps, and duration_s.
    """
    trace = []
    for step in STEP_SEQUENCE:
        record = state.steps.get(step.value)
        if record is None or record.get("status") == StepStatus.PENDING.value:
            continue

        entry: Dict[str, Any] = {
            "step": step.value,
            "status": record["status"],
            "started_at": record.get("started_at"),
            "completed_at": record.get("completed_at"),
            "error": record.get("error"),
            "duration_s": None,
        }

        # Calculate duration if both timestamps exist
        started = record.get("started_at")
        completed = record.get("completed_at")
        if started and completed:
            try:
                start_dt = datetime.fromisoformat(started)
                end_dt = datetime.fromisoformat(completed)
                entry["duration_s"] = round((end_dt - start_dt).total_seconds(), 3)
            except (ValueError, TypeError):
                pass

        trace.append(entry)

    return trace


def get_completion_summary(state: PipelineState) -> Dict[str, Any]:
    """Build a completion summary from pipeline state.

    Extracts agent count, step count, mode, overall status, and timing.

    Args:
        state: The completed pipeline state.

    Returns:
        Dict with keys: agent_count, step_count, mode, status, started_at,
        completed_at, duration_s.
    """
    trace = get_trace(state)
    step_count = len(trace)

    # Count distinct agents from step names that map to agents
    agent_step_names = {
        "alignment", "research_cache", "research", "plan",
        "acceptance_tests", "tdd_tests", "implement",
        "validate", "verify", "report",
    }
    agent_count = sum(
        1 for entry in trace
        if entry.get("step") in agent_step_names
        and entry.get("status") in ("passed", "skipped")
    )

    # Determine overall status
    statuses = [entry.get("status", "pending") for entry in trace]
    if any(s == "failed" for s in statuses):
        overall_status = "failed"
    elif all(s in ("passed", "skipped") for s in statuses) and statuses:
        overall_status = "completed"
    else:
        overall_status = "partial"

    # Timing
    started_at = state.created_at
    completed_at = state.updated_at
    duration_s = None  # type: Optional[float]
    if started_at and completed_at:
        try:
            start_dt = datetime.fromisoformat(started_at)
            end_dt = datetime.fromisoformat(completed_at)
            duration_s = round((end_dt - start_dt).total_seconds(), 3)
        except (ValueError, TypeError):
            pass

    return {
        "agent_count": agent_count,
        "step_count": step_count,
        "mode": state.mode,
        "status": overall_status,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_s": duration_s,
    }


def finalize_to_session(
    run_id: str,
    *,
    feature_ref: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> bool:
    """Merge pipeline state into session record for post-analysis.

    Loads pipeline state from /tmp/pipeline_state_{run_id}.json, reads the
    session record from docs/sessions/{run_id}-pipeline.json (if it exists),
    merges completion data, and writes back atomically.

    In batch mode (feature_ref is provided), each feature's pipeline data is
    appended to a ``features`` list in the session record, enabling per-feature
    analysis.  Flat ``pipeline_summary`` / ``pipeline_steps`` fields are still
    written for backward compatibility (last-feature-wins).

    Args:
        run_id: The pipeline run identifier.
        feature_ref: Optional feature reference for batch mode (e.g. issue
            number or feature slug).  When provided, the session record uses
            schema_version "2.0" with a ``features`` list.
        batch_id: Optional batch identifier to tag the session record.

    Returns:
        True if finalization succeeded, False otherwise.
    """
    import os
    import tempfile

    # Load pipeline state
    state = load_pipeline(run_id)
    if state is None:
        return False

    # Build completion summary
    summary = get_completion_summary(state)

    # Find session record path
    session_dir = Path(os.getcwd()) / "docs" / "sessions"
    session_file = session_dir / f"{run_id}-pipeline.json"

    # Load existing session record or create new one
    session_data = {}  # type: Dict[str, Any]
    if session_file.exists():
        try:
            session_data = json.loads(session_file.read_text())
        except (json.JSONDecodeError, OSError):
            session_data = {}

    # Merge pipeline data into session record (flat fields for v1 compat)
    session_data["pipeline_summary"] = summary
    session_data["pipeline_steps"] = state.steps
    session_data["run_id"] = run_id
    session_data["mode"] = state.mode
    session_data["feature"] = state.feature

    if feature_ref is not None:
        # Batch mode: append to features list (schema v2.0)
        session_data["schema_version"] = "2.0"
        if batch_id is not None:
            session_data["batch_id"] = batch_id

        features = session_data.setdefault("features", [])

        # Idempotency: skip if feature_ref already recorded
        existing_refs = {f.get("feature_ref") for f in features}
        if feature_ref not in existing_refs:
            features.append({
                "feature_ref": feature_ref,
                "pipeline_summary": summary,
                "pipeline_steps": state.steps,
                "feature": state.feature,
            })
    else:
        # Single-feature mode: set v1.0 schema (default)
        session_data.setdefault("schema_version", "1.0")

    # Write atomically (temp file + os.replace)
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    try:
        atomic_write_json(session_file, session_data, indent=2)
    except Exception:
        return False

    return True


def cleanup_pipeline(run_id: str) -> None:
    """Remove the pipeline state file and its secret from disk.

    Args:
        run_id: The pipeline run identifier.

    Does not raise if the files don't exist.
    """
    path = get_state_path(run_id)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    # Also clean up the associated secret file
    cleanup_pipeline_secret(run_id)



def set_remediation_flag(run_id: str) -> bool:
    """Set the remediation_occurred flag to True in the pipeline state.
    
    Issue #1271: This is called by the coordinator at STEP 11 when remediation
    is triggered (implementer re-invoked in REMEDIATION MODE).
    
    Args:
        run_id: The pipeline run identifier.
        
    Returns:
        True if the flag was successfully set, False otherwise.
    """
    state = load_pipeline(run_id)
    if state is None:
        return False
    
    state.remediation_occurred = True
    try:
        save_pipeline(state)
        return True
    except Exception:
        return False


def get_remediation_flag(run_id: str) -> bool:
    """Get the remediation_occurred flag from the pipeline state.
    
    Issue #1271: This is called by the coordinator at STEP 12 to determine
    whether doc-master needs to be re-invoked due to STEP 11 remediation.
    
    Args:
        run_id: The pipeline run identifier.
        
    Returns:
        True if remediation occurred, False otherwise (including if state not found).
    """
    state = load_pipeline(run_id)
    if state is None:
        return False
    
    return state.remediation_occurred

# =============================================================================
# BASE COMMIT ANCHORING (Issue #1069)
# =============================================================================
#
# Pre-existing working-tree modifications cause `git diff --name-only HEAD` to
# include files unrelated to the current pipeline run. When the coordinator
# emits acceptance criteria that reference "files in the diff", spec-validator
# correctly verifies the criterion and FAILs on pre-existing tree state —
# producing a false-positive that requires human override.
#
# The fix anchors diff commands to the commit SHA captured at pipeline start
# (PIPELINE_BASE_COMMIT). This restricts the diff to files actually changed by
# the current run, ignoring any tree state that existed before the pipeline
# began. The base commit is stored in the legacy sentinel state file
# (PIPELINE_STATE_FILE, default <repo>/.claude/local/implement_pipeline_state.json
# — was /tmp/implement_pipeline_state.json before Issue #1206) under the
# 'base_commit' key.


def set_pipeline_base_commit(
    base_commit: str,
    *,
    state_path: Optional[str] = None,
) -> bool:
    """Record PIPELINE_BASE_COMMIT in the pipeline state file.

    Called at pipeline start (full-pipeline STEP 1 or fix-mode STEP F1) to
    capture the git HEAD before any pipeline-driven file modifications. The
    captured SHA is later used by spec-validator (STEP 8.5 / STEP F3.5) to
    anchor `git diff --name-only` commands so the diff reflects only files
    changed by the current pipeline run, not pre-existing tree state.

    Args:
        base_commit: The git commit SHA captured via `git rev-parse HEAD`.
            Empty string is permitted (e.g., no-commit repository) but
            disables anchoring — callers should fall back to plain HEAD diff
            in that case.
        state_path: Optional override for the state file path. Defaults to
            the PIPELINE_STATE_FILE env var, falling back to the per-repo
            <repo>/.claude/local/implement_pipeline_state.json (Issue #1206).

    Returns:
        True if the base commit was successfully written. False (with NO write
        and NO mutation) if the state file does not exist, could not be
        read/written, or is signed but (a) carries no determinate owner, (b)
        declares a MAC version below the current one, or (c) does not already
        hold a valid current-version strict signature (Issue #1807 fail-closed:
        re-signing an unverified state would launder tampering into a valid MAC).
        A signed state that passes all three is RE-SIGNED after ``base_commit`` is
        set so the MAC keeps covering it; an unsigned legacy state is left
        unsigned (backward compatibility).
    """
    path = state_path or os.environ.get(
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
    )
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    # Issue #1807 (all-six binding): base_commit is inside the v3 signed message,
    # so a signed sentinel must be RE-SIGNED after base_commit changes or its MAC
    # stops covering its own base_commit. But re-signing is a SIGNING ORACLE: if
    # we re-signed an unverified state, a crafted state (valid-shaped owner, but
    # tampered issue_number/subject/base_commit whose current MAC is invalid)
    # would receive a FRESH VALID v3 signature — laundering the tampering. So a
    # signed state is re-signed ONLY when it ALREADY holds a valid CURRENT-version
    # strict signature. Order (any failure returns False with NO mutation, NO
    # write): (if signed) determinate owner -> declared version == current ->
    # strict verify -> then set base_commit + re-sign + write.
    #
    # An unsigned legacy state (no 'hmac') is written as-is (no owner, no MAC),
    # which verify_state_hmac still recognizes (backward compatibility).
    signed = state.get("hmac") is not None
    if signed:
        owner = state.get("session_id")
        if not _is_determinate_session_id(owner):
            # No verifiable owner: refuse rather than sign with an empty owner
            # (the #1807 forgery shape).
            return False
        if _declared_mac_version(state) != _STATE_MAC_CURRENT:
            # A below-current version does NOT bind all six fields (v2 omits
            # issue_number/subject), so verifying at that version then re-signing
            # to current would launder those unbound fields into an authenticated
            # state. A stale-version sentinel must be re-initialized by a fresh
            # run, not upgraded-in-place via a base_commit write. Fail closed.
            return False
        if not verify_state_hmac(state, owner, strict=True):
            # The existing signature is invalid: refuse. Re-signing here would
            # launder the tampering into a valid MAC (the #1807 signing oracle).
            return False

    state["base_commit"] = base_commit
    if signed:
        sign_state(state, state["session_id"])
    try:
        atomic_write_json(Path(path), state)
    except OSError:
        return False
    return True


def get_pipeline_base_commit(
    state_path: Optional[str] = None,
) -> Optional[str]:
    """Read PIPELINE_BASE_COMMIT from the pipeline state file.

    Returns the commit SHA captured at pipeline start, or None if not set.
    Callers SHOULD fall back to plain `HEAD` when the base commit is missing
    (e.g., legacy pipelines, fresh state files, no-commit repos).

    Args:
        state_path: Optional override for the state file path. Defaults to
            the PIPELINE_STATE_FILE env var, falling back to the per-repo
            <repo>/.claude/local/implement_pipeline_state.json (Issue #1206).

    Returns:
        The base commit SHA string if recorded and non-empty, otherwise None.
    """
    path = state_path or os.environ.get(
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
    )
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    base = state.get("base_commit")
    if not isinstance(base, str) or not base.strip():
        return None
    return base.strip()


# =============================================================================
# BASELINE SCOPE HELPERS (Issue #990)
# =============================================================================
#
# In the #972 run, the coordinator's STEP 5 test gate initially reported 188
# "new failures" that were pre-existing failures in test directories outside
# the baseline scope. The mismatch arose because the coordinator captured a
# baseline test count using one directory set (e.g., `tests/unit/ tests/integration/`)
# but the implementer ran tests against a broader set (e.g., adding
# `tests/regression/ tests/property/`). Directories never in the baseline
# appeared as regressions.
#
# The fix: normalize test scope at STEP 1 by recording the exact pytest
# invocation used for baseline capture in the sentinel. The implementer
# MUST use this recorded scope — not a self-chosen broader one — when
# running pytest at STEP 8.

#: The canonical baseline pytest command — stored as a list for shell-injection
#: safety (never joined into a shell string). Callers that need a string form
#: must join explicitly: ``" ".join(CANONICAL_BASELINE_CMD)``.
#:
#: Issue #1533 — ``--continue-on-collection-errors`` is deliberately ABSENT.
#: Surviving a collection error would let the run continue with the erroring
#: module's tests silently missing from the baseline, and would suppress the
#: loudest signal (``Interrupted:`` plus exit code 2) that
#: ``fix_forward.detect_capture_failure()`` relies on to write the
#: ``__COLLECTION_ERROR__`` sentinel. A collection error must abort loudly and
#: be reported as UNKNOWN, never masked into a plausible-looking baseline.
CANONICAL_BASELINE_CMD: List[str] = [
    "pytest",
    "tests/unit",
    "tests/integration",
    "-q",
    "--tb=no",
]


def record_baseline_scope(
    state_path: str,
    baseline_cmd: List[str],
    baseline_count: int,
) -> bool:
    """Persist baseline test scope into the pipeline sentinel JSON.

    Reads the existing sentinel at ``state_path``, merges ``baseline_cmd``
    and ``baseline_count`` under those exact key names, and writes back
    atomically (temp-file + os.replace). Overwrites any existing
    ``baseline_cmd``/``baseline_count`` keys — re-baselining within a
    session is intentional.

    ``baseline_cmd`` is stored as a list (not a shell string) to eliminate
    shell-injection ambiguity when it is later read back and passed directly
    to ``subprocess.run``.

    Args:
        state_path: Absolute path to the pipeline sentinel JSON file.
        baseline_cmd: The exact pytest invocation used for baseline capture,
            as a list of strings (e.g., ``["pytest", "tests/unit", "-q",
            "--tb=no"]``).
        baseline_count: The total number of tests found by the baseline run.
            As of the regression-gate scope fix this records the count over
            ``bugfix_detector.CANONICAL_TEST_COUNT_DIRS``, which is a
            *superset* of ``baseline_cmd``'s scope (it adds
            ``tests/regression``) — the two fields deliberately describe
            different scopes and must not be compared to each other.

    Returns:
        True on success, False on any IO or JSON error. NEVER raises.
    """
    if not os.path.exists(state_path):
        return False
    try:
        with open(state_path) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    state["baseline_cmd"] = list(baseline_cmd)
    state["baseline_count"] = int(baseline_count)

    try:
        atomic_write_json(Path(state_path), state)
    except (OSError, json.JSONDecodeError):
        return False
    return True


def get_baseline_scope(state_path: str) -> Optional[Dict[str, Any]]:
    """Return the recorded baseline test scope from the pipeline sentinel.

    Returns a dict with keys ``baseline_cmd`` (list of str) and
    ``baseline_count`` (int), or ``None`` if either field is missing or
    malformed (wrong type, empty list, non-integer count). NEVER raises.

    Args:
        state_path: Absolute path to the pipeline sentinel JSON file.

    Returns:
        ``{"baseline_cmd": [...], "baseline_count": N}`` if both fields are
        present and well-formed; ``None`` otherwise.
    """
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    cmd = state.get("baseline_cmd")
    count = state.get("baseline_count")

    if not isinstance(cmd, list) or len(cmd) == 0:
        return None
    if not all(isinstance(item, str) for item in cmd):
        return None
    if not isinstance(count, int):
        return None

    return {"baseline_cmd": cmd, "baseline_count": count}


# =============================================================================
# RUN_ID GENERATION AND LOCKFILE HELPERS (Issue #1047)
# =============================================================================

# Resume classification regexes — order matters (batch first, then hex, then legacy)
_BATCH_ID_RE = _re.compile(r"^batch-")
_RUN_ID_HEX_RE = _re.compile(r"^[a-f0-9]{16}$")
_RUN_ID_LEGACY_TIMESTAMP_RE = _re.compile(r"^\d{8}-\d{6}$")  # YYYYMMDD-HHMMSS back-compat


def generate_run_id() -> str:
    """Generate a 16-char hex run_id via secrets.token_hex(8).

    The format matches ``_RUN_ID_HEX_RE`` (16 lowercase hex characters) and
    is also accepted by the ``_RUN_ID_RE`` validator in
    ``pipeline_completion_state``.

    Returns:
        16-character lowercase hex string (e.g., ``'a3f1b2c4d5e67890'``).
    """
    return secrets.token_hex(8)


def get_lockfile_path(run_id: str) -> Path:
    """Return the lockfile path for the given run_id.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        Path to ``/tmp/pipeline_<run_id>.lock``.
    """
    return Path(f"/tmp/pipeline_{run_id}.lock")


def acquire_run_lock(run_id: str) -> Optional[int]:
    """Acquire exclusive non-blocking lock on /tmp/pipeline_<run_id>.lock.

    Uses ``fcntl.flock(LOCK_EX | LOCK_NB)``.  The OS releases the lock
    automatically when the process exits, even on a crash.  The caller must
    hold the returned file descriptor open for the entire duration of the
    pipeline run; closing it releases the lock.

    Args:
        run_id: The pipeline run identifier used to derive the lock path.

    Returns:
        An open file descriptor (int) on success; ``None`` if the lock is
        already held by another process or thread.
    """
    lock_path = get_lockfile_path(run_id)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except (BlockingIOError, OSError):
        os.close(fd)
        return None


def release_run_lock(fd: int) -> None:
    """Release the run lock by unlocking and closing the file descriptor.

    Idempotent — calling on an already-released descriptor does not raise.

    Args:
        fd: The file descriptor returned by ``acquire_run_lock``.
    """
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def classify_resume_id(arg: str) -> str:
    """Classify a ``--resume <id>`` argument by format.

    Classification order (first match wins):

    1. ``batch``        — ``arg`` starts with ``'batch-'``
    2. ``run_id``       — ``arg`` is exactly 16 lowercase hex characters
    3. ``run_id_legacy``— ``arg`` matches ``YYYYMMDD-HHMMSS`` (back-compat)
    4. ``invalid``      — no pattern matched

    Args:
        arg: The raw ``--resume`` argument value.

    Returns:
        One of ``"batch"``, ``"run_id"``, ``"run_id_legacy"``, or
        ``"invalid"``.
    """
    if not arg:
        return "invalid"
    if _BATCH_ID_RE.match(arg):
        return "batch"
    if _RUN_ID_HEX_RE.match(arg):
        return "run_id"
    if _RUN_ID_LEGACY_TIMESTAMP_RE.match(arg):
        return "run_id_legacy"
    return "invalid"
