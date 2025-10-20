# System Performance Testing Guide

**Layer 3: Meta-Validation** - Testing the autonomous development system itself

---

## The Three Testing Layers

### Layer 1: Code Coverage (pytest)
**What**: % of code lines executed by tests
**Command**: `/test unit integration uat`
**Validates**: Code correctness, regression prevention

### Layer 2: Quality Coverage (GenAI)
**What**: UX quality, architectural intent, goal alignment
**Command**: `/test uat-genai architecture`
**Validates**: Semantic quality, design intent preservation

### Layer 3: System Performance Coverage (Meta-Analysis) ⭐ **NEW**
**What**: Agent effectiveness, model optimization, cost efficiency
**Command**: `/test system-performance` (proposed)
**Validates**: The autonomous system itself is optimized

---

## Why Layer 3 Matters

**Without meta-validation**, you can't answer:
- ❓ Are we using the right models? (Opus vs Sonnet vs Haiku)
- ❓ Which agents are most/least effective?
- ❓ Are we wasting tokens/money?
- ❓ Which skills provide most value?
- ❓ How long does each feature take?
- ❓ What's our cost per feature?

**With meta-validation**, you get:
- ✅ Cost optimization (use Haiku instead of Sonnet when possible)
- ✅ Time optimization (identify slow agents)
- ✅ Agent tuning (improve or replace ineffective agents)
- ✅ Skill refinement (remove unused skills)
- ✅ ROI measurement (value delivered vs cost)

---

## What to Measure

### 1. Agent Performance Metrics

**For each agent, track**:
```markdown
| Metric | What It Tells You |
|--------|-------------------|
| Invocation count | How often used |
| Success rate | Reliability |
| Avg execution time | Speed |
| Tokens per invocation | Efficiency |
| Cost per invocation | Resource usage |
| Value delivered | Effectiveness |
```

**Example Report**:
```markdown
## Agent Performance (Feature: Add user authentication)

| Agent | Invocations | Success Rate | Avg Time | Tokens Used | Estimated Cost |
|-------|-------------|--------------|----------|-------------|----------------|
| researcher | 2 | 100% | 45s | 3,200 | $0.10 |
| planner | 1 | 100% | 30s | 2,500 | $0.08 |
| test-master | 2 | 100% | 60s | 5,100 | $0.15 |
| implementer | 3 | 100% | 90s | 8,900 | $0.27 |
| reviewer | 1 | 100% | 20s | 1,800 | $0.05 |
| security-auditor | 1 | 100% | 25s | 2,200 | $0.07 |
| doc-master | 1 | 100% | 15s | 1,500 | $0.05 |

**Totals**: 11 invocations, 100% success, 285s (4.75min), 25,200 tokens, $0.77
```

---

### 2. Model Optimization Analysis

**Question**: Did we use the right model for each task?

**Model Pricing** (Claude):
- **Opus**: $15/1M input tokens (most capable, expensive)
- **Sonnet**: $3/1M input tokens (balanced)
- **Haiku**: $0.25/1M input tokens (fast, cheap)

**Analysis**:
```markdown
## Model Usage (Feature: Add user authentication)

| Task | Model Used | Tokens | Cost | Right Choice? | Savings Opportunity |
|------|------------|--------|------|---------------|---------------------|
| Research patterns | Sonnet | 3,200 | $0.10 | ✅ Yes | None |
| Plan architecture | Sonnet | 2,500 | $0.08 | ✅ Yes | None |
| Write tests | Sonnet | 5,100 | $0.15 | ⚠️ Maybe | Could use Haiku ($0.01) |
| Implement code | Sonnet | 8,900 | $0.27 | ✅ Yes | None |
| Review code | Sonnet | 1,800 | $0.05 | ⚠️ Overkill | Use Haiku ($0.004) |
| Security scan | Sonnet | 2,200 | $0.07 | ✅ Yes | None |
| Update docs | Sonnet | 1,500 | $0.05 | ⚠️ Overkill | Use Haiku ($0.004) |

**Total Cost**: $0.77
**Optimized Cost**: $0.63 (18% savings)
**Recommendation**: Use Haiku for simple tasks (review, docs)
```

---

### 3. Skill Utilization Tracking

**Question**: Which skills are actually helpful?

**Metrics**:
```markdown
## Skill Usage (Feature: Add user authentication)

| Skill | Invocations | Value Rating | Should Keep? |
|-------|-------------|--------------|--------------|
| python-standards | 5 | ⭐⭐⭐⭐⭐ | ✅ Yes (enforced type hints) |
| testing-guide | 4 | ⭐⭐⭐⭐⭐ | ✅ Yes (TDD workflow) |
| security-patterns | 3 | ⭐⭐⭐⭐⭐ | ✅ Yes (auth best practices) |
| documentation-guide | 2 | ⭐⭐⭐⭐ | ✅ Yes (docstring format) |
| research-patterns | 2 | ⭐⭐⭐⭐ | ✅ Yes (found patterns) |
| engineering-standards | 1 | ⭐⭐⭐ | ⚠️ Maybe (generic advice) |

**Recommendation**: All skills provided value. Keep current set.
```

---

### 4. Cost Efficiency Analysis

**Question**: What's our cost per feature? Is it worth it?

**Calculation**:
```markdown
## Cost-Benefit Analysis

### Feature: Add user authentication

**Costs**:
- Agent execution: $0.77 (tokens)
- Developer time saved: 4 hours × $100/hr = $400
- Net savings: $399.23

**Value Delivered**:
- ✅ Tests written (2 hours saved)
- ✅ Code implemented (1.5 hours saved)
- ✅ Security reviewed (30 min saved)
- ✅ Docs updated (30 min saved)

**ROI**: 518× return on investment

**Verdict**: ✅ Excellent value
```

---

### 5. Time Efficiency Tracking

**Question**: How long does each feature take?

**Metrics**:
```markdown
## Time Analysis (Feature: Add user authentication)

| Phase | Time | % of Total | Bottleneck? |
|-------|------|------------|-------------|
| Research | 1.5min | 32% | ⚠️ Could optimize |
| Planning | 0.5min | 11% | ✅ Fast |
| Testing | 2min | 42% | ⚠️ Slowest phase |
| Implementation | 4.5min | - | (3 invocations) |
| Review | 0.3min | 6% | ✅ Fast |
| Security | 0.4min | 8% | ✅ Fast |
| Documentation | 0.25min | 5% | ✅ Fast |

**Total**: 4.75min
**Bottleneck**: Testing phase (42% of time)
**Recommendation**: Optimize test-master for speed
```

---

## How to Collect This Data

### Option 1: Session File Analysis (Manual)

**Currently, session files don't exist** (docs/sessions/ is empty), but they should contain:
```markdown
# Session: 20251020-143000
## Agent: researcher
Started: 14:30:00
Completed: 14:30:45
Duration: 45s
Model: Sonnet
Tokens: 3,200
Task: Research authentication patterns
Status: Success
Value: Found 3 existing patterns
```

**Analysis Script** (proposed):
```python
# scripts/analyze_session.py
import json
from pathlib import Path

def analyze_session(session_file):
    """Parse session file and extract metrics."""
    agents = []
    total_tokens = 0
    total_time = 0

    # Parse session markdown
    # Extract: agent, time, tokens, success

    return {
        "agents": agents,
        "total_tokens": total_tokens,
        "total_time": total_time,
        "estimated_cost": total_tokens * 0.003 / 1000  # Sonnet pricing
    }

# Usage
results = analyze_session("docs/sessions/latest.md")
print(f"Total cost: ${results['estimated_cost']:.2f}")
```

---

### Option 2: Real-Time Tracking (Automated)

**Instrument agents to log performance**:
```python
# agents/researcher.md (add to frontmatter)
---
log_performance: true
track_tokens: true
track_time: true
---
```

**Logging format**:
```python
# In agent execution
import time
start = time.time()

# ... agent work ...

duration = time.time() - start
log_performance({
    "agent": "researcher",
    "duration": duration,
    "tokens": context.tokens_used,
    "task": context.task,
    "success": True
})
```

---

### Option 3: Post-Feature Analysis (Hybrid)

**After feature completion**:
```bash
# Run analysis command (proposed)
/test system-performance

# Analyzes:
# 1. Recent git commits (feature size)
# 2. Test coverage changes
# 3. Documentation updates
# 4. Estimated agent usage
```

**Output**:
```markdown
# System Performance Report

## Feature: Add user authentication
**Committed**: 2025-10-20 14:35:00

### Estimated Metrics
- Lines changed: 320 (180 added, 140 modified)
- Files changed: 8
- Tests added: 12
- Coverage change: +5% (85% → 90%)

### Estimated Agent Usage (based on feature size)
- researcher: 1-2 invocations (~3K tokens)
- planner: 1 invocation (~2.5K tokens)
- test-master: 2 invocations (~5K tokens)
- implementer: 3 invocations (~9K tokens)
- reviewer: 1 invocation (~2K tokens)

**Estimated Cost**: $0.60-$0.80
**Estimated Time**: 4-6 minutes

### Optimization Opportunities
⚠️ Feature size suggests multiple implementer calls - consider breaking into smaller features
✅ Good test coverage increase
✅ Documentation updated
```

---

## Proposed: `/test system-performance` Command

### What It Does

**Analyzes the autonomous system's performance** across:
1. Agent effectiveness
2. Model optimization
3. Cost efficiency
4. Time efficiency
5. Skill utilization

### Usage

```bash
# Analyze most recent feature
/test system-performance

# Analyze specific feature (by session file)
/test system-performance --session docs/sessions/20251020-143000.md

# Analyze date range
/test system-performance --since 2025-10-01

# Compare features
/test system-performance --compare feature-a feature-b
```

### Output Format

```markdown
# System Performance Report

**Analysis Period**: Last 7 days
**Features Analyzed**: 5

---

## Executive Summary

**Average per feature**:
- Time: 5.2 minutes
- Cost: $0.85
- Success rate: 100%
- ROI: 470× (avg $400 saved per $0.85 spent)

**Recommendations**:
1. ⚠️ Use Haiku for simple review tasks (save 15%)
2. ✅ Agent performance excellent (no changes needed)
3. ⚠️ Testing phase slow (optimize test-master)

---

## Agent Performance

| Agent | Avg Invocations | Success Rate | Avg Time | Avg Tokens | Avg Cost |
|-------|-----------------|--------------|----------|------------|----------|
| researcher | 1.8 | 100% | 42s | 3,100 | $0.09 |
| planner | 1.0 | 100% | 28s | 2,400 | $0.07 |
| test-master | 2.2 | 100% | 65s | 5,500 | $0.17 |
| implementer | 3.4 | 100% | 95s | 9,200 | $0.28 |
| reviewer | 1.0 | 100% | 18s | 1,700 | $0.05 |
| security-auditor | 1.0 | 100% | 22s | 2,000 | $0.06 |
| doc-master | 0.8 | 100% | 12s | 1,300 | $0.04 |

---

## Model Optimization

**Current**: 100% Sonnet ($3/1M tokens)

**Opportunities**:
- reviewer: Could use Haiku (save $0.045/feature)
- doc-master: Could use Haiku (save $0.035/feature)

**Potential Savings**: 9% cost reduction ($0.08/feature)

---

## Skill Utilization

| Skill | Usage % | Value Rating | Keep? |
|-------|---------|--------------|-------|
| python-standards | 95% | ⭐⭐⭐⭐⭐ | ✅ |
| testing-guide | 88% | ⭐⭐⭐⭐⭐ | ✅ |
| security-patterns | 65% | ⭐⭐⭐⭐ | ✅ |
| documentation-guide | 72% | ⭐⭐⭐⭐ | ✅ |
| research-patterns | 80% | ⭐⭐⭐⭐ | ✅ |
| engineering-standards | 45% | ⭐⭐⭐ | ⚠️ |

**Recommendation**: engineering-standards underutilized - consider merging into other skills

---

## Cost Efficiency

**Total spent (7 days)**: $4.25 (5 features)
**Avg per feature**: $0.85
**Developer time saved**: ~20 hours ($2,000 value)
**ROI**: 470×

**Trend**: ✅ Cost stable, excellent value

---

## Time Efficiency

**Avg feature time**: 5.2 minutes

**Breakdown**:
- Research: 15% (47s)
- Planning: 9% (28s)
- Testing: 25% (78s) ⚠️ Slowest
- Implementation: 40% (125s) ⚠️ Expected
- Review: 6% (19s)
- Security: 7% (22s)
- Docs: 4% (12s)

**Bottleneck**: Testing + Implementation (65% of time)
**Recommendation**: Normal distribution - no action needed

---

## Recommendations

### High Priority
1. **Model optimization**: Switch reviewer + doc-master to Haiku
   - Savings: $0.08/feature (9%)
   - Risk: Low (simple tasks)
   - Action: Update agent configs

### Medium Priority
2. **Skill consolidation**: Merge engineering-standards into other skills
   - Reason: Only 45% utilization
   - Benefit: Reduce context overhead
   - Action: Review skill boundaries

### Low Priority
3. **Monitor testing time**: Testing phase takes 25% of time
   - Status: Acceptable for now
   - Threshold: Alert if exceeds 35%
   - Action: Monitor trend
```

---

## Integration with Existing Testing

### Current Testing Workflow

```bash
# Before merge
/test all                # Code coverage (pytest)
/test uat-genai          # UX quality (GenAI)
/test architecture       # Architectural intent (GenAI)
```

### Enhanced Workflow (with Layer 3)

```bash
# Before merge
/test all                # Layer 1: Code coverage
/test uat-genai          # Layer 2: UX quality
/test architecture       # Layer 2: Architectural intent

# After merge (weekly/monthly)
/test system-performance # Layer 3: Meta-optimization
```

**Frequency**:
- Layer 1 (pytest): Every commit
- Layer 2 (GenAI quality): Before merge
- Layer 3 (system performance): Weekly or after major features

---

## Metrics to Track Over Time

### Weekly Metrics
```markdown
## Week of 2025-10-14

| Metric | This Week | Last Week | Trend |
|--------|-----------|-----------|-------|
| Features completed | 5 | 4 | ↗️ +25% |
| Avg time per feature | 5.2min | 5.8min | ↗️ -10% |
| Avg cost per feature | $0.85 | $0.92 | ↗️ -8% |
| Success rate | 100% | 100% | → Stable |
| Code coverage | 88% | 85% | ↗️ +3% |
| UX score | 8.2/10 | 7.8/10 | ↗️ +5% |
```

### Monthly Trends
```markdown
## October 2025

**Features**: 22 total
**Cost**: $18.70 total ($0.85 avg)
**Time**: 114 minutes total (5.2min avg)
**Value**: $8,800 saved (22 features × 4hr × $100/hr)
**ROI**: 470×

**Agent Performance Trends**:
- researcher: Stable efficiency
- planner: Stable efficiency
- test-master: Improved 12% (faster tests)
- implementer: Stable efficiency
- reviewer: Could optimize (use Haiku)

**Recommendations for November**:
1. Switch reviewer to Haiku (save ~$0.05/feature)
2. Continue monitoring testing time
3. Consider batch documentation updates
```

---

## Implementation Options

### Option 1: Manual Analysis (Start Simple)
**What**: Document metrics manually after features
**Effort**: Low
**Accuracy**: Estimated
**Good for**: Getting started, understanding patterns

**Process**:
```bash
# After feature
1. Check git log (lines changed, files modified)
2. Estimate agent usage based on feature size
3. Record in spreadsheet
4. Review monthly
```

---

### Option 2: Session File Parsing (Semi-Automated)
**What**: Create session files, parse for metrics
**Effort**: Medium
**Accuracy**: Actual data
**Good for**: Accurate tracking

**Process**:
```bash
# Enable session logging
python scripts/session_tracker.py researcher "Starting research"

# After feature
python scripts/analyze_session.py docs/sessions/latest.md
```

---

### Option 3: Full Automation (Future)
**What**: Real-time tracking, automated reports
**Effort**: High
**Accuracy**: Perfect
**Good for**: At scale

**Process**:
```bash
# Automatic (no manual steps)
/test system-performance --auto
```

---

## Quick Start: Manual Tracking Template

### Simple Metrics Spreadsheet

```csv
Date,Feature,Time(min),Estimated_Cost,Lines_Changed,Coverage_Change,Notes
2025-10-20,Add authentication,5.2,$0.85,320,+5%,Good performance
2025-10-21,Add export,4.8,$0.75,180,+3%,Fast implementation
2025-10-22,Fix login bug,2.1,$0.30,45,+1%,Small fix
```

### Monthly Review Checklist

```markdown
## Monthly System Performance Review

**Date**: 2025-10-31

### Data Collection
- [ ] Count features completed this month
- [ ] Sum estimated costs
- [ ] Sum time spent
- [ ] Calculate average coverage

### Analysis
- [ ] Which agent was most/least used?
- [ ] Are we improving over time? (faster/cheaper)
- [ ] Any bottlenecks discovered?
- [ ] Model optimization opportunities?

### Actions
- [ ] Update agent configs (if needed)
- [ ] Adjust skill set (if needed)
- [ ] Document learnings
- [ ] Set goals for next month
```

---

## Success Criteria

### What "Good" Looks Like

**Agent Performance**:
- ✅ Success rate: 95%+ for all agents
- ✅ Time variance: < 20% (predictable)
- ✅ No single agent dominates (balanced pipeline)

**Cost Efficiency**:
- ✅ Avg cost per feature: < $1.00
- ✅ ROI: > 100× (value delivered vs cost)
- ✅ Trending down or stable (not increasing)

**Model Optimization**:
- ✅ Complex tasks use Sonnet/Opus
- ✅ Simple tasks use Haiku
- ✅ < 10% waste (wrong model used)

**Skill Utilization**:
- ✅ All skills used > 50% of time
- ✅ All skills provide value (3+ stars)
- ✅ No redundancy between skills

**Time Efficiency**:
- ✅ Avg feature time: < 10 minutes
- ✅ Trending down (getting faster)
- ✅ No single phase dominates (> 50%)

---

## Next Steps

### Immediate (< 1 week)
1. **Start manual tracking**: Use spreadsheet template
2. **Enable session logging**: Track one feature end-to-end
3. **Baseline metrics**: Record current performance

### Short-Term (1-4 weeks)
4. **Create analysis script**: Parse session files automatically
5. **Weekly reviews**: Check trends
6. **Optimize models**: Switch simple tasks to Haiku

### Long-Term (1-3 months)
7. **Implement `/test system-performance` command**: Full automation
8. **Dashboard**: Visual metrics over time
9. **Continuous optimization**: Monthly reviews and improvements

---

## Summary

**Current State**:
- ✅ Layer 1: Code coverage (pytest) ✅
- ✅ Layer 2: Quality coverage (GenAI) ✅
- ❌ Layer 3: System performance (missing)

**This Guide Adds**:
- ✅ Framework for measuring agent effectiveness
- ✅ Model optimization analysis
- ✅ Cost/benefit tracking
- ✅ Skill utilization metrics
- ✅ Time efficiency analysis

**Outcome**: Complete visibility into the autonomous system's performance, enabling continuous optimization

---

**Start simple** (manual tracking), **evolve to automation** (scripts, commands), **optimize continuously** (monthly reviews).

**The autonomous system should optimize itself** - that's true autonomy! 🚀
