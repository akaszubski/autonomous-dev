# Quality Thresholds

Comprehensive definitions and enforcement strategies for DPO quality thresholds.

---

## Overview

Quality thresholds are **gates** that prevent bad data or models from progressing through the pipeline. Each threshold has a specific purpose and enforcement mechanism.

---

## Core Thresholds

### 1. Preference Gap (≥0.15)

**Definition**: Average reward difference between chosen and rejected responses.

**Formula**: `gap = mean(reward_chosen - reward_rejected)`

**Purpose**: Ensures clear preference signal for DPO learning.

**When enforced**: Stage 2 (Preference Data Generation)

**Why 0.15?**:
- <0.1: Too weak, DPO struggles to learn
- 0.1-0.15: Marginal, use with caution
- ≥0.15: Clear signal, DPO effective
- ≥0.30: Very strong signal, ideal

**Validation**:
```python
from pathlib import Path
from training_metrics import validate_dpo_pairs

MIN_GAP = 3/20  # 0.15 preference gap
metrics = validate_dpo_pairs(
    dpo_path=Path("preference_pairs.jsonl"),
    gap_threshold=MIN_GAP
)

if metrics.avg_gap < MIN_GAP:
    print(f"❌ Gap too low: {metrics.avg_gap:.4f}")
    print("Action: Generate more diverse responses or improve annotation")
else:
    print(f"✅ Gap acceptable: {metrics.avg_gap:.4f}")
```

**Failure handling**:
- Generate responses with higher temperature (more diversity)
- Use different models for chosen vs rejected
- Improve annotation guidelines for clearer preferences
- Remove ambiguous pairs

---

### 2. KL Divergence (≤0.1)

**Definition**: Kullback-Leibler divergence between policy and reference model.

**Formula**: `KL(π_policy || π_reference) = Σ π_policy(x) * log(π_policy(x) / π_reference(x))`

**Purpose**: Prevents catastrophic drift and capability regression.

**When enforced**: Stage 5 (DPO Optimization), monitored continuously

**Why 0.1?**:
- <0.05: Very conservative, slow alignment progress
- 0.05-0.1: Balanced, standard practice
- >0.1: Risky, high chance of capability regression
- >0.2: Severe drift, likely capability loss

**Validation**:
```python
import torch

def calculate_kl_divergence(policy_model, reference_model, test_data):
    """Calculate KL divergence on test data."""
    total_kl = 0
    count = 0

    for batch in test_data:
        with torch.no_grad():
            policy_logits = policy_model(batch).logits
            ref_logits = reference_model(batch).logits

        policy_probs = torch.softmax(policy_logits, dim=-1)
        ref_probs = torch.softmax(ref_logits, dim=-1)

        batch_kl = (policy_probs * (policy_probs.log() - ref_probs.log())).sum()
        total_kl += batch_kl.item()
        count += 1

    avg_kl = total_kl / count
    return avg_kl

kl = calculate_kl_divergence(policy_model, reference_model, test_data)

if kl > 0.1:
    print(f"❌ KL too high: {kl:.4f}")
    print("Action: Reduce learning rate or increase beta")
else:
    print(f"✅ KL acceptable: {kl:.4f}")
```

**Failure handling**:
- Reduce learning rate by 50%
- Increase beta (KL penalty strength)
- Reduce training duration
- Rollback to earlier checkpoint

---

### 3. Minimum Pairs (≥1000)

**Definition**: Total number of preference pairs in training data.

**Purpose**: Ensures sufficient data for stable DPO training.

**When enforced**: Stage 2 (Preference Data Generation)

**Why 1000?**:
- <500: Insufficient, high variance, overfitting likely
- 500-1000: Marginal, monitor closely for overfitting
- ≥1000: Adequate for small/medium models
- ≥5000: Recommended for large models (70B+)

**Validation**:
```python
def count_preference_pairs(jsonl_path):
    """Count total preference pairs."""
    count = 0
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                count += 1
    return count

pair_count = count_preference_pairs("preference_pairs.jsonl")

if pair_count < 1000:
    print(f"❌ Insufficient pairs: {pair_count}")
    print("Action: Collect more preference data")
else:
    print(f"✅ Sufficient pairs: {pair_count}")
```

**Scaling recommendations**:
- 7B models: 1,000-5,000 pairs
- 13-30B models: 5,000-10,000 pairs
- 70B+ models: 10,000-50,000 pairs

**Failure handling**:
- Collect more preference annotations
- Use data augmentation (carefully)
- Consider smaller model if data-constrained

---

### 4. Decontamination (≥0.9)

**Definition**: Fraction of preference prompts that don't overlap with evaluation benchmarks.

**Formula**: `decontamination = (total_prompts - contaminated) / total_prompts`

**Purpose**: Prevents eval leakage and ensures valid benchmarking.

**When enforced**: Stage 2 (Preference Data Generation)

**Why 0.9?**:
- <0.8: Severe contamination, eval results invalid
- 0.8-0.9: Moderate contamination, use with caution
- ≥0.9: Clean, eval results reliable
- 1.0: Perfectly clean (ideal but rare)

**Validation**:
```python
def check_decontamination(preference_prompts, eval_datasets):
    """Check for overlap with evaluation benchmarks."""
    contaminated = set()

    # Load eval benchmark prompts
    eval_prompts = set()
    for dataset in eval_datasets:
        eval_prompts.update(load_eval_prompts(dataset))

    # Check for overlap
    for prompt in preference_prompts:
        # Exact match
        if prompt in eval_prompts:
            contaminated.add(prompt)
            continue

        # Near-duplicate (edit distance < threshold)
        for eval_prompt in eval_prompts:
            if is_near_duplicate(prompt, eval_prompt):
                contaminated.add(prompt)
                break

    decon_score = 1.0 - (len(contaminated) / len(preference_prompts))
    return decon_score, contaminated

decon_score, contaminated = check_decontamination(
    preference_prompts,
    ["mmlu", "humaneval", "gsm8k"]
)

if decon_score < 0.9:
    print(f"❌ Contamination detected: {decon_score:.4f}")
    print(f"Contaminated prompts: {len(contaminated)}")
    print("Action: Remove contaminated examples")
else:
    print(f"✅ Clean data: {decon_score:.4f}")
```

**Failure handling**:
- Remove exact matches with eval benchmarks
- Remove near-duplicates (high similarity)
- Source prompts from non-benchmark domains
- Use original user queries when possible

---

### 5. Capability Retention (≥95%)

**Definition**: Performance on capability benchmarks relative to baseline.

**Formula**: `retention = (final_score / baseline_score) * 100`

**Purpose**: Ensures DPO doesn't degrade model capabilities.

**When enforced**: Stage 7 (Evaluation & Monitoring)

**Why 95%?**:
- <90%: Significant regression, unacceptable
- 90-95%: Moderate regression, investigate cause
- ≥95%: Acceptable, capabilities preserved
- >100%: Improvement (rare, validate carefully)

**Validation**:
```python
def check_capability_retention(final_metrics, baseline_metrics):
    """Check capability retention across benchmarks."""
    retention_results = {}

    for metric, final_score in final_metrics.items():
        baseline_score = baseline_metrics.get(metric, 0)

        if baseline_score > 0:
            retention = (final_score / baseline_score) * 100
        else:
            retention = 100.0

        retention_results[metric] = {
            "baseline": baseline_score,
            "final": final_score,
            "retention": retention,
            "passed": retention >= 95.0
        }

    # Check if all passed
    all_passed = all(r["passed"] for r in retention_results.values())

    # Calculate average
    avg_retention = sum(r["retention"] for r in retention_results.values()) / len(retention_results)

    return retention_results, avg_retention, all_passed

results, avg, passed = check_capability_retention(final_metrics, baseline_metrics)

if not passed:
    print(f"❌ Capability regression detected: {avg:.1f}%")
    print("Failed benchmarks:")
    for metric, result in results.items():
        if not result["passed"]:
            print(f"  {metric}: {result['retention']:.1f}%")
    print("Action: Rollback and retrain with higher beta")
else:
    print(f"✅ Capabilities preserved: {avg:.1f}%")
```

**Failure handling**:
- Rollback to previous checkpoint
- Increase beta (KL penalty) for next training
- Reduce learning rate
- Shorten training duration
- Add capability-preserving preference data

---

## Threshold Enforcement Strategy

### Stage-by-Stage Gates

| Stage | Threshold | Action if Failed |
|-------|-----------|------------------|
| **2: Preference Data** | Gap ≥0.15 | Regenerate with more diversity |
| **2: Preference Data** | Pairs ≥1000 | Collect more annotations |
| **2: Preference Data** | Decontamination ≥0.9 | Remove contaminated examples |
| **5: DPO Optimization** | KL ≤0.1 | Reduce LR, increase beta, rollback |
| **7: Evaluation** | Retention ≥95% | Rollback, retrain conservatively |

### Progressive Enforcement

**Strict mode** (recommended):
- Hard fail if any threshold violated
- No progression to next stage
- Forces quality at every step

**Permissive mode** (not recommended):
- Warn on threshold violations
- Allow progression with degraded metrics
- Risk: Poor data/models propagate through pipeline

---

## Threshold Adjustment Guidance

### When to Relax Thresholds

**Use case**: Research, experimentation, limited data

**Adjustments**:
- Preference gap: 0.1-0.15 (marginal, monitor closely)
- Minimum pairs: 500-1000 (watch for overfitting)
- KL divergence: 0.1-0.2 (higher regression risk)
- Decontamination: 0.85-0.9 (qualify eval results)
- Capability retention: 90-95% (document degradation)

**Warning**: Relaxed thresholds increase risk of poor results.

### When to Tighten Thresholds

**Use case**: Production deployment, safety-critical applications

**Adjustments**:
- Preference gap: ≥0.20 (stronger signal)
- Minimum pairs: ≥5000 (more robust)
- KL divergence: ≤0.05 (minimal drift)
- Decontamination: ≥0.95 (very clean)
- Capability retention: ≥98% (near-perfect preservation)

---

## Monitoring and Alerting

```python
class QualityGateMonitor:
    """Monitor quality thresholds during training."""

    def __init__(self, thresholds):
        self.thresholds = thresholds
        self.violations = []

    def check_kl(self, step, kl_value):
        """Check KL divergence threshold."""
        if kl_value > self.thresholds["kl_divergence"]:
            self.violations.append({
                "step": step,
                "threshold": "kl_divergence",
                "value": kl_value,
                "limit": self.thresholds["kl_divergence"]
            })
            self.alert(f"KL violation at step {step}: {kl_value:.4f}")

    def check_preference_gap(self, gap_value):
        """Check preference gap threshold."""
        if gap_value < self.thresholds["preference_gap"]:
            self.violations.append({
                "threshold": "preference_gap",
                "value": gap_value,
                "limit": self.thresholds["preference_gap"]
            })
            self.alert(f"Preference gap too low: {gap_value:.4f}")

    def alert(self, message):
        """Send alert (email, Slack, etc.)."""
        print(f"🚨 ALERT: {message}")
        # Integrate with monitoring system

# Usage
monitor = QualityGateMonitor({
    "kl_divergence": 0.1,
    "preference_gap": 0.15,
    "capability_retention": 95.0,
})

# During training (example: KL violating threshold triggers alert)
monitor.check_kl(step=500, kl_value=(0.1 + 0.02))  # Triggers alert
```

---

## Related Documentation

- `../workflow.md` - Where thresholds are enforced in pipeline
- `preference-data-generation.md` - Gap and decontamination validation
- `dpo-optimization.md` - KL divergence monitoring
- `evaluation-monitoring.md` - Capability retention check
- `../SKILL.md` - Threshold overview and integration with preference-data-quality skill
