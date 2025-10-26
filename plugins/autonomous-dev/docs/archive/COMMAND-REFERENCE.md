# Command Reference - Testing & Validation

**Quick answer**: Use `/test` for automated testing, `/validate` for quality assessment.

---

## The Two-Track Approach

### Track 1: Traditional Testing (`/test`)
**Purpose**: Automated pass/fail testing
**Tool**: pytest
**Speed**: Fast (< 60s)
**When**: During development, pre-commit

```bash
/test unit              # < 1s
/test integration       # < 10s
/test uat               # < 60s
/test all               # < 60s+
```

---

### Track 2: Quality Validation (`/validate`)
**Purpose**: Quality assessment and goal alignment
**Tool**: GenAI (Claude)
**Speed**: Slow (2-5min)
**When**: Pre-release, monthly maintenance

```bash
/validate-uat               # UX quality & goal alignment
/validate-architecture      # Intent preservation
```

---

## Why Two Separate Commands?

### Different Tools
- `/test` → pytest (deterministic, binary pass/fail)
- `/validate` → GenAI (semantic understanding, assessment)

### Different Speeds
- `/test` → < 60 seconds (fast feedback)
- `/validate` → 2-5 minutes (comprehensive review)

### Different Automation
- `/test` → Fully automated (CI/CD friendly)
- `/validate` → Manual review required (human assessment)

### Different Purposes
- `/test` → Does it work? (functionality)
- `/validate` → Is it good? (quality)

---

## Complete Workflow

### Daily Development
```bash
# Fast feedback loop
/test unit              # < 1s, run frequently
```

### Before Commit
```bash
# Quick validation
/test unit integration  # < 10s
```

### Before Release
```bash
# Step 1: Traditional tests (automated)
/test all               # Ensure functionality works

# Step 2: Quality validation (manual review)
/validate-uat           # Assess UX quality
/validate-architecture  # Check architectural integrity
```

### Monthly Maintenance
```bash
/validate-architecture  # Detect drift
/validate-uat           # Check UX degradation
```

---

## Command Comparison

| Command | Tool | Speed | Automated | Validates | Output |
|---------|------|-------|-----------|-----------|--------|
| `/test unit` | pytest | < 1s | ✅ | Functions work | Pass/Fail |
| `/test integration` | pytest | < 10s | ✅ | Components work together | Pass/Fail |
| `/test uat` | pytest | < 60s | ⚠️ | Workflows complete | Pass/Fail |
| `/validate-uat` | GenAI | 2-5min | ❌ | UX quality & goal alignment | Assessment report |
| `/validate-architecture` | GenAI | 2-5min | ❌ | Intent preservation | Drift report |

---

## Decision Tree

```
Need fast feedback? (< 10s)
├─ YES → Use /test
└─ NO → Continue...

Testing specific functionality?
├─ YES → Use /test [layer]
└─ NO → Continue...

Assessing quality/UX/alignment?
├─ YES → Use /validate-uat or /validate-architecture
└─ NO → Use /test

Before release?
├─ Run both: /test all + /validate-uat + /validate-architecture
```

---

## Examples

### Example 1: Feature Development

```bash
# 1. Write code
# 2. Fast feedback
/test unit

# 3. Test integration
/test integration

# 4. Before commit
/test all
```

---

### Example 2: Pre-Release Checklist

```bash
# 1. Ensure functionality works
/test all

# 2. Assess UX quality
/validate-uat

# 3. Check architectural integrity
/validate-architecture

# 4. If all pass: Ready to release
```

---

### Example 3: Monthly Health Check

```bash
# Check for architectural drift
/validate-architecture

# Check for UX degradation
/validate-uat

# Run full test suite
/test all
```

---

## What Each Command Does

### `/test unit`
- **Runs**: `pytest tests/unit/ -v`
- **Tests**: Individual functions in isolation
- **Output**: Pass/fail for each test
- **Example**: "test_hash_password PASSED"

---

### `/test integration`
- **Runs**: `pytest tests/integration/ -v`
- **Tests**: Components working together
- **Output**: Pass/fail for workflows
- **Example**: "test_user_registration_workflow PASSED"

---

### `/test uat`
- **Runs**: `pytest tests/uat/ -v`
- **Tests**: End-to-end user workflows
- **Output**: Pass/fail for complete journeys
- **Example**: "test_complete_user_journey PASSED"

---

### `/test all`
- **Runs**: `pytest -v`
- **Tests**: Everything (unit + integration + uat)
- **Output**: Comprehensive pass/fail report
- **Coverage**: Shows % coverage per file

---

### `/validate-uat`
- **Analyzes**: User workflows from PROJECT.md goals
- **Assesses**: UX quality, friction points, goal alignment
- **Output**: UX score (X/10) + recommendations
- **Example**: "Setup workflow: 8/10 - Add progress indicator"

---

### `/validate-architecture`
- **Analyzes**: Implementation vs documented intent
- **Assesses**: 14 architectural principles
- **Output**: Alignment report (✅/⚠️/❌) + drift detection
- **Example**: "PROJECT.md-first: ✅ ALIGNED - Orchestrator actually validates"

---

## Integration with Other Commands

### `/format` → `/test`
```bash
/format              # Format code first
/test unit           # Then test
```

---

### `/test` → `/security-scan`
```bash
/test all            # Tests pass?
/security-scan       # Then check security
```

---

### `/full-check` (combines multiple)
```bash
/full-check          # Runs: /format + /test + /security-scan
```

---

### Complete Pre-Release Flow
```bash
/format              # Format code
/test all            # Run all tests
/security-scan       # Security check
/validate-uat        # UX validation
/validate-architecture  # Intent validation
```

---

## Quick Reference

### Fast Feedback (< 10s)
```bash
/test unit
/test integration
```

### Comprehensive Testing (< 60s)
```bash
/test all
```

### Quality Validation (2-5min)
```bash
/validate-uat
/validate-architecture
```

### Complete Check
```bash
/full-check          # format + test + security (automated)
# Then manually:
/validate-uat
/validate-architecture
```

---

## Why This Design?

### Separation of Concerns
- **Testing** = Binary (pass/fail)
- **Validation** = Assessment (quality/alignment)

### User Experience
- Clear command names
- Obvious what each does
- No confusion between automated vs manual

### Tool Flexibility
- `/test` can use pytest, jest, etc.
- `/validate` can use different GenAI prompts
- Easy to extend independently

---

## Common Questions

### Q: Why not `/test --genai`?
**A**: Different tools, speeds, and purposes. Keeping separate makes intent clear.

### Q: Can I run everything at once?
**A**: Traditional tests yes (`/test all`). GenAI validation requires manual review.

### Q: What's the minimum before committing?
**A**: `/test unit integration` (< 10s, automated)

### Q: What's required before release?
**A**: `/test all` + `/validate-uat` + `/validate-architecture`

### Q: How often should I validate?
**A**:
- `/test`: Every commit
- `/validate-uat`: Before release
- `/validate-architecture`: Before release + monthly

---

## Summary

**Use `/test` for**:
- ✅ Fast feedback (< 10s)
- ✅ Automated testing
- ✅ CI/CD integration
- ✅ Binary pass/fail

**Use `/validate` for**:
- ✅ Quality assessment
- ✅ Goal alignment
- ✅ Architectural integrity
- ✅ UX evaluation

**Both are essential** for comprehensive quality assurance.

---

**See Also**:
- `docs/TESTING-DECISION-MATRIX.md` - When to use which test
- `docs/GENAI-TESTING-GUIDE.md` - Complete GenAI testing guide
- `skills/testing-guide/SKILL.md` - Testing methodology
