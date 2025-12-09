# Three Layer Strategy

## Three-Layer Testing Strategy ⭐ UPDATED

### Critical Insight

**Layer 1 (pytest)** validates **STRUCTURE** and **BEHAVIOR**
**Layer 2 (GenAI)** validates **INTENT** and **MEANING**
**Layer 3 (Meta-analysis)** validates **SYSTEM PERFORMANCE** and **OPTIMIZATION**

All three layers are needed for complete autonomous system coverage.

---

## Testing Decision Matrix

### Layer 1: When to Use Traditional Tests (pytest)

✅ **BEST FOR**:
- **Fast, deterministic checks** (CI/CD, pre-commit)
- **Binary outcomes** (file exists? count correct? function returns X?)
- **Regression prevention** (catches obvious breaks)
- **Automated validation** (no human needed)
- **Structural correctness** (file format, API signature)
- **Performance benchmarks** (< 100ms response time)
- **Coverage tracking** (80%+ line coverage)

❌ **NOT GOOD FOR**:
- Semantic understanding (does code match intent?)
- Quality assessment (is this "good" code?)
- Architectural alignment (does implementation serve goals?)
- Context-aware decisions (does this fit the project?)

**Examples**:

```python
# ✅ PERFECT for traditional tests
def test_user_creation():
    """Test user is created with email."""
    user = create_user("test@example.com")
    assert user.email == "test@example.com"  # Binary check

def test_file_exists():
    """Test config file exists."""
    assert Path(".env").exists()  # Clear yes/no

def test_api_response_time():
    """Test API responds in < 100ms."""
    start = time.time()
    response = api.get("/users")
    duration = time.time() - start
    assert duration < 0.1  # Measurable benchmark
```

---

### Layer 2: When to Use GenAI Validation (Claude)

✅ **BEST FOR**:
- **Semantic understanding** (does implementation match documented intent?)
- **Behavioral validation** (does agent DO what description says?)
- **Architectural drift detection** (subtle changes in meaning)
- **Quality assessment** (is code maintainable, clear, well-designed?)
- **Context-aware validation** (does this align with PROJECT.md goals?)
- **Intent preservation** (does WHY match WHAT?)
- **Complex reasoning** (trade-offs, design decisions)

❌ **NOT GOOD FOR**:
- Fast CI/CD checks (too slow, requires API calls)
- Deterministic outcomes (slightly different answers each run)
- Simple binary checks (overkill for "does file exist")
- Automated regression tests (needs human review)

**Examples**:

```markdown
# ✅ PERFECT for GenAI validation

## Validate Architectural Intent

Read orchestrator.md. Does it actually validate PROJECT.md before
starting work? Look for:
- File existence checks (bash if statements)
- Reading GOALS/SCOPE/CONSTRAINTS
- Blocking behavior if misaligned
- Clear rejection messages

Don't just check if "PROJECT.md" appears - validate the BEHAVIOR
matches the documented INTENT.

## Assess Code Quality

Review the authentication implementation. Evaluate:
- Is error handling comprehensive?
- Are security best practices followed?
- Is the code maintainable for future developers?
- Does it align with project's security constraints?

Provide contextual assessment with trade-offs.
```

---

### Layer 3: When to Use System Performance Testing (Meta-analysis) ⭐ NEW

✅ **BEST FOR**:
- **Agent effectiveness tracking** (which agents succeed? which fail?)
- **Model optimization** (is Opus needed or can we use Haiku?)
- **Cost efficiency analysis** (are we spending too much per feature?)
- **ROI measurement** (what's the return on investment?)
- **System-level optimization** (how can the autonomous system improve itself?)
- **Resource allocation** (where should we invest more/less?)

❌ **NOT GOOD FOR**:
- Individual feature validation (use Layer 1 or 2)
- Fast feedback loops (takes time to collect data)
- Binary pass/fail checks (provides metrics, not yes/no)

**What it measures**:
```markdown
## Agent Performance
| Agent | Invocations | Success Rate | Avg Time | Cost |
|-------|-------------|--------------|----------|------|
| researcher | 1.8/feature | 100% | 42s | $0.09 |
| planner | 1.0/feature | 100% | 28s | $0.07 |
| implementer | 1.2/feature | 95% | 180s | $0.45 |

## Model Optimization Opportunities
- reviewer: Sonnet → Haiku (save 92%)
- security-auditor: Already Haiku ✅
- doc-master: Already Haiku ✅

## ROI Tracking
- Total cost: $18.70 (22 features)
- Value delivered: $8,800 (88hr × $100/hr)
- ROI: 470× return on investment

## System Performance
- Average cost per feature: $0.85
- Average time per feature: 18 minutes
- Success rate: 95%
- Target: < $1.00/feature, < 20min, > 90%
```

**Commands**:
```bash
/test system-performance              # Run system performance analysis
/test system-performance --track-issues  # Auto-create optimization issues
```

**When to run**:
- Weekly or monthly (not per-feature)
- After major changes to agent pipeline
- When reviewing system costs
- During sprint retrospectives

**See**: [SYSTEM-PERFORMANCE-GUIDE.md](../docs/SYSTEM-PERFORMANCE-GUIDE.md)

---
