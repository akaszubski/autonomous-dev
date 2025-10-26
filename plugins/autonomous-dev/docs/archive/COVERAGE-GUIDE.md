# Test Coverage Guide

**How to measure coverage for both automated tests and GenAI validation**

---

## Two Types of Coverage

### 1. Code Coverage (Automated Tests)
**What**: % of code lines executed by tests
**Tool**: pytest-cov
**Measures**: Traditional test coverage

### 2. Quality Coverage (GenAI Validation)
**What**: % of quality aspects validated
**Tool**: GenAI (Claude)
**Measures**: Architectural intent, UX quality, goal alignment

---

## Code Coverage (Automated Tests)

### How to Measure

```bash
# Run tests with coverage
/test all

# Or explicitly
pytest --cov=src --cov-report=term-missing --cov-report=html -v
```

### Example Output

```
=================== test session starts ====================
collected 45 items

tests/unit/test_auth.py::test_login PASSED           [ 2%]
tests/unit/test_auth.py::test_logout PASSED          [ 4%]
tests/unit/test_user.py::test_create_user PASSED     [ 6%]
...
tests/integration/test_workflow.py::test_full_flow PASSED [100%]

=================== 45 passed in 2.34s =====================

Coverage Report:
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
src/auth.py               42      3    93%   45-48
src/user.py               35      2    94%   67-68
src/models/base.py        28      0   100%
-----------------------------------------------------
TOTAL                    105      5    95%

✅ All tests passing
✅ Coverage: 95% (exceeds 80% threshold)

HTML report: file://./htmlcov/index.html
```

### Coverage Breakdown by Layer

```bash
# Unit test coverage
/test unit
# Shows: What % of individual functions are tested

# Integration test coverage
/test integration
# Shows: What % of workflows are tested

# UAT test coverage
/test uat
# Shows: What % of user journeys are tested
```

### Coverage Targets

| Layer | Target | Why |
|-------|--------|-----|
| **Unit** | 80%+ | Core logic must be tested |
| **Integration** | 70%+ | Key workflows covered |
| **UAT** | 60%+ | Critical user paths tested |
| **Overall** | 80%+ | Minimum quality threshold |

---

## Quality Coverage (GenAI Validation)

### How to Measure

```bash
# UX quality coverage
/test uat-genai

# Architectural intent coverage
/test architecture
```

### UX Quality Coverage (`/test uat-genai`)

**Measures**:
- ✅ Goal alignment: Do workflows serve PROJECT.md goals?
- ✅ UX quality: Are workflows intuitive?
- ✅ Friction points: Where do users get stuck?
- ✅ Error handling: Are errors helpful?
- ✅ Performance: Meet targets from PROJECT.md?
- ✅ Accessibility: Can all users use it?

**Example Output**:
```markdown
# UAT Validation Report (GenAI)

## Executive Summary
- Workflows Tested: 5
- Goal Alignment: 80% (4/5 workflows serve goals)
- Average UX Score: 7.5/10
- Critical Issues: 2
- Overall Status: GOOD (needs minor improvements)

## Workflow Coverage

| Workflow | Goal Alignment | UX Score | Status |
|----------|---------------|----------|--------|
| Setup | ✅ Aligned | 8/10 | Good |
| Feature implementation | ✅ Aligned | 9/10 | Excellent |
| Error recovery | ⚠️ Partial | 6/10 | Needs improvement |
| Context management | ✅ Aligned | 8/10 | Good |
| Documentation | ❌ Not aligned | 5/10 | Poor |

## Coverage Metrics
- Workflows with UX score ≥ 8/10: 60% (3/5)
- Workflows aligned with goals: 80% (4/5)
- Workflows with < 5 steps: 100% (5/5)
- Workflows with helpful errors: 60% (3/5)

## Recommendations
1. Fix documentation workflow (not aligned with goals)
2. Improve error recovery UX
3. Add progress indicators
```

---

### Architectural Coverage (`/test architecture`)

**Measures**:
- ✅ PROJECT.md-first architecture: Enforced?
- ✅ 8-agent pipeline: Order correct?
- ✅ Model optimization: opus/sonnet/haiku correct?
- ✅ Context management: Session files used?
- ✅ Agent specialization: No duplication?
- ✅ Skill boundaries: No redundancy?
- ✅ TDD enforcement: Tests before code?
- ✅ Read-only planning: Planner can't write?
- ✅ Security-first: Scan in pipeline?
- ✅ Documentation sync: Auto-updated?
- ✅ Agent communication: Via session files?
- ✅ Data flow: Forward only?
- ✅ Context budget: < 25K per feature?
- ✅ All architectural invariants: True?

**Example Output**:
```markdown
# Architectural Intent Validation Report

## Executive Summary
- Total Principles: 14
- ✅ Aligned: 13
- ⚠️ Drift Detected: 1
- ❌ Violations: 0
- Overall Status: PASS WITH MINOR DRIFT

## Coverage Metrics
- Principles validated: 100% (14/14)
- Principles aligned: 93% (13/14)
- Architectural invariants: 100% (all true)
- Breaking changes: 0

## Detailed Findings
1. PROJECT.md-first: ✅ ALIGNED (100% coverage)
2. 8-agent pipeline: ✅ ALIGNED (100% coverage)
3. Model optimization: ✅ ALIGNED (100% coverage)
4. Context management: ✅ ALIGNED (100% coverage)
5. Opt-in automation: ✅ ALIGNED (100% coverage)
...
14. Data flow: ⚠️ DRIFT DETECTED (minor)

## Architecture Coverage Score: 93%
```

---

## Combined Coverage Metrics

### Complete Coverage Report

```bash
# Step 1: Automated test coverage
/test all

# Step 2: UX quality coverage
/test uat-genai

# Step 3: Architectural coverage
/test architecture
```

### Unified Coverage Dashboard

| Dimension | Metric | Target | Current | Status |
|-----------|--------|--------|---------|--------|
| **Code Coverage** | Lines executed | 80%+ | 95% | ✅ |
| **Unit Tests** | Functions tested | 80%+ | 90% | ✅ |
| **Integration Tests** | Workflows tested | 70%+ | 85% | ✅ |
| **UAT Tests** | User journeys tested | 60%+ | 75% | ✅ |
| **UX Quality** | Avg workflow score | 8/10 | 7.5/10 | ⚠️ |
| **Goal Alignment** | Workflows aligned | 100% | 80% | ⚠️ |
| **Architectural Intent** | Principles aligned | 100% | 93% | ⚠️ |
| **Overall Quality** | Composite score | 80% | 87% | ✅ |

---

## Coverage Tracking Over Time

### Setup Coverage Tracking

```bash
# Create coverage history directory
mkdir -p .coverage-history

# After each test run, save coverage
pytest --cov=src --cov-report=json -v
mv coverage.json .coverage-history/coverage-$(date +%Y%m%d-%H%M%S).json
```

### View Coverage Trends

```bash
# List coverage files
ls -lt .coverage-history/

# View specific coverage report
cat .coverage-history/coverage-20251020-120000.json | jq '.totals.percent_covered'
```

### Track GenAI Validation Scores

```bash
# Save GenAI validation results
/test uat-genai > .coverage-history/uat-genai-$(date +%Y%m%d).md
/test architecture > .coverage-history/architecture-$(date +%Y%m%d).md
```

---

## Coverage by Test Type

### Unit Test Coverage

**Command**:
```bash
/test unit
pytest tests/unit/ --cov=src --cov-report=term-missing -v
```

**Shows**:
- % of src/ code executed by unit tests
- Which lines are NOT tested
- Which functions lack tests

**Target**: 80%+ coverage

**Example**:
```
tests/unit/test_auth.py ...................... [100%]

Coverage Report:
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
src/auth.py               42      3    93%   45-48
src/user.py               35      2    94%   67-68

Unit Test Coverage: 93.5%
```

---

### Integration Test Coverage

**Command**:
```bash
/test integration
pytest tests/integration/ --cov=src --cov-report=term-missing -v
```

**Shows**:
- % of src/ code executed by integration tests
- Which workflows are tested
- Which component interactions are covered

**Target**: 70%+ coverage

**Example**:
```
tests/integration/test_workflows.py .......... [100%]

Coverage Report:
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
src/workflows.py          50     10    80%   102-111

Integration Test Coverage: 80%
```

---

### UAT Coverage

**Command**:
```bash
/test uat
pytest tests/uat/ --cov=src --cov-report=term-missing -v
```

**Shows**:
- % of src/ code executed by UAT tests
- Which user journeys are tested
- End-to-end coverage

**Target**: 60%+ coverage

**Example**:
```
tests/uat/test_user_journey.py ............... [100%]

Coverage Report:
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
src/api.py                80     20    75%   150-169

UAT Test Coverage: 75%
```

---

## Improving Coverage

### Increase Code Coverage

**1. Find uncovered code**:
```bash
/test all
open htmlcov/index.html  # Visual coverage report
```

**2. Add tests for uncovered lines**:
```python
# tests/unit/test_auth.py
def test_password_reset():
    """Test password reset flow (was uncovered)."""
    result = reset_password("user@test.com")
    assert result.email_sent
```

**3. Verify coverage improved**:
```bash
/test unit
# Coverage should increase
```

---

### Increase UX Coverage

**1. Run GenAI validation**:
```bash
/test uat-genai
```

**2. Review recommendations**:
```markdown
Workflow: Setup
UX Score: 6/10
Issues:
- No progress indicator
- Preset descriptions missing
- Error messages unclear
```

**3. Implement improvements**:
```python
# Add progress indicator
print("[1/4] Copying hooks...")
print("[2/4] Creating PROJECT.md...")
```

**4. Re-validate**:
```bash
/test uat-genai
# UX score should improve to 8/10
```

---

### Increase Architectural Coverage

**1. Run architectural validation**:
```bash
/test architecture
```

**2. Review findings**:
```markdown
Principle: Context Management
Status: ⚠️ DRIFT
Issue: Orchestrator not logging to session files
```

**3. Fix implementation**:
```bash
# Add session logging
python scripts/session_tracker.py orchestrator "Starting feature"
```

**4. Re-validate**:
```bash
/test architecture
# Should show ✅ ALIGNED
```

---

## Coverage Gates (CI/CD)

### Pre-Commit Gates

```bash
# Minimum coverage required before commit
/test unit integration

# Must achieve:
# - Unit coverage: 80%+
# - Integration coverage: 70%+
# - All tests passing
```

### Pre-Release Gates

```bash
# Complete validation before release
/test all
/test uat-genai
/test architecture

# Must achieve:
# - Overall coverage: 80%+
# - UX score: 8/10 average
# - Architectural alignment: 100%
```

### Automated Gate Script

```python
# scripts/coverage_gate.py
import subprocess
import json

def check_coverage():
    # Run tests with coverage
    result = subprocess.run(
        ["pytest", "--cov=src", "--cov-report=json"],
        capture_output=True
    )

    # Load coverage data
    with open("coverage.json") as f:
        coverage = json.load(f)

    # Check threshold
    percent = coverage["totals"]["percent_covered"]

    if percent < 80:
        print(f"❌ Coverage too low: {percent}% (need 80%+)")
        exit(1)
    else:
        print(f"✅ Coverage sufficient: {percent}%")
        exit(0)

if __name__ == "__main__":
    check_coverage()
```

---

## Coverage Best Practices

### 1. Set Realistic Targets
- Don't aim for 100% (diminishing returns)
- 80% overall coverage is good
- Focus on critical paths first

### 2. Prioritize Coverage
1. **Critical functions** (auth, payments) → 95%+
2. **Business logic** (core features) → 85%+
3. **Utilities** (helpers) → 70%+
4. **UI code** (less critical) → 60%+

### 3. Track Trends
- Coverage should increase over time
- Watch for drops (regressions)
- Celebrate improvements

### 4. Balance Coverage Types
- Not just code coverage
- Also UX quality
- Also architectural integrity

---

## Quick Reference

### Measure Code Coverage
```bash
/test all                # Overall coverage
/test unit               # Unit test coverage
/test integration        # Integration coverage
/test uat                # UAT coverage
```

### Measure Quality Coverage
```bash
/test uat-genai          # UX quality score
/test architecture       # Architectural alignment %
```

### View Reports
```bash
# Code coverage (HTML)
open htmlcov/index.html

# GenAI validation (text)
cat docs/sessions/uat-validation-*.md
cat docs/sessions/architecture-validation-*.md
```

### Coverage Targets
- **Code**: 80%+ overall
- **UX Score**: 8/10 average
- **Architecture**: 100% alignment

---

## Summary

**Three dimensions of coverage**:

1. **Code Coverage** (automated)
   - Measured by pytest-cov
   - Target: 80%+
   - Command: `/test all`

2. **Quality Coverage** (GenAI)
   - Measured by Claude validation
   - Target: 8/10 UX, 100% architecture
   - Commands: `/test uat-genai`, `/test architecture`

3. **System Performance Coverage** (meta-analysis) ⭐ **NEW**
   - Measured by session analysis
   - Target: < $1/feature, 95%+ success rate, ROI > 100×
   - Command: `/test system-performance` (proposed)
   - See: [SYSTEM-PERFORMANCE-GUIDE.md](SYSTEM-PERFORMANCE-GUIDE.md)

**All three are essential for comprehensive quality assurance!**

---

## System Performance Coverage (Layer 3)

### What It Measures

**Meta-level validation** - testing the autonomous system itself:
- ✅ **Agent effectiveness**: Which agents perform well?
- ✅ **Model optimization**: Right model (Opus/Sonnet/Haiku) for each task?
- ✅ **Cost efficiency**: Tokens, time, $ per feature
- ✅ **Skill utilization**: Which skills provide most value?
- ✅ **ROI measurement**: Value delivered vs cost

### Why It Matters

Without meta-validation, you can't answer:
- ❓ Are we using the right models? (Could save 15% with Haiku)
- ❓ Which agents are most/least effective?
- ❓ Are we wasting tokens/money?
- ❓ Which skills provide most value?
- ❓ What's our cost per feature?

### How to Measure

**Manual tracking** (start simple):
```bash
# After each feature, record:
# - Time spent (minutes)
# - Estimated cost ($)
# - Lines changed
# - Coverage change
# Track in spreadsheet, review monthly
```

**Automated analysis** (future):
```bash
# Proposed command
/test system-performance

# Analyzes:
# - Agent invocation counts
# - Token usage per agent
# - Model optimization opportunities
# - Cost trends
# - Time efficiency
```

### Example Metrics

```markdown
## System Performance (October 2025)

**Features completed**: 22
**Avg time per feature**: 5.2 minutes
**Avg cost per feature**: $0.85
**Total cost**: $18.70
**Developer time saved**: 88 hours
**Value delivered**: $8,800
**ROI**: 470× return on investment

**Agent Performance**:
| Agent | Avg Invocations | Success Rate | Avg Cost |
|-------|-----------------|--------------|----------|
| researcher | 1.8 | 100% | $0.09 |
| planner | 1.0 | 100% | $0.07 |
| test-master | 2.2 | 100% | $0.17 |
| implementer | 3.4 | 100% | $0.28 |
| reviewer | 1.0 | 100% | $0.05 |

**Optimization Opportunities**:
- ⚠️ Switch reviewer to Haiku (save 9%)
- ✅ Agent performance excellent
- ✅ Cost trending stable
```

### Targets

| Metric | Target | Why |
|--------|--------|-----|
| **Avg cost/feature** | < $1.00 | Sustainable scaling |
| **Success rate** | 95%+ | Reliable automation |
| **ROI** | > 100× | Demonstrable value |
| **Time/feature** | < 10min | Fast iteration |
| **Model waste** | < 10% | Efficient model selection |

### Complete Guide

For comprehensive system performance testing:
**See**: [docs/SYSTEM-PERFORMANCE-GUIDE.md](SYSTEM-PERFORMANCE-GUIDE.md)

Includes:
- Agent performance metrics
- Model optimization analysis
- Cost/benefit tracking
- Skill utilization metrics
- Time efficiency analysis
- Manual tracking templates
- Automation roadmap
