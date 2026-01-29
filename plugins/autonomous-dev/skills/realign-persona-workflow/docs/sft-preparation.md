# Stage 1: SFT Preparation

Supervised Fine-Tuning (SFT) preparation establishes the baseline model and metrics before DPO training.

---

## Overview

**Purpose**: Train and validate base model on instruction-following data to establish capability baseline.

**Goal**: Create a strong starting point for DPO that has general capability without preference optimization.

**Key Principle**: A weak SFT base produces poor DPO results. Invest time in quality SFT training.

---

## Inputs

- **Pre-trained base model**: Foundation model (e.g., Llama-2, Mistral)
- **SFT training data**: Instruction-response pairs (≥10K examples)
- **Evaluation benchmarks**: Standard capability tests (MMLU, HumanEval, etc.)

---

## Process

### 1. Select Base Model

**Considerations**:
- Model size vs compute budget
- License compatibility with use case
- Pre-training data alignment with domain
- Community support and documentation

**Common choices**:
- Llama-2/3 family (7B, 13B, 70B)
- Mistral models (7B, 8x7B)
- Falcon models
- Custom pre-trained models

### 2. Prepare SFT Data

**Data requirements**:
- Format: Instruction-response pairs
- Quality: High-quality, diverse responses
- Quantity: ≥10K examples (more is better)
- Coverage: Broad capability coverage

**Data format example**:
```json
{
  "instruction": "Explain the difference between supervised and unsupervised learning.",
  "response": "Supervised learning uses labeled data where the correct answer is known..."
}
```

**Quality checks**:
- Response completeness and accuracy
- Instruction clarity and diversity
- No toxic or harmful content
- Deduplication (prevent memorization)

### 3. Configure Training

**Recommended hyperparameters** (7B model):
```yaml
learning_rate: 2e-5
batch_size: 8
gradient_accumulation_steps: 4
max_steps: 5000
warmup_steps: 500
lr_scheduler: "cosine"
weight_decay: 0.01
max_length: 2048
```

**For larger models** (70B+):
- Reduce learning rate (1e-5)
- Increase gradient accumulation
- Enable gradient checkpointing
- Use mixed precision (fp16/bf16)

### 4. Train SFT Model

**Training loop**:
1. Initialize model from pre-trained checkpoint
2. Tokenize instruction-response pairs
3. Train with causal language modeling objective
4. Monitor training loss (should decrease steadily)
5. Evaluate on held-out validation set
6. Save checkpoints regularly

**Red flags during training**:
- Loss not decreasing → Learning rate too high/low
- Validation loss increasing → Overfitting
- Training loss oscillating → Batch size too small

### 5. Validate SFT Performance

**Validation metrics**:
- Perplexity on held-out set (lower is better)
- Generation quality (sample outputs)
- Instruction-following accuracy

**Minimum thresholds**:
- Validation perplexity <20
- Clear instruction-following behavior
- Coherent and relevant responses

### 6. Run Capability Benchmarks

**Critical step**: Establish baseline metrics for regression detection.

**Recommended benchmarks**:

| Benchmark | Domain | Metric | Typical Range |
|-----------|--------|--------|---------------|
| MMLU | General knowledge | Accuracy | 30-70% |
| HumanEval | Code generation | pass@1 | 10-50% |
| GSM8K | Math reasoning | Accuracy | 20-60% |
| TruthfulQA | Truthfulness | MC1/MC2 | 30-50% |
| HellaSwag | Common sense | Accuracy | 60-85% |

**Record baseline metrics**:
```python
baseline_metrics = {
    "mmlu": 45.2,
    "humaneval": 18.5,
    "gsm8k": 32.8,
    "truthfulqa_mc1": 38.1,
    "hellaswag": 72.4,
}
# Save for comparison after DPO
```

### 7. Save Model Checkpoint

**Checkpoint naming convention**:
```
checkpoints/
  sft_baseline/
    config.json
    pytorch_model.bin
    tokenizer.json
    baseline_metrics.json
```

**Metadata to save**:
- Training configuration
- Final training loss
- Validation perplexity
- Benchmark scores
- Training date and duration

---

## Outputs

- ✅ **Base SFT model checkpoint**: Saved and validated
- ✅ **Baseline capability metrics**: Recorded for regression detection
- ✅ **Evaluation results**: Documented for comparison
- ✅ **Training logs**: Archived for reproducibility

---

## Quality Gate

**Pass criteria**:
- SFT training completed successfully
- Validation perplexity acceptable (<20)
- Instruction-following behavior demonstrated
- Capability benchmarks recorded
- Model checkpoint saved

**Failure handling**:
- If validation loss high → Improve data quality or increase training
- If benchmarks below expected → Review model selection or data
- If training unstable → Adjust learning rate or batch size

---

## Time Estimate

- **Small models** (7B): 1-2 days
- **Medium models** (13-30B): 2-4 days
- **Large models** (70B+): 3-7 days

Depends on:
- Model size
- Data volume
- Compute resources
- Number of training iterations

---

## Common Issues

### Issue 1: Training Loss Not Decreasing

**Symptoms**: Loss flat or increasing after warmup

**Causes**:
- Learning rate too low
- Data quality issues (noisy labels)
- Model initialization problems

**Solutions**:
- Increase learning rate (try 5e-5)
- Review and clean training data
- Verify model loads correctly from pre-trained checkpoint

### Issue 2: Validation Loss Increasing (Overfitting)

**Symptoms**: Training loss decreasing but validation loss increasing

**Causes**:
- Training too long
- Insufficient data diversity
- Model too large for dataset

**Solutions**:
- Reduce training steps
- Apply regularization (weight decay, dropout)
- Add more diverse training examples
- Use early stopping

### Issue 3: Poor Instruction Following

**Symptoms**: Model generates coherent text but ignores instructions

**Causes**:
- Weak instruction signal in data
- Data format inconsistency
- Insufficient training

**Solutions**:
- Improve instruction clarity in data
- Ensure consistent formatting
- Increase training duration
- Add more instruction-following examples

---

## Best Practices

1. **Start with quality data** - 10K high-quality examples > 100K low-quality
2. **Monitor validation closely** - Early stopping prevents overfitting
3. **Save multiple checkpoints** - Best validation, best training, latest
4. **Record all metrics** - Essential for DPO regression detection
5. **Test instruction following** - Sample generations before proceeding
6. **Use established recipes** - Follow community best practices for your model
7. **Document everything** - Configuration, metrics, decisions

---

## Related Documentation

- `../workflow.md` - Complete workflow overview
- `preference-data-generation.md` - Next stage: Creating preference pairs
- `../templates.md` - Configuration templates
- `capability-assessment.md` - Baseline metric recording
