# Maintaining the Core Philosophy

**Last Updated**: 2025-11-03
**Version**: v3.1.0

---

## Overview

This guide explains what you need to keep updated as you improve and iterate to maintain the core philosophy:

> **"Trust the model, enforce via hooks, enhance via agents"**

---

## The Golden Rule

### UPDATE PROJECT.md FIRST, EVERYTHING ELSE FOLLOWS

- **PROJECT.md** = Source of truth for alignment
- **orchestrator** reads it before any feature work
- **Hooks** validate against it on every commit
- **Agents** reference it for context
- **Documentation** mirrors it automatically

**If these get out of sync, the philosophy breaks.**

---

## Priority Matrix: What to Update When

### 🔴 ALWAYS Update (Critical Path)

These are the backbone of the system. Update these first:

#### 1. **PROJECT.md** (Most Critical)

**Location**: `.claude/PROJECT.md`

**When to update:**
- Strategy or direction changes
- New goals added or completed
- Scope boundaries shift (in-scope vs out-of-scope)
- New constraints emerge (technical, business, compliance)
- Architecture decisions made

**Why critical:**
- orchestrator agent reads this FIRST before validating any feature
- `validate_project_alignment.py` hook checks all commits against this
- All 19 agents reference this for context
- This IS the alignment mechanism

**Example workflow:**
```bash
# Strategy change: Moving from REST to GraphQL

# 1. UPDATE PROJECT.md FIRST
vim .claude/PROJECT.md
# Update SCOPE section:
#   In Scope: GraphQL API endpoints
#   Out of Scope: REST API (deprecated)

# 2. Commit the strategic change
git add .claude/PROJECT.md
git commit -m "docs: update scope to GraphQL architecture"

# 3. NOW implement features
# orchestrator will validate new features against GraphQL scope
# Hooks will enforce GraphQL patterns
# Documentation will stay aligned
```

**Sections to maintain:**
```markdown
## GOALS
- Your primary objectives (what success looks like)
- Success metrics (how you measure progress)

## SCOPE
### In Scope
- Features you're building (what's allowed)

### Out of Scope
- Features to avoid (what's NOT allowed)

## CONSTRAINTS
- Technical constraints (languages, frameworks, platforms)
- Business constraints (budget, timeline, team size)
- Compliance constraints (security, privacy, regulations)

## ARCHITECTURE
- Current architecture decisions
- Technology stack
- Design patterns
```

#### 2. **orchestrator.md** (Gatekeeper Behavior)

**Location**: `plugins/autonomous-dev/agents/orchestrator.md`

**When to update:**
- Coordination logic needs adjustment
- Agent invocation patterns change
- Workflow sequence needs modification
- Skills usage patterns evolve

**Why critical:**
- Controls WHEN other agents are invoked
- First line of PROJECT.md alignment validation
- Determines the autonomous workflow

**Key sections:**
```yaml
---
description: "Master coordinator - validates PROJECT.md alignment..."
tools: [Task, Read, Bash]
---

# System prompt defining coordination behavior
# Lines 1-150: Core coordination logic

## Skills Available (lines 74-109)
- List all 19 skills with descriptions
- Tell orchestrator HOW to reference skills
- Define WHEN to invoke specialist agents
```

**Update pattern:**
```bash
# Test current behavior
/auto-implement "add feature X"
# Review session log: docs/sessions/*orchestrator*.md

# If orchestrator behavior is wrong:
vim plugins/autonomous-dev/agents/orchestrator.md
# Update coordination logic

# Test again
/auto-implement "add feature Y"
# Verify improved behavior
```

#### 3. **settings.local.json** (Enforcement Rules)

**Location**: `.claude/settings.local.json`

**When to update:**
- Enable/disable strict mode
- Add new quality gates (PreCommit hooks)
- Change enforcement priorities
- Performance tuning (disable expensive hooks during dev)
- Feature flag adjustments

**Why critical:**
- Controls which hooks run (enforcement)
- Contains customInstructions (Claude's behavior)
- Defines when orchestrator is triggered
- Sets quality gate thresholds

**Critical sections:**
```json
{
  "customInstructions": "STRICT MODE: When user requests feature...",
  "hooks": {
    "UserPromptSubmit": [
      {
        "description": "Auto-detect feature requests",
        "hooks": [{
          "type": "command",
          "command": "python .claude/hooks/detect_feature_request.py"
        }]
      }
    ],
    "PreCommit": [
      {
        "description": "Quality gates",
        "hooks": [
          {"command": "python .claude/hooks/validate_project_alignment.py || exit 1"},
          {"command": "python .claude/hooks/enforce_orchestrator.py || exit 1"},
          {"command": "python .claude/hooks/security_scan.py || exit 1"}
        ]
      }
    ]
  }
}
```

**Iteration pattern:**
```bash
# During development: Disable strict enforcement
vim .claude/settings.local.json
# Change: "command": "python .claude/hooks/enforce_orchestrator.py || exit 1"
# To:     "command": "true"  # Placeholder (does nothing)

# After testing: Enable enforcement
# Change back to actual hook command

# Production: Full enforcement with all hooks enabled
```

---

### 🟡 FREQUENTLY Update (Quality Path)

Update these as you discover better patterns:

#### 4. **Agent Prompts** (Behavior Tuning)

**Location**: `plugins/autonomous-dev/agents/*.md`

**When to update:**
- Agent behavior not matching expectations
- New patterns discovered through usage
- Better prompts found through experimentation
- Skills need to be referenced differently

**Key agents to watch:**
- `orchestrator.md` - Coordination logic (most critical)
- `alignment-validator.md` - PROJECT.md checking logic
- `reviewer.md` - Quality standards enforcement
- `security-auditor.md` - Security pattern detection
- `implementer.md` - Code generation patterns
- `test-master.md` - TDD workflow

**Update pattern:**
```bash
# 1. Identify issue
# Agent not using skills? Not invoking sub-agents? Wrong decisions?

# 2. Review session log
cat docs/sessions/$(ls -t docs/sessions/*agent-name*.md | head -1)

# 3. Update agent prompt
vim plugins/autonomous-dev/agents/agent-name.md

# 4. Test behavior
# Invoke agent manually or via /auto-implement

# 5. Verify improvement
# Check session log for updated behavior
```

#### 5. **GenAI Prompts** (Decision Accuracy)

**Location**: `plugins/autonomous-dev/hooks/genai_prompts.py`

**When to update:**
- Hook decisions are inaccurate (false positives/negatives)
- New classification categories needed
- Better prompt engineering discovered
- Accuracy metrics below target

**Current prompts (6):**
```python
SECRET_ANALYSIS_PROMPT        # Lines 24-39  (Real vs test secrets)
INTENT_CLASSIFICATION_PROMPT  # Lines 51-64  (Feature vs refactor vs docs)
COMPLEXITY_ASSESSMENT_PROMPT  # Lines 78-94  (Simple vs complex changes)
DESCRIPTION_VALIDATION_PROMPT # Lines 109-122 (Accurate vs misleading docs)
DOC_GENERATION_PROMPT         # Lines 136-146 (Auto-generate descriptions)
FILE_ORGANIZATION_PROMPT      # Lines 161-202 (Semantic file placement)
```

**Version control pattern:**
```bash
# BEFORE changing prompt: Document current performance
git commit -m "docs: SECRET_ANALYSIS_PROMPT accuracy at 92%"

# Test new prompt
vim plugins/autonomous-dev/hooks/genai_prompts.py
# Update prompt

# Run tests
python .claude/hooks/security_scan.py
# Measure accuracy improvement

# AFTER changing: Document improvement
git commit -m "feat: improve SECRET_ANALYSIS_PROMPT accuracy from 92% to 97%"
```

**Testing prompts:**
```bash
# Test secret detection
echo "API_KEY=test_12345" | python .claude/hooks/security_scan.py

# Test intent classification
echo "implement user auth" | python .claude/hooks/auto_generate_tests.py

# Test complexity assessment
python .claude/hooks/auto_update_docs.py
```

#### 6. **Skills** (Knowledge Currency)

**Location**: `plugins/autonomous-dev/skills/*/skill.md`

**When to update:**
- New patterns discovered in code reviews
- Best practices evolve (framework updates, new standards)
- Technology standards change (Python 3.13, new libraries)
- Project conventions shift

**Structure:**
```yaml
---
auto_activate: true
keywords: ["authentication", "security", "API keys"]
description: Security patterns and API key management
---

# Skill Content

## Best Practices
[Pattern documentation]

## Examples
[Code examples]

## Anti-Patterns
[What to avoid]
```

**Update trigger examples:**
```bash
# Code review reveals new pattern
# → Add to skills/code-review/skill.md

# Bug caused by missing pattern
# → Update skills/testing-guide/skill.md

# New tool adopted (e.g., Ruff replaces Black)
# → Update skills/python-standards/skill.md

# Framework upgrade (e.g., FastAPI v0.100+)
# → Update skills/api-design/skill.md
```

**Maintenance workflow:**
```bash
# 1. Identify pattern to document
# From: code review, bug post-mortem, team discussion

# 2. Add to appropriate skill
vim plugins/autonomous-dev/skills/[category]/skill.md

# 3. Update agent prompts to reference new pattern
vim plugins/autonomous-dev/agents/[relevant-agent].md
# Add reference to skill in system prompt

# 4. Test that agents use the pattern
/auto-implement "feature using new pattern"
# Check session log for skill invocation
```

---

### 🟢 PERIODICALLY Review (Validation Path)

Check these regularly to ensure alignment:

#### 7. **Documentation** (Reality Mirror)

**Key files:**
- `README.md` - User-facing (what it does)
- `ARCHITECTURE-EXPLAINED.md` - How it works (500+ lines)
- `CLAUDE.md` - Development standards
- `docs/UPDATES.md` - Changelog
- `CHANGELOG.md` - Version history

**Auto-validation hooks:**
- `validate_docs_consistency.py` - Checks counts match reality
- `auto_fix_docs.py` - Auto-generates missing documentation
- `auto_update_docs.py` - Syncs code changes to docs
- `validate_claude_alignment.py` - Detects documentation drift

**Alignment pattern:**
```bash
# After adding new agent:
# 1. Agent count in PROJECT.md → updates automatically (hook)
# 2. Agent count in README.md → updates automatically (hook)
# 3. Agent count in CLAUDE.md → must check manually
python .claude/hooks/validate_claude_alignment.py

# If drift detected:
vim CLAUDE.md  # Update counts, versions, descriptions
git add CLAUDE.md
git commit -m "docs: fix CLAUDE.md alignment (19 agents, 8 commands)"
```

**Review schedule:**
```bash
# Weekly: Check for drift
python .claude/hooks/validate_docs_consistency.py
python .claude/hooks/validate_claude_alignment.py

# Monthly: Comprehensive audit
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --audit --genai

# Per release: Full documentation review
# - README.md (user-facing accuracy)
# - ARCHITECTURE-EXPLAINED.md (technical accuracy)
# - CLAUDE.md (standards currency)
# - CHANGELOG.md (release notes)
```

#### 8. **Session Logs** (Execution Evidence)

**Location**: `docs/sessions/YYYY-MM-DD-HH-MM-SS-agent-name.md`

**What to review:**
- Are agents being invoked as expected?
- Are quality gates catching issues?
- Are there patterns of failures?
- Is orchestrator running for all features?

**Audit commands:**
```bash
# Check orchestrator invocation rate
total_sessions=$(ls docs/sessions/*.md 2>/dev/null | wc -l)
orchestrator_sessions=$(ls docs/sessions/*orchestrator*.md 2>/dev/null | wc -l)
echo "orchestrator invoked in $orchestrator_sessions of $total_sessions sessions"

# Review recent session quality
tail -50 docs/sessions/$(ls -t docs/sessions/ | head -1)

# Find agent usage patterns
echo "Agent invocation counts:"
for agent in orchestrator researcher planner test-master implementer reviewer security-auditor doc-master; do
    count=$(ls docs/sessions/*${agent}*.md 2>/dev/null | wc -l)
    echo "  $agent: $count"
done

# Check for error patterns
grep -i "error\|failed\|blocked" docs/sessions/*.md | wc -l

# Find most recent orchestrator validation
ls -lt docs/sessions/*orchestrator*.md | head -1
```

**Review frequency:**
- **Daily** (during active development): Check if orchestrator is being invoked
- **Weekly**: Review error patterns
- **Monthly**: Analyze agent usage trends

#### 9. **Hook Configuration Performance**

**What to monitor:**
- Hook execution time (should be < 10 seconds total)
- GenAI API costs (Haiku usage)
- False positive/negative rates
- Hook failure patterns

**Performance tuning:**
```bash
# Measure hook execution time
time python .claude/hooks/validate_project_alignment.py
time python .claude/hooks/security_scan.py
time python .claude/hooks/auto_generate_tests.py

# If too slow (> 10s), consider:
# 1. Disable GenAI for specific hooks during dev
export GENAI_SECURITY_SCAN=false

# 2. Use caching for expensive operations
# (Already implemented in WebFetch tool)

# 3. Reduce scope of analysis
# (Edit hook to check only changed files)
```

---

### 🔵 AS NEEDED (Enhancement Path)

Update these for experimentation and evolution:

#### 10. **Feature Flags** (Control Knobs)

**Available flags:**
```bash
# GenAI features (in genai_prompts.py)
export GENAI_SECURITY_SCAN=true|false       # Secret detection
export GENAI_TEST_GENERATION=true|false     # Intent classification
export GENAI_DOC_UPDATE=true|false          # Complexity assessment
export GENAI_DOCS_VALIDATE=true|false       # Description validation
export GENAI_DOC_AUTOFIX=true|false         # Doc generation
export GENAI_FILE_ORGANIZATION=true|false   # File placement

# Debug flags
export DEBUG_GENAI=true   # Verbose GenAI logging
```

**Experimentation pattern:**
```bash
# Disable expensive feature during rapid iteration
export GENAI_SECURITY_SCAN=false
# ... make many commits quickly ...

# Re-enable for final validation
unset GENAI_SECURITY_SCAN  # Defaults to true
git commit -m "feat: final implementation with full validation"
```

#### 11. **GitHub Issues** (Evolution Roadmap)

**Pattern:**
- Research findings → GitHub issues
- Philosophy conflicts → Discussion + decision + PROJECT.md update
- New capabilities → Issue + implementation + documentation

**Current active issues:**
- #37 - Enable auto-orchestration
- #35 - Agents use skills more actively
- #34 - Pattern-based orchestration
- #29 - Pipeline verification

**Maintenance:**
```bash
# Close completed issues
gh issue close 37 --comment "Implemented in commit abc123"

# Reference commits in issues
git commit -m "feat: enable auto-orchestration (closes #37)"

# Update issue scope if needed
gh issue edit 35 --body "Updated scope: ..."
```

---

## The Core Philosophy Checklist

Before any major change, ask these questions:

### 1. ✅ Does this trust the model?

**Good (Aligned):**
- Adding GenAI reasoning to hooks
- Letting Claude decide which agents to invoke
- Using customInstructions to guide behavior
- Semantic understanding via LLMs

**Bad (Not Aligned):**
- Rigid if/else logic in Python
- Hardcoded sequences of agent invocations
- Static pattern matching (regex without GenAI fallback)
- Forcing specific workflow order

### 2. ✅ Is enforcement via hooks?

**Good (Aligned):**
- PreCommit hooks validate alignment
- Hooks block commits on failure
- 100% reliability (hooks always run)
- Hooks check evidence (session logs, file counts)

**Bad (Not Aligned):**
- Relying on agents to enforce standards
- Hoping developers follow process
- Optional validation steps
- Manual review processes

### 3. ✅ Is intelligence via agents?

**Good (Aligned):**
- Agents provide expertise and guidance
- Agents research patterns
- Agents make design decisions
- Agents coordinate specialists

**Bad (Not Aligned):**
- Hooks making complex decisions
- Hooks containing business logic
- Hooks implementing features
- Hooks doing AI work without GenAI

### 4. ✅ Does PROJECT.md control alignment?

**Good (Aligned):**
- orchestrator reads PROJECT.md first
- Hooks validate against PROJECT.md
- Dynamic scope changes via PROJECT.md updates
- All agents reference PROJECT.md

**Bad (Not Aligned):**
- Hardcoded scope checks in Python
- Agent prompts with static scope definitions
- Configuration files defining business logic
- Multiple sources of truth

### 5. ✅ Are skills used progressively?

**Good (Aligned):**
- Agents invoke skills as needed
- Skills loaded on-demand
- Progressive disclosure pattern
- Context stays small

**Bad (Not Aligned):**
- All skills loaded upfront
- Context bloat from unused skills
- Skills duplicating agent knowledge
- No skill invocation tracking

### 6. ✅ Is documentation auto-synced?

**Good (Aligned):**
- Hooks auto-update documentation
- Hooks validate documentation accuracy
- Documentation mirrors code automatically
- Drift detected and blocked

**Bad (Not Aligned):**
- Manual documentation updates
- Documentation as afterthought
- No validation of accuracy
- Drift accumulates silently

---

## Quick Reference: What to Update When

### ✨ You add a new agent

```bash
# 1. Create agent file
touch plugins/autonomous-dev/agents/new-agent.md
vim plugins/autonomous-dev/agents/new-agent.md

# 2. Counts update automatically (hooks)
git commit -m "feat: add new-agent for X capability"
# → PROJECT.md count updates (hook)
# → README.md count updates (hook)

# 3. Check CLAUDE.md alignment
python .claude/hooks/validate_claude_alignment.py
# If drift: update CLAUDE.md manually

# 4. Update orchestrator if needed
vim plugins/autonomous-dev/agents/orchestrator.md
# Add new-agent to coordination logic
```

### 🎯 You change project direction

```bash
# 1. UPDATE PROJECT.md FIRST (most critical)
vim .claude/PROJECT.md
# Update GOALS, SCOPE, CONSTRAINTS

# 2. Commit strategic change
git add .claude/PROJECT.md
git commit -m "docs: change direction to X architecture"

# 3. orchestrator reads new alignment automatically
# All future features validated against new SCOPE

# 4. Optional: Update agent prompts if needed
# (Only if agents need to know about new patterns)
```

### 🔍 You discover a new pattern

```bash
# 1. Add to relevant skill
vim plugins/autonomous-dev/skills/[category]/skill.md
# Document the pattern

# 2. Update agent prompts to reference skill
vim plugins/autonomous-dev/agents/[agent].md
# Tell agent to use the skill

# 3. Test that agents invoke skill
/auto-implement "feature using new pattern"
grep "skill" docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### 🔒 You change enforcement rules

```bash
# 1. Update hook configuration
vim .claude/settings.local.json
# Add/remove/modify hooks

# 2. Test with sample feature
/auto-implement "test feature"
git commit -m "test: verify new enforcement"

# 3. Document in architecture guide
vim docs/ARCHITECTURE-EXPLAINED.md
# Explain the new enforcement rule
```

### ⚡ Hook decisions are wrong

```bash
# 1. Identify which prompt is wrong
python .claude/hooks/[hook-name].py
# Check output/logs

# 2. Update prompt
vim plugins/autonomous-dev/hooks/genai_prompts.py
# Improve the prompt (lines X-Y)

# 3. Test accuracy improvement
python .claude/hooks/[hook-name].py
# Measure false positive/negative rate

# 4. Commit with metrics
git commit -m "feat: improve [PROMPT_NAME] accuracy from X% to Y%"
```

### 🤖 Agent behavior is wrong

```bash
# 1. Review session log
cat docs/sessions/$(ls -t docs/sessions/*agent-name*.md | head -1)

# 2. Update agent system prompt
vim plugins/autonomous-dev/agents/agent-name.md

# 3. Test with /auto-implement
/auto-implement "test feature"

# 4. Verify behavior in session log
cat docs/sessions/$(ls -t docs/sessions/*agent-name*.md | head -1)
grep "expected behavior" [session-file]
```

---

## Maintenance Schedules

### Daily (During Active Development)

```bash
# Check orchestrator invocation
ls -lt docs/sessions/*orchestrator*.md | head -1

# Review latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)

# Quick alignment check
git status  # PreCommit hooks catch issues automatically
```

### Weekly

```bash
# Documentation alignment
python .claude/hooks/validate_docs_consistency.py
python .claude/hooks/validate_claude_alignment.py

# Agent usage patterns
echo "Agent invocations this week:"
find docs/sessions -name "*.md" -mtime -7 | \
  xargs basename -a | \
  cut -d'-' -f6 | \
  sort | uniq -c | sort -rn

# Hook performance
echo "Hook execution times:"
for hook in validate_project_alignment security_scan auto_generate_tests; do
    echo -n "  $hook: "
    time python .claude/hooks/${hook}.py 2>&1 | grep real
done
```

### Monthly

```bash
# Comprehensive documentation audit
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --audit --genai

# Review PROJECT.md against reality
cat .claude/PROJECT.md
# Ask: Are GOALS still current? Is SCOPE accurate?

# Agent effectiveness review
cat docs/sessions/*.md | grep -i "error\|failed\|blocked" | wc -l
# Compare to previous month

# Skills currency check
ls -lt plugins/autonomous-dev/skills/*/skill.md | head -10
# Ask: Are these skills still current?
```

### Per Release

```bash
# Full documentation review
# - README.md (user-facing accuracy)
# - ARCHITECTURE-EXPLAINED.md (technical accuracy)
# - CLAUDE.md (standards currency)
# - PROJECT.md (strategic alignment)
# - CHANGELOG.md (release notes)

# Update version numbers
vim PROJECT.md  # Update version in header
vim CLAUDE.md   # Update version in header
vim README.md   # Update version in badges

# Tag release
git tag -a v3.1.0 -m "Release v3.1.0: [description]"
git push origin v3.1.0
```

---

## Warning Signs of Philosophy Drift

### 🚨 Red Flags

1. **Hardcoded scope checks in Python**
   - Fix: Move to PROJECT.md, let orchestrator validate

2. **Agents not being invoked**
   - Check: `ls docs/sessions/*orchestrator*.md | wc -l`
   - Fix: Enable detect_feature_request.py hook (Issue #37)

3. **Documentation out of sync**
   - Check: `python .claude/hooks/validate_docs_consistency.py`
   - Fix: Update docs, commit, let hooks validate

4. **Rigid Python orchestration**
   - Check: grep "subprocess.run.*agents" in codebase
   - Fix: Remove, use GenAI-powered coordination

5. **Context bloat**
   - Check: Token usage > 50K after 3-4 features
   - Fix: Use /clear, improve session logging

6. **Manual enforcement**
   - Check: "Please remember to..." in docs
   - Fix: Add hook to enforce automatically

### ✅ Health Indicators

1. **orchestrator runs for all features**
   ```bash
   # Should see orchestrator sessions regularly
   ls -lt docs/sessions/*orchestrator*.md | head -5
   ```

2. **PROJECT.md is updated before features**
   ```bash
   # PROJECT.md commits should precede feature commits
   git log --oneline .claude/PROJECT.md | head -5
   ```

3. **Hooks catch issues before merge**
   ```bash
   # Should see hook validation messages in git output
   git commit -m "test"  # Shows hook execution
   ```

4. **Documentation stays aligned**
   ```bash
   # Should pass validation
   python .claude/hooks/validate_docs_consistency.py
   # Exit code: 0
   ```

5. **GenAI is being used**
   ```bash
   # Should see GenAI analysis in hook output
   export DEBUG_GENAI=true
   python .claude/hooks/security_scan.py
   # Should show "✅ GenAI analysis successful"
   ```

---

## Emergency Recovery

### If philosophy has drifted significantly:

```bash
# 1. Audit current state
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --audit --genai
python .claude/hooks/validate_claude_alignment.py
python .claude/hooks/validate_docs_consistency.py

# 2. Review PROJECT.md
cat .claude/PROJECT.md
# Ask: Is this still accurate?

# 3. Check orchestrator invocation rate
total=$(ls docs/sessions/*.md 2>/dev/null | wc -l)
orchestrator=$(ls docs/sessions/*orchestrator*.md 2>/dev/null | wc -l)
echo "orchestrator rate: $orchestrator / $total"
# Target: > 50% for feature-heavy projects

# 4. Enable strict mode if needed
cp plugins/autonomous-dev/templates/settings.strict-mode.json \
   .claude/settings.local.json

# 5. Run /align-project
/align-project

# 6. Commit fixes
git add .
git commit -m "fix: restore core philosophy alignment"
```

---

## Summary

**The core philosophy stays active when:**

1. **PROJECT.md is updated FIRST** (source of truth)
2. **orchestrator validates all features** (gatekeeper)
3. **Hooks enforce quality gates** (100% reliable)
4. **Agents provide intelligence** (conditional, adaptive)
5. **Skills contain patterns** (progressive disclosure)
6. **Documentation auto-syncs** (no drift)
7. **GenAI makes decisions** (not static Python)

**Priority order for updates:**
1. 🔴 PROJECT.md, orchestrator.md, settings.local.json (always)
2. 🟡 Agent prompts, GenAI prompts, skills (frequently)
3. 🟢 Documentation, session logs, hooks (periodically)
4. 🔵 Feature flags, GitHub issues (as needed)

**Remember:** The system is designed to maintain itself through hooks and validation. Your job is to keep PROJECT.md accurate and let the automation handle the rest.
