"""Rung budget arms MB-1..MB-9, MB-4a..c, CB-0 and the workflow properties."""

from __future__ import annotations

import json
import re
import shlex

import pytest
import yaml

import _harness as H

# Externally reviewed ceilings, injected from THIS file. Without an outside
# witness, raising a limit and the change that needs it in one edit satisfies
# every intra-scope invariant -- the two-constant escape hatch.
REVIEWED_RUNTIME_LINES = 400
REVIEWED_PROOF_LINES = 1500
REVIEWED_CLI_SURFACES = 1
REVIEWED = (
    f"runtime_lines={REVIEWED_RUNTIME_LINES},proof_lines={REVIEWED_PROOF_LINES}"
    f",cli_surfaces={REVIEWED_CLI_SURFACES}"
)

# The SUPPORTED REPRODUCTION argv: the same frozen suite under the same pinned
# profile, runnable by hand. NOT a claim that every observed local run issued
# these exact bytes -- those went through a wrapper carrying the same suite and
# the same profile. CI must run this string and no other, or a CI green is
# evidence about a different command than the one anyone can reproduce. -B keeps
# bytecode out of the worktree and out of the measurement;
# $F0_BASETEMP is allocated fresh per run by the workflow env.
# -X pycache_prefix is as load-bearing as -B and for a DIFFERENT reason: -B is
# no-write, the prefix is no-stale-read. The outer trust suite runs under the
# same profile it imposes on its children, or CI measures a different thing.
LOCAL_COMMAND = (
    "env -i PATH=/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "
    '"$F0_PYTHON" -B -X pycache_prefix="$F0_PYCACHE" -I -m pytest '
    "-p no:cacheprovider -c /dev/null "
    '--rootdir="$PWD/bootstrap/control_trust/proof" --basetemp="$F0_BASETEMP" '
    "--noconftest -q bootstrap/control_trust/proof"
)

RUNS_ON = r"^ubuntu-\d+\.\d+$"
# push.branches selects which PUSHED branches fire. pull_request.branches selects
# the PR's TARGET (base) branch and never its head -- a head-name condition would
# be github.head_ref, which this workflow does not use. The F0 PR is STACKED on
# plan/control-tool-v12, so THAT entry is what makes this workflow fire on the
# rung's own pull request; feat/control-tool-f0 earns its place under push (that
# branch's own pushes) and, under pull_request, denotes PRs TARGETING it rather
# than PRs from it. A workflow that cannot run on its own PR reads as nothing
# rather than as a failure -- the Q1 connectivity failure this rung exists to
# catch, so the whole set is asserted, not assumed.
REQUIRED_TRIGGER_BRANCHES = ("plan/control-tool-v12", "feat/control-tool-f0", "master")
# No artifact uploads and no cache actions: the usual routes to incidental cost
# and to smuggling state between runs.
FORBIDDEN_ACTIONS = ("actions/upload-artifact", "actions/cache")
REQUIRED_JOB_ENV = ("F0_PYTHON", "F0_BASETEMP", "F0_PYCACHE")
# CI CONNECTIVITY. STRUCTURAL property of the checked-in workflow TEXT: it
# establishes what the file DECLARES, never that a run happened, passed or
# failed. Actual run evidence belongs on #1773, never in a comment here.
# actions/checkout@v4 defaults to depth 1, which cannot resolve the pinned
# ancestor CB-0 requires, and its all-history mode fetches branch refs under
# refs/remotes/origin -- so the declared base_branch must be spelled a way BOTH
# a local clone and the runner can resolve, or the rung is unmeasurable in CI
# while still passing locally.
REQUIRED_BASE_REF = "refs/remotes/origin/plan/control-tool-v12"
# The single verdict step carries this exact name, so the required check is
# identifiable in a checks list instead of inferred from a command string.
VERDICT_STEP_NAME = "control-tool-complexity-ratchet"

# CONTEXT AVAILABILITY. GitHub provides a DIFFERENT set of contexts at each key,
# and an expression naming one that is unavailable AT THAT KEY is a workflow-level
# error: the run never starts, so this rung's verdict reads as NOTHING rather than
# as a failure -- the same Q1 connectivity class as a workflow that cannot fire,
# and the reason it is checked here rather than assumed. MEASURED, actionlint
# 1.7.12 on 2026-09-12: the shipped jobs.trust.env carried ${{ runner.temp }} and
# exited 1 with `context "runner" is not allowed here`; the SAME values bound on
# the steps that consume them exit 0. What was wrong was the key, not the value.
# The set below is what GitHub allows at JOB-LEVEL keys -- everything under a job
# except steps:, which get a wider set (env, job, runner, steps) and are NOT
# checked by this arm. HONEST SCOPE: at a few job-level keys (name, runs-on)
# GitHub is narrower still -- secrets is excluded there -- so this refuses the
# CATEGORY without claiming to reproduce every row of GitHub's table. The property
# is the category, not the one expression that prompted it, which is why the
# second arm below is a different context at a different key.
JOB_KEY_CONTEXTS = frozenset(("github", "inputs", "matrix", "needs", "secrets", "strategy", "vars"))
EXPR_CTX = re.compile(r"\$\{\{\s*([A-Za-z_][A-Za-z0-9_-]*)")
# The two temp roots, written ONCE and used twice: as the flow-style step env of
# the positive control below, and as the pre-fix job-level value its refusing arm
# replays. A second copy is how the control and the artifact drift apart. Flow
# style parses to the same mapping the real workflow's block style parses to, and
# the checker reads the parsed document, never the bytes.
TEMP_PATH = "${{ runner.temp }}/f0-%s-${{ github.run_id }}"
TEMP_ENV = f'{{F0_BASETEMP: "{TEMP_PATH % "basetemp"}", F0_PYCACHE: "{TEMP_PATH % "pycache"}"}}'

# Setup is permitted but BOUNDED BY SHAPE, not by an open allowance: pinned
# dependency installation and fresh private root allocation, nothing else. A
# wrapper script or composite action would satisfy the letter and move the drift
# somewhere this checker cannot see it, so neither is a supported shape.
SETUP_SHAPES = (
    re.compile(r"^python -m pip install(?: [A-Za-z0-9_.-]+==[0-9][A-Za-z0-9_.-]*)+$"),
    re.compile(r'^mkdir -p "\$F0_BASETEMP" "\$F0_PYCACHE"$'),
)
# A verdict routed through a pipeline reports the LAST stage's status. This
# checker reads workflow TEXT, so a finding here is a limitation of the declared
# shape -- a diagnostic pipeline whose shell exit is not the pytest exit -- and
# never an observed CI failure; run evidence is recorded on #1773. It is the
# same defect class MO-1 and MC-1 catch in the producers.
#
# Why this suite asserts NAMED reasons and RAW process exits rather than
# trusting a status, with a measured citation: on run 34289878195
# `claude-review.yml` reported SUCCESS while logging "No trigger found, skipping
# remaining steps" -- a green that reviewed nothing. A check can pass by
# skipping the work it names, the same shape as the measured `enabled=true`
# alongside 0 log exporters and an event-dropped warning: the signal reports the
# mechanism's PRESENCE, not its OPERATION.
PIPELINE_TOKENS = ("|", "&&", ";", "tee")

CT = "bootstrap/control_trust"
BASE_SCOPE = {
    "limits": {"runtime_lines": 10, "proof_lines": 20, "cli_surfaces": 1},
    "changed_paths": [f"{CT}/**", "scripts/**"],
    "removals": [],
}
RAISED_LIMITS = {"runtime_lines": REVIEWED_RUNTIME_LINES + 1, "cli_surfaces": REVIEWED_CLI_SURFACES}
RAISED_LIMITS["proof_lines"] = REVIEWED_PROOF_LINES + 1
RAISED = {**BASE_SCOPE, "limits": RAISED_LIMITS}
NARROW = {**BASE_SCOPE, "changed_paths": [f"{CT}/**"]}
PROMISED = {**BASE_SCOPE, "removals": [f"{CT}/oracle.sh"]}
WITH_DOCS = {**BASE_SCOPE, "changed_paths": [f"{CT}/**", "scripts/**", "docs/**"]}
# The scope for the ignored-untracked control: its .gitignore is itself a
# committed change, so it must sit under a declared glob or the row would refuse
# for OMITTED_SPLIT instead of exercising the inventory.
IGNORING = {**BASE_SCOPE, "changed_paths": [f"{CT}/**", "scripts/**", ".gitignore"]}
# MB-4c fixture scope. The rung is STACKED, so the branch it is stacked on is the
# thing its base can fall behind.
STACKED = {**BASE_SCOPE, "base_branch": "plan"}

FORTY_LINES = "".join(f"helper_{i} = {i}\n" for i in range(40))
SIXTY_LINES = "".join(f"p_{i} = {i}\n" for i in range(60))
SH_APPENDER = "#!/bin/sh\necho hi >> ./led\n"
PY_APPENDER = 'def w(p):\n    with open(p, "a") as fh:\n        fh.write("x")\n'
PROOF_BIG = {f"{CT}/proof/test_big.py": SIXTY_LINES}
SECOND_CLI = (
    "import argparse\n\n\ndef main():\n" "    return argparse.ArgumentParser(prog='second')\n"
)


def _budget(repo, base, scope_path, script=None, reviewed=REVIEWED):
    args = ["budget", "--repo", str(repo), "--base", base, "--scope", str(scope_path)]
    return H.trustcheck([*args, "--reviewed", reviewed], script=script)


def _counted(path):
    # The counting rule expressed independently of the tool that reports it:
    # physical lines, minus blanks, minus whole-line comments.
    lines = path.read_text(encoding="utf-8").splitlines()
    return sum(1 for ln in lines if ln.strip() and not ln.lstrip().startswith("#"))


def _fixture(tmp_path, scope=None):
    repo, base = H.git_fixture(tmp_path, scope or BASE_SCOPE)
    return repo, base, repo / CT / "rung_scope.json"


def _apply(repo, changes, label):
    """Write/delete the seeded paths and commit. `None` content means delete."""
    for rel, content in changes.items():
        path = repo / rel
        if content is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    H.git_commit_all(repo, label)


# ===========================================================================
# CB-0: the unmutated instrument must PERMIT
# ===========================================================================


# CB-0, against the REAL repo at the base rung_scope.json itself pins. Without
# it every MB-* refusal below could equally mean "the budget instrument refuses
# everything".
#
# CONSOLIDATION: the control-copy row is removed. Its obligation -- a plain COPY
# of trustcheck.py RUNS from tmp_path, without which every mutant that runs from
# there is misattributed -- is owned, for THIS subcommand, by the `safe-repo`
# permit row of test_git_effects_are_refused_before_any_query, which executes
# exactly that copy under `budget`. The control-copy row of
# test_ct0_identical_true_records_agree covers `compare` only: a different
# subcommand is different evidence, so it does not discharge this one alone.
def test_cb0_unmutated_budget_against_the_real_worktree_agrees():
    H.require(H.RUNG_SCOPE, "bootstrap/control_trust/rung_scope.json")
    scope = json.loads(H.RUNG_SCOPE.read_text(encoding="utf-8"))
    base = scope["base"]
    assert re.fullmatch(r"[0-9a-f]{40}", base), f"base={base!r} is not a 40-hex sha"
    # Without a declared base_branch the currency check (MB-4c) has nothing to
    # compare the pinned base against, and would be inert on the real repo. Its
    # SPELLING is load-bearing too: a bare local branch name resolves here and
    # not on a runner, a connectivity failure that would read as a pass.
    assert scope.get("base_branch") == REQUIRED_BASE_REF, scope.get("base_branch")
    tip = H.git(H.ROOT, "rev-parse", scope["base_branch"]).stdout.strip()
    assert tip == base, f"the pinned base is not the {REQUIRED_BASE_REF} tip {tip!r}"
    proc = _budget(H.ROOT, base, H.RUNG_SCOPE)
    H.expect(proc)
    # The untracked half of the inventory, against the REAL worktree. An exit 0
    # over a handful of modified TRACKED files says nothing about the F0 tree,
    # which is untracked here: an inventory built from the committed diff alone
    # would report proof_lines=0 and permit any size at all. The independently
    # counted lines of the untracked proof files are a FLOOR the tool's own
    # figure has to clear. HONEST SCOPE: once this tree is committed the floor
    # falls to 0 and this row weakens to the non-zero assertion; the
    # unconditional obligation is carried by the private fixtures below.
    match = re.search(r"proof_lines=(\d+)", proc.stdout)
    assert match, f"the OK line reports no proof inventory: {proc.stdout!r}"
    others = H.git(H.ROOT, "ls-files", "--others", "--exclude-standard").stdout.split()
    floor = sum(_counted(H.ROOT / p) for p in others if p.startswith(f"{CT}/proof/"))
    assert int(match.group(1)) > 0, f"nothing was inventoried at all: {proc.stdout!r}"
    assert int(match.group(1)) >= floor, f"{match.group(1)} reported, {floor} untracked alone"


# ===========================================================================
# Untracked, non-ignored files are part of BOTH inventories
# ===========================================================================

# The shape a committed diff cannot see: a rung's own new runtime is UNTRACKED
# until the moment it lands, so an inventory built from `git diff base HEAD`
# alone measures nothing until after the growth it exists to refuse has already
# been committed. Each row commits ONE small in-scope doc change and then leaves
# the file under test untracked.
#
# ATTRIBUTION, asserted in the body rather than assumed: the committed diff is
# asserted NOT to carry the seeded file, and `ls-files --others
# --exclude-standard` is asserted to list it exactly when it is not ignored. So
# a refusal here can only come from an inventory that reads untracked files.
# `absent` is the same fixture with no seeded file and must PERMIT, which is what
# attributes the refusal to the file rather than to the fixture; `ignored` keeps
# the file but git-ignores it and must ALSO permit, so an implementation that
# counted every untracked path -- ignored ones included -- is visibly wrong too.
#
# THE SEEDED MISSING-SITE CONTROL for this enumerator (v12:198). The runtime has
# ONE untracked mechanism, and BOTH inventories consume it: the changed-path
# listing and the scoped accounting listing. So ONE anchored substitution blinds
# both, and the blind copy still exits 0 from git -- a pathspec matching nothing
# is not an error -- which is exactly the shape that matters: an inventory that
# SILENTLY OMITS, not one that fails loudly.
#
# BINDING REQUIREMENT for whoever formats or edits the runtime: the anchor is
# that constant's whole assignment line, spelled exactly. At 58 columns Black-100
# leaves it alone, but a rename or a re-wrap breaks the substitution -- loudly,
# by design (substitute() refuses zero or multiple matches), never as an inert
# green.
UNTRACKED_ANCHOR = 'UNTRACKED = ("ls-files", "--others", "--exclude-standard")'
UNTRACKED_BLIND = 'UNTRACKED = ("ls-files", "--others", "--exclude-standard", "--", "f0-none")'
UNTRACKED_ARMS = [
    ("over-budget", BASE_SCOPE, "scripts/f0_helper.py", False, "RUNTIME_LINES_OVER_BUDGET"),
    ("stray-path", NARROW, "docs/stray.py", False, "OMITTED_SPLIT"),
    ("ignored", IGNORING, "scripts/f0_helper.py", True, None),
    ("absent", BASE_SCOPE, None, False, None),
]


@pytest.mark.parametrize(
    "label,scope,rel,ignored,expect", UNTRACKED_ARMS, ids=[a[0] for a in UNTRACKED_ARMS]
)
def test_untracked_non_ignored_files_are_inventoried(tmp_path, label, scope, rel, ignored, expect):
    repo, base, scope_path = _fixture(tmp_path, scope)
    committed = {f"{CT}/note.txt": "n\n"}
    if ignored:
        committed[".gitignore"] = rel + "\n"
    _apply(repo, committed, label)
    if rel:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(FORTY_LINES, encoding="utf-8")

    tracked = H.git(repo, "diff", "--name-only", base, "HEAD").stdout.split()
    assert rel not in tracked, f"{label}: the seed was committed, so nothing is untracked"
    others = H.git(repo, "ls-files", "--others", "--exclude-standard").stdout.split()
    assert others == ([] if (rel is None or ignored) else [rel]), f"{label}: {others!r}"
    H.expect(_budget(repo, base, scope_path), expect)
    if expect is None:
        return
    # The permitted rows returned above and stay the opposing controls. For each
    # FAULT the same seeded repository is re-measured by the blind copy, which
    # must FALSELY PERMIT: without this, all four rows above show only that the
    # current runtime behaves, and an inventory that reads untracked files could
    # not be told apart from one that merely happens to refuse. `over-budget`
    # attributes the SCOPED ACCOUNTING route (its file is inside every declared
    # glob, so only the measured lines can refuse it); `stray-path` attributes
    # the CHANGED-PATH DISCOVERY route (its file is outside them). Two false
    # permits, one per route, from one mutation.
    subs = [(UNTRACKED_ANCHOR, UNTRACKED_BLIND)]
    blind = H.mutant_of(H.TRUSTCHECK, tmp_path / "blind", subs, H.TC_WHAT)
    permitted = _budget(repo, base, scope_path, script=blind)
    assert permitted.returncode == 0, f"{label}: blind still refused: {permitted.stdout!r}"


# ===========================================================================
# The budget arms. Each row seeds ONE change in a throwaway repo. Structurally
# identical arms are rows, not functions; the rationale for each is above it.
# ===========================================================================

BUDGET_ARMS = [
    # MB-1: raise the operative limits AND make the change that needs them in
    # one edit -- growth absorbed with every intra-scope assertion still green.
    # Only the externally injected REVIEWED ceiling can see it.
    ("MB-1", RAISED, {f"{CT}/extra.py": "e = 1\n"}, "LIMIT_ABOVE_REVIEWED"),
    # MB-2: runtime is a ROLE, not a directory. A helper parked in scripts/ is
    # runtime F0 must carry; hiding it by location is the cheapest way to look
    # small. It is covered by a declared glob, so this isolates the LINE budget.
    ("MB-2", BASE_SCOPE, {"scripts/f0_helper.py": FORTY_LINES}, "RUNTIME_LINES_OVER_BUDGET"),
    # MB-5: zero changed files passes every per-file budget trivially. An empty
    # changeset must be refused, not scored as perfect.
    ("MB-5", BASE_SCOPE, {}, "EMPTY_CHANGESET"),
    # MB-6 (NON-DELETABLE): F0 ships ONE argparse CLI. A second parser is a
    # second surface to keep honest forever, and is how one tool becomes three.
    # The fixture baseline already holds one, so this addition is the second.
    ("MB-6", BASE_SCOPE, {f"{CT}/second_cli.py": SECOND_CLI}, "CLI_SURFACES_OVER_BUDGET"),
    # MB-7 (NON-DELETABLE), both shapes: an append writer is how a bootstrap
    # harness quietly acquires state, and state is what turns a check into
    # something gameable. Issue #1718 pins the repo count at 33; F0 adds zero.
    # A grep for open(...,"a") alone misses the first; one for '>>' the second.
    ("MB-7-shell", BASE_SCOPE, {f"{CT}/appender.sh": SH_APPENDER}, "APPEND_WRITER_ADDED"),
    ("MB-7-python", BASE_SCOPE, {f"{CT}/appender.py": PY_APPENDER}, "APPEND_WRITER_ADDED"),
    # INV-4: a bootstrap trust harness that can edit the enforcement it might
    # later judge is not independent of it.
    ("INV-4", BASE_SCOPE, {"plugins/autonomous-dev/lib/f0_touch.py": "X = 1\n"}, "INV4_VIOLATION"),
    # MB-8 (NON-DELETABLE): the declaration is generated from what is observed,
    # so a path that changed while matching no declared glob means declaration
    # and reality have split. Ignoring it lets any file leave by omission.
    ("MB-8", NARROW, {"docs/stray.py": "Y = 2\n"}, "OMITTED_SPLIT"),
    # MB-9 (NON-DELETABLE): "we will delete X" is the commonest unkept half of a
    # shrink; the promise is worth something only if its absence is checked.
    ("MB-9", PROMISED, {f"{CT}/note.txt": "n\n"}, "ABSENT_REMOVAL"),
    # The proof suite is budgeted too: a harness free to grow without limit in
    # order to prove a runtime that may not is the same problem relocated.
    ("proof-lines", BASE_SCOPE, PROOF_BIG, "PROOF_LINES_OVER_BUDGET"),
    # Opposite controls, DIFFERENT in shape from the arms they control: the same
    # edit under a declared glob, and a promise actually kept. Without them the
    # refusals above could all mean "the instrument refuses every changeset".
    ("MB-8-control", WITH_DOCS, {"docs/stray.py": "Y = 2\n"}, None),
    ("MB-9-control", PROMISED, {f"{CT}/oracle.sh": None}, None),
]


@pytest.mark.parametrize("label,scope,changes,expect", BUDGET_ARMS, ids=[a[0] for a in BUDGET_ARMS])
def test_budget_arm(tmp_path, label, scope, changes, expect):
    # VACUITY: the changeset is asserted non-empty exactly when the arm needs
    # one, and a declared removal is asserted present or absent to match the arm,
    # so no row can pass because its seed silently did nothing. The two -control
    # rows expect exit 0 from the same engine, so a refusal cannot be produced by
    # an instrument that refuses everything.
    repo, base, scope_path = _fixture(tmp_path, scope)
    if changes:
        _apply(repo, changes, label)
    else:
        base = H.git(repo, "rev-parse", "HEAD").stdout.strip()

    changed = H.git(repo, "diff", "--name-only", base, "HEAD").stdout.split()
    assert bool(changed) == (expect != "EMPTY_CHANGESET"), f"{label}: changed={changed!r}"
    still_present = [p for p in scope["removals"] if (repo / p).exists()]
    assert bool(still_present) == (expect == "ABSENT_REMOVAL"), f"{label}: {still_present!r}"
    H.expect(_budget(repo, base, scope_path), expect)
    if label != "MB-2":
        return
    # MB-3, the PERMITTING half, attached to the row whose refusal it explains.
    # CONSOLIDATION: the standalone MB-3 test rebuilt this same fixture, seeded
    # the same scripts/f0_helper.py at the same size under the same scope and
    # asserted the same RUNTIME_LINES_OVER_BUDGET refusal the MB-2 row already
    # asserts. Only that duplicate fixture and refusal are gone: MB-3 keeps its
    # exact anchor (substitute() refuses zero or multiple matches, so the
    # mutation cannot be inert) and its own mutant exit. Both halves are required
    # -- a mutant that permits alone would be satisfied by an instrument that
    # permits everything, which the two -control rows above rule out.
    mutant = H.mutant_of(
        H.TRUSTCHECK,
        tmp_path / "mb3",
        [(H.ANCHOR_MB3_CLASSIFIER, '    return path.startswith("bootstrap/")')],
        H.TC_WHAT,
    )
    permitted = _budget(repo, base, scope_path, script=mutant)
    # Still refusing means the MB-2 row is not attributable to the classifier.
    assert permitted.returncode == 0, f"narrowing did not hide it: {permitted.stdout}"


@pytest.mark.parametrize(
    "base,reason_id",
    [("0" * 40, "BASE_UNRESOLVABLE"), ("main", "BASE_NOT_PINNED"), ("HEAD~1", "BASE_NOT_PINNED")],
)
def test_mb4_base_must_be_a_pinned_resolvable_commit(tmp_path, base, reason_id):
    # MB-4a. A moving base makes every later measurement incomparable; a symbolic
    # one is a base that can be redefined afterwards.
    repo, _, scope_path = _fixture(tmp_path)
    H.expect(_budget(repo, base, scope_path), reason_id)


def test_mb4_base_not_an_ancestor_is_refused(tmp_path):
    # MB-4b, the subtle case: it resolves, so only an ancestry check refuses it.
    repo, base, scope_path = _fixture(tmp_path)
    H.git(repo, "checkout", "-q", "-b", "sidebranch", base)
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    orphan = H.git_commit_all(repo, "divergent")
    H.git(repo, "checkout", "-q", "main")
    (repo / CT / "note.txt").write_text("m\n", encoding="utf-8")
    H.git_commit_all(repo, "mainline")
    assert orphan != base, "the fixture did not actually diverge"
    H.expect(_budget(repo, orphan, scope_path), "BASE_NOT_ANCESTOR")


# MB-4c: base CURRENCY, which is a DIFFERENT property from the base VALIDITY of
# MB-4a/4b. This base resolves AND is an ancestor, so neither of those refuses
# it; only a currency check does. A superseded base silently puts everything that
# landed on the stacked-on branch since outside the measured diff, so growth
# carried there is invisible to every per-file budget. The `current` row is the
# opposite control: the same fixture, the same engine, one commit of real change,
# and the base still at its branch tip must be PERMITTED.
@pytest.mark.parametrize(
    "label,advance,expect", [("stale", True, "BASE_STALE"), ("current", False, None)]
)
def test_mb4c_a_base_its_branch_moved_past_is_refused(tmp_path, label, advance, expect):
    repo, base, scope_path = _fixture(tmp_path, STACKED)
    H.git(repo, "branch", "plan", base)
    if advance:
        H.git(repo, "checkout", "-q", "plan")
        (repo / "upstream.txt").write_text("landed since\n", encoding="utf-8")
        assert H.git_commit_all(repo, "the base branch moves on") != base
        H.git(repo, "checkout", "-q", "main")
    _apply(repo, {f"{CT}/note.txt": "n\n"}, label)
    tip = H.git(repo, "rev-parse", "plan").stdout.strip()
    assert (tip != base) == advance, f"{label}: tip={tip!r} base={base!r}"
    H.expect(_budget(repo, base, scope_path), expect)


def test_git_unavailable_is_refused_not_assumed_clean(tmp_path):
    # Failing open here would make the whole budget inert.
    plain = tmp_path / "notarepo"
    (plain / CT).mkdir(parents=True)
    scope_path = H.write_json(plain / CT / "rung_scope.json", BASE_SCOPE)
    H.expect(_budget(plain, "a" * 40, scope_path), "GIT_UNAVAILABLE")


# ===========================================================================
# Configured Git effects, refused BEFORE any object or worktree query
# ===========================================================================

# MEASURED dependency fact, NOT a portable barrier: the pinned runtime git is
# /usr/bin/git, measured 2.39.3 (Apple Git-146), which has no GIT_NO_LAZY_FETCH.
# A worktree query in a repository configured with a clean or process filter RUNS
# that command; a promisor / partial-clone configuration can FETCH; a mode-160000
# entry can traverse submodule configuration. The frozen boundary is deliberately
# small -- a local-config key check WITH includes, plus a stage inventory --
# refusing an unsupported configuration BY NAME instead of traversing it. It is
# not a sandbox and claims none; the host's current config was clean, which is a
# precondition of one machine, not a guard.
GIT_EFFECTS, GITLINK = "GIT_EFFECTS_UNSUPPORTED", "SUBMODULE_UNSUPPORTED"
# A HARMLESS private sentinel: it appends to a file under tmp_path and passes the
# content through unchanged. No arm contacts a network and none claims a lazy
# fetch was reproduced -- the promisor rows assert refusal and the ABSENCE of any
# effect, which is what can honestly be established without one.
# The constant carries ONLY the fixed shell program. The sentinel path travels as
# a POSITIONAL argument quoted by shlex.join, never interpolated into script
# source: git hands a filter value to a shell, and the value itself is then
# re-split, so a basetemp holding a quote, a space or a $-expression would
# otherwise break the outer quoting or expand in the inner shell. The basename
# in the arm carries all three so the counter-control proves they stay literal DATA.
SENTINEL_PROGRAM = 'echo ran >> "$1"; cat'
EFFECT_ARMS = [
    ("clean-filter", "filter.f0.clean", None, False, GIT_EFFECTS),
    ("process-filter", "filter.f0.process", None, False, GIT_EFFECTS),
    ("promisor-remote", "remote.origin.promisor", "true", False, GIT_EFFECTS),
    ("partial-clone", "extensions.partialClone", "origin", False, GIT_EFFECTS),
    # Reachable ONLY through include.path: a guard that reads .git/config without
    # includes cannot see this key and would permit exactly the same effect.
    ("included-clean-filter", "filter.f0.clean", None, True, GIT_EFFECTS),
    ("gitlink", None, None, False, GITLINK),
    # The permit arm: same engine, same disposable repo, no configured effect and
    # no gitlink, must still be MEASURED rather than refused.
    ("safe-repo", None, None, False, None),
]


@pytest.mark.parametrize("label,key,value,inc,expect", EFFECT_ARMS, ids=[a[0] for a in EFFECT_ARMS])
def test_git_effects_are_refused_before_any_query(tmp_path, label, key, value, inc, expect):
    # The changeset is committed BEFORE any effect is configured, so the setup
    # cannot itself fire the sentinel and the pre-run assertion below is real.
    # Every git setup return code is checked: a silently failed seed would leave
    # an arm refusing (or permitting) for a reason it does not name.
    repo, base, scope_path = _fixture(tmp_path)
    _apply(repo, {f"{CT}/note.txt": "n\n"}, label)
    sentinel = tmp_path / "effect ' dollar${F0_UNSET}-ran"
    extra = repo / ".git" / "f0extra.config"
    if key:
        filt = shlex.join(["/bin/sh", "-c", SENTINEL_PROGRAM, "f0-filter", str(sentinel)])
        where = ["config", "--file", str(extra)] if inc else ["config"]
        seeded = H.git(repo, *where, key, value or filt)
        assert seeded.returncode == 0, f"{label}: {key} not seeded: {seeded.stderr!r}"
        (repo / ".gitattributes").write_text("* filter=f0\n", encoding="utf-8")
        if inc:
            res = H.git(repo, "config", "include.path", str(extra))
            assert res.returncode == 0, f"include.path not seeded: {res.stderr!r}"
    if expect == GITLINK:
        add = H.git(repo, "update-index", "--add", "--cacheinfo", f"160000,{base},sub")
        assert add.returncode == 0, f"gitlink not staged: {add.stderr!r}"
        assert "160000 " in H.git(repo, "ls-files", "--stage").stdout, "no gitlink staged"
    assert not sentinel.exists(), f"{label}: the fixture setup already ran the filter"
    # CB-0's relocated COPY permit, on the one row that must be PERMITTED: the
    # `budget` subcommand runs from a plain control copy in tmp_path, so no red
    # anywhere in this file can be read as "a copy of trustcheck.py cannot run
    # from a temp directory". The refusing rows keep H.TRUSTCHECK itself, which
    # is the F0 source checkout's script -- no consumer install is in evidence.
    copy = H.control_copy(H.TRUSTCHECK, tmp_path / "control", H.TC_WHAT) if not expect else None
    H.expect(_budget(repo, base, scope_path, script=copy), expect)
    assert not sentinel.exists(), f"{label}: a configured effect ran during the query"
    if label == "clean-filter":
        # The other half. With a directly controlled unsafe query the SAME
        # configuration really does execute, so the refusal above is not vacuous;
        # the guard refused BEFORE this point, which is the ordering under test.
        (repo / CT / "note.txt").write_text("modified\n", encoding="utf-8")
        probe = H.git(repo, "diff", "--name-only")
        assert probe.returncode == 0, f"the controlled query failed: {probe.stderr!r}"
        assert sentinel.exists(), "the clean filter cannot run; the refusal is vacuous"


# ===========================================================================
# Workflow properties
# ===========================================================================


def workflow_violations(doc) -> list[str]:
    # One checker so the negative-control fixture exercises the same code path
    # the real file does. PyYAML parses a bare `on:` key as the boolean True,
    # hence doc.get(True).
    out = []
    if not isinstance(doc, dict) or not doc:
        return ["EMPTY_DOCUMENT"]
    jobs = doc.get("jobs") or {}
    if not jobs:
        return ["NO_JOBS"]
    triggers = doc.get(True, doc.get("on", {}))
    if "workflow_run" in json.dumps(triggers):
        out.append("WORKFLOW_RUN_TRIGGER")
    for event in ("push", "pull_request"):
        spec = triggers.get(event) if isinstance(triggers, dict) else None
        branches = (spec or {}).get("branches") or [] if isinstance(spec, dict) else []
        absent = [b for b in REQUIRED_TRIGGER_BRANCHES if b not in branches]
        out += [f"TRIGGER_NOT_COVERED:{event}:{b}" for b in absent]
    # Anywhere in the document, at any depth: one continue-on-error is a route
    # from a real failure to a green job.
    if "continue-on-error" in json.dumps(doc):
        out.append("CONTINUE_ON_ERROR")
    for name, job in jobs.items():
        if "needs" in job:
            out.append(f"NEEDS:{name}")
        if "uses" in job:
            out.append(f"REUSABLE_WORKFLOW:{name}")
        # str() rather than json.dumps(): a YAML scalar can parse to a date, which
        # json cannot serialise. MEASURED, not assumed: such a document already
        # raises at the continue-on-error json.dumps(doc) above, which is a
        # PRE-EXISTING limitation of this checker and not one this arm adds -- str()
        # simply declines to add a second place that would raise.
        for key in (k for k in job if k != "steps"):
            bad = sorted(set(EXPR_CTX.findall(str(job[key]))) - JOB_KEY_CONTEXTS)
            out += [f"CONTEXT_NOT_AVAILABLE:{name}:{key}:{c}" for c in bad]
        if not re.match(RUNS_ON, str(job.get("runs-on", ""))):
            out.append(f"RUNS_ON_NOT_PINNED:{name}")
        if job.get("timeout-minutes") != 10:
            out.append(f"TIMEOUT:{name}")
        steps = [s for s in (job.get("steps") or []) if isinstance(s, dict)]
        # The required names are looked for at the job AND at its steps, because
        # GitHub decides which of the two a value may be spelled at: runner.temp is
        # legal only on a step, so a job-env-only check would demand a spelling the
        # platform refuses. Names, not values -- a name bound in one step and read
        # in another leaves that step's expansion EMPTY, which fails the run
        # loudly; it is the unstartable workflow above that fails silently.
        env = set(job.get("env") or ()) | {k for s in steps for k in (s.get("env") or ())}
        out += [f"ENV_MISSING:{name}:{k}" for k in REQUIRED_JOB_ENV if k not in env]
        uses = [str(s.get("uses", "")) for s in steps if isinstance(s, dict)]
        withs = [s.get("with") or {} for s in steps if isinstance(s, dict)]
        out += [f"FORBIDDEN_ACTION:{name}:{u}" for u in uses if u.startswith(FORBIDDEN_ACTIONS)]
        # Depth 1 cannot resolve the pinned ancestor; fetch-depth 0 is all history.
        checkouts = [w for u, w in zip(uses, withs) if u.startswith("actions/checkout")]
        if not any(str(w.get("fetch-depth")) == "0" for w in checkouts):
            out.append(f"CHECKOUT_NOT_ALL_HISTORY:{name}")
        # actions/checkout@v4 declares persist-credentials with DEFAULT true in
        # its action.yml, and the runner supplies that default, so an ABSENT key
        # leaves a usable token in .git/config for every later step. EVERY
        # checkout must opt out: an any-one-safe check passes a job whose second
        # checkout re-persists the token. The action reads that input as a
        # case-insensitive "true" string, so both YAML false and the quoted
        # "false" really do disable persistence while missing and true do not --
        # a false-SPELLING check, never truthiness. (Read off the v4 snapshots of
        # action.yml and src/input-helper.ts; not a promise about every future
        # upstream version, which is why the property is re-checked here.)
        unsafe = [w for w in checkouts if str(w.get("persist-credentials")).lower() != "false"]
        if unsafe:
            out.append(f"CHECKOUT_PERSISTS_CREDENTIALS:{name}:{len(unsafe)}")
        runs = [s for s in steps if isinstance(s, dict) and "run" in s]
        verdicts = [s for s in runs if s["run"].strip() == LOCAL_COMMAND]
        if len(verdicts) != 1:
            out.append(f"VERDICT_STEP_COUNT:{name}:{len(verdicts)}")
        else:
            # The verdict step runs LAST so the job's exit is its exit, with the
            # honest qualification that actions' own POST steps still run after it
            # and can fail the job: a conclusion is not literally the raw exit.
            if runs[-1] is not verdicts[0]:
                out.append(f"VERDICT_NOT_LAST:{name}")
            if verdicts[0].get("name") != VERDICT_STEP_NAME:
                out.append(f"VERDICT_STEP_NAME:{name}")
        for cmd in (s["run"].strip() for s in runs if s["run"].strip() != LOCAL_COMMAND):
            if not any(shape.match(cmd) for shape in SETUP_SHAPES):
                out.append(f"SETUP_NOT_BOUNDED:{name}:{cmd[:40]}")
        if not any(re.match(r"^\d+\.\d+\.\d+$", str(w.get("python-version", ""))) for w in withs):
            out.append(f"PYTHON_NOT_PINNED:{name}")
    return out


# The seeded bad workflow, carrying EVERY violation the checker names so it goes
# through the SAME function the real file does. Job `a` stacks the needs,
# continue-on-error and forbidden-action shapes; `b` is a reusable-workflow call
# (drift moved somewhere this checker cannot see); `c` puts the verdict step
# somewhere other than last, which is where the job's exit stops being the pytest
# exit -- the MO-1 / MC-1 defect class relocated into CI.
# `c` also carries an otherwise-correct full-history checkout that never opts out
# of credential persistence, so that prefix is in the matrix as well.
BAD_WORKFLOW = f"""on:
  workflow_run:
    workflows: [other]
jobs:
  a:
    needs: [c]
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/cache@v4
      - run: echo a
  b:
    uses: ./.github/workflows/reusable.yml
  c:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: {LOCAL_COMMAND}
      - run: echo after the verdict
"""


def test_workflow_has_no_forbidden_properties():
    # CONSOLIDATION: the separate parse/non-empty arm is gone because the same
    # checker owns it -- {} returns EMPTY_DOCUMENT and a jobless mapping returns
    # NO_JOBS, both asserted in the negative control below, so an empty parse
    # cannot satisfy this vacuously.
    H.require(H.WORKFLOW, ".github/workflows/control-runner-trust.yml")
    violations = workflow_violations(yaml.safe_load(H.WORKFLOW.read_text("utf-8")))
    assert violations == [], f"workflow violations: {violations!r}"


def test_workflow_checker_negative_control():
    # A checker that cannot fail tells you nothing, and the two degenerate
    # documents are the vacuity guard itself: {} must be REPORTED, never accepted.
    assert workflow_violations({}) == ["EMPTY_DOCUMENT"]
    assert workflow_violations({"jobs": {}}) == ["NO_JOBS"]
    violations = workflow_violations(yaml.safe_load(BAD_WORKFLOW))
    named = (
        "CONTINUE_ON_ERROR WORKFLOW_RUN_TRIGGER NEEDS: TIMEOUT: RUNS_ON_NOT_PINNED: "
        "VERDICT_STEP_COUNT: SETUP_NOT_BOUNDED: ENV_MISSING: PYTHON_NOT_PINNED: "
        "TRIGGER_NOT_COVERED: FORBIDDEN_ACTION: REUSABLE_WORKFLOW: VERDICT_NOT_LAST: "
        "CHECKOUT_NOT_ALL_HISTORY: VERDICT_STEP_NAME: CHECKOUT_PERSISTS_CREDENTIALS:"
    ).split()
    for prefix in named:
        assert any(v.startswith(prefix) for v in violations), (prefix, violations)


# The POSITIVE control. Without it the checker is one-armed: a checker that
# refuses everything is indistinguishable from one that works. This fixture
# carries the supported bounded setup plus the single verdict-bearing step, and
# must come back with ZERO violations.
GOOD_WORKFLOW = f"""on:
  push:
    branches: [plan/control-tool-v12, feat/control-tool-f0, master]
  pull_request:
    branches: [plan/control-tool-v12, feat/control-tool-f0, master]
jobs:
  trust:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    env:
      F0_PYTHON: /opt/hostedtoolcache/Python/3.11.14/x64/bin/python
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@v5
        with:
          python-version: 3.11.14
      - run: python -m pip install pytest==8.4.2 PyYAML==6.0.2
      - run: mkdir -p "$F0_BASETEMP" "$F0_PYCACHE"
        env: {TEMP_ENV}
      - name: {VERDICT_STEP_NAME}
        env: {TEMP_ENV}
        run: {LOCAL_COMMAND}
"""


def test_workflow_checker_positive_control():
    doc = yaml.safe_load(GOOD_WORKFLOW)
    assert isinstance(doc, dict) and doc.get("jobs"), "the positive fixture is empty"
    assert workflow_violations(doc) == [], workflow_violations(doc)
    # CONSOLIDATION: the standalone raw-exit arm is folded in here, against the
    # same constant it always inspected. STRUCTURAL property of the declared
    # command TEXT, not a run outcome: the final explicit run step preserves
    # pytest's raw status, but actions' own POST steps can still fail the job, so
    # a job conclusion is not literally the raw exit. Run evidence goes to #1773.
    for token in PIPELINE_TOKENS:
        assert token not in LOCAL_COMMAND, f"{token!r} in the verdict command"


def test_a_context_unavailable_at_a_job_level_key_is_refused():
    # `shipped` REVERSES the fix exactly: TEMP_PATH is the value the real workflow
    # binds on its steps, put back at the job-level env key it was spelled at in
    # 5fa26e86 -- `F0_BASETEMP: ${{ runner.temp }}/f0-basetemp-${{ github.run_id }}`
    # -- so the guard is watched refusing the bytes that actually shipped, not a
    # paraphrase of them. The F0_PYCACHE half is the same context at the same key
    # and adds no distinct reason. The PERMITTING arm is deliberately not here:
    # the same checker over the unmodified GOOD_WORKFLOW and over the real file
    # must return [], asserted by test_workflow_checker_positive_control and
    # test_workflow_has_no_forbidden_properties. `other` is a DIFFERENT shape --
    # another context (steps) at another job-level key (if) -- over the otherwise
    # good document, so a guard that only knows `runner` at `env` fails it.
    shipped, other = yaml.safe_load(GOOD_WORKFLOW), yaml.safe_load(GOOD_WORKFLOW)
    shipped["jobs"]["trust"]["env"]["F0_BASETEMP"] = TEMP_PATH % "basetemp"
    other["jobs"]["trust"]["if"] = "${{ steps.probe.outputs.go }}"
    assert workflow_violations(shipped) == ["CONTEXT_NOT_AVAILABLE:trust:env:runner"], shipped
    assert workflow_violations(other) == ["CONTEXT_NOT_AVAILABLE:trust:if:steps"], other


# Credential-persistence arms over the OTHERWISE-GOOD document, so a refusal is
# attributable to THIS property and cannot be masked by an unrelated violation.
# `mixed` is the arm an any-one-safe implementation cannot survive: the first
# checkout opts out and a second one silently re-persists the token.
CRED_OFF = {"fetch-depth": 0, "persist-credentials": False}
CRED_ARMS = (
    ("explicit-false", [CRED_OFF], True),
    ("literal-false", [{"fetch-depth": 0, "persist-credentials": "false"}], True),
    ("missing", [{"fetch-depth": 0}], False),
    ("explicit-true", [{"fetch-depth": 0, "persist-credentials": True}], False),
    ("mixed", [CRED_OFF, {"persist-credentials": True}], False),
)


@pytest.mark.parametrize("label,checkouts,permitted", CRED_ARMS, ids=[a[0] for a in CRED_ARMS])
def test_every_checkout_must_opt_out_of_credential_persistence(label, checkouts, permitted):
    doc = yaml.safe_load(GOOD_WORKFLOW)
    job = doc["jobs"]["trust"]
    assert str(job["steps"][0].get("uses", "")).startswith("actions/checkout"), job["steps"][0]
    seeded = [{"uses": "actions/checkout@v4", "with": w} for w in checkouts]
    job["steps"] = seeded + job["steps"][1:]
    violations = workflow_violations(doc)
    persists = [v for v in violations if v.startswith("CHECKOUT_PERSISTS_CREDENTIALS")]
    # Nothing ELSE may differ from the positive control, or a permitting arm
    # could pass for a reason that has nothing to do with credentials.
    assert violations == persists, f"{label}: unrelated violations {violations!r}"
    assert (persists == []) is permitted, f"{label}: {violations!r}"
