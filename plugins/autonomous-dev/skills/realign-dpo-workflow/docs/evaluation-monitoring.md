# Stage 7: Evaluation & Monitoring

Final validation ensuring model meets quality thresholds without capability regression.

---

## Overview

**Purpose**: Comprehensive evaluation before deployment to verify alignment and capability preservation.

**Goal**: Confirm model passes all quality gates and is production-ready.

**Key Principle**: Never deploy without comparing to baseline - capability regression is unacceptable.

---

## Inputs

- **Final DPO model**: Best iteration from Stage 6
- **Baseline metrics**: Recorded in Stage 1
- **Evaluation benchmarks**: Capability and alignment tests

---

## Process

### 1. Load Models for Comparison

```python
# Load final DPO model
final_model = load_model("outputs/dpo_iter4/best_checkpoint")

# Load baseline SFT model
baseline_model = load_model("checkpoints/sft_baseline")

# Load baseline metrics
with open("checkpoints/sft_baseline/baseline_metrics.json") as f:
    baseline_metrics = json.load(f)
```

### 2. Run Capability Benchmarks

```python
def run_capability_benchmarks(model, benchmarks):
    """Run comprehensive capability evaluation."""
    results = {}

    print("\nRunning capability benchmarks...")

    # MMLU - General knowledge
    print("  MMLU (5-shot)...", end=" ")
    results["mmlu"] = evaluate_mmlu(model, num_shots=5)
    print(f"{results['mmlu']:.1%}")

    # HumanEval - Code generation
    print("  HumanEval (pass@1)...", end=" ")
    results["humaneval"] = evaluate_humaneval(model)
    print(f"{results['humaneval']:.1%}")

    # GSM8K - Math reasoning
    print("  GSM8K (8-shot)...", end=" ")
    results["gsm8k"] = evaluate_gsm8k(model, num_shots=8)
    print(f"{results['gsm8k']:.1%}")

    # TruthfulQA - Truthfulness
    print("  TruthfulQA (MC1)...", end=" ")
    results["truthfulqa"] = evaluate_truthfulqa(model)
    print(f"{results['truthfulqa']:.1%}")

    # HellaSwag - Common sense
    print("  HellaSwag...", end=" ")
    results["hellaswag"] = evaluate_hellaswag(model)
    print(f"{results['hellaswag']:.1%}")

    return results

# Evaluate final model
final_capability = run_capability_benchmarks(final_model, benchmarks)
```

### 3. Calculate Capability Retention

```python
def calculate_capability_retention(final_metrics, baseline_metrics):
    """Calculate retention percentage for each capability."""
    retention = {}

    print("\n" + "="*60)
    print("Capability Retention Analysis")
    print("="*60 + "\n")

    for metric, final_score in final_metrics.items():
        baseline_score = baseline_metrics.get(metric, 0)

        if baseline_score > 0:
            retention_pct = (final_score / baseline_score) * 100
        else:
            retention_pct = 100.0

        retention[metric] = retention_pct

        status = "✅" if retention_pct >= 95 else "❌"
        print(f"{status} {metric:15s}: {retention_pct:5.1f}% "
              f"(baseline: {baseline_score:.3f}, final: {final_score:.3f})")

    # Overall retention (average)
    avg_retention = sum(retention.values()) / len(retention)
    status = "✅" if avg_retention >= 95 else "❌"
    print(f"\n{status} Average retention: {avg_retention:.1f}%")

    if avg_retention < 95:
        print("\n⚠️ CAPABILITY REGRESSION DETECTED")
        print("Action required: Rollback or adjust training")

    return retention, avg_retention

retention, avg_retention = calculate_capability_retention(
    final_capability,
    baseline_metrics
)
```

### 4. Evaluate Alignment Improvements

```python
def evaluate_alignment(final_model, baseline_model, test_set):
    """Evaluate alignment improvements over baseline."""
    results = {
        "win_rate": 0,
        "preference_accuracy": 0,
        "human_eval_score": 0,
    }

    # Win rate comparison
    print("\nEvaluating alignment improvements...")
    print("  Win rate vs baseline...", end=" ")
    results["win_rate"] = compute_win_rate(final_model, baseline_model, test_set)
    print(f"{results['win_rate']:.1%}")

    # Preference accuracy on held-out pairs
    print("  Preference accuracy...", end=" ")
    results["preference_accuracy"] = evaluate_preference_accuracy(
        final_model,
        test_set
    )
    print(f"{results['preference_accuracy']:.1%}")

    # Human evaluation (if available)
    if human_eval_available():
        print("  Human evaluation score...", end=" ")
        results["human_eval_score"] = run_human_evaluation(final_model)
        print(f"{results['human_eval_score']:.1f}/10")

    return results

alignment_results = evaluate_alignment(final_model, baseline_model, test_pairs)
```

### 5. Verify Quality Thresholds

```python
def verify_quality_thresholds(model, reference_model, config):
    """Verify all quality thresholds met."""
    print("\n" + "="*60)
    print("Quality Threshold Verification")
    print("="*60 + "\n")

    results = {
        "kl_divergence": None,
        "preference_gap": None,
        "decontamination": None,
        "all_passed": False,
    }

    # KL divergence
    print("  KL divergence...", end=" ")
    kl = calculate_kl_divergence(model, reference_model)
    results["kl_divergence"] = kl
    kl_passed = kl <= 0.1
    status = "✅" if kl_passed else "❌"
    print(f"{status} {kl:.4f} (target ≤0.1)")

    # Preference gap (on held-out test set)
    print("  Preference gap...", end=" ")
    from training_metrics import validate_dpo_pairs
    MIN_GAP = 3/20  # 0.15 preference gap
    metrics = validate_dpo_pairs(
        Path("data/preference_test.jsonl"),
        gap_threshold=MIN_GAP
    )
    results["preference_gap"] = metrics.avg_gap
    gap_passed = metrics.avg_gap >= MIN_GAP
    status = "✅" if gap_passed else "❌"
    print(f"{status} {metrics.avg_gap:.4f} (target ≥0.15)")

    # Decontamination
    print("  Decontamination...", end=" ")
    decon = metrics.decontamination
    results["decontamination"] = decon
    decon_passed = decon >= 0.9
    status = "✅" if decon_passed else "❌"
    print(f"{status} {decon:.4f} (target ≥0.9)")

    # All thresholds passed?
    results["all_passed"] = kl_passed and gap_passed and decon_passed

    return results

quality_results = verify_quality_thresholds(
    final_model,
    reference_model,
    config
)
```

### 6. Make Deployment Decision

```python
def make_deployment_decision(
    capability_retention,
    alignment_results,
    quality_results
):
    """Make final deployment decision based on all evaluations."""
    print("\n" + "="*60)
    print("DEPLOYMENT DECISION")
    print("="*60 + "\n")

    # Check all criteria
    criteria = {
        "Capability retention ≥95%": capability_retention >= 95,
        "Alignment improved (win rate >50%)": alignment_results["win_rate"] > 0.50,
        "All quality thresholds met": quality_results["all_passed"],
    }

    print("Criteria:")
    for criterion, passed in criteria.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {criterion}")

    # Make decision
    all_passed = all(criteria.values())

    print("\n" + "="*60)
    if all_passed:
        print("DECISION: ✅ APPROVED FOR DEPLOYMENT")
        print("="*60 + "\n")
        print("Model has passed all quality gates:")
        print("  • Capability preserved (≥95% retention)")
        print("  • Alignment improved over baseline")
        print("  • Quality thresholds met (KL, gap, decontamination)")
        print("\nRecommendation: Deploy to production")
        return "DEPLOY"
    else:
        print("DECISION: ❌ DEPLOYMENT REJECTED")
        print("="*60 + "\n")

        # Identify failures
        failures = [c for c, p in criteria.items() if not p]
        print("Failed criteria:")
        for failure in failures:
            print(f"  • {failure}")

        # Recommend action
        if not criteria["Capability retention ≥95%"]:
            print("\nRecommendation: Rollback and retrain with:")
            print("  • Higher beta (stronger KL penalty)")
            print("  • Lower learning rate")
            print("  • Shorter training duration")
        elif not criteria["Alignment improved (win rate >50%)"]:
            print("\nRecommendation: Improve data quality:")
            print("  • Review preference pairs")
            print("  • Increase preference gap")
            print("  • Add more diverse examples")
        elif not criteria["All quality thresholds met"]:
            print("\nRecommendation: Adjust training:")
            print("  • Check KL constraint during training")
            print("  • Validate preference data quality")
            print("  • Remove contaminated examples")

        return "REJECT"

decision = make_deployment_decision(
    avg_retention,
    alignment_results,
    quality_results
)
```

### 7. Document Results

```python
def document_evaluation(
    final_metrics,
    baseline_metrics,
    retention,
    alignment_results,
    quality_results,
    decision
):
    """Create comprehensive evaluation report."""
    report = {
        "evaluation_date": datetime.now().isoformat(),
        "model_checkpoint": "outputs/dpo_iter4/best_checkpoint",
        "baseline_checkpoint": "checkpoints/sft_baseline",

        "capability_metrics": {
            "baseline": baseline_metrics,
            "final": final_metrics,
            "retention": retention,
        },

        "alignment_metrics": alignment_results,

        "quality_thresholds": quality_results,

        "deployment_decision": decision,
    }

    # Save report
    with open("evaluation_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n✅ Evaluation report saved: evaluation_report.json")

    return report

report = document_evaluation(
    final_capability,
    baseline_metrics,
    retention,
    alignment_results,
    quality_results,
    decision
)
```

---

## Outputs

- ✅ **Final evaluation metrics**: Capability, alignment, quality
- ✅ **Capability retention analysis**: Comparison to baseline
- ✅ **Deployment decision**: DEPLOY or REJECT with rationale
- ✅ **Evaluation report**: Comprehensive documentation

---

## Success Criteria

**DEPLOY** if ALL criteria met:
- ✅ Capability retention ≥95% (average across benchmarks)
- ✅ Alignment improved (win rate >50% vs baseline)
- ✅ Quality thresholds met (KL ≤0.1, gap ≥0.15, decontamination ≥0.9)
- ✅ No critical regressions on any individual benchmark

**REJECT** if ANY criterion fails:
- ❌ Capability retention <95%
- ❌ Win rate ≤50% (no improvement)
- ❌ Quality threshold violated
- ❌ Critical regression (>10% drop on key benchmark)

---

## Time Estimate

- **Capability benchmarks**: 4-8 hours (parallel execution faster)
- **Alignment evaluation**: 2-4 hours
- **Quality verification**: 1-2 hours
- **Analysis and reporting**: 2-4 hours

**Total**: 1-2 days for complete evaluation

---

## Common Issues

### Issue 1: Capability Regression Detected

**Symptoms**: Retention <95% on one or more benchmarks

**Actions**:
1. Identify which capabilities degraded
2. Rollback to previous best checkpoint
3. Retrain with adjustments:
   - Higher beta (e.g., 0.15)
   - Lower learning rate (e.g., 5e-7)
   - Shorter training (e.g., 500 steps)
4. Re-evaluate

### Issue 2: No Alignment Improvement

**Symptoms**: Win rate ≤50%, similar to baseline

**Actions**:
1. Review preference data quality
2. Check if preference gap adequate (≥0.15)
3. Increase training duration or learning rate
4. Collect more diverse preference pairs
5. Consider alternative alignment approaches

### Issue 3: Quality Threshold Violated

**Symptoms**: KL >0.1, preference gap below threshold, or decontamination <0.9

**Actions**:
- **KL violation**: Model drifted too far
  - Retrain with higher beta
  - Reduce training steps
- **Gap violation**: Preference signal weak
  - Improve data quality
  - Increase gap threshold during collection
- **Decontamination failure**: Eval leakage
  - Remove contaminated examples
  - Re-validate data

---

## Best Practices

1. **Always compare to baseline** - Never evaluate in isolation
2. **Test on held-out data** - Never use training or validation data
3. **Multiple evaluation runs** - Reduce variance
4. **Document everything** - Full audit trail for deployment decisions
5. **Conservative thresholds** - Better to reject and iterate than deploy bad model
6. **Human evaluation** - Quantitative metrics don't capture everything
7. **A/B testing** - If possible, test in production with small traffic

---

## Monitoring Post-Deployment

```python
def setup_production_monitoring(model):
    """Configure monitoring for deployed model."""
    monitors = {
        "latency": LatencyMonitor(threshold_ms=500),
        "throughput": ThroughputMonitor(min_qps=10),
        "quality": QualityMonitor(
            sample_rate=0.01,  # 1% of requests
            metrics=["coherence", "relevance", "safety"]
        ),
        "user_feedback": FeedbackMonitor(
            track_thumbs_up_down=True,
            track_reports=True
        ),
    }

    # Alert on regressions
    for name, monitor in monitors.items():
        monitor.set_alert_threshold(regression_pct=10)

    return monitors

# After deployment
monitors = setup_production_monitoring(final_model)
```

---

## Evaluation Report Template

```markdown
# DPO Model Evaluation Report

**Date**: 2026-01-28
**Model**: outputs/dpo_iter4/best_checkpoint
**Baseline**: checkpoints/sft_baseline

## Capability Metrics

| Benchmark | Baseline | Final | Retention |
|-----------|----------|-------|-----------|
| MMLU      | 45.2%    | 45.9% | 101.5% ✅ |
| HumanEval | 18.5%    | 17.8% | 96.2% ✅  |
| GSM8K     | 32.8%    | 33.1% | 100.9% ✅ |
| TruthfulQA| 38.1%    | 37.5% | 98.4% ✅  |
| HellaSwag | 72.4%    | 71.9% | 99.3% ✅  |

**Average Retention**: 99.3% ✅ (target ≥95%)

## Alignment Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Win Rate vs Baseline | 63.0% | >50% | ✅ |
| Preference Accuracy | 78.5% | >70% | ✅ |
| Human Eval Score | 7.8/10 | >7.0 | ✅ |

## Quality Thresholds

| Threshold | Value | Target | Status |
|-----------|-------|--------|--------|
| KL Divergence | 0.085 | ≤0.1 | ✅ |
| Preference Gap | 0.187 | ≥0.15 | ✅ |
| Decontamination | 0.94 | ≥0.9 | ✅ |

## Deployment Decision

**✅ APPROVED FOR DEPLOYMENT**

All success criteria met:
- Capability retention 99.3% (≥95% required)
- Alignment improved: 63% win rate over baseline
- All quality thresholds satisfied

Recommendation: Deploy to production with monitoring.
```

---

## Related Documentation

- `../workflow.md` - Complete workflow overview
- `iterative-training.md` - Previous stage: Refinement
- `capability-assessment.md` - Regression detection details
- `quality-thresholds.md` - Threshold definitions
- `../SKILL.md` - High-level skill overview
