#!/usr/bin/env python3
"""F0 bootstrap comparator and cumulative rung budget. Standard library only.

`compare` puts one flat f0-oracle-1 record beside one canonical receipt and
refuses BY NAME on the first disagreement. `budget` measures the cumulative rung
aggregate against a ceiling reviewed from OUTSIDE the rung. Neither writes
product state, emits product decision vocabulary, nor reaches the network. Exit 0
from `compare` says only that two independent observers reported the same facts;
where those facts include a non-zero subject exit, that exit is the evidence.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ORACLE_SCHEMA = "f0-oracle-1"
RECEIPT_SCHEMA = "control-tool-receipt-1"
# The nine compared observation facts, spelled once and in report order. ALL
# nine are required, and a key that is absent and a key present with a null
# value are ONE named defect: either would otherwise reach every later check as
# "nothing to compare" and fail open.
RECORD_FIELDS = "python python_version target subject_digest collect_exit".split()
RECORD_FIELDS += "run_exit selected_count nonce selected".split()
ORACLE_FIELDS = ["schema", *RECORD_FIELDS]
ENVELOPE_FIELDS = "schema case observation decision tool_version dependency_digests".split()
INTEGER_FIELDS = ("collect_exit", "run_exit", "selected_count")
# One compared fact, one REASON_ID, reported in this order. subject_digest is
# deliberately NOT here: it is owned by check_subject_digest, which runs after
# the node-id comparison so that a frozen prior record is attributed to the
# selection it replayed rather than to the subject bytes it also carried.
COMPARED_FACTS = (
    ("python", "PYTHON_MISMATCH"),
    ("python_version", "PYTHON_MISMATCH"),
    ("target", "TARGET_MISMATCH"),
    ("collect_exit", "COLLECT_EXIT_MISMATCH"),
    ("run_exit", "RUN_EXIT_MISMATCH"),
    ("selected_count", "SELECTED_MISMATCH"),
)


def refuse(reason_id: str, detail: object) -> int:
    # Exactly one line, REASON_ID first: a caller discriminating on the id cannot
    # parse a traceback or a paragraph, so the detail is whitespace-collapsed.
    sys.stdout.write("REFUSED: %s %s\n" % (reason_id, " ".join(str(detail).split())))
    return 1


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def load_side(path_text, prefix, parse):
    # ONE route per side: read the file, then hand the bytes to that side's own
    # independent parser, so no side can be parsed by the other's reader.
    # An unreadable record must never be read as agreement: a producer that
    # crashed leaves an empty file behind, and that is the fail-open shape.
    path = Path(path_text)
    if not path.exists():
        return None, (f"{prefix}_ABSENT", f"no record at {path}")
    text = read_text(path)
    if not text.strip():
        return None, (f"{prefix}_EMPTY", f"the record at {path} is empty")
    return parse(text)


def parse_oracle(text):
    rec = {"selected": []}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition("=")
        if not sep or key not in ORACLE_FIELDS:
            return None, ("ORACLE_MALFORMED", f"not an oracle field: {line[:60]!r}")
        if key == "selected":
            rec["selected"].append(value)
        else:
            rec[key] = value
    if rec.get("schema") != ORACLE_SCHEMA:
        return None, ("ORACLE_MALFORMED", f"schema is {rec.get('schema')!r}")
    for field in INTEGER_FIELDS:
        if field in rec and not re.fullmatch(r"-?\d+", rec[field]):
            return None, ("ORACLE_MALFORMED", f"{field} is not an integer: {rec[field]!r}")
    return rec, None


def parse_receipt(text):
    try:
        doc = json.loads(text)
    except ValueError as exc:
        return None, ("CANDIDATE_MALFORMED", f"the receipt is not JSON: {exc}")
    if not isinstance(doc, dict) or doc.get("schema") != RECEIPT_SCHEMA:
        return None, ("CANDIDATE_MALFORMED", f"not a {RECEIPT_SCHEMA} object")
    if not isinstance(doc.get("observation"), dict):
        return None, ("CANDIDATE_MALFORMED", "observation is absent or not an object")
    unknown = sorted(set(doc) - set(ENVELOPE_FIELDS))
    if unknown:
        return None, ("UNKNOWN_FIELD", f"the receipt envelope carries {unknown}")
    return doc, None


def flatten(doc: dict) -> dict:
    # Unknown keys INSIDE observation are legitimate R0 metadata and must travel
    # unchanged; only the envelope's own key set is closed. NOTHING is coerced
    # here: list() over a null `selected` raises before any check can name the
    # defect, and a traceback is not a REASON_ID.
    return dict(doc["observation"])


def paired(ctx, field):
    left, right = ctx.oracle.get(field), ctx.candidate.get(field)
    # An ABSENT field is owned by check_required_fields alone. Comparing here as
    # well would make that check's removal produce some other refusal instead of
    # the permit its mutation arm requires.
    if left is None or right is None:
        return None
    return str(left), str(right)


def check_required_fields(ctx):
    missing = [key for key in ENVELOPE_FIELDS if key not in ctx.envelope]
    if missing:
        return "MISSING_FIELD", f"the receipt envelope lacks {missing}"
    for label, rec in (("oracle record", ctx.oracle), ("receipt observation", ctx.candidate)):
        # A key PRESENT with a null value is not supplied evidence: it reaches
        # every later check as "nothing to compare" and would fail open, so an
        # absent key and a null value are ONE named defect rather than two
        # routes, one of which is named and one of which is a traceback.
        absent = [key for key in RECORD_FIELDS if rec.get(key) is None]
        if absent:
            return "MISSING_FIELD", f"the {label} lacks {absent}"
    return None


def check_bindings(ctx):
    # Truth is supplied by the CALLER from independently resolved bytes on EVERY
    # comparison. A receipt that vouches for its own provenance proves nothing.
    supplied = {"case": ctx.args.expect_case, "tool_version": ctx.args.expect_tool_version}
    for key, expected in supplied.items():
        if ctx.envelope.get(key) != expected:
            return f"{key.upper()}_MISMATCH", f"receipt {key} is {ctx.envelope.get(key)!r}"
    if ctx.envelope.get("dependency_digests") != ctx.args.expect_dependency_digests:
        return "DEPENDENCY_DIGEST_MISMATCH", "the receipt's digests are not the resolved ones"
    return None


def check_nonce(ctx):
    for label, rec in (("oracle record", ctx.oracle), ("receipt", ctx.candidate)):
        stamped = rec.get("nonce")
        if stamped is not None and str(stamped) != ctx.args.nonce:
            return "STALE_RECORD", f"the {label} carries nonce {stamped!r}, not this run's"
    return None


def check_compared_facts(ctx):
    for field, reason_id in COMPARED_FACTS:
        pair = paired(ctx, field)
        if pair and pair[0] != pair[1]:
            return reason_id, f"{field}: oracle {pair[0]!r}, receipt {pair[1]!r}"
    return None


def check_selected_ids(ctx):
    # The node-id SET AND ITS ORDER, never the count alone: a reordered or
    # substituted id keeps the count identical, and a count-only comparator is
    # blind to exactly that. The count itself is compared one check earlier, so
    # a consistently reduced count is refused by name too.
    left, right = ctx.oracle.get("selected"), ctx.candidate.get("selected")
    if left is None or right is None:
        return None
    if [str(sid) for sid in left] != [str(sid) for sid in right]:
        differ = sorted(set(map(str, left)) ^ set(map(str, right)))[:3]
        return "SELECTED_MISMATCH", f"{len(left)} oracle ids vs {len(right)}; differing {differ}"
    return None


def check_subject_digest(ctx):
    # Every other freshness signal says "fresh" over a stale measurement: after
    # an inert subject edit the path, the node ids, both exits and a re-stamped
    # nonce are all unchanged. Only independently supplied bytes refuse it.
    pair = paired(ctx, "subject_digest")
    if pair and pair[0] != pair[1]:
        return "STALE_SUBJECT", "the two observers digested different subject bytes"
    expected = ctx.args.expect_subject_digest
    for label, rec in (("oracle record", ctx.oracle), ("receipt", ctx.candidate)):
        got = rec.get("subject_digest")
        if expected and got is not None and str(got) != expected:
            return "STALE_SUBJECT", f"the {label} digests {got!r}, not the subject as it stands"
    return None


def check_non_empty(ctx):
    if not (ctx.oracle.get("selected") or ctx.candidate.get("selected")):
        return "EMPTY_SELECTION", "both observers selected NOTHING, so nothing was established"
    return None


# The ordered pipeline: the FIRST failing check names the refusal. Deleting one
# entry is the MT-* mutation, and each deletion must PERMIT the input its arm
# refuses -- which is why no other check may cover for it.
CHECKS = (
    check_required_fields,
    check_bindings,
    check_nonce,
    check_compared_facts,
    check_selected_ids,
    check_subject_digest,
    check_non_empty,
)


def cmd_compare(args) -> int:
    # A FIXED order, one load-and-parse route per side: an absent, empty or
    # malformed oracle is named as the ORACLE_* defect it is and is never
    # attributed to the receipt, and the candidate side likewise.
    oracle, err = load_side(args.oracle, "ORACLE", parse_oracle)
    if err:
        return refuse(*err)
    doc, err = load_side(args.candidate, "CANDIDATE", parse_receipt)
    if err:
        return refuse(*err)
    ctx = SimpleNamespace(oracle=oracle, candidate=flatten(doc), envelope=doc, args=args)
    for check in CHECKS:
        found = check(ctx)
        if found:
            return refuse(*found)
    counts = (int(oracle["run_exit"]), int(oracle["collect_exit"]), len(oracle["selected"]))
    sys.stdout.write("OK subject_exit=%d collect_exit=%d selected=%d\n" % counts)
    return 0


# ---------------------------------------------------------------------------
# The cumulative rung budget
# ---------------------------------------------------------------------------

GIT_ENV = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_GLOBAL": "/dev/null"}
GIT_ENV |= {"GIT_CONFIG_SYSTEM": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
GIT_ENV |= {"GIT_ATTR_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
# CONFIGURED GIT EFFECTS, refused BY NAME before the first object or worktree
# query rather than sandboxed -- this is a small boundary and claims to be
# nothing else. A clean or process filter RUNS a command during a worktree
# query; a promisor remote or a partialClone extension can FETCH; a mode-160000
# entry can traverse submodule configuration. MEASURED dependency fact: the
# pinned /usr/bin/git is 2.39.3 (Apple Git-146), which has NO GIT_NO_LAZY_FETCH,
# so no environment variable closes the fetch route on this host. --includes is
# explicit below because a scope-limited read defaults includes OFF, and an
# include.path indirection would otherwise be invisible to the check. A host
# whose configuration happens to carry none of these keys is a precondition of
# one machine, never the guard.
EFFECT_KEYS = r"^(filter\..*\.(clean|process)|remote\..*\.promisor|extensions\.partialclone)$"
# INV-4: a bootstrap harness able to edit the enforcement it may later judge is
# not independent of it. The SAME eleven globs as before, built rather than
# listed: the five plugin-source directories, plus the root-level copies an
# installed deployment lands beside them.
INV4_DIRS = "lib hooks agents commands skills".split()
INV4_GLOBS = [f"plugins/autonomous-dev/{d}/**" for d in INV4_DIRS]
INV4_GLOBS += "hooks/** lib/** agents/** commands/** templates/** config/**".split()
CLI_MARK = "argparse.ArgumentParser("
# Constructed rather than written out: a detector matching its own source would
# refuse the very file that carries it.
APPEND_SHELL = ">" + ">"
APPEND_PY = re.compile(r"open\([^)]*[\"']" + "a")


def git(repo, *argv):
    # Read-only and ambient-free: no user or system config, no hooks, no
    # external diff or textconv program, and no index refresh in the live
    # worktree. GIT_ATTR_NOSYSTEM suppresses the SYSTEM attributes file ONLY --
    # it does NOT disable attributes, and an in-tree .gitattributes still
    # applies, which is exactly how a configured filter is reached. That route
    # is closed by refusing the configuration above, not by this environment.
    # A missing git is a refusal, never an assumed-clean tree.
    flags = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-C", str(repo)]
    kw = dict(capture_output=True, text=True, env=GIT_ENV, timeout=120)
    try:
        return subprocess.run(["/usr/bin/git", *flags, *argv], **kw)
    except (OSError, subprocess.SubprocessError) as exc:
        return SimpleNamespace(returncode=127, stdout="", stderr=str(exc))


def covered(path: str, globs) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in globs)


def _is_runtime(path: str) -> bool:
    return path.endswith(".py") or path.endswith(".sh")


def bucket(path: str) -> str:
    # Runtime is a ROLE, not a directory: a helper parked in scripts/ is runtime
    # this rung must carry. Every category is inventoried, never moved out of the
    # count -- config, doc and other lines are reported beside the budgeted two.
    if "/proof/" in path:
        return "proof"
    for ends, name in (((".json", ".yml", ".yaml"), "config"), ((".md", ".txt", ".rst"), "doc")):
        if path.endswith(ends):
            return name
    return "runtime" if _is_runtime(path) else "other"


def count_lines(path: Path) -> int:
    lines = read_text(path).splitlines()
    return sum(1 for ln in lines if ln.strip() and not ln.lstrip().startswith("#"))


def appends(path: Path) -> bool:
    # An append writer is how a bootstrap harness quietly acquires state, and
    # state is what turns a check into something gameable. Both shapes: a shell
    # redirect and a Python append mode.
    text = read_text(path)
    return APPEND_SHELL in text or bool(APPEND_PY.search(text))


# Base against the WORKING TREE plus untracked-but-not-ignored files: a new file
# is the added case, and a rung that looked only at committed history would
# measure nothing until after its own change had already landed.
CHANGED = ("diff", "--name-only", "--no-ext-diff", "--no-textconv")
UNTRACKED = ("ls-files", "--others", "--exclude-standard")


def listing(repo, *argvs):
    # A git failure REFUSES. Failing open here would make the whole budget inert.
    found = set()
    for argv in argvs:
        proc = git(repo, *argv)
        if proc.returncode != 0:
            return None, ("GIT_UNAVAILABLE", f"git {argv[0]}: {proc.stderr.strip()[:80]}")
        found.update(line for line in proc.stdout.splitlines() if line.strip())
    return sorted(found), None


def load_scope(path_text):
    path = Path(path_text)
    if not path.exists():
        return None, ("SCOPE_ABSENT", f"no rung scope at {path}")
    try:
        doc = json.loads(read_text(path))
    except ValueError as exc:
        return None, ("SCOPE_MALFORMED", f"{path} is not readable JSON: {exc}")
    for key, kind in (("limits", dict), ("changed_paths", list), ("removals", list)):
        if not isinstance(doc, dict) or not isinstance(doc.get(key), kind):
            return None, ("SCOPE_MALFORMED", f"{path} lacks a usable {key!r}")
    return doc, None


def reviewed_limits(text: str) -> dict:
    # Injected from OUTSIDE the rung. Raising a ceiling and making the change
    # that needs it in one edit satisfies every intra-scope invariant, so the
    # only witness that can see it is one the rung does not own.
    limits = {}
    for item in text.split(","):
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"{item!r} is not key=value")
        limits[key.strip()] = int(value)
    return limits


def check_base(repo, base, scope):
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        return "BASE_NOT_PINNED", f"base {base!r} is not a 40-hex commit"
    if git(repo, "cat-file", "-e", base + "^{commit}").returncode != 0:
        return "BASE_UNRESOLVABLE", f"base {base[:12]} is not a commit in {repo}"
    if git(repo, "merge-base", "--is-ancestor", base, "HEAD").returncode != 0:
        return "BASE_NOT_ANCESTOR", f"base {base[:12]} is not an ancestor of HEAD"
    # CURRENCY is a different property from VALIDITY: a superseded base puts
    # everything landed on the stacked-on branch since outside the measured diff.
    branch = scope.get("base_branch")
    if not branch:
        return None
    tip = git(repo, "rev-parse", "--verify", "--quiet", branch + "^{commit}").stdout.strip()
    if not tip:
        return "BASE_UNRESOLVABLE", f"base_branch {branch!r} does not resolve in {repo}"
    if tip != base:
        return "BASE_STALE", f"{branch} is now {tip[:12]}, the pinned base is {base[:12]}"
    return None


def cmd_budget(args) -> int:
    repo = Path(args.repo)
    effects = git(
        repo, "config", "--local", "--includes", "--name-only", "--get-regexp", EFFECT_KEYS
    )
    # Exit 1 is the ONLY "no such key". 0 means at least one IS configured, and
    # any other status is a git that could not answer -- never read as clean.
    if effects.returncode == 0:
        return refuse("GIT_EFFECTS_UNSUPPORTED", effects.stdout.split()[:4])
    if effects.returncode != 1:
        return refuse("GIT_UNAVAILABLE", f"git config: {effects.stderr.strip()[:80]}")
    staged = git(repo, "ls-files", "--stage", "-z")
    if staged.returncode != 0:
        return refuse("GIT_UNAVAILABLE", f"git ls-files: {staged.stderr.strip()[:80]}")
    links = [e for e in staged.stdout.split("\0") if e.startswith("160000 ")]
    if links:
        return refuse("SUBMODULE_UNSUPPORTED", f"gitlink entries: {links[:2]}")
    top = git(repo, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip() or ".").resolve() != repo.resolve():
        return refuse("GIT_UNAVAILABLE", f"{repo} is not the root of a git worktree")
    scope, err = load_scope(args.scope)
    if err:
        return refuse(*err)
    limits, globs = scope["limits"], scope["changed_paths"]
    rev = args.reviewed
    above = [f"{k}={limits[k]}" for k in rev if k in limits and limits[k] > rev[k]]
    if above:
        return refuse("LIMIT_ABOVE_REVIEWED", f"the rung raises its own ceiling: {above}")
    err = check_base(repo, args.base, scope)
    if err:
        return refuse(*err)
    changed, err = listing(repo, (*CHANGED, args.base), UNTRACKED)
    if err:
        return refuse(*err)
    if not changed:
        return refuse("EMPTY_CHANGESET", f"nothing changed since {args.base[:12]}")
    touched = [path for path in changed if covered(path, INV4_GLOBS)]
    if touched:
        return refuse("INV4_VIOLATION", f"the rung edits protected infrastructure: {touched[:4]}")
    stray = [path for path in changed if not covered(path, globs)]
    if stray:
        return refuse("OMITTED_SPLIT", f"changed outside every declared glob: {stray[:4]}")
    still = [path for path in scope["removals"] if (repo / path).exists()]
    if still:
        return refuse("ABSENT_REMOVAL", f"promised removals still present: {still}")
    writers = [path for path in changed if bucket(path) == "runtime" and appends(repo / path)]
    if writers:
        return refuse("APPEND_WRITER_ADDED", f"an append writer was added: {writers}")
    measured, surfaces = {}, []
    scoped, err = listing(repo, ("ls-files",), UNTRACKED)
    if err:
        return refuse(*err)
    for rel in (path for path in scoped if covered(path, globs)):
        kind = bucket(rel)
        measured[kind] = measured.get(kind, 0) + count_lines(repo / rel)
        if kind == "runtime" and CLI_MARK in read_text(repo / rel):
            surfaces.append(rel)
    measured["cli_surfaces"] = len(surfaces)
    for kind, key, reason_id in (
        ("runtime", "runtime_lines", "RUNTIME_LINES_OVER_BUDGET"),
        ("proof", "proof_lines", "PROOF_LINES_OVER_BUDGET"),
        ("cli_surfaces", "cli_surfaces", "CLI_SURFACES_OVER_BUDGET"),
    ):
        if measured.get(kind, 0) > limits.get(key, 0):
            return refuse(reason_id, f"{key}={measured.get(kind, 0)} over {limits.get(key, 0)}")
    # Every category is reported, including the two that carry no budget.
    kinds = ("runtime", "proof", "config", "doc", "other")
    inventory = " ".join(f"{k}_lines={measured.get(k, 0)}" for k in kinds)
    head = f"OK base={args.base[:12]} changed={len(changed)} cli_surfaces={len(surfaces)}"
    sys.stdout.write(f"{head} {inventory}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    # ONE argparse surface. A second entry point is a second surface to keep
    # honest forever, and the rung budget counts CLI surfaces.
    parser = argparse.ArgumentParser(prog="trustcheck", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    compare = sub.add_parser("compare", help="compare one oracle record with one receipt")
    for flag in ("--oracle", "--candidate", "--nonce", "--expect-case", "--expect-tool-version"):
        compare.add_argument(flag, required=True)
    compare.add_argument("--expect-dependency-digests", required=True, type=json.loads)
    compare.add_argument("--expect-subject-digest", default="")
    compare.set_defaults(handler=cmd_compare)
    budget = sub.add_parser("budget", help="measure the cumulative rung aggregate")
    for flag in ("--repo", "--base", "--scope"):
        budget.add_argument(flag, required=True)
    budget.add_argument("--reviewed", required=True, type=reviewed_limits)
    budget.set_defaults(handler=cmd_budget)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
