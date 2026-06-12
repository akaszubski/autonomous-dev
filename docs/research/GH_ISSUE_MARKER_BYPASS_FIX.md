---
topic: gh_issue_filing_allowance_root_cause
created: 2026-04-01
updated: 2026-06-12
supersedes: ["#987", "#1095", "#1199"]
related: ["#1203", "#1206"]
sources: []
---

# gh issue filing allowance — root cause and four-defect fix (#1203)

This document supersedes the earlier marker-bypass stub. It consolidates
the four distinct defects that caused `gh issue create` to be blocked
despite whitelist membership, and maps the user-visible evidence onto the
hook-internal stages where the failure originates.

## Symptom

`/plan`, `/improve`, `/create-issue --quick`, `/plan-to-issues`,
`/refactor --issues`, and `/retrospective --auto-file` all reported
filing GitHub issues during a session, but the hook denied the
`gh issue create` Bash call with:

> BLOCKED: Cannot create GitHub issues with 'gh issue create' directly.

The whitelist (`GH_ISSUE_COMMANDS` in `unified_pre_tool.py`) listed
five of these six commands explicitly and the hook had an allow-through
specifically for "an issue-creating command is active." So why block?

## Four defects (defects ordered by primacy)

### Defect 1 (PRIMARY) — TOCTOU-inverse: PreToolUse evaluates each Bash call BEFORE it runs

The Claude Code PreToolUse hook is fired with the FULL command string of
the Bash invocation BEFORE the command executes. The command markdowns
(plan.md, improve.md, plan-to-issues.md, refactor.md, retrospective.md,
create-issue.md) bundled "write `/tmp/autonomous_dev_cmd_context.json`
then run `gh issue create`" into a SINGLE Bash invocation. At hook
evaluation time, the context file did NOT yet exist on disk (Bash has
not started). `_is_issue_command_active` (allow-through #4, lines
~1417-1451 in unified_pre_tool.py) read the absent file and fell closed
(returns False). Result: every bundled invocation was blocked.

This is the inverse of a TOCTOU race: instead of "check then use" where
the resource may change between check and use, this is "use then write"
where the hook checks for a side effect that the same call is supposed
to produce. The hook's auto-write helper `_maybe_write_issue_context`
(line ~4509) covers the Skill-tool invocation path only — when the
user types `/create-issue ...` Claude Code fires the Skill tool first,
the hook writes the context, and the subsequent Bash call (separate
invocation) sees the context. When the markdown bundles the write into
the Bash call itself, the Skill path never fires.

**Fix**: split context write from `gh issue create` into separate Bash
tool calls in all six command markdowns. Add a FORBIDDEN note in each
markdown so future edits cannot re-bundle.

### Defect 2 — `/plan` was doubly broken

Two independent bugs:
(a) `'plan'` was NOT in `GH_ISSUE_COMMANDS` (line 513). plan.md STEP 6
files issues by design when there are >=2 independent work items (per
its own HARD GATE), but the hook's `_is_issue_command_active` rejected
the context (line 1441-1442) because `'plan'` was not a recognized
command name.
(b) plan.md wrote `'command': 'plan'` into the context, which the hook
auto-writer `_maybe_write_issue_context` rejects for unknown skill
names.

**Fix**: add `'plan'` to `GH_ISSUE_COMMANDS`. This is the minimal,
durable resolution — `/plan` is a first-class issue-filing entry point
in the project's intended workflow, and re-routing it through a
different mechanism is more disruptive than whitelisting.

### Defect 3 — bypass-detector content false-positive on backticks in `--body`

`_contains_gh_issue_create_bypass` (lines 2591-2658) scanned the RAW
command string for backtick command substitution (`` `gh issue create...` ``).
The intent is to catch shell bypass forms like `RESULT=` `gh issue create...` ``,
but the regex matched ANY backtick-quoted substring that contained the
literal `gh issue create` — including prose inside a `--body` argument
value of a benign `gh issue comment` call. Live-confirmed false positive
this session: a `gh issue comment` whose body contained backtick-quoted
diagnostic prose was blocked.

There is an in-file precedent for argv-aware shell parsing:
`_detect_git_bypass` (~line 624) uses `shlex.split`.

**Fix**: tokenize via `shlex.split`, strip the VALUE token that follows
`--body` / `--title` / `--body-file` / `-m` / `--message` (and the
attached `--body=VALUE` form), rejoin, then run the original regex on
the reconstructed command. On `shlex.ValueError` (malformed shell), fall
back to the raw-regex behavior so we never weaken blocking on garbled
input.

### Defect 4 — dead marker READ allow-through

Allow-through #3 (lines 2821-2828 pre-fix) read
`/tmp/autonomous_dev_gh_issue_allowed.marker` and granted a 1-hour pass
when the file existed and was fresh. The WRITE of that marker has been
blocked by `_detect_gh_issue_marker_creation` since #627. Nothing in the
current codebase writes the marker. The READ allow-through is dead code
that adds confusion and a phantom escape hatch.

**Fix**: delete the READ allow-through. Keep `GH_ISSUE_MARKER_PATH` and
`_detect_gh_issue_marker_creation` as defense-in-depth (a successful
WRITE by a malicious actor would not grant allow anymore — the READ is
gone). Add regression tests that (a) marker presence has no effect on
allow, (b) marker WRITE is still blocked.

## Evidence-to-stage mapping

| User-visible symptom | Hook stage | Defect # |
|---|---|---|
| `/plan` STEP 6 blocked with "BLOCKED: Cannot create GitHub issues..." | `_is_issue_command_active` rejects `command:'plan'` | 2 (whitelist) |
| `/plan` STEP 6 blocked even after Step 1 wrote context | PreToolUse evaluates bundled Bash call BEFORE context write executes | 1 (TOCTOU-inverse) |
| `/improve`, `/refactor`, `/retrospective`, `/plan-to-issues` blocked | Same — bundled context write + `gh issue create` in one Bash call | 1 |
| `gh issue comment 1203 ... --body "...backticks..."` blocked | `_contains_gh_issue_create_bypass` backtick regex matched body prose | 3 |
| (case-1 evidence: 4 creates passed then 5th blocked, no Skill invocation) | Concurrent session's `/tmp` pipeline sentinel went stale mid-session | (out of scope — #1206) |

## Out of scope

A concurrent-session `/tmp` state leak (a parallel session's pipeline
sentinel kept `_is_pipeline_active()` fresh for an unrelated session,
then went stale and unblocked-blocked behavior shifted within a single
user session) was diagnosed but is OUT of scope for #1203's hook-code
fix. Tracked as **#1206**.

## Superseded issues

- **#987**: prior partial diagnosis of marker bypass — superseded by the
  comprehensive root cause documented here.
- **#1095**: prior partial fix attempt for command-context allow-through
  that did not address the bundling pattern in the markdowns — superseded.
- **#1199**: prior re-report of the same allow-through symptom — superseded.

## Defense-in-depth invariants preserved

- The marker file WRITE blocker (`_detect_gh_issue_marker_creation`) is
  retained — direct creation of the marker file remains blocked.
- The four other allow-throughs (pipeline active, authorized agent,
  issue-command-active via context file, plan-exit-gate) are unchanged.
- True bypass forms (subprocess wrappers, `sh -c`, `bash -c`, backtick
  / `$()` at command position) remain blocked. The Change C false-positive
  fix only relaxes the detector on body/title/message argument VALUES.
- The Change A whitelist addition (`'plan'`) does NOT lower any security
  invariant: the `_is_issue_command_active` allow-through still requires
  a fresh on-disk context file written by a prior tool call. The
  prior-call ordering contract is the security boundary; the whitelist
  is a recognition rule, not a permission grant.

## Sources

- `plugins/autonomous-dev/hooks/unified_pre_tool.py` (constants ~line
  507-513; `_is_issue_command_active` ~line 1417; `_detect_gh_issue_create`
  ~line 2846; `_contains_gh_issue_create_bypass` ~line 2600;
  `_maybe_write_issue_context` ~line 4509)
- `plugins/autonomous-dev/commands/{plan,improve,plan-to-issues,refactor,retrospective,create-issue}.md`
- `tests/unit/hooks/test_gh_issue_create_runtime.py` (#1203 runtime locks)
- `tests/unit/hooks/test_gh_issue_create_block.py` (#1203 false-positive lock)
- `tests/regression/test_gh_issue_create_regression.py` (#1203 marker dead-code lock)
