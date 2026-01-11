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

## Bypass Detection (Still Active)

**Explicit bypasses are still blocked**:
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
