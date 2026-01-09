# Issue #214: Setup Wizard Agent Evaluation

## Executive Summary

**Decision**: KEEP UNIFIED

**Status**: Recommendation accepted

**Date**: 2026-01-09

**Issue**: [#214 - Evaluate splitting setup-wizard.md (1,145 lines)](https://github.com/akaszubski/autonomous-dev/issues/214)

**TL;DR**: Don't split setup-wizard.md into multiple agents. Sequential phase dependencies, interactive state machine, and one-time execution make splitting impractical. Instead, apply hybrid optimizations by extracting reusable libraries while preserving unified user experience.

---

## Current State Analysis

### Size and Complexity

- **Lines**: 1,145 lines (6,520 tokens)
- **Target**: 3,000 tokens (2.17x over target)
- **Largest agent**: 3x larger than average agent
- **Structure**: 6 sequential phases (0-5) with dependencies
- **Conditional logic**: Phase 0 and Phase 4 are optional
- **Interactive**: 8-12 AskUserQuestion calls per run
- **Execution frequency**: Once per installation (~$0.02 Sonnet cost)

### Phase Breakdown

| Phase | Description | Estimated Size | Complexity |
|-------|-------------|----------------|------------|
| Phase 0 | GenAI Installation (optional) | ~220 lines (19%) | Conditional |
| Phase 1 | Welcome & Tech Stack Detection | ~180 lines (16%) | Sequential |
| Phase 2 | PROJECT.md Setup | ~550 lines (48%) | Sequential |
| Phase 4.5 | GitHub Integration (optional) | ~80 lines (7%) | Conditional |
| Phase 5 | Validation & Summary | ~115 lines (10%) | Sequential |

**Key Finding**: Phase 2 (PROJECT.md Setup) is the largest section at 48% of content, suggesting a clear library extraction opportunity.

### Sequential Dependencies

```
Phase 0 (Optional)
    ↓
Phase 1: Detect tech stack
    ↓ (tech_info passed to Phase 2)
Phase 2: Generate PROJECT.md
    ↓ (project structure stored)
Phase 4.5: Configure GitHub (Optional)
    ↓ (integration settings)
Phase 5: Validate & Summarize
    ↓ (references all previous phases)
```

**Why dependencies matter**: Each phase builds on the previous phase's output. Splitting would require:
- Robust state serialization between agents
- Complex handoff logic
- Risk of data loss during transitions
- Degraded user experience (6 separate conversations)

---

## Evaluation Questions Answered

### Question 1: Should we split setup-wizard.md into multiple agents?

**Answer**: NO

**Rationale**:
1. **Sequential phase dependencies**: Phase 1 output feeds Phase 2, Phase 2 output validated in Phase 5
2. **Interactive state machine**: 8-12 user questions with branching logic across phases
3. **User experience**: Users expect ONE setup conversation, not 6 handoffs
4. **One-time cost**: $0.02 Sonnet cost per installation (minimal optimization value)
5. **State passing complexity**: Would need robust serialization, error handling, retry logic

**Splitting would create more problems than it solves.**

---

### Question 2: Is the size problematic?

**Answer**: NO, not for this use case

**Context**:
- Agents run ONCE per installation
- Cost: ~$0.02 Sonnet (6,520 tokens at $3/million input)
- User sees: Single setup flow (good UX)
- Alternative cost: Splitting would increase development/maintenance cost by ~$50-100 (engineer time)

**ROI Analysis**:
- Token savings per run: ~3,000 tokens (if split optimally)
- Cost savings per run: ~$0.01
- Development cost: ~$100 (2 hours engineer time)
- Break-even: 10,000 installations

**Verdict**: Not worth optimizing for token count. One-time execution and good UX trump size concerns.

---

### Question 3: What about maintainability?

**Answer**: Valid concern, address with hybrid approach

**Current challenges**:
- Phase 2 has complex PROJECT.md generation logic (~550 lines)
- Tech stack detection logic embedded in Phase 1
- Hook configuration logic could be reused elsewhere

**Solution**: Extract reusable libraries while keeping agent unified.

---

## Recommendation with Rationale

### Primary Recommendation: KEEP UNIFIED

**Keep the agent as a single unified flow for these reasons:**

1. **Sequential dependencies make splitting impractical**
   - Phase 1 → Phase 2 → Phase 5 data flow
   - Conditional branching based on previous phase results
   - State machine complexity across phases

2. **User experience requires unified conversation**
   - Users expect: "Run /setup once, get configured"
   - Splitting creates: "Run 6 agents sequentially"
   - No user benefit from splitting

3. **One-time execution = minimal optimization value**
   - Runs once per installation
   - Cost: $0.02 Sonnet per run
   - Not a performance bottleneck

4. **Engineering cost exceeds benefit**
   - Splitting cost: ~$100 (engineer time)
   - Savings per run: ~$0.01 (token optimization)
   - Break-even: 10,000 installations
   - Maintenance burden: Higher complexity

---

## Hybrid Optimization Plan

Instead of splitting the agent, apply targeted optimizations:

### Option 1: Extract Reusable Libraries (RECOMMENDED)

Extract phase-specific logic to shared libraries while keeping agent unified.

**Libraries to extract:**

1. **tech_stack_detector.py** (Phase 1 logic, ~50 lines)
   - Detect Python/Node/etc from directory structure
   - Reusable across agents and tools
   - Reduces agent from 1,145 → 1,095 lines

2. **project_md_generator.py** (Phase 2 logic, ~100 lines)
   - Generate PROJECT.md from templates
   - Reusable for /align command, retrofit scenarios
   - Reduces agent from 1,095 → 995 lines

3. **hook_configurator.py** (Phase 3 logic, ~50 lines)
   - Configure hooks based on project type
   - Reusable for hook management tools
   - Reduces agent from 995 → 945 lines

**Expected result**: 1,145 → ~945 lines (17% reduction) while improving code reusability.

**Benefits:**
- Reduced agent complexity (17% smaller)
- Reusable logic across commands
- Easier to test libraries independently
- Better separation of concerns
- Maintains unified user experience

---

### Option 2: Move Phase 0 Documentation to Separate Doc (OPTIONAL)

Phase 0 (GenAI Installation) contains detailed model download instructions.

**Opportunity:**
- Extract GenAI installation details to `docs/genai-installation.md`
- Reference doc from Phase 0 instead of embedding
- Reduces agent by ~80 lines (7%)

**Trade-off:**
- Saves ~80 lines in agent
- Creates separate documentation file
- Phase 0 logic still conditional in agent

**Verdict**: Lower priority than library extraction. Consider for future cleanup.

---

### Option 3: Refactor Phase 2 Template Logic (OPTIONAL)

Phase 2 includes extensive PROJECT.md template examples.

**Opportunity:**
- Move templates to separate file
- Load templates dynamically
- Reduces agent by ~50 lines (4%)

**Trade-off:**
- Adds file I/O dependency
- Templates less visible in agent code
- Minimal complexity reduction

**Verdict**: Lower priority. Keep templates inline for now.

---

## Benefits of Hybrid Approach

### Compared to Splitting

| Aspect | Splitting (NOT RECOMMENDED) | Hybrid (RECOMMENDED) |
|--------|---------------------------|---------------------|
| User Experience | 6 separate conversations | Single unified flow |
| State Management | Complex serialization needed | Simple in-memory state |
| Development Cost | ~$100 (2+ hours) | ~$50 (1 hour) |
| Maintenance | Higher complexity | Lower complexity |
| Code Reusability | No improvement | Significant improvement |
| Token Reduction | ~3,000 tokens (46%) | ~1,000 tokens (15%) |
| Risk | High (state loss, UX degradation) | Low (incremental extraction) |

### Compared to No Action

| Aspect | No Action | Hybrid (RECOMMENDED) |
|--------|-----------|---------------------|
| Code Reusability | Low | High |
| Testing | Harder (agent E2E only) | Easier (unit test libraries) |
| Maintainability | Agent-specific logic | Shared libraries |
| Token Count | 6,520 tokens | ~5,500 tokens (15% reduction) |
| Development Cost | $0 | ~$50 (1 hour) |

---

## Implementation Timeline

### Immediate Action (This Issue)

- [x] Document evaluation decision (this file)
- [x] Update PROJECT.md to reflect decision
- [ ] Close Issue #214 with evaluation link

### Future Work (Separate Issues)

Create follow-up issues for library extraction:

1. **Issue: Extract tech_stack_detector.py library**
   - Phase 1 tech stack detection logic
   - Estimate: 1 hour
   - Priority: Medium
   - Blocks: None

2. **Issue: Extract project_md_generator.py library**
   - Phase 2 PROJECT.md generation logic
   - Estimate: 1.5 hours
   - Priority: Medium
   - Blocks: None

3. **Issue: Extract hook_configurator.py library**
   - Phase 3 hook configuration logic
   - Estimate: 0.5 hours
   - Priority: Low
   - Blocks: None

**Total effort**: ~3 hours across 3 separate issues

**Benefits**: Incremental improvements without disrupting working system.

---

## Lessons Learned

### When to Split Agents

**Split when:**
- Agent has multiple independent workflows (no dependencies)
- Agent serves different user personas
- Agent is frequently used (ROI from optimization)
- Each sub-agent has clear boundaries

**Don't split when:**
- Sequential dependencies between phases
- Interactive state machine across phases
- One-time execution (low ROI)
- User experience requires unified flow

### Validation Process

This evaluation demonstrates the "validate-need" review pattern:

1. **Identify**: setup-wizard.md is 2.17x over token target
2. **Analyze**: Measure dependencies, complexity, user impact
3. **Evaluate**: Compare splitting vs alternatives
4. **Document**: Record decision and rationale
5. **Plan**: Define future optimizations (if any)

**Key insight**: Not all large agents need splitting. Consider use case, dependencies, and user experience first.

---

## Conclusion

**Decision**: KEEP UNIFIED with hybrid optimizations

**Action plan**:
1. Keep setup-wizard.md as single agent
2. Extract reusable libraries (future work)
3. Maintain unified user experience
4. Document evaluation for future reference

**Why this is the right decision**:
- Sequential phase dependencies make splitting impractical
- User experience requires unified conversation
- One-time execution = minimal optimization value
- Hybrid approach provides better ROI (code reusability > token savings)

**Future optimizations**:
- Library extraction (tech_stack_detector.py, project_md_generator.py, hook_configurator.py)
- Total reduction: ~200 lines (17%) while improving code quality

---

## References

- Issue #214: https://github.com/akaszubski/autonomous-dev/issues/214
- Test suite: tests/regression/progression/test_issue_214_setup_wizard_evaluation.py
- Agent file: .claude/agents/setup-wizard.md
- Related: docs/ARCHITECTURE-OVERVIEW.md (agent design principles)

---

**Status**: Evaluation complete. Recommendation accepted. Libraries to be extracted in future issues.
