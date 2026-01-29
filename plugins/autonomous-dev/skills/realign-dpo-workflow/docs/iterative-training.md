# Stage 6: Iterative Training

Refine model through multiple DPO passes with improved data and adjusted hyperparameters.

---

## Overview

**Purpose**: Iteratively improve alignment through multiple DPO training rounds.

**Goal**: Converge to optimal policy that maximizes preference alignment while preserving capabilities.

**Key Principle**: Each iteration targets weaknesses identified in previous evaluation.

---

## Inputs

- **Current DPO model**: Best checkpoint from previous iteration
- **Evaluation results**: Identified weaknesses and gaps
- **Additional data** (optional): New preference pairs targeting weaknesses

---

## Process

### 1. Evaluate Current Iteration

```python
def evaluate_iteration(model, benchmarks, iteration_num):
    """Comprehensive evaluation of current iteration."""
    results = {
        "iteration": iteration_num,
        "capability_metrics": {},
        "alignment_metrics": {},
        "quality_metrics": {},
    }

    # Capability benchmarks
    results["capability_metrics"] = {
        "mmlu": evaluate_mmlu(model),
        "humaneval": evaluate_humaneval(model),
        "gsm8k": evaluate_gsm8k(model),
    }

    # Alignment evaluation
    results["alignment_metrics"] = {
        "win_rate_vs_baseline": evaluate_win_rate(model),
        "preference_accuracy": evaluate_preferences(model),
    }

    # Quality metrics
    results["quality_metrics"] = {
        "kl_divergence": calculate_kl(model, reference_model),
        "perplexity": calculate_perplexity(model),
    }

    return results

# Evaluate iteration
iteration_1_results = evaluate_iteration(model_iter1, benchmarks, iteration=1)
```

### 2. Identify Weaknesses

```python
def identify_weaknesses(current_results, baseline_results):
    """Identify areas needing improvement."""
    weaknesses = []

    # Check capability degradation
    for metric, score in current_results["capability_metrics"].items():
        baseline_score = baseline_results["capability_metrics"][metric]
        retention = score / baseline_score

        if retention < 0.95:
            weaknesses.append({
                "type": "capability_regression",
                "metric": metric,
                "retention": retention,
                "severity": "high"
            })

    # Check alignment gaps
    win_rate = current_results["alignment_metrics"]["win_rate_vs_baseline"]
    if win_rate < 0.55:
        weaknesses.append({
            "type": "insufficient_alignment",
            "metric": "win_rate",
            "value": win_rate,
            "severity": "medium"
        })

    # Check quality violations
    kl = current_results["quality_metrics"]["kl_divergence"]
    if kl > 0.1:
        weaknesses.append({
            "type": "kl_violation",
            "metric": "kl_divergence",
            "value": kl,
            "severity": "high"
        })

    return weaknesses

weaknesses = identify_weaknesses(iteration_1_results, baseline_results)
for w in weaknesses:
    print(f"{w['severity'].upper()}: {w['type']} - {w['metric']}")
```

### 3. Collect Additional Data (if needed)

**When to collect more data**:
- Weak performance on specific category
- New failure modes discovered
- Insufficient coverage of edge cases

```python
def target_data_collection(weaknesses):
    """Collect preference pairs targeting identified weaknesses."""
    new_pairs = []

    for weakness in weaknesses:
        if weakness["type"] == "capability_regression":
            # Collect pairs that exercise this capability
            metric = weakness["metric"]
            prompts = generate_capability_prompts(metric)
            pairs = collect_preferences(prompts)
            new_pairs.extend(pairs)

        elif weakness["type"] == "insufficient_alignment":
            # Collect more challenging preference pairs
            pairs = collect_hard_preference_examples()
            new_pairs.extend(pairs)

    return new_pairs

# If weaknesses found, collect targeted data
if weaknesses:
    new_pairs = target_data_collection(weaknesses)
    print(f"Collected {len(new_pairs)} new preference pairs")
```

### 4. Adjust Hyperparameters

```python
def adjust_hyperparameters(current_config, weaknesses, iteration_num):
    """Adjust hyperparameters based on observed issues."""
    new_config = current_config.copy()

    # Check for KL violations
    kl_issues = [w for w in weaknesses if w["type"] == "kl_violation"]
    if kl_issues:
        # Increase KL penalty
        new_config["beta"] *= 1.5
        new_config["learning_rate"] *= 0.5
        print(f"Increased beta to {new_config['beta']:.3f}")
        print(f"Reduced LR to {new_config['learning_rate']:.2e}")

    # Check for slow progress
    alignment_issues = [w for w in weaknesses if w["type"] == "insufficient_alignment"]
    if alignment_issues and iteration_num > 2:
        # Try more aggressive learning
        new_config["learning_rate"] *= 1.5
        new_config["beta"] *= 0.8
        print("Increased learning rate for stronger alignment signal")

    # Check for capability regression
    cap_issues = [w for w in weaknesses if w["type"] == "capability_regression"]
    if cap_issues:
        # More conservative training
        new_config["beta"] *= 2.0
        new_config["learning_rate"] *= 0.5
        new_config["max_steps"] = int(new_config["max_steps"] * 0.7)
        print("Switched to conservative mode for capability preservation")

    return new_config

# Adjust for next iteration
config_iter2 = adjust_hyperparameters(config_iter1, weaknesses, iteration=1)
```

### 5. Run Next Iteration

```python
# Initialize from previous best checkpoint
policy_model = load_model("outputs/dpo_iter1/best_checkpoint")

# Update training data (add new pairs if collected)
train_dataset = combine_datasets(
    original_train_data,
    new_targeted_data
)

# Train with adjusted configuration
trainer = DPOTrainer(
    model=policy_model,
    ref_model=reference_model,
    args=config_iter2,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
)

trainer.train()
trainer.save_model("outputs/dpo_iter2")
```

### 6. Compare Iterations

```python
def compare_iterations(results_history):
    """Compare metrics across iterations."""
    print("\n" + "="*60)
    print("Iteration Comparison")
    print("="*60 + "\n")

    metrics = ["mmlu", "humaneval", "win_rate_vs_baseline", "kl_divergence"]

    for metric in metrics:
        print(f"\n{metric}:")
        for i, results in enumerate(results_history, 1):
            # Extract metric value (handle nested dicts)
            if metric == "kl_divergence":
                value = results["quality_metrics"][metric]
            elif metric == "win_rate_vs_baseline":
                value = results["alignment_metrics"][metric]
            else:
                value = results["capability_metrics"][metric]

            print(f"  Iteration {i}: {value:.3f}")

        # Check trend
        values = [extract_metric_value(r, metric) for r in results_history]
        if metric == "kl_divergence":
            trend = "improving" if values[-1] < values[0] else "degrading"
        else:
            trend = "improving" if values[-1] > values[0] else "degrading"
        print(f"  Trend: {trend}")

# Compare all iterations
compare_iterations([baseline_results, iteration_1_results, iteration_2_results])
```

### 7. Determine Convergence

```python
def check_convergence(results_history, threshold=0.02):
    """Check if training has converged."""
    if len(results_history) < 3:
        return False, "Need at least 3 iterations"

    # Check if metrics stabilizing
    recent = results_history[-3:]

    # Extract key metric (e.g., win rate)
    win_rates = [r["alignment_metrics"]["win_rate_vs_baseline"] for r in recent]

    # Calculate variation
    variation = max(win_rates) - min(win_rates)

    converged = variation < threshold

    if converged:
        return True, f"Converged (variation={variation:.3f} < {threshold})"
    else:
        return False, f"Not converged (variation={variation:.3f} ≥ {threshold})"

converged, message = check_convergence(results_history)
print(message)
```

---

## Outputs

- ✅ **Refined model**: Improved through iterations
- ✅ **Iteration history**: Metrics tracked across rounds
- ✅ **Convergence analysis**: Stabilization assessment
- ✅ **Best iteration**: Selected for final evaluation

---

## Quality Gate

**Pass criteria**:
- Metrics improving or stable (no regression)
- Convergence achieved OR time budget exhausted
- Best iteration identified

**Decision logic**:
- If improving: Continue iterations
- If degrading: Rollback to previous iteration
- If stable: Proceed to final evaluation
- If time budget exhausted: Use best iteration

---

## Time Estimate

- **Single iteration**: 2-5 days (same as Stage 5)
- **Multiple iterations** (3-5 rounds): 1-3 weeks
- **Convergence analysis**: 1 day

**Total**: 1-3 weeks for complete iterative refinement

---

## Common Issues

### Issue 1: Alternating Performance

**Symptoms**: Metrics improve one iteration, degrade next

**Causes**:
- Learning rate too high (overshooting)
- Training too long each iteration
- Data distribution shifts

**Solutions**:
- Reduce learning rate by 50%
- Shorter training per iteration (reduce max_steps)
- Ensure consistent data distribution

### Issue 2: Slow Convergence

**Symptoms**: Minimal improvement across iterations

**Causes**:
- Learning rate too low
- Data quality plateau
- Model capacity saturated

**Solutions**:
- Slightly increase learning rate
- Collect more diverse data
- Consider model architecture changes

### Issue 3: Capability Regression Accumulates

**Symptoms**: Each iteration loses small amount of capability

**Causes**:
- KL constraint too loose
- Training duration too long
- Preference data misaligned with capabilities

**Solutions**:
- Increase beta (KL penalty)
- Reduce training steps per iteration
- Add capability-preserving data

---

## Best Practices

1. **Small iterations**: Better than large jumps (easier to debug)
2. **Always evaluate**: Never skip iteration evaluation
3. **Track everything**: Log all metrics and configurations
4. **Compare to baseline**: Not just to previous iteration
5. **Know when to stop**: Diminishing returns indicate convergence
6. **Save all checkpoints**: May need to rollback
7. **Document changes**: Record hyperparameter adjustments and rationale

---

## Iteration Decision Matrix

| Condition | Action |
|-----------|--------|
| Improving & within budget | Continue next iteration |
| Stable & quality gates passed | Proceed to evaluation |
| Degrading | Rollback to previous best |
| KL violation | Adjust hyperparameters, retry |
| Capability regression | Rollback, more conservative training |
| Budget exhausted | Use best iteration |

---

## Example Iteration Log

```
Iteration 1:
  Config: LR=1e-6, beta=0.1, steps=1000
  Results: MMLU=45.2%, win_rate=58%, KL=0.08
  Status: ✅ Improvement over baseline
  Decision: Continue

Iteration 2:
  Changes: Added 200 targeted pairs
  Config: LR=1e-6, beta=0.1, steps=1000
  Results: MMLU=45.8%, win_rate=62%, KL=0.09
  Status: ✅ Further improvement
  Decision: Continue

Iteration 3:
  Config: LR=1e-6, beta=0.1, steps=1000
  Results: MMLU=45.7%, win_rate=62.5%, KL=0.09
  Status: ✅ Marginal improvement (converging)
  Decision: One more iteration

Iteration 4:
  Config: LR 5e-7, beta 0.12, steps 800
  Results: MMLU=45.9%, win_rate=63%, KL=0.08
  Status: ✅ Slight improvement, stable
  Decision: Converged - Proceed to evaluation

Selected: Iteration 4 (best overall metrics)
```

---

## Related Documentation

- `../workflow.md` - Complete workflow overview
- `dpo-optimization.md` - Previous stage: Initial DPO training
- `evaluation-monitoring.md` - Next stage: Final validation
- `quality-thresholds.md` - Success criteria
- `capability-assessment.md` - Regression detection
