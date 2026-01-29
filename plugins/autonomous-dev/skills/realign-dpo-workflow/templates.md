# DPO Workflow Templates

Actionable checklists and configuration templates for DPO implementation.

---

## Pre-DPO Planning Checklist

### Model Selection
- [ ] Base model selected and validated
- [ ] Model size appropriate for compute budget
- [ ] License compatible with use case
- [ ] Pre-training data understood

### Data Planning
- [ ] Target domain identified
- [ ] Prompt distribution defined
- [ ] Annotation strategy selected (human/AI/hybrid)
- [ ] Target pair count determined (≥1000)
- [ ] Budget allocated for data collection

### Infrastructure
- [ ] Training compute secured (GPUs/TPUs)
- [ ] Storage for checkpoints and logs
- [ ] Experiment tracking configured (W&B, MLflow)
- [ ] Version control for code and configs

### Evaluation
- [ ] Benchmark suite selected
- [ ] Baseline metrics defined
- [ ] Human evaluation protocol designed
- [ ] Success criteria documented

---

## Stage-by-Stage Checklists

### Stage 1: SFT Preparation

- [ ] Base model downloaded and verified
- [ ] SFT training data prepared and validated
- [ ] Train/validation split created (e.g., 90/10)
- [ ] Training configuration finalized
- [ ] SFT training completed successfully
- [ ] Validation perplexity acceptable
- [ ] Capability benchmarks run and recorded
- [ ] Baseline metrics documented:
  - [ ] MMLU score: _____
  - [ ] HumanEval pass@1: _____
  - [ ] GSM8K accuracy: _____
  - [ ] Other domain metrics: _____
- [ ] Model checkpoint saved with clear naming
- [ ] Training logs archived

### Stage 2: Preference Data Generation

- [ ] Prompt dataset collected (≥1000 unique prompts)
- [ ] Response generation strategy defined
- [ ] Multiple responses per prompt generated (≥2)
- [ ] Annotation guidelines created
- [ ] Annotators trained (if human annotation)
- [ ] Preference pairs collected
- [ ] Data format validated (JSONL):
  ```json
  {"prompt": "...", "chosen": "...", "rejected": "..."}
  ```
- [ ] Quality validation completed:
  - [ ] Preference gap calculated: _____ (target ≥0.15)
  - [ ] Pair count: _____ (target ≥1000)
  - [ ] Decontamination score: _____ (target ≥0.9)
- [ ] Conflicting preferences resolved
- [ ] Data splits created (80% train, 20% validation)
- [ ] Data stored with version control

### Stage 3: Model Initialization

- [ ] Reference model loaded from SFT checkpoint
- [ ] Reference model frozen (no gradients)
- [ ] Policy model initialized as copy of reference
- [ ] Model architectures verified to match
- [ ] Tokenizer consistency checked
- [ ] Initial KL divergence calculated (should be ≈0)
- [ ] DPO trainer initialized
- [ ] Configuration validated

### Stage 4: Preference Modeling

- [ ] Reward model architecture selected
- [ ] Training data loaded (preference pairs)
- [ ] Train/validation split configured
- [ ] Reward model training completed
- [ ] Training accuracy: _____ (target ≥70%)
- [ ] Validation accuracy: _____ (target ≥70%)
- [ ] Overfitting checked (train/val gap <10%)
- [ ] Reward model checkpoint saved
- [ ] Optional: Low-quality pairs filtered

### Stage 5: DPO Optimization

- [ ] Hyperparameters configured (see config template below)
- [ ] Performance optimization completed:
  - [ ] Hardware selected based on model size
  - [ ] Batch size optimized (M4 Max: 32, M3 Ultra: 4)
  - [ ] Environment variables set (MLX_METAL_PREALLOCATE, MLX_METAL_FAST_SYNCH)
  - [ ] Work distribution configured if distributed (65/35 split)
- [ ] Training loop implemented
- [ ] Logging configured (W&B, TensorBoard)
- [ ] Checkpoint saving strategy defined
- [ ] DPO training started
- [ ] Training metrics monitored:
  - [ ] Preference accuracy trending up
  - [ ] KL divergence ≤0.1
  - [ ] Training loss decreasing
  - [ ] Throughput (examples/sec): _____
- [ ] Validation evaluation run
- [ ] Quality gates checked:
  - [ ] KL divergence: _____ (target ≤0.1)
  - [ ] Preference gap: _____ (target ≥0.15)
- [ ] Best checkpoint identified
- [ ] Training logs saved

### Stage 6: Iterative Training

- [ ] Current iteration metrics recorded
- [ ] Weaknesses identified from evaluation
- [ ] Additional preference data collected (if needed)
- [ ] Next iteration DPO training configured
- [ ] Iteration training completed
- [ ] Metrics compared to previous iteration:
  - [ ] Iteration 1 score: _____
  - [ ] Iteration 2 score: _____
  - [ ] Iteration 3 score: _____
- [ ] Convergence assessed
- [ ] Best iteration checkpoint identified
- [ ] Decision made (continue/stop/rollback)

### Stage 7: Evaluation & Monitoring

- [ ] Final model checkpoint loaded
- [ ] Capability benchmarks run:
  - [ ] MMLU: _____ (baseline: _____)
  - [ ] HumanEval: _____ (baseline: _____)
  - [ ] GSM8K: _____ (baseline: _____)
  - [ ] Domain-specific: _____ (baseline: _____)
- [ ] Capability retention calculated:
  - [ ] Retention rate: _____ % (target ≥95%)
- [ ] Alignment evaluation completed:
  - [ ] Win rate vs baseline: _____ % (target >50%)
  - [ ] Human eval score: _____ /10
  - [ ] Qualitative assessment: _____
- [ ] Quality thresholds verified:
  - [ ] Final KL divergence: _____ (≤0.1)
  - [ ] Preference gap maintained: _____ (≥0.15)
  - [ ] No eval contamination detected
- [ ] All success criteria met
- [ ] Evaluation report written
- [ ] Deployment decision made

---

## Configuration Templates

### DPO Training Configuration (YAML)

```yaml
# dpo_config.yaml
model:
  base_model: "meta-llama/Llama-2-7b-hf"  # Path or HF model ID
  reference_model: "checkpoints/sft_baseline"  # Frozen reference
  policy_model: "checkpoints/sft_baseline"  # Initialized from reference

data:
  train_file: "data/preference_pairs_train.jsonl"
  validation_file: "data/preference_pairs_val.jsonl"
  max_prompt_length: 512
  max_response_length: 1024

training:
  learning_rate: 1.0e-6  # Conservative for stability
  beta: 0.1  # KL penalty strength (higher = closer to reference)
  batch_size: 4  # Per device
  gradient_accumulation_steps: 4  # Effective batch = 16
  max_steps: 1000
  warmup_steps: 100
  logging_steps: 10
  eval_steps: 100
  save_steps: 100

optimization:
  optimizer: "adamw"
  weight_decay: 0.01
  max_grad_norm: 1.0
  lr_scheduler: "cosine"

constraints:
  kl_target: 0.1  # Maximum KL divergence
  preference_gap_target: 0.15  # Minimum preference gap

compute:
  fp16: true  # Mixed precision training
  device: "cuda"
  num_devices: 8
  gradient_checkpointing: true  # Memory optimization

logging:
  wandb_project: "dpo-alignment"
  wandb_run_name: "dpo-exp-001"
  output_dir: "outputs/dpo-exp-001"
```

### Preference Data Format (JSONL)

```jsonl
{"prompt": "Explain quantum entanglement to a 10-year-old.", "chosen": "Imagine you have two magic coins. When you flip one and it lands on heads, the other coin automatically lands on tails, no matter how far apart they are. That's similar to how particles can be 'entangled' in quantum physics!", "rejected": "Quantum entanglement is a phenomenon where quantum states of two or more objects have to be described with reference to each other, even though the individual objects may be spatially separated."}
{"prompt": "Write a haiku about programming.", "chosen": "Code flows like water,\nBugs hide in silent darkness,\nDebug brings the light.", "rejected": "Programming is hard.\nWriting code all day long.\nComputers are cool."}
{"prompt": "What's 15% of 80?", "chosen": "To find 15% of 80:\n15% as decimal is 0.15\n0.15 × 80 = 12\n\nSo 15% of 80 is 12.", "rejected": "12"}
```

### Evaluation Benchmark Configuration (Python)

```python
# eval_config.py
from pathlib import Path

EVALUATION_CONFIG = {
    "capability_benchmarks": {
        "mmlu": {
            "dataset": "cais/mmlu",
            "subset": "all",
            "num_shots": 5,
            "metric": "accuracy",
            "baseline_threshold": 0.45,  # Minimum acceptable
        },
        "humaneval": {
            "dataset": "openai_humaneval",
            "metric": "pass@1",
            "baseline_threshold": 0.15,
        },
        "gsm8k": {
            "dataset": "gsm8k",
            "subset": "main",
            "num_shots": 8,
            "metric": "accuracy",
            "baseline_threshold": 0.30,
        },
    },
    "alignment_evaluation": {
        "preference_validation": {
            "test_set": "data/preference_pairs_test.jsonl",
            "metric": "win_rate",
            "baseline_threshold": 0.50,  # Must beat baseline
        },
        "human_eval": {
            "sample_size": 100,
            "criteria": ["helpfulness", "harmlessness", "honesty"],
            "scale": "1-10",
        },
    },
    "quality_thresholds": {
        "kl_divergence": {"max": 0.1},
        "preference_gap": {"min": 0.15},
        "capability_retention": {"min": 0.95},
        "decontamination": {"min": 0.9},
    },
}
```

### Training Monitoring Script (Python)

```python
# monitor_training.py
from pathlib import Path
from training_metrics import validate_dpo_pairs

def check_quality_gates(checkpoint_dir: Path, config: dict) -> dict:
    """Check if quality thresholds are met during training.

    Args:
        checkpoint_dir: Path to checkpoint directory
        config: Training configuration dict

    Returns:
        Dict with quality gate results
    """
    results = {
        "kl_divergence": None,
        "preference_gap": None,
        "gates_passed": False,
    }

    # Load metrics from checkpoint
    metrics_file = checkpoint_dir / "training_metrics.json"
    if not metrics_file.exists():
        return results

    import json
    with open(metrics_file) as f:
        metrics = json.load(f)

    # Check KL divergence
    kl = metrics.get("kl_divergence", float("inf"))
    kl_threshold = config["constraints"]["kl_target"]
    results["kl_divergence"] = kl

    # Check preference gap
    val_file = Path(config["data"]["validation_file"])
    dpo_metrics = validate_dpo_pairs(
        dpo_path=val_file,
        gap_threshold=config["constraints"]["preference_gap_target"]
    )
    results["preference_gap"] = dpo_metrics.avg_gap

    # Determine if gates passed
    results["gates_passed"] = (
        kl <= kl_threshold and
        dpo_metrics.avg_gap >= config["constraints"]["preference_gap_target"]
    )

    return results

# Example usage:
if __name__ == "__main__":
    import yaml

    config_path = Path("dpo_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    checkpoint_dir = Path("outputs/dpo-exp-001/checkpoint-1000")
    results = check_quality_gates(checkpoint_dir, config)

    print(f"KL Divergence: {results['kl_divergence']:.4f} (target ≤0.1)")
    print(f"Preference Gap: {results['preference_gap']:.4f} (target ≥0.15)")
    print(f"Gates Passed: {'✅' if results['gates_passed'] else '❌'}")
```

### Hyperparameter Tuning Sweep (W&B)

```yaml
# sweep_config.yaml
program: train_dpo.py
method: bayes
metric:
  name: validation/win_rate
  goal: maximize
parameters:
  learning_rate:
    distribution: log_uniform_values
    min: 1e-7
    max: 1e-5
  beta:
    distribution: uniform
    min: 0.05
    max: 0.3
  batch_size:
    values: [2, 4, 8]
  warmup_ratio:
    distribution: uniform
    min: 0.05
    max: 0.15
```

---

## Quality Gate Enforcement Script

```python
# enforce_quality_gates.py
from pathlib import Path
from training_metrics import validate_dpo_pairs
import sys

def enforce_gates(
    stage: str,
    dpo_pairs_path: Path = None,
    kl_divergence: float = None,
    capability_retention: float = None,
) -> bool:
    """Enforce quality gates for DPO workflow stages.

    Args:
        stage: Stage name (e.g., "preference_data", "dpo_training", "evaluation")
        dpo_pairs_path: Path to preference pairs (for Stage 2)
        kl_divergence: Computed KL divergence (for Stage 5)
        capability_retention: Retention percentage (for Stage 7)

    Returns:
        True if gates passed, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Quality Gate Enforcement: {stage}")
    print(f"{'='*60}\n")

    if stage == "preference_data":
        if dpo_pairs_path is None:
            print("❌ Error: dpo_pairs_path required for preference_data stage")
            return False

        MIN_GAP = 3/20  # 0.15 preference gap
        metrics = validate_dpo_pairs(dpo_pairs_path, gap_threshold=MIN_GAP)

        print(f"Preference Gap: {metrics.avg_gap:.4f} (target ≥0.15)")
        print(f"Pair Count: {metrics.total_pairs} (target ≥1000)")
        print(f"Decontamination: {metrics.decontamination:.4f} (target ≥0.9)")

        gates_passed = (
            metrics.avg_gap >= MIN_GAP and
            metrics.total_pairs >= 1000 and
            metrics.decontamination >= 0.9
        )

    elif stage == "dpo_training":
        if kl_divergence is None:
            print("❌ Error: kl_divergence required for dpo_training stage")
            return False

        print(f"KL Divergence: {kl_divergence:.4f} (target ≤0.1)")
        gates_passed = kl_divergence <= 0.1

    elif stage == "evaluation":
        if capability_retention is None:
            print("❌ Error: capability_retention required for evaluation stage")
            return False

        print(f"Capability Retention: {capability_retention:.1f}% (target ≥95%)")
        gates_passed = capability_retention >= 95.0

    else:
        print(f"❌ Error: Unknown stage '{stage}'")
        return False

    print(f"\n{'='*60}")
    print(f"Result: {'✅ PASSED' if gates_passed else '❌ FAILED'}")
    print(f"{'='*60}\n")

    return gates_passed

# Example usage:
if __name__ == "__main__":
    # Stage 2: Preference Data
    passed = enforce_gates(
        stage="preference_data",
        dpo_pairs_path=Path("data/preference_pairs.jsonl")
    )
    if not passed:
        sys.exit(1)

    # Stage 5: DPO Training
    passed = enforce_gates(
        stage="dpo_training",
        kl_divergence=0.08
    )
    if not passed:
        sys.exit(1)

    # Stage 7: Evaluation
    passed = enforce_gates(
        stage="evaluation",
        capability_retention=96.5
    )
    if not passed:
        sys.exit(1)
```

---

## Related Documentation

- `workflow.md` - Complete 7-stage pipeline
- `docs/quality-thresholds.md` - Threshold definitions
- `docs/dpo-optimization.md` - Training implementation details
- SKILL.md - High-level overview
