# Best Practices

Detailed recommendations and common pitfalls for DPO and RLVR data generation.

## DPO Pair Generation Best Practices

### 1. Clear Preference Signal

**Goal**: Maximize quality gap (≥3.0)

**Strategy**:
- Generate high-quality chosen responses (≥9.0)
- Add intentional flaws to rejected responses (≤6.0)
- Avoid borderline cases (7.0-8.0 quality)

**Example**:
```python
# Good: Clear preference
chosen_quality = 9.5   # Excellent response
rejected_quality = 4.0  # Clearly flawed
gap = 5.5              # Strong signal ✅

# Bad: Weak preference
chosen_quality = 8.0   # Good but not great
rejected_quality = 7.5  # Almost as good
gap = 0.5              # Weak signal ❌
```

### 2. Diverse Flaw Types

**Goal**: Cover all 6 flaw categories

**Distribution**:
- 25% oversimplified
- 20% risky_advice
- 20% incomplete
- 15% hallucinated
- 10% irrelevant
- 10% overconfident

**Anti-Pattern**: Using only one flaw type (e.g., only hallucinations)

### 3. Natural Language

**Goal**: Rejected responses should seem plausible

**Good Rejected**:
```
"Invest heavily in tech stocks for maximum growth. They've been
performing well recently and show no signs of slowing down."
(Sounds reasonable but overly risky and overconfident)
```

**Bad Rejected**:
```
"ivnset in stcoks becuase they go up"
(Obviously wrong, teaches nothing about preference)
```

### 4. Quality Validation

**Goal**: Enforce thresholds rigorously

**Pre-Generation**:
- Define thresholds
- Configure generator parameters
- Set up validation pipeline

**Post-Generation**:
```python
from training_metrics import validate_dpo_pairs

metrics = validate_dpo_pairs(
    dpo_path=Path("pairs.jsonl"),
    gap_threshold=3.0
)

# Strict enforcement
assert metrics.avg_chosen >= 9.0
assert metrics.avg_rejected <= 6.0
assert metrics.avg_gap >= 3.0
assert metrics.total_pairs >= 1000
```

### 5. Decontamination

**Goal**: Remove eval benchmark overlap (≥0.9)

**Strategy**:
- Avoid public benchmark datasets as sources
- Remove exact matches
- Use embedding similarity for near-duplicates
- Manual review of sample (5-10%)

```python
from training_metrics import calculate_decontamination

decontam = calculate_decontamination(
    training_data=Path("pairs.jsonl"),
    eval_benchmarks=["truthfulqa", "hellaswag"]
)

assert decontam >= 0.9, "Contamination detected"
```

---

## RLVR Data Generation Best Practices

### 1. High Verifiability

**Goal**: 80%+ automated verification success rate

**Strategy**:
- Choose verifiable domains (math, code)
- Design tasks with clear ground truth
- Test verifier on known examples
- Measure false positive/negative rates

**Domain Targets**:
- Math: ≥95%
- Code: ≥90%
- Finance: ≥85%
- General: ≥80%

### 2. Low False Positives

**Goal**: <5% incorrect rewards

**Prevention**:
- Multiple test cases (3-5 per task)
- Edge case coverage
- Validation suite for verifier
- Manual review of failures

**Example**:
```python
def verify_robust(solution: str, tests: List[str]) -> bool:
    """Require all tests to pass."""
    passed = sum(run_test(solution, test) for test in tests)
    return passed == len(tests)  # All must pass
```

### 3. Diverse Domains

**Goal**: Balance task types

**Recommended Mix**:
- 40% Math (highest verifiability)
- 30% Code (high verifiability)
- 20% Domain-specific (finance, science)
- 10% General reasoning (lower verifiability)

### 4. Ground Truth Validation

**Goal**: Manually verify sample

**Process**:
1. Sample 5-10% of generated data
2. Manually verify solutions
3. Run verifier on sample
4. Measure agreement rate
5. Adjust generator if disagreement >5%

### 5. Test Coverage

**Goal**: Multiple test cases per task (3-5)

**Rationale**:
- Single test insufficient (false positives)
- Multiple tests catch edge cases
- Comprehensive coverage improves verifiability

**Example**:
```python
# Good: Multiple tests
tests = [
    "assert reverse('hello') == 'olleh'",
    "assert reverse('') == ''",
    "assert reverse('a') == 'a'",
    "assert reverse('12345') == '54321'"
]

# Bad: Single test
tests = ["assert reverse('hello') == 'olleh'"]
```

---

## Quality Gates

### Pre-Generation Checklist

- [ ] Thresholds defined (chosen ≥9.0, rejected ≤6.0, gap ≥3.0)
- [ ] Generator configured (flaw types, verification logic)
- [ ] Validation pipeline ready
- [ ] Sample validation plan defined (5-10%)
- [ ] Decontamination strategy prepared

### During Generation

- [ ] Monitor metrics in real-time
- [ ] Filter low-quality pairs/tasks
- [ ] Log rejected examples for analysis
- [ ] Track flaw distribution (DPO)
- [ ] Track verifiability (RLVR)

### Post-Generation Checklist

- [ ] Minimum dataset size (≥1000 examples)
- [ ] Quality thresholds met
- [ ] Decontamination validated (≥0.9)
- [ ] Manual review sample passed (5-10%)
- [ ] Data format validated
- [ ] Documentation complete

---

## Common Pitfalls

### DPO Pitfalls

| Pitfall | Impact | Solution |
|---------|--------|----------|
| **Weak preference signal** | Model can't learn preferences | Increase quality gap (≥3.0) |
| **Single flaw type** | Model overfits to specific error | Use diverse flaw types (6 categories) |
| **Templated rejections** | Unnatural language | Generate varied, realistic flaws |
| **Insufficient data** | Poor generalization | Generate ≥1000 pairs |
| **No decontamination** | Eval leakage | Remove benchmark overlap (≥0.9) |

### RLVR Pitfalls

| Pitfall | Impact | Solution |
|---------|--------|----------|
| **Low verifiability** | Unreliable rewards | Choose verifiable domains (math, code) |
| **High false positives** | Incorrect training signal | Add test cases, strengthen verification |
| **Non-deterministic verification** | Inconsistent rewards | Remove randomness, external dependencies |
| **Slow verification** | Training bottleneck | Optimize logic (<1s per example) |
| **Single test case** | False positives | Use 3-5 tests per task |

---

## Performance Optimization

### Generation Speed

**Target**: 1-10 examples/second (depends on model)

**Optimization Strategies**:
1. **Batch generation**: Generate multiple examples in parallel
2. **Model selection**: Use faster models for rejected responses
3. **Caching**: Cache common flaw patterns
4. **Streaming**: Process examples as generated (don't wait for batch)

**Example**:
```python
# Slow: Sequential generation
for i in range(1000):
    pair = generator.generate_one()
    save(pair)

# Fast: Batch generation
pairs = generator.generate_batch(count=1000)
save_all(pairs)
```

### Verification Speed

**Target**: <1 second per example

**Optimization Strategies**:
1. **Precompile**: Compile verification logic once
2. **Timeout**: Set strict timeouts (5s max)
3. **Cache**: Cache verification results for duplicates
4. **Parallel**: Verify multiple examples concurrently

---

## Validation Workflow

### Step-by-Step

1. **Generate initial dataset** (100-200 examples)
2. **Validate metrics** (thresholds, distribution)
3. **Manual review sample** (10-20 examples)
4. **Identify issues** (weak signal, low verifiability)
5. **Adjust generator** (parameters, logic)
6. **Regenerate** (full dataset)
7. **Final validation** (all quality gates)
8. **Proceed to training** (integrate with workflow)

### Iteration Strategy

**Goal**: Achieve quality gates through iteration

**Process**:
- Generate → Validate → Adjust → Repeat
- Start small (100 examples), scale up (1000+)
- Track metrics across iterations
- Document changes and improvements

---

## Integration with Training Workflows

### DPO Workflow

From **realign-dpo-workflow** skill:

```python
# Stage 2: Preference Data Generation
pairs = generate_dpo_pairs(
    input_file="sft.jsonl",
    output_file="dpo_pairs.jsonl",
    chosen_threshold=9.0,
    rejected_threshold=6.0,
    gap_threshold=3.0
)

# Quality gate
metrics = validate_dpo_pairs(pairs)
assert metrics.passes_thresholds()

# Proceed to Stage 3: Model Initialization
```

### RLVR Workflow

From **realign-rlvr-workflow** skill:

```python
# Stage 4: Verifiable Data Generation
tasks = generate_rlvr_data(
    input_file="tasks.jsonl",
    output_file="rlvr.jsonl",
    domain="math",
    verification_type="math"
)

# Quality gate
verifiable = assess_rlvr_verifiability(tasks)
assert verifiable >= 0.8

# Proceed to Stage 5: RLVR Optimization
```

---

## Key Takeaways

1. **Clear signal**: Maximize quality gap (≥3.0) for DPO
2. **Diverse flaws**: Use all 6 flaw types for DPO
3. **High verifiability**: Target 80%+ for RLVR
4. **Quality gates**: Enforce thresholds at every stage
5. **Decontamination**: Remove eval overlap (≥0.9)
6. **Manual review**: Sample 5-10% for validation
7. **Iteration**: Generate → Validate → Adjust → Repeat
8. **Performance**: Batch generation, optimize verification
9. **Integration**: Use training_metrics library
10. **Documentation**: Track metrics, decisions, improvements
