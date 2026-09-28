"""Issue #1589 regression: plan_gate PreToolUse enum conformance + fix-mode awareness.

THE DEFECT (measured live, twice). ``plan_gate.py`` emitted
``permissionDecision: "block"`` at both refusal sites. The documented
``PreToolUse`` enum is ``allow|deny|ask`` (``docs/HOOKS.md``). Claude Code
2.1.236 REJECTS the envelope ("Hook JSON output validation failed") and the
tool call PROCEEDS — the refusal path fails OPEN. Observed 2026-09-09
(session 6d2a9c8e) and 2026-09-28 (session dddf88aa, two refusal-then-success
pairs ~30-90ms apart).

THE ACTIVATION DEPENDENCY. Changing ``"block"`` to ``"deny"`` alone would turn
a gate that never refused into one that refuses for real — including against
``/implement --fix`` runs, which by design have NO plan file and routinely
write >100-line test modules. So the enum fix ships WITH fix-mode awareness: a
``mode="fix"`` sentinel that ``pipeline_state.classify_current_run_authority``
rules AUTHORIZED permits the write explicitly, and every other sentinel shape
falls through to the deny (``DENY_SHAPES``).

EVIDENCE CLASS OF THIS FILE: ``[source-subprocess]`` — every decision assertion
drives the real worktree hook file as a subprocess with controlled stdin, in a
throwaway git repo with a throwaway ``HOME``. That proves the hook's EMISSION
logic. It does NOT and cannot certify what the installed Claude Code client
does with the emission; that is the ``[native-isolated-profile]`` harness
(``scripts/native_proof_1589.py``) and the deferred post-deploy re-proof.

AMENDMENT 1 (frozen acceptance, 2026-09-28): a PreToolUse hook cannot know at
emission time whether the client honoured its decision. The telemetry row
records EMITTED INTENT only; ``honoured`` stays ``"unverified"`` forever.
``test_hook_never_claims_client_honour`` pins that, because manufacturing an
``honoured: true`` field is precisely the false-provenance defect this issue
exists to kill.
"""

import ast
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pytest

# tests/unit/hooks/test_x.py -> hooks -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
# The hook file under test. Overridable so the RED-BEFORE proof is
# reproducible: point it at the pre-fix bytes (``git show <rev>:<path>``) and
# the refusal/permit tests in this module must FAIL. A regression test that
# cannot be shown failing without the fix is not a regression test.
HOOK_PATH = Path(
    os.environ.get("PLAN_GATE_HOOK_UNDER_TEST") or (HOOKS_DIR / "plan_gate.py")
)

# docs/HOOKS.md: "permissionDecision": "allow|deny|ask"
DOCUMENTED_PRETOOLUSE_DECISIONS = frozenset({"allow", "deny", "ask"})

# plan_gate.SIMPLE_EDIT_LINE_THRESHOLD is 100 newlines.
BIG_CONTENT = "x = 1\n" * 200
SMALL_CONTENT = "x = 1\n" * 5

VALID_PLAN = (
    "# Plan\n\n## WHY + SCOPE\nreason\n\n"
    "## Existing Solutions\nnone\n\n## Minimal Path\nstep\n"
)
INVALID_PLAN = "# Plan\n\nno required sections\n"

SUBPROCESS_TIMEOUT = 10

# Env vars that must not leak from the developer's shell into a hook probe.
_SCRUBBED_ENV = (
    "SKIP_PLAN_CHECK",
    "CLAUDE_SESSION_ID",
    "INTENT_CLASSIFIER_ENFORCE",
    "CLAUDE_PROJECT_DIR",
    "AUTONOMOUS_DEV_ACTIVITY_LOG_DIR",
    "AUTONOMOUS_DEV_BYPASS",
    "PIPELINE_STATE_FILE",
)


@dataclass
class Sandbox:
    """A throwaway git repo + throwaway HOME for one hook probe.

    ``ledger_owners`` records the session ids this probe stamped receipts for.
    The receipt ledger is the one artifact that cannot be redirected into the
    sandbox — ``pipeline_completion_state._state_file_path`` hard-codes
    ``/tmp/pipeline_agent_completions_<sha8>.json`` with no env override — so
    it is purged by id after each test.

    XDIST SAFETY. That ledger path is keyed by ``sha256(session_id)[:8]`` and
    by nothing else — not by ``run_id``, not by worker. CI runs
    ``pytest tests/unit/ -n auto``, so two cases that share a session id share
    a /tmp file across concurrently executing workers: ``flock`` keeps the file
    intact, but worker B's ``record_run_start`` can still land between worker
    A's setup and A's hook subprocess read, flipping A's decision. The fix is
    to remove the shared resource rather than serialize around it: every owner
    id is derived from :attr:`nonce`, which is unique per test CASE, so no two
    cases ever address the same ledger path. The two exceptions are the
    placeholder-owner arms (``"none"``/``"null"``), whose literal spelling IS
    the subject under test and therefore cannot be varied — those mint no
    receipt at all (``OWNER_UNAVAILABLE`` is decided before any receipt
    lookup), so they touch no ledger path either.
    """

    repo: Path
    home: Path
    #: Unique per test case; the root of every derived session id below.
    nonce: str = "static"
    ledger_owners: "list[str]" = field(default_factory=list)

    @property
    def owner(self) -> str:
        """The run-owning session id for THIS case. Determinate, non-synthetic."""
        return f"fixmode-session-1589-{self.nonce}"

    @property
    def foreign(self) -> str:
        """A DIFFERENT live run's session id for THIS case."""
        return f"legitimate-other-run-1589-{self.nonce}"

    def synthetic(self, prefix: str) -> str:
        """A synthetic-shaped id carrying *prefix*, unique to this case.

        The synthetic predicate matches on the PREFIX
        (``pipeline_completion_state._SYNTHETIC_SESSION_ID_PREFIXES``), so
        varying the tail keeps the shape under test while giving the case its
        own ledger path.
        """
        return f"{prefix}{self.nonce}"

    @property
    def sentinel(self) -> Path:
        return self.repo / ".claude" / "local" / "implement_pipeline_state.json"

    def plans_dir(self) -> Path:
        d = self.repo / ".claude" / "plans"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def rows(self) -> "list[dict]":
        """Telemetry rows written by the probe, from either candidate root."""
        out: "list[dict]" = []
        for root in (self.repo, self.home):
            log = root / ".claude" / "logs" / "hook-blocks.jsonl"
            if log.exists():
                out.extend(
                    json.loads(line)
                    for line in log.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
        return out


def _case_nonce(request) -> str:
    """A session-id tail unique to one test CASE, and readable in /tmp.

    The node name (parametrize id included) makes a leaked ledger file
    traceable to the case that leaked it; the uuid suffix guarantees
    uniqueness even across two consecutive runs of the same case, so a stale
    file can never be mistaken for a live one.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", request.node.name.lower()).strip("-")
    return f"{slug[:48]}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sandbox(tmp_path, monkeypatch, request) -> Sandbox:
    """Isolated repo + HOME + per-case session ids.

    ``pipeline_state.sign_state`` writes the per-run secret under
    ``Path.home()/.claude/pipeline_secrets``; the hook subprocess reads it back
    from the same place. Redirecting HOME for the test process and inheriting
    it into the subprocess keeps both on the throwaway copy and leaves the
    developer's real ``~/.claude`` untouched.

    The receipt ledger cannot be redirected that way, so isolation there comes
    from :func:`_case_nonce` instead — see :class:`Sandbox` for why shared
    session ids are an xdist race and not merely untidy.
    """
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    for name in _SCRUBBED_ENV:
        monkeypatch.delenv(name, raising=False)
    box = Sandbox(repo=repo, home=home, nonce=_case_nonce(request))
    yield box
    _purge_receipt_ledger(box)


def _purge_receipt_ledger(box: Sandbox) -> None:
    """Remove the /tmp receipt ledger (and lockfile) this probe wrote.

    ``/tmp`` is not cleared between pytest invocations, so a leaked receipt
    would make the no-receipt arm pass for the wrong reason on the next run.

    The lockfile is ``<ledger>.json.lock`` — ``_flock_state_update`` builds it
    as ``str(_state_file_path(...)) + ".lock"`` (#1807), so ``with_suffix`` is
    the wrong spelling and leaves one file behind per owner. That matters more
    now that owner ids are unique per case: a misspelt purge would leak a new
    lockfile on every run forever instead of reusing a fixed handful.
    """
    pcs = _pipeline_completion_state_module()
    for owner in box.ledger_owners:
        try:
            path = pcs._state_file_path(owner)
        except Exception:  # noqa: BLE001 - cleanup must not fail a test
            continue
        for candidate in (path, Path(str(path) + ".lock")):
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _pipeline_state_module():
    """Import the worktree ``pipeline_state`` (the copy the hook also loads)."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    import pipeline_state  # noqa: PLC0415 - deliberate late import

    return pipeline_state


def _pipeline_completion_state_module():
    """Import the worktree ``pipeline_completion_state`` (the receipt ledger)."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    import pipeline_completion_state  # noqa: PLC0415 - deliberate late import

    return pipeline_completion_state


def write_payload(
    file_path: str = "src/feature.py",
    content: str = BIG_CONTENT,
    *,
    tool_name: str = "Write",
    session_id: str = "",
) -> dict:
    """Build a PreToolUse stdin payload."""
    return {
        "session_id": session_id,
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path, "content": content},
    }


def run_hook(
    sandbox: Sandbox,
    payload,
    *,
    extra_env: "dict | None" = None,
    raw_stdin: "str | None" = None,
) -> "tuple[dict, subprocess.CompletedProcess, float]":
    """Drive the REAL worktree hook file as a subprocess.

    The subject is what executes: no import of ``main()``, no monkeypatched
    decision path. Returns ``(hookSpecificOutput, proc, elapsed_seconds)``.
    """
    env = dict(os.environ)
    for name in _SCRUBBED_ENV:
        env.pop(name, None)
    env["HOME"] = str(sandbox.home)
    if extra_env:
        env.update(extra_env)

    stdin = raw_stdin if raw_stdin is not None else json.dumps(payload)
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(sandbox.repo),
        env=env,
        timeout=SUBPROCESS_TIMEOUT,
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, (
        f"hook exited {proc.returncode}; stderr={proc.stderr}"
    )
    envelope = json.loads(proc.stdout)
    hso = envelope["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    return hso, proc, elapsed


def decide(sandbox: Sandbox, payload, **kwargs) -> "tuple[str, str]":
    """Return ``(permissionDecision, permissionDecisionReason)``."""
    hso, _proc, _elapsed = run_hook(sandbox, payload, **kwargs)
    return hso["permissionDecision"], hso["permissionDecisionReason"]


def record_run_start_receipt(sandbox: Sandbox, owner: str, run_id: str) -> None:
    """Stamp a run-start receipt through the REAL STEP 0 API.

    ``/implement --fix`` calls ``record_run_start(session_id, run_id)`` before
    any agent runs; so does this. Hand-writing the ledger JSON would test a
    file format instead of the initialization path.

    Args:
        sandbox: The probe sandbox — records the owner for ledger cleanup.
        owner: The session the receipt belongs to.
        run_id: The run id the receipt must name.
    """
    pcs = _pipeline_completion_state_module()
    sandbox.ledger_owners.append(owner)
    assert pcs.record_run_start(owner, run_id) is True, (
        f"record_run_start refused owner={owner!r} run_id={run_id!r}; the "
        "receipt arm cannot be set up, so no authority result below is valid"
    )
    assert pcs.get_run_start_receipt(owner) == run_id, (
        "the receipt did not read back — the ledger is not where the hook "
        "subprocess will look for it"
    )


#: The signed-field skeleton every minted sentinel starts from. ONE copy, so a
#: schema change cannot make two arms disagree about what a run looks like.
_BASE_STATE = {
    "issue_number": 1589,
    "session_start": "2026-09-28T08:00:00+00:00",
    "explicitly_invoked": True,
    "alignment_passed": True,
    "alignment_verdict": "auto_pass",
    "subject": "issue 1589",
    "base_commit": "9c678b54",
}


def write_sentinel(sandbox: Sandbox, state: dict) -> dict:
    """Write *state* to the sandbox's legacy sentinel path."""
    sandbox.sentinel.parent.mkdir(parents=True, exist_ok=True)
    sandbox.sentinel.write_text(json.dumps(state), encoding="utf-8")
    return state


def mint_sentinel(
    sandbox: Sandbox,
    *,
    session_id: str,
    mode: str = "fix",
    sign: bool = True,
    sign_as_mode: "str | None" = None,
    sign_for_session: "str | None" = None,
    extra: "dict | None" = None,
    run_id: str = "run1589test",
    receipt: bool = True,
) -> dict:
    """Write a legacy sentinel into the sandbox repo.

    The canonical mint helper: every arm below differs from the certified one
    by keyword, not by a hand-rolled copy of this body.

    ``receipt`` defaults to ON for every arm INCLUDING the refusing ones, so
    each refusal stays ATTRIBUTABLE — a sentinel refused for its tampered mode
    must not be silently refused for a missing receipt instead. It is stamped
    through the real ``record_run_start`` STEP 0 API, not a hand-written ledger.

    Args:
        sandbox: The probe sandbox.
        session_id: Owner written into the state (and the MAC, when signed).
        mode: The mode the sentinel ENDS UP declaring.
        sign: When False, no HMAC at all (the legacy-recognition shape).
        sign_as_mode: Sign with THIS mode, then overwrite with ``mode`` — the
            post-signing tamper shape.
        sign_for_session: Sign for a DIFFERENT owner than ``session_id``.
        extra: Extra top-level keys (e.g. the recovered shape).
        run_id: Run identity; also names the per-run secret file.
        receipt: When True, stamp a genuine run-start receipt for the owner.

    Returns:
        The state dict as written.
    """
    pipeline_state = _pipeline_state_module()
    state = dict(_BASE_STATE)
    state.update(
        run_id=run_id,
        session_id=sign_for_session or session_id,
        mode=sign_as_mode or mode,
    )
    if extra:
        state.update(extra)
    if receipt:
        record_run_start_receipt(sandbox, state["session_id"], run_id)
    if sign:
        pipeline_state.sign_state(state, state["session_id"])
    if sign_as_mode is not None:
        state["mode"] = mode  # post-signing tamper: the MAC no longer covers it
    return write_sentinel(sandbox, state)


def mint_ownerless_sentinel(
    sandbox: Sandbox, *, run_id: str = "run1589ownerless"
) -> dict:
    """Mint a GENUINELY signed fix-mode sentinel that declares NO owner.

    Reviewer FINDING-2's shape, and the one ``mint_sentinel`` cannot produce:
    ``sign_state(state, "")`` takes the real per-run-secret MAC path but its
    indeterminate argument backfills no owner, so the signature is authentic
    while the ownership claim is absent.

    Args:
        sandbox: The probe sandbox.
        run_id: Run identity; also names the per-run secret file.

    Returns:
        The state dict as written.
    """
    pipeline_state = _pipeline_state_module()
    state = dict(_BASE_STATE)
    state.update(run_id=run_id, mode="fix")
    pipeline_state.sign_state(state, "")
    assert "session_id" not in state, "the ownerless arm must be ownerless"
    assert isinstance(state.get("hmac"), str) and state["hmac"], (
        "the ownerless arm must carry a REAL MAC, or it proves nothing new"
    )
    return write_sentinel(sandbox, state)


# ---------------------------------------------------------------------------
# CASE RED-FIXED (emission arm) and its permitting counterpart
# ---------------------------------------------------------------------------


class TestEnumConformantRefusal:
    """The refusal sites emit a decision the PreToolUse protocol accepts."""

    def test_no_plan_complex_write_emits_deny(self, sandbox):
        """RED-FIXED emission: no plan, >100 lines, no sentinel -> deny."""
        decision, reason = decide(sandbox, write_payload())
        assert decision == "deny", (
            "plan_gate must refuse with the documented PreToolUse value. "
            "'block' is outside allow|deny|ask and the client rejects the "
            "envelope, so the write proceeds (Issue #1589)."
        )
        assert "Plan gate" in reason
        assert reason == "Plan gate: no plan file found"

    def test_invalid_plan_emits_deny(self, sandbox):
        """The second refusal site (missing sections) is enum-conformant too."""
        (sandbox.plans_dir() / "PLAN-x.md").write_text(INVALID_PLAN, encoding="utf-8")
        decision, reason = decide(sandbox, write_payload())
        assert decision == "deny"
        assert reason.startswith("Plan gate: plan missing sections:")

    def test_valid_plan_still_allows(self, sandbox):
        """Negative control for both refusal tests: a valid plan permits."""
        (sandbox.plans_dir() / "PLAN-x.md").write_text(VALID_PLAN, encoding="utf-8")
        decision, reason = decide(sandbox, write_payload())
        assert decision == "allow"
        assert "valid plan found" in reason

    def test_every_emitted_decision_is_in_the_documented_enum(self, sandbox):
        """Sweep every reachable emission; none may leave the enum."""
        cases = [
            (write_payload(), {}),
            (write_payload("README.md", BIG_CONTENT), {}),
            (write_payload("src/f.py", SMALL_CONTENT), {}),
            (write_payload(tool_name="Read"), {}),
            (write_payload(), {"extra_env": {"SKIP_PLAN_CHECK": "1"}}),
        ]
        seen = set()
        for payload, kwargs in cases:
            decision, _reason = decide(sandbox, payload, **kwargs)
            seen.add(decision)
            assert decision in DOCUMENTED_PRETOOLUSE_DECISIONS, (
                f"emitted {decision!r}, outside docs/HOOKS.md allow|deny|ask"
            )
        assert {"allow", "deny"} & seen, "the sweep exercised no real decision"

    def test_refusal_latency_fits_the_registration_timeout(self, sandbox):
        """The fix-mode lookup must not blow the 3s hook budget."""
        _hso, _proc, elapsed = run_hook(sandbox, write_payload())
        assert elapsed < 3.0, (
            f"the deny path took {elapsed:.2f}s against a 3s registration "
            "timeout; an overrun silently drops the gate"
        )


# ---------------------------------------------------------------------------
# CASE GREEN-FIXMODE + every shape that must NOT permit
# ---------------------------------------------------------------------------

# Each builder writes ONE sentinel shape and returns the session id the caller
# presents on stdin. Fixture-integrity assertions live in the builder, so a
# broken fixture fails as itself rather than as a false deny.
#
# Owner ids come from the sandbox (``box.owner`` / ``box.foreign`` /
# ``box.synthetic``), never from a module constant: a shared constant is a
# shared /tmp ledger path, which races under ``pytest -n auto``. See
# :class:`Sandbox`.


def _s_absent(box):
    return box.owner


def _s_foreign_owner(box):
    mint_sentinel(
        box, session_id=box.owner, mode="fix", sign_for_session=box.foreign
    )
    assert json.loads(box.sentinel.read_text())["session_id"] == box.foreign
    return box.owner


def _s_mode_tampered(box):
    mint_sentinel(box, session_id=box.owner, mode="fix", sign_as_mode="full")
    assert json.loads(box.sentinel.read_text())["mode"] == "fix"
    return box.owner


def _s_unsigned(box):
    mint_sentinel(box, session_id=box.owner, mode="fix", sign=False)
    assert "hmac" not in json.loads(box.sentinel.read_text())
    return box.owner


def _s_recovered_plain(box):
    write_sentinel(box, {"session_id": box.owner, "recovered": True})
    return box.owner


def _s_recovered_signed(box):
    mint_sentinel(box, session_id=box.owner, mode="fix", extra={"recovered": True})
    return box.owner


def _s_full_mode(box):
    mint_sentinel(box, session_id=box.owner, mode="full")
    return box.owner


def _s_corrupt_json(box):
    box.sentinel.parent.mkdir(parents=True, exist_ok=True)
    box.sentinel.write_text("{not json", encoding="utf-8")
    return box.owner


def _s_ownerless(box):
    mint_ownerless_sentinel(box)
    return box.owner


def _s_no_receipt(box):
    mint_sentinel(box, session_id=box.owner, run_id="runnoreceipt", receipt=False)
    return box.owner


def _s_receipt_other_run(box):
    record_run_start_receipt(box, box.owner, "someotherrun")
    mint_sentinel(box, session_id=box.owner, run_id="runmismatch", receipt=False)
    return box.owner


#: Marker for "the caller presents the owner's own id".
_SELF = object()


def _resolve(value, box):
    """Resolve a per-case id: a callable is given the box, a literal is itself."""
    return value(box) if callable(value) else value


def _owned_by(owner, presented=_SELF, run_id="runowned", receipt=True):
    """Builder factory: a genuine signed sentinel owned by *owner*.

    ``owner`` and ``presented`` may each be a literal or a callable taking the
    sandbox — callables are how a case gets a session id nobody else uses.

    ``presented=_SELF`` means the caller presents the owner's own id (the
    self-consistent shapes); any other value means the caller presents
    something else (the foreign-sentinel shapes).

    ``receipt=False`` is only for owners whose literal spelling IS the subject
    (``"none"``/``"null"``): those cannot be made unique, and they are refused
    at ``OWNER_UNAVAILABLE`` before any receipt is consulted, so minting one
    would buy no attribution and would reintroduce a shared ledger path.
    """

    def _build(box):
        resolved_owner = _resolve(owner, box)
        mint_sentinel(
            box,
            session_id=resolved_owner,
            mode="fix",
            run_id=run_id,
            receipt=receipt,
        )
        return resolved_owner if presented is _SELF else _resolve(presented, box)

    return _build


def _foreign(box):
    return box.foreign


#: Every shape that must NOT obtain the fix-mode permit. One table because the
#: ASSERTION is identical (deny); the mechanisms stay individually attributable
#: because every id names its shape and appears in the failure output.
DENY_SHAPES = [
    pytest.param(_s_absent, id="no-sentinel"),
    pytest.param(_s_foreign_owner, id="owner-binding-foreign-sentinel"),
    pytest.param(_s_mode_tampered, id="post-signing-mode-tamper"),
    pytest.param(_s_unsigned, id="unsigned-legacy-recognition"),
    pytest.param(_s_recovered_plain, id="recovered-plain"),
    pytest.param(_s_recovered_signed, id="recovered-but-genuinely-signed"),
    pytest.param(_s_full_mode, id="authorized-but-mode-full"),
    pytest.param(_s_corrupt_json, id="corrupt-sentinel-json"),
    pytest.param(_s_ownerless, id="signed-but-no-owner-field"),
    pytest.param(_s_no_receipt, id="signed-but-no-run-start-receipt"),
    pytest.param(_s_receipt_other_run, id="receipt-names-a-different-run"),
    # Presented-id band: a REAL sentinel owned by another live run, claimed by a
    # caller naming nobody. "" and "unknown" take a different path from the
    # rest — extract_session_id filters those two spellings to None, which is
    # precisely the drift that let "none"/"null" through as strings.
    pytest.param(_owned_by(_foreign, "none"), id="presented-none"),
    pytest.param(_owned_by(_foreign, "null"), id="presented-null"),
    # Two normalisation variants, kept SEPARATE: a single combined "  NONE  "
    # case that failed could not say whether ``lower()`` or ``strip()`` broke.
    pytest.param(_owned_by(_foreign, "NONE"), id="presented-NONE-uppercase"),
    pytest.param(_owned_by(_foreign, "  none  "), id="presented-none-padded"),
    pytest.param(_owned_by(_foreign, ""), id="presented-empty"),
    pytest.param(_owned_by(_foreign, "unknown"), id="presented-unknown"),
    # Declared-owner band: self-consistent placeholder and synthetic owners.
    # The placeholder spellings are literal because the spelling is the whole
    # point; they mint no receipt (see ``_owned_by``).
    pytest.param(_owned_by("none", receipt=False), id="owner-and-caller-none"),
    pytest.param(_owned_by("null", receipt=False), id="owner-and-caller-null"),
    # Synthetic band: BOTH prefixes the canonical predicate recognises, one case
    # each. A second ``test-`` case would resolve through the identical
    # ``lower.startswith("test-")`` branch and prove nothing the first does not,
    # so only the two-PREFIX distinction is carried here.
    pytest.param(
        _owned_by(lambda box: box.synthetic("stop-")), id="synthetic-stop-N"
    ),
    pytest.param(
        _owned_by(lambda box: box.synthetic("test-")), id="synthetic-test-N"
    ),
]


class TestFixModePermit:
    """A certified fix-mode run writes without a plan; nothing else does.

    Issue #1589: making the refusal enum-conformant ACTIVATES a gate that never
    fired, including against ``/implement --fix``, which has no plan by design.
    The permit is the deliberate exemption — and every shape in ``DENY_SHAPES``
    is a way of asking for it that must fail.
    """

    @pytest.mark.parametrize("build", DENY_SHAPES)
    def test_permit_unreachable(self, sandbox, build):
        """No degenerate, foreign, unsigned, unreceipted or misidentified run permits."""
        presented = build(sandbox)
        decision, reason = decide(sandbox, write_payload(session_id=presented))
        assert decision == "deny", f"shape obtained the permit; reason={reason!r}"
        assert "Plan gate" in reason

    @pytest.mark.parametrize(
        "pad",
        [
            pytest.param(False, id="exact-owner"),
            pytest.param(True, id="owner-with-whitespace"),
        ],
    )
    def test_certified_fix_mode_sentinel_permits(self, sandbox, pad):
        """GREEN-FIXMODE: signed, owner-bound, receipted, mode=fix -> allow.

        The POSITIVE CONTROL for the whole table above: a guard watched only
        refusing is indistinguishable from one that cannot permit. The padded
        variant pins normalisation parity — the predicates strip, so a
        padded-but-real id must not become a new false refusal.
        """
        mint_sentinel(sandbox, session_id=sandbox.owner, mode="fix")
        presented = f"  {sandbox.owner}  " if pad else sandbox.owner
        decision, reason = decide(sandbox, write_payload(session_id=presented))
        assert decision == "allow", (
            "a certified /implement --fix run has no plan by design; denying "
            "it would activate the gate against a supported workflow"
        )
        assert "fix" in reason.lower() and "Plan gate" in reason

    def test_receipt_is_the_only_difference_from_the_no_receipt_arm(self, sandbox):
        """Attribution control for ``signed-but-no-run-start-receipt``.

        Same ``run_id`` and same sentinel shape, receipt added. Without this the
        no-receipt deny is unattributable — it would read the same if
        ``run_id="runnoreceipt"`` had broken signing.
        """
        mint_sentinel(
            sandbox, session_id=sandbox.owner, run_id="runnoreceipt", receipt=True
        )
        decision, _reason = decide(sandbox, write_payload(session_id=sandbox.owner))
        assert decision == "allow"

    def test_ownerless_sentinel_is_refused_on_identity_not_on_signature(self, sandbox):
        """Attribution control for ``signed-but-no-owner-field``.

        Proves the fixture's MAC genuinely verifies, so that arm's deny comes
        from the absent ownership claim (``OWNER_UNAVAILABLE``, reached before
        the receipt lookup) and not from a broken signature.
        """
        state = mint_ownerless_sentinel(sandbox)
        pipeline_state = _pipeline_state_module()
        assert pipeline_state.verify_state_hmac(state, sandbox.owner, strict=True)


# ---------------------------------------------------------------------------
# Which checks the permit may delegate, and which it must keep (#1589 cycle 1)
# ---------------------------------------------------------------------------


class TestPermitDelegatesAuthority:
    """Evidence for every local pre-check DELETED, and every one KEPT.

    A deleted check widens the permit unless the delegate refuses the same
    shape; a kept check is drift-bait unless the delegate would have AUTHORIZED
    it. Both directions are asserted against the named
    :class:`RunAuthority` member, so a future change that refuses for a
    different reason cannot quietly pass.
    """

    def _verdict(self, state, presented):
        pipeline_state = _pipeline_state_module()
        return pipeline_state, pipeline_state.classify_current_run_authority(
            state, presented
        )

    @pytest.mark.parametrize(
        "build,presented,expected",
        [
            pytest.param(
                lambda box, sid: mint_sentinel(box, session_id=sid, sign=False),
                _SELF,
                "UNSIGNED_LEGACY",
                id="deleted-hmac-presence-check",
            ),
            pytest.param(
                lambda box, sid: mint_sentinel(box, session_id=sid),
                "none",
                "IDENTITY_UNAVAILABLE",
                id="deleted-presented-id-check-none",
            ),
            pytest.param(
                lambda box, sid: mint_sentinel(box, session_id=sid),
                "null",
                "IDENTITY_UNAVAILABLE",
                id="deleted-presented-id-check-null",
            ),
            pytest.param(
                lambda box, _sid: mint_sentinel(
                    box, session_id=box.synthetic("stop-")
                ),
                lambda box: box.synthetic("stop-"),
                "OWNER_UNAVAILABLE",
                id="deleted-declared-owner-check-synthetic",
            ),
            pytest.param(
                # Literal placeholder owner: the spelling IS the subject, so it
                # cannot be made per-case unique — and it mints no receipt, so
                # it addresses no shared ledger path either.
                lambda box, _sid: mint_sentinel(
                    box, session_id="none", receipt=False
                ),
                "none",
                "OWNER_UNAVAILABLE",
                id="deleted-declared-owner-check-placeholder",
            ),
            pytest.param(
                lambda box, _sid: mint_ownerless_sentinel(box),
                _SELF,
                "OWNER_UNAVAILABLE",
                id="deleted-owner-presence-check-FINDING-2",
            ),
        ],
    )
    def test_classifier_alone_refuses_every_deleted_check(
        self, sandbox, build, presented, expected
    ):
        """Each removed pre-check is subsumed by a NAMED classifier refusal."""
        state = build(sandbox, sandbox.owner)
        presented_id = (
            sandbox.owner if presented is _SELF else _resolve(presented, sandbox)
        )
        pipeline_state, verdict = self._verdict(state, presented_id)
        assert verdict.authority is getattr(pipeline_state.RunAuthority, expected)
        assert not verdict.authorized

    def test_classifier_can_authorize_at_all(self, sandbox):
        """Instrument control: six refusals prove nothing if nothing can pass."""
        state = mint_sentinel(sandbox, session_id=sandbox.owner, mode="fix")
        _ps, verdict = self._verdict(state, sandbox.owner)
        assert verdict.authorized, verdict.detail

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"mode": "full"}, id="kept-mode-check"),
            pytest.param({"extra": {"recovered": True}}, id="kept-recovered-check"),
        ],
    )
    def test_kept_pre_checks_refuse_what_the_classifier_authorizes(
        self, sandbox, kwargs
    ):
        """Both kept checks are fix-SCOPE questions authority does not answer.

        The classifier says AUTHORIZED and the hook still denies — which is
        exactly what makes the local check load-bearing rather than redundant.
        The corresponding hook-level denies are ``authorized-but-mode-full``
        and ``recovered-but-genuinely-signed`` in ``DENY_SHAPES``.
        """
        state = mint_sentinel(sandbox, session_id=sandbox.owner, **kwargs)
        _ps, verdict = self._verdict(state, sandbox.owner)
        assert verdict.authorized, (
            "the classifier already refuses this shape, so the local check is "
            f"redundant and should be deleted; verdict={verdict.detail}"
        )


# ---------------------------------------------------------------------------
# CASE ENUM-GUARD — both arms, at the emitter
# ---------------------------------------------------------------------------


_EMITTER_DRIVER = """
import sys
sys.path.insert(0, sys.argv[1])
import plan_gate
try:
    plan_gate._output_decision(sys.argv[2], "enum guard probe")
except ValueError as exc:
    sys.stderr.write("GUARD_REFUSED: " + str(exc))
    sys.exit(3)
sys.exit(0)
"""


def _drive_emitter(sandbox: Sandbox, decision: str) -> subprocess.CompletedProcess:
    """Call the real ``_output_decision`` with *decision*, in isolation."""
    env = dict(os.environ)
    for name in _SCRUBBED_ENV:
        env.pop(name, None)
    env["HOME"] = str(sandbox.home)
    return subprocess.run(
        [sys.executable, "-c", _EMITTER_DRIVER, str(HOOKS_DIR), decision],
        capture_output=True,
        text=True,
        cwd=str(sandbox.repo),
        env=env,
        timeout=SUBPROCESS_TIMEOUT,
    )


class TestEnumGuard:
    """The guard is watched REFUSING and PERMITTING, on different shapes."""

    @pytest.mark.parametrize("decision", sorted(DOCUMENTED_PRETOOLUSE_DECISIONS))
    def test_documented_values_pass_through_unchanged(self, sandbox, decision):
        """PERMITTING arm: every documented value reaches stdout verbatim."""
        proc = _drive_emitter(sandbox, decision)
        assert proc.returncode == 0, proc.stderr
        hso = json.loads(proc.stdout)["hookSpecificOutput"]
        assert hso["permissionDecision"] == decision
        assert hso["permissionDecisionReason"] == "enum guard probe"

    @pytest.mark.parametrize(
        "decision",
        [
            "block",  # the reproducer value
            "Deny",  # case near-miss of a VALID value
            "",  # empty
            "allow,deny",  # composite containing valid values
        ],
    )
    def test_out_of_enum_values_are_refused_at_the_emitter(self, sandbox, decision):
        """REFUSING arm, three shapes BEYOND the reproducer.

        The class removed is "any value outside the documented enum", not the
        single literal ``"block"`` that prompted the fix.
        """
        proc = _drive_emitter(sandbox, decision)
        assert proc.returncode == 3, (
            f"emitter accepted out-of-enum {decision!r}; stdout={proc.stdout!r}"
        )
        assert "GUARD_REFUSED" in proc.stderr
        assert "permissionDecision" not in proc.stdout, (
            "an out-of-enum decision reached stdout before the guard fired"
        )

    def test_no_call_site_in_the_hook_emits_an_out_of_enum_literal(self):
        """Structural arm: read what the hook actually says, via AST.

        A guard at the emitter stops an out-of-enum value at runtime. This
        stops one being WRITTEN — and it covers every present and future
        ``_output_decision`` call site, not the two that prompted #1589.
        """
        tree = ast.parse(HOOK_PATH.read_text(encoding="utf-8"))
        literals = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name != "_output_decision" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                literals.append(first.value)
        assert literals, "no literal _output_decision call sites found"
        offenders = sorted(set(literals) - DOCUMENTED_PRETOOLUSE_DECISIONS)
        assert not offenders, (
            f"plan_gate call sites emit out-of-enum values {offenders}; "
            "docs/HOOKS.md documents allow|deny|ask"
        )
        assert "deny" in literals, "the refusal sites disappeared entirely"


# ---------------------------------------------------------------------------
# CASE CONTROLS — each exemption with a positive AND a negative instance
# ---------------------------------------------------------------------------


class TestControlsUnchanged:
    """The documented fail-open and exemption paths behave exactly as before."""

    def test_invalid_stdin_fails_open(self, sandbox):
        decision, reason = decide(sandbox, None, raw_stdin="}{ not json")
        assert decision == "allow"
        assert "fail-open" in reason

    def test_valid_stdin_same_intent_denies(self, sandbox):
        """Negative control: the SAME write, parseable, takes the other path."""
        decision, _reason = decide(sandbox, write_payload())
        assert decision == "deny"

    def test_doc_file_allowed(self, sandbox):
        decision, reason = decide(sandbox, write_payload("docs/guide.md", BIG_CONTENT))
        assert decision == "allow"
        assert "doc file exemption" in reason

    def test_source_file_same_size_denies(self, sandbox):
        decision, _reason = decide(sandbox, write_payload("src/guide.py", BIG_CONTENT))
        assert decision == "deny"

    def test_simple_edit_allowed(self, sandbox):
        decision, reason = decide(sandbox, write_payload("src/f.py", SMALL_CONTENT))
        assert decision == "allow"
        assert "simple edit" in reason

    def test_complex_edit_same_path_denies(self, sandbox):
        decision, _reason = decide(sandbox, write_payload("src/f.py", BIG_CONTENT))
        assert decision == "deny"

    def test_non_write_tool_allowed(self, sandbox):
        decision, reason = decide(
            sandbox, write_payload(tool_name="Read", content=BIG_CONTENT)
        )
        assert decision == "allow"
        assert "not subject to plan check" in reason

    def test_write_tool_same_input_denies(self, sandbox):
        decision, _reason = decide(
            sandbox, write_payload(tool_name="Write", content=BIG_CONTENT)
        )
        assert decision == "deny"

    def test_skip_plan_check_allowed(self, sandbox):
        decision, reason = decide(
            sandbox, write_payload(), extra_env={"SKIP_PLAN_CHECK": "1"}
        )
        assert decision == "allow"
        assert "SKIP_PLAN_CHECK" in reason

    def test_without_skip_plan_check_denies(self, sandbox):
        decision, _reason = decide(
            sandbox, write_payload(), extra_env={"SKIP_PLAN_CHECK": "0"}
        )
        assert decision == "deny"

    def test_universal_bypass_allowed(self, sandbox):
        (sandbox.repo / ".claude").mkdir(parents=True, exist_ok=True)
        (sandbox.repo / ".claude" / ".bypass").write_text("", encoding="utf-8")
        decision, reason = decide(sandbox, write_payload())
        assert decision == "allow"
        assert "bypass" in reason.lower()

    def test_without_universal_bypass_denies(self, sandbox):
        assert not (sandbox.repo / ".claude" / ".bypass").exists()
        decision, _reason = decide(sandbox, write_payload())
        assert decision == "deny"


# ---------------------------------------------------------------------------
# Telemetry: emitted INTENT only (frozen AMENDMENT 1)
# ---------------------------------------------------------------------------


class TestRefusalTelemetry:
    """The row records what went out, and claims nothing about honour."""

    def test_deny_records_exactly_one_row_naming_the_emitted_value(self, sandbox):
        hso, _proc, _elapsed = run_hook(sandbox, write_payload())
        rows = sandbox.rows()
        assert len(rows) == 1, f"expected one row per refusal, got {rows}"
        row = rows[0]
        assert row["hook_name"] == "plan_gate.py"
        assert row["decision_shape"] == "dict"
        assert row["refused"] is True
        assert row["reason"] == "Plan gate: no plan file found"
        # Read from the SAME run, so the row is compared to the wire rather
        # than to a literal that could drift with it.
        assert row["metadata"]["permission_decision"] == hso["permissionDecision"]
        assert row["metadata"]["permission_decision"] == "deny"

    def test_permit_records_no_refusal_row(self, sandbox):
        """Negative control for the recorder: an allow is not a refusal."""
        mint_sentinel(sandbox, session_id=sandbox.owner, mode="fix")
        hso, _proc, _elapsed = run_hook(
            sandbox, write_payload(session_id=sandbox.owner)
        )
        assert hso["permissionDecision"] == "allow"
        assert sandbox.rows() == []

    def test_hook_never_claims_client_honour(self, sandbox):
        """AMENDMENT 1: honour lives in a joined receipt, never in the hook.

        A PreToolUse hook emits and exits; it cannot observe whether the client
        acted on its decision. Writing ``honoured: true`` here would recreate
        the false-provenance defect #1589 exists to kill.
        """
        run_hook(sandbox, write_payload())
        rows = sandbox.rows()
        assert rows, "no row to inspect"
        honoured = rows[0]["metadata"].get("honoured")
        assert honoured == "unverified", (
            f"metadata claims honoured={honoured!r}; a PreToolUse hook has no "
            "standing to make that claim (frozen AMENDMENT 1)"
        )
