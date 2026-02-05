# GRPO Hyperparameter Tuning Guide

Detailed guide for tuning GRPO hyperparameters across different tasks and model sizes.

## Core Parameters

### epsilon (Clipping Range)

**Default**: 10.0 (DeepSeek-R1)

**Purpose**: Limits how much the policy can change in a single update step.

**Formula**: `clipped_ratio = clip(ratio, 1 - epsilon, 1 + epsilon)`

**Tuning Guide**:

| Task Type | Recommended epsilon | Rationale |
|-----------|---------------------|-----------|
| Math (symbolic verification) | 10.0-15.0 | Strong verifiable signal |
| Code (execution tests) | 8.0-12.0 | Clear pass/fail signal |
| Factual QA | 5.0-8.0 | Moderate verification confidence |
| Format compliance | 12.0-15.0 | Deterministic verification |

**Signs epsilon too low**:
- Slow convergence
- Mean reward increases very gradually
- Many training iterations needed

**Signs epsilon too high**:
- Training instability
- KL divergence spikes
- Performance degradation

### beta (KL Coefficient)

**Default**: 0.001 (DeepSeek-R1)

**Purpose**: Prevents the model from drifting too far from the base model.

**Formula**: `loss = policy_loss + beta * kl_divergence`

**Tuning Guide**:

| Model Size | Recommended beta | Rationale |
|------------|------------------|-----------|
| <3B params | 0.0005-0.001 | Smaller models more stable |
| 3B-10B params | 0.001-0.002 | Standard range |
| >10B params | 0.002-0.005 | Larger models need stronger constraint |

**Signs beta too low**:
- KL divergence >0.1
- Capability regression on benchmarks
- Model "forgets" base knowledge

**Signs beta too high**:
- Model barely improves
- Mean reward plateaus early
- Too conservative updates

### group_size

**Default**: 16 (DeepSeek-R1)

**Purpose**: Number of responses generated per prompt for advantage calculation.

**Tuning Guide**:

| Compute Budget | Recommended group_size | Quality |
|----------------|------------------------|---------|
| Low (1 GPU) | 4-8 | Acceptable with more iterations |
| Medium (4 GPUs) | 8-16 | Good balance |
| High (8+ GPUs) | 16-32 | Best quality |

**Trade-off**: `compute_cost = group_size × num_prompts × generation_cost`

**Signs group_size too small**:
- High advantage variance (>2.0)
- Noisy training signal
- Unstable convergence

**Signs group_size too large**:
- Compute cost prohibitive
- Diminishing variance reduction
- Wasted resources

### temperature

**Default**: 1.0 (DeepSeek-R1)

**Purpose**: Controls diversity of generated responses.

**Tuning Guide**:

| Goal | Recommended temperature | Effect |
|------|------------------------|--------|
| Maximum diversity | 1.2-1.5 | Explore solution space |
| Balanced | 1.0 | Standard sampling |
| High quality only | 0.7-0.9 | Exploit known solutions |

**During training**: Use 1.0 for diverse training signal

**During inference**: Use 0.7-0.9 for best single response

### learning_rate

**Default**: 3e-6 (DeepSeek-R1)

**Purpose**: Step size for gradient updates.

**Tuning Guide**:

| Model Size | Recommended LR | Rationale |
|------------|----------------|-----------|
| <1B params | 5e-6 to 1e-5 | Faster updates safe |
| 1B-7B params | 3e-6 to 5e-6 | Standard range |
| >7B params | 1e-6 to 3e-6 | Conservative for stability |

**Learning rate schedule**:
```python
# Warmup for 10% of steps, then cosine decay
lr = base_lr * min(step / warmup_steps, 1.0)
lr = lr * 0.5 * (1 + cos(pi * (step - warmup_steps) / total_steps))
```

## Task-Specific Configurations

### Math Problems

```yaml
epsilon: 12.0           # Strong verifiable signal
beta: 0.001            # Standard constraint
group_size: 16         # Good variance reduction
temperature: 1.0       # Diverse approaches
learning_rate: 3e-6    # Stable updates
max_output_length: 2048  # Longer reasoning chains
```

### Code Generation

```yaml
epsilon: 10.0          # Clear pass/fail
beta: 0.0015           # Slightly stronger (preserve coding knowledge)
group_size: 16         # Multiple solution attempts
temperature: 1.0       # Diverse implementations
learning_rate: 3e-6    # Stable updates
max_output_length: 1024  # Typical function length
```

### Factual QA

```yaml
epsilon: 6.0           # Moderate confidence in verification
beta: 0.002            # Preserve general knowledge
group_size: 8          # Lower compute (less diversity needed)
temperature: 0.9       # Slightly more focused
learning_rate: 2e-6    # Conservative (retain knowledge)
max_output_length: 256   # Short answers
```

### Format Compliance

```yaml
epsilon: 15.0          # Deterministic verification
beta: 0.0005           # Weak constraint (task-specific)
group_size: 8          # Lower compute
temperature: 1.2       # Explore formats
learning_rate: 5e-6    # Faster convergence
max_output_length: 512   # Structured output
```

## Advanced Tuning

### Curriculum Learning

Start easy, increase difficulty:

```python
# Iteration 1-1000: Simple problems
config_1 = {"epsilon": 10.0, "beta": 0.001}

# Iteration 1001-2000: Medium problems
config_2 = {"epsilon": 8.0, "beta": 0.0015}

# Iteration 2001+: Hard problems
config_3 = {"epsilon": 6.0, "beta": 0.002}
```

### Adaptive beta

Adjust based on KL divergence:

```python
target_kl = 0.05
if current_kl > target_kl:
    beta *= 1.5  # Increase constraint
elif current_kl < target_kl * 0.5:
    beta *= 0.9  # Relax constraint
```

## Monitoring & Adjustment

### Key Metrics to Track

1. **Mean reward**: Should increase steadily
2. **KL divergence**: Should stay <0.1
3. **Advantage variance**: Should be 0.5-1.5
4. **Pass@1**: Should improve over baseline
5. **Capability retention**: Should stay >95%

### When to Adjust

**If mean reward plateaus**:
- Increase epsilon (allow larger updates)
- Increase learning_rate (faster convergence)
- Add harder prompts (ceiling effect)

**If KL divergence spikes**:
- Increase beta (stronger constraint)
- Decrease learning_rate (smaller steps)
- Reduce epsilon (smaller policy changes)

**If advantage variance too high**:
- Increase group_size (better normalization)
- Improve verifier (reduce noise)
- Filter outlier prompts

**If capability regression**:
- Increase beta significantly
- Use smaller learning_rate
- Mix in general data (prevent specialization)

## Quick Reference Table

| Parameter | Default | Range | Main Effect |
|-----------|---------|-------|-------------|
| epsilon | 10.0 | 5.0-15.0 | Policy update magnitude |
| beta | 0.001 | 0.0005-0.005 | KL constraint strength |
| group_size | 16 | 4-32 | Advantage variance |
| temperature | 1.0 | 0.7-1.5 | Response diversity |
| learning_rate | 3e-6 | 1e-6 to 1e-5 | Convergence speed |
| max_output_length | 2048 | 256-32768 | Response length |

## References

1. DeepSeek-R1 Technical Report
2. PPO Hyperparameter Tuning Guide
3. RLHF Best Practices
