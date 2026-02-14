# GRPO Algorithm Details

Complete implementation guide for Group Relative Policy Optimization training loop.

## Training Loop Implementation

### Core GRPO Update Step

```python
def grpo_update(
    model,
    prompts: list,
    group_size: int,
    epsilon: float,
    beta: float
):
    """GRPO training step with group-based advantage."""

    # 1. Generate group of responses per prompt
    for prompt in prompts:
        responses = []
        for _ in range(group_size):
            response = model.generate(prompt, temperature=1.0)
            responses.append(response)

        # 2. Verify responses
        rewards = [verifier(prompt, r) for r in responses]

        # 3. Calculate group-based advantage
        mean_reward = sum(rewards) / len(rewards)
        std_reward = std(rewards)
        advantages = [(r - mean_reward) / (std_reward + 1e-8) for r in rewards]

        # 4. PPO-style update with GRPO advantages
        for response, advantage in zip(responses, advantages):
            # Calculate policy ratio
            old_logprob = model.log_prob(prompt, response)
            new_logprob = model.log_prob(prompt, response)
            ratio = exp(new_logprob - old_logprob)

            # Clipped surrogate objective
            clipped_ratio = clip(ratio, 1 - epsilon, 1 + epsilon)
            loss = -min(ratio * advantage, clipped_ratio * advantage)

            # KL penalty
            kl = kl_divergence(model, base_model, prompt)
            loss += beta * kl

            # Backward pass
            loss.backward()

        # 5. Update model weights
        optimizer.step()
        optimizer.zero_grad()
```

### Advantage Calculation Details

**Formula**:
```
advantage_i = (reward_i - μ_G) / (σ_G + ε)

Where:
- μ_G = mean(rewards in group G)
- σ_G = std(rewards in group G)
- ε = 1e-8 (numerical stability)
```

**Properties**:
- Zero mean per group (normalized)
- Unit variance per group (standardized)
- No critic model needed (group provides baseline)
- Reduces variance compared to raw rewards

**Example**:
```
Group rewards: [0.0, 1.0, 1.0, 0.0]
mean = 0.5, std = 0.5

Advantages:
- reward=0.0 → advantage = (0.0 - 0.5) / 0.5 = -1.0
- reward=1.0 → advantage = (1.0 - 0.5) / 0.5 = +1.0
```

## Hyperparameter Tuning

### epsilon (Clipping Range)

**Purpose**: Controls how much policy can change per update

| Value | Effect | Use Case |
|-------|--------|----------|
| 0.2 | Small changes (PPO default) | General RL tasks |
| 1.0 | Moderate changes | Moderate updates |
| **10.0** | Large changes (GRPO default) | Verifiable tasks with clear signal |

**Why GRPO uses 10.0**:
- Verifiable rewards provide strong signal (less noise than human preferences)
- Group normalization provides stability (less risk of collapse)
- Faster convergence on objective tasks

### beta (KL Coefficient)

**Purpose**: Prevents drift from base model

| Value | Effect | Use Case |
|-------|--------|----------|
| 0.01 | Strong constraint | Preserve base model capabilities |
| **0.001** | Moderate constraint (GRPO default) | Balance improvement vs drift |
| 0.0001 | Weak constraint | Maximize task performance |

**Monitoring**: Track KL divergence, keep <0.1

### group_size

**Purpose**: Number of responses per prompt for advantage calculation

| Value | Variance | Compute Cost | Quality |
|-------|----------|--------------|---------|
| 4 | High | Low | Noisy signal |
| 8 | Moderate | Moderate | Acceptable |
| **16** | Low (GRPO default) | High | Stable training |
| 32 | Very low | Very high | Diminishing returns |

**Trade-off**: Larger groups reduce variance but increase compute (linear scaling)

## Metric Calculation

### Mean Reward

```python
def calculate_mean_reward(rewards: list) -> float:
    """Average reward across all responses."""
    return sum(rewards) / len(rewards)
```

**Target**: Should increase over training iterations

### Advantage Variance

```python
def calculate_advantage_variance(advantages: list) -> float:
    """Variance of normalized advantages."""
    mean = sum(advantages) / len(advantages)
    variance = sum((a - mean) ** 2 for a in advantages) / len(advantages)
    return variance
```

**Target**: 0.5-1.5 (sufficient diversity, not too noisy)

### KL Divergence

```python
def calculate_kl_divergence(model, base_model, prompt: str) -> float:
    """KL divergence between current and base model."""
    logprobs_new = model.log_prob(prompt)
    logprobs_base = base_model.log_prob(prompt)
    kl = sum(exp(logprobs_base) * (logprobs_base - logprobs_new))
    return kl
```

**Target**: <0.1 (not drifting too far)

### Pass@K

```python
def calculate_pass_at_k(prompts: list, model, k: int) -> float:
    """Percentage of prompts with ≥1 correct response in top-k."""
    passed = 0
    for prompt in prompts:
        responses = [model.generate(prompt) for _ in range(k)]
        scores = [verifier(prompt, r) for r in responses]
        if any(s >= 0.99 for s in scores):
            passed += 1
    return passed / len(prompts)
```

**Target**: Pass@1 > baseline, Pass@10 > 80%

## Best Practices

### 1. Data Generation
- Use temperature=1.0 for diversity
- Generate group_size responses per prompt
- Ensure diverse prompts (avoid repetition)

### 2. Verification
- Fast verifiers (<1s per response)
- Deterministic when possible
- Handle edge cases gracefully

### 3. Training
- Monitor KL divergence (stop if >0.1)
- Track mean reward (should increase)
- Checkpoint frequently (recovery from drift)

### 4. Evaluation
- Test on held-out prompts
- Measure Pass@1 and Pass@10
- Check capability retention on benchmarks

## Common Issues

### Low Variance (std <0.3)

**Causes**:
- All responses similar (low temperature)
- Verifier too strict (all fail or all pass)
- Prompts too easy (ceiling effect)

**Solutions**:
- Increase temperature to 1.2-1.5
- Add diverse test cases
- Use harder prompts

### High Variance (std >2.0)

**Causes**:
- Verifier noisy (inconsistent scoring)
- Group size too small
- Prompts too diverse

**Solutions**:
- Improve verifier logic
- Increase group_size to 32
- Filter outlier prompts

### Reward Hacking

**Symptoms**:
- High verification scores
- Low actual quality (manual inspection)

**Solutions**:
- Add diverse test cases
- Multi-faceted verification (multiple checks)
- Manual spot-checking (quality control)

## References

1. DeepSeek-R1 paper: https://arxiv.org/abs/2501.12948
2. PPO algorithm: https://arxiv.org/abs/1707.06347
3. RLHF survey: https://arxiv.org/abs/2203.02155
