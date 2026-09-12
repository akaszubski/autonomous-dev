"""The comparator arms and the verdict/exit contract: one arm per REASON_ID."""

# The exit contract (0 agreed / 1 one REFUSED line / 2 argparse only) is enforced
# once in H.expect and H.reason_of, which every arm here inherits, and is
# asserted directly by the argparse arm below.

from __future__ import annotations

import json
import re

import pytest

import _harness as H

OK_LINE = re.compile(r"^OK subject_exit=(-?\d+) collect_exit=(-?\d+) selected=(\d+)$")

# Deleted vocabulary. Its reappearance would mean F0 had started emitting a
# product decision instead of a comparison outcome.
DELETED_VOCABULARY = ("AGREE", "DISAGREE", "UNUSABLE", "BROKEN")

# The hand-declared truth for the fixture subject. A row that reorders or drops
# an id names the ids it changes, rather than deriving them from either parser.
PASS_IDS = H.selected_of("s_pass")


# ---------------------------------------------------------------------------
# Builders. Each returns (oracle_file, candidate_file, nonce, expect_digest).
# The known-good record is an EXPLICITLY SYNTHETIC fixture, built by _good from
# the hand-declared SUBJECTS table -- it is not a measurement and is never
# labelled one. That is deliberate: it makes these arms go red on trustcheck.py's
# absence ALONE, so they stay interpretable while oracle.sh is still being
# written. The arms that must be REAL EXECUTIONS run the producers for real:
# STALE_SUBJECT/MT-5 below, and CO-0, CC-0 and MC-1..3 in the other files.
# ---------------------------------------------------------------------------


def _good(tmp_path, name="s_pass"):
    # EXPLICITLY SYNTHETIC: built from the hand-declared SUBJECTS table, never
    # from a measurement wearing a measurement's label; the header above lists
    # the arms that are real executions instead.
    workroot = H.make_workroot(tmp_path, (name,))
    nonce = H.new_nonce()
    rec = H.synthetic_record(workroot, name, nonce)
    orc, cand = H.write_boundary(tmp_path / "rec", rec, H.render_receipt(rec))
    return orc, cand, nonce, rec["subject_digest"], rec


def _file(side, content):
    def build(tmp_path):
        orc, cand, nonce, dig, _ = _good(tmp_path)
        target = orc if side == "oracle" else cand
        if content is None:
            target.unlink()
        else:
            target.write_text(content, encoding="utf-8")
        return orc, cand, nonce, dig

    return build


def _empty_selection(tmp_path):
    """Two verifiers that both selected NOTHING agree perfectly and establish nothing."""
    orc, cand, nonce, dig, rec = _good(tmp_path, "s_empty")
    assert int(rec["selected_count"]) == 0, "the s_empty fixture is not empty"
    return orc, cand, nonce, dig


def _stale_subject(tmp_path):
    # The subject's BYTES change while path, node ids, collect_exit and run_exit
    # stay identical, and the old record is re-stamped with the CURRENT nonce.
    # Every freshness signal says fresh; only an independently supplied subject
    # digest can refuse it. Both measurements are actual oracle runs, so the
    # "behaviourally inert" precondition is observed rather than asserted from a
    # table.
    workroot = H.make_workroot(tmp_path, ("s_pass",))
    target = H.subject_path(workroot, "s_pass")
    old_digest = H.digest(target)
    rec = H.parse_record(H.run_oracle(workroot, target, H.new_nonce()).stdout)
    assert rec["selected"] == H.selected_of("s_pass")

    target.write_text(target.read_text("utf-8") + "\n# inert edit\n", encoding="utf-8")
    new_digest = H.digest(target)
    assert new_digest != old_digest, "the subject bytes did not actually change"

    fresh = H.parse_record(H.run_oracle(workroot, target, H.new_nonce()).stdout)
    same = ("collect_exit", "run_exit", "selected")
    assert [fresh[k] for k in same] == [rec[k] for k in same], "the edit changed behaviour"

    current = H.new_nonce()
    restamped = {**rec, "nonce": current, "subject_digest": old_digest}
    orc, cand = H.write_boundary(tmp_path / "rec", restamped, H.render_receipt(restamped))
    return orc, cand, current, new_digest


# ---------------------------------------------------------------------------
# One arm per REASON_ID. `anchor` is set where a comparator mutant (MT-*)
# removes the very check the arm depends on; that mutant must then PERMIT the
# same input. Structurally identical arms are rows here, not functions.
# ---------------------------------------------------------------------------


# ONE builder for every synthesized receipt arm: an observation override, a
# dropped field, or a forged envelope binding. A None VALUE in `top` DELETES that
# envelope key, which is how the absent-binding arm differs from the forged ones.
# Native JSON types are kept rather than flattened and re-inflated, and the
# mutation is asserted to have actually changed the bytes -- an edit that changed
# nothing would leave the row refusing (or agreeing) for some other reason.
def _envelope(top=None, obs=None, drop=None):
    def build(tmp_path):
        orc, cand, nonce, dig, rec = _good(tmp_path)
        payload = {k: v for k, v in rec.items() if k != drop}
        doc = json.loads(H.render_receipt(payload, top, obs))
        for key, value in (top or {}).items():
            if value is None:
                doc.pop(key, None)
        text = json.dumps(doc, sort_keys=True, indent=2) + "\n"
        assert text != H.render_receipt(rec), "the mutation changed nothing"
        cand.write_text(text, encoding="utf-8")
        return orc, cand, nonce, dig

    return build


# Two one-line spellings of the same builder, so a row that changes ONE envelope
# key or ONE observation value fits on ONE line and stays readable as a row.
def _top(**keys):
    return _envelope(top=keys)


def _obs(**keys):
    return _envelope(obs=keys)


FORGED = {"case_manifest": "0" * 64, "verifier": "0" * 64}
META = {"command": "pytest ...", "cwd": "/nowhere"}
BAD_RECEIPT = "not a receipt at all\n"
ARMS = [
    # The three envelope bindings. Without these the comparator could accept a
    # receipt that claims any case, any tool version and any dependency set:
    # a forged dependency_digests block would pass, and the receipt would be
    # vouching for its own provenance. Each is refused against truth the CALLER
    # supplied, in the established --expect-* pattern.
    ("CASE_MISMATCH", _top(case="some-other-case"), "CASE_MISMATCH", None),
    ("TOOL_VERSION", _top(tool_version="candidate-verifier-99"), "TOOL_VERSION_MISMATCH", None),
    ("DEPENDENCY_DIGEST", _top(dependency_digests=FORGED), "DEPENDENCY_DIGEST_MISMATCH", None),
    # A binding that is ABSENT is not the same defect as one that is forged.
    ("MISSING_FIELD_tool_version", _top(tool_version=None), "MISSING_FIELD", None),
    # An unknown TOP-LEVEL envelope key is refused; see the observation-metadata
    # row below for the key that must NOT be.
    ("UNKNOWN_FIELD", _top(bogus_field="1"), "UNKNOWN_FIELD", None),
    # Presence of neighbours is not substitution: a MISSING compared observation
    # field still fails even when extra legitimate metadata sits beside it.
    ("MISSING_FIELD_with_neighbours", _envelope(obs=META, drop="run_exit"), "MISSING_FIELD", None),
    # MT-1: without the required-field check a truncated record reads as agreement.
    ("MISSING_FIELD", _envelope(drop="run_exit"), "MISSING_FIELD", H.ANCHOR_MT1_FIELDS),
    # MT-2: without the nonce check a replayed record is indistinguishable from a run.
    ("STALE_RECORD", _obs(nonce="deadbeefdeadbeef"), "STALE_RECORD", H.ANCHOR_MT2_NONCE),
    # s_pass truly exits 0 on both, so 1 is a real disagreement; the builder
    # refuses an edit that changed nothing, so neither row can go inert.
    ("COLLECT_EXIT_MISMATCH", _obs(collect_exit=1), "COLLECT_EXIT_MISMATCH", None),
    ("RUN_EXIT_MISMATCH", _obs(run_exit=1), "RUN_EXIT_MISMATCH", None),
    # Reordering keeps the COUNT identical, so a count-only comparator is blind
    # to it. MT-3 removes exactly that id comparison.
    ("reordered-ids", _obs(selected=PASS_IDS[::-1]), "SELECTED_MISMATCH", H.ANCHOR_MT3_IDS),
    # A DROPPED id with a consistently reduced count is the omitted-denominator
    # shape this suite exists to catch, stated end to end.
    ("dropped-id", _obs(selected=PASS_IDS[:1], selected_count=1), "SELECTED_MISMATCH", None),
    ("PYTHON_MISMATCH", _obs(python="/usr/bin/python3"), "PYTHON_MISMATCH", None),
    ("TARGET_MISMATCH", _obs(target="/nowhere/test_other.py"), "TARGET_MISMATCH", None),
    ("ORACLE_ABSENT", _file("oracle", None), "ORACLE_ABSENT", None),
    ("CANDIDATE_ABSENT", _file("candidate", None), "CANDIDATE_ABSENT", None),
    # An unreadable record must never be read as agreement: a producer that
    # crashed leaves an empty file behind. This is the fail-open shape.
    ("ORACLE_EMPTY", _file("oracle", ""), "ORACLE_EMPTY", None),
    ("CANDIDATE_EMPTY", _file("candidate", ""), "CANDIDATE_EMPTY", None),
    ("ORACLE_MALFORMED", _file("oracle", "not a record at all\n"), "ORACLE_MALFORMED", None),
    # The candidate side is the CANONICAL RECEIPT, so malformed means bad JSON
    # or JSON that is not a receipt object. Both rows are direct evidence that
    # the frozen comparator really consumes a receipt rather than a flat record.
    ("malformed-not-json", _file("candidate", BAD_RECEIPT), "CANDIDATE_MALFORMED", None),
    ("malformed-json-not-object", _file("candidate", "[1, 2, 3]\n"), "CANDIDATE_MALFORMED", None),
    # MT-4: the check that stops "we agreed about nothing" counting as agreement.
    ("EMPTY_SELECTION", _empty_selection, "EMPTY_SELECTION", H.ANCHOR_MT4_NONEMPTY),
    # MT-5: without the digest, a current nonce over a stale measurement looks fresh.
    ("STALE_SUBJECT", _stale_subject, "STALE_SUBJECT", H.ANCHOR_MT5_DIGEST),
]

# A present-but-NULL value is NOT the same defect as an absent key, and the two
# reach different fail-open routes: a null run_exit is skipped by a comparison
# that treats None as "nothing to compare" while the required-field check sees
# the key and passes, and a null selected reaches list(None) before any named
# refusal is reached. One directly attributed row per COMPARED field, built by
# the same _envelope builder (no second schema or parser), including selected
# and nonce. CT-0 (the same fixture, unmutated, PERMITTED) and the MT-1
# required-field mutant remain the opposing controls for the whole group.
ARMS += [
    (f"NULL_VALUE_{field}", _envelope(obs={field: None}), "MISSING_FIELD", None)
    for field in H.OBSERVATION_FIELDS
]


# VACUITY: CT-0 below proves the same fixture AGREES when unmutated, so a
# refusal here is attributable to the one thing each row changes. Where an
# anchor is given, both halves are required: the mutant exiting 0 alone would be
# satisfied by a comparator that permits everything, and the real one refusing
# alone by a comparator that refuses everything.
@pytest.mark.parametrize("label,build,reason_id,anchor", ARMS, ids=[a[0] for a in ARMS])
def test_defect_is_refused_by_name_and_its_check_is_load_bearing(
    tmp_path, label, build, reason_id, anchor
):
    orc, cand, nonce, dig = build(tmp_path)
    H.expect(H.compare(orc, cand, nonce, dig), reason_id)
    if anchor is None:
        return
    mutant = H.mutant_of(H.TRUSTCHECK, tmp_path / label, [(anchor, "")], H.TC_WHAT)
    permitted = H.compare(orc, cand, nonce, dig, script=mutant)
    # Still refusing means the refusal above is attributed to the wrong check.
    assert permitted.returncode == 0, f"{label}: still refusing: {H._detail(permitted)}"


# ===========================================================================
# CT-0 and the exit contract
# ===========================================================================


# CT-0. Without a known-good input every refusal above could equally mean
# "trustcheck refuses everything". The control-copy row is the second half: the
# MT-* mutants run from tmp_path, so if a plain COPY of trustcheck.py cannot run
# from there, every MT-* result is a false attribution.
#
# CONSOLIDATION: the synthesized "with-R0-observation-metadata" row is removed.
# Its obligation -- legitimate extra R0 observation metadata travels unchanged
# and is NOT refused, or the frozen comparator could never read a real R0
# receipt -- is owned by the `unchanged` row of test_direct_receipt_boundary,
# which permits a REAL emitted receipt after asserting that command, cwd,
# timeout_s, stdout_digest and carrier_id are all present in its observation.
@pytest.mark.parametrize("copied", [False, True], ids=["installed", "control-copy"])
def test_ct0_identical_true_records_agree(tmp_path, copied):
    orc, cand, nonce, dig, rec = _good(tmp_path)
    script = H.control_copy(H.TRUSTCHECK, tmp_path / "control", H.TC_WHAT) if copied else None
    proc = H.compare(orc, cand, nonce, dig, script=script)
    H.expect(proc)
    match = OK_LINE.match(proc.stdout.strip())
    assert match, f"the OK line does not match the contract: {proc.stdout!r}"
    assert int(match.group(3)) == int(rec["selected_count"])


# The single-line "REFUSED: <REASON_ID> <explanation>" shape is enforced inside
# H.reason_of, so EVERY refusal arm above inherits it rather than one arm
# asserting it once for itself.


# Exit 2 stays reserved. If a designed refusal ever exits 2 the caller cannot
# tell a comparison outcome from a broken invocation.
def test_argparse_failure_is_exit_two_not_a_refusal():
    proc = H.trustcheck(["compare"])
    assert proc.returncode == 2, f"a missing argument exited {proc.returncode}, not 2"
    assert "REFUSED:" not in proc.stdout, f"channels collapsed: {proc.stdout!r}"


# ONE argparse CLI. A second entry point is a second surface to keep honest
# forever, and the rung budget counts CLI surfaces.
@pytest.mark.parametrize("subcommand", ["compare", "budget"])
def test_one_cli_two_subcommands(subcommand):
    proc = H.trustcheck([subcommand, "--help"])
    assert proc.returncode == 0, f"`{subcommand} --help` exited {proc.returncode}"
    assert proc.stdout.strip(), f"`{subcommand} --help` printed nothing"


# F0 grants no trust state and is not a promotion event.
# VACUITY: a run that did nothing would also write nothing, so the comparison is
# asserted to have actually happened (exit 0 + OK line) first.
def test_f0_emits_no_product_decision_and_writes_no_product_state(tmp_path):
    orc, cand, nonce, dig, _ = _good(tmp_path)
    before = H.snapshot(H.ROOT / ".claude")
    proc = H.compare(orc, cand, nonce, dig)
    H.expect(proc)
    assert H.snapshot(H.ROOT / ".claude") == before, "F0 wrote product state"

    source = H.TRUSTCHECK.read_text(encoding="utf-8")
    for word in DELETED_VOCABULARY:
        assert not re.search(rf"\b{word}\b", proc.stdout), f"{word!r} on stdout"
        assert not re.search(rf"\b{word}\b", source), f"{word!r} in {H.TC_WHAT}"
