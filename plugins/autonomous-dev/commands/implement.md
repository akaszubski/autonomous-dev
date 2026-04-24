---
name: implement
description: "Smart code implementation with full pipeline and batch modes"
argument-hint: "<feature> | --batch <file> | --issues <nums> | --resume <id>"
allowed-tools: [Agent, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch]
user-invocable: true
---

# /implement — Thin Coordinator (Issue #444)

> The key words "MUST", "MUST NOT", "SHOULD", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

**You (Claude) are the coordinator.** Delegate specialist work to agents via the Agent tool. Each agent runs in isolated context — pass outputs from prior stages explicitly.

| Mode | Flag | Description |
|------|------|-------------|
| **Full Pipeline** | (default) | Acceptance-first: Research → Plan → Acceptance Tests → Implement + Unit Tests → Review → Security → Docs |
| **Light** | `--light` | Fast pipeline: Align → Plan → Implement → Test → Docs → CI Analysis (4 agents, no research/security) |
| **TDD-First** | `--tdd-first` | Research → Plan → Unit Tests → Implement → Review → Security → Docs |
| **Fix** | `--fix` | Minimal pipeline: Align → Test Context → Implement Fix → Review + Docs → CI Analysis (4 agents minimum) |
| **Batch File** | `--batch <file>` | Process features from file with auto-worktree |
| **Batch Issues** | `--issues <nums>` | Process GitHub issues with auto-worktree |
| **Resume** | `--resume <id>` | Resume interrupted batch from checkpoint |

## Implementation

**COORDINATOR FORBIDDEN LIST** — You MUST NOT do any of the following (violations = pipeline failure):

#### Agent Management (you are a dispatcher, not a substitute)
- ❌ You MUST NOT skip any STEP (even under context pressure or time constraints)
- ❌ You MUST NOT write implementation code yourself instead of delegating to agents
- ❌ You MUST NOT contain detailed agent instructions inline — those belong in agents/*.md
- ❌ You MUST NOT do an agent's work yourself when the agent crashes — RETRY the agent once with the same prompt. If retry also crashes, BLOCK and report to user. This applies to ALL specialist agents (implementer, test-master, researcher, planner, reviewer, security-auditor, doc-master). The coordinator is a dispatcher, never a substitute.
- ❌ You MUST NOT summarize agent output instead of passing full results to next agent

#### Pipeline Integrity — Step Ordering and Gates
- ❌ You MUST NOT declare "good enough" on failing tests (STEP 8 HARD GATE is absolute)
- ❌ You MUST NOT run STEP 10 before STEP 8 test gate passes
- ❌ You MUST NOT parallelize agents from different pipeline phases (e.g., implementer + reviewer) — within-phase parallel validation in STEP 10 is permitted for low-risk changesets per STEP 10 routing rules
- ❌ You MUST NOT treat STEP 13 as the final step (STEP 15 is mandatory)
- ❌ You MUST NOT clean up pipeline state before STEP 15 launches

#### Pipeline Integrity — Output Fidelity and Isolation
- ❌ You MUST NOT paraphrase, summarize, or condense agent output when passing it to the next stage. Pass the FULL agent output text verbatim. If output exceeds context limits, pass the first 2000 words plus the final summary/conclusion section — never your own restatement. The anti-pattern: "The implementer changed X, Y, Z" instead of the implementer's actual output. STEP 10 agents (reviewer, security-auditor) need the real output to do real reviews.
- ❌ You MUST NOT skip validation agents (reviewer, security-auditor, doc-master) under context pressure — BLOCK the pipeline instead and suggest `/clear` then `/implement --resume $RUN_ID`
- ❌ You MUST NOT pass fewer than 50% of the implementer's output words to the reviewer — if you must truncate, include the first 3000 words plus the full summary/conclusion. Log the word counts: "Implementer output: N words → Reviewer input: M words (ratio: M/N)"
- ❌ You MUST NOT leak implementer output, code diffs, reviewer feedback, research findings, or planner rationale to the spec-validator agent (STEP 8.5 context boundary violation)

### Pipeline Progress Protocol

**You MUST output structured progress to the user at each pipeline milestone.** This keeps the user informed of what's happening, which agents are running, and how long each step takes.

**Timing**: Capture `STEP_START=$(date +%s)` before each step. After each step, calculate elapsed: `STEP_ELAPSED=$(( $(date +%s) - STEP_START ))`. Format: `Xs` if under 60s, `M:SS` if 60s+.

**Step Banner** — output before each step begins:
```
========================================
STEP N/TOTAL — Step Name
Agent: agent-name (Model) [or "Agents: a, b (Model)" for parallel]
========================================
```

For non-agent steps (gates, checks), omit the Agent line.

**Agent Completion** — output after each agent returns:
```
  [done] agent-name              Xs
```
On failure:
```
  [FAIL] agent-name              Xs — reason
```

**HARD GATE Result** — output after each gate check:
```
  GATE: gate-name — PASS                Xs
```
or:
```
  GATE: gate-name — BLOCKED (reason)
```

**Test Gate Result** (STEP 8) — output after pytest:
```
  Tests: N passed, M failed, K skipped | Coverage: X.X% (baseline: Y.Y%) | Acceptance: N/M criteria | Tiers: T0=X, T1=Y, T2=Z, T3=W
```

**Final Summary** (STEP 13) — output the full pipeline summary:
```
========================================
PIPELINE COMPLETE
========================================
Step   Description                  Agent(s)                     Time     Status
-----  ---------------------------  ---------------------------  -------  ------
1      Pre-staged check             —                            2s       PASS
2      Alignment                    —                            3s       PASS
3      Research cache               —                            1s       MISS
4      Research                     researcher-local, researcher 45s      done
5      Planning                     planner                      1:32     done
6      Acceptance tests             —                            18s      done
8      Implementation               implementer                  3:45     done
8      Test gate                    —                            12s      PASS
8.5    Spec-blind validation        spec-validator               30s      done
9      Hook registration            —                            2s       PASS
10     Validation                   reviewer, security, docs     52s      done
11     Remediation gate             —                            0s       PASS
12     Verification                 —                            3s       PASS
13     Git operations               —                            5s       done
14     Doc congruence               —                            8s       PASS
15     Continuous improvement       ci-analyst                   (bg)     done
========================================
Total: 7:08 | Files changed: N | Tests: N passed, M failed | Security: PASS
========================================
```

### Pre-Dispatch Ordering Protocol — REQUIRED

Before EVERY Agent tool dispatch, you MUST run this inline verification. This catches ordering violations early (at dispatch time) instead of late (at hook time). Issue #850.

```bash
python3 -c "
import sys, os, json, time
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break

# Session-ID fallback chain (Issue #904):
#   1. CLAUDE_SESSION_ID env var (primary — set in-process by Claude Code)
#   2. /tmp/implement_pipeline_state.json['session_id'] (sentinel written at STEP 0)
#      — only honored when mtime is within 3600s (avoids cross-pipeline bleed)
#   3. 'unknown' (preserved legacy sentinel — first-boot/pre-STEP-0 case)
def _resolve_session_id():
    sid = os.environ.get('CLAUDE_SESSION_ID', '').strip()
    if sid and sid != 'unknown':
        return sid
    sentinel = '/tmp/implement_pipeline_state.json'
    try:
        if os.path.exists(sentinel):
            mtime = os.path.getmtime(sentinel)
            if time.time() - mtime < 3600:
                with open(sentinel) as _f:
                    _state = json.load(_f)
                _recovered = str(_state.get('session_id', '')).strip()
                if _recovered and _recovered != 'unknown':
                    return _recovered
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return 'unknown'

from agent_ordering_gate import check_ordering_with_session_fallback
result = check_ordering_with_session_fallback(
    'TARGET_AGENT',
    _resolve_session_id(),
    issue_number=ISSUE_NUMBER_OR_0,
    pipeline_mode='MODE'
)
if not result.passed:
    print(f'ORDERING BLOCK: {result.reason}')
else:
    print(f'ORDERING OK: dispatching TARGET_AGENT')
"
```

Replace `TARGET_AGENT` with the agent about to be dispatched (e.g., `planner`, `implementer`). Replace `ISSUE_NUMBER_OR_0` with the current issue number or `0`. Replace `MODE` with the pipeline mode (`full`, `light`, `fix`, or `tdd-first`).

**Session-ID propagation contract** (Issue #904): The helper above implements the fallback chain `env → sentinel → 'unknown'`. Coordinator subshells inherit `CLAUDE_SESSION_ID` in-process, but some exec contexts (nested heredocs, pipe subshells) drop the env var — the sentinel written at STEP 0 provides a recovery path. See [docs/PIPELINE-MODES.md](../../../docs/PIPELINE-MODES.md#session-id-propagation-contract) for the full contract.

**HARD GATE**: If `result.passed` is False, you MUST NOT dispatch the agent. Resolve the missing prerequisite agents first.

**FORBIDDEN**: Dispatching an Agent tool call when the pre-dispatch ordering check returns `passed=False`.

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 0: Parse Mode and Route

Parse ARGUMENTS: `--batch` → see [implement-batch.md](implement-batch.md), `--issues` → see [implement-batch.md](implement-batch.md), `--resume` → see [implement-resume.md](implement-resume.md), `--fix` → see [implement-fix.md](implement-fix.md), `--light` → LIGHT PIPELINE MODE (below), `--tdd-first` → FULL PIPELINE (TDD variant), `--acceptance-first` → recognized but no-op (same as default), `--full-tests` → disable smart test routing (run complete test suite in STEP 8), else → FULL PIPELINE (acceptance-first default). Reject `--quick`. Auto-detect batch: 2+ issue refs → BATCH ISSUES MODE. Check `--no-cache` flag.

**Mutual exclusivity**: `--fix` and `--light` are each mutually exclusive with `--batch`, `--issues`, and `--resume`. If combined, BLOCK with error. `--light` and `--fix` are also mutually exclusive.

**Auto-mode detection** — If no mode flag was explicitly provided (no `--fix`, `--light`, `--batch`, `--issues`, `--resume`, `--tdd-first` in ARGUMENTS), scan the feature description (case-insensitive) for signal patterns:

- **Fix signals**: "fix test", "failing test", "broken test", "test failure", "flaky test", "skip test" → candidate: `--fix`
- **Light signals (keyword-based)**: "update docs", "update readme", "readme", "changelog", "typo", "rename", "config change", "update comment" → candidate: `--light`
- **Light signals (file-path-based)**: If the feature description contains an explicit file path matching `*.md`, `*.json`, `*.yaml`, `*.yml`, `*.toml`, `docs/**`, `*.txt`, `*.cfg` AND that file path does NOT match any security-sensitive pattern (`*.py`, `*.sh`, `hooks/*`, `lib/*`, `.env*`, `*secret*`, `*auth*`, `*token*`) → candidate: `--light`
- **Tie-break**: If both fix and light patterns match (keyword or file-path), suggest `--fix`. If file-path suggests `--light` but keywords suggest `--fix`, use `--fix`.
- **Agent count optimization**: File-path light detection and fully-specified research skip (see STEP 3.5) reduce effective agent count for simple changes.

If a candidate is detected, output and STOP — wait for user response before proceeding:

```
Auto-detected: This looks like a [test fix | docs/config change].
Recommended: --[fix|light] ([one-line description from mode table])
Full pipeline: Research → Plan → Acceptance Tests → Implement → Review → Security → Docs

Proceed with --[fix|light]? (reply "yes" to confirm, anything else runs the full pipeline)
```

- User confirms ("yes", "y", or repeats the mode name) → route to suggested mode
- Anything else → FULL PIPELINE (default)
- No pattern match → proceed directly to FULL PIPELINE without prompting

**FORBIDDEN**: ❌ Silently switching mode without user confirmation. ❌ Prompting when a mode flag was explicitly specified. ❌ Blocking pipeline on ambiguous reply — default to FULL PIPELINE.

**Issue Body Fetching** (single-issue mode only):

If ARGUMENTS contains an issue reference (`#NNN` or issue number), fetch the issue body for potential research reuse:

```bash
ISSUE_NUMBER=$(echo "ARGUMENTS" | grep -oE '#?([0-9]+)' | head -1 | tr -d '#')
if [ -n "$ISSUE_NUMBER" ]; then
  ISSUE_DATA=$(gh issue view "$ISSUE_NUMBER" --json title,body 2>/dev/null)
  if [ $? -eq 0 ]; then
    ISSUE_TITLE=$(echo "$ISSUE_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin).get('title',''))")
    ISSUE_BODY=$(echo "$ISSUE_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin).get('body',''))")
  fi
fi
```

Store `ISSUE_BODY` and `ISSUE_TITLE` as pipeline context. If `gh issue view` fails, proceed without issue body (ISSUE_BODY remains empty). Do NOT block the pipeline on fetch failure.

Activate pipeline state:
```bash
RUN_ID="$(date +%Y%m%d-%H%M%S)"
PIPELINE_START=$(date +%s)
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import create_pipeline, save_pipeline
state = create_pipeline('$RUN_ID', 'FEATURE_DESC', mode='MODE')
save_pipeline(state)
print(f'Pipeline {state.run_id} initialized')
"
python3 -c "
import sys, os, json, time
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import sign_state

# Session-ID fallback chain (Issue #904): env → sentinel → 'unknown'.
# Honor a prior-written sentinel when the env var was dropped by a
# subshell, e.g. /implement --resume re-entering STEP 0.
def _resolve_session_id():
    sid = os.environ.get('CLAUDE_SESSION_ID', '').strip()
    if sid and sid != 'unknown':
        return sid
    sentinel = '/tmp/implement_pipeline_state.json'
    try:
        if os.path.exists(sentinel):
            mtime = os.path.getmtime(sentinel)
            if time.time() - mtime < 3600:
                with open(sentinel) as _f:
                    _state = json.load(_f)
                _recovered = str(_state.get('session_id', '')).strip()
                if _recovered and _recovered != 'unknown':
                    return _recovered
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return 'unknown'

sid = _resolve_session_id()
state = {
    'session_start': '$(date +%Y-%m-%dT%H:%M:%S)',
    'mode': 'MODE',
    'run_id': '$RUN_ID',
    'explicitly_invoked': True,
    'session_id': sid
}
state = sign_state(state, sid)
with open('/tmp/implement_pipeline_state.json', 'w') as f:
    json.dump(state, f)
"
```

---

# FULL PIPELINE MODE (Default)

Execute steps IN ORDER. Default mode uses acceptance-first testing (8 agents). TDD-first mode (`--tdd-first`) adds test-master (9 agents).

### STEP 1: Pre-Staged Files Check — HARD GATE

**Progress**: Output step banner (STEP 1/15 — Pre-Staged Files Check). Output gate result after check.

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

These would be bundled into this feature's commit, creating misleading git history.

Options:
A) Unstage: git reset HEAD
B) Commit first: git commit -m "wip: staged changes from previous session"
C) Review: git diff --cached
```

Do NOT proceed to STEP 2 until the staging area is clean.

**FORBIDDEN**:
- ❌ Proceeding with pre-staged files present
- ❌ Silently unstaging files without user confirmation
- ❌ Treating pre-staged files as part of the current feature

**Baseline Test Count Capture** (for regression test gate in STEP 8):

```bash
BASELINE_TEST_COUNT=$(python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from bugfix_detector import get_test_count
from pathlib import Path
print(get_test_count(Path('.')))
")
echo "Baseline test count: $BASELINE_TEST_COUNT"
```

**Baseline Failing Tests Capture** (for fix-forward classification in STEP 8 — Issue #860):

```bash
BASELINE_FAILING_FILE="/tmp/baseline_failing_tests.txt"
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from fix_forward import parse_failing_tests
import subprocess
result = subprocess.run(['pytest', '--tb=no', '-q'], capture_output=True, text=True, timeout=120)
failing = parse_failing_tests(result.stdout + result.stderr)
for t in sorted(failing):
    print(t)
" > "$BASELINE_FAILING_FILE"
BASELINE_FAILING_COUNT=$(grep -c . "$BASELINE_FAILING_FILE" 2>/dev/null || echo "0")
echo "Baseline failing tests: $BASELINE_FAILING_COUNT"
```

### STEP 2: Validate PROJECT.md Alignment — HARD GATE

**Progress**: Output step banner (STEP 2/15 — Alignment). Output gate result after.

Read `.claude/PROJECT.md`. If missing: BLOCK ("Run `/setup` or `/align --retrofit`"). Check feature against GOALS, SCOPE, CONSTRAINTS. If misaligned: BLOCK with reason and options.

**After alignment passes**, update the pipeline state to record that STEP 2 completed:

```bash
python3 -c "
import sys, os, json, time
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import sign_state

# Session-ID fallback chain (Issue #904): env → sentinel → 'unknown'.
# In a subshell that lost CLAUDE_SESSION_ID (e.g., nested heredoc in a
# pipe), recover the real session_id from the STEP-0 sentinel instead of
# re-signing the state as 'unknown' (which would break HMAC verification).
def _resolve_session_id():
    sid = os.environ.get('CLAUDE_SESSION_ID', '').strip()
    if sid and sid != 'unknown':
        return sid
    sentinel = '/tmp/implement_pipeline_state.json'
    try:
        if os.path.exists(sentinel):
            mtime = os.path.getmtime(sentinel)
            if time.time() - mtime < 3600:
                with open(sentinel) as _f:
                    _state = json.load(_f)
                _recovered = str(_state.get('session_id', '')).strip()
                if _recovered and _recovered != 'unknown':
                    return _recovered
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return 'unknown'

state_path = '/tmp/implement_pipeline_state.json'
if os.path.exists(state_path):
    with open(state_path) as f:
        state = json.load(f)
    state['alignment_passed'] = True
    sid = _resolve_session_id()
    state = sign_state(state, sid)
    with open(state_path, 'w') as f:
        json.dump(state, f)
    print('Alignment gate passed — state updated')
"
```

**FORBIDDEN**:
- ❌ Proceeding to STEP 3 without updating `alignment_passed` in the pipeline state
- ❌ Declaring alignment "obvious" without reading PROJECT.md
- ❌ Skipping STEP 2 under time or context pressure

### STEP 3: Check Research Cache

**Progress**: Output step banner (STEP 3/15 — Research Cache). Output CACHE_HIT or CACHE_MISS after.

**Issue Body Research Check** (before file-based cache):

If `ISSUE_BODY` is set (from STEP 0) AND `--no-cache` was NOT specified, DETECT embedded research:

```bash
# Write issue body to temp file to avoid shell escaping issues
echo "$ISSUE_BODY" > /tmp/implement_issue_body_$RUN_ID.txt
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from research_persistence import detect_issue_research
with open('/tmp/implement_issue_body_$RUN_ID.txt') as f:
    body = f.read()
result = detect_issue_research(body)
if result['is_research_rich']:
    print('ISSUE_RESEARCH_HIT')
    print(f'Sections: {result[\"section_count\"]} ({chr(44).join(result[\"matched_sections\"])})')
else:
    print('ISSUE_RESEARCH_MISS')
    print(f'Research sections found: {result[\"section_count\"]} (need >= 3)')
"
rm -f /tmp/implement_issue_body_$RUN_ID.txt
```

ISSUE_RESEARCH_HIT → use the issue body content as research context, output:
```
Research: SKIPPED (issue #$ISSUE_NUMBER contains pre-researched content — N sections detected: [section names])
```
Skip STEP 4. Pass issue body research to STEP 5 with prefix: "Research from GitHub Issue #$ISSUE_NUMBER (created by /create-issue):" followed by the extracted research sections.

ISSUE_RESEARCH_MISS → fall through to existing file-based cache check (unchanged behavior).

If `--no-cache` was specified, skip this check entirely (force fresh research).

**File-based cache check** (existing behavior):

```bash
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from research_persistence import check_cache, load_cached_research
cached = check_cache('FEATURE_TOPIC', max_age_days=7)
print('CACHE_HIT' if cached else 'CACHE_MISS')
"
```
CACHE_HIT → load cached research, skip STEP 4, pass to STEP 5. CACHE_MISS → proceed to STEP 3.5.

### STEP 3.5: Fully-Specified Change Detection

**Progress**: Output step banner (STEP 3.5/15 — Fully-Specified Change Detection). Output skip decision after.

Before invoking research agents, check if the feature description is a **fully-specified change** — one where both of the following conditions are met:
1. The description contains a **specific file path** (e.g., `plugins/autonomous-dev/agents/reviewer.md`, `config/settings.json`)
2. The description contains a **specific modification instruction** (e.g., "change X to Y", "add Z after line N", "remove section X", "replace X with Y", "set X to Y")

If BOTH conditions are met AND ALL of the following safeguards pass:
- The referenced file(s) do NOT match security-sensitive patterns: `hooks/*.py`, `lib/*security*`, `lib/*auth*`, `lib/*token*`, `*.env*`, `*secret*`, `*auth*`, `config/auto_approve_policy.json`, `templates/settings.*.json`
- The feature description does NOT contain security/authentication/encryption/sso/oauth/rbac/permission/session/jwt keywords
- The description references 3 or fewer files

Then: **skip STEP 4**, proceed directly to STEP 5. Output:
```
Research: SKIPPED (fully-specified change — file path + instruction provided, no security topics)
```

**Record research skip in pipeline state** (Issue #802): When research is skipped, record it so the agent completeness gate knows researchers are not required:
```python
from pipeline_completion_state import record_research_skipped
record_research_skipped(SESSION_ID, issue_number=ISSUE_NUM)
```

Otherwise: proceed to STEP 4.

**FORBIDDEN** — You MUST NOT skip research when:
- ❌ Only a file path is given without a specific modification instruction
- ❌ The change touches security-sensitive files or topics (authentication, encryption, tokens, secrets, sso, oauth, rbac, permission, session, jwt)
- ❌ More than 3 files are referenced in the description

### STEP 4: Parallel Research (2 agents)

**Progress**: Output step banner (STEP 4/15 — Research, Agents: researcher-local (Haiku), researcher (Sonnet)). Output agent completions after each returns.

**Pre-dispatch**: Follow the Pre-Dispatch Ordering Protocol (above) for each agent before invoking.

Invoke TWO agents in PARALLEL (single message, both Agent tool calls):
1. **Agent**(subagent_type="researcher-local", model="haiku") — "Search codebase for patterns related to: {feature}. Output JSON with findings and sources."
2. **Agent**(subagent_type="researcher", model="sonnet") — "Research best practices for: {feature}. MUST use WebSearch. Output JSON with findings, sources, security considerations."

Validation: If web researcher shows 0 tool uses, retry. Merge both outputs. Persist research via `save_merged_research()`.

### STEP 4.5: Research Completeness Critique (inline — no agent)

**Progress**: Output step banner (STEP 4.5/15 — Research Completeness Critique). No agent invoked.

After merging research, perform one FEEDBACK pass on the merged output before passing it to the planner. This implements the Self-Refine pattern (GENERATE → FEEDBACK → REFINE).

Check the merged research against these criteria:

1. **Coverage**: Does the research cover the feature's core algorithm/logic, integration points, and failure modes? If any are missing, note them as "Research Gaps".
2. **Missing perspectives**: Are security implications, performance at scale, and backwards-compatibility addressed? If not, flag each gap.
3. **Source quality**: Did the web researcher cite at least one non-trivial external source (docs, paper, RFC)? If not, note it.

If gaps are found, append a "**Research Gaps**" section to the merged research summary before passing to STEP 5. The planner MUST be made aware of gaps so it can flag them in the architecture plan. This step is performed inline by the coordinator.

### STEP 5: Planner (1 agent)

**Progress**: Output step banner (STEP 5/15 — Planning, Agent: planner (Opus)). Output agent completion after.

**Pre-dispatch**: Follow the Pre-Dispatch Ordering Protocol (above) for each agent before invoking.

If research came from the issue body (ISSUE_RESEARCH_HIT), prefix the research context with: "Research from GitHub Issue #$ISSUE_NUMBER:" followed by the extracted research sections from `detect_issue_research()`. The planner should treat this identically to merged research from STEP 4.

**Agent**(subagent_type="planner", model="opus") — Pass merged research + feature description + PROJECT.md GOALS and SCOPE sections (verbatim). Read `.claude/PROJECT.md` and extract the GOALS section and SCOPE section (both IN Scope and OUT of Scope). Include them in the planner prompt as: "PROJECT.md GOALS: [verbatim text]. PROJECT.md SCOPE (In Scope): [verbatim items]. PROJECT.md SCOPE (Out of Scope): [verbatim items]. The plan MUST align with these scope boundaries." Output: file-by-file plan, dependencies, edge cases, testing strategy.

### STEP 5.5: Plan Validation Gate — HARD GATE

**Progress**: Output step banner (STEP 5.5/15 — Plan Validation Gate). Output gate result after.

#### 5.5a — Pre-Validated Plan Check

Search `.claude/plans/` for a file whose name or content matches the current feature description (case-insensitive substring match). If a matching file is found AND that file contains the string "Verdict: PROCEED" in its Critique History section:

- **Skip plan-critic invocation** and continue to 5.5c (structural validation still runs)
- Log: `Plan validation: SKIPPED (pre-validated plan: {path})`
- **Record plan-critic skip in pipeline state** (Issue #878): When plan-critic is skipped, record it so the agent completeness gate knows plan-critic is not required:
```python
from pipeline_completion_state import record_plan_critic_skipped
record_plan_critic_skipped(SESSION_ID, issue_number=ISSUE_NUM)
```

If no matching file with "Verdict: PROCEED" is found, proceed to 5.5b.

#### 5.5b — Budget Plan-Critic Invocation

**When no pre-validated plan exists**, invoke the plan-critic agent with a constrained budget:

- **Rounds**: 1 (single pass, no iterative critique)
- **Axes**: 3 only — Assumption Audit, Existing Solution Search, Minimalism Pressure
- **Agent**(subagent_type="plan-critic", model="sonnet") — Pass planner output. Instruct: "Single-pass critique on 3 axes only: Assumption Audit, Existing Solution Search, Minimalism Pressure. Output verdict: PROCEED, REVISE, or BLOCKED." (When running under --batch, include the BATCH CONTEXT block (worktree path + issue number) per implement-batch.md STEP B3.)

**Parse verdict from plan-critic output**:

- **PROCEED** → continue to 5.5c (structural validation)
- **REVISE** → pass the plan-critic feedback to the planner, re-invoke planner once (same prompt as STEP 5 plus feedback), then accept the revised plan and continue to 5.5c regardless of a second critique
- **BLOCKED** → BLOCK the pipeline with message:
  ```
  BLOCKED (STEP 5.5): Plan-critic returned BLOCKED verdict.
  Reason: {plan-critic feedback}
  Resolution: Revise the feature description or scope and re-run /implement.
  ```

#### 5.5c — Structural Validation

**Always runs** (even when 5.5a skipped plan-critic). Verify the plan (from STEP 5 or revised in 5.5b) satisfies all three structural requirements:

1. **File paths**: Plan contains ≥1 absolute or relative file path (matches pattern `[\w/.-]+\.(py|md|json|yaml|sh|ts|js)`)
2. **Acceptance criteria**: Plan contains an "acceptance criteria" section (case-insensitive: "acceptance criteria", "acceptance criterion", or "## Acceptance")
3. **Testing strategy**: Plan contains a "testing strategy" or "test" section (case-insensitive: "testing strategy", "test plan", or "## Test")

If any requirement is missing:
- Re-invoke planner once with instruction: "Your plan is missing: {list of missing elements}. Please revise to include all required sections."
- Re-check the three requirements on the revised plan.
- If still missing after one revision → BLOCK the pipeline:
  ```
  BLOCKED (STEP 5.5): Plan failed structural validation after revision.
  Missing: {list of still-missing elements}
  Resolution: Ensure the planner output includes file paths, acceptance criteria, and testing strategy.
  ```

#### 5.5d — FORBIDDEN

**FORBIDDEN** — You MUST NOT do any of the following:

- ❌ You MUST NOT accept a plan that contains 0 file paths (structural validation always blocks this)
- ❌ You MUST NOT accept a plan that has no acceptance criteria section
- ❌ You MUST NOT skip plan-critic when no pre-validated plan file exists in `.claude/plans/`
- ❌ You MUST NOT skip structural validation for any reason (it always runs, even with a pre-validated plan)

### STEP 6: Generate Acceptance Tests (default mode only)

**Progress**: Output step banner (STEP 6/15 — Acceptance Tests). Output completion after. **Output the STEP 6 banner even when skipping** — the banner followed by the skip reason provides an audit trail.

**Skip Logic**: Skip if `--tdd-first`. Check `tests/genai/conftest.py` exists (if not, fall back to TDD-first). Generate `tests/genai/test_acceptance_{slug}.py` with one `genai.judge()` test per acceptance criterion from planner output.

**Required Skip/Execute Logging** — The coordinator MUST output exactly one of the following after the step banner:
```
STEP 6: SKIPPED (--tdd-first mode — test-master handles tests in STEP 7)
STEP 6: SKIPPED (tests/genai/conftest.py not found — falling back to TDD-first)
STEP 6: EXECUTED (N acceptance tests generated from M criteria)
```

**Test Placement Classification Rule** — Before writing any acceptance test, classify it by what it actually does:

| Test Type | Placement | Marker |
|-----------|-----------|--------|
| Calls `genai.judge()` or makes any LLM API call | `tests/genai/` | `@pytest.mark.genai` |
| Static file inspection: regex, string matching, file existence, line counts | `tests/unit/` | none |
| Parses output structure without LLM | `tests/unit/` | none |

**Why this matters**: Tests in `tests/genai/` require the `--genai` flag to run. The standard test gate (`pytest --tb=short -q`) does NOT run them. If a static file inspection test is placed in `tests/genai/`, it becomes invisible to the STEP 8 test gate and the acceptance criterion is effectively unverified.

**Classification rule**:
- If the test body contains `genai.judge(` → `tests/genai/` with `@pytest.mark.genai`
- If the test body only reads files, checks strings, runs regex, or asserts on file contents → `tests/unit/` without `@pytest.mark.genai`
- When in doubt: static checks belong in unit, LLM calls belong in genai

**Save Acceptance Criteria Registry** — After generating acceptance tests, save the criteria-to-test mapping for later coverage tracking:
```python
from acceptance_criteria_tracker import save_criteria_registry
criteria = [
    {"criterion": "<acceptance criterion text>", "scenario_name": "<test function name>", "test_file": "<test file path>"}
    # ... one entry per acceptance criterion
]
save_criteria_registry(criteria, Path(".claude/local"))
```
This registry is consumed by `step5_quality_gate.run_quality_gate()` to report acceptance coverage (N/M criteria) in the STEP 8 test gate output.

**FORBIDDEN**:
- ❌ Silently skipping STEP 6 without outputting a skip reason
- ❌ Proceeding from STEP 5 to STEP 8 without either executing or explicitly skipping STEP 6
- ❌ Skipping STEP 6 when tests/genai/conftest.py exists and mode is not --tdd-first

### STEP 7: Test-Master (--tdd-first only)

**Progress**: Output step banner (STEP 7/15 — Test-Master, Agent: test-master (Opus)). Skip banner if not --tdd-first. Output agent completion after.

If `--tdd-first`: **Agent**(subagent_type="test-master", model="opus") — Pass planner output + file list + GenAI infra status (`test -f tests/genai/conftest.py && echo "GENAI_INFRA=EXISTS" || echo "GENAI_INFRA=ABSENT"`). Otherwise: skip (implementer writes unit tests alongside code in default acceptance-first mode).

### STEP 8: Implementer + Test Gate — HARD GATE

**Progress**: Output step banner (STEP 8/15 — Implementation + Test Gate, Agent: implementer (Opus)). Output agent completion, then test gate result with pass/fail/skip counts and coverage after.

**Pre-dispatch**: Follow the Pre-Dispatch Ordering Protocol (above) for each agent before invoking.

**Agent**(subagent_type="implementer", model=PLANNER_RECOMMENDED_MODEL) — Pass planner output + acceptance tests (or test-master output if TDD). Must write WORKING code, no stubs. Use the model recommended by the planner (see STEP 5). Default to "opus" if planner did not specify.

**Ghost Invocation Detection** — After the implementer agent returns, verify the output is non-trivial. Count the words in the implementer's result. If the result word count is fewer than 50 words AND the agent completed in less than 10 seconds, treat it as a ghost invocation — the agent was invoked but did not actually execute implementation work:
1. Log: `[GHOST-INVOCATION-DETECTED] Implementer returned <N> words in <T>s — retrying once with same prompt`
2. **RETRY the implementer once** with the exact same prompt (same planner output + acceptance tests)
3. If the retry also produces fewer than 50 words in less than 10 seconds, BLOCK the pipeline:
```
BLOCKED: Ghost implementer invocation — agent returned <N> words in <T>s on both initial attempt and retry.
This indicates the implementer failed to execute. Investigate agent health and retry manually:
  /implement --resume $RUN_ID
```

**FORBIDDEN** — You MUST NOT do any of the following for ghost invocation:
- ❌ You MUST NOT proceed past STEP 8 when a ghost invocation is detected without first retrying
- ❌ You MUST NOT treat 0-word or near-0-word output as a valid implementation result
- ❌ You MUST NOT retry more than once (one retry maximum — block after two consecutive ghost results)

**HARD GATE** (inline — coordinator must verify):
```bash
pytest --tb=short -q
```
For EACH failure, you MUST choose one:
1. **Fix it** — debug and fix code/test
2. **Adjust it** — update test expectations to match correct behavior

**HARD GATE: No New Skips** — Adding `@pytest.mark.skip` is FORBIDDEN. 0 new skips allowed. Skip count is tracked across sessions via `coverage_baseline.check_skip_regression()`. If the current skip count exceeds the baseline, the quality gate BLOCKS.

**FORBIDDEN** — You MUST NOT do any of the following (coverage/skip/test count violations):
- ❌ You MUST NOT add `@pytest.mark.skip` to any test (0 new skips, enforced by baseline comparison)
- ❌ You MUST NOT let coverage drop more than 0.5% below baseline (enforced by `coverage_baseline.check_coverage_regression()`)
- ❌ You MUST NOT declare coverage loss "acceptable" or "minor"
- ❌ You MUST NOT proceed to STEP 10 when `step5_quality_gate.run_quality_gate()` returns `passed=False`
- ❌ You MUST NOT proceed when test count drops significantly from baseline (enforced by `coverage_baseline.check_test_count_regression()`)

Loop until **0 failures, 0 errors**. Do NOT proceed to STEP 10 with any failures.

**Pre-Existing Failure Classification (Fix-Forward -- Issue #860)**

After achieving 0 test failures OR when remaining failures are all pre-existing, run classification:

```bash
python3 -c "
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from fix_forward import parse_failing_tests, classify_failures
import subprocess
# Capture current pytest output inline (not via shell variable)
current_result = subprocess.run(['pytest', '--tb=no', '-q'], capture_output=True, text=True, timeout=120)
current_failing = parse_failing_tests(current_result.stdout + current_result.stderr)
# Read baseline failing tests from temp file written in STEP 1 (newline-separated test IDs)
baseline_file = '/tmp/baseline_failing_tests.txt'
try:
    baseline_contents = open(baseline_file).read().strip()
    baseline_failing = set(baseline_contents.split('\n')) if baseline_contents else set()
except FileNotFoundError:
    baseline_failing = set()
result = classify_failures(baseline_failing, current_failing)
print(f'Fixed: {len(result[\"fixed\"])} | Pre-existing: {len(result[\"pre_existing_remaining\"])} | New: {len(result[\"new_failures\"])}')
"
```

Gate: `new_failures > 0` BLOCKS (unchanged). `new_failures == 0` with `pre_existing_remaining > 0` auto-files issues via `gh issue create` with label `pre-existing-failure`, then proceeds. `fixed > 0` notes in commit context. FORBIDDEN: classifying failures in implementer-modified files as "pre-existing", or silently dropping pre-existing failures without fixing or filing.

**Smart Test Routing** (unless `--full-tests` flag was passed): The quality gate uses `test_routing.route_tests()` to classify changed files and run only relevant test tiers. When routing is active, report which tiers ran and which were skipped:
```
Test Routing: hook, lib changes detected
  Running: smoke, hooks, unit, regression, property
  Skipped: genai
```
If `--full-tests` was passed, report "Full test suite (--full-tests override)".

Coverage check: `pytest tests/ --cov=plugins --cov-report=term-missing -q 2>&1 | tail -5` — must be >= baseline - 0.5%. On success, baseline is automatically updated via `coverage_baseline.save_baseline()`.

**Test Gate Output Format** — The quality gate (`step5_quality_gate.run_quality_gate()`) now reports acceptance coverage and tier distribution in the summary:
```
PASS: 45 passed | Coverage: 87% (baseline: 85%) | Skip count OK: 2 | Test count OK: 45 (baseline: 44) | Acceptance: 3/4 criteria | Tiers: T0=2, T1=5, T2=8, T3=30
```
- **Acceptance coverage** (WARNING only, never blocks): Reports how many acceptance criteria from STEP 6 have matching tests. When total > 0 but covered == 0, a WARNING is appended to the summary.
- **Tier distribution**: Reports test count by Diamond Model tier (T0-T3), computed by globbing `tests/**/*.py`.

### HARD GATE: Regression Test Requirement (Bug Fixes)

If the feature being implemented is a bug fix, at least one NEW test must be added. This gate applies the same enforcement as `implement-fix.md` (lines 166-177) to the full pipeline.

**Bug-fix detection** (inline — coordinator checks):
```bash
IS_BUGFIX=$(python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from bugfix_detector import is_bugfix_feature
desc = '''FEATURE_DESCRIPTION'''
labels = ISSUE_LABELS  # from STEP 0 gh issue view, or empty list
print('true' if is_bugfix_feature(desc, labels) else 'false')
")
```

If `IS_BUGFIX` is `true`:

```bash
CURRENT_TEST_COUNT=$(python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from bugfix_detector import get_test_count
from pathlib import Path
print(get_test_count(Path('.')))
")
```

If `CURRENT_TEST_COUNT <= BASELINE_TEST_COUNT`: **BLOCK** with message:
```
BLOCKED — Bug fix detected but no new regression tests added.

Feature: FEATURE_DESCRIPTION
Test count before: $BASELINE_TEST_COUNT
Test count after: $CURRENT_TEST_COUNT

REQUIRED NEXT ACTION:
Add at least one test that reproduces the bug and fails without the fix.

Exception: If an existing failing test IS the regression test, document
which test covers it and the gate passes automatically.
```

**Exception**: If the bug was caught BY an existing failing test (the test that originally failed IS the regression test), this gate passes. Document which existing test covers the regression.

**FORBIDDEN**:
- ❌ Fixing a bug without a test that proves it was broken
- ❌ Claiming "the fix is obvious and doesn't need a test"
- ❌ Adding a test that passes both with and without the fix (not a real regression test)

#### OUTPUT VALIDATION GATE: Plan-Implementation Alignment

After tests pass, verify that the implementer worked on the files the planner intended. This prevents scope creep and silent under-delivery.

**Step 1 — Collect planned files**

Extract the list of files from the STEP 5 planner output that were marked `CREATE` or `MODIFY`.

**Step 2 — Collect implemented files**

```bash
IMPLEMENTED_FILES=$(git diff --name-only HEAD)
```

**Step 3 — Exclude noise**

Remove from both lists:
- Test files: paths matching `tests/**`
- Documentation files: paths matching `docs/**`, `*.md` at repo root, and `CHANGELOG.md`

**Step 4 — Compare**

- Files in plan but NOT in implementation → WARNING
- Files in implementation but NOT in plan → WARNING
- If more than 50% of non-excluded implemented files are unplanned → **BLOCK**

**Step 5 — Output alignment report**

```
Plan-Implementation Alignment Check:
  Planned files: N | Implemented files: M (after exclusions)
  Planned but not implemented: [list or "none"]
  Implemented but not planned: [list or "none"]
  Verdict: PASS | WARNING (N unplanned files) | BLOCKED (X% divergence > 50%)
```

**FORBIDDEN**:
- ❌ Skipping this gate
- ❌ Treating >50% divergence as acceptable and continuing

### STEP 8.5: Spec-Blind Validation — HARD GATE

**Progress**: Output step banner (STEP 8.5/15 — Spec-Blind Validation, Agent: spec-validator (Opus)). Output agent completion and verdict after.

**Pre-dispatch**: Follow the Pre-Dispatch Ordering Protocol (above) for each agent before invoking.

**Context Boundary** — The spec-validator operates with strict isolation. You MUST pass ONLY the following to this agent:
- Acceptance criteria from STEP 6
- Feature description (from user input)
- Changed file paths (from `git diff --name-only`)
- PROJECT.md scope sections

**FORBIDDEN** — You MUST NOT pass any of the following to the spec-validator:
- Implementer output or summary
- Code diffs or patch content
- Reviewer feedback
- Security-auditor findings
- Research findings from STEP 4
- Planner rationale or design decisions
- Any coordinator commentary on implementation quality

**Agent**(subagent_type="spec-validator", model="opus") — Pass acceptance criteria + feature description + changed file paths ONLY.

**Verdict Parsing**: Parse the agent output for `SPEC-VALIDATOR-VERDICT: PASS` or `SPEC-VALIDATOR-VERDICT: FAIL`.

- If **PASS**: proceed to STEP 9.
- If **FAIL**: Re-invoke the implementer in REMEDIATION MODE with ONLY the failing test names from the spec-validator output. Do NOT pass the spec-validator's test code or implementation suggestions. Maximum 2 remediation cycles. After remediation, re-run the spec-validator. If it still fails after 2 cycles, BLOCK the pipeline:
```
BLOCKED: Spec-validator failed after 2 remediation cycles.
Failing criteria: [list from spec-validator output]
```

### STEP 9: Hook Registration Check — HARD GATE

**Progress**: Output step banner (STEP 9/15 — Hook Registration). Output gate result after.

If hooks were created/modified: verify they appear in `templates/settings.*.json`, `config/global_settings_template.json`, and `config/install_manifest.json`. BLOCK if unregistered.

### STEP 9.5: Agent Count Gate — HARD GATE

Before proceeding to validation, verify that the minimum required specialist agents have actually run. This prevents the coordinator from skipping agents under context pressure and going straight to STEP 10.

**Required agents before STEP 10** (full pipeline):
- researcher-local (STEP 4) — unless research cache hit
- researcher (STEP 4) — unless research cache hit
- planner (STEP 5)
- implementer (STEP 8)
- spec-validator (STEP 8.5)

**Minimum count**: 5 agents (or 3 if research was cached). Count the distinct `subagent_type` values you have invoked so far in this pipeline run.

**HARD GATE**: If agent count < minimum:
```
BLOCKED: Agent count gate failed.
Required: researcher-local, researcher, planner, implementer
Actually ran: [list agents that ran]
Missing: [list agents that didn't run]

You MUST invoke the missing agents before proceeding to STEP 10.
```

**FORBIDDEN**: Proceeding to STEP 10 with fewer than the minimum agents. If an agent was skipped due to a crash, the crash retry rule (forbidden list) applies — retry once, then block.

**Hook enforcement** (Issue #802): The unified_pre_tool.py hook also enforces agent completeness at git commit time via `_check_pipeline_agent_completions()`. This provides a defense-in-depth hard gate — even if the coordinator bypasses STEP 9.5, the hook will block the commit if required agents are missing. The hook reads pipeline state from `verify_pipeline_agent_completions()` and respects `SKIP_AGENT_COMPLETENESS_GATE=1` as an escape hatch.

### STEP 9.7: Conditional UI Testing (ui-tester)

**This step is OPTIONAL.** Only invoke ui-tester when BOTH conditions are met:
1. Changed files include frontend patterns: `*.html`, `*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.css`
2. Playwright MCP tools are available (test by attempting `mcp__playwright__browser_navigate` to `about:blank`)

If both conditions are met:
- **Agent**(subagent_type="ui-tester", model="sonnet") — Pass changed file list + target URL (from user prompt or `http://localhost:3000` default)
- Parse output for `UI-TESTER-VERDICT: PASS` or `UI-TESTER-VERDICT: SKIP`
- Either result allows proceeding — E2E testing is ADVISORY, never blocking

If conditions are NOT met, skip this step silently and proceed to STEP 9.8.

**FORBIDDEN**: Blocking the pipeline based on ui-tester output. The ui-tester verdict is informational only.

### STEP 9.8: Conditional Mobile Testing (mobile-tester)

**This step is OPTIONAL.** Only invoke mobile-tester when BOTH conditions are met:
1. Changed files include mobile patterns: `*.swift`, `*.kt`, `*.dart`, `ios/`, `android/`, `Podfile`, `build.gradle`, `pubspec.yaml`
2. At least one of the following is available: Appium MCP tools (test by attempting `mcp__appium__get_session`) OR Maestro CLI (test by running `maestro --version`)

If both conditions are met:
- **Agent**(subagent_type="mobile-tester", model="sonnet") — Pass changed file list + target platform (ios/android/flutter, detected from changed file patterns)
- Parse output for `MOBILE-TESTER-VERDICT: PASS` or `MOBILE-TESTER-VERDICT: SKIP`
- Either result allows proceeding — mobile testing is ADVISORY, never blocking

If conditions are NOT met, skip this step silently and proceed to STEP 10.

**FORBIDDEN**: Blocking the pipeline based on mobile-tester output. The mobile-tester verdict is informational only.

### STEP 10: Validation — Reviewer, Security, and Docs (3 agents)

**Progress**: Output step banner (STEP 10/15 — Validation). Output each agent completion as they return.

**Validation mode routing**: Before launching any validator, check if any changed files match security-sensitive patterns:
- Security-sensitive patterns: `hooks/*.py`, `lib/*security*`, `lib/*auth*`, `lib/*token*`, `*.env*`, `*secret*`, `config/auto_approve_policy.json`, `templates/settings.*.json`, `*trading*`, `*payment*`, `*billing*`, `*financial*`, `*transaction*`, `*wallet*`, `*crypto*`, `*permission*`, `*session*`, `*credential*`, `*password*`, `*oauth*`, `*sso*`, `*jwt*`, `*rbac*`, `migrations/`, `*migrate*`, `alembic/`

Output the selected mode before proceeding:
```
Validation mode: parallel (low-risk change)
```
or:
```
Validation mode: sequential (security-sensitive files detected: [list of matched files])
```

---

**DEFAULT: Parallel mode** (no security-sensitive files in changeset)

**Pre-dispatch**: Follow the Pre-Dispatch Ordering Protocol (above) for each agent before invoking.

Invoke reviewer, security-auditor, and doc-master in a SINGLE message (all three parallel). Pass STEP 8 test results to the reviewer along with the implementer output (see VERBATIM PASSING requirement below).

**VERBATIM PASSING REQUIRED**: Pass the FULL implementer output from STEP 8 to the reviewer, including the STEP 8 test results (pass/fail/skip counts, coverage, any failure details). Do NOT summarize, condense, or paraphrase. If the output is too long, pass the first 3000 words plus the complete file change list and test results section. If the implementer output contains an Evidence Manifest section, it MUST be included in the passed content. When truncating long output, preserve the Evidence Manifest in addition to the file change list and test results. Log word counts: "Implementer output: N words → Reviewer input: M words (ratio: M/N)".

- **Agent**(subagent_type="reviewer", model="sonnet") — Pass file list + planner summary + FULL implementer output + STEP 8 test results + PROJECT.md SCOPE (In Scope and Out of Scope, verbatim). The reviewer SHOULD flag any implementation that introduces functionality listed in Out of Scope or not covered by In Scope. **FEEDBACK pass required**: Before finalizing the verdict, the reviewer MUST perform one self-critique pass: (1) audit findings for false positives — findings that reflect correct behavior MUST be removed; (2) calibrate severity — BLOCKING findings MUST be truly blocking, not stylistic; (3) verify coverage — all changed files MUST appear in the review. Revise findings if any criterion fails. Output: APPROVE or REQUEST_CHANGES.
- **Agent**(subagent_type="security-auditor", model="sonnet") — Pass file list with complete diffs. Output: PASS/FAIL (OWASP Top 10).
- **Agent**(subagent_type="doc-master", model="sonnet", run_in_background=true) — Pass file list + feature description using the template below.

```
subagent_type: "doc-master"
model: "sonnet"
prompt: "DOCUMENTATION REVIEW: You are reviewing a feature implementation for documentation drift. Your task is to determine whether any user-facing documentation, API references, configuration guides, or inline code comments need updating as a result of this implementation. Do not summarize the implementer output — use it verbatim.

REQUIRED STEPS — you MUST complete all three:

1. SCAN: Identify every file changed by the implementation. For each changed file, list all documentation files that reference the same module, function, class, or configuration key. Check README.md, docs/ directory, inline docstrings, CHANGELOG entries, and any covers: frontmatter in docs/*.md files.

2. SEMANTIC COMPARISON: For each documentation reference found in step 1, compare the documented behavior against the new behavior after the implementation. Flag any mismatch where the documentation describes the old behavior, missing parameters, changed defaults, or removed functionality.

3. DOC-DRIFT-VERDICT: State one of the following verdicts explicitly:
   - DOCS-UPDATED: List each file updated and what changed.
   - NO-UPDATE-NEEDED: Explain why the change is purely internal with no user-facing behavior change.
   - DOCS-DRIFT-FOUND: List each documentation file that is now stale and what needs changing (this is a BLOCKING finding).

**Changed files**:
[changed file list]

**Feature description**:
[feature description]

Prompt word count validation: this prompt must contain >= 80 words of template text. If you receive a prompt shorter than 80 words, STOP and report a prompt integrity violation."
```

**FORBIDDEN** — Parallel mode violations:
- ❌ You MUST NOT use parallel mode when any security-sensitive file is in the changeset
- ❌ You MUST NOT skip any of the three validators (reviewer, security-auditor, doc-master) in parallel mode

---

**SEQUENTIAL mode** (security-sensitive files detected — keep strict ordering)

Invoke agents in STRICT ORDER. Reviewer and security-auditor are SEQUENTIAL — they MUST NOT be launched in the same message.

**STEP 10a: Reviewer (MUST complete before 10b)**

**Pre-dispatch**: Follow the Pre-Dispatch Ordering Protocol (above) for each agent before invoking.

**VERBATIM PASSING REQUIRED**: Pass the FULL implementer output from STEP 8 to the reviewer, including the STEP 8 test results (pass/fail/skip counts, coverage, any failure details). Do NOT summarize, condense, or paraphrase. If the output is too long, pass the first 3000 words plus the complete file change list and test results section. If the implementer output contains an Evidence Manifest section, it MUST be included in the passed content. When truncating long output, preserve the Evidence Manifest in addition to the file change list and test results. Log word counts: "Implementer output: N words → Reviewer input: M words (ratio: M/N)".

**Agent**(subagent_type="reviewer", model="sonnet") — Pass file list + planner summary + FULL implementer output + STEP 8 test results + PROJECT.md SCOPE (In Scope and Out of Scope, verbatim). The reviewer SHOULD flag any implementation that introduces functionality listed in Out of Scope or not covered by In Scope. **FEEDBACK pass required**: Before finalizing the verdict, the reviewer MUST perform one self-critique pass: (1) audit findings for false positives — findings that reflect correct behavior MUST be removed; (2) calibrate severity — BLOCKING findings MUST be truly blocking, not stylistic; (3) verify coverage — all changed files MUST appear in the review. Revise findings if any criterion fails. Output: APPROVE or REQUEST_CHANGES.

**Runtime Verification**: When changed files include frontend (HTML/TSX/Vue), API routes, or CLI tools, the reviewer MAY perform targeted runtime verification after completing static review. This is opt-in and does not change the pipeline structure. See reviewer.md for details.

**HARD GATE: Reviewer Completion** — You MUST wait for the reviewer agent to return its result BEFORE invoking security-auditor. Do NOT launch security-auditor in the same message as reviewer. This is a SEQUENTIAL constraint, not a suggestion. If you violate this gate, the pipeline is invalid. **This ordering is now hook-enforced**: `unified_pre_tool.py` Layer 4 reads agent completion state and blocks out-of-order Agent calls (Issues #625, #629, #632).

**STEP 10b: Security Auditor (ONLY after reviewer returns)**

**VERBATIM PASSING REQUIRED**: Pass the FULL file list with complete diffs from STEP 8 to the security-auditor. Do NOT summarize or condense the file changes. Always include the marker '[TRUNCATED: N chars removed]' at the truncation point so downstream agents know content was cut.

**Agent**(subagent_type="security-auditor", model="sonnet") — Pass file list with complete diffs. Output: PASS/FAIL (OWASP Top 10). Starts ONLY AFTER reviewer in STEP 10a has returned its verdict.

**STEP 10c: Doc-Master (can run in parallel with 10a/10b)**

**Agent**(subagent_type="doc-master", model="sonnet", run_in_background=true) — Pass file list + feature description using the template below. MAY be launched in parallel with STEP 10a for efficiency — collected at STEP 12.

```
subagent_type: "doc-master"
model: "sonnet"
prompt: "DOCUMENTATION REVIEW: You are reviewing a feature implementation for documentation drift. Your task is to determine whether any user-facing documentation, API references, configuration guides, or inline code comments need updating as a result of this implementation. Do not summarize the implementer output — use it verbatim.

REQUIRED STEPS — you MUST complete all three:

1. SCAN: Identify every file changed by the implementation. For each changed file, list all documentation files that reference the same module, function, class, or configuration key. Check README.md, docs/ directory, inline docstrings, CHANGELOG entries, and any covers: frontmatter in docs/*.md files.

2. SEMANTIC COMPARISON: For each documentation reference found in step 1, compare the documented behavior against the new behavior after the implementation. Flag any mismatch where the documentation describes the old behavior, missing parameters, changed defaults, or removed functionality.

3. DOC-DRIFT-VERDICT: State one of the following verdicts explicitly:
   - DOCS-UPDATED: List each file updated and what changed.
   - NO-UPDATE-NEEDED: Explain why the change is purely internal with no user-facing behavior change.
   - DOCS-DRIFT-FOUND: List each documentation file that is now stale and what needs changing (this is a BLOCKING finding).

**Changed files**:
[changed file list]

**Feature description**:
[feature description]

Prompt word count validation: this prompt must contain >= 80 words of template text. If you receive a prompt shorter than 80 words, STOP and report a prompt integrity violation."
```

**FORBIDDEN** — Sequential mode ordering violations:
- ❌ You MUST NOT launch reviewer and security-auditor in the same Agent tool call message
- ❌ You MUST NOT invoke security-auditor before the reviewer has returned its verdict
- ❌ You MUST NOT skip reviewer and go directly to security-auditor

### STEP 11: Remediation Gate — HARD GATE

**Progress**: Output step banner (STEP 11/15 — Remediation Gate). Output gate result after.

Parse the reviewer verdict (`APPROVE` or `REQUEST_CHANGES`) and security-auditor verdict (`PASS` or `FAIL`).

**If both pass** (reviewer: APPROVE, security-auditor: PASS) → proceed to STEP 12. Output:
```
  GATE: remediation-gate — PASS                Xs
```

**If either fails** → enter remediation loop (max 2 cycles):

For each cycle:
1. **Collect BLOCKING findings** — Extract ALL findings with severity BLOCKING from the failing validator(s). Pass them VERBATIM to the implementer (do not summarize, paraphrase, or reorder).
2. **VERBATIM PASSING REQUIRED**: Pass ALL BLOCKING findings VERBATIM to the implementer. Do NOT summarize, reword, or condense. Include the full validator output as critique history. The implementer needs the exact finding text to understand what to fix.
3. **Re-invoke implementer in REMEDIATION MODE** — **Agent**(subagent_type="implementer", model="opus") with prompt: "REMEDIATION MODE — Fix the following BLOCKING findings. Critique history: {full validator output verbatim}. BLOCKING findings: {findings verbatim}." The coordinator MUST NOT apply fixes directly. Even for trivial one-line fixes, the implementer agent must be re-invoked. If context limits prevent implementer re-invocation, BLOCK the pipeline and suggest `/clear` then `/implement --resume`.
4. **Run pytest** — Verify 0 failures after remediation fixes.
5. **Re-run failing validators AND security-auditor** — If reviewer failed, re-run reviewer. If security-auditor failed, re-run security-auditor. **security-auditor MUST always re-run after remediation, even if it passed originally**, because remediation changes the code it certified — a PASS from STEP 10 is stale and cannot be accepted when code was modified in STEP 11. Do NOT invoke doc-master during remediation.
6. **Check verdicts** — If all pass → proceed to STEP 12. If any fail → next cycle.

**After 2 cycles still failing**:
- File GitHub issues for each remaining BLOCKING finding:
  ```bash
  gh issue create --title "Remediation: {finding summary}" --body "BLOCKING finding from pipeline run $RUN_ID that could not be auto-resolved after 2 remediation cycles.\n\nFinding:\n{finding verbatim}\n\nValidator: {reviewer|security-auditor}" --label "remediation"
  ```
- **BLOCK** the pipeline. Do NOT proceed to STEP 12. Output:
  ```
    GATE: remediation-gate — BLOCKED (2 cycles exhausted, N issues filed)
  ```

**FORBIDDEN** — You MUST NOT do any of the following:
- You MUST NOT skip the remediation loop when a validator fails
- You MUST NOT summarize or paraphrase BLOCKING findings when passing to implementer (pass VERBATIM)
- You MUST NOT exceed 2 remediation cycles (file issues and block after 2)
- You MUST NOT skip re-running security-auditor after remediation — the STEP 10 PASS is against pre-remediation code and is stale once any file is changed during remediation
- ❌ Accepting a security-auditor PASS from STEP 10 when remediation occurred in STEP 11 — the PASS is stale and must not be carried forward
- You MUST NOT invoke doc-master during remediation (doc-master is excluded from the remediation loop)
- ❌ Applying remediation fixes directly via Edit/Write/Bash instead of re-invoking the implementer agent — even for "simple" one-line fixes, the implementer agent MUST be re-invoked
- ❌ Citing context pressure, context compression, or token limits as justification for skipping implementer re-invocation — if context prevents re-invocation, BLOCK the pipeline and suggest `/clear` then `/implement --resume`

**Reviewer Out-of-Scope Finding Tracking**

When the reviewer returns `REQUEST_CHANGES` and any findings are marked as out-of-scope or deferred (e.g., "future work", "separate issue", "not in scope", "out of scope", "defer", "follow-up"), the coordinator MUST create a GitHub issue for EACH such finding:

```bash
gh issue create --title "[Review] finding-summary" --body "Out-of-scope finding from reviewer in pipeline run $RUN_ID.\n\nFinding:\n{finding verbatim}\n\nContext: {brief description of what was being implemented}" --label "auto-improvement"
```

This ensures deferred findings are tracked as searchable artifacts, not lost in session logs.

**FORBIDDEN** — Out-of-scope finding violations:
- ❌ Acknowledging an out-of-scope finding verbally without creating a tracking issue
- ❌ Deferring a finding to "future work" without filing a GitHub issue
- ❌ Logging findings only in Stop hook messages (these are not searchable artifacts)

### STEP 11.5: Skill Effectiveness Gate (Conditional)

**Progress**: Output step banner only if skill files were modified.

Check if any changed files match `skills/*/SKILL.md`:
```bash
CHANGED_SKILLS=$(python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from skill_change_detector import detect_skill_changes
import subprocess
files = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], text=True).strip().split('\n')
skills = detect_skill_changes(files)
print(','.join(skills) if skills else '')
")
```

If `CHANGED_SKILLS` is empty: skip silently (no banner needed).

If skills were modified:
1. Output step banner: `STEP 11.5/15 — Skill Effectiveness Gate`
2. For each skill, check eval status:
   ```bash
   python3 -c "
   import sys, json, os as _os
   for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
       if _os.path.isdir(_p):
           sys.path.insert(0, _p)
           break
   from skill_change_detector import get_eval_status, format_skill_eval_report
   from pathlib import Path
   skills = '$CHANGED_SKILLS'.split(',')
   results = [get_eval_status(s, repo_root=Path('.')) for s in skills if s]
   print(format_skill_eval_report(results))
   "
   ```
   - If no eval prompts for a skill: WARNING "Skill {name} modified but has no eval prompts"
   - If eval prompts exist and `OPENROUTER_API_KEY` is set: run `scripts/skill-effectiveness-check.sh --quick --skill {name}`
   - If `OPENROUTER_API_KEY` not set: WARNING "Skill eval skipped (no OPENROUTER_API_KEY)"
3. Parse results: delta < -0.10 → BLOCK. Otherwise → PASS with advisory.

**FORBIDDEN**: Blocking the pipeline when `OPENROUTER_API_KEY` is missing or when eval prompts don't exist for a skill. These are advisory warnings only.

### STEP 12: Final Verification + Doc-Drift Gate — HARD GATE

**Progress**: Output step banner (STEP 12/15 — Final Verification + Doc-Drift Gate). Output result after.

Verify all required agents ran. Default: 8 (researcher-local, researcher, planner, implementer, spec-validator, reviewer, security-auditor, doc-master). TDD-first: 9 (add test-master). If ANY of the 8 (or 9) required agents are missing, you MUST invoke them NOW. Do NOT proceed to STEP 13 with missing agents. If context pressure prevents invoking them, BLOCK the pipeline and output:
```
BLOCKED: Context limit reached. Required agents missing: [list missing agents].
Run: /clear then /implement --resume $RUN_ID to complete validation.
```
**FORBIDDEN**: Proceeding to STEP 13 with fewer than the required agent count. Missing validation agents (reviewer, security-auditor, doc-master) is a pipeline failure, not a degraded pass.

**Remediation-Aware Doc-Drift** — If STEP 11 remediation occurred (the implementer was re-invoked in REMEDIATION MODE), the STEP 10 background doc-master result is STALE — it ran against pre-remediation code and file list. You MUST:
1. DISCARD the STEP 10 background doc-master result (do not wait for it, do not parse it)
2. Get the CURRENT changed file list: `git diff --name-only HEAD~1 2>/dev/null || git diff --name-only --cached`
3. Re-invoke doc-master BLOCKING (not background): **Agent**(subagent_type="doc-master", model="sonnet") — Pass the CURRENT changed file list + feature description. Log: `[DOC-VERDICT-REINVOKE] Re-invoking doc-master after remediation with updated file list (N files)`
4. Parse the verdict from this fresh invocation — proceed to the collection point below

If STEP 11 did NOT trigger remediation (both validators passed on first try), use the original STEP 10 background result as normal (existing flow below).

**Doc-Drift Collection Point** — Collect doc-master background result (in batch mode, see implement-batch.md STEP B3 for per-issue doc-drift verdict collection):
1. Wait for doc-master to complete (it was launched in STEP 10 background).
   Use the Agent tool's return value — do NOT grep transcript files directly.
   The return value contains the agent's full output text including DOC-DRIFT-VERDICT.
   If you must parse a transcript file instead of the return value, wait at least 3 seconds
   after the agent reports completion before reading the file (filesystem flush delay — Issue #682).
2. Parse output for `DOC-DRIFT-VERDICT: PASS` or `DOC-DRIFT-VERDICT: FAIL`
2a. **Shallow Verdict Detection**: Count the words in the doc-master output. If the output is fewer than 100 words, treat it as `DOC-VERDICT-SHALLOW` — the output is too short to confirm a real semantic sweep occurred. Log `[DOC-VERDICT-SHALLOW] doc-master produced N words (minimum: 100)` and retry once with reduced context (same as step 6 retry logic below). If retry also produces fewer than 100 words or no verdict, log `[DOC-VERDICT-SHALLOW-RETRY-FAILED] doc-master still shallow after retry — proceeding with warning`.
3. If **PASS**: proceed to STEP 13
4. If **FAIL with unfixed findings**: BLOCK pipeline. Output:
   ```
   GATE: doc-drift — BLOCKED (N unfixed findings)
   ```
   Display each finding. User must address before proceeding.
5. If doc-master made fixes: stage them with `git add`
6. If doc-master returned empty output (has_output: false OR result_word_count: 0) OR no DOC-DRIFT-VERDICT found:
   - Wait 3 seconds for filesystem flush (known race condition — Issue #682)
   - Re-check the agent's return value for DOC-DRIFT-VERDICT
   - If still missing: **Retry once** with reduced context: obtain the CURRENT changed file list via `git diff --name-only HEAD~1 2>/dev/null || git diff --name-only --cached`, then re-invoke doc-master BLOCKING (not background) with ONLY this current file list and feature description (no implementer output, no reviewer output). Log: `[DOC-VERDICT-RETRY] Re-invoking doc-master with reduced context and current file list (N files)`
   - If retry produces a DOC-DRIFT-VERDICT: use that verdict
   - If retry also fails or returns empty: explicitly set `verdict = "MISSING"`, call `record_doc_verdict(session_id, issue_number, verdict)` and `record_agent_completion(session_id, 'doc-master', issue_number=issue_number, success=False)` so the audit trail is never silently lost (Issue #906 / #897). Log `[DOC-VERDICT-MISSING] doc-master produced no verdict after retry — proceeding with warning`
7. **REQUIRED: Persist verdict to completion state** (Issues #837, #852): After parsing the final verdict (whether PASS, FAIL, MISSING, or SHALLOW), call `record_doc_verdict(session_id, issue_number, verdict)` AND `record_agent_completion(session_id, 'doc-master', issue_number=issue_number, success=(verdict not in ('MISSING',)))` from `pipeline_completion_state.py`. The `record_doc_verdict` call enables the batch doc-master gate hook to verify a valid verdict was produced. The `record_agent_completion` call is required because SubagentStop doesn't fire reliably for background agents, leaving 'doc-master' absent from the completed agents set (Issue #852).

```python
from pipeline_completion_state import record_doc_verdict, record_agent_completion
record_doc_verdict(session_id, issue_number, verdict)
# Issue #852: Explicitly record doc-master completion since SubagentStop
# doesn't fire reliably for background agents
record_agent_completion(session_id, 'doc-master', issue_number=issue_number, success=(verdict not in ('MISSING',)))
```

### STEP 13: Report and Finalize

**Precondition**: STEP 11 Remediation Gate must have status PASS. If STEP 11 is BLOCKED, do NOT proceed with git operations.

**Progress**: Output the **Final Summary** table per Pipeline Progress Protocol. Include per-step elapsed times, total pipeline time (from PIPELINE_START), files changed, test counts, and security result. Then finalize pipeline state and proceed with git operations.

```bash
# Finalize pipeline state to session record (before cleanup)
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import finalize_to_session
finalize_to_session('$RUN_ID')
" 2>/dev/null || true

# Git push (if AUTO_GIT_PUSH=true)
git push origin $(git branch --show-current) 2>/dev/null || echo "Warning: Push failed"

# Dependabot security tracking (non-blocking, Issue #767)
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
try:
    from dependabot_tracker import run_dependabot_tracker, parse_owner_repo
    import subprocess
    remote = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True).strip()
    parsed = parse_owner_repo(remote)
    if parsed:
        result = run_dependabot_tracker(*parsed)
        if result['created'] > 0:
            print(f'[dependabot-tracker] Created {result[\"created\"]} security tracking issue(s)')
except Exception as e:
    print(f'[dependabot-tracker] Skipped: {e}')
" 2>/dev/null || true

# Close GitHub issue (if feature references #NNN)
COMMIT_SHA=$(git rev-parse --short HEAD)
gh issue close <number> -c "Implemented in $COMMIT_SHA" 2>/dev/null || echo "Warning: Could not close issue"

# Test-tracing warning (Issue #675) — non-blocking, informational only
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
try:
    from test_issue_tracer import TestIssueTracer
    from pathlib import Path
    tracer = TestIssueTracer(Path('.'))
    issue_number = int('$ISSUE_NUMBER') if '$ISSUE_NUMBER'.isdigit() else 0
    if issue_number > 0 and not tracer.check_issue_has_test(issue_number):
        print(f'WARNING: Issue #{issue_number} has no corresponding test. Consider adding a regression test.')
except Exception:
    pass
" 2>/dev/null || true
```

### STEP 14: Documentation Congruence — HARD GATE

**Progress**: Output step banner (STEP 14/15 — Documentation Congruence). Output gate result after.

```bash
pytest tests/unit/test_documentation_congruence.py --tb=short -q
```
If FAIL: invoke doc-master to fix, re-run until 0 failures. **FORBIDDEN**: skipping, proceeding with failures, manual edits without re-running tests.

### STEP 15: Continuous Improvement — HARD GATE

**Progress**: Output step banner (STEP 15/15 — Continuous Improvement). Output agent launch confirmation.

**Pre-dispatch**: Follow the Pre-Dispatch Ordering Protocol (above) for each agent before invoking.

**REQUIRED**: **Agent**(subagent_type="continuous-improvement-analyst", model="sonnet", run_in_background=true) — Examines session logs for bypasses, test drift, pipeline completeness.

**FORBIDDEN** — You MUST NOT do any of the following (violations = pipeline failure):
- ❌ You MUST NOT skip STEP 15 for any reason (time pressure, context limits, "already reported")
- ❌ You MUST NOT clean up pipeline state before launching the analyst
- ❌ You MUST NOT inline the analysis yourself instead of invoking the agent
- ❌ You MUST NOT treat STEP 13 as the final step — STEP 15 is mandatory

After launching analyst, confirm the agent task ID is valid, THEN cleanup: `rm -f /tmp/implement_pipeline_state.json && python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from pipeline_state import cleanup_pipeline;cleanup_pipeline('RUN_ID');from pipeline_completion_state import clear_session;clear_session('SESSION_ID')" 2>/dev/null || true`

**FORBIDDEN** (Issue #559): Cleaning up pipeline state before confirming the STEP 15 analyst agent launch succeeded. The analyst reads pipeline state — cleanup before launch loses context.

---

# LIGHT PIPELINE MODE (`--light`)

Fast pipeline for low-risk changes: markdown, config, docs, simple edits, renames. 6 steps, 5 agents. Skips research, acceptance tests, security audit, and reviewer.

**When to use**: `--light` flag, or coordinator MAY suggest it when the feature description clearly involves only markdown/config/docs/typos/renames and no new logic or security-sensitive code.

**When NOT to use**: New features with logic, security-sensitive changes, API changes, hook/agent modifications that need security review.

### STEP L0: Pre-Staged Files Check — HARD GATE

Same as STEP 1 in full pipeline.

### STEP L1: Validate PROJECT.md Alignment — HARD GATE

**Progress**: Output step banner (STEP 1/5 — Alignment).

Same as STEP 2 in full pipeline.

### STEP L2: Planner (1 agent)

**Progress**: Output step banner (STEP 2/5 — Planning, Agent: planner (Sonnet)).

**Agent**(subagent_type="planner", model="sonnet") — Pass feature description. No research input (skipped). Output: file-by-file plan, testing strategy, and `Recommended implementer model: sonnet|opus`.

### STEP L2.5: Plan Structural Validation — HARD GATE

**Progress**: Output step banner (STEP 2.5/6 — Plan Structural Validation).

**Coordinator performs these three structural checks inline** (no agent required):

1. **File paths**: The planner output contains ≥1 specific file path (matches a pattern like `path/to/file.ext` — must contain a `/` and a `.` extension or be an identifiable path token). Vague phrases like "update relevant files" do NOT count.
2. **Testing strategy**: The planner output contains a testing section OR an explicit statement about testing (e.g., "no new tests needed", "testing strategy:", "tests to write:", "test coverage:"). Either confirming or explicitly opting out is acceptable.
3. **Recommended implementer model**: The planner output contains the exact phrase `Recommended implementer model:` followed by `sonnet` or `opus`.

**On validation failure**: Re-invoke the planner once with a prompt listing the specific missing elements:

```
PLAN REJECTED — structural validation failed. Missing:
- [list each missing element from the 3 checks above]

Re-plan with explicit file paths, a testing statement, and a model recommendation.
```

**On second failure**: BLOCK the pipeline. Output:

```
PIPELINE BLOCKED — Planner failed structural validation twice.
Missing: [list elements still absent]
Resolve by providing a more specific feature description or invoking /implement without --light.
```

**FORBIDDEN**:
- ❌ You MUST NOT accept planner output with 0 specific file paths
- ❌ You MUST NOT proceed to STEP L3 when the plan contains only vague language like "update relevant files" without naming specific paths
- ❌ You MUST NOT skip structural validation for any reason (time pressure, simple feature, single-file change)

### STEP L3: Implementer + Test Gate — HARD GATE

**Progress**: Output step banner (STEP 3/6 — Implementation + Test Gate, Agent: implementer (PLANNER_RECOMMENDED_MODEL)).

**Agent**(subagent_type="implementer", model=PLANNER_RECOMMENDED_MODEL) — Pass planner output. Default to "sonnet" if planner did not specify. Must write WORKING code, no stubs.

**HARD GATE**: Same test gate as STEP 8 in full pipeline:
```bash
pytest --tb=short -q
```
Loop until **0 failures, 0 errors**.

Coverage check: `pytest tests/ --cov=plugins --cov-report=term-missing -q 2>&1 | tail -5` — must be >= baseline - 0.5%.

### STEP L3.5: Spec-Blind Validation — HARD GATE

**Progress**: Output step banner (STEP 3.5/6 — Spec-Blind Validation, Agent: spec-validator (Opus)).

Same context boundary as STEP 8.5 in the full pipeline. Pass ONLY:
- Feature description
- Changed file paths
- PROJECT.md scope sections

**FORBIDDEN**: Passing implementer output, code diffs, or any implementation details to the spec-validator.

**Agent**(subagent_type="spec-validator", model="opus") — Pass feature description + changed file paths ONLY.

Parse verdict: `SPEC-VALIDATOR-VERDICT: PASS` or `SPEC-VALIDATOR-VERDICT: FAIL`. On FAIL, re-invoke implementer with failing test names only (max 2 cycles). Block if still failing.

### STEP L4: Doc-master (1 agent)

**Progress**: Output step banner (STEP 4/5 — Documentation, Agent: doc-master (Sonnet)).

**Agent**(subagent_type="doc-master", model="sonnet", run_in_background=true) — Pass file list + feature description using the template below.

```
subagent_type: "doc-master"
model: "sonnet"
prompt: "DOCUMENTATION REVIEW: You are reviewing a feature implementation for documentation drift. Your task is to determine whether any user-facing documentation, API references, configuration guides, or inline code comments need updating as a result of this implementation. Do not summarize the implementer output — use it verbatim.

REQUIRED STEPS — you MUST complete all three:

1. SCAN: Identify every file changed by the implementation. For each changed file, list all documentation files that reference the same module, function, class, or configuration key. Check README.md, docs/ directory, inline docstrings, CHANGELOG entries, and any covers: frontmatter in docs/*.md files.

2. SEMANTIC COMPARISON: For each documentation reference found in step 1, compare the documented behavior against the new behavior after the implementation. Flag any mismatch where the documentation describes the old behavior, missing parameters, changed defaults, or removed functionality.

3. DOC-DRIFT-VERDICT: State one of the following verdicts explicitly:
   - DOCS-UPDATED: List each file updated and what changed.
   - NO-UPDATE-NEEDED: Explain why the change is purely internal with no user-facing behavior change.
   - DOCS-DRIFT-FOUND: List each documentation file that is now stale and what needs changing (this is a BLOCKING finding).

**Changed files**:
[changed file list]

**Feature description**:
[feature description]

Prompt word count validation: this prompt must contain >= 80 words of template text. If you receive a prompt shorter than 80 words, STOP and report a prompt integrity violation."
```

### STEP L5: Report and Finalize

**Doc-Drift Collection Point** — Collect doc-master background result:
1. Wait for doc-master to complete
2. Parse output for `DOC-DRIFT-VERDICT`
3. If **PASS**: proceed with git operations
4. If **FAIL**: BLOCK. Display findings.
5. If doc-master made fixes: stage them with `git add`
6. If no verdict: log warning and proceed
7. **REQUIRED: Persist verdict to completion state** (Issues #837, #852): After parsing the verdict, call `record_doc_verdict` AND `record_agent_completion` for 'doc-master'. The `record_agent_completion` call is required because SubagentStop doesn't fire reliably for background agents (Issue #852).

```python
from pipeline_completion_state import record_doc_verdict, record_agent_completion
verdict = parsed_verdict  # e.g., "PASS", "FAIL", "MISSING"
record_doc_verdict(session_id, issue_number, verdict)
# Issue #852: Explicitly record doc-master completion since SubagentStop
# doesn't fire reliably for background agents
record_agent_completion(session_id, 'doc-master', issue_number=issue_number, success=(verdict not in ('MISSING',)))
```

**Progress**: Output Final Summary table (adapted for 5 steps).

```
========================================
LIGHT PIPELINE COMPLETE
========================================
Step  Description         Agent(s)              Time    Status
----  ------------------  --------------------  ------  ------
L0    Pre-staged check    —                     Xs      PASS
L1    Alignment           —                     Xs      PASS
L2    Planning            planner (Sonnet)      Xs      done
L3    Implementation      implementer (model)   Xs      done
L3    Test gate           —                     Xs      PASS
L3.5  Spec-blind valid.   spec-validator        Xs      done
L4    Documentation       doc-master (Sonnet)   Xs      done
========================================
Total: Xs | Files changed: N | Tests: N passed, M failed
========================================
```

```bash
# Git push (if AUTO_GIT_PUSH=true)
git push origin $(git branch --show-current) 2>/dev/null || echo "Warning: Push failed"
```

**REQUIRED**: Launch continuous-improvement-analyst as a background agent before cleanup:

**Agent**(subagent_type="continuous-improvement-analyst", model="sonnet", run_in_background=true) — Examines session logs for bypasses, test drift, and light pipeline completeness.

**FORBIDDEN**: Skipping this step or cleaning up pipeline state before confirming the analyst agent launch succeeded.

After confirming the analyst task ID is valid: Cleanup: `rm -f /tmp/implement_pipeline_state.json`

**Agents (light)**: planner (Sonnet), implementer (Sonnet or Opus per planner), doc-master (Sonnet), continuous-improvement-analyst (Sonnet). 4 agents.

---

**Agents (full)**: researcher-local (Haiku), researcher (Sonnet), planner (Opus), test-master (Opus, `--tdd-first` only), implementer (per planner recommendation, default Opus), spec-validator (Opus), reviewer (Sonnet), security-auditor (Sonnet), doc-master (Sonnet), continuous-improvement-analyst (Sonnet). Default: 8 agents. TDD-first: 9 agents.

**Issue**: #203, #444 | **Version**: 3.48.0
