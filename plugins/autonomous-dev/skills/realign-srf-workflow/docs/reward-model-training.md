# Stage 3: Reward Model Training

Train reward model to predict preference scores for RL fine-tuning.

---

## Overview

**Purpose**: Create interpretable reward model that accurately predicts human preferences.

**Goal**: Train reward model with ≥70% accuracy on validation set.

**Key Principle**: Reward model quality directly determines RL fine-tuning effectiveness.

---

## Inputs

- **Validated preference pairs**: From Stage 2 (≥1000 pairs)
- **Base model**: SFT model or separate architecture
- **Training configuration**: Learning rate, batch size, epochs

---

## Process

### 1. Choose Reward Model Architecture

**Option A: Shared Architecture (Recommended)**
- Add reward head to base SFT model
- Shares parameters with policy
- More efficient, better alignment

**Option B: Separate Model**
- Smaller dedicated reward model
- Independent from policy
- Faster inference, easier debugging

**Trade-offs**:
| Aspect | Shared | Separate |
|--------|--------|----------|
| Parameter efficiency | High | Low |
| Training time | Medium | Fast |
| Inference speed | Slow | Fast |
| Alignment | Strong | Moderate |

### 2. Prepare Training Data

**Format preference pairs for training**:
```python
from pathlib import Path
import json

def prepare_reward_training_data(pairs_file: Path):
    """Convert preference pairs to reward training format.
    
    Input format (JSONL):
    {"prompt": "...", "chosen": "...", "rejected": "..."}
    
    Output format:
    {
        "input_chosen": "prompt + chosen",
        "input_rejected": "prompt + rejected",
        "label": 1  # chosen is better
    }
    """
    training_examples = []
    
    with open(pairs_file) as f:
        for line in f:
            pair = json.loads(line)
            training_examples.append({
                "input_chosen": pair["prompt"] + " " + pair["chosen"],
                "input_rejected": pair["prompt"] + " " + pair["rejected"],
                "label": 1  # Binary: chosen > rejected
            })
    
    return training_examples
```

**Data splits**:
- Training: 80% (≥800 pairs)
- Validation: 20% (≥200 pairs)

### 3. Implement Reward Model Training

**Training loop**:
```python
import torch
from transformers import AutoModelForSequenceClassification, Trainer

def train_reward_model(
    base_model: str,
    train_dataset,
    val_dataset,
    config: dict
):
    """Train reward model using binary classification.
    
    Args:
        base_model: Base model name or path
        train_dataset: Training preference pairs
        val_dataset: Validation preference pairs
        config: Training configuration
    """
    # Load model with single output (reward score)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=1  # Single reward score
    )
    
    # Configure training
    training_args = TrainingArguments(
        output_dir="outputs/reward_model",
        learning_rate=config["learning_rate"],
        per_device_train_batch_size=config["batch_size"],
        num_train_epochs=config["max_epochs"],
        evaluation_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        load_best_model_at_end=True,
        metric_for_best_model="accuracy"
    )
    
    # Custom loss: Bradley-Terry model
    def compute_loss(model, inputs, return_outputs=False):
        """Compute pairwise ranking loss."""
        # Forward pass for chosen and rejected
        reward_chosen = model(inputs["input_chosen"]).logits
        reward_rejected = model(inputs["input_rejected"]).logits
        
        # Bradley-Terry loss
        loss = -torch.log(torch.sigmoid(reward_chosen - reward_rejected)).mean()
        
        return (loss, None) if return_outputs else loss
    
    # Train
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_accuracy
    )
    
    trainer.train()
    
    return model
```

### 4. Monitor Training Metrics

**Critical metrics**:
- **Training accuracy**: Should reach ≥70%
- **Validation accuracy**: Must be ≥70% (primary quality gate)
- **Loss convergence**: Should decrease smoothly
- **Train/val gap**: Should be <10% (prevent overfitting)

**Monitoring script**:
```python
def monitor_reward_training(trainer_state):
    """Monitor reward model training progress."""
    train_acc = trainer_state.log_history[-1]["train_accuracy"]
    val_acc = trainer_state.log_history[-1]["eval_accuracy"]
    
    print(f"Training Accuracy: {train_acc:.2%}")
    print(f"Validation Accuracy: {val_acc:.2%}")
    print(f"Train/Val Gap: {(train_acc - val_acc):.2%}")
    
    if val_acc < 0.70:
        print("⚠️ Validation accuracy below threshold (70%)")
    if train_acc - val_acc > 0.10:
        print("⚠️ Overfitting detected (gap >10%)")
```

### 5. Save Best Checkpoint

**Checkpoint selection**:
- Select based on **validation accuracy** (not training)
- Save complete model state
- Include tokenizer and config
- Document training metrics

```python
# Save best reward model
trainer.save_model("outputs/best_reward_model")

# Save metrics
metrics = {
    "train_accuracy": final_train_acc,
    "val_accuracy": final_val_acc,
    "overfitting_gap": train_acc - val_acc,
    "num_parameters": model.num_parameters(),
    "training_steps": trainer.state.global_step
}

with open("outputs/best_reward_model/metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)
```

---

## Outputs

- ✅ **Trained reward model**: Checkpoint with ≥70% validation accuracy
- ✅ **Training metrics**: Accuracy, loss, overfitting analysis
- ✅ **Learning curves**: Training and validation trajectories
- ✅ **Model card**: Architecture, hyperparameters, performance

---

## Quality Gate

**Pass criteria**:
- Training accuracy ≥70%
- Validation accuracy ≥70%
- Train/val gap <10% (no severe overfitting)
- Loss converged

**Failure handling**:
- If val accuracy <70% → Improve data quality, increase capacity
- If train/val gap >10% → Add regularization, more data
- If not converging → Adjust learning rate, longer training

---

## Time Estimate

- **Small model** (1B params): 4-8 hours
- **Medium model** (7B params): 1-2 days
- **Large model** (70B+ params): 3-5 days

---

## Common Issues

### Issue 1: Low Validation Accuracy (<70%)

**Causes**:
- Weak preference signal in data
- Insufficient model capacity
- Poor hyperparameter selection

**Solutions**:
- Review data quality (Stage 2)
- Increase model size
- Tune learning rate (try 1e-6 to 1e-4)
- Train for more epochs

### Issue 2: Overfitting (train/val gap >10%)

**Causes**:
- Small validation set
- Model too large for data
- Insufficient regularization

**Solutions**:
- Increase validation set size
- Add dropout or weight decay
- Early stopping based on validation
- Collect more diverse training data

### Issue 3: Training Instability

**Causes**:
- Learning rate too high
- Gradient explosion
- Batch size too small

**Solutions**:
- Reduce learning rate (try 1e-6)
- Gradient clipping (max_norm=1.0)
- Increase batch size
- Use warmup steps

---

## Best Practices

1. **Start simple** - Begin with smaller model, validate approach
2. **Monitor overfitting** - Validation accuracy > training accuracy indicates issues
3. **Save frequently** - Checkpoint every 100 steps
4. **Compare baselines** - Test against random baseline (50% accuracy)
5. **Analyze errors** - Which preference types does model struggle with?
6. **Document thoroughly** - Record all hyperparameters and design decisions

---

## Related Documentation

- `../workflow.md` - Complete workflow overview
- `reward-model-validation.md` - Next stage: Validation
- `quality-thresholds.md` - Accuracy threshold definitions
- `../templates.md` - Training configuration templates
