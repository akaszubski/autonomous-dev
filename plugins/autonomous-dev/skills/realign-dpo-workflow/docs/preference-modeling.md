# Stage 4: Preference Modeling

Train or validate reward model to predict human preferences for quality control.

---

## Overview

**Purpose**: Create reward model that accurately predicts chosen vs rejected responses.

**Goal**: Achieve ≥70% accuracy on validation set for reliable preference signal.

**Key Principle**: Reward model quality directly impacts DPO effectiveness and data filtering.

---

## Inputs

- **Preference pairs**: Validated data from Stage 2
- **Base model**: SFT model or separate reward model architecture

---

## Process

### 1. Prepare Reward Model Data

```python
# Convert preference pairs to reward model format
def prepare_reward_data(preference_pairs):
    """Convert DPO pairs to reward model training format."""
    data = []
    for pair in preference_pairs:
        # Positive example (chosen)
        data.append({
            "text": pair["prompt"] + " " + pair["chosen"],
            "label": 1.0  # High reward
        })
        # Negative example (rejected)
        data.append({
            "text": pair["prompt"] + " " + pair["rejected"],
            "label": 0.0  # Low reward
        })
    return data
```

### 2. Split Data

**Recommended split**:
- Training: 80% (≥800 pairs → 1600 examples)
- Validation: 20% (≥200 pairs → 400 examples)

**Stratification**: Ensure balanced distribution of categories.

### 3. Train Reward Model

```python
from transformers import AutoModelForSequenceClassification

# Initialize reward model
reward_model = AutoModelForSequenceClassification.from_pretrained(
    "checkpoints/sft_baseline",
    num_labels=1,  # Regression task (reward score)
)

# Training configuration
training_args = {
    "learning_rate": 2e-5,
    "batch_size": 16,
    "num_epochs": 3,
    "weight_decay": 0.01,
}

# Train on preference comparisons
# Model learns to assign higher scores to chosen responses
```

### 4. Evaluate Accuracy

```python
def evaluate_reward_model(model, validation_pairs):
    """Evaluate reward model pairwise accuracy."""
    correct = 0
    total = len(validation_pairs)

    for pair in validation_pairs:
        # Score chosen and rejected
        chosen_score = model(pair["prompt"] + " " + pair["chosen"])
        rejected_score = model(pair["prompt"] + " " + pair["rejected"])

        # Check if chosen scored higher
        if chosen_score > rejected_score:
            correct += 1

    accuracy = correct / total
    return accuracy

val_accuracy = evaluate_reward_model(reward_model, validation_pairs)
print(f"Validation accuracy: {val_accuracy:.1%} (target ≥70%)")
```

### 5. Check for Overfitting

```python
train_accuracy = evaluate_reward_model(reward_model, train_pairs)
val_accuracy = evaluate_reward_model(reward_model, val_pairs)

gap = train_accuracy - val_accuracy
print(f"Train accuracy: {train_accuracy:.1%}")
print(f"Val accuracy: {val_accuracy:.1%}")
print(f"Gap: {gap:.1%} (target <10%)")

# Check overfitting (train/val accuracy gap, different from preference gap)
if gap > 0.1:  # 10% train/val gap indicates overfitting
    print("⚠️ Overfitting detected - reduce training or add regularization")
```

### 6. Optional: Filter Low-Quality Pairs

```python
def filter_low_confidence_pairs(pairs, reward_model, threshold=0.2):
    """Remove pairs where reward model is uncertain."""
    filtered = []

    for pair in pairs:
        chosen_score = reward_model(pair["prompt"] + " " + pair["chosen"])
        rejected_score = reward_model(pair["prompt"] + " " + pair["rejected"])

        # Reward gap (confidence)
        gap = abs(chosen_score - rejected_score)

        if gap >= threshold:
            filtered.append(pair)
        else:
            print(f"Filtered low-confidence pair (gap={gap:.3f})")

    return filtered

# Filter training data
filtered_pairs = filter_low_confidence_pairs(train_pairs, reward_model)
print(f"Retained {len(filtered_pairs)}/{len(train_pairs)} pairs")
```

---

## Outputs

- ✅ **Trained reward model**: Checkpoint saved
- ✅ **Accuracy metrics**: Train and validation scores
- ✅ **Filtered pairs** (optional): High-confidence preference data

---

## Quality Gate

**Pass criteria**:
- Validation accuracy ≥70%
- Train/val gap <10% (no severe overfitting)
- Model checkpoint saved

**Decision**:
- If accuracy ≥70% → Proceed to DPO optimization
- If accuracy <70% → Improve data quality or model capacity

---

## Time Estimate

- **Training**: 1-2 days (depending on data size)
- **Validation**: 2-4 hours
- **Filtering** (optional): 4-8 hours

---

## Common Issues

### Issue 1: Low Validation Accuracy (<70%)

**Causes**:
- Poor data quality (weak preference signal)
- Model capacity insufficient
- Training configuration suboptimal

**Solutions**:
- Improve preference pair quality (increase gap)
- Use larger reward model
- Increase training epochs
- Adjust learning rate

### Issue 2: Overfitting (train/val gap >10%)

**Causes**:
- Training too long
- Insufficient validation data
- Model too complex

**Solutions**:
- Reduce training epochs
- Add regularization (weight decay, dropout)
- Increase validation set size
- Use early stopping

### Issue 3: Reward Model Bias

**Symptoms**: Model favors certain response patterns regardless of quality

**Causes**:
- Biased training data
- Spurious correlations learned

**Solutions**:
- Review and balance training data
- Add diverse examples
- Analyze model predictions on edge cases

---

## Best Practices

1. **Start simple**: Use base SFT model as reward model (fine-tune last layer)
2. **Validate thoroughly**: Check accuracy on diverse examples
3. **Monitor overfitting**: Track train/val gap continuously
4. **Filter strategically**: Remove only truly ambiguous pairs
5. **Save checkpoints**: Best validation, not final epoch
6. **Document biases**: Record known model limitations

---

## Related Documentation

- `../workflow.md` - Complete workflow overview
- `preference-data-generation.md` - Previous stage: Creating pairs
- `dpo-optimization.md` - Next stage: DPO training
- `quality-thresholds.md` - Accuracy requirements
