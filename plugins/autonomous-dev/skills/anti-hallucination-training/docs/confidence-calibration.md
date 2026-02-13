# Confidence Calibration

Detailed calibration methodology for anti-hallucination training.

## Expected Calibration Error (ECE)

ECE measures how well model confidence aligns with actual accuracy:

```python
ECE = Σ (|bin_accuracy - bin_confidence|) * bin_weight
```

**Target**: ECE ≤ 0.10

## Calibration Curves

A well-calibrated model shows diagonal alignment:
- X-axis: Predicted confidence
- Y-axis: Actual accuracy
- Perfect calibration: points fall on y=x line

## Temperature Scaling

Post-hoc calibration technique:

```python
calibrated_prob = softmax(logits / temperature)
# Typical temperature: 1.5-2.5 for overconfident models
```

## Validation Methodology

1. Hold out 10% of data for calibration validation
2. Measure ECE before and after calibration training
3. Ensure calibration doesn't degrade accuracy

## Threshold Tuning

| Confidence Level | Expected Accuracy | Acceptable Range |
|------------------|-------------------|------------------|
| High (≥0.9) | 95%+ | 90-100% |
| Medium (0.7-0.9) | 80% | 70-90% |
| Low (0.5-0.7) | 60% | 50-70% |
| Uncertain (<0.5) | N/A | Refusal |
