---
name: implement
description: "Smart code implementation with three modes (full pipeline, quick, batch)"
argument-hint: "<feature> | --quick <feature> | --batch <file> | --issues <nums> | --resume <id>"
allowed-tools: [Task, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch]
---

# /implement - Unified Smart Implementation

Smart code implementation with full pipeline, quick, and batch modes.

## Modes

| Mode | Flag | Time | Description |
|------|------|------|-------------|
| **Full Pipeline** | (default) | 15-25 min | Research → Plan → Test → Implement → Review → Security → Docs |
| **Quick** | `--quick` | 2-5 min | Implementer agent only (for pre-planned work) |
| **Batch File** | `--batch <file>` | 20-30 min/feature | Process features from file with auto-worktree |
| **Batch Issues** | `--issues <nums>` | 20-30 min/feature | Process GitHub issues with auto-worktree |
| **Resume** | `--resume <id>` | Continues | Resume interrupted batch from checkpoint |

## Usage

```bash
# Full pipeline (default) - recommended for new features
/implement add user authentication with JWT

# Quick mode - for pre-planned work or docs
/implement --quick fix typo in README

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

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 0: Parse Mode and Route

Parse ARGUMENTS: `--quick` → QUICK MODE, `--batch` → BATCH FILE MODE, `--issues` → BATCH ISSUES MODE, `--resume` → RESUME MODE, else → FULL PIPELINE.

Before routing, activate pipeline state:
```bash
echo '{"session_start": "'$(date -u +%Y-%m-%dT%H:%M:%S)'", "mode": "'$mode'"}' > /tmp/implement_pipeline_state.json
```

---

# FULL PIPELINE MODE (Default)

This is the complete 8-agent SDLC workflow. Execute steps IN ORDER.

---

### STEP 1: Validate PROJECT.md Alignment

Read `.claude/PROJECT.md`. Check feature against GOALS, SCOPE, CONSTRAINTS. If not aligned, BLOCK with reason and options (modify feature, update PROJECT.md, or don't implement). If aligned, proceed.

---

### STEP 2: Parallel Research

Invoke TWO agents in PARALLEL (single response, both Task calls at once):

1. **researcher-local** (haiku): Search codebase for patterns, files to update, similar implementations. Output JSON.
2. **researcher** (sonnet): Web research for best practices, libraries, security (OWASP), pitfalls. MUST use WebSearch tool. Output JSON with source URLs.

**Validation**: If web researcher shows 0 tool uses, retry it. Then merge both outputs for planner.

---

### STEP 3: Invoke Planner Agent

Call **planner** (opus) with merged research. Include codebase context + external guidance. Output: step-by-step plan with file-by-file breakdown, dependencies, edge cases, security, testing strategy.

---

### STEP 4: Invoke Test-Master Agent (TDD)

Tests MUST be written BEFORE implementation. Call **test-master** (opus) with planner output. Output: comprehensive test files (unit, integration, edge cases).

---

### STEP 5: Invoke Implementer Agent

Call **implementer** (opus) with planner output + test summary. CRITICAL: Must write WORKING code, no `NotImplementedError` or placeholders.

**HARD GATE: 3 Quality Principles** (enforced by `implementation_quality_gate.py`):
1. **Real Implementation**: No stubs, no `pass` placeholders
2. **Test-Driven**: ALL tests pass (`pytest --tb=short -q` — 0 failures)
3. **Complete Work**: Blockers use `TODO(blocked: reason)`, no silent stubs

**After implementer completes**, run `pytest --tb=short -q`. For EACH failure, you MUST:
1. **Fix it** — debug and fix code/test
2. **Skip it** — `@pytest.mark.skip(reason="Not yet implemented: [desc]")`
3. **Adjust it** — update test expectations to match correct behavior

Loop until **0 failures, 0 errors**. Do NOT proceed to STEP 6 with any failures.

**Coverage check** (after tests pass):
```bash
pytest tests/ --cov=plugins --cov-report=term-missing -q 2>&1 | tail -5
```
Coverage must be >= baseline - 0.5% (see `.claude/local/coverage_baseline.json`). Skip rate >10% must be fixed.

**Optional**: `python plugins/autonomous-dev/lib/step5_quality_gate.py` for machine-readable pass/fail.

---

### STEP 6: Parallel Validation (3 Agents Simultaneously)

Invoke THREE agents in PARALLEL (single response):

1. **reviewer** (sonnet): Review code quality, patterns, test coverage, error handling. Output: APPROVAL or issues.
2. **security-auditor** (opus): Scan for secrets, injection, XSS, OWASP Top 10. Output: PASS/FAIL.
3. **doc-master** (haiku): Update README, CHANGELOG, docstrings.

---

### STEP 7: Final Verification

Verify all 8 agents ran (researcher-local, researcher-web, planner, test-master, implementer, reviewer, security-auditor, doc-master). If any missing, invoke NOW.

### STEP 8: Report Completion

Report: pipeline summary (1-line per agent), files changed, tests, security PASS/FAIL, docs updated. Then cleanup: `rm -f /tmp/implement_pipeline_state.json`

---

# QUICK MODE

Invoke **implementer** (sonnet) for pre-planned work (docs, config, features with existing tests).

After completion, run `pytest --tb=short -q`. **HARD GATE**: 0 failures required (same rules as STEP 5). Then cleanup: `rm -f /tmp/implement_pipeline_state.json`

**Git Automation** (Issue #258): If `AUTO_GIT_ENABLED=true`, run:
```bash
FORCE_GIT_TRIGGER=true python3 ~/.claude/hooks/unified_git_automation.py 2>/dev/null || true
```

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

**Libraries**: `batch_orchestrator.py`, `batch_state_manager.py`, `path_utils.py`

**Issue**: #203 | **Version**: 3.47.0
