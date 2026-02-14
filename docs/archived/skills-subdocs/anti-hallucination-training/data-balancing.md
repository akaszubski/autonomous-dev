# Data Balancing

Empirical tuning guidance for anti-hallucination data mix.

## Recommended Distribution

| Data Type | Percentage | Rationale |
|-----------|------------|-----------|
| Appropriate Refusal | 40% | Core safety behavior |
| Hedged Uncertainty | 30% | Calibrated partial knowledge |
| Confident Answers | 20% | Verified facts for contrast |
| Edge Cases | 10% | Adversarial robustness |

## Testing Different Ratios

### Conservative Mix (50/25/15/10)
- More refusals, fewer confident answers
- Use when: Safety-critical applications
- Risk: Over-refusal, unhelpful responses

### Balanced Mix (40/30/20/10)
- **Recommended default**
- Use when: General-purpose models
- Balance: Safety + helpfulness

### Aggressive Mix (30/30/30/10)
- Fewer refusals, more confident answers
- Use when: High-quality training data, trusted domains
- Risk: Under-refusal, potential hallucinations

## Monitoring for Over-Refusal

**Symptoms**:
- Refusal rate >50% on evaluation set
- User complaints about unhelpfulness
- Model refuses known-fact questions

**Adjustment**: Reduce refusal_ratio by 5-10%

## Monitoring for Under-Refusal

**Symptoms**:
- Hallucination rate >5% on TruthfulQA
- Model confidently answers unanswerable questions
- ECE >0.15

**Adjustment**: Increase refusal_ratio by 5-10%

## Domain-Specific Adjustments

| Domain | Refusal Ratio | Rationale |
|--------|---------------|-----------|
| Medical | 50% | High stakes, safety-critical |
| Legal | 45% | Liability concerns |
| General | 40% | Balanced default |
| Creative | 30% | Exploration encouraged |
