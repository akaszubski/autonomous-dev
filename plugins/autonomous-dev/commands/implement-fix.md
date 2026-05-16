---
name: implement-fix
description: Minimal pipeline for test-fixing tasks
version: 1.0.0
user-invocable: false
allowed-tools: [Agent, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch]
---

# FIX MODE

> The key words "MUST", "MUST NOT", "SHOULD", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

Minimal pipeline (5 steps, 4 agents minimum) for test-fixing tasks.
Invoked via `/implement --fix "description"`. Skips research and planning
since the problem is already known (failing tests).

## Coordinator Role — HARD GATE

The coordinator is a **dispatcher**, not a substitute for specialist agents. These constraints apply globally — before any step definitions — and MUST NOT be violated regardless of circumstances.

### Agent Management

The coordinator dispatches work to specialists; it MUST NOT do the work itself.

**FORBIDDEN — You MUST NOT do any of the following**:
- ❌ You MUST NOT write, edit, or modify any project files directly — ALL file modifications MUST go through specialist agents (implementer, doc-master)
- ❌ You MUST NOT do an agent's work when the agent crashes — RETRY once, then BLOCK with a clear error message; never substitute coordinator judgment for agent execution
- ❌ You MUST NOT skip any STEP in the pipeline
- ❌ You MUST NOT summarize agent output instead of passing full results to the next agent — verbatim output is required

### Pipeline Integrity

Step ordering and post-completion behavior are strictly constrained.

**FORBIDDEN — You MUST NOT do any of the following**:
- ❌ You MUST NOT parallelize agents from different pipeline phases (e.g., running F3 and F4 concurrently)
- ❌ You MUST NOT clean up pipeline state before STEP F5 launches
- ❌ You MUST NOT perform any file edits after agents complete — the coordinator's only permitted post-agent actions are: outputting the final summary, git operations (add, commit, push), and launching STEP F5

### Output Fidelity

The coordinator MUST transmit agent outputs intact.

**FORBIDDEN — You MUST NOT do any of the following**:
- ❌ You MUST NOT paraphrase or condense agent output when passing to the next stage
- ❌ You MUST NOT pass fewer than 50% of the implementer output words to the reviewer — if context is a constraint, include the implementer's file change list and test results in full before trimming any prose sections

## Fix Mode Progress Protocol

Output structured progress at each step. Same format conventions as the full pipeline protocol.

**Step Banner**: `STEP FN/5 — Step Name` with agent info where applicable.
**Timing**: Capture `FIX_START=$(date +%s)` at pipeline start. Capture per-step timing.
**Gate Results**: `GATE: name — PASS/BLOCKED`
**Final Summary** (after STEP F4, before STEP F5 launches in background):
```
========================================
FIX COMPLETE
========================================
Step  Description         Agent(s)                           Time    Status
----  ------------------  ---------------------------------  ------  ------
F1    Alignment           —                                  2s      PASS
F1.5  Pre-staged check    —                                  1s      PASS
F2    Test context        —                                  5s      done
F3    Implementation      implementer (Opus)                 2:30    done
F3    Test gate           —                                  8s      PASS
F4    Review + docs       reviewer, doc-master               45s     done
F5    CI analysis         continuous-improvement-analyst     bg      launched
========================================
Total: 3:31 | Tests: N passed, M failed | Files changed: N
========================================
```

## Implementation

## Steps F1-F2: Alignment and Test Context

### STEP F1: Validate PROJECT.md Alignment

**Progress**: Output step banner (STEP F1/5 — Alignment). Capture FIX_START. Output gate result.

Read `.claude/PROJECT.md`. If missing: BLOCK ("Run `/setup` or `/align --retrofit`").
Verify the fix is within project scope. If misaligned: BLOCK with reason.

This is the same alignment gate as the full pipeline STEP 1.

#### Prompt Baseline Reset (Defensive — Issue #1088 F3)

Before initializing pipeline state, clear any stale `prompt_baselines.json` from a prior session. /fix mode by design dispatches shorter, focused prompts; stale baselines from prior runs frequently exceed the 20% shrinkage threshold against fresh fix-mode prompts and produce false-positive integrity blocks.

```python
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from prompt_integrity import clear_prompt_baselines
clear_prompt_baselines()
print('Prompt baselines cleared for fix mode')
```

Note: This step becomes unnecessary once #1082 Phase 1a (per-issue baseline split) lands. Until then, /fix mode SHOULD clear baselines defensively at pipeline start.

#### Pipeline State Initialization

After alignment validation passes, initialize the pipeline state file so that hook enforcement (prompt integrity, pipeline ordering) is active during fix mode:

```bash
python3 -c "
import json, os, time
state = {'mode': 'fix', 'explicitly_invoked': True, 'start_time': int(time.time())}
with open(os.environ.get('PIPELINE_STATE_FILE', '/tmp/implement_pipeline_state.json'), 'w') as f:
    json.dump(state, f)
print('Pipeline state initialized for fix mode')
"
```

This ensures prompt integrity enforcement (Layer 5) can detect an active pipeline and apply baseline shrinkage checks in addition to the minimum word count gate.

### STEP F1.5: Pre-Staged Files Check — HARD GATE

**Progress**: Output step banner (STEP F1.5/5 — Pre-Staged Check). Output gate result.

```bash
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)
if [ -n "$STAGED_FILES" ]; then
  echo "BLOCKED: Pre-staged files detected"
  echo "$STAGED_FILES"
fi
```

If `STAGED_FILES` is non-empty: **BLOCK** the pipeline. Display:

```
BLOCKED — Pre-staged files detected.

The following files are already staged from a previous session:
[list files]

These would be bundled into this fix's commit, creating misleading git history.

Options:
A) Unstage: git reset HEAD
B) Commit first: git commit -m "wip: staged changes from previous session"
C) Review: git diff --cached
```

Do NOT proceed to STEP F2 until the staging area is clean.

**FORBIDDEN**:
- ❌ Proceeding with pre-staged files present
- ❌ Silently unstaging files without user confirmation
- ❌ Treating pre-staged files as part of the current fix

### STEP F2: Gather Test Context

**Progress**: Output step banner (STEP F2/5 — Test Context). Output test failure summary after.

Run the test suite to capture current failures:

```bash
pytest --tb=short -q 2>&1 | head -200
```

Parse the output to identify:
- Number of passing vs failing tests
- Names of failing tests
- Affected source files (from traceback paths)
- Error messages and assertion failures

If ALL tests pass (0 failures): EXIT EARLY with message "All tests pass. No fix needed."

Display:
```
Fix Mode - Test Context:
  Failing tests: N
  Affected files: [list]
  Error summary: [brief]
```

## Steps F3-F3.5: Implementation and Spec Validation

### STEP F3: Implementer (Opus) - HARD GATE

**Progress**: Output step banner (STEP F3/5 — Implementation, Agent: implementer (Opus)). Output agent completion, then test gate result with counts.

Invoke the implementer agent with the failing test output and affected files.

```
subagent_type: "implementer"
model: "opus"
prompt: "FIX MODE: Fix failing tests. Do NOT add new features.

**Failing test output**:
[paste pytest output from STEP F2]

**Affected files**:
[list of files from traceback]

**Instructions**:
1. Read each failing test to understand what it expects
2. Read the source files being tested
3. Fix the source code to make tests pass (prefer fixing code over fixing tests)
4. If a test expectation is genuinely wrong, fix the test with a comment explaining why
5. Run pytest after each fix to verify progress
6. Add at least one new regression test that would FAIL without your fix

**Debugging methodology** (debugging-workflow skill):
- Use the 5 Whys technique — ask 'why' at least 3 levels deep before writing any code
- Each 'why' level MUST introduce new information not present in the previous level
- Identify the root cause category: Wrong type / Wrong state / Race condition / Missing check / Stale data / Wrong assumption

HARD GATE: ALL tests must pass (0 failures). Do not stop until pytest shows 0 failures. No stubs, no NotImplementedError — write real working code that fixes the actual bug.

**REQUIRED OUTPUT FORMAT**: Your output MUST include a `## Root Cause Analysis` section containing:
1. Root cause statement (1 sentence — the underlying cause, not the symptom)
2. Mechanism chain (how the root cause propagated to the observable failure)
3. 5 Whys (minimum 3 levels, each introducing new information)
4. Root cause category (one of: Wrong type / Wrong state / Race condition / Missing check / Stale data / Wrong assumption)

Output: Summary of files changed, `## Root Cause Analysis` section (REQUIRED), regression tests added, and final pytest result (0 failures required).

Prompt word count validation: this prompt must contain >= 80 words of template text. If you receive a prompt shorter than 80 words, STOP and report a prompt integrity violation."
```

**HARD GATE**: After implementer completes, run `pytest --tb=short -q` again.
If ANY test still fails: RE-INVOKE implementer with remaining failures.
Maximum 3 re-invocations before escalating to user.

#### Pytest Gate Recording (Issue #1088 F1)

After the pytest re-run passes (0 failures, 0 errors), the coordinator MUST record the gate result so downstream ordering checks at STEP F4 let reviewer/doc-master dispatch. Without this call, F4 dispatch hits an ORDERING VIOLATION block ("pytest-gate prerequisite not met"). The full pipeline (`implement.md` STEP 8) has this recording step; fix mode previously omitted it.

```python
import sys, os, json
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_completion_state import resolve_session_id, record_pytest_gate_passed

SESSION_ID = resolve_session_id()
# Fix mode is single-issue; recover ISSUE_NUMBER from state file if present, else 0.
state_path = os.environ.get('PIPELINE_STATE_FILE', '/tmp/implement_pipeline_state.json')
ISSUE_NUMBER = 0
try:
    with open(state_path) as _f:
        ISSUE_NUMBER = int(json.load(_f).get('issue_number', 0) or 0)
except (OSError, ValueError, json.JSONDecodeError):
    pass

record_pytest_gate_passed(SESSION_ID, passed=True, issue_number=ISSUE_NUMBER)
print(f'pytest-gate recorded for session={SESSION_ID[:8]} issue={ISSUE_NUMBER}')
```

**FORBIDDEN**:
- ❌ Skipping the `record_pytest_gate_passed()` call — downstream ordering gates will block STEP F4 dispatch.
- ❌ Calling `record_pytest_gate_passed(passed=True)` when pytest still has failures.

### HARD GATE: Root Cause Analysis Output Gate

After the implementer completes STEP F3, inspect the implementer output for the presence of `## Root Cause Analysis`.

**Check**: Does the implementer output contain the literal string `## Root Cause Analysis`?

**If absent on first completion**: Re-invoke the implementer once with the following addition to the prompt:
```
HARD GATE VIOLATION: Your output is missing the required `## Root Cause Analysis` section.
You MUST add it now. The section must include:
1. Root cause statement (1 sentence)
2. Mechanism chain (A → B → C → failure)
3. 5 Whys (minimum 3 levels, each introducing new information)
4. Root cause category (Wrong type / Wrong state / Race condition / Missing check / Stale data / Wrong assumption)
Output the complete Root Cause Analysis section and nothing else.
```

**If still absent after re-invocation**: BLOCK the pipeline with:
```
BLOCKED — Root Cause Analysis missing after retry.
The implementer did not produce the required ## Root Cause Analysis section.
This section is required in fix mode to ensure the root cause is identified,
not just the symptom. Re-invoke /implement --fix with a more specific bug description.
```

**FORBIDDEN**:
- ❌ Proceeding to STEP F3.5 without verifying `## Root Cause Analysis` is present in the output
- ❌ Treating a symptom description as a root cause analysis
- ❌ Skipping this gate when the implementer output is long (length does not exempt the gate)

### HARD GATE: Regression Test Requirement

If fixing a bug, at least one NEW test must be added that would FAIL without the fix. This ensures the bug never returns.

**Verification**: Compare test count from STEP F2 (before fix) vs after STEP F3 (after fix). If `after_count <= before_count`, BLOCK with message: "Bug fix requires at least one new regression test that reproduces the bug. Add a test that fails without your fix and passes with it."

**Exception**: If the bug was caught BY an existing failing test (i.e., the test that originally failed IS the regression test), this gate passes automatically. Document which existing test covers the regression.

**FORBIDDEN**:
- Fixing a bug without a test that proves it was broken
- Claiming "the fix is obvious and doesn't need a test"
- Adding a test that passes both with and without the fix (that's not a regression test)

### STEP F3.5: Spec-Blind Validation — HARD GATE

**Progress**: Output step banner (STEP F3.5/5 — Spec-Blind Validation, Agent: spec-validator (Opus)). Output verdict after.

Same context boundary as STEP 8.5 in the full pipeline. Pass ONLY:
- Bug description / fix description (from user input)
- Changed file paths (from `git diff --name-only`)
- PROJECT.md scope sections

**FORBIDDEN**: Passing implementer output, code diffs, reviewer feedback, or any implementation details to the spec-validator.

**Agent**(subagent_type="spec-validator", model="opus") — Pass bug description + changed file paths ONLY.

Parse verdict: `SPEC-VALIDATOR-VERDICT: PASS` or `SPEC-VALIDATOR-VERDICT: FAIL`. On FAIL, re-invoke implementer with failing test names only (max 2 cycles). Block if still failing after 2 cycles.

## Step F4: Review, Security, and Docs

### STEP F4: Reviewer + Doc-master (parallel)

**Progress**: Output step banner (STEP F4/5 — Review + Docs, Agents: reviewer (Sonnet), doc-master (Sonnet)). Output each agent completion. Then output Final Summary table.

#### Security-Sensitivity Detection — HARD GATE

Before invoking any STEP F4 agents, run deterministic security-sensitivity detection on the changed file list:

```bash
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null)
```

Match each file path against security-sensitive patterns (substring match, case-insensitive). Patterns are grouped by domain — false positives are cheap (an extra security review), false negatives are expensive (missed security regression):

**Infrastructure**: `hooks/`, `lib/auto_approval_engine`, `lib/tool_validator`, `config/auto_approve_policy`, `lib/security`

**Auth/access**: `auth`, `crypto`, `permission`, `session`, `token`, `secret`, `credential`, `password`, `oauth`, `sso`, `jwt`, `rbac`

**Financial**: `trading`, `payment`, `billing`, `financial`, `transaction`, `wallet`

**Schema/environment**: `migration`, `alembic`, `.env`

**Exclusion rule**: File paths starting with `tests/` are excluded — test files that reference security topics do not themselves pose a security risk.

Output the detection result before proceeding:
```
Security-auditor: SKIP (no security-sensitive files)
```
or:
```
Security-auditor: REQUIRED (matched: [list of matched files and patterns])
```

When detection outputs `REQUIRED`, the security-auditor invocation is **mandatory** — it MUST be added to the parallel agent invocations in this step.

**FORBIDDEN**:
- ❌ Skipping security-auditor when detection flagged one or more files as REQUIRED
- ❌ Running the pattern match only against file names — match against full relative paths
- ❌ Proceeding without outputting the detection result

#### HARD GATE: Verbatim Implementer Output

You MUST pass the FULL implementer output from STEP F3 to the reviewer and security-auditor agents — do NOT summarize, condense, or paraphrase. The implementer output contains file paths, diff context, and test results that the reviewer needs verbatim to perform a thorough review. Truncating or summarizing this output is the root cause of prompt word count violations.

#### HARD GATE: Prompt Integrity Validation

Before invoking the reviewer or security-auditor agent, validate the constructed prompt word count:

1. Reviewer prompt MUST be >= 80 words
2. Security-auditor prompt (if invoked) MUST be >= 80 words
3. If below minimum, reconstruct prompt by including more context from the implementer output — add the full list of changed files, the complete test results, and the diff summary

The library function `validate_prompt_word_count(agent_type, prompt)` from `plugins/autonomous-dev/lib/prompt_integrity.py` provides this validation. Call it and check `result.passed` before invoking each critical agent.

**FORBIDDEN**:
- Sending a reviewer or security-auditor prompt with fewer than 80 words
- Summarizing or condensing the implementer output before passing it to the reviewer
- Omitting file paths, test results, or diff context from the reviewer prompt
- Invoking security-auditor with only the skeleton prompt template without the actual verbatim implementer output pasted in

Invoke agents in PARALLEL. When security-auditor is REQUIRED, invoke all three simultaneously. When security-auditor is SKIP, invoke two (reviewer + doc-master):

1. **Reviewer** (Sonnet): Review the fix for correctness, edge cases, and regressions.

```
subagent_type: "reviewer"
model: "sonnet"
prompt: "FIX MODE REVIEW: You are reviewing a test fix for correctness, edge cases, and potential regressions. Your review MUST be thorough and MUST cover all changed files.

**Review checklist — evaluate each item explicitly**:
1. Read every changed file listed below and verify the fix is correct
2. Identify edge cases that the fix may not handle
3. Verify that no regressions were introduced by the changes
4. Confirm that new regression tests exist and would fail without the fix
5. Verify that error handling is preserved and not weakened by the fix
6. Verify test assertions are meaningful and not trivially passing

**Implementer output (VERBATIM — do not skip any section)**:
[paste FULL implementer output from STEP F3 here — do NOT summarize]

**Changed files for review**:
[list all files modified in STEP F3]

**Test results after fix**:
[paste final pytest output from STEP F3]

Report BLOCKING findings (must fix before merge) and WARNING findings (improvements for later) separately."
```

2. **Doc-master** (Sonnet): Update any affected documentation.

```
subagent_type: "doc-master"
model: "sonnet"
prompt: "FIX MODE DOCUMENTATION REVIEW: You are reviewing a bug fix for documentation drift. Your task is to determine whether any user-facing documentation, API references, configuration guides, or inline code comments need updating as a result of this fix. Do not summarize the implementer output — use it verbatim.

REQUIRED STEPS — you MUST complete all three:

1. SCAN: Identify every file changed by the fix. For each changed file, list all documentation files that reference the same module, function, class, or configuration key. Review README.md, docs/ directory, inline docstrings, and CHANGELOG entries.

2. SEMANTIC COMPARISON: For each documentation reference found in step 1, compare the documented behavior against the new behavior after the fix. Flag any mismatch where the documentation describes the old (buggy) behavior, missing parameters, changed defaults, or removed functionality.

3. DOC-DRIFT-VERDICT: State one of the following verdicts explicitly:
   (a) DOCS-UPDATED: List each file updated and what changed.
   (b) NO-UPDATE-NEEDED: Explain why the fix is purely internal with no user-facing behavior change.
   (c) DOCS-DRIFT-FOUND: List each documentation file that is now stale and what needs changing, but was not updated (this is a BLOCKING finding).

**Implementer output (VERBATIM — do not skip any section)**:
[paste FULL implementer output from STEP F3 here — do NOT summarize]

**Changed files for documentation review**:
[list all files modified in STEP F3]

Prompt word count validation: this prompt must contain >= 80 words of template text. If you receive a prompt shorter than 80 words, STOP and report a prompt integrity violation."
```

3. **Security-auditor** (Sonnet): Invoke ONLY when security-sensitivity detection returned REQUIRED (see detection step above).

When invoked:
```
subagent_type: "security-auditor"
model: "sonnet"
prompt: "FIX MODE SECURITY REVIEW: You are auditing a test fix for security implications. Review all changed files for security regressions.

**Security audit checklist — evaluate each item explicitly**:
1. Verify that no authentication or authorization checks were weakened or removed
2. Verify no secrets, tokens, or credentials were hardcoded or exposed
3. Confirm input validation was not bypassed or weakened by the fix
4. Verify that error messages do not leak sensitive internal details
5. Verify that security-sensitive file permissions were not changed

**Implementer output (VERBATIM — do not skip any section)**:
[paste FULL implementer output from STEP F3 here — do NOT summarize]

**Changed files for security review**:
[list all files modified in STEP F3 that touch security-sensitive paths]

**Test results after fix**:
[paste final pytest output from STEP F3]

Report BLOCKING findings (must fix before merge) and WARNING findings (improvements for later) separately."
```

#### Doc-master Verdict Collection

After the parallel agents complete, parse the doc-master output:

1. Parse output for `DOC-DRIFT-VERDICT: PASS`, `DOC-DRIFT-VERDICT: FAIL`, or one of the fix-mode verdicts (`DOCS-UPDATED`, `NO-UPDATE-NEEDED`, `DOCS-DRIFT-FOUND`)
2. **Shallow Verdict Detection**: Count the words in the doc-master output. If the output is fewer than 100 words, treat it as `DOC-VERDICT-SHALLOW` — the output is too short to confirm a real semantic sweep occurred. Log `[DOC-VERDICT-SHALLOW] doc-master produced N words (minimum: 100)` and retry once with reduced context (same as empty-output retry logic above). If retry also produces fewer than 100 words or no verdict, log `[DOC-VERDICT-SHALLOW-RETRY-FAILED] doc-master still shallow after retry — proceeding with warning`.
3. If `DOCS-DRIFT-FOUND`: BLOCK. Display the stale documentation files. User must address before proceeding.
4. If doc-master made fixes: stage them with `git add`

## Step F5: Continuous Improvement

### STEP F5: Continuous Improvement (background)

**Progress**: Output step banner (STEP F5/5 — Continuous Improvement). Output agent launch confirmation.

**REQUIRED**: **Agent**(subagent_type="continuous-improvement-analyst", model="sonnet", run_in_background=true) — Examines session logs for bypasses, test drift, and fix pipeline completeness.

**FORBIDDEN** — You MUST NOT do any of the following (violations = pipeline failure):
- ❌ You MUST NOT skip STEP F5 for any reason (time pressure, context limits, "already reported")
- ❌ You MUST NOT clean up pipeline state before launching the analyst
- ❌ You MUST NOT inline the analysis yourself instead of invoking the agent

After launching the analyst and confirming the agent task ID is valid, cleanup: `rm -f "${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}"`

**FORBIDDEN** (Issue #559): Cleaning up pipeline state before confirming the STEP F5 analyst agent launch succeeded. The analyst reads pipeline state — cleanup before launch loses context.

---

## Agent Count

- **Minimum**: 4 agents (implementer, reviewer, doc-master, continuous-improvement-analyst)
- **Maximum**: 5 agents (+ security-auditor if security-sensitive files changed)

## Mutual Exclusivity

`--fix` is mutually exclusive with:
- `--batch` (batch file mode)
- `--issues` (batch issues mode)
- `--resume` (resume mode)

If combined with any of these, BLOCK with error message.
