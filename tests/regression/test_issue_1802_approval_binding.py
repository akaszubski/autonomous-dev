#!/usr/bin/env python3
"""Alignment approval is fail-closed AT THE CANONICAL API (Issue #1802, OPEN).

WHAT THESE TESTS PIN, AND WHAT THEY DO NOT.

They pin that the ``escalate -> user_approved`` upgrade and approval-metadata
laundering are fail-closed at the canonical library surface —
``record_alignment_verdict``, ``evaluate_and_record`` and ``map_verdict``.

They do NOT certify acceptance of #1802, which remains OPEN:

* The same-principal direct-writer / re-signing ceiling is still OPEN (#1807).
  A caller that bypasses this choke point and writes the verdict artifact or
  re-signs pipeline state itself is outside every arm below, and runs as the
  same principal, so nothing here constrains it.
* The genuine human-approval positive arm is UNMEASURED — see the closing
  note in this docstring.
* These arms pin a PARTIAL fix. Read no arm below, and no "closed" or
  "refuses" phrasing in it, as a system-wide property.

This module docstring is the ONE home for the shared rationale; the tests
below carry only what is specific to their own arm.

The defect: ``evaluate_and_record()`` accepted a bare caller boolean
``user_approved=True`` and upgraded a deterministic ESCALATE to
``verdict=user_approved`` / ``alignment_passed=true``, synthesizing
``approval.source = "ask_user_question"`` even though no round trip occurred.
The approval sub-object was manufactured by the library from the very
assertion it was supposed to evidence. Observed live on 2026-09-25 (run
01e99c0efb9202ae) and 2026-09-27 (run 5b7478ef3af7718e).

Why no receipt object fixes it, and why every arm below refuses:

1. Anything a coordinator can hand this library, the coordinator can also
   manufacture. It runs as the SAME principal, so it can reach any signing key
   this process can reach. A signed, bound, single-use record relocates the
   self-attestation; it does not remove it. Arm (d) pins exactly that.
2. There is no response SHAPE that proves a human either — Claude Code hooks
   permit ``AskUserQuestion`` ``updatedInput.answers`` to be supplied
   programmatically.

So the upgrade refuses at this API until an independently verifiable receipt
channel exists (#1807). Refusing an unknown is fail-closed; labelling it
honestly and then permitting it is not.

Arm (h) covers a SECOND, distinct laundering route (issue comment 5849895757):
the metadata sanitization was scoped to approval-relevant verdicts, so an
AUTO_PASS or BLOCK skipped it and carried whatever the caller attached into
the artifact, the audit row and signed state. That one went THROUGH the choke
point and the choke point let it past — it is not the same-principal
direct-writer ceiling, which remains open and separately tracked.

Arm naming: (a) the reported forgery, (b) untouched control, (c) autonomy,
(d) caller receipts of any shape, (e) unreadable PROJECT.md, (f) positive
permit controls, (g) legacy/public-surface paths, (h) forged metadata on
non-approval verdicts.

The genuine human-approval POSITIVE arm is UNMEASURED here by construction:
there is nothing in this environment that could produce one. It is absent
rather than simulated, and no test below should be read as standing in for it.

GitHub Issue: #1802
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from alignment_classifier import (  # noqa: E402
    ALLOWED_VERDICTS,
    APPROVAL_UNAVAILABLE,
    AlignmentVerdict,
    ProjectDoc,
    Stage0Outcome,
    Stage0Result,
    Verdict,
    evaluate_and_record,
    map_verdict,
    record_alignment_verdict,
)

_PROJECT_MD = """# Project Context — Issue 1802

## GOALS

**Mission**: Prove the alignment approval path cannot be self-approved.

## SCOPE

**IN Scope:**
- Alignment gate regression tests

**OUT of Scope:**
- SaaS billing dashboards and hosted per-seat pricing

## CONSTRAINTS

**Philosophy**: "Less is more".

## ARCHITECTURE (Solution-on-a-Page)

Deterministic layers run before probabilistic ones.
"""

_FEATURE = "Add a hosted SaaS billing dashboard with per-seat pricing"
_IN_SCOPE = "Alignment gate regression tests"
_FORGED_APPROVAL = {
    "source": "ask_user_question",
    "approved_at": "2026-09-27T00:00:00+00:00",
    "human_verified": True,
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A tmp repo root with a readable PROJECT.md. Never the live sentinel."""
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "PROJECT.md").write_text(_PROJECT_MD, encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def _interactive_by_default(monkeypatch):
    """Default every arm to INTERACTIVE.

    Otherwise a stray env var makes arms refuse for the autonomy reason and
    the approval-channel refusal goes untested — green while proving nothing.
    """
    monkeypatch.delenv("AUTONOMOUS_DEV_NONINTERACTIVE", raising=False)


def _escalated() -> AlignmentVerdict:
    """An ESCALATE verdict carrying a concrete Stage 0 reason."""
    return AlignmentVerdict(
        verdict=Verdict.ESCALATE,
        feature_text=_FEATURE,
        classification="out_of_scope",
        reasoning="Out of scope per PROJECT.md.",
        stage0_outcome=Stage0Outcome.ESCALATE,
        stage0_reason="OUT-of-scope overlap: SaaS billing dashboards",
        issue_number="1802",
        timestamp="2026-09-27T00:00:00+00:00",
    )


def _state_file(repo: Path) -> Path:
    """A minimal signed-state target so persistence is exercised, not skipped."""
    path = repo / "state.json"
    path.write_text(json.dumps({
        "session_start": "2026-09-27T00:00:00", "mode": "full",
        "run_id": "forge-1802", "explicitly_invoked": True,
    }))
    return path


def _artifact(repo: Path) -> dict:
    return json.loads((repo / ".claude" / "alignment_verdict.json").read_text())


def _audit_rows(repo: Path) -> list:
    path = repo / ".claude" / "logs" / "alignment_verdicts.jsonl"
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _assert_refused(final: AlignmentVerdict, repo: Path, reason: str) -> None:
    """Shared assertions for every refusal arm.

    ``ask_user_question`` must appear NOWHERE: that synthesized source string
    was the bug's signature, so its total absence from verdict, artifact and
    audit trail is what shows the path is closed, not merely relabelled.
    """
    assert final.verdict is Verdict.ESCALATE
    assert final.verdict.value not in ALLOWED_VERDICTS
    assert final.approval is None
    assert final.user_approved_refused == reason

    payload = final.to_dict()
    assert payload["verdict"] == "escalate"
    assert "approval" not in payload

    for row in _audit_rows(repo):
        assert "approval" not in row
        assert "ask_user_question" not in json.dumps(row)


# ---------------------------------------------------------------------------
# (a) The reported forgery
# ---------------------------------------------------------------------------


def test_a_bare_user_approved_boolean_is_refused(repo: Path) -> None:
    """The exact pre-fix reproducer: it returned user_approved / passed=true."""
    final = record_alignment_verdict(_escalated(), repo_root=repo, user_approved=True)
    _assert_refused(final, repo, APPROVAL_UNAVAILABLE)
    assert final.attempted_user_approval is True


def test_a_bare_boolean_refused_through_the_entry_point(repo: Path) -> None:
    """Same forgery, end to end through the entry point the snippet calls."""
    out = evaluate_and_record(
        _FEATURE, None,
        project_md_path=repo / ".claude" / "PROJECT.md",
        repo_root=repo, user_approved=True,
    )
    assert out["verdict"] == "escalate"
    assert out["alignment_passed"] is False
    assert "approval" not in out
    assert out["user_approved_refused"] == APPROVAL_UNAVAILABLE
    assert _artifact(repo)["verdict"] == "escalate"


def test_a_refusal_names_the_issue_and_the_remaining_options(repo: Path) -> None:
    """A block with no route forward gets routed around, so name the routes."""
    final = record_alignment_verdict(_escalated(), repo_root=repo, user_approved=True)
    reasoning = final.reasoning.lower()
    assert "1802" in reasoning
    assert "narrow the change" in reasoning
    assert "update project.md scope" in reasoning
    assert "stop" in reasoning


# ---------------------------------------------------------------------------
# (b) No flag — the untouched control
# ---------------------------------------------------------------------------


def test_b_escalate_without_any_approval_attempt_is_unchanged(repo: Path) -> None:
    """Control: refusal fields appear because approval was ATTEMPTED, not always."""
    out = evaluate_and_record(
        _FEATURE, None,
        project_md_path=repo / ".claude" / "PROJECT.md", repo_root=repo,
    )
    assert out["verdict"] == "escalate"
    assert out["alignment_passed"] is False
    assert "approval" not in out
    assert "user_approved_refused" not in out
    assert "attempted_user_approval" not in out


# ---------------------------------------------------------------------------
# (c) Autonomous context — refuses, and keeps its OWN distinct reason
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("signal", ["env_var", "drain_marker"])
def test_c_autonomy_refuses_with_its_own_reason(
    repo: Path, monkeypatch, signal: str
) -> None:
    """Both autonomy signals refuse, and neither collapses into #1802's reason.

    "Nobody was there to ask" is not "we cannot verify who answered"; an
    auditor needs to tell them apart even though refusal is over-determined.
    """
    if signal == "env_var":
        monkeypatch.setenv("AUTONOMOUS_DEV_NONINTERACTIVE", "1")
    else:
        (repo / ".claude" / "local").mkdir(parents=True, exist_ok=True)
        (repo / ".claude" / "local" / "drain_pending.json").write_text(json.dumps(
            {"issues": [1802], "cluster_tag": "t", "started_at": 0, "session_id": "s"}
        ))
    final = record_alignment_verdict(_escalated(), repo_root=repo, user_approved=True)
    _assert_refused(final, repo, "autonomous_context")


# ---------------------------------------------------------------------------
# (d) No caller-supplied receipt, of ANY shape, is accepted
# ---------------------------------------------------------------------------

_HONEST_MINTED = {
    "schema_version": 1, "record_id": "3f7a9c21b8e04d5f", "run_id": "b68c6011e7e68a72",
    "feature_digest": "a" * 64, "project_md_digest": "b" * 64,
    "escalation_digest": "c" * 64, "issued_at": "2026-09-27T00:00:00+00:00",
    "source": "coordinator_asserted_response", "response": "approve",
    "provenance": "UNMEASURED", "human_verified": False, "hmac": "d" * 64,
}
_CLAIMS_HUMAN = {
    "source": "ask_user_question", "human_verified": True,
    "provenance": "human_confirmed", "response": "approve",
}


@pytest.mark.parametrize("record,flag", [
    pytest.param(_HONEST_MINTED, True, id="honest_minted_bound_record"),
    pytest.param(_CLAIMS_HUMAN, True, id="record_claiming_a_human"),
    pytest.param({"response": "approve"}, False, id="record_without_the_flag"),
])
def test_d_no_caller_receipt_is_accepted(repo: Path, record: dict, flag: bool) -> None:
    """Every receipt shape refuses, including the one an earlier revision ACCEPTED.

    ``honest_minted_bound_record`` is that shape: bound, single-use,
    HMAC-signed, honestly labelled ``provenance: UNMEASURED``. It still
    refuses, because honest labelling of an unknown is not permission.
    ``record_claiming_a_human`` is the opposite label and fares no better —
    the library does not adjudicate the label, it declines caller provenance
    entirely. Subsumes wrong-run/stale/replayed/tampered: binding correctness
    is irrelevant when no binding can be trusted.
    """
    final = record_alignment_verdict(
        _escalated(), repo_root=repo, user_approved=flag, approval_record=record
    )
    _assert_refused(final, repo, APPROVAL_UNAVAILABLE)


def test_d_refused_attempt_is_appended_not_rewritten(repo: Path) -> None:
    """Acceptance 5: attempts accumulate; audit history is immutable."""
    record_alignment_verdict(_escalated(), repo_root=repo, user_approved=True)
    after_first = _audit_rows(repo)
    record_alignment_verdict(
        _escalated(), repo_root=repo, approval_record={"response": "approve"}
    )
    after_second = _audit_rows(repo)

    assert after_second[: len(after_first)] == after_first
    assert len(after_second) == len(after_first) + 1
    assert all(row["attempted_user_approval"] is True for row in after_second)
    assert all(row["user_approved_refused"] == APPROVAL_UNAVAILABLE for row in after_second)


# ---------------------------------------------------------------------------
# (e) PROJECT.md missing or unreadable — fail closed
# ---------------------------------------------------------------------------


def test_e_missing_project_md_blocks_and_never_auto_passes(tmp_path: Path) -> None:
    """No alignment source of truth, no pass. Always blocked correctly."""
    out = evaluate_and_record(_IN_SCOPE, None, repo_root=tmp_path)
    assert out["verdict"] == "block"
    assert out["alignment_passed"] is False
    assert out["project_md_found"] is False


@pytest.fixture
def unreadable_repo(tmp_path: Path, monkeypatch):
    """A repo whose PROJECT.md exists but raises PermissionError when READ.

    Injected rather than chmod-000: ``os.geteuid`` does not exist on Windows,
    so a real-permission arm would raise AttributeError there and skipping it
    would report green while proving nothing. The injection raises the same
    exception from the same call site (``Path.read_text`` inside
    ``parse_project_md``, after ``path.exists()`` is already True). Scoped to
    PROJECT.md so a failure cannot be an artifact of breaking unrelated I/O.
    """
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / "PROJECT.md").write_text(_PROJECT_MD, encoding="utf-8")
    real_read_text = Path.read_text

    def _deny_project_md(self, *args, **kwargs):
        if self.name == "PROJECT.md":
            raise PermissionError(13, "Permission denied", str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _deny_project_md)
    return tmp_path


@pytest.mark.parametrize("flag", [False, True], ids=["no_flag", "with_approval_flag"])
def test_e_unreadable_project_md_blocks_instead_of_raising(
    unreadable_repo: Path, flag: bool
) -> None:
    """Pre-fix this escaped as an uncaught PermissionError, so the gate crashed.

    A caller that swallowed the exception proceeded ungated. Different failure
    shape from the missing-file case, which always blocked. The flag cannot
    rescue an unreadable gate input either.
    """
    out = evaluate_and_record(
        _IN_SCOPE, None, repo_root=unreadable_repo, user_approved=flag
    )
    assert out["verdict"] == "block"
    assert out["alignment_passed"] is False
    assert "approval" not in out
    assert "PermissionError" in out["stage0_reason"]


# ---------------------------------------------------------------------------
# (f) POSITIVE controls — legitimate work must not be over-refused
# ---------------------------------------------------------------------------


def test_f_verified_citation_auto_pass_still_permits(repo: Path) -> None:
    """The permit arm. Without it every refusal arm passes against a gate that
    refuses everything."""
    out = evaluate_and_record(
        _IN_SCOPE,
        {"classification": "in_scope", "cited_clause": _IN_SCOPE,
         "confidence": "high", "reasoning": "Matches an IN-scope bullet verbatim."},
        project_md_path=repo / ".claude" / "PROJECT.md", repo_root=repo,
    )
    assert out["verdict"] == "auto_pass"
    assert out["alignment_passed"] is True
    assert out["citation_verified"] is True
    assert "approval" not in out
    assert "user_approved_refused" not in out


def test_f_auto_pass_survives_an_autonomous_run(repo: Path, monkeypatch) -> None:
    """A citation-verified pass is untouched by the autonomy gate."""
    monkeypatch.setenv("AUTONOMOUS_DEV_NONINTERACTIVE", "1")
    final = record_alignment_verdict(
        AlignmentVerdict(verdict=Verdict.AUTO_PASS, feature_text=_IN_SCOPE,
                         cited_clause=_IN_SCOPE, citation_verified=True),
        repo_root=repo,
    )
    assert final.verdict is Verdict.AUTO_PASS
    assert final.verdict.value in ALLOWED_VERDICTS
    assert final.user_approved_refused == ""


# ---------------------------------------------------------------------------
# (g) Legacy and public-surface paths cannot upgrade either
# ---------------------------------------------------------------------------


def test_g_map_verdict_can_never_manufacture_user_approved(repo: Path) -> None:
    """ATTACK-3 control on the PUBLIC pure function, swept not enumerated.

    ``map_verdict`` has no leading underscore, so an external caller could
    once import it, pass the flag and get a USER_APPROVED that never reached
    the choke point's refusal. #1802 removed the parameter.
    """
    doc = ProjectDoc(raw=_PROJECT_MD)
    produced = {
        map_verdict(Stage0Result(outcome=outcome), classification, clause, doc)
        for outcome in Stage0Outcome
        for classification in (None, "in_scope", "out_of_scope", "architecture_delta", "bogus")
        for clause in (None, _IN_SCOPE, "nonexistent clause")
    }
    assert Verdict.USER_APPROVED not in produced
    assert produced <= {Verdict.BLOCK, Verdict.ESCALATE, Verdict.AUTO_PASS}
    # Positive control: the sweep reaches a real pass, so "no USER_APPROVED"
    # is not an artifact of nothing passing at all.
    assert Verdict.AUTO_PASS in produced


def test_g_pre_upgraded_user_approved_verdict_is_downgraded(repo: Path) -> None:
    """A USER_APPROVED arriving from ANY source is downgraded at the choke point."""
    final = record_alignment_verdict(
        AlignmentVerdict(verdict=Verdict.USER_APPROVED, feature_text=_FEATURE),
        repo_root=repo,
    )
    _assert_refused(final, repo, APPROVAL_UNAVAILABLE)


def test_g_block_is_never_upgraded(repo: Path) -> None:
    """INV-7 preserved — a BLOCK is not approvable at any price."""
    final = record_alignment_verdict(
        AlignmentVerdict(verdict=Verdict.BLOCK, feature_text=_FEATURE,
                         stage0_outcome=Stage0Outcome.BLOCK,
                         stage0_reason="injection markers detected"),
        repo_root=repo, user_approved=True, approval_record={"response": "approve"},
    )
    assert final.verdict is Verdict.BLOCK
    assert final.approval is None


def test_g_no_input_combination_can_produce_user_approved(repo: Path) -> None:
    """Sweep the whole caller-controlled input space, removing the category.

    Enumerating members is how a guard ends up scoped to the instance that
    prompted it.
    """
    produced = set()
    for flag in (False, True):
        for record in (None, {}, {"response": "approve"}, {"source": "ask_user_question"}):
            for start in (Verdict.ESCALATE, Verdict.USER_APPROVED):
                final = record_alignment_verdict(
                    AlignmentVerdict(verdict=start, feature_text=_FEATURE),
                    repo_root=repo, user_approved=flag, approval_record=record,
                )
                produced.add(final.verdict)

    assert produced == {Verdict.ESCALATE}
    assert Verdict.USER_APPROVED not in produced
    assert not any(row.get("approval") for row in _audit_rows(repo))


# ---------------------------------------------------------------------------
# (h) Forged metadata on NON-approval verdicts (issue comment 5849895757)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind,preset,forge,expected", [
    # Exhaustive over (inbound marker) x (actual tampering) for AUTO_PASS,
    # plus BLOCK to pin that the scope is non-approval verdicts generally.
    pytest.param(Verdict.AUTO_PASS, None, False, False, id="auto_pass__unset__clean__False"),
    pytest.param(Verdict.AUTO_PASS, None, True, True, id="auto_pass__unset__forged__True"),
    pytest.param(Verdict.AUTO_PASS, True, False, False, id="auto_pass__preset_True__clean__False"),
    pytest.param(Verdict.AUTO_PASS, True, True, True, id="auto_pass__preset_True__forged__True"),
    pytest.param(Verdict.AUTO_PASS, False, False, False, id="auto_pass__preset_False__clean__False"),
    pytest.param(Verdict.AUTO_PASS, False, True, True, id="auto_pass__preset_False__forged__True"),
    pytest.param(Verdict.BLOCK, None, True, True, id="block__unset__forged__True"),
])
def test_h_forged_metadata_cannot_survive_persistence(
    repo: Path, kind: Verdict, preset, forge: bool, expected: bool
) -> None:
    """Forged approval metadata never persists, and the marker is DERIVED.

    Two defects in one table, because they share every assertion:

    * Comment 5849895757 — sanitization was scoped to approval-relevant
      verdicts, so AUTO_PASS/BLOCK skipped it and laundered whatever the
      caller attached into artifact, audit row and signed state.
    * Comment 5850061581 — ``approval_metadata_stripped``, added to record
      that stripping, was itself forgeable by the same route.

    Cells are chosen to discriminate, not to enumerate:
    ``preset_True__clean__False`` fails against a pass-through implementation
    (the actual 5850061581 defect); ``preset_False__forged__True`` is the
    suppression direction; ``block__unset__forged`` pins that the fix is
    scoped to non-approval verdicts generally, not to AUTO_PASS.

    STRIP, do not downgrade: the verdict was computed deterministically by
    ``map_verdict`` from Stage 0 plus citation verification, so forged
    metadata does not invalidate it and downgrading would over-refuse honest
    work. The metadata is what lies, so the metadata is what is removed.
    """
    fields = dict(verdict=kind, feature_text=_FEATURE, citation_verified=True)
    if preset is not None:
        fields["approval_metadata_stripped"] = preset
    if forge:
        fields["approval"] = dict(_FORGED_APPROVAL)

    final = record_alignment_verdict(
        AlignmentVerdict(**fields), state_path=_state_file(repo),
        session_id="forge-1802", repo_root=repo,
    )

    payload, artifact, rows = final.to_dict(), _artifact(repo), _audit_rows(repo)

    # The verdict itself is never collateral damage of metadata handling.
    assert final.verdict is kind, "stripped, not downgraded"
    assert final.approval is None
    for blob in (payload, artifact, *rows):
        assert "approval" not in blob
        assert "ask_user_question" not in json.dumps(blob)
    assert "ask_user_question" not in (repo / "state.json").read_text()

    assert final.approval_metadata_stripped is expected
    if expected:
        for blob in (payload, artifact, rows[-1]):
            assert blob["approval_metadata_stripped"] is True
    else:
        # Absence, not merely falsiness: a clean payload must stay
        # byte-identical to the pre-#1802 schema for existing readers.
        for blob in (payload, artifact, rows[-1]):
            assert "approval_metadata_stripped" not in blob


def test_h_forged_refusal_metadata_cannot_survive_on_auto_pass(repo: Path) -> None:
    """The same laundering applied to the refusal fields, not just ``approval``.

    A caller could stamp an approval attempt that never happened onto a clean
    AUTO_PASS and pollute the audit trail.
    """
    verdict = AlignmentVerdict(
        verdict=Verdict.AUTO_PASS, feature_text=_FEATURE, citation_verified=True,
        user_approved_refused="autonomous_context", attempted_user_approval=True,
    )
    final = record_alignment_verdict(
        verdict, state_path=_state_file(repo), session_id="forge-1802", repo_root=repo
    )

    assert final.verdict is Verdict.AUTO_PASS
    assert final.user_approved_refused == ""
    assert final.attempted_user_approval is False
    payload = final.to_dict()
    assert "user_approved_refused" not in payload
    assert "attempted_user_approval" not in payload


# ---------------------------------------------------------------------------
# Consumer coherence: historical user_approved states must still be readable
# ---------------------------------------------------------------------------


def test_historical_user_approved_verdict_remains_an_allowed_verdict() -> None:
    """New ones cannot be produced, but pre-fix signed states still carry one,
    so the consumer must not retro-block them."""
    assert "user_approved" in ALLOWED_VERDICTS
    assert "auto_pass" in ALLOWED_VERDICTS


def test_historical_artifact_with_an_approval_object_still_deserializes() -> None:
    """Pre-fix artifacts carrying an ``approval`` sub-object still load."""
    historical = AlignmentVerdict(
        verdict=Verdict.USER_APPROVED, feature_text=_FEATURE,
        approval={"source": "ask_user_question", "approved_at": "2026-09-25T00:00:00+00:00"},
    )
    payload = historical.to_dict()
    assert payload["verdict"] == "user_approved"
    assert payload["approval"]["source"] == "ask_user_question"
    assert "attempted_user_approval" not in payload
