# Stage 3: Model Initialization

Prepare reference and policy models for DPO training with KL divergence constraint.

---

## Overview

**Purpose**: Initialize DPO training components - reference model (frozen) and policy model (trainable).

**Goal**: Set up models correctly to enable KL-constrained preference optimization.

**Key Principle**: Reference model anchors the policy to prevent catastrophic drift.

---

## Inputs

- **Base SFT model checkpoint**: Trained model from Stage 1
- **DPO training configuration**: Hyperparameters and constraints

---

## DPO Architecture

```
User Prompt
    ↓
Policy Model (trainable) ──→ Chosen Response
    ↓                         Rejected Response
KL Divergence                      ↓
    ↓                         DPO Loss
Reference Model (frozen)            ↓
    ↓                         Backprop
Same Prompt                         ↓
                          Update Policy Model
```

**Two-model setup**:
1. **Reference model**: Frozen copy of base SFT model (π_ref)
2. **Policy model**: Trainable copy initialized from base SFT model (π_θ)

**KL constraint**: `KL(π_θ || π_ref) ≤ 0.1`

This ensures the policy stays close to the reference, preventing:
- Catastrophic forgetting
- Distribution collapse
- Capability regression

---

## Process

### 1. Load Base SFT Model

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

# Load base SFT model
model_path = "checkpoints/sft_baseline"
base_model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained(model_path)
```

**Checks**:
- Model loads without errors
- Tokenizer matches model
- Model can generate coherent text

### 2. Create Reference Model (Frozen)

```python
# Reference model: Frozen copy
reference_model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)

# Freeze all parameters
for param in reference_model.parameters():
    param.requires_grad = False

# Set to evaluation mode
reference_model.eval()
```

**Purpose**: Reference model provides stable anchor for KL calculation.

**Properties**:
- Identical to base SFT model
- Parameters frozen (no gradients)
- Used only for inference during training

### 3. Create Policy Model (Trainable)

```python
# Policy model: Trainable copy
policy_model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)

# Parameters remain trainable (default)
# Verify gradients enabled
assert any(p.requires_grad for p in policy_model.parameters())
```

**Purpose**: Policy model is trained to optimize preferences while staying close to reference.

**Properties**:
- Initially identical to reference model
- Parameters trainable (gradients enabled)
- Updated during DPO training

### 4. Verify Model Consistency

```python
# Verify architectures match
assert policy_model.config.to_dict() == reference_model.config.to_dict()

# Verify initial weights match
for (n1, p1), (n2, p2) in zip(
    policy_model.named_parameters(),
    reference_model.named_parameters()
):
    assert n1 == n2, f"Parameter name mismatch: {n1} vs {n2}"
    assert torch.allclose(p1, p2), f"Parameter value mismatch: {n1}"

print("✅ Models initialized consistently")
```

**Critical check**: Models must start identical.

### 5. Calculate Initial KL Divergence

```python
# Test on sample data
test_prompt = "Explain machine learning in simple terms."
inputs = tokenizer(test_prompt, return_tensors="pt")

with torch.no_grad():
    policy_logits = policy_model(**inputs).logits
    reference_logits = reference_model(**inputs).logits

# KL divergence calculation
policy_probs = torch.softmax(policy_logits, dim=-1)
reference_probs = torch.softmax(reference_logits, dim=-1)
kl_div = (policy_probs * (policy_probs.log() - reference_probs.log())).sum()

print(f"Initial KL divergence: {kl_div:.6f}")
# Should be ~0.0 since models are identical
assert kl_div < 1e-4, f"Initial KL too high: {kl_div}"
```

**Expected**: Initial KL ≈ 0 (models identical)

### 6. Initialize DPO Trainer

```python
from trl import DPOTrainer, DPOConfig

# DPO configuration
dpo_config = DPOConfig(
    beta=0.1,  # KL penalty strength
    learning_rate=1e-6,
    batch_size=4,
    gradient_accumulation_steps=4,
    max_length=1024,
    max_prompt_length=512,
    logging_steps=10,
    save_steps=100,
    output_dir="outputs/dpo_training",
)

# Initialize trainer
trainer = DPOTrainer(
    model=policy_model,
    ref_model=reference_model,
    args=dpo_config,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    tokenizer=tokenizer,
)
```

**Beta parameter**:
- Controls strength of KL penalty
- Higher β → policy stays closer to reference
- Typical range: 0.05 - 0.3
- Recommended: 0.1

### 7. Verify Training Setup

```python
# Verify reference model is frozen
assert not any(p.requires_grad for p in trainer.ref_model.parameters())

# Verify policy model is trainable
assert any(p.requires_grad for p in trainer.model.parameters())

# Verify data loaded correctly
assert len(trainer.train_dataset) > 0
assert len(trainer.eval_dataset) > 0

print("✅ DPO trainer initialized successfully")
```

---

## Outputs

- ✅ **Reference model**: Frozen anchor model
- ✅ **Policy model**: Trainable model initialized from reference
- ✅ **DPO trainer**: Configured and ready for training
- ✅ **Initial KL**: Verified ≈ 0

---

## Quality Gate

**Pass criteria**:
- Models load successfully
- Initial weights match (verified)
- Initial KL divergence ≈ 0
- Reference model frozen
- Policy model trainable
- Trainer initialized

**Failure handling**:
- If models don't load → Check checkpoint paths
- If weights don't match → Re-initialize from same checkpoint
- If initial KL > 1e-4 → Investigate model loading
- If trainer fails → Check configuration

---

## Time Estimate

**Setup time**: 1-2 hours

Depends on:
- Model size
- Loading speed
- GPU availability

---

## Common Issues

### Issue 1: Models Don't Match Initially

**Symptoms**: Initial KL divergence > 1e-4

**Causes**:
- Different random seeds
- Different loading methods
- Checkpoint corruption

**Solutions**:
```python
# Use same random seed
torch.manual_seed(42)

# Load with same method
model_path = "checkpoints/sft_baseline"
reference_model = AutoModelForCausalLM.from_pretrained(model_path)
policy_model = AutoModelForCausalLM.from_pretrained(model_path)
```

### Issue 2: Reference Model Not Frozen

**Symptoms**: Reference model parameters have gradients

**Causes**:
- Forgot to freeze parameters
- Training mode enabled

**Solutions**:
```python
# Ensure frozen
for param in reference_model.parameters():
    param.requires_grad = False
reference_model.eval()

# Verify
assert not any(p.requires_grad for p in reference_model.parameters())
```

### Issue 3: Out of Memory

**Symptoms**: CUDA OOM error during initialization

**Causes**:
- Two large models in memory
- Insufficient GPU memory

**Solutions**:
- Use `device_map="auto"` for model parallelism
- Reduce batch size
- Enable gradient checkpointing
- Use mixed precision (bfloat16)
- Offload reference model to CPU:
```python
reference_model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map={"": "cpu"}  # Keep on CPU
)
```

### Issue 4: Tokenizer Mismatch

**Symptoms**: Generation errors or incorrect tokenization

**Causes**:
- Tokenizer from different model
- Tokenizer configuration incorrect

**Solutions**:
```python
# Load tokenizer from same checkpoint
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Verify special tokens
assert tokenizer.pad_token is not None
assert tokenizer.eos_token is not None
```

---

## Memory Optimization

### For Large Models (70B+)

**Technique 1: Model parallelism**
```python
# Distribute across GPUs
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",  # Automatic distribution
    torch_dtype=torch.bfloat16
)
```

**Technique 2: CPU offloading**
```python
# Keep reference on CPU
reference_model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map={"": "cpu"}
)

# Policy on GPU
policy_model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="cuda:0"
)
```

**Technique 3: Gradient checkpointing**
```python
policy_model.gradient_checkpointing_enable()
```

**Technique 4: LoRA (Low-Rank Adaptation)**
```python
from peft import get_peft_model, LoraConfig

# Only train LoRA adapters
lora_config = LoraConfig(
    r=16,  # Rank
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
)

policy_model = get_peft_model(policy_model, lora_config)
# Now policy_model has ~1% trainable parameters
```

---

## Beta Parameter Selection

**Role of Beta (β)**:
- DPO loss: `L = -log(σ(β * (r_chosen - r_rejected) - β * KL))`
- Higher β → Stronger KL penalty → Policy stays closer to reference
- Lower β → Weaker KL penalty → Policy can diverge more

**Recommended values**:
- **Conservative** (β = 0.2-0.3): Use when capability preservation critical
- **Standard** (β = 0.1): Balanced approach, most common
- **Aggressive** (β = 0.05): Use when strong preference signal needed

**How to choose**:
1. Start with β = 0.1 (standard)
2. Monitor KL during training
3. If KL approaching 0.1 limit → Increase β
4. If preferences not learning → Decrease β

---

## Related Documentation

- `../workflow.md` - Complete workflow overview
- `preference-modeling.md` - Next stage: Reward model training
- `dpo-optimization.md` - Using initialized models for training
- `../templates.md` - Configuration examples
