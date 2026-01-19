# Workflow Discipline

**REQUIRED**: Use `/implement` for all code changes. This is not optional.

Claude MUST use `/implement` for code changes because it catches 85% of issues before commit. The data proves this works.

---

## Why /implement Produces Better Results (Data-Driven)

**The Data** (from autonomous-dev production metrics):

| Metric | Direct Implementation | /implement |
|--------|----------------------|-----------|
| Bug rate | 23% (need hotfixes) | 4% (caught in tests) |
| Security issues | 12% (need audit) | 0.3% (caught by auditor) |
| Documentation drift | 67% (manual sync) | 2% (auto-synced) |
| Test coverage | 43% (optional) | 94% (required) |

**Benefits**: Research catches duplicates, TDD catches bugs, security blocks vulns, docs stay synced.

---

## When to Use Each Approach

**STOP AND CHECK**: Before writing ANY code, ask: "Am I about to write new logic?" If yes → `/implement`.

**Exceptions** (direct implementation allowed):
- Documentation updates (.md files only)
- Configuration changes (.json, .yaml, .toml)
- Typo fixes (1-2 lines, no logic changes)

**REQUIRED /implement** (no exceptions):
- New functions, classes, methods
- Bug fixes requiring logic changes
- Feature additions
- API changes
- Anything that should have tests

**Default Rule**: If unsure, use `/implement`. Quality-safe default.

---

## Time Comparison

| Step | Direct Implementation | /implement |
|------|----------------------|-----------|
| Research | Manual (you do it) | Automatic (2-3 min) |
| Tests | Manual (you write them) | Automatic (TDD enforced) |
| Security | Manual (you audit) | Automatic (security-auditor) |
| Docs | Manual (you update) | Automatic (doc-master) |
| Git | Manual (you commit/push) | Automatic (auto-git) |
| **Total effort** | High (all manual) | Low (orchestrated) |
| **Total time** | Variable | 15-25 min |

---

## Enforcement: Deterministic Only (Issue #141)

**What IS enforced** (deterministic rules):
- `gh issue create` blocked → Use `/create-issue` instead
- `.env` edits blocked → Protects secrets
- `git push --force` blocked → Protects history
- Quality gates → Tests must pass before commit

**What is NOT enforced** (intent detection removed):
- "implement X" patterns → Not detected (Claude rephrases)
- Line count thresholds → Not detected (Claude makes small edits)
- "Significant change" detection → Not detected (easily bypassed)

**Why intent detection was removed** (Issue #141):
- Hooks see tool calls, not Claude's reasoning
- Claude bypasses via: Bash heredocs, small edits, rephrasing
- False positives frustrate users (doc updates blocked)
- False negatives miss violations (small cumulative edits)

**The new approach**: Persuasion + Convenience + Skills
1. CLAUDE.md explains WHY /implement is better (data-driven)
2. /implement is faster than manual implementation
3. Skills inject knowledge into agents (Issue #140)
4. Deterministic hooks block only verifiable violations

---

## Graduated Enforcement Levels (Issue #246)

The /implement workflow enforcement supports graduated levels to balance discipline and friction:

### Enforcement Levels

| Level | Behavior | Use Case | Environment Variable |
|-------|----------|----------|----------------------|
| **OFF** | Allow all changes, no enforcement | Development/learning | `ENFORCEMENT_LEVEL=off` |
| **WARN** | Allow all changes, log warnings to stderr | Monitoring without friction | `ENFORCEMENT_LEVEL=warn` |
| **SUGGEST** | Allow all changes, suggest /implement in response | Default - guidance without blocking | `ENFORCEMENT_LEVEL=suggest` (default) |
| **BLOCK** | Deny significant changes, require /implement | Strict teams, production | `ENFORCEMENT_LEVEL=block` |

### Configuration

**New Environment Variable** (recommended):
```bash
# Set enforcement level
ENFORCEMENT_LEVEL=off      # Disable enforcement
ENFORCEMENT_LEVEL=warn     # Warn on violations
ENFORCEMENT_LEVEL=suggest  # Suggest /implement (default)
ENFORCEMENT_LEVEL=block    # Block violations (strictest)
```

**Legacy Variable** (backward compatible):
```bash
ENFORCE_WORKFLOW_STRICT=false   # Maps to OFF (disabled)
ENFORCE_WORKFLOW_STRICT=true    # Maps to BLOCK (strictest)
```

**Precedence**: `ENFORCEMENT_LEVEL` takes precedence over `ENFORCE_WORKFLOW_STRICT`

### Default Behavior (v3.49.0+)

By default, enforcement level is **SUGGEST**:
- Claude can make code changes directly
- If significant code detected, Claude gets a suggestion to use `/implement`
- No blocking, no friction - purely informational
- Users can opt-in to stricter levels as needed

### What Each Level Does

**OFF**:
- Disables all enforcement for the hook
- All edits allowed without restriction
- No logging or warnings
- Use in early development phases

**WARN**:
- Allows all edits to proceed
- Logs violations to stderr with timestamps
- Useful for monitoring without disrupting workflows
- Violations appear in console/logs for auditing

**SUGGEST** (Default):
- Allows all edits to proceed
- Includes /implement suggestion in Claude's response when significant code detected
- Non-blocking guidance toward better workflow
- Balances discipline with user friction
- Most suitable for most teams

**BLOCK**:
- Denies significant code edits (new functions, classes, >10 lines)
- Forces use of /implement for meaningful work
- Allows minor edits (typos, config, docs)
- Strictly enforces workflow discipline
- Best for teams with high-quality requirements or regulated environments

---

## Enforcement Layers (Issue #250)

The /implement workflow is enforced across three deterministic layers:

### Layer 1: Git Bypass Prevention (block_git_bypass Hook)

**PreCommit hook that blocks git command bypasses**.

Blocked commands:
```bash
git commit --no-verify        # BLOCKED - Bypasses pre-commit hooks
git commit --no-gpg-sign      # BLOCKED - Bypasses GPG signing
```

What this prevents:
- Committing code that fails tests
- Committing code without running security checks
- Bypassing documentation validation
- Bypassing linting and formatting

Configuration:
```bash
# .env file
ALLOW_GIT_BYPASS=false  # Default: false (strict)
ALLOW_GIT_BYPASS=true   # Emergency bypass only (not recommended)
```

Log location: `logs/workflow_violations.log` (JSON Lines format)

### Layer 2: Protected Paths Enforcement (enforce_implementation_workflow Hook)

**PreToolUse hook that enforces code quality with configurable levels** (Issue #246).

This hook works at four graduated levels (new in v3.49.0):

**OFF**: Allow all changes unconditionally
**WARN**: Allow changes but warn about significant code
**SUGGEST** (default): Allow changes, suggest /implement when significant code detected
**BLOCK**: Deny significant code changes, require /implement workflow

Protected paths (always protected, even at SUGGEST level):
```
.claude/commands/*.md        # Command definitions
.claude/agents/*.md          # Agent definitions
plugins/autonomous-dev/lib/* # Core library infrastructure
```

What this prevents:
- Significant code changes outside the /implement workflow
- Claude autonomously editing system paths (protected at all levels)
- Bypassing the /implement pipeline for meaningful work

Exemptions:
- Allowed agents: `implementer`, `test-master`, `brownfield-analyzer`, `setup-wizard`, `project-bootstrapper`
- These agents ARE part of the /implement workflow

Configuration:
```bash
# .env file
ENFORCEMENT_LEVEL=off       # Disable enforcement
ENFORCEMENT_LEVEL=warn      # Warn on violations
ENFORCEMENT_LEVEL=suggest   # Suggest /implement (default)
ENFORCEMENT_LEVEL=block     # Strictly enforce /implement

# Legacy variable (backward compatible)
ENFORCE_WORKFLOW_STRICT=false   # Maps to OFF
ENFORCE_WORKFLOW_STRICT=true    # Maps to BLOCK
```

Violations logged to: `logs/workflow_violations.log` (JSON Lines format)

### Layer 3: Workflow Violation Audit Logging

**workflow_violation_logger.py library provides audit trail**.

Logged violation types:
- `direct_implementation`: Code changes outside /implement workflow
- `git_bypass_attempt`: Attempt to bypass hooks (--no-verify, --no-gpg-sign)
- `protected_path_edit`: Edits to protected system paths

Log format (JSON Lines, one event per line):
```json
{"timestamp": "2026-01-19T12:34:56+00:00", "violation_type": "git_bypass_attempt", "agent_name": "claude", "reason": "--no-verify flag detected", "command": "git commit --no-verify -m 'bypass'"}
```

Query violations:
```python
from workflow_violation_logger import parse_violation_log, get_violation_summary

# Get all violations
entries = parse_violation_log()

# Filter by type
bypasses = parse_violation_log(violation_type_filter="git_bypass_attempt")

# Get statistics
stats = get_violation_summary()
print(stats)
# {"total_violations": 5, "by_type": {"git_bypass_attempt": 3, "protected_path_edit": 2}, "by_agent": {"claude": 5}}
```

Log rotation:
- Maximum size: 10MB per file
- Backups kept: 10 rotated files
- Format: `workflow_violations.log.YYYYMMDD_HHMMSS`

---

## Explicit Bypass Detection (Still Active)

**Explicit bypasses in user prompts are still blocked**:
```bash
gh issue create ...  # BLOCKED - Use /create-issue
skip /create-issue   # BLOCKED - No skipping allowed
bypass /implement    # BLOCKED - No bypassing
```

**To Disable** (not recommended):
```bash
# Add to .env file
ENFORCE_WORKFLOW=false  # Disables bypass detection
```

---

## Why This is Mandatory

Hooks don't block direct implementation (Intent detection doesn't work - Issue #141). But `/implement` is still REQUIRED by instruction.

**If you skip `/implement`, you cause**:
- Higher bug rate (23% vs 4%)
- Security vulnerabilities (12% vs 0.3%)
- Documentation drift (67% of changes)
- Lower test coverage (43% vs 94%)

**The rule**: Use `/implement` for code changes. The data proves it works.

---

## Example Scenario

```bash
# ❌ WRONG: Vibe coding (bypass)
User: "implement JWT authentication"
Claude: Implements directly (no PROJECT.md check, no TDD, no research)

# ✅ CORRECT: Use pipeline
User: "/create-issue Add JWT authentication"
Claude: Creates issue with research + duplicate check + cache
User: "/implement #123"
Claude: Validates alignment → TDD → implements → reviews → documents
```

---

## 4-Layer Consistency Architecture (Epic #142)

| Layer | % | Purpose | Implementation |
|-------|---|---------|----------------|
| **HOOKS** | 10 | Deterministic blocking | `unified_pre_tool.py`, `unified_prompt_validator.py` |
| **CLAUDE.md** | 30 | Persuasion via data | Workflow Discipline section |
| **CONVENIENCE** | 40 | Quality path easiest | `/implement` pipeline |
| **SKILLS** | 20 | Agent expertise | Native `skills:` frontmatter |

**Completed**: #140-146. **Details**: `docs/epic-142-closeout.md`

---

## Quality Reflexes (Mandatory Self-Check)

**BEFORE writing any code**, you MUST ask:

1. **Am I about to write new logic?** → If yes, STOP and use `/implement`
2. **Is this just docs/config/typo?** → If yes, proceed directly
3. **Am I unsure?** → Use `/implement` (quality-safe default)

**Why This is Required**:

| Metric | Direct Implementation | /implement Pipeline |
|--------|----------------------|--------------------------|
| Bug rate | 23% (need hotfixes) | 4% (caught in tests) |
| Security issues | 12% (need audit) | 0.3% (caught by auditor) |
| Documentation drift | 67% (manual sync) | 2% (auto-synced) |
| Test coverage | 43% (optional) | 94% (required) |

**The Rule**: `/implement` is required for code changes. Exceptions are documented above (docs, config, typos only).
