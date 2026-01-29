# SRF Workflow Templates

Actionable checklists and configuration templates for SRF implementation.

---

## Pre-SRF Planning Checklist

### Model Selection
- [ ] Base model selected and validated
- [ ] Model size appropriate for compute budget
- [ ] License compatible with use case
- [ ] Reward model architecture decided (shared vs separate)

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
- [ ] RL framework selected (TRL, trlX, etc.)

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
- [ ] Data splits created (80% train, 20% validation)
- [ ] Data stored with version control

### Stage 3: Reward Model Training

- [ ] Reward model architecture selected
- [ ] Training data loaded (preference pairs)
- [ ] Train/validation split configured
- [ ] Loss function implemented (binary cross-entropy)
- [ ] Training loop configured
- [ ] Reward model training completed
- [ ] Training accuracy: _____ (target ≥70%)
- [ ] Validation accuracy: _____ (target ≥70%)
- [ ] Loss curves reviewed
- [ ] Best checkpoint saved

### Stage 4: Reward Model Validation

- [ ] Held-out test set prepared
- [ ] Validation accuracy measured: _____ (target ≥70%)
- [ ] Overfitting checked:
  - [ ] Train/val gap: _____ (target <10%)
- [ ] Edge case testing completed
- [ ] Reward consistency validated
- [ ] Failure modes documented
- [ ] Systematic biases analyzed
- [ ] Final reward model checkpoint saved

### Stage 5: RL Fine-tuning

- [ ] RL algorithm selected (PPO, A2C, etc.)
- [ ] Hyperparameters configured (see config template below)
- [ ] Policy initialization (from SFT model)
- [ ] Reward model frozen and loaded
- [ ] Training loop implemented
- [ ] Logging configured (W&B, TensorBoard)
- [ ] Checkpoint saving strategy defined
- [ ] RL training started
- [ ] Training metrics monitored:
  - [ ] KL divergence: _____ (target ≤0.1)
  - [ ] Entropy: _____ (target 0.5-2.0)
  - [ ] Average reward (trending up)
  - [ ] Policy loss (decreasing)
- [ ] Best checkpoint identified
- [ ] Training logs saved

### Stage 6: Iterative Training

- [ ] Current iteration metrics recorded
- [ ] Weaknesses identified from evaluation
- [ ] Next iteration strategy decided:
  - [ ] New preference data
  - [ ] Reward model retraining
  - [ ] Hyperparameter adjustment
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
  - [ ] Reward model scores on test set: _____
  - [ ] Human eval score: _____ /10
- [ ] Quality thresholds verified:
  - [ ] Final KL divergence: _____ (≤0.1)
  - [ ] Reward accuracy maintained: _____ (≥70%)
- [ ] Reward interpretability analyzed
- [ ] Evaluation report written
- [ ] Deployment decision made

---

## Configuration Templates

### SRF Training Configuration (YAML)

```yaml
# srf_config.yaml
model:
  base_model: "meta-llama/Llama-2-7b-hf"  # Path or HF model ID
  sft_checkpoint: "checkpoints/sft_baseline"
  reward_model_type: "shared"  # "shared" or "separate"

data:
  train_file: "data/preference_pairs_train.jsonl"
  validation_file: "data/preference_pairs_val.jsonl"
  max_prompt_length: 512
  max_response_length: 1024

reward_training:
  learning_rate: 1.0e-5
  batch_size: 8
  max_epochs: 3
  loss_function: "binary_cross_entropy"
  optimizer: "adamw"
  weight_decay: 0.01
  warmup_ratio: 0.1

rl_training:
  algorithm: "PPO"  # PPO, A2C, etc.
  learning_rate: 1.0e-6
  kl_penalty: 0.1  # KL constraint strength
  entropy_bonus: 0.01  # Maintain diversity
  reward_scale: 1.0
  batch_size: 4
  mini_batch_size: 1
  gradient_accumulation_steps: 4
  max_steps: 1000
  ppo_epochs: 4  # PPO-specific
  clip_range: 0.2  # PPO-specific

constraints:
  kl_target: 0.1  # Maximum KL divergence
  entropy_min: 0.5  # Minimum entropy
  entropy_max: 2.0  # Maximum entropy
  reward_accuracy_target: 0.70  # Minimum reward model accuracy

compute:
  fp16: true
  device: "cuda"
  num_devices: 8
  gradient_checkpointing: true

logging:
  wandb_project: "srf-alignment"
  wandb_run_name: "srf-exp-001"
  output_dir: "outputs/srf-exp-001"
  log_interval: 10
  save_interval: 100
```

### Reward Model Training Script (Python)

```python
# train_reward_model.py
from pathlib import Path
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer
import torch

def train_reward_model(
    base_model: str,
    train_file: Path,
    val_file: Path,
    output_dir: Path,
    config: dict
):
    """Train reward model on preference pairs.
    
    Args:
        base_model: Base model name or path
        train_file: Training preference pairs (JSONL)
        val_file: Validation preference pairs (JSONL)
        output_dir: Directory for checkpoints
        config: Training configuration dict
    """
    # Load model with classification head
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=1  # Regression for reward scores
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    
    # Load and prepare data
    train_dataset = load_preference_pairs(train_file, tokenizer)
    val_dataset = load_preference_pairs(val_file, tokenizer)
    
    # Configure trainer
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        learning_rate=config["learning_rate"],
        per_device_train_batch_size=config["batch_size"],
        num_train_epochs=config["max_epochs"],
        logging_steps=10,
        evaluation_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        load_best_model_at_end=True,
        metric_for_best_model="accuracy"
    )
    
    # Train
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_reward_accuracy
    )
    
    trainer.train()
    
    # Save best model
    trainer.save_model(str(output_dir / "best_reward_model"))
    
    return trainer.state.best_metric

def compute_reward_accuracy(eval_pred):
    """Compute reward model accuracy."""
    predictions, labels = eval_pred
    predictions = (predictions > 0).astype(int)
    accuracy = (predictions == labels).mean()
    return {"accuracy": accuracy}
```

### RL Fine-tuning Script (Python)

```python
# rl_finetune.py
from pathlib import Path
from trl import PPOTrainer, PPOConfig
from transformers import AutoModelForCausalLM, AutoTokenizer

def rl_finetune(
    policy_model_path: Path,
    reward_model_path: Path,
    prompts_file: Path,
    config: dict
):
    """RL fine-tuning with learned reward model.
    
    Args:
        policy_model_path: Path to SFT model (policy)
        reward_model_path: Path to trained reward model
        prompts_file: Prompts for RL training
        config: RL configuration dict
    """
    # Load models
    policy_model = AutoModelForCausalLM.from_pretrained(str(policy_model_path))
    reward_model = AutoModelForSequenceClassification.from_pretrained(
        str(reward_model_path)
    )
    reward_model.eval()  # Freeze reward model
    
    tokenizer = AutoTokenizer.from_pretrained(str(policy_model_path))
    
    # Configure PPO
    ppo_config = PPOConfig(
        learning_rate=config["learning_rate"],
        kl_penalty=config["kl_penalty"],
        batch_size=config["batch_size"],
        mini_batch_size=config["mini_batch_size"],
        ppo_epochs=config["ppo_epochs"],
        clip_range=config["clip_range"]
    )
    
    # Initialize trainer
    ppo_trainer = PPOTrainer(
        config=ppo_config,
        model=policy_model,
        tokenizer=tokenizer
    )
    
    # Load prompts
    prompts = load_prompts(prompts_file)
    
    # Training loop
    for step, prompt in enumerate(prompts):
        # Generate response
        query_tensors = tokenizer(prompt, return_tensors="pt").input_ids
        response_tensors = ppo_trainer.generate(query_tensors)
        
        # Score with reward model
        full_text = tokenizer.decode(response_tensors[0])
        reward = get_reward(reward_model, full_text, tokenizer)
        
        # PPO update
        stats = ppo_trainer.step(
            queries=query_tensors,
            responses=response_tensors,
            rewards=[reward]
        )
        
        # Monitor metrics
        if step % 10 == 0:
            print(f"Step {step}: KL={stats['kl']:.4f}, "
                  f"Entropy={stats['entropy']:.4f}, "
                  f"Reward={reward:.4f}")
            
            # Early stopping if KL too high
            if stats['kl'] > config["constraints"]["kl_target"]:
                print("⚠️ KL divergence exceeded threshold!")
                break
    
    # Save final model
    ppo_trainer.save_model("outputs/rl_finetuned_model")
```

### Quality Gate Monitoring Script (Python)

```python
# monitor_srf_quality.py
from pathlib import Path
from training_metrics import validate_dpo_pairs
import json

def monitor_quality_gates(
    reward_model_metrics: dict,
    rl_training_metrics: dict,
    config: dict
) -> dict:
    """Monitor SRF quality gates.
    
    Args:
        reward_model_metrics: Reward model accuracy, overfitting metrics
        rl_training_metrics: KL divergence, entropy, reward stats
        config: Configuration with thresholds
        
    Returns:
        Dict with gate status
    """
    gates = {
        "reward_accuracy": {
            "value": reward_model_metrics["val_accuracy"],
            "threshold": config["constraints"]["reward_accuracy_target"],
            "passed": reward_model_metrics["val_accuracy"] >= 
                     config["constraints"]["reward_accuracy_target"]
        },
        "kl_divergence": {
            "value": rl_training_metrics["kl"],
            "threshold": config["constraints"]["kl_target"],
            "passed": rl_training_metrics["kl"] <= 
                     config["constraints"]["kl_target"]
        },
        "entropy": {
            "value": rl_training_metrics["entropy"],
            "range": [config["constraints"]["entropy_min"],
                     config["constraints"]["entropy_max"]],
            "passed": (config["constraints"]["entropy_min"] <= 
                      rl_training_metrics["entropy"] <= 
                      config["constraints"]["entropy_max"])
        }
    }
    
    all_passed = all(g["passed"] for g in gates.values())
    gates["overall"] = all_passed
    
    # Print status
    print("\n" + "="*60)
    print("SRF Quality Gates Status")
    print("="*60)
    for name, gate in gates.items():
        if name == "overall":
            continue
        status = "✅" if gate["passed"] else "❌"
        print(f"{status} {name}: {gate['value']:.4f}")
    print("="*60)
    print(f"Overall: {'✅ PASSED' if all_passed else '❌ FAILED'}")
    print("="*60 + "\n")
    
    return gates
```

---

## Related Documentation

- `workflow.md` - Complete 7-stage pipeline
- `docs/quality-thresholds.md` - Threshold definitions
- `docs/reward-model-training.md` - Reward training details
- `docs/optimization.md` - RL fine-tuning implementation
- SKILL.md - High-level overview
