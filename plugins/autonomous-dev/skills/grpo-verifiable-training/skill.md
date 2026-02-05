---
name: GRPO Verifiable Training
version: 1.0.0
type: knowledge
description: Group Relative Policy Optimization for math/code verification training. Uses group-based advantage calculation without critic model, ideal for verifiable tasks with objective correctness.
keywords: [grpo, group relative policy, verifiable training, math verification, code verification, deepseek-r1, advantage calculation, critic-free rl]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# GRPO Verifiable Training Skill

Complete guide to Group Relative Policy Optimization (GRPO) for training models on verifiable tasks like math problem solving and code generation.

## When This Skill Activates

- Implementing GRPO training workflows
- Training on verifiable tasks (math, code)
- Designing critic-free RL approaches
- Optimizing advantage calculation
- Keywords: "grpo", "group relative policy", "verifiable training", "math verification", "code verification"

---

## Core Principle

**Group-based advantage calculation eliminates need for critic model.**

- GRPO compares responses within groups (no baseline model needed)
- Advantage = (reward - group_mean) / group_std
- Ideal for tasks with objective correctness verification
- Used in DeepSeek-R1 for reasoning and code generation

---

## GRPO Formula

### Advantage Calculation

```
For each response i in group G:

advantage_i = (reward_i - mean(rewards_G)) / std(rewards_G)

Where:
- reward_i: Binary or continuous score (0.0-1.0)
- mean(rewards_G): Average reward across all responses in group
- std(rewards_G): Standard deviation of rewards in group
```

### vs Traditional RLHF/PPO

| Method | Critic Model | Advantage Calculation | Best For |
|--------|--------------|----------------------|----------|
| **GRPO** | ❌ No | Group-relative | Verifiable tasks |
| **PPO** | ✅ Yes | Value function baseline | General tasks |
| **RLHF** | ✅ Yes | Reward model | Human preferences |

---

## When to Use GRPO

| Task Type | Verifiability | GRPO Suitability | Example |
|-----------|---------------|------------------|---------|
| **Math problems** | 95%+ | ✅ Ideal | Symbolic solver verification |
| **Code generation** | 95%+ | ✅ Ideal | Execution in sandbox |
| **Factual QA** | 85%+ | ✅ Good | Knowledge base lookup |
| **Format compliance** | 95%+ | ✅ Ideal | Regex/parser validation |
| **Reasoning steps** | 70%+ | ⚠️ Moderate | Step-by-step verification |
| **Creative writing** | <50% | ❌ Poor | Subjective quality |
| **Open-ended tasks** | <50% | ❌ Poor | No objective correctness |

**Rule of Thumb**: Use GRPO when >80% of responses can be objectively verified as correct/incorrect.

---

## DeepSeek-R1 Hyperparameters

Production-validated hyperparameters from DeepSeek-R1 (reasoning + code model):

| Parameter | Value | Purpose |
|-----------|-------|---------|
| **epsilon** | 10.0 | PPO clipping range (large for stable updates) |
| **beta** | 0.001 | KL divergence coefficient (prevents drift) |
| **group_size** | 16 | Responses per prompt for advantage calculation |
| **temperature** | 1.0 | Sampling temperature |
| **learning_rate** | 3e-6 | Small for stable fine-tuning |
| **max_output_length** | 32,768 tokens | Long-form reasoning support |
| **num_epochs** | 3-5 | Training epochs |
| **batch_size** | 32-64 | Depends on GPU memory |

**Critical Parameters**:
- **epsilon=10**: Much larger than PPO's typical 0.2 (GRPO needs wider clipping)
- **beta=0.001**: Small KL penalty (group normalization provides stability)
- **group_size=16**: Balance between variance reduction and compute cost

**See**: `docs/hyperparameters.md` for detailed parameter tuning guidance.

---

## Data Format

### JSONL Format (Training Data)

```jsonl
{"prompt": "Solve for x: 2x + 5 = 15", "responses": [{"text": "2x + 5 = 15\n2x = 10\nx = 5", "score": 1.0, "correct": true}, {"text": "2x + 5 = 15\nx = 10", "score": 0.0, "correct": false}, {"text": "2x + 5 = 15\n2x = 10\nx = 5 ✓", "score": 1.0, "correct": true}]}
{"prompt": "Write a function to reverse a string in Python", "responses": [{"text": "def reverse(s):\n    return s[::-1]", "score": 1.0, "correct": true}, {"text": "def reverse(s):\n    return reversed(s)", "score": 0.0, "correct": false}, {"text": "def reverse(s):\n    return ''.join(reversed(s))", "score": 1.0, "correct": true}]}
```

### Field Descriptions

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `prompt` | string | Input question/task | ✅ Yes |
| `responses` | list | Group of responses for advantage calculation | ✅ Yes |
| `responses[].text` | string | Model-generated response | ✅ Yes |
| `responses[].score` | float | Verification score (0.0-1.0) | ✅ Yes |
| `responses[].correct` | bool | Binary correctness flag | ⚠️ Optional |
| `responses[].reasoning` | string | Chain-of-thought steps | ⚠️ Optional |
| `responses[].execution_output` | string | Code execution result | ⚠️ Optional |

**See**: `docs/data-format.md` for data generation workflows and batching strategies.

---

## Verifier Types

### 1. Symbolic Solver (Math)

**Use Case**: Algebra, calculus, symbolic math

```python
from sympy import sympify, solve

def verify_math(problem: str, answer: str) -> float:
    """Verify math answer using symbolic solver."""
    try:
        expected = solve(problem)
        provided = sympify(answer)
        return 1.0 if provided in expected else 0.0
    except:
        return 0.0
```

**Verifiability**: 95%+ (exact symbolic comparison)

### 2. Execution Sandbox (Code)

**Use Case**: Python, JavaScript, SQL code generation

```python
import subprocess
import tempfile

def verify_code(code: str, test_cases: list) -> float:
    """Verify code by executing test cases in sandbox."""
    passed = 0
    for test_input, expected_output in test_cases:
        try:
            result = subprocess.run(
                ["python", "-c", code],
                input=test_input,
                capture_output=True,
                timeout=5
            )
            if result.stdout.decode().strip() == expected_output:
                passed += 1
        except:
            continue
    return passed / len(test_cases)
```

**Verifiability**: 90%+ (depends on test coverage)

### 3. Knowledge Base Lookup (Factual QA)

**Use Case**: Factual questions with known answers

```python
def verify_factual(question: str, answer: str, kb: dict) -> float:
    """Verify factual answer against knowledge base."""
    correct_answer = kb.get(question)
    if not correct_answer:
        return 0.5  # Unknown question
    return 1.0 if answer.lower() == correct_answer.lower() else 0.0
```

**Verifiability**: 85%+ (depends on KB coverage)

### 4. Regex/Parser Validation (Format Compliance)

**Use Case**: JSON, XML, structured output

```python
import json
import re

def verify_format(output: str, format_type: str) -> float:
    """Verify output matches required format."""
    if format_type == "json":
        try:
            json.loads(output)
            return 1.0
        except:
            return 0.0
    elif format_type == "email":
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return 1.0 if re.match(pattern, output) else 0.0
```

**Verifiability**: 95%+ (deterministic parsing)

**See**: `docs/verifier-types.md` for verifier implementations and best practices.

---

## GRPO Training Workflow

### 1. Data Generation

```bash
# Generate multiple responses per prompt (group_size=16)
python generate_responses.py \
    --prompts data/math_problems.jsonl \
    --output data/grpo_training.jsonl \
    --group_size 16 \
    --temperature 1.0
```

### 2. Verification

```bash
# Score responses with verifier
python verify_responses.py \
    --input data/grpo_training.jsonl \
    --output data/grpo_verified.jsonl \
    --verifier symbolic_math
```

### 3. GRPO Training

```bash
# Train with GRPO
python train_grpo.py \
    --model meta-llama/Llama-3.2-1B-Instruct \
    --data data/grpo_verified.jsonl \
    --epsilon 10.0 \
    --beta 0.001 \
    --group_size 16 \
    --output models/grpo_checkpoint
```

**See**: `docs/algorithm-details.md` for complete training loop implementation.

---

## Quality Metrics

### During Training

| Metric | Target | Purpose |
|--------|--------|---------|
| **Mean reward** | Increasing | Model improving on task |
| **Advantage variance** | 0.5-1.5 | Sufficient signal diversity |
| **KL divergence** | <0.1 | Not drifting from base model |
| **Verification rate** | >80% | Tasks are verifiable |

### Post-Training

| Metric | Target | Purpose |
|--------|--------|---------|
| **Pass@1** | >baseline | Correctness on first attempt |
| **Pass@10** | >80% | Correctness in top 10 samples |
| **Capability retention** | >95% | No regression on benchmarks |

**See**: `docs/algorithm-details.md` for metric calculation and monitoring strategies.

---

## Common Pitfalls

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Low variance** | Advantage std <0.3 | Increase temperature, diversify prompts |
| **High variance** | Advantage std >2.0 | Reduce temperature, improve verifier |
| **Reward hacking** | High score, low quality | Add diverse test cases, multi-faceted verification |
| **Model drift** | KL >0.1 | Increase beta, reduce learning rate |
| **Poor verifiability** | Verification rate <80% | Filter tasks, improve verifier logic |

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): High-level concepts and quick reference (<300 lines)
- **Detailed docs**: `docs/*.md` files with implementation details (loaded on-demand)

**Available Documentation**:
- `docs/algorithm-details.md` - Complete GRPO algorithm implementation
- `docs/hyperparameters.md` - Parameter tuning guide
- `docs/data-format.md` - Data generation and batching workflows
- `docs/verifier-types.md` - Verifier implementations and best practices

---

## Cross-References

**Related Skills**:
- **realign-rlvr-workflow** - Alternative verifiable training approach
- **preference-data-quality** - Quality metrics and thresholds
- **scientific-validation** - Experimental validation methodology

**Related Libraries**:
- `training_metrics.py` - Metric calculation functions

**Related Tools**:
- HuggingFace TRL library - RL fine-tuning implementation
- DeepSpeed - Distributed training
- Weights & Biases - Training monitoring

---

## Key Takeaways

1. **Group-based advantage** - No critic model needed, simpler than PPO
2. **High verifiability** - Best for tasks with >80% objective verification
3. **DeepSeek-R1 hyperparameters** - epsilon=10, beta=0.001, group_size=16
4. **Verifier types** - Symbolic solver (math), execution sandbox (code), KB lookup (factual), parser (format)
5. **Quality gates** - Mean reward increasing, KL <0.1, verification rate >80%
6. **Data format** - JSONL with prompt + group of responses + verification scores
7. **Common pitfalls** - Low variance, reward hacking, model drift
8. **Progressive disclosure** - See docs/*.md for implementation details
9. **Training workflow** - Generate → Verify → Train (iterative)
10. **Monitoring critical** - Track advantage variance, KL divergence, verification rate
