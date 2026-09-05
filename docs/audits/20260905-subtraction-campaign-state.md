# Subtraction campaign — state, plan, and what was learned

**Date**: 2026-09-05 · **Branch**: `fix/searxng-migration-inv8` (**unpushed, no upstream**) · **HEAD**: `71d6646b`
**Status**: 4 commits landed. **Deployed and verified on this machine only** (§2). The Mac
Studio is on its own `master` at `73b90cf8` and still loads all 3,223 deleted lines — that
is a push/merge gap, not a deploy gap. Layer 2 work not started.

This is a handoff document. It exists because the session that produced these commits
was long, and the useful part is not the diffs — it is the measurements, the corrections,
and the reasons behind several deliberate non-changes that look like oversights.

---

## 0. What was asked, and what it turned into

**The ask (2026-09-04 morning)**: delete ~117 dead modules, ~55,000 lines, to make the
system smaller.

**What happened**: every time the "dead" list was checked, it was wrong. The work became
*repair the instrument before trusting it*, then delete the one thing that was provably
safe to delete.

**The instrument was wrong three ways, and the deploy a fourth.** Combined, the
reachability ratchet was wrong about **27 modules** it reported as dead — eleven of them
imported by a settings-registered hook and nine agent definitions.

---

## 1. The four commits

| Commit | What was broken | Result |
|---|---|---|
| `7c3a527e` | Ratchet could not see `importlib.spec_from_file_location` loading, nor repo-root `scripts/*.py` as entry surfaces | 6 live modules were being called dead. Ceiling **132 → 121**. Deleted 5 genuinely dead modules (1,646 lines) |
| `12b47f3b` | Ratchet could not follow package `__init__.py` re-exports | **16 more** live modules called dead. Ceiling **121 → 105** |
| `413a383a` | `deploy_global()` had no `--delete`, so deleted modules survived in `~/.claude/lib` and stayed importable via `sys.path` fallback | `import workflow_tracker` went from resolving to `ModuleNotFoundError`. `target_only` 12 → 6 |
| `64e6db90` | An entire permission subsystem shipped to 5 repos and never executed | **3,223 lines deleted** across 6 modules + 12 test files. Ceiling **105 → 99** |

---

## 2. Current state

### The reachability ratchet

```
live unknown 99 | pin 99 | ceiling 99 | high-water 99
live − pin = []   pin − live = []
```

Three edges now: absolute/stem imports, `importlib` module-loader calls (reads the FIRST
POSITIONAL argument, which by contract IS the module name), and relative re-export through
a package `__init__.py` (walk-time, sourced from the initialiser so conditionality falls
out of the worklist rather than being implemented).

**Its contract is REACHED / UNKNOWN. It never asserts DEAD.** Membership in
`PINNED_UNREACHED_LIBRARY` means "no route this repo can mechanically check", not "safe to
delete". That distinction is load-bearing and its docstring says so.

### The three permission layers

```
LAYER 1  Claude Code native      4 allow + 61 deny rules      LIVE
LAYER 2  unified_pre_tool.py     167 refusals in 2 days       LIVE, works
LAYER 3  the approval subsystem  0 refusals, ever             DELETED in 64e6db90
```

Layer 2 is 9,811 lines / 139 functions / 51 checks behind **one 5-second timeout**, with
**33 `fail_open` events** against those 167 refusals in the same window.

### DEPLOYED LOCALLY 2026-09-05 — and the remote prediction below was WRONG

**Local: done and verified by re-derivation, not by the banner.** `bash scripts/deploy-all.sh`
ran at HEAD `71d6646b`. Probe run before and after, same script, `PYTHONPATH=~/.claude/lib`:

```
BEFORE  auto_approval_engine  IMPORTABLE  /Users/akaszubski/.claude/lib/auto_approval_engine.py   (x6)
        workflow_tracker      ModuleNotFoundError                    <- negative control, already dead
AFTER   all six               ModuleNotFoundError
```

Both arms moved as designed; the negative control stayed put. Files gone from `.claude/lib/`
and `~/.claude/lib/`. This check matters because `413a383a` records the same banner —
`=== ALL VALIDATIONS PASSED ===` — printing while five deleted modules were still importable.

**CORRECTION — the paragraph that stood here predicted the wrong thing, twice.** It said the
six modules would ORPHAN on the Mac Studio and be reported under `deploy_state.py`
`target_only_files` / `dirty`. Neither half happened. They are on the Mac Studio (12 files,
6 modules x `~/.claude/lib` + `~/Dev/autonomous-dev/.claude/lib`) and `target_only` reports
**zero** `lib/` entries for any of the five remote repos, four of which stamped **clean**.

The first reading of that — *the instrument is blind to `lib/`* — is also wrong, and is the
more dangerous of the two because it indicts a working guard. The actual cause:

> **`deploy-all.sh` never ships local source to the remote.** The remote phase ssh's in and
> rsyncs from the *remote's own* `~/Dev/autonomous-dev` checkout (`:518`, `:566` are relative
> to `$PWD` **on the Mac Studio**). That checkout sits on `master` at `73b90cf8` — a commit
> that does not exist in this local repo at all (the Studio carries its own autonomous
> cloud-drain commits). Its source tree still contains all six modules, verified present.

So they are not orphans; they are correctly-deployed live files whose source still declares
them, and `deploy_state` reporting no `target_only` for `lib/` is **the correct answer**.
`--delete` on the remote would have changed nothing here.

The real gap is one level up and is not a deploy defect: branch `fix/searxng-migration-inv8`
has **no upstream and has never been pushed**. Layer 3 is deleted on this machine only. The
Mac Studio still loads all 3,223 lines. Closing that is a push-and-merge decision, not a
deploy re-run — and `deploy-all.sh` will not surface it, because every machine validates
against its own source and both are internally consistent.

**Same defect class as §4**, at deploy scope: *ALL VALIDATIONS PASSED* is a true statement
about what it measured. Nothing in the deploy compares the two machines' source revisions.

---

## 3. The 105 → 99 remaining modules, and why they are NOT a deletion queue

`99` unreached modules, ~47,984 lines. **There is no free tier:**

```
72 connected components (import graph within the pinned set)
   58 singletons        28,160 lines
   14 multi-module      19,824 lines   delete whole or not at all
ZERO components have no test files.  Cheapest is 0.6 test-lines per lib-line.
```

98 of the 105 had test importers, across test files totalling 125,957 lines. Deleting them
is not removing dead weight; it is deleting tested subsystems and their tests.

**The next candidate is `tool_validator.py`** — 985 lines, UNREACHED, zero importers, and
its own security tests fail **ten** behavioural assertions (command substitution, newline
injection, whitelist/blacklist bypass, agent impersonation, TOCTOU symlink race), verified
identical at base. Defects in code that never runs. That is a stronger deletion case than
unreachability alone.

---

## 4. The defect class — the single most useful thing learned

> **A check whose subject is a description of the thing, rather than the thing.**

Counted well past twenty instances in one session. A representative sample:

- A pin that could not see a package because a **shim file stem-shadowed the directory**
- A manifest completeness test comparing **basenames** where paths were needed, and using
  `glob` where `rglob` was needed — 26 files invisible, all 31 tests green
- A bug-fix gate comparing a count from one directory scope against a count from another,
  with the variable **never exported**, so it compared a number to zero forever
- `test_rsync_commands_exclude_extensions` filtering to lines that **already contain**
  `--delete` — a line lacking the flag is invisible to it *by construction*
- Three count-derived assertions (`len(X) - 2`, `X[:5]`, `== 5`) riding on a list being
  shrunk — all stay green, none means what its comment says
- A ratchet pinning a module by **file path AND line number** in a string tuple
- `docs/MCP-SECURITY.md` carrying a banner saying a module was gone and, 210 lines below,
  a paragraph headed **"Note for auditors"** saying it "still exists and implements
  policy-driven filesystem/shell/network validation"
- A collection-error probe reporting 3 errors, all of which were **test parameter IDs
  containing the literal string "3 errors during collection"**
- A stale-claim regex using `[^.]{0,200}` whose positive control returned False on
  known-bad text, because `.py` in the adjacent filename terminated the character class
- A production `--exclude=extensions/` flag existing **only** to satisfy a test that greps
  the script's text and cannot see through `"${DEPLOY_EXCLUDES[@]}"`

### What actually catches these

Not care. In every case the catch came from **re-deriving the measurement**, usually by a
different agent with a different instrument:

- Positive AND negative controls on every probe — *a probe that cannot fail cannot inform*
- Attribution by **SET**, never by count (this repo has a measured ~29-ID flaky band)
- Observing RED before touching a pin, and capturing it verbatim
- Mutation: revert one edge, confirm the moved set is disjoint from the other edge's
- Runtime liveness as a cross-check on static reachability (Google's Sensenmann:
  *"the only real way to know if programs are useful is to check whether they're being run"*)

---

## 5. Research findings worth not re-deriving

**rsync `--delete` semantics** (man page, verified): files matching `--exclude` are absent
from the file list on both sides, so bare `--delete` leaves them alone on the receiver.
`--delete-excluded` removes that protection. `--delete` requires `--recursive` or `--dirs`.
An **empty or misresolved source wipes the target** — hence the non-empty-source pre-flight.
`--max-delete=N` is the standard circuit breaker and is **not transactional**: hitting the
cap leaves the target half-pruned (measured 49 of 60, and 5 of 20).

**A trailing-slash rsync pattern is directory-typed and case-sensitive.** Constructed
proof: a plain FILE named `.claude`, a SYMLINK named `.claude`, and a directory named
`.Claude` are all DELETED by `--exclude='.claude/'`. The real telemetry survives only
because it sits in a real lowercase directory.

**Vacuous pass vs tautological assertion** (formal-verification literature). A check
asserting an import must be **ABSENT** remains a real regression guard — it can still fail
on re-introduction. Only "must be PRESENT" checks become unsatisfiable garbage after their
target is deleted. This is why `deploy-all.sh:621-626`, `scripts/deploy_local.sh:74-79`,
`tests/unit/hooks/test_default_allow_permissions.py:77` and the retained
`pipeline_intent_validator.py:147` entry were all **deliberately kept**. Do not remove them
as dead weight.

**ISO/IEC 27001:2022 control 8.32** makes documentation part of closing a change, not a
follow-up. **NIST SP 800-218 PW.4/PW.7** treats a doc-implementation mismatch as itself a
finding. The required shape is to *state affirmatively what enforces the control now*, not
merely delete the false sentence.

**Deletion propagation**: no mature tool does blanket untracked deletion. Ansible
`synchronize` requires opt-in; Capistrano symlinks releases; Helm and Terraform track
state; `kubectl apply --prune` requires a label selector against last-applied config.
Package managers use ownership records (`dpkg` file lists, Homebrew `INSTALL_RECEIPT.json`).
**Removing a manifest entry stops future installs; it does not remove an installed file** —
documented as a still-open failure mode in Helm (#13279, #12287).

**Google Sensenmann** binds test fate to code fate via strongly-connected components,
explicitly because *"we cannot use test runs as a liveness signal ... this would keep dead
code around forever."* Meta's SCARF does the same coupled deletion.

---

## 6. Filed and unfixed (20)

Ranked by what I would fix first.

```
 1  implement.md inline snippets bypass resolve_session_id()   ROOT-CAUSED, see below
 2  Bash(*git *--force*) denies `git worktree remove --force`  forces rm -rf in the pipeline
 3  tool_validator.py: 985 unreached lines, 10 failing security assertions
 4  README.md:116 lists deleted batch_retry_manager.py as live  flagged by 3 validators
 5  unified_pre_tool.py:1818 returns allow on ImportError of a nonexistent module (A01)
 6  activity log truncates every command at 200 chars           blinds every audit
 7  activity log 4.25x duplicated + polluted by hook test fixtures
 8  one untracked file blackens the whole pytest baseline       test_issue_1570_*
 9  agent template forces "Navigation: grep (serena unavailable)" when serena WAS available
10  duration_ms inflated 44-80x for background-collected agents
11  validator artifacts must be VERBATIM captures, not composed prose
12  manifest fetched over network with no signature or hash check
13  three sibling pre-commit validators still fail open on deletion
14  the top-level orphan manifest: 185 entries pointing at nonexistent files
15  _relative_import_targets stats candidates before the caller's containment check
16  .claude/ exclude pattern is directory-typed and case-sensitive
17  no audit trail of which files a --delete run removed (--itemize-changes)
18  --max-delete=50 sits above config/'s real count of 16
19  recursive lib/ scan will ship a future test_*.py
20  docs/TOOL-AUTO-APPROVAL.md body below the banner (partially fixed in 64e6db90)
```

### #1 in detail — root-caused, worth fixing first

Every coordinator snippet in `commands/implement.md` resolves the session id inline:

```python
sid = os.environ.get('CLAUDE_SESSION_ID','').strip() or 'unknown'
```

No fallback chain. `pipeline_completion_state.py:327-395` already ships a hardened
`resolve_session_id()` built for exactly this failure (#779/#904/#1093). When one Bash
subprocess loses the env var, `sid` becomes the literal string `"unknown"` and every later
call addresses a **different state file**:

```
/tmp/pipeline_agent_completions_0218e4c4.json   sha256(real session_id)[:8]
/tmp/pipeline_agent_completions_b23a6a84.json   sha256("unknown")[:8]
```

This caused **four apparent "completion state losses"** in one run, each requiring manual
re-recording. The state was never lost — the coordinator was reading the wrong file. Also:
`record_agent_completion` is never called with `run_id=`, so all runs in a session share
one file, filtered only by `current_run_id` stamps.

---

## 7. What is next

### Immediately

1. **`bash scripts/deploy-all.sh`** — makes all four commits real on disk. Clears the six
   modules from `.claude/lib/` and `~/.claude/lib/`. The remote will orphan them (see §2);
   verify via `deploy_state.py` `target_only` per `docs/RUNBOOK.md:327`.

### Then — Layer 2, in this order

**STRENGTHEN before SIMPLIFY.** The measured target is **33 fail-opens against 167
refusals** — one in six uncertain cases resolves to "yes". A timeout currently means
*permit*; there is no state for "I could not tell you". The tri-state landed in
`bugfix_detector.py` (`BLOCK` / `PASS` / `UNMEASURED` / `ERROR`, where ERROR fails CLOSED
and UNMEASURED fails open by design) is the shape to copy.

**Do not split the file first.** From `docs/audits/20260904-structural-picture.md`:
*"A 9,810-line file that fails open is one failure mode; five 2,000-line files that each
fail open independently is five."*

Fold in #1 (session-id) and #2 (`git --force`) — both are small and both actively disrupt
the pipeline.

### Later

The 99 unreached modules, via the **component** analysis in §3 — whole components or none,
never individual modules. And the two live permission layers overlap; consolidating them is
a real question but not this month's.

---

## 8. Standing constraints that must survive a context clear

**Eight files must never be modified or staged** (dirty from unrelated work):
`.gitignore`, `PROJECT.md`, `README.md`, `docs/audits/inventory-2026-09-01.json`,
`docs/research/README.md`, `plugins/autonomous-dev/docs/TROUBLESHOOTING.md`,
`scripts/audit_inventory.py`, `.claude/settings.json`. **Never `git add -A`.**

**Repo-wide pytest aborts at collection** on the untracked
`tests/regression/test_issue_1570_multi_operand_write_targets.py`, which parametrizes
`tool_intent._BASH_COMMAND_PREFIXES` — a symbol that has never existed. Use
`--ignore=` for wide runs. **Do not fix, stage, or delete it** without deciding
deliberately; it has never passed and was never committed.

`lib/*.py`, `hooks/*.py`, `agents/*.md`, `commands/*.md`, `skills/*/SKILL.md` and the
deployment manifests require `/implement`. Never route around a hook block — surface it.

**Two git worktrees are registered** from validator probes and need `git worktree remove`.
