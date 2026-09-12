"""Candidate mutants MC-1..MC-3, child bounding, and denominator independence."""

from __future__ import annotations

import os
import time

import pytest

import _harness as H

ANCHOR_MC1 = "    proc = subprocess.run(argv, **kw)"
ANCHOR_MC2 = "    record = _render(envelope)"
ANCHOR_MC3 = "    digest = _digest(Path(args.target))"

# The MC-1 mutant carries the DEFECT UNDER TEST and nothing else: it reads the
# child's status through a pipeline. shlex.join quotes the interpreter, workroot,
# cache-prefix and target paths, which are DATA rather than shell syntax, so a
# path containing a space cannot turn into an unrelated argument-parsing defect
# and the named RUN_EXIT_MISMATCH stays attributable to the swallowed status.
# The subject keeps those kwargs in `kw`, which the mutant reuses unchanged: the
# ONE swapped line is the whole defect, and substitute() still refuses to apply
# an anchor that matches zero or more than one site.
MC1_PIPELINE = (
    "    import shlex\n" '    proc = subprocess.run(shlex.join(argv) + " | cat", shell=True, **kw)'
)
MC3_GLOB = (
    "    import glob as _glob\n"
    "    _hits = sorted(_glob.glob(str(Path(args.workroot).parent /"
    " 'planted' / '*.json')))\n"
    "    if _hits:\n"
    "        sys.stdout.write(Path(_hits[0]).read_text())\n"
    "        return 0\n"
    "    digest = _digest(Path(args.target))"
)

CHANGED_SUBJECT = "def test_gam():\n    assert True\n\n\ndef test_del():\n    assert True\n"
DECOY_MARKER = "F0DECOY"

# The real-manifest floor and id-uniqueness assertions live ONCE, in
# test_case_manifest.py, over the shipped cases.json. Repeating them here would
# be two homes for one contract.


def _measure(tmp_path, name, script=None):
    # The truth side is the proof suite's own measurement, so an MC-* red is
    # attributable to the candidate rather than to oracle.sh being unwritten.
    workroot = H.make_workroot(tmp_path, (name,))
    target = H.subject_path(workroot, name)
    nonce = H.new_nonce()
    # BOTH sides are real executions of the two independent producers, each
    # checked against the hand-declared table rather than against each other.
    oracle_out = H.run_oracle(workroot, target, nonce).stdout
    assert oracle_out.strip(), "the oracle emitted no record"
    truth = H.parse_record(oracle_out)
    proc = H.run_candidate(workroot, target, nonce, script=script)
    assert proc.stdout.strip(), H._detail(proc)
    # The comparator gets the RAW emitted bytes; parse_receipt is used only to
    # make assertions about their content, never to re-render what is compared.
    cand_rec = H.parse_receipt(proc.stdout)
    orc, cand = H.write_boundary(tmp_path / "rec", oracle_out, proc.stdout)
    return truth, cand_rec, orc, cand, nonce


# ===========================================================================
# CC-0 and MC-1: the swallowed exit
# ===========================================================================

# CC-0, parametrized rather than looped: a shared assertion inside a manual loop
# can be satisfied by one target while masking a failure in another.
# s_pass carries the space-bearing parameter id, so this control also proves the
# candidate's independently written parser keeps it -- checked against the
# hand-declared set, never against the oracle's parser.
#
# s_collect_error is kept, NOT dropped, and its expected result is reconciled
# with the contract: both producers really did select nothing, agreement about
# nothing establishes nothing, so EMPTY_SELECTION is the correct outcome and the
# non-zero collect_exit stays asserted beside it.
#
# CONSOLIDATION: the s_runtime_fail row is removed here. Its obligation -- an
# UNMUTATED candidate agreeing with the oracle on the subject and environment
# MC-1 uses -- is owned by the `unchanged` row of test_direct_receipt_boundary
# below, which runs both real producers on s_runtime_fail and requires exit 0.
CC0_FACTS = ("collect_exit", "run_exit", "selected_count", "subject_digest", "selected")


@pytest.mark.parametrize("name,expect", [("s_pass", None), ("s_collect_error", "EMPTY_SELECTION")])
def test_cc0_unmutated_candidate_agrees_with_the_truth(tmp_path, name, expect):
    truth, cand_rec, orc, cand, nonce = _measure(tmp_path, name)
    assert cand_rec["selected"] == H.selected_of(name), cand_rec["selected"]
    assert truth["selected"] == H.selected_of(name), truth["selected"]
    proc = H.compare(orc, cand, nonce, truth["subject_digest"])
    if expect is not None:
        assert int(truth["collect_exit"]) != 0, "s_collect_error collected cleanly"
    H.expect(proc, expect)

    # CC-0 proper: the control copy is EXECUTED, not merely materialised. Every
    # MC-* mutant runs from tmp_path, so without this a mutant's red could equally
    # mean "a copy of the candidate cannot run from a temp directory". The fresh
    # nonce in its receipt is what shows it really ran rather than replayed.
    workroot = tmp_path / "workroot"
    control = H.control_copy(H.CANDIDATE, tmp_path / "control", H.CAND_WHAT)
    ctrl_nonce = H.new_nonce()
    ctrl = H.run_candidate(workroot, H.subject_path(workroot, name), ctrl_nonce, script=control)
    assert ctrl.stdout.strip(), f"the control copy emitted nothing: {H._detail(ctrl)}"
    ctrl_rec = H.parse_receipt(ctrl.stdout)
    assert ctrl_rec["nonce"] == ctrl_nonce, "the control copy did not run this nonce"
    assert {k: ctrl_rec[k] for k in CC0_FACTS} == {k: cand_rec[k] for k in CC0_FACTS}


# MC-1 is the defect class that actually matters: `cmd | tee`, `|| true`.
# Measured against s_runtime_fail, which COLLECTS CLEANLY and fails at CALL
# time; a collect-time import error never exercises the execution path, so
# s_collect_error cannot stand in for this.
def test_mc1_swallowed_exit_is_caught_as_run_exit_mismatch(tmp_path):
    mutant = H.mutant_of(H.CANDIDATE, tmp_path / "mc1", [(ANCHOR_MC1, MC1_PIPELINE)], H.CAND_WHAT)
    # A PRIVATE workroot whose path CONTAINS A SPACE, so the quoting above is
    # exercised rather than asserted. Node ids stay relative to --rootdir, so the
    # hand-declared expected set is unchanged by it.
    truth, cand_rec, orc, cand, nonce = _measure(tmp_path / "with space", "s_runtime_fail", mutant)
    assert " " in truth["target"], "the space-bearing workroot never reached the run"
    assert int(truth["run_exit"]) == 1, "the truth side did not see the real failure"
    assert int(cand_rec["run_exit"]) == 0, "the pipeline did not hide the failure"
    # The executable under test is the MUTANT, so its bindings are resolved from
    # the mutant's own bytes. Comparing against the original candidate's digest
    # would make every MC-* arm refuse for DEPENDENCY_DIGEST_MISMATCH and leave
    # the named defect unattributable.
    deps = H.expected_dependency_digests(mutant)
    proc = H.compare(orc, cand, nonce, truth["subject_digest"], dep_digests=deps)
    H.expect(proc, "RUN_EXIT_MISMATCH")


SLEEP_S = 4


def _slow_subject(base, name):
    workroot = H.make_workroot(base / name, ("s_pass",))
    target = H.subject_path(workroot, "s_pass")
    started, late = base / name / "started", base / name / "late"
    target.write_text(
        f"import os, pathlib, time\n\n"
        f"pathlib.Path({str(started)!r}).write_text(str(os.getpid()))\n"
        f"time.sleep({SLEEP_S})\n"
        f'pathlib.Path({str(late)!r}).write_text("late")\n\n\n'
        f"def test_x():\n    assert True\n",
        encoding="utf-8",
    )
    return workroot, target, started, late


def _alive(pid):
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


# Child bounding, OBSERVED, with both arms. The wrapper timeout around the
# candidate does not by itself bound what the candidate spawns, so the candidate
# takes --child-timeout and applies it per child.
#
# VACUITY, and this arm previously had it: a fast non-zero exit, no stdout and
# no late marker are ALL satisfied by a child that never started. So the subject
# writes a startup marker with its PID as its FIRST action and that marker is
# asserted present; the bounded-out result is asserted by its NAMED token rather
# than a bare non-zero exit, which a startup crash also produces; and the
# generous-deadline row is the control showing the fixture can reach its late
# marker at all, which is what makes the marker's absence informative.
#
# SCOPE, stated rather than overclaimed: the recorded PID is checked gone, so
# DIRECT-child bounding and reaping are established. Cleanup of GRANDchildren is
# NOT established here -- it is carried as an UNMEASURED case in the manifest,
# and no process supervisor, reaper or descendant tracking is invented for it.
@pytest.mark.parametrize("label,bound,times_out", [("bounded", 2, True), ("generous", 60, False)])
def test_candidate_bounds_its_children_and_reaps_them(tmp_path, label, bound, times_out):
    workroot, target, started, late = _slow_subject(tmp_path, label)
    nonce = H.new_nonce()
    began = time.monotonic()
    proc = H.run_candidate(workroot, target, nonce, child_timeout=bound, timeout=180)
    elapsed = time.monotonic() - began

    assert started.exists(), f"[{label}] the child never started: {H._detail(proc)}"
    child_pid = int(started.read_text())

    if not times_out:
        assert late.exists(), "no late marker even when generous; absence proves nothing"
        assert proc.returncode == 0 and proc.stdout.strip(), proc.stderr
        return

    assert elapsed < SLEEP_S, f"ran {elapsed:.1f}s; --child-timeout {bound} was ignored"
    assert proc.returncode == H.CHILD_TIMEOUT_EXIT, f"not the contracted exit: {proc.stderr!r}"
    # A NAMED outcome, because a bare non-zero exit is also what a startup crash
    # produces and the two must stay distinguishable.
    assert H.CHILD_TIMEOUT_TOKEN in proc.stderr, f"no named outcome: {proc.stderr!r}"
    assert not proc.stdout.strip(), f"a partial record was emitted: {proc.stdout!r}"

    time.sleep(SLEEP_S + 1)
    assert not _alive(child_pid), f"the bounded-out child {child_pid} is still alive"
    assert not late.exists(), "the child completed; the timeout bounded the wait only"

    # End to end: no record means the comparison cannot be established, and a
    # named reason says so rather than the run passing for want of evidence. The
    # comparator is handed the bounded-out run's ACTUAL stdout bytes, verbatim,
    # not a manufactured empty candidate file.
    synthetic = H.synthetic_record(workroot, "s_pass", nonce)
    orc, cand = H.write_boundary(tmp_path / "rec", synthetic, proc.stdout)
    H.expect(H.compare(orc, cand, nonce), "CANDIDATE_EMPTY")


# ===========================================================================
# MC-2: reporting a hardcoded prior receipt
# ===========================================================================


def _hardcode(rec, freeze_nonce):
    frozen = {k: int(rec[k]) for k in ("collect_exit", "run_exit", "selected_count")}
    frozen |= {"subject_digest": rec["subject_digest"], "selected": list(rec["selected"])}
    if freeze_nonce:
        frozen["nonce"] = rec["nonce"]
    return f'    envelope["observation"].update({frozen!r})\n' f"    record = _render(envelope)"


MC2_ARMS = [("changed-subject-live-nonce", True, False, "SELECTED_MISMATCH")]
MC2_ARMS += [("same-subject-replayed-nonce", False, True, "STALE_RECORD")]


# Two shapes that fail in DIFFERENT directions, so neither check covers for the
# other. Arm one: the record is frozen but the NONCE is still stamped live --
# the realistic "report last known good" shape, which defeats freshness
# signalling entirely and must be caught on CONTENT. Arm two: same subject,
# nothing changed, the record replayed wholesale including its nonce -- content
# comparison alone cannot see it, and only the nonce refuses it.
@pytest.mark.parametrize("label,change_subject,freeze_nonce,reason_id", MC2_ARMS)
def test_mc2_a_frozen_prior_record_is_refused(
    tmp_path, label, change_subject, freeze_nonce, reason_id
):
    workroot = H.make_workroot(tmp_path, ("s_pass",))
    target = H.subject_path(workroot, "s_pass")
    # A REAL prior candidate execution, which is what a replayed record is.
    prior = H.parse_receipt(H.run_candidate(workroot, target, H.new_nonce()).stdout)
    if change_subject:
        target.write_text(CHANGED_SUBJECT, encoding="utf-8")

    subs = [(ANCHOR_MC2, _hardcode(prior, freeze_nonce))]
    mutant = H.mutant_of(H.CANDIDATE, tmp_path / label, subs, H.CAND_WHAT)
    nonce = H.new_nonce()
    assert nonce != prior["nonce"]
    truth = H.parse_record(H.run_oracle(workroot, target, nonce).stdout)
    moved = truth["selected"] != prior["selected"]
    assert moved == change_subject, f"{label}: the subject edit was inert; it isolates nothing"

    proc = H.run_candidate(workroot, target, nonce, script=mutant)
    assert proc.stdout.strip(), f"mutant emitted nothing: {proc.stderr!r}"
    cand_rec = H.parse_receipt(proc.stdout)
    assert cand_rec["nonce"] == (prior["nonce"] if freeze_nonce else nonce)
    assert cand_rec["selected"] == prior["selected"]

    orc, cand = H.write_boundary(tmp_path / "rec2", truth, proc.stdout)
    deps = H.expected_dependency_digests(mutant)
    H.expect(H.compare(orc, cand, nonce, truth["subject_digest"], dep_digests=deps), reason_id)


# MC-3: a candidate that finds the oracle's record and echoes it agrees
# perfectly and has measured nothing. The decoy carries an impossible node id,
# so "did it copy?" is answerable directly rather than inferred from agreement,
# and the unmutated control must NOT pick the decoy up.
def test_mc3_candidate_copying_a_planted_record_is_detected(tmp_path):
    workroot = H.make_workroot(tmp_path, ("s_pass",))
    target = H.subject_path(workroot, "s_pass")
    nonce = H.new_nonce()
    truth = H.parse_record(H.run_oracle(workroot, target, nonce).stdout)

    planted = workroot.parent / "planted"
    planted.mkdir()
    decoy = {**truth, "selected": [f"{DECOY_MARKER}::x", f"{DECOY_MARKER}::y"]}
    (planted / "prior.receipt.json").write_text(H.render_receipt(decoy), encoding="utf-8")

    control = H.control_copy(H.CANDIDATE, tmp_path / "control", H.CAND_WHAT)
    ctrl_out = H.run_candidate(workroot, target, nonce, script=control).stdout
    assert ctrl_out.strip(), "the control candidate emitted nothing"
    assert DECOY_MARKER not in ctrl_out, "the UNMUTATED candidate took the decoy"

    mutant = H.mutant_of(H.CANDIDATE, tmp_path / "mc3", [(ANCHOR_MC3, MC3_GLOB)], H.CAND_WHAT)
    mut_out = H.run_candidate(workroot, target, nonce, script=mutant).stdout
    assert DECOY_MARKER in mut_out, "the MC-3 mutant did not copy the planted record"
    # The mutant emits the PLANTED bytes verbatim, which carry the ORIGINAL
    # candidate's bindings, so the default expectation is the correct one here.
    orc, cand = H.write_boundary(tmp_path / "rec3", truth, mut_out)
    H.expect(H.compare(orc, cand, nonce, truth["subject_digest"]), "SELECTED_MISMATCH")


# ===========================================================================
# The direct receipt boundary: the comparator's REAL two inputs
# ===========================================================================

# The primitive oracle emits its own flat f0-oracle-1 record; the candidate,
# standing in for R0, emits the canonical receipt JSON. This arm runs both
# producers separately, saves the candidate's EXACT stdout unchanged, and hands
# the two files to the same digest-bound comparator. No reparse, no re-render,
# no translator: if the comparator cannot read a real receipt, this goes red.
#
# The subject collects cleanly and FAILS AT CALL TIME, and carries the
# space-bearing parameter id, so both survive the boundary together.
#
# The "unchanged" row returns comparison exit 0 while the observed subject exit
# is 1. That is NOT a product pass and must never be read as one: it means the
# two independent observations AGREED, and the non-zero subject exit is the
# adverse evidence they agreed about. Without this row the mismatch rows below
# prove nothing, because a permanently broken boundary also refuses everything.
#
# The id mutation keeps selected_count UNCHANGED, which is what proves the
# comparator compares the node-id SET rather than a count.
CASE_KEY = '{\n  "case":'
BOGUS_KEY = '{\n  "bogus_field": "x",\n  "case":'
BOUNDARY_ARMS = [
    ("unchanged", None, None, None),
    ("raw-run-exit-flipped", '"run_exit": 1', '"run_exit": 0', "RUN_EXIT_MISMATCH"),
    ("one-node-id-same-count", "::test_zebra", "::test_zulu", "SELECTED_MISMATCH"),
    # An unknown TOP-LEVEL envelope key is still refused, while unknown keys
    # INSIDE observation are legitimate R0 metadata and must travel unchanged.
    ("unknown-top-level-key", CASE_KEY, BOGUS_KEY, "UNKNOWN_FIELD"),
]


@pytest.mark.parametrize(
    "label,anchor,replacement,reason_id", BOUNDARY_ARMS, ids=[a[0] for a in BOUNDARY_ARMS]
)
def test_direct_receipt_boundary(tmp_path, label, anchor, replacement, reason_id):
    workroot = H.make_workroot(tmp_path, ("s_runtime_fail",))
    target = H.subject_path(workroot, "s_runtime_fail")
    nonce = H.new_nonce()

    emitted = H.run_candidate(workroot, target, nonce).stdout
    assert emitted.strip(), "the candidate emitted no receipt"
    oracle_out = H.run_oracle(workroot, target, nonce).stdout
    assert oracle_out.strip(), "the oracle emitted no record"

    # substitute() refuses zero or multiple matches, so a mutation that silently
    # changed nothing cannot masquerade as a detected defect.
    payload = emitted if anchor is None else H.substitute(emitted, anchor, replacement)
    orc, cand = H.write_boundary(tmp_path / "boundary", oracle_out, payload)
    assert cand.read_text(encoding="utf-8") == payload, "the receipt was rewritten"

    receipt = H.parse_receipt(payload)
    envelope = receipt["_envelope"]
    assert any(" " in sid for sid in receipt["selected"]), "the space-bearing id was lost"
    assert int(receipt["selected_count"]) == 2, "the count moved; the arm is not isolated"
    assert envelope["schema"] == H.RECEIPT_SCHEMA, envelope["schema"]

    # The fixture must not certify its own bindings: `case`, `tool_version` and
    # `dependency_digests` are checked against the KNOWN BYTES the harness
    # resolved independently, not against what the receipt asserts about itself.
    assert envelope["case"] == H.CASE_ID
    assert envelope["tool_version"] == H.TOOL_VERSION
    assert envelope["dependency_digests"] == H.expected_dependency_digests()
    # decision is SYNTHETIC fixture data. F0 comparison success certifies only
    # the frozen compared facts -- never this decision, and never the full R0
    # metadata; R0's own frozen acceptance validates the rest.
    assert envelope["decision"] in ("PASS", "FAIL")
    for meta in ("command", "cwd", "timeout_s", "stdout_digest", "carrier_id"):
        assert meta in envelope["observation"], f"R0 metadata {meta} absent"

    H.expect(H.compare(orc, cand, nonce, expect_digest=H.digest(target)), reason_id)


# ===========================================================================
# Denominator independence -- sources that fail in DIFFERENT directions
# ===========================================================================


def e1_declared(doc) -> set[str]:
    return {case["id"] for case in doc["cases"]}


def e2_executed(record_dir, nonce) -> set[str]:
    # Keyed on the run nonce, so a case cannot enter the denominator by editing
    # a declaration -- only by producing a record in THIS run.
    found = set()
    for path in sorted(record_dir.glob("*.rec")):
        rec = H.parse_record(path.read_text(encoding="utf-8"))
        if rec.get("nonce") == nonce and rec.get("case_id"):
            found.add(rec["case_id"])
    return found


def e3_on_disk(subjects_dir) -> set[str]:
    # A file in no declaration that never runs is invisible to BOTH E1 and E2.
    return {path.stem for path in sorted(subjects_dir.glob("case_*.py"))}


def _seed(tmp_path):
    subjects, records = tmp_path / "subjects", tmp_path / "records"
    subjects.mkdir()
    records.mkdir()
    nonce = H.new_nonce()
    for case_id in ("case_ok", "case_a_undeclared", "case_b_dead", "case_c_orphan"):
        (subjects / f"{case_id}.py").write_text("def test_x():\n    pass\n", "utf-8")
    declared = {"cases": [{"id": "case_ok"}, {"id": "case_b_dead"}]}
    # E2's POSITIVE records come from ACTUAL PRIVATE EXECUTIONS of those two case
    # subjects under the frozen profile, in this tmp_path and nowhere else. Typed-in
    # records would have made E2 a nonce filter wearing an enumerator's label.
    for case_id in ("case_ok", "case_a_undeclared"):
        proc = H.run_profile(subjects, subjects / f"{case_id}.py", collect_only=False)
        assert proc.returncode == 0, f"{case_id} did not execute: {H._detail(proc)}"
        text = f"nonce={nonce}\ncase_id={case_id}\nrun_exit={proc.returncode}\n"
        (records / f"{case_id}.rec").write_text(text, "utf-8")
    return declared, records, subjects, nonce


SHAPES = [("A", "case_a_undeclared", "e2", "e1"), ("B", "case_b_dead", "e1", "e2")]
SHAPES += [("C", "case_c_orphan", "e3", "e1|e2")]


# Each shape is invisible to at least one enumerator. One source can only
# confirm itself; that is how a missing case survives forever.
@pytest.mark.parametrize("shape,case_id,seen_by,blind_to", SHAPES)
def test_denominator_shapes_need_all_three_enumerators(tmp_path, shape, case_id, seen_by, blind_to):
    declared, records, subjects, nonce = _seed(tmp_path)
    got = {"e1": e1_declared(declared), "e2": e2_executed(records, nonce)}
    got["e3"] = e3_on_disk(subjects)
    blind = set().union(*(got[k] for k in blind_to.split("|")))
    assert case_id in got[seen_by], f"shape {shape} is not recovered by {seen_by}"
    assert case_id not in blind, f"shape {shape} is not actually blind to {blind_to}"
    assert got[seen_by] - blind == {case_id}, f"shape {shape}: {got[seen_by] - blind!r}"


# The binding property of E2: if it ignored the nonce, last run's records would
# pad this run's denominator.
#
# CONSOLIDATION: the `fabricated-declaration` shape is removed. Its obligation --
# a case that is DECLARED but never executed must not enter E2, or E2 would be
# E1 with extra steps -- is owned by shape B above, where case_b_dead is in E1,
# is asserted NOT recovered by E2, and is the only member of that difference.
def test_e2_counts_only_records_produced_by_this_run(tmp_path):
    _, records, _, nonce = _seed(tmp_path)
    # Deliberately hand-written: a record from a previous run is exactly an
    # artifact this run did not produce.
    (records / "case_stale.rec").write_text(
        "nonce=00000000deadbeef\ncase_id=case_stale\n", encoding="utf-8"
    )
    executed = e2_executed(records, nonce)
    assert "case_stale" not in executed, f"E2 counted a previous run: {executed!r}"
    assert executed, "E2 recovered nothing at all, so the exclusion is vacuous"
