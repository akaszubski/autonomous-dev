# Stage 5: DPO Optimization

Train policy model to optimize preferences while maintaining KL constraint.

---

## Overview

**Purpose**: Run DPO training loop to align policy model with preferences.

**Goal**: Improve preference accuracy while keeping KL divergence ≤0.1.

**Key Principle**: Balance preference optimization with capability preservation via KL constraint.

---

## Inputs

- **Policy model**: Initialized from Stage 3
- **Reference model**: Frozen anchor from Stage 3
- **Preference pairs**: Validated data from Stage 2
- **Training configuration**: Hyperparameters

---

## DPO Loss Function

```
L_DPO = -E[(log σ(β * (r_chosen - r_rejected) - β * KL))]

Where:
- r_chosen = reward for chosen response
- r_rejected = reward for rejected response
- β = KL penalty strength (typically 0.1)
- KL = KL divergence between policy and reference
- σ = sigmoid function
```

**Intuition**: Maximize reward gap between chosen/rejected while penalizing deviation from reference.

---

## Process

### 1. Configure Training

```python
from trl import DPOConfig

dpo_config = DPOConfig(
    # Learning
    learning_rate=1e-6,  # Conservative for stability
    num_train_epochs=3,
    max_steps=1000,

    # Batch
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,  # Effective batch = 16

    # DPO-specific
    beta=0.1,  # KL penalty strength
    max_length=1024,
    max_prompt_length=512,

    # Optimization
    warmup_steps=100,
    lr_scheduler_type="cosine",
    weight_decay=0.01,
    max_grad_norm=1.0,

    # Logging
    logging_steps=10,
    eval_steps=100,
    save_steps=100,
    output_dir="outputs/dpo_training",

    # Compute
    fp16=False,
    bf16=True,  # Better for training stability
    gradient_checkpointing=True,
)
```

### 2. Monitor Training Metrics

**Key metrics to track**:

```python
# During training, monitor:
metrics = {
    "loss/train": ...,  # Should decrease
    "rewards/chosen": ...,  # Should increase
    "rewards/rejected": ...,  # Should decrease/stable
    "rewards/margins": ...,  # Should increase (chosen - rejected)
    "kl_divergence": ...,  # Must stay ≤0.1
    "logps/chosen": ...,  # Log probabilities
    "logps/rejected": ...,
}
```

**Ideal training trajectory**:
- Loss: Decreasing steadily
- Reward margin: Increasing
- KL divergence: Rising slowly, staying <0.1

### 3. Run Training Loop

```python
from trl import DPOTrainer

trainer = DPOTrainer(
    model=policy_model,
    ref_model=reference_model,
    args=dpo_config,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    tokenizer=tokenizer,
)

# Train
trainer.train()

# Save final model
trainer.save_model("outputs/dpo_final")
```

### 4. Handle KL Constraint Violations

```python
# Check KL divergence during training
def check_kl_constraint(trainer, step):
    """Monitor KL divergence and adjust if needed."""
    metrics = trainer.state.log_history[-1]
    kl = metrics.get("kl_divergence", 0.0)

    if kl > 0.1:
        print(f"⚠️ KL constraint violated at step {step}: {kl:.4f}")
        print("Actions:")
        print("  1. Reduce learning rate by 50%")
        print("  2. Increase beta (KL penalty)")
        print("  3. Rollback to previous checkpoint")

        # Option 1: Reduce learning rate
        for param_group in trainer.optimizer.param_groups:
            param_group['lr'] *= 0.5
        print(f"  → Learning rate reduced to {param_group['lr']}")

    return kl <= 0.1

# Check every eval_steps
if step % dpo_config.eval_steps == 0:
    passed = check_kl_constraint(trainer, step)
    if not passed:
        # Take corrective action
        pass
```

### 5. Evaluate on Validation Set

```python
def evaluate_dpo_model(trainer):
    """Evaluate DPO model on validation set."""
    eval_metrics = trainer.evaluate()

    print(f"Validation metrics:")
    print(f"  Loss: {eval_metrics['eval_loss']:.4f}")
    print(f"  Reward margin: {eval_metrics['eval_rewards/margins']:.4f}")
    print(f"  KL divergence: {eval_metrics['eval_kl_divergence']:.4f}")

    # Check quality gates
    kl_ok = eval_metrics['eval_kl_divergence'] <= 0.1
    margin_positive = eval_metrics['eval_rewards/margins'] > 0

    if kl_ok and margin_positive:
        print("✅ Quality gates passed")
    else:
        if not kl_ok:
            print("❌ KL divergence too high")
        if not margin_positive:
            print("❌ Reward margin not improving")

    return eval_metrics

# Evaluate after training
final_metrics = evaluate_dpo_model(trainer)
```

### 6. Select Best Checkpoint

```python
import json
from pathlib import Path

def select_best_checkpoint(output_dir: Path):
    """Select checkpoint with best validation metrics."""
    checkpoints = list(output_dir.glob("checkpoint-*"))

    best_checkpoint = None
    best_score = float("-inf")

    for ckpt in checkpoints:
        metrics_file = ckpt / "trainer_state.json"
        if not metrics_file.exists():
            continue

        with open(metrics_file) as f:
            state = json.load(f)

        # Find best by reward margin and KL constraint
        for entry in state.get("log_history", []):
            if "eval_kl_divergence" not in entry:
                continue

            kl = entry["eval_kl_divergence"]
            margin = entry.get("eval_rewards/margins", 0)

            # Score: reward margin if KL constraint satisfied
            score = margin if kl <= 0.1 else -float("inf")

            if score > best_score:
                best_score = score
                best_checkpoint = ckpt

    print(f"Best checkpoint: {best_checkpoint}")
    print(f"Best reward margin: {best_score:.4f}")

    return best_checkpoint

best_ckpt = select_best_checkpoint(Path("outputs/dpo_training"))
```

---

## Outputs

- ✅ **DPO-trained policy model**: Aligned with preferences
- ✅ **Training metrics**: Loss, rewards, KL divergence
- ✅ **Model checkpoints**: Saved at regular intervals
- ✅ **Best checkpoint**: Selected based on validation metrics

---

## Quality Gate

**Pass criteria**:
- Training completed successfully
- Final KL divergence ≤0.1
- Reward margin increasing (chosen > rejected)
- Validation metrics improving

**Failure handling**:
- If KL >0.1 → Reduce learning rate, increase beta, retry
- If margin not improving → Check data quality, adjust hyperparameters
- If training unstable → Reduce learning rate, increase warmup

---

## Time Estimate

- **Small models (7B)**: 2-3 days
- **Medium models (13-30B)**: 3-5 days
- **Large models (70B+)**: 5-10 days

Depends on:
- Model size
- Data volume
- Compute resources
- Number of training steps

---

## Common Issues

### Issue 1: KL Divergence Exceeds 0.1

**Symptoms**: Policy diverging too much from reference

**Causes**:
- Learning rate too high
- Beta (KL penalty) too low
- Training too many steps

**Solutions**:
```python
# Reduce learning rate
learning_rate = 5e-7  # Was 1e-6

# Increase beta
beta = 0.2  # Was 0.1

# Reduce training steps
max_steps = 500  # Was 1000
```

### Issue 2: Reward Margin Not Improving

**Symptoms**: chosen and rejected rewards similar

**Causes**:
- Poor preference signal (data quality)
- Learning rate too low
- Beta too high (over-constrained)

**Solutions**:
- Validate preference data quality (gap ≥0.15)
- Increase learning rate carefully
- Reduce beta slightly (e.g., 0.08)
- Increase training duration

### Issue 3: Training Unstable (Loss Spikes)

**Symptoms**: Loss oscillating or increasing

**Causes**:
- Learning rate too high
- Batch size too small
- Gradient clipping too loose

**Solutions**:
```python
# Reduce learning rate
learning_rate = 5e-7

# Increase effective batch size
gradient_accumulation_steps = 8  # Was 4

# Tighten gradient clipping
max_grad_norm = 0.5  # Was 1.0

# Add warmup
warmup_steps = 200  # Was 100
```

### Issue 4: Out of Memory

**Symptoms**: CUDA OOM during training

**Causes**:
- Batch size too large
- Sequence length too long
- Insufficient gradient checkpointing

**Solutions**:
```python
# Reduce batch size
per_device_train_batch_size = 2  # Was 4

# Enable gradient checkpointing
gradient_checkpointing = True

# Reduce max length
max_length = 512  # Was 1024

# Use mixed precision
bf16 = True
```

---

## Hyperparameter Tuning Guide

### Learning Rate

| Range | Use Case |
|-------|----------|
| 1e-7 - 5e-7 | Very conservative (large models, safety-critical) |
| 5e-7 - 1e-6 | **Standard** (most cases) |
| 1e-6 - 5e-6 | Aggressive (small models, strong data) |

**Rule**: Start conservative, increase if progress too slow.

### Beta (KL Penalty)

| Value | Effect | Use Case |
|-------|--------|----------|
| 0.05 | Weak constraint | Strong preference signal, less critical capabilities |
| **0.1** | **Standard** | **Balanced (most cases)** |
| 0.15-0.3 | Strong constraint | Capability preservation critical |

**Rule**: Increase if KL approaching 0.1, decrease if progress too slow.

### Batch Size

| Effective Batch | Training | Use Case |
|-----------------|----------|----------|
| 4-8 | Faster, less stable | Small datasets, experimentation |
| 16-32 | **Standard** | **Most cases** |
| 64+ | Slower, more stable | Large datasets, production |

**Rule**: Larger batch = more stable but slower.

---

## Advanced Techniques

### Technique 1: Adaptive Beta

```python
def adaptive_beta(current_kl, target_kl=0.1, beta=0.1, adapt_rate=0.1):
    """Adjust beta based on current KL divergence."""
    if current_kl > target_kl:
        # KL too high, increase penalty
        beta *= (1 + adapt_rate)
    elif current_kl < target_kl * 0.5:
        # KL too low, can relax penalty
        beta *= (1 - adapt_rate)
    return beta
```

### Technique 2: Curriculum Learning

```python
# Start with easy examples, progress to hard
def curriculum_dpo(pairs, reward_model):
    """Order preference pairs by difficulty."""
    # Score difficulty (smaller gap = harder)
    scored = []
    for pair in pairs:
        gap = reward_model.score_gap(pair)
        scored.append((gap, pair))

    # Sort by gap (easy to hard)
    scored.sort(reverse=True)

    # Return ordered pairs
    return [pair for gap, pair in scored]
```

### Technique 3: LoRA for Efficiency

```python
from peft import get_peft_model, LoraConfig

# Train only LoRA adapters
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=0.05,
)

policy_model = get_peft_model(policy_model, lora_config)

# ~1% trainable parameters, 10x faster training
```

---

## Related Documentation

- `../workflow.md` - Complete workflow overview
- `model-initialization.md` - Previous stage: Model setup
- `iterative-training.md` - Next stage: Refinement
- `quality-thresholds.md` - KL divergence requirements
- `../templates.md` - Training configuration templates
