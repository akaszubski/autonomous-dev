# Project Status Analyzer - Metrics & Formulas

Detailed metrics calculation and output format.

---

## Goal Progress Calculation

### Status Determination

```
0% → ⏳ NOT STARTED
1-49% → 🔄 IN PROGRESS
50-99% → 🔄 IN PROGRESS (>50%)
100% → ✅ COMPLETE
```

### Progress Formula

```
Goal Progress = (Features Completed / Total Features) * 100

Example:
- Goal: "Add authentication"
- Completed: OAuth, JWT, Password reset (3 features)
- Total planned: 5 features
- Progress: (3/5) * 100 = 60%
```

---

## Code Quality Metrics

### Test Coverage
- Run: `pytest --cov=src --cov-report=term-missing`
- Extract coverage percentage
- Compare to target (80% typical)
- Flag files < 70% coverage

### Technical Debt Estimation
- Count TODO/FIXME comments
- Estimate 2-4 hours per item
- Total debt = item_count * avg_hours
- Flag if > 20% of sprint capacity

### Documentation Currency
- Compare README vs PROJECT.md modification dates
- Check CHANGELOG updated in last 2 weeks
- Verify API docs match code
- Scan for orphaned documentation

---

## Blocker Detection

**Critical blockers:**
- Red flags in test output (failing tests)
- Blocked PRs without assignee
- Alignment issues (CLAUDE.md drift)
- Dependency conflicts

**Minor blockers:**
- Unreviewed code awaiting feedback
- Missing docstrings
- Code style issues

---

## Velocity Calculation

```
Velocity = (Features completed this period) / (Time period in weeks)

Example:
- 6 features in 2 weeks
- Velocity = 3 features/week

Trend:
- Last 4 weeks: [2, 2.5, 3, 3.2]
- Trend: ↑ Increasing
- Average: 2.7 features/week
```

---

## Recommendation Engine

**Priority Matrix:**
- **HIGH**: Blocks current sprint OR critical for goals
- **MEDIUM**: Improves quality OR advances strategy
- **LOW**: Nice-to-have OR future work

**Categories:**
- **Sprint**: Current sprint blockers
- **Quality**: Test coverage, documentation, refactoring
- **Strategic**: Advancing project goals
- **Operational**: Setup, configuration, tooling

---

## Output Format Example

```json
{
  "timestamp": "2025-10-27T14:30:00Z",
  "overall_health": "Good (77%)",
  "strategic_progress": {
    "total_goals": 6,
    "completed": 2,
    "in_progress": 3,
    "completion_percentage": "33%"
  },
  "code_quality": {
    "test_coverage": "87%",
    "coverage_trend": "↑ +2% this week",
    "failing_tests": 0,
    "technical_debt": {"todo_count": 3, "fixme_count": 1}
  },
  "velocity": {
    "this_week": 3,
    "trend": "↑ 50% increase",
    "projected_completion": "2025-11-15"
  },
  "blockers": [],
  "recommendations": [
    {
      "priority": "HIGH",
      "category": "Sprint",
      "action": "Review PR #42",
      "effort": "< 30 min"
    }
  ]
}
```

---

## Output Examples

### Good Health
```
📊 Project Status: HEALTHY ✅

Overall: 77% (Good)
Strategic Progress: 6/12 goals (50% done)
Code Quality: 87% coverage (↑ exceeds target)
Velocity: 3.2 features/week (↑ trending up)
Blockers: None

Next Steps: Continue current sprint momentum
```

### Needs Attention
```
📊 Project Status: NEEDS ATTENTION ⚠️

Overall: 55% (Concerning)
Strategic Progress: 2/8 goals (25% done, behind schedule)
Code Quality: 62% coverage (↓ below 80% target)
Velocity: 1.5 features/week (↓ 40% down)
Blockers: 3 failing tests blocking PRs

URGENT:
1. Fix failing tests (blocking merge)
2. Add 100+ lines of test coverage
3. Accelerate feature delivery
```

---

## Tips

- **Get baseline metrics first**: Run pytest, git log, lint tools
- **Calculate trends**: 1-week metrics are noise, use 4-week trends
- **Celebrate progress**: Highlight completed goals
- **Be specific**: "87% coverage" not "good coverage"
- **Link to actions**: Each metric should suggest next action
