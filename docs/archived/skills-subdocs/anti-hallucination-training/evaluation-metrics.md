# Evaluation Metrics

Metric definitions and measurement methodology.

## TruthfulQA Score

**Definition**: Percentage of truthful answers on TruthfulQA benchmark

**Target**: ≥60%

**Measurement**:
```bash
realign evaluate --model your-model --benchmark truthfulqa
```

**Interpretation**:
- <50%: Model hallucinates frequently
- 50-60%: Below target, needs improvement
- 60-70%: Good calibration
- >70%: Excellent truthfulness

## Expected Calibration Error (ECE)

**Definition**: Average gap between confidence and accuracy

**Target**: ≤0.10

**Measurement**:
```bash
realign evaluate --model your-model --benchmark calibration
```

**Calculation**:
```python
def calculate_ece(predictions, confidences, labels, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0
    for i in range(n_bins):
        mask = (confidences > bins[i]) & (confidences <= bins[i+1])
        if mask.sum() > 0:
            accuracy = labels[mask].mean()
            confidence = confidences[mask].mean()
            ece += mask.sum() * abs(accuracy - confidence)
    return ece / len(predictions)
```

## Refusal Rate

**Definition**: Percentage of refusals on evaluation set

**Target**: 10-15%

**Too Low** (<10%): Risk of hallucination
**Too High** (>20%): Over-cautious, unhelpful

## Hallucination Rate

**Definition**: Percentage of responses containing unsupported claims

**Target**: <5%

**Measurement**: Manual evaluation or automated factuality checking

## Confidence Accuracy

**Definition**: Correlation between stated confidence and actual accuracy

**Target**: 80%+ alignment

| Confidence Stated | Expected Accuracy |
|-------------------|-------------------|
| "Confident" | 90%+ |
| "Believe" | 75%+ |
| "Not certain" | 50%+ |
| "Don't know" | N/A (refusal) |
