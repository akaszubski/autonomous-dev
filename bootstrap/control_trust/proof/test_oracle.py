"""PV-1 (FIRST and BLOCKING), the measurement profile, and the oracle arms."""

from __future__ import annotations

import os
import re
import shutil

import pytest

import _harness as H

PLUGIN_CONTAMINANT = "Running teardown with pytest sessionfinish..."
STRIPPED_ID = "::test_stripped_rootdir"

SEEDED_CONFTEST = "import pytest\n\n\n@pytest.fixture\ndef seeded_value():\n    return 7\n"
SEEDED_TEST = "def test_uses_seeded(seeded_value):\n    assert seeded_value == 7\n"


def _seeded_fixture_tree(base):
    # Never the product conftest: invoking real legacy autouse fixtures to prove
    # they were disabled is the #1720 hazard and is forbidden here.
    sub = base / "workroot" / "seeded"
    sub.mkdir(parents=True)
    (sub / "conftest.py").write_text(SEEDED_CONFTEST, encoding="utf-8")
    (sub / "test_s.py").write_text(SEEDED_TEST, encoding="utf-8")
    return base / "workroot", sub / "test_s.py"


def _oracle_record(workroot, target, nonce, script=None):
    proc = H.run_oracle(workroot, target, nonce, script=script)
    assert proc.stdout.strip(), f"oracle emitted nothing ({proc.returncode}): {proc.stderr!r}"
    return H.parse_record(proc.stdout)


def _control_vs_mutant(tmp_path, root, target, subs):
    control = H.control_copy(H.ORACLE, tmp_path / "control", H.ORACLE_WHAT)
    mutant = H.mutant_of(H.ORACLE, tmp_path / "mutant", subs, H.ORACLE_WHAT)
    true_rec = _oracle_record(root, target, H.new_nonce(), control)
    return true_rec, _oracle_record(root, target, H.new_nonce(), mutant)


# ===========================================================================
# PV-1 -- the selection primitive and the blocking preconditions
# ===========================================================================


# The expected set is SUBJECTS[...]["selected"]: a third, hand-declared source,
# neither the oracle's output nor the candidate's. Checking the two
# implementations against each other is exactly what let both encode the same
# false "a node id has no spaces" assumption and agree on a selection of size 1
# where the truth is 2.
#
# VACUITY: an empty recovery would satisfy "no bad ids", so equality with a
# non-empty declared set is asserted; the incomplete result the old parser
# produced was itself NON-EMPTY, so no emptiness check can stand in for this;
# and the literal sed program is executed rather than re-expressed in Python,
# which would be self-comparison.
def test_pv1_selection_recovers_the_exact_hand_declared_set(tmp_path):
    workroot = H.make_workroot(tmp_path, ("s_pass",))
    target = H.subject_path(workroot, "s_pass")
    assert target.is_relative_to(workroot), "the subject must live UNDER --rootdir"
    proc = H.run_profile(workroot, target, collect_only=True)
    assert proc.stdout.strip(), f"collection emitted nothing: {proc.stderr!r}"

    expected = H.selected_of("s_pass")
    assert len(expected) == 2 and any(" " in sid for sid in expected), expected
    emitted = sorted(ln for ln in proc.stdout.splitlines() if "::" in ln)
    assert emitted == expected, f"pytest emitted {emitted!r}, not declared {expected!r}"
    recovered = sorted(H.sed_recover(proc.stdout))
    assert recovered == expected, f"recovered {recovered!r}, not {expected!r}"


NON_NODE_LINES = [("summary", "2 tests collected in 0.07s")]
NON_NODE_LINES += [("plugin-chatter", PLUGIN_CONTAMINANT), ("rootdir-stripped", STRIPPED_ID)]
NON_NODE_LINES += [("error-prefix", "ERROR collecting s_pass/test_s.py::x")]


# Widening the parser to admit spaces AFTER `::` must not widen it to admit the
# summary line, plugin chatter, an id with no file, or a prefixed diagnostic --
# each of those would inflate selected_count silently.
@pytest.mark.parametrize("label,line", NON_NODE_LINES)
def test_pv1_selection_rejects_non_node_id_lines(label, line):
    assert H.sed_recover(line + "\n") == [], f"the parser accepted the {label} line"


# A DIFFERENT-SHAPE negative control for PV-1: same flags, subject moved OUT of
# the workroot. If this does not reproduce stripped ids, PV-1 above is passing
# for a reason unrelated to placement and proves nothing.
def test_pv1_sibling_subject_strips_filenames(tmp_path):
    workroot = H.make_workroot(tmp_path, ("s_pass",))
    sibling = tmp_path / "sibling" / "s_pass"
    sibling.mkdir(parents=True)
    target = sibling / "test_s.py"
    target.write_text(H.SUBJECTS["s_pass"]["src"], encoding="utf-8")
    assert not target.is_relative_to(workroot), "the control must be OUTSIDE workroot"

    proc = H.run_profile(workroot, target, collect_only=True)
    emitted = [ln for ln in proc.stdout.splitlines() if "::" in ln]
    assert emitted, f"no node-id lines; the control did not run: {proc.stderr!r}"
    assert all(ln.startswith("::") for ln in emitted), f"expected stripped: {emitted!r}"
    assert H.sed_recover(proc.stdout) == [], "stripped ids matched; must fail CLOSED"


# ===========================================================================
# The measurement profile: interpreter, bytecode, no-write
# ===========================================================================


PROFILE_ROWS = [("3.11.14", "8.4.2", True), ("3.14.3", "8.4.2", False)]
PROFILE_ROWS += [("3.11.14", "9.1.1", False), ("3.12.0", "9.1.1", False)]


# The pinned-profile check must be able to REFUSE, or asserting it passes here
# proves nothing. A version probe is not proof of running the approved profile.
@pytest.mark.parametrize("py,pytest_v,ok", PROFILE_ROWS)
def test_profile_check_refuses_the_wrong_environment(py, pytest_v, ok):
    assert (H.profile_violations(py, pytest_v) == []) is ok


# A setup-only venv path such as /tmp/<fixed-name>/venv is a local artifact, not
# the contract: it will not exist in a clean checkout or in CI, so a suite
# pinned to one passes only where it was authored.
#
# The alt root is produced by COPYING a venv rather than deriving one, because
# MEASURED: a venv derived from a venv inherits the BASE prefix's
# site-packages, which does not carry pytest. For a non-venv interpreter the
# derived-venv path is correct instead, so both are covered without a skip.
#
# VACUITY: the alt interpreter is asserted DIFFERENT from the executing one and
# asserted to appear in the record, so "the same record" cannot be produced by
# silently reusing the original interpreter.
def test_interpreter_is_relocatable_and_version_checked(tmp_path, monkeypatch):
    py_version, pytest_version = H.interpreter_facts()
    assert H.profile_violations(py_version, pytest_version) == [], (py_version, pytest_version)
    assert H.PYTHON.exists() and H.PYTHON.is_absolute(), H.PYTHON
    # Regression guard for a MEASURED defect: a venv's bin/python imports pytest
    # while its realpath does not, so dereferencing silently leaves the pinned
    # environment. The invocation path is what carries virtualenv semantics. The
    # /tmp scan beside it is the separate no-local-artifact obligation: both are
    # source properties of the same files, so they share ONE read.
    sources = sorted(H.PROOF_DIR.rglob("*.py"))
    assert sources, "no proof sources found; this scan would be vacuous"
    for path in sources:
        text = path.read_text(encoding="utf-8")
        # Built like the runtime's APPEND_SHELL constant: a contiguous literal
        # would match THIS line and report its own file as the defect.
        assert ("sys.executable)" + ".resolve()") not in text, f"{path.name} derefs PYTHON"
        assert not re.findall(r"""["']/tmp/""", text), f"{path.name} hardcodes /tmp"

    home = H.PYTHON.parent.parent
    alt_root = tmp_path / "altroot"
    if (home / "pyvenv.cfg").exists():
        shutil.copytree(home, alt_root, symlinks=True)
    else:
        # -I and a private cwd: the fallback must not import anything the
        # invocation directory or the ambient environment supplies.
        argv = [H.PYTHON, "-B", "-I", "-m", "venv", "--without-pip", "--system-site-packages"]
        made = H.run([*argv, alt_root], cwd=tmp_path)
        assert made.returncode == 0, f"venv creation failed: {made.stderr!r}"
    alt = alt_root / "bin" / H.PYTHON.name
    assert alt.exists() and alt != H.PYTHON, "the alt root is not distinct"

    monkeypatch.setattr(H, "PYTHON", alt)
    H.interpreter_facts.cache_clear()
    try:
        workroot = H.make_workroot(tmp_path, ("s_pass",))
        rec = _oracle_record(workroot, H.subject_path(workroot, "s_pass"), H.new_nonce())
    finally:
        monkeypatch.undo()
        H.interpreter_facts.cache_clear()

    assert rec["python"] == str(alt), f"the record names {rec['python']!r}, not the alt"
    assert rec["selected"] == H.selected_of("s_pass")
    assert (rec["collect_exit"], rec["run_exit"]) == ("0", "0")


# A measuring-apparatus hazard. MEASURED, and the weaker earlier claim that -B
# cures it is REFUTED: -B is NO-WRITE, not stale-read immunity.
#
# Both arms are handed the SAME directory, the SAME already-changed subject and
# the SAME pre-existing stale __pycache__; only the cache prefix differs, and
# the stale cache is never deleted before either instrument sees it. Running the
# clean arm in a separate cache-free directory would only prove it did not WRITE
# bytecode, which is a different property and would not defeat this hazard.
#
# The mtime is FORCED with os.utime rather than raced for inside one second, so
# the hazard is constructed deterministically instead of flaking.
#
# The stale stimulus is compiled EXPLICITLY, for the private subject ALONE, by a
# helper run under -B -I, so no arm ever enables process-wide bytecode writing
# and no .pyc can land beside installed pytest, its dependencies or the stdlib.
# VERIFIED DEPENDENCY DETAIL: the pinned pytest's assertion rewriter reads its
# OWN version-tagged cache name and header, not py_compile's default, and it
# reads that cache even under -B. An ordinary CPython .pyc would therefore never
# be read and this arm would be vacuous, so the tail and the cache directory are
# resolved FROM THE EXECUTING pytest at runtime -- never a hardcoded local path.
SEED_PYC = (
    "import sys\n"
    "from pathlib import Path\n"
    "from _pytest.assertion.rewrite import PYC_TAIL, get_cache_dir, _write_pyc_fp\n"
    "fn = Path(sys.argv[1])\n"
    "cache = get_cache_dir(fn)\n"
    "cache.mkdir(parents=True, exist_ok=True)\n"
    "code = compile(fn.read_bytes(), str(fn), 'exec', dont_inherit=True)\n"
    "with open(cache / (fn.name[:-3] + PYC_TAIL), 'wb') as fp:\n"
    "    _write_pyc_fp(fp, fn.stat(), code)\n"
)


def test_stale_bytecode_is_read_under_B_and_defeated_only_by_a_cache_prefix(tmp_path):
    old, new = "def test_old():\n    assert True\n", "def test_new():\n    assert True\n"
    assert len(new) == len(old), "equal byte length keeps the stale .pyc valid"

    root = tmp_path / "wr"
    sub = root / "s"
    sub.mkdir(parents=True)
    target = sub / "test_c.py"
    target.write_text(old, encoding="utf-8")

    seeded = H.run([H.PYTHON, "-B", "-I", "-c", SEED_PYC, target], cwd=root)
    assert seeded.returncode == 0, f"the pyc seed failed: {H._detail(seeded)}"
    cache = sub / "__pycache__"
    assert list(cache.glob("*.pyc")), "no bytecode was written; both arms are vacuous"

    st = target.stat()
    target.write_text(new, encoding="utf-8")
    os.utime(target, (st.st_atime, st.st_mtime))

    # A change here is NEWS: re-measure before trusting any in-place rewrite.
    # This is also what proves the seeded cache is really READ: if pytest ignored
    # it, the current source would collect test_new here and this arm goes red.
    stale = H.sed_recover(H.run_profile(root, target, pycache_prefix=None).stdout)
    assert stale == ["s/test_c.py::test_old"], f"-B alone reported {stale!r}"
    assert list(cache.glob("*.pyc")), "the stale cache vanished before the clean arm"

    prefix = tmp_path / "pycache"  # freshly allocated, private, ephemeral scratch
    fresh = H.sed_recover(H.run_profile(root, target, pycache_prefix=prefix).stdout)
    assert fresh == ["s/test_c.py::test_new"], f"clean profile reported {fresh!r}"
    assert list(cache.glob("*.pyc")), "the clean arm destroyed the fixture cache"


# OBSERVED, not inferred from flag text: snapshot the tree, run the apparatus,
# compare. THREE distinct claims, kept distinct:
#   1. before == after: this invocation changed nothing that was already there;
#   2. no cache APPEARED. A __pycache__ present BEFORE is preserved evidence of
#      some earlier run under a different profile and is NOT attributable to this
#      invocation; deleting it to make a number green would destroy that
#      evidence, so it is excluded by set difference rather than removed;
#   3. the injected-write counter-control. An equal before/after is equally
#      satisfied by a snapshot that cannot see any write at all, so the SAME
#      snapshot() runs against a PRIVATE representative tree under tmp_path -- a
#      proof-shaped directory with a held __pycache__ beside a source file -- and
#      a real file is created THERE. Nothing is written to, or removed from, the
#      live source, .claude or any other shared path: a finally block does not
#      make a live-source probe safe against a crash (the #1720 hazard).
CACHE_NAMES = ("__pycache__", ".ruff_cache", ".pytest_cache")


def test_no_writes_to_the_source_tree_or_product_ledger(tmp_path):
    watched = (H.CT_DIR, H.ROOT / ".claude")
    before = H.snapshot(*watched)
    assert before, "the snapshot is empty; this comparison would be vacuous"

    workroot = H.make_workroot(tmp_path, ("s_pass",))
    rec = _oracle_record(workroot, H.subject_path(workroot, "s_pass"), H.new_nonce())
    assert rec["selected"] == H.selected_of("s_pass"), "the run did nothing"

    after = H.snapshot(*watched)
    assert after == before, f"F0 wrote: {sorted(set(after) ^ set(before))!r}"
    appeared = [p for p in after if p not in before and H.Path(p).name in CACHE_NAMES]
    assert not appeared, f"this invocation created a cache: {appeared!r}"

    private = tmp_path / "representative" / "control_trust" / "proof"
    (private / "__pycache__").mkdir(parents=True)
    (private / "test_s.py").write_text("X = 1\n", encoding="utf-8")
    clean = H.snapshot(private.parent)
    assert clean, "the private tree is empty, so the counter-control is vacuous"
    (private / f"probe-{H.new_nonce()}").write_text("w", encoding="utf-8")
    assert H.snapshot(private.parent) != clean, "snapshot() cannot see a real write"


# CONSOLIDATION: the removed H.measured()/H.record_for obligation -- a REAL
# measurement of EVERY declared subject checked against the hand-declared table
# -- is owned by test_oracle_record_matches_measured_subject_behaviour below,
# which runs the real oracle over all four subjects in both the installed and the
# control-copy arm and asserts the selection AND the exit pair. A second
# all-subject execution path here would be a third way to run pytest and format a
# record, which is exactly what was consolidated away.


# ===========================================================================
# The oracle record, and CO-0
# ===========================================================================


# Parametrizing over (subject x installed/control-copy) merges the record-shape
# arm with CO-0: the control-copy rows ARE CO-0, and without them every MO-* red
# could equally mean "a copy of oracle.sh cannot run from a temp directory".
#
# Collection failure and execution failure are DISTINCT arms: s_collect_error
# dies at import, s_runtime_fail collects cleanly and fails at CALL time. A
# collect-only import error never exercises the execution path, so one can never
# stand in for the other.
@pytest.mark.parametrize("copied", [False, True], ids=["installed", "CO-0-copy"])
@pytest.mark.parametrize("name", H.SUBJECT_NAMES)
def test_oracle_record_matches_measured_subject_behaviour(tmp_path, name, copied):
    workroot = H.make_workroot(tmp_path, (name,))
    script = H.control_copy(H.ORACLE, tmp_path / "control", H.ORACLE_WHAT) if copied else None
    nonce = H.new_nonce()
    rec = _oracle_record(workroot, H.subject_path(workroot, name), nonce, script)

    assert rec.get("schema") == H.SCHEMA
    for field in H.SCALAR_FIELDS:
        assert field in rec, f"record for {name} is missing required field {field}"
    assert rec["nonce"] == nonce, "the oracle must stamp the harness-supplied nonce"

    exp = H.SUBJECTS[name]
    if exp["collect"] is None:
        # s_empty: NON-ZERO, never the literal 5.
        assert int(rec["collect_exit"]) != 0 and int(rec["run_exit"]) != 0
    else:
        assert int(rec["collect_exit"]) == exp["collect"]
        assert int(rec["run_exit"]) == exp["run"]

    assert rec["selected"] == H.selected_of(name), f"oracle: {rec['selected']!r}"
    assert int(rec["selected_count"]) == len(rec["selected"]), "count vs selected= lines"
    assert rec["selected"] == sorted(rec["selected"]), "selected= lines are not sorted"


# ===========================================================================
# Oracle mutants MO-1..MO-4
# ===========================================================================


# MO-1: a pipeline reports the LAST stage's status. Measured against
# s_runtime_fail, whose true run_exit is 1, so a 0 is unambiguous swallowing.
#
# The mutant is bound to the ACTUAL failed process, not to an unrelated command:
# it captures the real status first, then routes THAT status through a pipeline
# (`( exit $run_exit ) | cat`) and re-reads $?. An inserted `true | cat` would
# only have shown that any intervening command clobbers $? -- a weaker claim
# that does not demonstrate the real failure being lost by the pipeline itself.
def test_mo1_status_through_a_pipe_loses_the_failure(tmp_path):
    workroot = H.make_workroot(tmp_path, ("s_runtime_fail",))
    target = H.subject_path(workroot, "s_runtime_fail")
    piped = "run_exit=$?\n( exit $run_exit ) | cat >/dev/null\nrun_exit=$?"
    subs = [(H.ANCHOR_MO1_STATUS, piped)]
    true_rec, mut_rec = _control_vs_mutant(tmp_path, workroot, target, subs)
    assert int(true_rec["run_exit"]) == 1, "the control must see the real failure"
    assert int(mut_rec["run_exit"]) == 0, f"piped mutant: {mut_rec['run_exit']}"


# MO-2: strict parsing turns a rootdir misconfiguration into a visible empty
# selection, which EMPTY_SELECTION then refuses; `grep ::` turns it into
# plausible-looking ids that identify no file, and stays silent.
def test_mo2_loose_parser_admits_filename_stripped_ids(tmp_path):
    workroot = H.make_workroot(tmp_path, ("s_pass",))
    outside = tmp_path / "outside" / "s_pass"
    outside.mkdir(parents=True)
    target = outside / "test_s.py"
    target.write_text(H.SUBJECTS["s_pass"]["src"], encoding="utf-8")

    # Parser-level control first, using the real programs, so the end-to-end
    # difference below is attributable to the parser and not to the subject.
    stripped = f"{STRIPPED_ID}\n::test_alpha[with space]\n"
    assert H.sed_recover(stripped) == [], "the strict parser accepted stripped ids"
    loose = H.run(["/usr/bin/grep", "::"], stdin=stripped, timeout=60).stdout.splitlines()
    assert len(loose) == 2, f"grep :: rejected stripped ids, got {loose!r}"

    subs = [(H.ANCHOR_MO2_PARSER, "grep '::'")]
    true_rec, mut_rec = _control_vs_mutant(tmp_path, workroot, target, subs)
    assert int(true_rec["selected_count"]) == 0, "strict oracle must fail CLOSED"
    assert int(mut_rec["selected_count"]) != 0, "the loose parser detected nothing"
    assert all(s.startswith("::") for s in mut_rec["selected"]), mut_rec["selected"]


# MO-3: order is part of the compared fact -- an unsorted list makes two honest
# runs disagree and a dishonest one indistinguishable. s_pass defines zebra
# before alpha[with space], and that asymmetry is what makes this arm
# non-vacuous; if it were lost, the second assertion below fires and says so.
def test_mo3_missing_sort_changes_the_selection_order(tmp_path):
    workroot = H.make_workroot(tmp_path, ("s_pass",))
    target = H.subject_path(workroot, "s_pass")
    subs = [(H.ANCHOR_MO3_SORT, "cat")]
    true_rec, mut_rec = _control_vs_mutant(tmp_path, workroot, target, subs)
    assert true_rec["selected"] == H.selected_of("s_pass")
    # Re-author s_pass out of sorted order if the first ever goes green-for-free.
    assert mut_rec["selected"] != true_rec["selected"], "removing the sort was inert"
    assert sorted(mut_rec["selected"]) == true_rec["selected"], "entries lost/gained"


# MO-4: --noconftest keeps ambient conftest code out of the measurement. The
# observable is FIXTURE RESOLUTION, not a print: measured, pytest captures
# conftest-level stdout under this profile, so a marker print is invisible and
# would have made this arm vacuous.
def test_mo4_dropping_noconftest_admits_a_seeded_conftest(tmp_path):
    root, target = _seeded_fixture_tree(tmp_path)
    subs = [(H.ANCHOR_MO4_NOCONFTEST, "-p no:cacheprovider")]
    ctrl, mut = _control_vs_mutant(tmp_path, root, target, subs)
    assert int(ctrl["run_exit"]) != 0, "ambient conftest reached the measurement"
    assert int(mut["run_exit"]) == 0, f"--noconftest drop was inert: {mut!r}"


# ===========================================================================
# Isolation controls IC-1, IC-2 -- SAFE ARMS ONLY
# ===========================================================================


def test_ic1_seeded_conftest_fixture_resolves_only_without_noconftest(tmp_path):
    root, target = _seeded_fixture_tree(tmp_path)
    off = H.run_profile(root, target, collect_only=False, noconftest=False)
    on = H.run_profile(root, target, collect_only=False, noconftest=True)
    assert (off.stdout + off.stderr).strip(), "the --noconftest OFF arm ran nothing"
    assert (on.stdout + on.stderr).strip(), "the --noconftest ON arm ran nothing"
    assert off.returncode == 0, f"fixture did not resolve when ENABLED: {off.stdout}"
    assert on.returncode != 0, "with --noconftest the seeded fixture still resolved"
    assert "fixture 'seeded_value' not found" in (on.stdout + on.stderr), on.stdout


# IC-2: asserting "pytest-cov is not loaded" would need pytest-cov installed to
# mean anything; a seeded plugin is the same claim with no dependency. The
# capable arm is essential: the profile's -I ignores PYTHONPATH, so without it
# both negative arms would pass because the plugin could never load at all.
def test_ic2_seeded_plugin_loads_only_outside_the_profile(tmp_path):
    root = tmp_path / "workroot"
    sub = root / "ic2"
    sub.mkdir(parents=True)
    marker = "F0_SEEDED_PLUGIN_ACTIVE"
    plugin = f'def pytest_configure(config):\n    print("{marker}")\n'
    (root / "f0_seeded_plugin.py").write_text(plugin, encoding="utf-8")
    target = sub / "test_s.py"
    target.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    env = {"PYTHONPATH": str(root)}

    plug = ("-p", "f0_seeded_plugin")
    capable = H.run_profile(root, target, extra=plug, env_extra=env, isolated=False)
    ambient = H.run_profile(root, target, env_extra=env)
    off = (*plug, "-p", "no:f0_seeded_plugin")
    suppressed = H.run_profile(root, target, extra=off, env_extra=env, isolated=False)
    for label, proc in (("capable", capable), ("ambient", ambient), ("suppressed", suppressed)):
        assert (proc.stdout + proc.stderr).strip(), f"the {label} arm ran nothing"

    assert marker in capable.stdout + capable.stderr, f"never loaded: {capable.stdout}"
    assert marker not in ambient.stdout + ambient.stderr, "ambient plugin got in"
    assert ambient.returncode == 0, f"the profile arm failed otherwise: {ambient.stdout}"
    assert marker not in suppressed.stdout + suppressed.stderr, "-p no: did not suppress"
