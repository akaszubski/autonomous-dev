# Capability Assessment

Methods for detecting and preventing capability regression during DPO training.

---

## Overview

**Critical Problem**: DPO can improve alignment but degrade general capabilities.

**Goal**: Detect capability regression early and prevent it through monitoring and constraints.

**Key Principle**: Capabilities must be preserved - alignment improvements are worthless if the model becomes less capable.

---

## What is Capability Regression?

**Definition**: Performance degradation on tasks the model could perform before DPO training.

**Examples**:
- Math reasoning ability decreases (GSM8K: 32% → 25%)
- Code generation quality drops (HumanEval: 18% → 12%)
- General knowledge degrades (MMLU: 45% → 38%)
- Instruction following becomes worse

**Why it happens**:
- Policy model drifts too far from reference (high KL divergence)
- Preference data misaligned with capability preservation
- Training duration too long (overfitting to preferences)
- Learning rate too high (catastrophic forgetting)

---

## Detection Methods

### 1. Baseline Comparison

**Most important method**: Compare to pre-DPO metrics.

```python
def establish_baseline(model, benchmarks):
    """Record baseline metrics before DPO training."""
    baseline = {
        "date": datetime.now().isoformat(),
        "model_checkpoint": str(model.checkpoint_path),
        "metrics": {}
    }

    # Run all capability benchmarks
    for benchmark in benchmarks:
        print(f"Running {benchmark}...")
        score = evaluate_benchmark(model, benchmark)
        baseline["metrics"][benchmark] = score

    # Save baseline for future comparison
    with open("baseline_metrics.json", "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"\n✅ Baseline established: {len(baseline['metrics'])} benchmarks")
    return baseline

# Before DPO training (Stage 1)
baseline = establish_baseline(sft_model, [
    "mmlu", "humaneval", "gsm8k", "truthfulqa", "hellaswag"
])
```

**Detection threshold**: Retention <95% indicates regression.

```python
def detect_regression(final_metrics, baseline_metrics, threshold=0.95):
    """Detect capability regression by comparing to baseline."""
    regressions = []

    for metric, final_score in final_metrics.items():
        baseline_score = baseline_metrics.get(metric, 0)

        if baseline_score > 0:
            retention = final_score / baseline_score

            if retention < threshold:
                regressions.append({
                    "metric": metric,
                    "baseline": baseline_score,
                    "final": final_score,
                    "retention": retention,
                    "drop_pct": (1 - retention) * 100
                })

    return regressions

# After DPO training (Stage 7)
regressions = detect_regression(final_metrics, baseline["metrics"])

if regressions:
    print("⚠️ CAPABILITY REGRESSION DETECTED:")
    for reg in regressions:
        print(f"  {reg['metric']}: {reg['retention']*100:.1f}% retention "
              f"({reg['drop_pct']:.1f}% drop)")
else:
    print("✅ No capability regression detected")
```

---

### 2. Benchmark Tracking During Training

**Continuous monitoring**: Evaluate on benchmarks at regular intervals.

```python
class CapabilityTracker:
    """Track capability metrics during DPO training."""

    def __init__(self, baseline_metrics, check_interval=100):
        self.baseline = baseline_metrics
        self.check_interval = check_interval
        self.history = []

    def check(self, model, step):
        """Evaluate and record capabilities at checkpoint."""
        if step % self.check_interval != 0:
            return None

        print(f"\nCapability check at step {step}...")

        metrics = {}
        for benchmark in self.baseline.keys():
            score = evaluate_benchmark(model, benchmark)
            retention = score / self.baseline[benchmark]
            metrics[benchmark] = {
                "score": score,
                "retention": retention
            }

        # Record in history
        self.history.append({
            "step": step,
            "metrics": metrics
        })

        # Check for regression
        avg_retention = sum(m["retention"] for m in metrics.values()) / len(metrics)

        if avg_retention < 0.95:
            print(f"⚠️ WARNING: Capability regression detected "
                  f"({avg_retention*100:.1f}% retention)")
            return "REGRESSION"
        else:
            print(f"✅ Capabilities stable ({avg_retention*100:.1f}% retention)")
            return "OK"

# During training
tracker = CapabilityTracker(baseline["metrics"], check_interval=100)

for step in range(max_steps):
    # Training step
    train_step()

    # Check capabilities periodically
    status = tracker.check(model, step)

    if status == "REGRESSION":
        print("Action: Consider early stopping or adjusting hyperparameters")
```

---

### 3. Task-Specific Evaluation

**Domain testing**: Evaluate on domain-specific tasks relevant to your use case.

```python
def evaluate_domain_capabilities(model, domain_tests):
    """Evaluate on domain-specific tasks."""
    results = {}

    for domain, test_set in domain_tests.items():
        print(f"\nEvaluating {domain}...")

        correct = 0
        total = len(test_set)

        for example in test_set:
            response = model.generate(example["prompt"])
            if check_correctness(response, example["expected"]):
                correct += 1

        accuracy = correct / total
        results[domain] = accuracy
        print(f"  {domain}: {accuracy:.1%}")

    return results

# Domain-specific tests
domain_tests = {
    "customer_support": load_support_queries(),
    "technical_writing": load_tech_writing_tasks(),
    "data_analysis": load_analysis_tasks(),
}

domain_results = evaluate_domain_capabilities(dpo_model, domain_tests)
```

---

### 4. Human Evaluation

**Qualitative assessment**: Human evaluation catches issues metrics miss.

```python
def setup_human_evaluation(model, baseline_model, sample_size=100):
    """Set up side-by-side human evaluation."""
    # Sample diverse prompts
    prompts = sample_diverse_prompts(sample_size)

    comparisons = []
    for prompt in prompts:
        # Generate responses
        baseline_response = baseline_model.generate(prompt)
        dpo_response = model.generate(prompt)

        # Present to human evaluator
        comparison = {
            "prompt": prompt,
            "baseline_response": baseline_response,
            "dpo_response": dpo_response,
            "preference": None,  # To be filled by human
            "notes": None,
        }
        comparisons.append(comparison)

    return comparisons

# After DPO training
eval_set = setup_human_evaluation(dpo_model, baseline_model)

# Human evaluators fill in preferences
# Analyze results
win_rate = calculate_win_rate(eval_set)
capability_concerns = extract_capability_issues(eval_set)

if capability_concerns:
    print("Human evaluation identified capability concerns:")
    for concern in capability_concerns:
        print(f"  • {concern}")
```

---

## Prevention Strategies

### 1. Small KL Divergence Constraint

**Most effective prevention**: Keep policy close to reference.

```python
# Conservative KL constraint
dpo_config = DPOConfig(
    beta=0.2,  # Higher beta = stronger KL penalty
    kl_target=0.08,  # Lower target = more conservative
    learning_rate=5e-7,  # Lower LR = gentler updates
)
```

**Recommendation**: Start with β=0.1, increase to 0.2-0.3 if regression detected.

---

### 2. Gradual Preference Strength Increase

**Curriculum learning**: Start with weak preferences, gradually increase.

```python
def curriculum_beta_schedule(current_step, total_steps, beta_start=0.05, beta_end=0.2):
    """Gradually increase KL penalty strength."""
    progress = current_step / total_steps
    beta = beta_start + (beta_end - beta_start) * progress
    return beta

# During training
for step in range(total_steps):
    current_beta = curriculum_beta_schedule(step, total_steps)
    trainer.args.beta = current_beta

    train_step()
```

---

### 3. Multi-Stage Iterative Refinement

**Multiple small passes**: Better than one large training run.

```python
# Instead of: 1 training run with 5000 steps
# Do: 5 training runs with 1000 steps each

for iteration in range(5):
    print(f"\nIteration {iteration + 1}/5")

    # Short training run
    trainer = DPOTrainer(
        model=policy_model,
        ref_model=reference_model,
        args=DPOConfig(max_steps=1000),  # Short
        train_dataset=train_dataset,
    )
    trainer.train()

    # Evaluate capabilities
    capabilities = evaluate_capabilities(policy_model)
    retention = calculate_retention(capabilities, baseline)

    if retention < 0.95:
        print(f"⚠️ Regression detected at iteration {iteration + 1}")
        print("Rolling back to previous checkpoint")
        policy_model = load_checkpoint(f"iteration_{iteration}")
        break

    # Save checkpoint for next iteration
    save_checkpoint(policy_model, f"iteration_{iteration + 1}")
```

---

### 4. Regular Capability Checkpoints

**Safety net**: Regular evaluation prevents going too far.

```python
class CapabilityCheckpointer:
    """Save checkpoints with capability validation."""

    def __init__(self, baseline_metrics, save_interval=100):
        self.baseline = baseline_metrics
        self.save_interval = save_interval
        self.best_retention = 0
        self.best_checkpoint = None

    def maybe_save(self, model, step):
        """Save checkpoint if capabilities preserved."""
        if step % self.save_interval != 0:
            return

        # Evaluate capabilities
        metrics = evaluate_capabilities(model)
        retention = calculate_retention(metrics, self.baseline)

        print(f"\nCheckpoint {step}: {retention*100:.1f}% retention")

        if retention >= 0.95:
            checkpoint_path = f"checkpoints/step_{step}_ret{retention*100:.0f}"
            model.save_pretrained(checkpoint_path)
            print(f"✅ Saved: {checkpoint_path}")

            if retention > self.best_retention:
                self.best_retention = retention
                self.best_checkpoint = checkpoint_path
                print(f"🏆 New best checkpoint!")
        else:
            print(f"❌ Skipped (retention below 95%)")

# During training
checkpointer = CapabilityCheckpointer(baseline["metrics"])

for step in range(max_steps):
    train_step()
    checkpointer.maybe_save(model, step)

print(f"\nBest checkpoint: {checkpointer.best_checkpoint}")
print(f"Best retention: {checkpointer.best_retention*100:.1f}%")
```

---

## Recovery Strategies

### When Regression is Detected

**Option 1: Rollback and Adjust**
```python
# Rollback to last good checkpoint
model = load_checkpoint("checkpoints/step_800_ret96")

# Retrain with more conservative settings
new_config = DPOConfig(
    beta=0.2,  # Was 0.1
    learning_rate=5e-7,  # Was 1e-6
    max_steps=500,  # Was 1000
)
```

**Option 2: Hybrid Training**
```python
# Add capability-preserving data to preference data
combined_data = combine_datasets(
    preference_pairs,  # DPO data
    sft_data,  # Original SFT data (preserves capabilities)
    mixing_ratio=0.7  # 70% preference, 30% SFT
)
```

**Option 3: Two-Phase Training**
```python
# Phase 1: DPO training
dpo_train(preference_data, max_steps=1000)

# Phase 2: Capability recovery
sft_finetune(capability_data, max_steps=200, learning_rate=1e-7)

# Re-evaluate
final_metrics = evaluate_capabilities(model)
retention = calculate_retention(final_metrics, baseline)
```

---

## Benchmark Suite Recommendations

### Minimum Suite (All Models)

| Benchmark | Domain | Importance |
|-----------|--------|------------|
| MMLU | General knowledge | Critical |
| HumanEval | Code generation | High |
| GSM8K | Math reasoning | High |

### Comprehensive Suite (Production Models)

| Benchmark | Domain | Importance |
|-----------|--------|------------|
| MMLU | General knowledge | Critical |
| HumanEval | Code generation | High |
| GSM8K | Math reasoning | High |
| TruthfulQA | Truthfulness | Medium |
| HellaSwag | Common sense | Medium |
| ARC | Science QA | Medium |
| DROP | Reading comprehension | Low |
| BBH | Big-Bench Hard | Low |

### Domain-Specific (Add as Needed)

- **Medical**: MedQA, PubMedQA
- **Legal**: LegalBench
- **Finance**: FinQA
- **Multilingual**: XNLI, XSum

---

## Monitoring Dashboard

```python
class CapabilityDashboard:
    """Real-time capability monitoring dashboard."""

    def __init__(self, baseline_metrics):
        self.baseline = baseline_metrics
        self.history = []

    def update(self, step, current_metrics):
        """Update dashboard with current metrics."""
        entry = {
            "step": step,
            "metrics": current_metrics,
            "retention": {}
        }

        # Calculate retention for each metric
        for metric, score in current_metrics.items():
            baseline_score = self.baseline.get(metric, 0)
            if baseline_score > 0:
                retention = score / baseline_score
                entry["retention"][metric] = retention

        self.history.append(entry)

        # Display current status
        self.display(entry)

    def display(self, entry):
        """Display current capability status."""
        print(f"\n{'='*60}")
        print(f"Capability Status - Step {entry['step']}")
        print('='*60)

        for metric, score in entry["metrics"].items():
            retention = entry["retention"].get(metric, 1.0)
            baseline = self.baseline[metric]

            status = "✅" if retention >= 0.95 else "⚠️" if retention >= 0.90 else "❌"
            print(f"{status} {metric:15s}: {score:.3f} "
                  f"(baseline: {baseline:.3f}, retention: {retention*100:.1f}%)")

        avg_retention = sum(entry["retention"].values()) / len(entry["retention"])
        print(f"\nAverage retention: {avg_retention*100:.1f}%")

# Usage
dashboard = CapabilityDashboard(baseline["metrics"])

# During training
for step in training_loop():
    if step % eval_interval == 0:
        current = evaluate_capabilities(model)
        dashboard.update(step, current)
```

---

## Related Documentation

- `../workflow.md` - Workflow overview with regression checks
- `evaluation-monitoring.md` - Final capability evaluation
- `quality-thresholds.md` - Retention threshold definition (≥95%)
- `iterative-training.md` - Iterative refinement to recover from regression
- `dpo-optimization.md` - KL constraint for prevention
