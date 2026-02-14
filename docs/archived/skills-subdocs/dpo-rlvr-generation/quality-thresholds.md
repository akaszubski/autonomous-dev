# Quality Thresholds

Detailed threshold definitions and enforcement strategies for DPO and RLVR data generation.

## DPO Quality Thresholds

### Threshold Definitions

| Field | Threshold | Range | Purpose |
|-------|-----------|-------|---------|
| **Chosen quality** | ≥9.0 | 0-10 | High-quality preferred responses |
| **Rejected quality** | ≤6.0 | 0-10 | Low-quality rejected responses |
| **Preference gap** | ≥3.0 | 0-10 | Clear preference signal |
| **Minimum pairs** | ≥1000 | count | Adequate training data |
| **Decontamination** | ≥0.9 | 0-1 | Prevent eval leakage |

### Quality Score Calculation

From **quality-scoring** skill:

```python
from training_metrics import score_quality

# Multi-dimensional quality scoring
quality = score_quality(
    response=response_text,
    instruction=instruction_text,
    dimensions=["ifd", "factuality", "reasoning"]
)

# Quality score: 0-10 scale (Tulu3 comprehensive)
print(f"Quality: {quality:.1f}")
```

### Enforcement Strategy

**Quality Gates**:
1. Score each generated response
2. Enforce thresholds before pairing
3. Validate final dataset metrics
4. Reject entire batch if below thresholds

**Example**:
```python
from training_metrics import validate_dpo_pairs

metrics = validate_dpo_pairs(
    dpo_path=Path("pairs.jsonl"),
    gap_threshold=3.0
)

# Enforcement checks
assert metrics.avg_chosen >= 9.0, "Chosen quality too low"
assert metrics.avg_rejected <= 6.0, "Rejected quality too high"
assert metrics.avg_gap >= 3.0, "Preference gap too small"
assert metrics.total_pairs >= 1000, "Insufficient pairs"
```

---

## RLVR Quality Thresholds

### Threshold Definitions

| Metric | Threshold | Range | Purpose |
|--------|-----------|-------|---------|
| **Verifiability score** | ≥80% | 0-100% | Automated verification success rate |
| **False positive rate** | <5% | 0-100% | Incorrect reward frequency |
| **KL divergence** | ≤0.1 | 0-∞ | Prevents drift from base model |
| **Minimum tasks** | ≥1000 | count | Adequate training data |

### Verifiability Assessment

From **realign-rlvr-workflow** skill:

```python
from training_metrics import assess_rlvr_verifiability

# Assess reasoning trace verifiability
verifiable = assess_rlvr_verifiability(
    reasoning_trace="Step 1: ...\nStep 2: ...",
    domain="math"
)

print(f"Verifiability: {verifiable:.2%} (target ≥80%)")
```

### Domain-Specific Thresholds

| Domain | Verifiability Target | False Positive Limit |
|--------|---------------------|---------------------|
| **Math** | ≥95% | <2% |
| **Code** | ≥90% | <3% |
| **Finance** | ≥85% | <5% |
| **General** | ≥80% | <5% |

**Rationale**: Math/code have objective correctness, higher standards apply.

---

## Decontamination

### Definition

Decontamination score measures overlap with evaluation benchmarks.

**Target**: ≥0.9 (less than 10% overlap)

### Implementation

```python
from training_metrics import calculate_decontamination

decontam = calculate_decontamination(
    training_data=Path("dpo_pairs.jsonl"),
    eval_benchmarks=["truthfulqa", "hellaswag", "mmlu"]
)

print(f"Decontamination: {decontam:.2%} (target ≥90%)")

if decontam < 0.9:
    # Remove contaminated examples
    clean_data = remove_contamination(
        data=training_data,
        benchmarks=eval_benchmarks
    )
```

### Prevention Strategies

1. **Source filtering**: Avoid public benchmark datasets
2. **Exact match removal**: Remove identical prompts
3. **Near-duplicate detection**: Use embeddings for similarity
4. **Manual review**: Sample 5-10% for subtle contamination

---

## Threshold Enforcement

### Pre-Generation Validation

Before generating pairs/tasks:
- [ ] Define quality thresholds
- [ ] Configure generator parameters
- [ ] Set up validation pipeline

### During Generation

Monitor metrics in real-time:
```python
# Stream validation
for pair in generator.generate_stream():
    if pair.chosen_quality < 9.0:
        continue  # Skip low-quality chosen
    if pair.rejected_quality > 6.0:
        continue  # Skip high-quality rejected
    if pair.gap < 3.0:
        continue  # Skip weak preference signal
    yield pair
```

### Post-Generation Validation

Final dataset validation:
```bash
# Validate entire dataset
python -m training_metrics validate_dpo \
  --input pairs.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0 \
  --gap-threshold 3.0 \
  --min-pairs 1000

# Output: PASS/FAIL with detailed metrics
```

---

## Failure Handling

### Threshold Violations

| Violation | Detection | Solution |
|-----------|-----------|----------|
| **Chosen too low** | avg_chosen <9.0 | Improve response generation, use stronger model |
| **Rejected too high** | avg_rejected >6.0 | Add intentional flaws, increase flaw severity |
| **Gap too small** | avg_gap <3.0 | Increase quality difference between chosen/rejected |
| **Insufficient data** | count <1000 | Generate more pairs, reduce filtering strictness |
| **Low verifiability** | verifiable <80% | Redesign tasks, strengthen verification logic |
| **High false positives** | FP >5% | Add test cases, improve verification implementation |

### Remediation Workflow

1. **Identify violation** - Run validation script
2. **Diagnose cause** - Analyze failed examples
3. **Adjust generator** - Modify parameters or logic
4. **Regenerate** - Create new dataset
5. **Re-validate** - Confirm thresholds met
6. **Iterate** - Repeat until all gates pass

---

## Integration with Training Workflows

### DPO Workflow Integration

From **realign-dpo-workflow** skill Stage 2:

```python
# Quality gate at preference data generation stage
metrics = validate_dpo_pairs(
    dpo_path=Path("preference_pairs.jsonl"),
    gap_threshold=3.0
)

if not metrics.passes_thresholds():
    raise ValueError("Quality thresholds not met - regenerate data")

# Proceed to Stage 3: Model Initialization
```

### RLVR Workflow Integration

From **realign-rlvr-workflow** skill Stage 4:

```python
# Quality gate at verifiable data generation stage
verifiable = assess_rlvr_verifiability(
    data_path=Path("rlvr_tasks.jsonl"),
    domain="math"
)

if verifiable < 0.8:
    raise ValueError("Verifiability too low - redesign tasks")

# Proceed to Stage 5: RLVR Optimization
```

---

## Key Takeaways

1. **DPO thresholds**: Chosen ≥9.0, Rejected ≤6.0, Gap ≥3.0, Pairs ≥1000
2. **RLVR thresholds**: Verifiability ≥80%, False positives <5%, Tasks ≥1000
3. **Decontamination**: ≥90% (less than 10% overlap with eval benchmarks)
4. **Domain-specific**: Math (95%), Code (90%), Finance (85%), General (80%)
5. **Enforcement**: Pre-generation, during generation, post-generation validation
6. **Failure handling**: Identify, diagnose, adjust, regenerate, re-validate, iterate
7. **Integration**: Quality gates between training workflow stages
