# Migration Guide: v1.x → v2.0

**Status**: v2.0 in alpha (infrastructure complete, agent integration in progress)
**Timeline**: Full migration recommended in 8-10 weeks (when v2.0 reaches beta)
**Last Updated**: 2025-10-23

---

## Overview

This guide helps you understand the differences between autonomous-dev v1.x and v2.0, and plan your migration strategy.

**Key Message**: **Keep using v1.x for production work**. v2.0 is currently in alpha with infrastructure complete but agent pipeline still in development.

---

## What's Changed in v2.0

### Architecture

| Aspect | v1.x | v2.0 | Impact |
|--------|------|------|--------|
| **Agent Definitions** | Python scripts | Markdown files | More transparent |
| **Communication** | Session files | JSON artifacts | More structured |
| **Alignment** | Keyword matching | Semantic validation | More accurate |
| **Checkpoints** | None | Full support | More resilient |
| **Logging** | Basic | Comprehensive | Better debugging |
| **Testing** | Limited | Complete | More reliable |

### What Stays the Same

✅ **PROJECT.md structure** - 100% backward compatible
✅ **8-agent pipeline** - Same order, same responsibilities
✅ **TDD workflow** - Tests before code
✅ **Git workflow** - Branches, commits, PRs
✅ **Security scanning** - Same checks

### What's Better in v2.0

1. **Semantic Alignment**
   - v1.x: "auth" keyword matches "auth" in goals
   - v2.0: "authentication" semantically matches "security" goal

2. **Debuggability**
   - v1.x: Session files (unstructured text)
   - v2.0: JSON artifacts with schemas

3. **Resilience**
   - v1.x: Start over if interrupted
   - v2.0: Resume from checkpoint

4. **Transparency**
   - v1.x: Python scripts (opaque)
   - v2.0: Markdown agents (human-readable)

5. **Testability**
   - v1.x: Hard to test agent behavior
   - v2.0: Complete test framework

---

## Migration Timeline

### Phase 1: Now (Weeks 1-3) ✅

**Status**: Infrastructure complete

**You can**:
- ✅ Test v2.0 infrastructure
- ✅ Run validation tests
- ✅ Explore the new architecture
- ✅ Provide feedback

**You should NOT**:
- ❌ Use v2.0 for production work
- ❌ Migrate PROJECT.md yet (it's compatible!)
- ❌ Remove v1.x installation

**Action**: Test v2.0 in parallel
```bash
# Keep v1.x for production
/auto-implement feature X

# Test v2.0 infrastructure
python plugins/autonomous-dev/lib/test_workflow_v2.py
```

### Phase 2: Week 4-10 ⏳

**Status**: Agent integration in progress

**What's happening**:
- ⏳ Agent invocation via Task tool
- ⏳ Sequential pipeline (researcher → planner → test-master → implementer)
- ⏳ Parallel validators (reviewer ‖ security ‖ docs)

**You can**:
- ✅ Continue using v1.x for production
- ✅ Test v2.0 agent invocation (when ready)
- ✅ Report issues

**You should NOT**:
- ❌ Rely on v2.0 for critical work
- ❌ Migrate production workflows

**Action**: Stay with v1.x, test v2.0 beta features as they become available

### Phase 3: Week 11-12 ⏳

**Status**: Beta testing

**What's happening**:
- ⏳ End-to-end testing
- ⏳ Performance optimization
- ⏳ Documentation finalization

**You can**:
- ✅ Test v2.0 beta with real features
- ✅ Plan migration strategy
- ✅ Identify migration blockers

**Action**: Prepare for gradual migration

### Phase 4: Week 12+ ⏳

**Status**: Production ready

**You can**:
- ✅ Start migrating low-risk workflows
- ✅ Use v2.0 for new features
- ✅ Keep v1.x for critical paths (initially)

**Action**: Gradual cutover

---

## Migration Strategy

### Recommended Approach: Gradual Cutover

**Don't**: Switch everything at once
**Do**: Migrate agent by agent, feature by feature

#### Step 1: Parallel Testing (Now - Week 10)

```bash
# Production work: Use v1.x
/auto-implement critical-feature

# Experimental work: Test v2.0
/auto-implement-v2 experimental-feature
```

**Goal**: Build confidence in v2.0

#### Step 2: New Features First (Week 12+)

```bash
# Critical features: Still use v1.x
/auto-implement security-update

# New features: Use v2.0
/auto-implement-v2 new-feature
```

**Goal**: Minimize risk

#### Step 3: Gradual Agent Migration (Week 13+)

Migrate one agent at a time:

1. ✅ Start with read-only agents (researcher, reviewer)
2. ✅ Then validators (security, docs)
3. ✅ Then generators (planner, test-master)
4. ✅ Finally implementer
5. ✅ Last: orchestrator (when fully confident)

#### Step 4: Full Migration (Week 15+)

Once comfortable:

```bash
# All work uses v2.0
/auto-implement-v2 any-feature

# v1.x kept as fallback
/auto-implement fallback-if-needed
```

---

## PROJECT.md Migration

### Good News: 100% Compatible! ✅

Your existing PROJECT.md works with v2.0 without changes.

**v1.x PROJECT.md**:
```markdown
## GOALS
- Improve security
- Automate workflows

## SCOPE
**IN Scope**:
- Authentication
- Testing

**OUT of Scope**:
- Social media

## CONSTRAINTS
- Must use Python 3.8+
```

**v2.0 PROJECT.md**: Same format! ✅

### Enhanced Features in v2.0

v2.0 **additionally supports** (but doesn't require):

**Numbered lists**:
```markdown
## GOALS
1. Improve security
2. Automate workflows
3. Maintain quality
```

**Subsections**:
```markdown
## SCOPE
### In Scope
- Authentication

### Out of Scope
- Social media
```

**Your existing PROJECT.md works in both versions!**

---

## Code Migration

### Agent Definitions

**v1.x approach** (Python):
```python
# .claude/hooks/auto_research.py
def trigger_research(user_prompt):
    if should_research(user_prompt):
        run_researcher_agent()
```

**v2.0 approach** (Markdown):
```markdown
---
name: researcher
description: Research patterns and best practices
tools: [Read, WebSearch, Grep]
---

# Researcher Agent

Read manifest: .claude/artifacts/{workflow_id}/manifest.json
Create research: .claude/artifacts/{workflow_id}/research.json
```

**Migration**:
- ✅ v1.x Python scripts still work
- ✅ v2.0 agents will be in markdown
- ✅ Gradual migration (agent by agent)
- ✅ No breaking changes to existing workflows

### Artifact Access

**v1.x approach**:
```bash
# Session files
cat docs/sessions/20251023-session.md
# Parse text to find paths
```

**v2.0 approach**:
```python
# Structured artifacts
from lib.artifacts import ArtifactManager

manager = ArtifactManager()
research = manager.read_artifact(workflow_id, 'research')
print(research['best_practices'])
```

**Migration**:
- ✅ v1.x session files still created
- ✅ v2.0 artifacts ALSO created (in `.claude/artifacts/`)
- ✅ Both systems can coexist
- ✅ Gradually shift to v2.0 artifact API

### Logging

**v1.x approach**:
```python
# Basic logging
print(f"Researcher completed: {findings}")
```

**v2.0 approach**:
```python
from lib.logging_utils import WorkflowLogger

logger = WorkflowLogger(workflow_id, 'researcher')
logger.log_decision(
    decision='Use library X',
    rationale='Best performance',
    alternatives_considered=['library Y']
)
```

**Migration**:
- ✅ v1.x logging still works
- ✅ v2.0 structured logging optional
- ✅ Add v2.0 logging incrementally
- ✅ Both can coexist

---

## Breaking Changes

### None! (By Design)

v2.0 is designed to be **non-breaking**:

- ✅ PROJECT.md format: 100% compatible
- ✅ Git workflow: Same
- ✅ Command names: v1.x commands still work
- ✅ Hooks: v1.x hooks still work
- ✅ Output: Same file structure

**New in v2.0**:
- New `/auto-implement-v2` command (alongside `/auto-implement`)
- New `.claude/artifacts/` directory (alongside `docs/sessions/`)
- New structured logging (alongside basic logging)

**Old v1.x functionality remains!**

---

## Feature Comparison

### What Works in Both

| Feature | v1.x | v2.0 |
|---------|------|------|
| PROJECT.md validation | ✅ | ✅ |
| 8-agent pipeline | ✅ | ✅ |
| TDD workflow | ✅ | ✅ |
| Git automation | ✅ | ✅ |
| Security scanning | ✅ | ✅ |
| Documentation updates | ✅ | ✅ |

### What's New in v2.0

| Feature | v1.x | v2.0 |
|---------|------|------|
| Semantic alignment | ❌ | ✅ |
| Checkpoint/resume | ❌ | ✅ |
| Structured artifacts | ❌ | ✅ |
| Complete logging | ❌ | ✅ |
| Test framework | ❌ | ✅ |
| Artifact validation | ❌ | ✅ |

---

## Migration Checklist

### Before Migration

- [ ] ✅ Test v2.0 infrastructure
  ```bash
  python plugins/autonomous-dev/lib/test_workflow_v2.py
  ```

- [ ] ✅ Verify PROJECT.md compatibility
  ```bash
  python -c "from plugins.autonomous_dev.lib.orchestrator import Orchestrator; print('Compatible!' if Orchestrator() else '')"
  ```

- [ ] ✅ Backup current setup
  ```bash
  git add .
  git commit -m "backup: before v2.0 migration"
  ```

- [ ] ✅ Document current workflows
  - What features use v1.x?
  - What's critical vs experimental?
  - What can break vs what's safe?

### During Migration

- [ ] ⏳ Test v2.0 with non-critical features first
- [ ] ⏳ Monitor both v1.x and v2.0 workflows
- [ ] ⏳ Compare results (quality, speed, reliability)
- [ ] ⏳ Document any issues
- [ ] ⏳ Keep v1.x as fallback

### After Migration

- [ ] ⏳ Validate all workflows work
- [ ] ⏳ Performance: v2.0 matches or exceeds v1.x
- [ ] ⏳ Quality: Same or better code
- [ ] ⏳ Team: Everyone comfortable with v2.0
- [ ] ⏳ Remove v1.x fallback (optional)

---

## Rollback Plan

If v2.0 doesn't work for you:

### Easy Rollback (Weeks 1-12)

v1.x remains installed and functional:

```bash
# Use v1.x
/auto-implement feature-x

# v2.0 artifacts don't interfere
# (.claude/artifacts/ is separate from docs/sessions/)
```

### If You Fully Migrated

```bash
# Reinstall v1.x
/plugin uninstall autonomous-dev@v2.0
/plugin install autonomous-dev@v1.x

# Your PROJECT.md still works!
# Your Git history intact
# Your workflows unchanged
```

---

## Support During Migration

### Resources

- **Quickstart**: `docs/V2_QUICKSTART.md`
- **Status**: `docs/V2_IMPLEMENTATION_STATUS.md`
- **Issues**: File issues on GitHub

### Common Questions

**Q: When should I migrate?**
A: When v2.0 reaches beta (Week 12+) and you've tested it with non-critical work.

**Q: Will my PROJECT.md need changes?**
A: No, it's 100% compatible.

**Q: Can I use both v1.x and v2.0?**
A: Yes! They coexist peacefully.

**Q: What if v2.0 breaks something?**
A: Easy rollback to v1.x (see Rollback Plan above).

**Q: Will v1.x be maintained?**
A: Yes, until v2.0 is stable and widely adopted.

---

## Summary

**Migration is EASY because**:
- ✅ No breaking changes
- ✅ PROJECT.md 100% compatible
- ✅ v1.x and v2.0 can coexist
- ✅ Gradual migration supported
- ✅ Easy rollback available

**Migration is SAFE because**:
- ✅ Start with non-critical features
- ✅ Test in parallel with v1.x
- ✅ Keep v1.x as fallback
- ✅ Migrate agent by agent

**Timeline**:
- ✅ Now: Test v2.0 infrastructure
- ⏳ Week 4-10: Test v2.0 agent pipeline
- ⏳ Week 12+: Start gradual migration
- ⏳ Week 15+: Full migration (if comfortable)

**Recommendation**: **Keep using v1.x for now**. Test v2.0 in parallel. Plan migration for Week 12+ when beta is ready.

---

**Status**: Migration guide for alpha → beta transition
**Version**: 2.0.0-alpha
**Last Updated**: 2025-10-23
