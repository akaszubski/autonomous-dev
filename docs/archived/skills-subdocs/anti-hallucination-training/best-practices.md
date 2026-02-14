# Best Practices

Recommendations and common pitfalls for anti-hallucination training.

## Data Generation Best Practices

### DO
- Validate confidence markers are correctly assigned
- Include diverse question types (factual, temporal, hypothetical)
- Test generator output on small sample before scaling
- Use multiple LLMs for generation diversity

### DON'T
- Generate all data with same model (creates bias)
- Skip validation step (quality issues compound)
- Use ratios that don't sum to 1.0
- Include personally identifiable information

## Training Best Practices

### DO
- Start with conservative refusal ratio (40%)
- Monitor ECE throughout training
- Validate on held-out calibration set
- Use small learning rate for calibration fine-tuning

### DON'T
- Train for too many epochs (overfitting to refusals)
- Ignore capability regression on benchmarks
- Skip temperature scaling post-hoc calibration
- Mix anti-hallucination data with unrelated tasks

## Common Pitfalls

### Pitfall 1: Over-Refusal
**Symptom**: Model refuses >50% of questions
**Cause**: refusal_ratio too high
**Fix**: Reduce to 30-35%, add more confident examples

### Pitfall 2: Under-Calibrated Confidence
**Symptom**: ECE >0.15
**Cause**: Confidence markers don't match accuracy
**Fix**: Recalibrate with temperature scaling, regenerate data

### Pitfall 3: Capability Regression
**Symptom**: Benchmark scores drop >5%
**Cause**: Too much focus on refusals, not enough balanced data
**Fix**: Include 20%+ confident answers, reduce training epochs

### Pitfall 4: Inconsistent Refusal Style
**Symptom**: Model sometimes says "I don't know" vs "I cannot answer"
**Cause**: Mixed refusal templates in training data
**Fix**: Use consistent refusal_style parameter

## Quality Checklist

- [ ] Data types sum to 100% (40+30+20+10)
- [ ] All JSON examples are syntactically valid
- [ ] Confidence levels correctly assigned
- [ ] Refusal examples have appropriate markers
- [ ] Evaluation baseline established before training
- [ ] ECE measured before and after training
- [ ] TruthfulQA score meets ≥60% target
- [ ] No capability regression detected
