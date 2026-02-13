---
name: training-methods
version: 1.0.0
type: knowledge
description: 8 stable training methods with data formats, use cases, and backend support. Comprehensive guide to SFT/LoRA, DPO, ORPO, GRPO, CPO, RLVR, Abliteration, and Activation Steering for model training and alignment.
keywords: [sft, lora, dpo, orpo, grpo, cpo, rlvr, abliteration, steering, training, alignment, fine-tuning, preference, optimization]
auto_activate: false
allowed-tools: [Read]
---

# Training Methods Skill

Complete reference guide to 8 stable training methods for model fine-tuning and alignment. Use this skill to choose the right training method for your use case, understand data format requirements, and verify backend support.

## When This Skill Activates

- Choosing training methods
- Understanding data format requirements
- Comparing training approaches
- Planning training workflows
- Verifying backend support (MLX, PyTorch, Cloud)
- Keywords: "training", "alignment", "fine-tuning", "sft", "dpo", "grpo", "rlvr", "preference", "optimization"

---

## 8 Stable Training Methods

### Method Comparison Table

| Method | Purpose | Data Format | Use Case | Backend Support |
|--------|---------|-------------|----------|-----------------|
| **SFT/LoRA** | Base capabilities | instruction + output | Knowledge injection | MLX, PyTorch, Cloud |
| **DPO** | Preference alignment | chosen + rejected | Behavior change | MLX, PyTorch, Cloud |
| **ORPO** | Preference (simple) | chosen + rejected | No reference model | MLX, PyTorch, Cloud |
| **GRPO** | Verifiable rewards | prompt + scored responses | Math/code verification | MLX, PyTorch, Cloud |
| **CPO** | Conservative preference | chosen + rejected | Reduce distribution shift | PyTorch, Cloud |
| **RLVR** | Verified rewards | problem + solution + verify | Complex reasoning | MLX only |
| **Abliteration** | Remove constraints | harmful + harmless | Uncensoring | PyTorch |
| **Activation Steering** | Runtime control | inference-time | Reversible, composable | PyTorch |

**Legend**: ✅ Full support | ⚠️ Experimental | ❌ Not available

---

## Data Formats

### SFT/LoRA (Supervised Fine-Tuning)

```python
# JSONL format
{"instruction": "Explain quantum computing", "output": "Quantum computing uses quantum mechanics principles..."}
{"instruction": "Write a Python function to sort a list", "output": "def sort_list(lst):\n    return sorted(lst)"}
```

**Fields**:
- `instruction` (string): Input prompt/question
- `output` (string): Expected model response

**Use Case**: Inject new knowledge, teach new tasks, adapt base model to domain

---

### DPO/ORPO/CPO (Preference-Based)

```python
# JSONL format
{"prompt": "Explain AI ethics", "chosen": "AI ethics considers fairness, accountability...", "rejected": "AI ethics is boring and irrelevant"}
{"prompt": "Write a function to reverse a string", "chosen": "def reverse(s):\n    return s[::-1]", "rejected": "def reverse(s):\n    s.reverse()"}
```

**Fields**:
- `prompt` (string): Input question/task
- `chosen` (string): Preferred response (high quality)
- `rejected` (string): Dispreferred response (low quality)

**Use Case**:
- **DPO**: Align model to preferences without reward model
- **ORPO**: Simplified DPO without reference model
- **CPO**: Conservative DPO to reduce distribution shift

---

### GRPO (Group Relative Policy Optimization)

```python
# JSONL format
{"prompt": "Solve: 2x + 5 = 15", "responses": [
    {"text": "2x + 5 = 15\n2x = 10\nx = 5", "score": 1.0},
    {"text": "2x + 5 = 15\nx = 10", "score": 0.0},
    {"text": "2x = 10\nx = 5 ✓", "score": 1.0}
]}
```

**Fields**:
- `prompt` (string): Input question/task
- `responses` (list): Group of responses for advantage calculation
- `responses[].text` (string): Model-generated response
- `responses[].score` (float): Verification score (0.0-1.0)

**Use Case**: Verifiable tasks with objective correctness (math, code, factual QA)

---

### RLVR (Reinforcement Learning with Verified Rewards)

```python
# JSONL format
{"problem": "Write a function to check if a number is prime",
 "solution": "def is_prime(n):\n    if n < 2: return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0: return False\n    return True",
 "responses": [
     {"text": "def is_prime(n): return n > 1 and all(n % i for i in range(2, n))", "correct": false},
     {"text": "def is_prime(n):\n    if n < 2: return False\n    return all(n % i != 0 for i in range(2, int(n**0.5)+1))", "correct": true}
 ]}
```

**Fields**:
- `problem` (string): Task description
- `solution` (string): Reference solution
- `responses` (list): Model-generated responses
- `responses[].text` (string): Generated response
- `responses[].correct` (bool): Binary correctness flag

**Use Case**: Complex reasoning tasks with multi-step verification

---

## Method Selection Guide

### Decision Tree

```
Is the task verifiable (>80% objective correctness)?
├─ YES: Verifiable tasks
│   ├─ Simple verification (math, code)? → GRPO
│   └─ Complex multi-step reasoning? → RLVR
│
└─ NO: Subjective tasks
    ├─ Need behavior change? → DPO
    ├─ No reference model available? → ORPO
    ├─ Minimize distribution shift? → CPO
    ├─ Inject new knowledge? → SFT/LoRA
    ├─ Remove safety constraints? → Abliteration
    └─ Runtime control needed? → Activation Steering
```

### Method Details

#### 1. SFT/LoRA - Knowledge Injection

**When to Use**:
- Teaching new tasks
- Domain adaptation
- Knowledge injection
- Base capability improvement

**Strengths**:
- Simple, well-understood
- Works for any task type
- Widely supported (all backends)

**Weaknesses**:
- No preference modeling
- Can overfit to examples
- May degrade base capabilities

**See**: `docs/sft-lora.md` for implementation details

---

#### 2. DPO - Preference Alignment

**When to Use**:
- Align to human preferences
- Behavior change (style, tone, format)
- Preference over factual correctness

**Strengths**:
- No reward model needed (simpler than RLHF)
- Direct preference optimization
- Stable training

**Weaknesses**:
- Requires reference model
- Needs high-quality preference pairs (gap ≥0.15)
- Can drift from base model (monitor KL)

**See**: `docs/dpo.md`, `realign-dpo-workflow` skill for complete workflow

---

#### 3. ORPO - Simplified Preference

**When to Use**:
- Same as DPO but no reference model available
- Lower compute budget
- Simple preference alignment

**Strengths**:
- No reference model needed (simpler than DPO)
- Lower memory requirements
- Faster training

**Weaknesses**:
- Less stable than DPO
- May have higher distribution shift
- Experimental in some backends

**See**: `docs/orpo.md` for implementation details

---

#### 4. GRPO - Verifiable Rewards

**When to Use**:
- Math problem solving
- Code generation
- Factual QA with verifiable answers
- Format compliance tasks

**Strengths**:
- No critic model needed
- Group-based advantage (stable)
- Objective correctness verification

**Weaknesses**:
- Only works for verifiable tasks (>80% verifiability)
- Requires verification logic
- Higher compute (generate multiple responses)

**See**: `grpo-verifiable-training` skill for complete guide

---

#### 5. CPO - Conservative Preference

**When to Use**:
- DPO causing too much distribution shift
- Need to preserve base model capabilities
- Safety-critical applications

**Strengths**:
- Lower distribution shift than DPO
- Preserves base capabilities better
- More conservative alignment

**Weaknesses**:
- Slower convergence
- May need more data
- Limited backend support (PyTorch, Cloud)

**See**: `docs/cpo.md` for implementation details

---

#### 6. RLVR - Verified Rewards

**When to Use**:
- Complex multi-step reasoning
- Tasks requiring process verification
- Chain-of-thought training

**Strengths**:
- Verified rewards at each step
- Better for complex reasoning
- Handles multi-step tasks

**Weaknesses**:
- Requires step-by-step verification
- Higher compute cost
- MLX backend only (currently)

**See**: `realign-rlvr-workflow` skill for complete workflow

---

#### 7. Abliteration - Constraint Removal

**When to Use**:
- Remove safety guardrails
- Research on model constraints
- Uncensored model creation

**Strengths**:
- Directly removes refusal behaviors
- No training data needed
- Fast (inference-time or single epoch)

**Weaknesses**:
- Safety concerns (use responsibly)
- May remove beneficial constraints
- Can affect model quality

**See**: `docs/abliteration.md` for implementation details

---

#### 8. Activation Steering - Runtime Control

**When to Use**:
- Need reversible control
- Multiple steering vectors (composable)
- A/B testing different behaviors

**Strengths**:
- Inference-time control (no retraining)
- Reversible (remove vector to restore)
- Composable (combine multiple vectors)

**Weaknesses**:
- Limited control precision
- May affect unrelated outputs
- Requires vector extraction

**See**: `docs/activation-steering.md` for implementation details

---

## Recommended Training Order

### Sequential Training Pipeline

```
1. SFT (base) → Instruction following, domain adaptation
2. RLVR/GRPO (verification) → Reasoning improvement (if applicable)
3. DPO (alignment) → Behavior change, preference alignment (LAST — most fragile)
```

**Rationale**:
- **SFT first**: Establish base capabilities (include calibration + anti-hallucination data in SFT mix)
- **RLVR/GRPO second**: Improve reasoning while weights are still stable
- **DPO last**: Most fragile phase — preference optimization can degrade if followed by further training

**Scale-dependent parameters**:
- LoRA (<100K): SFT 3 epochs, DPO 5-20K pairs, RLVR 10K
- Full FT (1M+): SFT 1 epoch, DPO up to 240K pairs, RLVR 25K

**See**: `docs/training-order.md` for detailed rationale and examples

---

## Backend Support Matrix

| Method | MLX | PyTorch | Cloud (OpenAI/Anthropic) |
|--------|-----|---------|--------------------------|
| **LoRA** | ✅ Full | ✅ Full | ✅ Full |
| **DPO** | ✅ Full | ✅ Full | ✅ Full |
| **ORPO** | ⚠️ Experimental | ✅ Full | ✅ Full |
| **GRPO** | ✅ Full | ✅ Full | ✅ Full |
| **CPO** | ❌ Not available | ✅ Full | ✅ Full |
| **RLVR** | ✅ Full | ❌ Not available | ❌ Not available |
| **Abliteration** | ❌ Not available | ✅ Full | ❌ Not available |
| **Activation Steering** | ❌ Not available | ✅ Full | ❌ Not available |

**Backend Notes**:
- **MLX**: Apple Silicon optimized, best for M1/M2/M3 Macs
- **PyTorch**: Most comprehensive support, GPU-accelerated
- **Cloud**: Managed training (OpenAI, Anthropic), easiest setup

**See**: `docs/backend-support.md` for detailed backend comparison

---

## Common Patterns

### Pattern 1: Base Knowledge + Alignment

```
1. SFT (domain knowledge)
2. DPO (align to preferences)
```

**Use Case**: Domain-specific chatbot with preferred style

---

### Pattern 2: Verifiable Reasoning

```
1. SFT (instruction following)
2. GRPO (math/code correctness)
```

**Use Case**: Math tutoring or code generation assistant

---

### Pattern 3: Complex Reasoning

```
1. SFT (base capabilities)
2. RLVR (step-by-step reasoning)
3. Calibration (uncertainty handling)
```

**Use Case**: Research assistant with verified reasoning

---

### Pattern 4: Behavioral Modification

```
1. Base model (pre-trained)
2. DPO (behavior change)
3. Activation Steering (fine-grained control)
```

**Use Case**: Customizable assistant with multiple personas

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): Method comparison and quick reference (<500 lines)
- **Detailed docs**: `docs/*.md` files with implementation details (loaded on-demand)

**Available Documentation**:
- `docs/sft-lora.md` - SFT/LoRA implementation guide
- `docs/dpo.md` - DPO implementation guide
- `docs/orpo.md` - ORPO implementation guide
- `docs/cpo.md` - CPO implementation guide
- `docs/abliteration.md` - Abliteration implementation guide
- `docs/activation-steering.md` - Activation Steering implementation guide
- `docs/training-order.md` - Sequential training pipeline rationale
- `docs/backend-support.md` - Detailed backend comparison
- `docs/method-comparison.md` - Side-by-side method comparison

---

## Cross-References

**Related Skills**:
- **grpo-verifiable-training** - Complete GRPO workflow and hyperparameters
- **realign-dpo-workflow** - 7-stage DPO pipeline with quality gates
- **realign-rlvr-workflow** - RLVR workflow with step-by-step verification
- **preference-data-quality** - Quality metrics and thresholds for preference data
- **anti-hallucination-training** - Reduce model hallucinations post-training

**Related Libraries**:
- `training_metrics.py` - Metric calculation functions
- `data_validation.py` - Data format validation

**Related Tools**:
- **`realign train`** - Production CLI wrapping mlx-lm (all methods, handles format/config/metrics)
- HuggingFace TRL - RL fine-tuning library (DPO, GRPO, PPO)
- MLX-LM - Apple Silicon training (LoRA, DPO, GRPO, RLVR) — use via `realign train`
- Axolotl - Training framework (all methods)
- Unsloth - Efficient training (LoRA, DPO)

### Full Fine-Tuning Hyperparameters

For hardware-specific batch sizes, memory requirements, gradient checkpointing, and learning rate scaling, see **mlx-performance** skill.

**Method-specific guidelines** (hardware-agnostic):
- **SFT**: LR 1e-5, 1 epoch (1M+ data) or 3 epochs (35K data)
- **RLVR**: After SFT, 1 epoch, verifiable rewards
- **DPO**: After RLVR, LR 5e-6 (lower than SFT), 1 epoch — most fragile phase

---

## Key Takeaways

1. **8 methods** - SFT/LoRA, DPO, ORPO, GRPO, CPO, RLVR, Abliteration, Activation Steering
2. **Method selection** - Verifiable (GRPO/RLVR) vs subjective (DPO/ORPO) tasks
3. **Data formats** - Instruction+output (SFT), chosen+rejected (DPO), prompt+responses (GRPO)
4. **Training order** - SFT → RLVR/GRPO → DPO (DPO last — most fragile)
5. **Backend support** - MLX (Apple), PyTorch (GPU), Cloud (managed)
6. **Quality gates** - Preference gap ≥0.15, KL ≤0.1, verifiability >80%
7. **Common patterns** - Base+alignment, verifiable reasoning, complex reasoning, behavioral modification
8. **Progressive disclosure** - See docs/*.md for implementation details
9. **Cross-references** - grpo-verifiable-training, realign-dpo-workflow, realign-rlvr-workflow skills
10. **Tool ecosystem** - TRL, MLX-LM, Axolotl, Unsloth

---

**Use this skill to choose the right training method, understand data requirements, and verify backend support before starting a training workflow.**
