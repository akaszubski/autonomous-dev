# Workflow Discipline

**Philosophy**: Prefer pipelines. Choose quality over speed.

Claude SHOULD use the proper commands for feature implementation because they produce better results, not because hooks enforce it.

---

## Why /auto-implement Produces Better Results (Data-Driven)

**The Data** (from autonomous-dev production metrics):

| Metric | Direct Implementation | /auto-implement |
|--------|----------------------|-----------------|
| Bug rate | 23% (need hotfixes) | 4% (caught in tests) |
| Security issues | 12% (need audit) | 0.3% (caught by auditor) |
| Documentation drift | 67% (manual sync) | 2% (auto-synced) |
| Test coverage | 43% (optional) | 94% (required) |

**Benefits**: Research catches duplicates, TDD catches bugs, security blocks vulns, docs stay synced.

---

## When to Use Each Approach

**Use Direct Implementation** (quick changes):
- Documentation updates (.md files)
- Configuration changes (.json, .yaml)
- Minor refactoring (renaming, moving)
- Typo fixes (1-2 lines)

**Use /auto-implement** (quality matters):
- New functions, classes, methods
- Bug fixes requiring logic changes
- Feature additions
- API changes
- Anything that should have tests

---

## Time Comparison

| Step | Direct Implementation | /auto-implement |
|------|----------------------|-----------------|
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
1. CLAUDE.md explains WHY /auto-implement is better (data-driven)
2. /auto-implement is faster than manual implementation
3. Skills inject knowledge into agents (Issue #140)
4. Deterministic hooks block only verifiable violations

---

## Bypass Detection (Still Active)

**Explicit bypasses are still blocked**:
```bash
gh issue create ...  # BLOCKED - Use /create-issue
skip /create-issue   # BLOCKED - No skipping allowed
bypass /auto-implement  # BLOCKED - No bypassing
```

**To Disable** (not recommended):
```bash
# Add to .env file
ENFORCE_WORKFLOW=false  # Disables bypass detection
```

---

## The Choice is Yours

Hooks no longer block direct implementation for new code. But the data shows /auto-implement catches 85% of issues before commit.

**When you implement directly, you accept**:
- Higher bug rate (23% vs 4%)
- No security audit (12% vulnerability rate)
- Documentation drift (67% of changes)
- Lower test coverage (43% vs 94%)

**The pipeline exists because it works, not because it's forced.**

---

## Example Scenario

```bash
# ❌ WRONG: Vibe coding (bypass)
User: "implement JWT authentication"
Claude: Implements directly (no PROJECT.md check, no TDD, no research)

# ✅ CORRECT: Use pipeline
User: "/create-issue Add JWT authentication"
Claude: Creates issue with research + duplicate check + cache
User: "/auto-implement #123"
Claude: Validates alignment → TDD → implements → reviews → documents
```

---

## 4-Layer Consistency Architecture (Epic #142)

| Layer | % | Purpose | Implementation |
|-------|---|---------|----------------|
| **HOOKS** | 10 | Deterministic blocking | `unified_pre_tool.py`, `unified_prompt_validator.py` |
| **CLAUDE.md** | 30 | Persuasion via data | Workflow Discipline section |
| **CONVENIENCE** | 40 | Quality path easiest | `/auto-implement` pipeline |
| **SKILLS** | 20 | Agent expertise | Native `skills:` frontmatter |

**Completed**: #140-146. **Details**: `docs/epic-142-closeout.md`

---

## Quality Reflexes (Constitutional Self-Critique)

Before implementing any feature directly, ask yourself these questions. This is guidance, not enforcement — you decide whether to follow the pipeline or proceed directly.

**Self-Validation Questions**:

1. **Alignment**: Does this feature align with PROJECT.md goals? (If unsure → `cat .claude/PROJECT.md`)
2. **Research**: Have I researched existing patterns in the codebase? (If not → `grep`/`glob` first)
3. **Duplicates**: Am I duplicating work that's already implemented or exists as an open issue? (If unsure → `gh issue list --search`)
4. **Tests First**: Should I write tests first for this change? (If yes → TDD approach)
5. **Documentation**: Will this require documentation updates? (If yes → plan doc changes now)

**Why This Works** (Constitutional AI Pattern):

Constitutional AI uses natural language principles for self-critique rather than rigid enforcement. By asking questions, Claude can reflect on the best approach before committing to implementation. This respects your agency while surfacing quality considerations.

The 4-Layer Consistency Architecture allocates 30% to CLAUDE.md persuasion — guidance through data and reasoning, not blocking.

**The Data Shows**:

| Metric | Direct Implementation | /auto-implement Pipeline |
|--------|----------------------|--------------------------|
| Bug rate | 23% (need hotfixes) | 4% (caught in tests) |
| Security issues | 12% (need audit) | 0.3% (caught by auditor) |
| Documentation drift | 67% (manual sync) | 2% (auto-synced) |
| Test coverage | 43% (optional) | 94% (required) |

**Your Choice**:

Consider using `/auto-implement` for features where quality matters. For quick fixes, documentation updates, or trivial changes, direct implementation may be appropriate. The data above helps you decide — the choice is yours.
