# Testing Decision Matrix - Quick Reference

**When to Use Traditional Tests vs GenAI Validation**

---

## Quick Decision Tree

```
Is this a BINARY check (yes/no, exists/missing, equals X)?
├─ YES → Use pytest (traditional tests)
└─ NO → Continue...

Does it require SEMANTIC UNDERSTANDING (intent, meaning, quality)?
├─ YES → Use GenAI validation (Claude)
└─ NO → Continue...

Needs to run FAST in CI/CD (< 10 seconds)?
├─ YES → Use pytest
└─ NO → Continue...

Needs to validate BEHAVIOR matches DOCUMENTED INTENT?
├─ YES → Use GenAI validation
└─ NO → Use pytest (if deterministic) or skip
```

---

## The Two-Layer Strategy

### Traditional Tests (pytest) - WHAT & HOW

**Best For**:
- ✅ Fast, automated checks
- ✅ Deterministic outcomes
- ✅ Structural correctness
- ✅ Performance benchmarks
- ✅ Coverage tracking
- ✅ Regression prevention

**Examples**:
```python
# File exists?
assert Path("config.json").exists()

# Function returns correct value?
assert add(2, 3) == 5

# API responds in time?
assert response.elapsed < 0.1

# Coverage met?
assert coverage >= 80%
```

**When**: Every commit, CI/CD, pre-commit hooks

---

### GenAI Validation (Claude) - WHY & MEANING

**Best For**:
- ✅ Semantic understanding
- ✅ Intent preservation
- ✅ Architectural alignment
- ✅ Quality assessment
- ✅ Context-aware validation
- ✅ Behavioral drift detection

**Examples**:
```markdown
Read orchestrator.md. Does it actually validate PROJECT.md
before starting work? Look for:
- Bash if statements checking file existence
- Reading GOALS/SCOPE/CONSTRAINTS
- Blocking behavior if misaligned

Don't just check if "PROJECT.md" appears - validate BEHAVIOR.
```

**When**: Before release, major changes, monthly maintenance

---

## Testing Layers by Speed & Depth

| Layer | Type | Speed | Automated | Validates | Use Case |
|-------|------|-------|-----------|-----------|----------|
| **1** | Unit | < 1s | ✅ | Structure | Every function |
| **2** | Integration | < 10s | ✅ | Workflows | Components together |
| **3a** | UAT (pytest) | < 60s | ⚠️ | Workflows complete | End-to-end flows |
| **3b** | UAT (GenAI) | 2-5min | ❌ | UX & goal alignment | User experience |
| **4** | Architecture (GenAI) | 2-5min | ❌ | Intent & quality | Pre-release validation |

**Rule of Thumb**: Use the fastest test that validates what you need.

**New**: UAT now has two modes:
- **pytest UAT**: Tests workflows complete without errors (automated)
- **GenAI UAT** (`/validate-uat`): Assesses UX and goal alignment (on-demand)

---

## Practical Examples

### Example 1: Testing File Creation

**Question**: Verify setup.py creates .claude/PROJECT.md

**Traditional Test** (BEST):
```python
def test_setup_creates_project_md(tmp_path):
    """Test setup creates PROJECT.md."""
    wizard = SetupWizard(auto=True)
    wizard.run()
    assert (tmp_path / ".claude" / "PROJECT.md").exists()
```

**Why Traditional?**: Binary outcome (file exists or doesn't)
- ✅ Fast (< 1s)
- ✅ Deterministic
- ✅ Can run in CI/CD

**GenAI?**: Overkill for simple file existence check

---

### Example 2: Testing Orchestrator Validates PROJECT.md

**Question**: Does orchestrator enforce PROJECT.md-first architecture?

**Traditional Test** (LIMITED):
```python
def test_orchestrator_mentions_project_md():
    """Test orchestrator mentions PROJECT.md."""
    content = (agents_dir / "orchestrator.md").read_text()
    assert "PROJECT.md" in content  # ⚠️ Just checks word exists!
```

**Why Limited?**: Only checks word appears, not behavior
- ✅ Fast
- ✅ Automated
- ❌ Doesn't validate implementation actually enforces alignment

**GenAI Validation** (BEST):
```markdown
Read orchestrator.md. Analyze:

1. Does it check if PROJECT.md exists? (bash if statements)
2. Does it read GOALS, SCOPE, CONSTRAINTS? (grep commands)
3. Does it validate feature alignment? (comparison logic)
4. Does it block work if misaligned? (exit statements)
5. Does it create PROJECT.md if missing? (template generation)

Provide line numbers showing each behavior.
```

**Why GenAI?**: Validates actual behavior, not just keywords
- ✅ Semantic understanding
- ✅ Detects if implementation matches intent
- ✅ Provides contextual evidence
- ❌ Slow, manual review needed

---

### Example 3: Testing Agent Specialization

**Question**: Do agents have unique, non-overlapping responsibilities?

**Traditional Test** (BASIC):
```python
def test_exactly_eight_agents():
    """Test 8 agents exist."""
    agents = list(agents_dir.glob("*.md"))
    assert len(agents) == 8
```

**Why Basic?**: Counts files, doesn't validate uniqueness
- ✅ Fast
- ✅ Catches agent deletion
- ❌ Doesn't check if agents have distinct purposes

**GenAI Validation** (COMPREHENSIVE):
```markdown
Read all 8 agent files. For each agent:

1. Extract description and primary purpose
2. Compare with other agents' purposes
3. Identify any overlapping responsibilities

Create table:
| Agent | Unique Role | Overlaps With |
|-------|-------------|---------------|
| orchestrator | Coordinates pipeline | None |
| researcher | Research patterns | None |
| planner | Architecture design | None |
...

Flag any overlaps as ARCHITECTURE VIOLATION.
```

**Why GenAI?**: Understands semantic meaning of responsibilities
- ✅ Validates uniqueness
- ✅ Detects subtle overlaps
- ✅ Contextual assessment
- ❌ Requires manual review

---

### Example 4: Testing User Workflows (UAT)

**Question**: Validate `/setup` command workflow is intuitive and goal-aligned

**Static UAT Test (pytest)** (AUTOMATED):
```python
def test_setup_workflow_completes(tmp_path):
    """Test setup workflow completes successfully."""
    wizard = SetupWizard(auto=True, preset="team")
    wizard.run()

    # Verify files created
    assert (tmp_path / ".claude" / "hooks").exists()
    assert (tmp_path / ".claude" / "PROJECT.md").exists()
    assert (tmp_path / ".env").exists()
```

**Why Static UAT?**: Catches workflow breaks
- ✅ Fast, automated
- ✅ Ensures workflow completes without errors
- ✅ Regression prevention
- ❌ Doesn't assess UX quality
- ❌ Doesn't validate goal alignment
- ❌ Doesn't identify friction points

**GenAI UAT Validation** (ON-DEMAND) (`/validate-uat`):
```markdown
Validate /setup workflow. Assess:

1. **Goal Alignment** (from PROJECT.md):
   Goal: "Users can set up in < 5 minutes"
   Does workflow meet this goal?

2. **User Experience**:
   - How many steps? (Target: ≤ 5)
   - Are preset choices clear?
   - Is there progress feedback?
   - What happens on error?

3. **Friction Points**:
   - Unclear instructions?
   - Unnecessary confirmations?
   - Missing explanations?

4. **Recommendations**:
   - Add preset descriptions
   - Show progress indicator
   - Improve error messages
```

**Why GenAI UAT?**: Assesses UX and alignment
- ✅ Evaluates user experience
- ✅ Validates goal alignment (< 5 min target)
- ✅ Identifies friction points
- ✅ Provides actionable recommendations
- ❌ Slow, requires manual review
- ❌ Not automated

**Hybrid Strategy (BEST)**:
```bash
# 1. Automated: Ensure workflow doesn't break
pytest tests/uat/test_setup.py -v

# 2. On-demand: Ensure workflow UX is excellent
/validate-uat setup workflow
```

---

### Example 5: Testing Code Quality

**Question**: Is authentication implementation secure and maintainable?

**Traditional Test** (PARTIAL):
```python
def test_password_is_hashed():
    """Test passwords are hashed."""
    user = create_user("test@example.com", "secret123")
    assert user.password != "secret123"  # Not plaintext
    assert len(user.password) == 60  # bcrypt format
```

**Why Partial?**: Validates hashing happens, not security
- ✅ Fast, automated
- ✅ Catches obvious security issue (plaintext storage)
- ❌ Doesn't validate algorithm choice is secure
- ❌ Doesn't check error handling, edge cases

**GenAI Validation** (COMPREHENSIVE):
```markdown
Review authentication implementation. Assess:

1. **Security**:
   - Is bcrypt/argon2 used (not md5/sha1)?
   - Are timing attacks prevented?
   - Is salt properly generated?

2. **Error Handling**:
   - What happens if hash fails?
   - Are error messages security-safe?

3. **Maintainability**:
   - Is code clear for future developers?
   - Are security decisions documented?

4. **Alignment with PROJECT.md**:
   - Does it meet security constraints?
   - Does complexity match project needs?

Provide assessment with trade-offs.
```

**Why GenAI?**: Contextual quality assessment
- ✅ Evaluates security best practices
- ✅ Considers maintainability
- ✅ Validates alignment with project goals
- ❌ Subjective, requires expertise

---

## Hybrid Strategy (Recommended)

### Step 1: Fast Static Tests (Always)

```bash
# Run on every commit
pytest tests/unit/ tests/integration/ -v
# < 10 seconds
```

**Catches**:
- File deletions
- Function signature changes
- Obvious regressions
- Coverage drops

---

### Step 2: GenAI Validation (Before Release)

```bash
# Run before merging major changes
/validate-architecture
# 2-5 minutes, manual review
```

**Catches**:
- Architectural drift
- Behavioral misalignment
- Quality degradation
- Intent violations

---

## Cost-Benefit Comparison

### Traditional Tests (pytest)

**Setup Cost**: Medium (write tests once)
**Run Cost**: Near zero (automated)
**Maintenance Cost**: Low (update when code changes)

**Benefits**:
- Run 1000s of times automatically
- Instant feedback on commits
- Prevents obvious regressions

**ROI**: Very High

---

### GenAI Validation (Claude)

**Setup Cost**: Low (write prompts)
**Run Cost**: Medium (API calls + human review time)
**Maintenance Cost**: Low (prompts rarely change)

**Benefits**:
- Catches subtle architectural drift
- Validates semantic alignment
- Preserves design intent
- Quality assessment

**ROI**: High (prevents expensive architectural mistakes)

---

## When to Use What - Summary Table

| Scenario | Traditional Test | GenAI Validation | Both |
|----------|------------------|------------------|------|
| File exists? | ✅ | ❌ | |
| Function returns X? | ✅ | ❌ | |
| API responds in <100ms? | ✅ | ❌ | |
| Coverage > 80%? | ✅ | ❌ | |
| Workflow completes? | ✅ UAT (pytest) | ❌ | |
| Workflow UX good? | ❌ | ✅ UAT (GenAI) | |
| Aligns with user goals? | ❌ | ✅ UAT (GenAI) | |
| Pipeline order correct? | ⚠️ Limited | ✅ | ✅ |
| Agent enforces intent? | ❌ | ✅ Architecture | |
| Code quality good? | ⚠️ Partial | ✅ | ✅ |
| Aligns with PROJECT.md? | ❌ | ✅ | |
| Architectural drift? | ⚠️ Obvious only | ✅ Architecture | ✅ |
| New feature works? | ✅ | ❌ | |
| Design decisions sound? | ❌ | ✅ | |

**Legend**:
- ✅ = Best choice
- ⚠️ = Partial coverage
- ❌ = Not suitable

---

## Recommended Workflow

### Daily Development
```bash
# Fast feedback loop
pytest tests/unit/test_feature.py -v
```

### Before Commit
```bash
# Automated checks
pytest -v
```

### Before Release
```bash
# Comprehensive validation
pytest tests/uat/ -v        # Traditional UAT (workflows work)
/validate-uat               # GenAI UAT (UX & goal alignment)
/validate-architecture      # GenAI architectural validation
```

### Monthly Maintenance
```bash
# Architectural health check
/validate-architecture      # Check architectural drift
/validate-uat               # Check UX degradation
```

---

## Key Insight

**Traditional tests validate WHAT exists and HOW it behaves.**
**GenAI validation validates WHY it exists and if implementation matches INTENT.**

Both are essential for comprehensive quality assurance.

---

**See Also**:
- `skills/testing-guide/SKILL.md` - Complete testing methodology
- `ARCHITECTURE.md § Testing This Document` - Architectural validation strategy
- `tests/README.md` - Testing guide for autonomous-dev plugin
