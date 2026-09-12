"""Shared apparatus for the F0 bootstrap trust proof suite."""

# Outside ``tests/`` deliberately, and that placement is load-bearing:
# ``tests/conftest.py`` injects ``plugins/`` onto ``sys.path`` and does an
# unguarded product import at collection, and
# ``scripts/validate_test_categorization.py`` globs ``tests/**/test_*.py``.
# A trust harness may not load the system it measures.
#
# No product imports, no network, no ``gh``, no paid service. Every mutable
# artifact goes to a freshly allocated private temp directory.

from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

PROOF_DIR = Path(__file__).resolve().parent


def _repo_root() -> Path:
    for candidate in [PROOF_DIR, *PROOF_DIR.parents]:
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("no .git ancestor above the F0 proof suite")


ROOT = _repo_root()
CT_DIR = ROOT / "bootstrap" / "control_trust"
ORACLE = CT_DIR / "oracle.sh"
TRUSTCHECK = CT_DIR / "trustcheck.py"
CASES = CT_DIR / "cases.json"
RUNG_SCOPE = CT_DIR / "rung_scope.json"
WORKFLOW = ROOT / ".github" / "workflows" / "control-runner-trust.yml"
CANDIDATE = PROOF_DIR / "subjects" / "candidate_verifier.py"

ORACLE_WHAT = "bootstrap/control_trust/oracle.sh"
TC_WHAT = "bootstrap/control_trust/trustcheck.py"
CAND_WHAT = "proof/subjects/candidate_verifier.py"

# The EXECUTING interpreter, or one explicitly supplied. Never a fixed shared
# /tmp path: such a path is a local setup artifact that will not exist in a
# clean checkout or in CI, so pinning one makes the suite pass only where it was
# authored. interpreter_facts() verifies it at runtime instead.
#
# NOT .resolve()d. MEASURED: a venv's bin/python imports pytest 8.4.2 fine, but
# its realpath (the base CPython in Cellar) fails `-I -B -c "import pytest"`
# with ModuleNotFoundError. The invocation path is what carries virtualenv
# semantics, so dereferencing the symlink silently leaves the pinned
# environment. Use .absolute(), which never follows links.
PYTHON = Path(os.environ.get("F0_PYTHON") or sys.executable).absolute()

# The APPROVED profile. A version probe alone is not proof of running it, so
# these are enforced, and profile_violations() is exercised by a wrong-profile
# negative control -- a check that cannot refuse tells you nothing.
REQUIRED_PYTHON_SERIES = "3.11."
REQUIRED_PYTEST = "8.4.2"

# A freshly allocated private bytecode-cache prefix for this process.
# MEASURED: -B gives NO-WRITE, not stale-read immunity. With a pre-existing
# __pycache__ beside a subject whose bytes changed at equal length and restored
# mtime, `-B -I --noconftest -c /dev/null --rootdir=... -p no:cacheprovider`
# still collected the OLD node ids at exit 0. The same command plus
# -X pycache_prefix=<fresh private dir> collected the CURRENT ones. The prefix
# is ephemeral invocation scratch, never a persistent store.
PYCACHE_PREFIX = Path(tempfile.mkdtemp(prefix="f0-pycache-"))
atexit.register(shutil.rmtree, PYCACHE_PREFIX, True)

# CORRECTED PARSER. The previous program, s/^\([^ :][^ ]*::[^ ]*\)$/\1/p,
# silently dropped every valid node id containing a space -- a pytest parameter
# id such as `test_p[with space]`. Two independently written parsers encoded the
# SAME false assumption and agreed on the same incomplete set, so comparing them
# to each other could never find it. The fix requires the part BEFORE `::` to be
# whitespace-free and to end in `.py` (a subject-qualified id) and allows
# anything after it, so parameter ids survive while the summary line, plugin
# chatter and rootdir-stripped ids are still rejected.
NODE_ID_SED = r"s/^\([^ :][^ ]*\.py::.*\)$/\1/p"

SCHEMA = "f0-oracle-1"
SCALAR_FIELDS = (
    "schema python python_version target subject_digest "
    "collect_exit run_exit selected_count nonce"
).split()

# Mutation anchors the runtime MUST carry exactly once each. substitute()
# refuses 0 or >1 matches, so a drifting implementation gives a loud RED rather
# than a mutant that changes nothing and then "passes".
ANCHOR_MO1_STATUS = "run_exit=$?"
ANCHOR_MO2_PARSER = "sed -n '" + NODE_ID_SED + "'"
ANCHOR_MO3_SORT = "LC_ALL=C sort"
ANCHOR_MO4_NOCONFTEST = "--noconftest"
ANCHOR_MT1_FIELDS = "    check_required_fields,\n"
ANCHOR_MT2_NONCE = "    check_nonce,\n"
ANCHOR_MT3_IDS = "    check_selected_ids,\n"
ANCHOR_MT4_NONEMPTY = "    check_non_empty,\n"
ANCHOR_MT5_DIGEST = "    check_subject_digest,\n"
ANCHOR_MB3_CLASSIFIER = '    return path.endswith(".py") or path.endswith(".sh")'

# The four subjects and their hand-declared truth, in ONE table.
#
# `selected` is THE THIRD, INDEPENDENT SOURCE: written from observed pytest
# output, not produced by the oracle's parser and not by the candidate's. Every
# selection assertion in this suite is made against it. The central defect was
# two implementations checked against each other, so nothing here compares one
# parser to the other.
#
# s_pass carries BOTH an ordinary node id and a parameter id containing a space,
# defined out of sorted order (zebra before alpha[...]):
#   - the space-bearing id is the case the old parser lost, and the ordinary id
#     beside it keeps the incomplete result NON-EMPTY, so no emptiness check can
#     stand in for the real assertion;
#   - the definition/sort asymmetry is what makes MO-3 ("remove the sort")
#     non-vacuous.
#
# collect/run of None means "assert NON-ZERO", never the literal 5, so a pytest
# release renumbering no-tests-collected does not cry wolf.
#
# ONE source template for the two parameter-bearing subjects: identical shape,
# differing only in the assertion that decides pass-or-fail at CALL time.
_SRC = (
    "import pytest\n\n\n"
    "def test_zebra():\n    assert True\n\n\n"
    '@pytest.mark.parametrize("v", [1], ids=["with space"])\n'
    "def test_alpha(v):\n    assert {}\n"
)


# The hand-declared expectation for a subject built from _SRC, spelled out in
# ONE place: sorted, and carrying the space-bearing parameter id the old parser
# silently dropped. Still the THIRD source -- neither parser produces it.
def _ids(name: str) -> list[str]:
    return [f"{name}/test_s.py::test_alpha[with space]", f"{name}/test_s.py::test_zebra"]


PASS_IDS, FAIL_IDS = _ids("s_pass"), _ids("s_runtime_fail")
COLLECT_ERR = "import nonexistent_module_xyz\n\n\ndef test_never():\n    assert True\n"
SUBJECTS = {
    "s_pass": {"src": _SRC.format("True"), "collect": 0, "run": 0, "selected": PASS_IDS},
    "s_collect_error": {"src": COLLECT_ERR, "collect": 2, "run": 2, "selected": []},
    # Collects cleanly and fails at CALL time, and carries the space-bearing id
    # too, so the direct receipt-boundary arms exercise both at once.
    "s_runtime_fail": {"src": _SRC.format("v == 2"), "collect": 0, "run": 1, "selected": FAIL_IDS},
    "s_empty": {"src": "X = 1\n", "collect": None, "run": None, "selected": []},
}
SUBJECT_NAMES = tuple(SUBJECTS)
# Only for SYNTHETIC fixtures, where a concrete non-zero exit must be written
# into the record. Every arm that MEASURES s_empty asserts "non-zero", never
# this literal, so a pytest release renumbering it cannot make an arm cry wolf.
EMPTY_COLLECT = EMPTY_RUN = 5

# The candidate's contracted bounded-out result: a NAMED outcome, not merely a
# non-zero exit, so it is distinguishable from a startup crash.
CHILD_TIMEOUT_EXIT = 3
CHILD_TIMEOUT_TOKEN = "F0_CHILD_TIMEOUT"


def selected_of(name: str) -> list[str]:
    return SUBJECTS[name]["selected"]


def require(path: Path, what: str) -> Path:
    # Acceptance-first: this suite is RED until the implementer writes the runtime.
    assert path.exists(), f"F0 RUNTIME ABSENT: {what} is not at {path}"
    return path


def new_nonce() -> str:
    return secrets.token_hex(8)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def profile_env(extra=None) -> dict:
    return {"PATH": "/usr/bin:/bin", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", **(extra or {})}


def run(argv, cwd=None, env_extra=None, timeout=300, stdin=None):
    where = None if cwd is None else str(cwd)
    kw = dict(capture_output=True, text=True, input=stdin, env=profile_env(env_extra))
    return subprocess.run([str(a) for a in argv], cwd=where, timeout=timeout, **kw)


def profile_violations(py_version: str, pytest_version: str) -> list[str]:
    out = []
    if not py_version.startswith(REQUIRED_PYTHON_SERIES):
        out.append(f"PYTHON_SERIES:{py_version}")
    if pytest_version != REQUIRED_PYTEST:
        out.append(f"PYTEST_VERSION:{pytest_version}")
    return out


@lru_cache(maxsize=1)
def interpreter_facts() -> tuple[str, str]:
    # Versions are never inferred from a checked-in path: a relocated or
    # substituted interpreter is reported here rather than silently changing
    # what every downstream expectation means.
    probe = "import platform,pytest;print(platform.python_version());print(pytest.__version__)"
    proc = run([PYTHON, "-B", "-I", "-c", probe], timeout=120)
    assert proc.returncode == 0, f"{PYTHON} cannot import pytest: {proc.stderr!r}"
    parts = proc.stdout.split()
    assert len(parts) == 2, f"unexpected version probe output: {proc.stdout!r}"
    # Every subject expectation here was measured under the approved profile, so
    # a different one turns them from measurements into claims.
    bad = profile_violations(*parts)
    assert not bad, f"{PYTHON} is {parts}, not the approved profile: {bad}"
    return parts[0], parts[1]


def make_workroot(base: Path, names: tuple = ()) -> Path:
    # Under-workroot placement is the PV-1 precondition: a subject in a sibling
    # directory yields filename-stripped ids and a permanent zero selection.
    workroot = base / "workroot"
    workroot.mkdir(parents=True, exist_ok=True)
    for name in names or SUBJECT_NAMES:
        (workroot / name).mkdir(parents=True, exist_ok=True)
        (workroot / name / "test_s.py").write_text(SUBJECTS[name]["src"], "utf-8")
    return workroot


def subject_path(workroot: Path, name: str) -> Path:
    return workroot / name / "test_s.py"


def run_profile(
    workroot,
    target,
    collect_only=True,
    noconftest=True,
    extra=(),
    env_extra=None,
    isolated=True,
    pycache_prefix=PYCACHE_PREFIX,
    timeout=180,
):
    # Two SEPARATE properties, deliberately separable here so each has its own
    # arm: -B is NO-WRITE (nothing lands beside the subject or in the source
    # worktree); -X pycache_prefix is NO-STALE-READ (lookup is redirected away
    # from an existing __pycache__, which -B alone does not do). -I ignores
    # PYTHONDONTWRITEBYTECODE and PYTHONPYCACHEPREFIX, so both must be flags.
    #
    # -B is UNCONDITIONAL: no arm may enable process-wide bytecode writing, which
    # would permit writes beside installed pytest, its dependencies and the
    # stdlib. The stale-bytecode stimulus is instead compiled explicitly, for the
    # private subject only, by SEED_PYC in test_oracle.py.
    # -s is unconditional too: the IC-2 arms turn -I OFF so their private
    # PYTHONPATH is honoured, and must still start without the real user site.
    prefix = ["-X", f"pycache_prefix={pycache_prefix}"] if pycache_prefix else []
    base = ["-m", "pytest", "-p", "no:cacheprovider", "-c", "/dev/null", f"--rootdir={workroot}"]
    opts = (["--noconftest"] if noconftest else []) + (["--collect-only"] if collect_only else [])
    argv = [PYTHON, "-B", "-s", *prefix, *(["-I"] if isolated else []), *base, *opts]
    return run([*argv, *extra, "-q", target], cwd=workroot, env_extra=env_extra, timeout=timeout)


def sed_recover(text: str) -> list[str]:
    # Re-expressing it here would compare this suite's idea of the parser to
    # itself; the bytes that ship in oracle.sh are what is measured.
    proc = run(["/usr/bin/sed", "-n", NODE_ID_SED], stdin=text, timeout=60)
    assert proc.returncode == 0, f"sed itself failed: {proc.stderr}"
    return [line for line in proc.stdout.splitlines() if line]


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


def parse_record(text: str) -> dict:
    # Dropping unknown keys would make the UNKNOWN_FIELD arm untestable. Values
    # may contain spaces: a parameter node id does.
    rec: dict = {"selected": []}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition("=")
        if key == "selected":
            rec["selected"].append(value)
        else:
            rec[key] = value
    return rec


# TWO INPUT SHAPES, ONE COMPARISON, TWO FORMATS INVENTORIED HONESTLY:
#   1. `f0-oracle-1` -- the PRIVATE bootstrap protocol of the POSIX oracle only,
#      flat key=value, deliberately dumb and independent.
#   2. `control-tool-receipt-1` -- the ONE public canonical receipt, emitted by
#      the candidate because it stands in for R0. Not an F0-specific schema.
# The two sides serialize by their own routes and share no encoder or parser;
# the harness renders both only to synthesize fixtures for the comparator arms.
def render_record(rec: dict) -> str:
    lines = [f"{k}={rec[k]}" for k in SCALAR_FIELDS if k in rec]
    lines += [f"{k}={rec[k]}" for k in rec if k not in SCALAR_FIELDS and k != "selected"]
    lines += [f"selected={sid}" for sid in rec.get("selected", [])]
    return "\n".join(lines) + "\n"


RECEIPT_SCHEMA = "control-tool-receipt-1"
CASE_ID = "f0-executing-candidate"
TOOL_VERSION = "candidate-verifier-1"
OBSERVATION_FIELDS = tuple(f for f in SCALAR_FIELDS if f != "schema") + ("selected",)


def render_receipt(rec: dict, top_extra=None, obs_extra=None) -> str:
    """Synthesize a canonical receipt envelope from a flat record dict."""
    obs = {"stage": "executing", **{k: rec[k] for k in OBSERVATION_FIELDS if k in rec}}
    for key in ("collect_exit", "run_exit", "selected_count"):
        if key in obs:
            obs[key] = int(obs[key])
    obs["selected"] = list(rec.get("selected", []))
    obs.update(obs_extra or {})
    envelope = {
        "schema": RECEIPT_SCHEMA,
        "case": CASE_ID,
        "observation": obs,
        "decision": "PASS" if int(rec.get("run_exit", 0)) == 0 else "FAIL",
        "tool_version": TOOL_VERSION,
        "dependency_digests": expected_dependency_digests(),
    }
    envelope.update(top_extra or {})
    return json.dumps(envelope, sort_keys=True, indent=2) + "\n"


def parse_receipt(text: str) -> dict:
    doc = json.loads(text)
    obs = doc.get("observation", {})
    rec = {k: str(v) for k, v in obs.items() if k != "selected"}
    rec["selected"] = list(obs.get("selected", []))
    rec["_envelope"] = doc
    return rec


# A receipt that vouches for its own bindings proves nothing, so the harness
# resolves them from the bytes of the EXECUTABLE UNDER TEST. A mutant runs from a
# temp copy and therefore carries its own digest: passing that mutant here is what
# keeps its intended refusal attributable to the one defect it was given, instead
# of every mutant arm refusing for DEPENDENCY_DIGEST_MISMATCH.
def expected_dependency_digests(verifier: Path = CANDIDATE) -> dict:
    manifest = digest(CASES) if CASES.exists() else ""
    return {"case_manifest": manifest, "verifier": digest(verifier) if verifier.exists() else ""}


def synthetic_record(workroot: Path, name: str, nonce: str) -> dict:
    """EXPLICITLY SYNTHETIC, from the hand-declared SUBJECTS table and never
    labelled a measurement: real observations call run_oracle/run_candidate."""
    exp = SUBJECTS[name]
    target = subject_path(workroot, name)
    assert target.exists(), f"{name} has no materialised subject at {target}"
    return {
        "schema": SCHEMA,
        "python": str(PYTHON),
        "python_version": interpreter_facts()[0],
        "target": str(target),
        "subject_digest": digest(target),
        "collect_exit": str(EMPTY_COLLECT if exp["collect"] is None else exp["collect"]),
        "run_exit": str(EMPTY_RUN if exp["run"] is None else exp["run"]),
        "selected_count": str(len(exp["selected"])),
        "nonce": nonce,
        "selected": list(exp["selected"]),
    }


# NO THIRD RECORD PATH. Arms that must observe a real execution invoke the real
# producers (run_oracle / run_candidate) and read what those emit; the only
# fixture builder here is synthetic_record, and it says so in its own name.
def write_boundary(dirpath: Path, oracle_side, candidate_bytes: str):
    # Parsing the candidate's stdout and re-rendering it would mean the
    # comparator never saw the bytes the producer actually emitted, which is the
    # entire point of a boundary test. A dict oracle_side is a synthesized
    # fixture; a str is the oracle's own literal stdout.
    dirpath.mkdir(parents=True, exist_ok=True)
    orc, cand = dirpath / "oracle.rec", dirpath / "candidate.json"
    text = render_record(oracle_side) if isinstance(oracle_side, dict) else oracle_side
    orc.write_text(text, encoding="utf-8")
    cand.write_text(candidate_bytes, encoding="utf-8")
    return orc, cand


# ---------------------------------------------------------------------------
# Runtime invocation
# ---------------------------------------------------------------------------


# Resolved at CALL time, never captured at import. MEASURED DEFECT: capturing
# PYTHON into module constants meant monkeypatching H.PYTHON changed the value a
# test asserted on while the interpreter actually invoked stayed the original --
# the relocation arm would have passed without relocating anything.
def _py_flags() -> list:
    return [PYTHON, "-B", "-X", f"pycache_prefix={PYCACHE_PREFIX}", "-I"]


def _common() -> list:
    return ["--python", PYTHON, "--pycache-prefix", PYCACHE_PREFIX]


def run_oracle(workroot, target, nonce, script=None):
    """CONTRACT: oracle.sh --target T --workroot W --nonce N --python P
    --pycache-prefix D, emitting one flat f0-oracle-1 record on stdout."""
    script = script or require(ORACLE, ORACLE_WHAT)
    argv = ["/bin/sh", script, "--target", target, "--workroot", workroot, "--nonce", nonce]
    return run([*argv, *_common()], cwd=workroot)


def run_candidate(workroot, target, nonce, script=None, child_timeout=120, timeout=300):
    """CONTRACT: candidate ... --child-timeout S. Every child it spawns is bounded
    by --child-timeout; the wrapper timeout here is a backstop, not the bound."""
    script = script or require(CANDIDATE, CAND_WHAT)
    argv = [*_py_flags(), script, "--target", target, "--workroot", workroot, "--nonce", nonce]
    argv += [*_common(), "--child-timeout", child_timeout, "--case", CASE_ID]
    argv += ["--case-manifest", require(CASES, "cases.json")]
    return run(argv, cwd=workroot, timeout=timeout)


def trustcheck(args, script=None):
    script = script or require(TRUSTCHECK, TC_WHAT)
    return run([*_py_flags(), script, *args], cwd=ROOT)


def compare(
    oracle_file,
    candidate_file,
    nonce,
    expect_digest=None,
    script=None,
    case=CASE_ID,
    tool_version=TOOL_VERSION,
    dep_digests=None,
):
    """CONTRACT: compare ... --expect-case/--expect-tool-version/
    --expect-dependency-digests, from bytes the CALLER resolved independently."""
    deps = expected_dependency_digests() if dep_digests is None else dep_digests
    args = ["compare", "--oracle", str(oracle_file), "--candidate", str(candidate_file)]
    args += ["--nonce", nonce, "--expect-case", case, "--expect-tool-version", tool_version]
    args += ["--expect-dependency-digests", json.dumps(deps, sort_keys=True)]
    if expect_digest:
        args += ["--expect-subject-digest", expect_digest]
    return trustcheck(args, script=script)


REFUSAL_SHAPE = re.compile(r"^REFUSED: [A-Z][A-Z0-9_]+ .+$")


def reason_of(proc) -> str:
    # stdout is asserted NON-EMPTY first: an empty stdout must never be read as
    # "no reason present, therefore fine".
    assert proc.stdout.strip(), f"trustcheck emitted NOTHING: {_detail(proc)}"
    # The single-line, REASON_ID-then-explanation shape is enforced HERE, so
    # every refusal arm in the suite inherits it instead of one arm asserting it
    # once. A refusal printing a traceback or three lines cannot be parsed by a
    # caller discriminating on REASON_ID.
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected exactly one stdout line, got {lines!r}"
    assert REFUSAL_SHAPE.match(lines[0]), f"bad refusal shape: {lines[0]!r}"
    return lines[0][len("REFUSED: ") :].split(" ", 1)[0].strip()


def _detail(proc):
    return f"exit={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"


# ONE expected-result assertion, so no arm can assert a weaker shape for itself.
# reason_id=None is the PERMITTED arm (exit 0 AND the contracted OK line); a
# reason_id is the REFUSED arm, where a non-zero exit alone proves nothing --
# the arm must fail for the reason it targets or it measures some other defect.
def expect(proc, reason_id: str | None = None) -> None:
    if reason_id is None:
        assert proc.returncode == 0, f"expected exit 0 (facts agreed): {_detail(proc)}"
        assert proc.stdout.startswith("OK "), f"exit 0 but no OK line: {proc.stdout!r}"
        return
    assert proc.returncode == 1, f"expected exit 1 for {reason_id}: {_detail(proc)}"
    assert reason_of(proc) == reason_id, f"refused for {reason_of(proc)}, not {reason_id}"


# ---------------------------------------------------------------------------
# Mutation: anchored substitution on a TEMP COPY. Tracked source is never
# touched, and scripts/mutation_witness.py is deliberately not imported -- it
# mutates tracked source in place under an fcntl lock.
# ---------------------------------------------------------------------------


def substitute(source: str, anchor: str, replacement: str) -> str:
    # At 0 the mutant would equal the control and its green would mean nothing;
    # above 1 it would mutate the wrong site.
    count = source.count(anchor)
    assert count == 1, f"anchor {anchor!r} appears {count} time(s), expected one"
    return source.replace(anchor, replacement)


def mutant_of(src: Path, dest_dir: Path, subs: list, what: str) -> Path:
    # The control copy sits at the same depth with the same permissions, so a
    # mutant's red can never be read as "a copy of this file cannot run from a
    # temp directory".
    require(src, what)
    text = src.read_text(encoding="utf-8")
    for anchor, replacement in subs:
        text = substitute(text, anchor, replacement)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    dest.write_text(text, encoding="utf-8")
    dest.chmod(0o755)
    return dest


def control_copy(src: Path, dest_dir: Path, what: str) -> Path:
    return mutant_of(src, dest_dir, [], what)


# ---------------------------------------------------------------------------
# Git fixtures for the budget arms: a throwaway repo in a private temp dir,
# never the real worktree, never a shared /tmp name.
# ---------------------------------------------------------------------------

GIT_ENV = {"GIT_AUTHOR_NAME": "f0", "GIT_AUTHOR_EMAIL": "f0@invalid", "GIT_COMMITTER_NAME": "f0"}
# No ambient identity, configuration or attributes: a disposable fixture that
# reads the machine's git config can be steered by it (core.hooksPath among
# others), and that config belongs to the user, not to this suite.
GIT_ENV |= {"GIT_COMMITTER_EMAIL": "f0@invalid", "GIT_CONFIG_GLOBAL": "/dev/null"}
GIT_ENV |= {"GIT_CONFIG_SYSTEM": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1"}
# One baseline CLI surface, so MB-6's added parser is the SECOND one; with an
# empty baseline a single added parser would sit inside the limit and MB-6 would
# pass without testing anything.
BASELINE_CLI = "import argparse\n\n\ndef main():\n    return argparse.ArgumentParser()\n"


def git(repo: Path, *args: str):
    env = {**GIT_ENV, "HOME": str(repo)}
    return run(["/usr/bin/git", "-C", repo, *args], env_extra=env, timeout=120)


def git_fixture(base: Path, scope: dict) -> tuple[Path, str]:
    repo = base / "gitfix"
    ct = repo / "bootstrap" / "control_trust"
    ct.mkdir(parents=True)
    # An EMPTY template directory: no sample hooks and no ambient template
    # content are copied into this throwaway repository's .git.
    template = base / "empty-template"
    template.mkdir(exist_ok=True)
    init = git(repo, "init", "-q", "-b", "main", f"--template={template}")
    # A failed init STOPS here, before any add/commit/checkout. Continuing would
    # let git's ancestor discovery resolve those mutations against whatever
    # repository encloses this fixture -- the route from a disposable arm into a
    # live checkout. The toplevel is then asserted to BE the fixture root, so
    # discovery cannot have redirected it.
    assert init.returncode == 0, f"fixture git init failed: {init.stderr!r}"
    top = git(repo, "rev-parse", "--show-toplevel").stdout.strip()
    assert Path(top).resolve() == repo.resolve(), f"toplevel {top!r} is not {repo}"
    write_json(ct / "rung_scope.json", scope)
    (ct / "oracle.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (ct / "trustcheck.py").write_text(BASELINE_CLI, encoding="utf-8")
    sha = git_commit_all(repo, "baseline")
    assert len(sha) == 40, f"git fixture produced no base sha: {sha!r}"
    return repo, sha


def git_commit_all(repo: Path, message: str) -> str:
    added = git(repo, "add", "-A")
    assert added.returncode == 0, f"fixture add failed: {added.stderr!r}"
    proc = git(repo, "commit", "-q", "-m", message)
    assert proc.returncode == 0, f"fixture commit failed: {proc.stderr}"
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def snapshot(*roots: Path) -> dict:
    # Used to OBSERVE that a run wrote nothing, rather than grepping a command
    # line for a -B that may or may not have had the intended effect.
    out: dict = {}
    for root in (r for r in roots if r.exists()):
        for path in sorted(root.rglob("*")):
            st = path.lstat()
            out[str(path)] = (st.st_size, st.st_mtime_ns, path.is_dir())
    return out
