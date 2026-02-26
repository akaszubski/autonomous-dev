---
name: implement
description: "Smart code implementation with full pipeline and batch modes"
argument-hint: "<feature> | --batch <file> | --issues <nums> | --resume <id>"
allowed-tools: [Task, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch]
---

# /implement - Unified Smart Implementation

Smart code implementation with full pipeline and batch modes.

**Quick mode has been removed.** It was used as a bypass to skip research, planning, testing, review, security, and docs. All code changes go through the full pipeline. No exceptions.

## Modes

| Mode | Flag | Time | Description |
|------|------|------|-------------|
| **Full Pipeline** | (default) | 15-25 min | Research → Plan → Test → Implement → Review → Security → Docs |
| **Acceptance-First** | `--acceptance-first` | 20-30 min | Research → Plan → Acceptance Tests → Implement + Unit Tests → Review → Security → Docs |
| **Batch File** | `--batch <file>` | 20-30 min/feature | Process features from file with auto-worktree |
| **Batch Issues** | `--issues <nums>` | 20-30 min/feature | Process GitHub issues with auto-worktree |
| **Resume** | `--resume <id>` | Continues | Resume interrupted batch from checkpoint |

## Usage

```bash
# Full pipeline (default) - recommended for new features
/implement add user authentication with JWT

# Acceptance-first mode (diamond testing model) - acceptance tests before implementation
/implement --acceptance-first add user authentication with JWT

# Batch from file - multiple features with auto-worktree isolation
/implement --batch features.txt

# Batch from GitHub issues - with auto-worktree isolation
/implement --issues 72 73 74

# Resume interrupted batch
/implement --resume batch-20260110-143022
```

---

## Implementation

**You (Claude) are the coordinator for this workflow.**

**COORDINATOR FORBIDDEN LIST** (violations = pipeline failure):
- ❌ Skipping any STEP (even under context pressure or time constraints)
- ❌ Summarizing agent output instead of passing full results to next agent
- ❌ Declaring "good enough" on failing tests (STEP 5 HARD GATE is absolute)
- ❌ Running STEP 6 (validation) before STEP 5 (test gate) passes
- ❌ Combining or parallelizing sequential steps (e.g., implementer + reviewer)
- ❌ Treating STEP 8 as the final step (STEP 9 is mandatory)
- ❌ Cleaning up pipeline state before STEP 9 launches

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 0: Parse Mode and Route

Parse ARGUMENTS: `--batch` → BATCH FILE MODE, `--issues` → BATCH ISSUES MODE, `--resume` → RESUME MODE, `--acceptance-first` → FULL PIPELINE with ACCEPTANCE-FIRST variant, else → FULL PIPELINE.

**If `--quick` is passed**: Reject it. Output: "Quick mode has been removed. All code changes go through the full pipeline. Running full pipeline instead." Then proceed with FULL PIPELINE.

**Auto-detect batch issues mode**: If no explicit flag is present but ARGUMENTS contains 2+ issue references (e.g. `#621 #620` or `621 620`), auto-route to BATCH ISSUES MODE. This prevents accidentally running multiple issues on main without worktree isolation. A single `#NNN` is full pipeline mode for that issue.

Also check for `--no-cache` flag. If present, skip STEP 1.5 (research cache check) and always run fresh research in STEP 2.

**Acceptance-first mode**: When `--acceptance-first` is present, the pipeline uses the diamond testing model — acceptance tests are written BEFORE implementation (STEP 3.5), and unit tests are generated alongside code (STEP 4 is skipped). Falls back to standard TDD if `tests/genai/conftest.py` doesn't exist.

Before routing, activate pipeline state:
```bash
echo '{"session_start": "'$(date +%Y-%m-%dT%H:%M:%S)'", "mode": "'$mode'"}' > /tmp/implement_pipeline_state.json
```

---

# FULL PIPELINE MODE (Default)

This is the complete 8-agent SDLC workflow. Execute steps IN ORDER.

---

### STEP 1: Validate PROJECT.md Alignment

**HARD GATE**: Check for `.claude/PROJECT.md` in the current working directory. If it does NOT exist, BLOCK immediately:
- Output: "PROJECT.md not found. Run `/setup` or `/align --retrofit` to create one for this repo. Cannot proceed without project alignment."
- Do NOT fall back to reading PROJECT.md from other locations (plugin source, parent dirs, etc.)
- Do NOT continue the pipeline without it

If it exists, read it and check the feature against GOALS, SCOPE, CONSTRAINTS. If not aligned, BLOCK with reason and options (modify feature, update PROJECT.md, or don't implement). If aligned, proceed.

---

### STEP 1.5: Check Research Cache

Before invoking researchers, check if recent research exists for this topic:

```bash
python3 -c "
import sys; sys.path.insert(0, 'plugins/autonomous-dev/lib')
from research_persistence import check_cache, load_cached_research
cached = check_cache('FEATURE_TOPIC', max_age_days=7)
if cached:
    data = load_cached_research('FEATURE_TOPIC')
    print('CACHE_HIT')
    print(data.get('content', ''))
else:
    print('CACHE_MISS')
"
```

- **CACHE_HIT** (< 7 days old): Load cached research. Log: `"Research cache hit for <topic> — skipping STEP 2"`. Pass cached findings directly to STEP 3 (planner). Skip STEP 2 entirely.
- **CACHE_MISS**: Proceed to STEP 2 as normal.

**Note**: Cache TTL is 7 days for /implement (shorter than /create-issue's 24h because implementation needs fresher context). If the user passes `--no-cache`, skip this step.

---

### STEP 2: Parallel Research

Invoke TWO agents in PARALLEL (single response, both Task calls at once):

1. **researcher-local** (haiku): Search codebase for patterns, files to update, similar implementations. Output JSON.
2. **researcher** (sonnet): Web research for best practices, libraries, security (OWASP), pitfalls. MUST use WebSearch tool. Output JSON with source URLs.

**Validation**: If web researcher shows 0 tool uses, retry it. Then merge both outputs for planner.

**Persist research**: After merging outputs, save research for future sessions:

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'plugins/autonomous-dev/lib')
from research_persistence import save_merged_research
local_json = json.loads('''LOCAL_RESEARCH_JSON''')
web_json = json.loads('''WEB_RESEARCH_JSON''')
path = save_merged_research('FEATURE_TOPIC', local_json, web_json)
print(f'Research saved: {path}')
"
```

This persists both local and web research to `docs/research/` so future `/implement` runs on the same topic get a cache hit in STEP 1.5. The coordinator MUST substitute the actual researcher agent JSON outputs for `LOCAL_RESEARCH_JSON` and `WEB_RESEARCH_JSON`, and the feature description for `FEATURE_TOPIC`.

---

### STEP 3: Invoke Planner Agent

Call **planner** (opus) with merged research. Include codebase context + external guidance. Output: step-by-step plan with file-by-file breakdown, dependencies, edge cases, security, testing strategy.

---

### STEP 3.5: Generate Acceptance Tests (Acceptance-First Mode Only)

**Skip this step if `--acceptance-first` was NOT specified.**

Before writing unit tests, generate GenAI acceptance tests from the planner output. These define "done" from the user's perspective.

**Prerequisites check**: Verify `tests/genai/conftest.py` exists. If not, log `"GenAI infrastructure not found — falling back to standard TDD"` and skip to STEP 4.

**Generate acceptance test file**: Create `tests/genai/test_acceptance_{feature_slug}.py` with:

```python
"""Acceptance tests for: {feature description}

Generated by acceptance-first pipeline mode.
Validates feature intent using LLM-as-judge evaluation.
"""
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

@pytest.mark.genai
class TestAcceptance_{FeatureSlug}:
    """Acceptance criteria from planner output."""

    def test_{criterion_1}(self, genai):
        # Read the relevant implementation files
        context = (PROJECT_ROOT / "path/to/file").read_text()
        result = genai.judge(
            question="Does this implementation satisfy: {criterion}?",
            context=context,
            criteria="{detailed criterion from planner}",
            category="architecture",
        )
        assert result["band"] != "hard_fail", result["reasoning"]

    # ... one test per acceptance criterion from the planner
```

**Key rules**:
- One test method per acceptance criterion from the planner's output
- Use `genai.judge()` with the `category` kwarg for soft-failure band classification
- Assert `result["band"] != "hard_fail"` (allows soft failures through)
- Use descriptive test names matching the acceptance criteria
- Read actual implementation files as context (not mocked)

These tests will be validated in STEP 5 HARD GATE alongside unit tests.

---

### STEP 4: Invoke Test-Master Agent (TDD)

**Standard mode**: Tests MUST be written BEFORE implementation. Call **test-master** (opus) with:
1. **Planner output** (architecture, components, interfaces)
2. **File list** — all files to be created or modified (from planner output)
3. **GenAI infra check** — run `test -f tests/genai/conftest.py && echo "GENAI_INFRA=EXISTS" || echo "GENAI_INFRA=ABSENT"` and include the result

Test-master will run a coverage gap assessment first, then write only the test types appropriate for the change. Output: gap summary + targeted test files (unit, integration, and/or GenAI as determined).

**Acceptance-first mode**: Skip this step. Unit tests will be generated by the implementer alongside the code in STEP 5. The acceptance tests from STEP 3.5 serve as the specification; unit tests serve as regression locks.

---

### STEP 5: Invoke Implementer Agent

Call **implementer** (opus) with planner output + test summary. CRITICAL: Must write WORKING code, no `NotImplementedError` or placeholders.

**Acceptance-first mode**: Also pass the acceptance test file from STEP 3.5. The implementer MUST generate unit tests alongside code (since test-master was skipped). Acceptance tests define "done"; unit tests lock in behavior.

**HARD GATE: 3 Quality Principles** (enforced by `stop_quality_gate.py`):
1. **Real Implementation**: No stubs, no `pass` placeholders
2. **Test-Driven**: ALL tests pass (`pytest --tb=short -q` — 0 failures)
3. **Complete Work**: Blockers use `TODO(blocked: reason)`, no silent stubs

**After implementer completes**, run `pytest --tb=short -q`. For EACH failure, you MUST:
1. **Fix it** — debug and fix code/test
2. **Adjust it** — update test expectations to match correct behavior

**HARD GATE: No New Skips** — Adding `@pytest.mark.skip` is NOT an option. 0 new skips allowed. The skip decorator accumulates across sessions and LLM agents never revisit them. If a test fails, fix it or adjust expectations — never skip it.

Loop until **0 failures, 0 errors**. Do NOT proceed to STEP 6 with any failures.

**Coverage check** (after tests pass):
```bash
pytest tests/ --cov=plugins --cov-report=term-missing -q 2>&1 | tail -5
```
Coverage must be >= baseline - 0.5% (see `.claude/local/coverage_baseline.json`). Skip rate >10% must be fixed.

**Optional**: `python plugins/autonomous-dev/lib/step5_quality_gate.py` for machine-readable pass/fail.

---

### STEP 5.5: Hook Registration Check

If ANY hook file was created or modified in this implementation, verify:
1. Hook appears in ALL `plugins/autonomous-dev/templates/settings.*.json` under correct event
2. Hook appears in `plugins/autonomous-dev/config/global_settings_template.json`
3. Hook listed in `plugins/autonomous-dev/config/install_manifest.json`

**HARD GATE**: Do NOT proceed to STEP 6 if any hook is unregistered. Fix it first.

Skip this step if no hooks were created or modified.

---

### STEP 6: Parallel Validation (3 Agents Simultaneously)

Invoke THREE agents in PARALLEL (single response):

1. **reviewer** (sonnet): Review code quality, patterns, test coverage, error handling. Output: APPROVAL or issues.
2. **security-auditor** (opus): Scan for secrets, injection, XSS, OWASP Top 10. Output: PASS/FAIL.
3. **doc-master** (haiku): Update README, CHANGELOG, docstrings.

---

### STEP 7: Final Verification

Verify all 8 pipeline agents ran (researcher-local, researcher-web, planner, test-master, implementer, reviewer, security-auditor, doc-master). If any missing, invoke NOW. Note: continuous-improvement-analyst runs in STEP 9 post-report — do NOT skip it.

### STEP 8: Report and Finalize

Report: pipeline summary (1-line per agent), files changed, tests, security PASS/FAIL, docs updated.

**Git push** (if `AUTO_GIT_PUSH=true`):
```bash
git push origin $(git branch --show-current) 2>/dev/null || echo "Warning: Push failed"
```

**Close GitHub issue** (if feature references an issue number like `#123` or `issue #123`):
```bash
COMMIT_SHA=$(git rev-parse --short HEAD)
gh issue close <number> -c "Implemented in $COMMIT_SHA" 2>/dev/null || echo "Warning: Could not close issue"
```

---

### STEP 9: Continuous Improvement Analysis — HARD GATE

**FORBIDDEN** (violations = pipeline failure):
- ❌ Skipping STEP 9 for any reason (time pressure, context limits, "already reported")
- ❌ Cleaning up pipeline state (`implement_pipeline_state.json`) before launching the analyst
- ❌ Inlining the analysis yourself instead of invoking the **continuous-improvement-analyst** agent
- ❌ Treating STEP 8 as the final step — STEP 9 is mandatory

**REQUIRED**: Launch the **continuous-improvement-analyst** (sonnet) agent using the Task tool with `run_in_background: true`. The analyst examines session logs in `.claude/logs/activity/` for workflow bypasses, test drift, documentation staleness, pipeline completeness, and model intent bypasses. It checks known bypass patterns in `plugins/autonomous-dev/config/known_bypass_patterns.json` and outputs critical findings, warnings, and suggestions.

This step is NON-BLOCKING on results — the pipeline result is already reported in STEP 8. However, **launching** the analyst is mandatory. You do not need to wait for the analyst to finish, but you MUST invoke it.

After launching the analyst, cleanup: `rm -f /tmp/implement_pipeline_state.json`

---

# BATCH FILE MODE

See [implement-batch.md](implement-batch.md) for batch file processing (STEPS B1-B5).

# BATCH ISSUES MODE

See [implement-batch.md](implement-batch.md) for batch issues processing (STEPS I1-I2).

# RESUME MODE

See [implement-resume.md](implement-resume.md) for resuming interrupted batches (STEPS R1-R4).

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `MCP_AUTO_APPROVE=true` | Auto-approve for unattended operation |
| `AUTO_GIT_ENABLED=true` | Git automation |
| `AUTO_GIT_PUSH=true` | Auto-push after commit |
| `FORCE_GIT_TRIGGER=true` | Force git trigger (quick/batch modes, Issue #258) |
| `BATCH_RETRY_ENABLED=true` | Batch retry on transient errors |

---

## Technical Details

**Agents**: researcher-local (Haiku), researcher (Sonnet), planner (Opus), test-master (Opus), implementer (Opus), reviewer (Sonnet), security-auditor (Opus), doc-master (Haiku).

**Libraries**: `batch_orchestrator.py`, `batch_state_manager.py`, `path_utils.py`, `research_persistence.py`

**Issue**: #203 | **Version**: 3.47.0
