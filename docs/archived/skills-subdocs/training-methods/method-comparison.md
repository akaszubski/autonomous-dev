# Training Method Comparison

Side-by-side comparison of 8 stable training methods with strengths, weaknesses, and best-fit use cases.

---

## Comparison Matrix

### Complexity vs Capability

```
High Capability
    │
    │  RLVR ●
    │      │
    │      │  GRPO ●
    │          │
    │      DPO ●  CPO ●
    │          │
    │      ORPO ●
    │          │
    │  SFT/LoRA ●
    │
    │  Abliteration ●  Activation Steering ●
    │
Low │────────────────────────────────────────→ High Complexity
```

---

## Feature Comparison

| Feature | SFT/LoRA | DPO | ORPO | GRPO | CPO | RLVR | Abliteration | Steering |
|---------|----------|-----|------|------|-----|------|--------------|----------|
| **Requires reference model** | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Requires reward model** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Requires verification logic** | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Training time** | Fast | Medium | Medium | Slow | Medium | Slow | Fast | N/A |
| **Inference overhead** | None | None | None | None | None | None | None | Low |
| **Data requirements** | Low | High | High | Medium | High | Medium | None | Low |
| **Reversible** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Composable** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## Strengths & Weaknesses

### SFT/LoRA

**Strengths**:
- Simple, well-understood methodology
- Fast training (<1 hour on consumer GPU)
- Low data requirements (100-1000 examples)
- Works for any task type
- Widely supported (all backends)
- Low memory (4-bit quantization + LoRA)

**Weaknesses**:
- No preference modeling
- Can overfit to training examples
- May degrade base model capabilities
- No control over style/tone preferences
- Catastrophic forgetting possible

**Best For**: Knowledge injection, domain adaptation, teaching new tasks

---

### DPO (Direct Preference Optimization)

**Strengths**:
- No reward model needed (simpler than RLHF)
- Direct preference optimization
- Stable training (no RL instability)
- Strong alignment results
- Well-studied (many papers, implementations)

**Weaknesses**:
- Requires reference model (2x memory)
- Needs high-quality preference pairs (gap ≥0.15)
- Can drift from base model (monitor KL ≤0.1)
- Preference data labeling expensive
- May sacrifice capability for alignment

**Best For**: Behavior change, style alignment, human preference alignment

---

### ORPO (Odds Ratio Preference Optimization)

**Strengths**:
- No reference model needed (lower memory)
- Simpler than DPO (fewer hyperparameters)
- Faster training (no reference forward pass)
- Lower compute cost
- Still uses preference data

**Weaknesses**:
- Less stable than DPO (higher variance)
- May have higher distribution shift
- Experimental in some backends
- Fewer papers/implementations (newer method)
- May need more data for same quality

**Best For**: Budget-constrained preference alignment, simple behavior change

---

### GRPO (Group Relative Policy Optimization)

**Strengths**:
- No critic model needed (simpler than PPO)
- Group-based advantage (stable)
- Objective correctness verification
- Used in DeepSeek-R1 (proven at scale)
- Strong for verifiable tasks

**Weaknesses**:
- Only works for verifiable tasks (>80% verifiability)
- Requires verification logic implementation
- Higher compute (generate multiple responses per prompt)
- Group size hyperparameter tuning needed
- Not suitable for subjective tasks

**Best For**: Math, code generation, factual QA, format compliance

---

### CPO (Conservative Policy Optimization)

**Strengths**:
- Lower distribution shift than DPO
- Preserves base capabilities better
- More conservative alignment (safer)
- Good for safety-critical applications
- Reduces catastrophic forgetting

**Weaknesses**:
- Slower convergence than DPO
- May need more data for same alignment
- Limited backend support (PyTorch, Cloud)
- Fewer papers/implementations
- Hyperparameter tuning more sensitive

**Best For**: Safety-critical apps, minimal capability loss, conservative alignment

---

### RLVR (Reinforcement Learning with Verified Rewards)

**Strengths**:
- Verified rewards at each step
- Better for complex multi-step reasoning
- Handles chain-of-thought tasks
- Process verification (not just outcome)
- Strong theoretical guarantees

**Weaknesses**:
- Requires step-by-step verification logic
- Higher compute cost (verify each step)
- MLX backend only (currently)
- More complex implementation
- Limited tooling/support

**Best For**: Complex reasoning, research tasks, multi-step problem solving

---

### Abliteration

**Strengths**:
- Directly removes refusal behaviors
- No training data needed
- Fast (inference-time or single epoch)
- Simple implementation
- Reversible (keep original model)

**Weaknesses**:
- Safety concerns (removes guardrails)
- May remove beneficial constraints
- Can affect model quality unpredictably
- Limited research/validation
- Ethical considerations

**Best For**: Research on constraints, uncensored models (use responsibly)

---

### Activation Steering

**Strengths**:
- Inference-time control (no retraining)
- Reversible (remove vector to restore)
- Composable (combine multiple vectors)
- Fast experimentation (A/B testing)
- Low cost (no training)

**Weaknesses**:
- Limited control precision
- May affect unrelated outputs (side effects)
- Requires vector extraction (data collection)
- Not as powerful as training
- Can be brittle (model-specific)

**Best For**: Runtime control, A/B testing, composable behaviors, quick experiments

---

## Use Case Matrix

| Use Case | Primary Method | Alternative | Notes |
|----------|----------------|-------------|-------|
| **Domain adaptation** | SFT/LoRA | - | Simple knowledge injection |
| **Style alignment** | DPO | ORPO | Prefer DPO if memory allows |
| **Math tutoring** | GRPO | SFT + GRPO | Start with SFT for base |
| **Code generation** | GRPO | SFT + GRPO | Verifiable correctness |
| **Research assistant** | RLVR | GRPO | Multi-step reasoning |
| **Safety-critical** | CPO | DPO | Minimize capability loss |
| **Uncensored model** | Abliteration | - | Use responsibly |
| **A/B testing** | Activation Steering | - | Quick experiments |

---

## Training Time Estimates

| Method | Training Time (1B model, consumer GPU) | Notes |
|--------|----------------------------------------|-------|
| **SFT/LoRA** | 30-60 min | Fast, single pass over data |
| **DPO** | 2-4 hours | Reference model forward pass overhead |
| **ORPO** | 1-2 hours | Faster than DPO (no reference) |
| **GRPO** | 4-8 hours | Multiple response generation |
| **CPO** | 3-5 hours | Similar to DPO |
| **RLVR** | 6-12 hours | Step-by-step verification |
| **Abliteration** | 5-10 min | Single epoch or inference-time |
| **Activation Steering** | 10-30 min | Vector extraction only |

**Note**: Times assume 1000-5000 training examples on RTX 3090 or M2 Ultra.

---

## Data Requirements

| Method | Minimum Examples | Recommended | Quality Priority |
|--------|------------------|-------------|-----------------|
| **SFT/LoRA** | 100 | 1000+ | Diversity, correctness |
| **DPO** | 1000 | 5000+ | Preference gap ≥0.15 |
| **ORPO** | 1000 | 5000+ | Preference gap ≥0.15 |
| **GRPO** | 500 | 2000+ | Verifiability >80% |
| **CPO** | 1000 | 5000+ | Preference gap ≥0.15 |
| **RLVR** | 500 | 2000+ | Step verification |
| **Abliteration** | 0 | 0 | None (no data needed) |
| **Activation Steering** | 50 | 200+ | Targeted examples |

---

## Memory Requirements

| Method | Reference Model | Extra Memory | Total (1B model, 4-bit) |
|--------|-----------------|--------------|-------------------------|
| **SFT/LoRA** | ❌ No | LoRA adapters | ~2 GB |
| **DPO** | ✅ Yes | Reference + gradients | ~4 GB |
| **ORPO** | ❌ No | Gradients only | ~2.5 GB |
| **GRPO** | ❌ No | Multiple responses | ~3 GB |
| **CPO** | ✅ Yes | Reference + gradients | ~4 GB |
| **RLVR** | ❌ No | Verification overhead | ~3 GB |
| **Abliteration** | ❌ No | Original model | ~2 GB |
| **Activation Steering** | ❌ No | Steering vectors | ~2 GB |

**Note**: Memory estimates for 1B parameter model with 4-bit quantization on consumer hardware.

---

## Quality Metrics

| Method | Key Metrics | Target Thresholds |
|--------|-------------|-------------------|
| **SFT/LoRA** | Loss, perplexity, eval accuracy | Loss decreasing, eval accuracy >baseline |
| **DPO** | Preference gap, KL divergence | Gap ≥0.15, KL ≤0.1 |
| **ORPO** | Preference gap, KL divergence | Gap ≥0.15, KL ≤0.15 |
| **GRPO** | Mean reward, advantage variance | Reward increasing, variance 0.5-1.5 |
| **CPO** | KL divergence, capability retention | KL ≤0.05, retention ≥95% |
| **RLVR** | Step correctness, final correctness | Step >80%, final >90% |
| **Abliteration** | Refusal rate, quality retention | Refusals <5%, quality >90% |
| **Activation Steering** | Steering strength, side effects | Strength adequate, side effects <10% |

---

## Selection Flowchart

```
START: What is your goal?
│
├─ Inject new knowledge/skills
│   └─ SFT/LoRA (simple, fast)
│
├─ Align to human preferences
│   ├─ High budget (memory available)
│   │   └─ DPO (stable, proven)
│   └─ Low budget (memory constrained)
│       └─ ORPO (simpler, lower memory)
│
├─ Improve verifiable task performance
│   ├─ Simple verification (math, code)
│   │   └─ GRPO (no critic needed)
│   └─ Complex multi-step reasoning
│       └─ RLVR (step-by-step verification)
│
├─ Minimize capability loss
│   └─ CPO (conservative alignment)
│
├─ Remove safety constraints
│   └─ Abliteration (use responsibly)
│
└─ Need runtime control
    └─ Activation Steering (reversible, composable)
```

---

## Combined Training Strategies

### Strategy 1: Base + Alignment

```
1. SFT/LoRA (domain knowledge)
2. DPO (align preferences)
```

**Time**: 2-4 hours total
**Memory**: 4 GB peak (during DPO)
**Use Case**: Domain-specific assistant with preferred style

---

### Strategy 2: Verifiable Reasoning

```
1. SFT/LoRA (instruction following)
2. GRPO (correctness)
3. Anti-hallucination (confidence calibration)
```

**Time**: 5-9 hours total
**Memory**: 3 GB peak
**Use Case**: Math tutor or code assistant

---

### Strategy 3: Research Assistant

```
1. SFT/LoRA (base capabilities)
2. RLVR (multi-step reasoning)
3. Calibration (uncertainty)
4. Anti-hallucination (reduce false confidence)
```

**Time**: 10-15 hours total
**Memory**: 3 GB peak
**Use Case**: Research assistant with verified reasoning

---

### Strategy 4: Customizable Assistant

```
1. SFT/LoRA (base)
2. DPO (default behavior)
3. Activation Steering (runtime personas)
```

**Time**: 3-5 hours total
**Memory**: 4 GB peak
**Use Case**: Multi-persona assistant (professional, casual, technical)

---

**See**: `training-order.md` for detailed sequential training rationale.
