# SRF Workflow: 7-Stage Pipeline

Complete workflow for Supervised Reward Fine-tuning (SRF) model realignment from SFT preparation through final evaluation.

---

## Workflow Overview

```
SFT Preparation → Preference Data → Reward Training → Reward Validation
       ↓                  ↓              ↓                  ↓
   Baseline           Quality        Reward Model       Validated
   Metrics            Gate 1         (Accuracy)          Reward
                   (gap ≥0.15)        (≥70%)           (No overfit)
                                       ↓
                                  RL Fine-tuning → Iterative Training → Evaluation
                                       ↓                    ↓                ↓
                                   Aligned              Refined          Validated
                                   Model                Model            Model
                              (KL ≤0.1, entropy      (Improving)      (No regression)
                               0.5-2.0)
```

**Decision Points**:
- After Stage 2: If preference gap <0.15, return to data generation
- After Stage 4: If reward validation fails, improve data or model
- After Stage 5: If KL >0.1 or entropy out of range, adjust hyperparameters
- After Stage 7: If capability regression detected, rollback and adjust

---

## Stage 1: SFT Preparation

**Purpose**: Establish baseline model and metrics before SRF training.

**Inputs**:
- Pre-trained base model
- SFT training data
- Evaluation benchmarks

**Process**:
1. Train base model on SFT data
2. Validate SFT performance on held-out set
3. Run capability benchmarks (MMLU, HumanEval, etc.)
4. Record baseline metrics for regression detection
5. Save model checkpoint as reference

**Outputs**:
- Base SFT model checkpoint
- Baseline capability metrics
- Evaluation results

**Quality Gate**: SFT model meets minimum performance thresholds on benchmarks.

**Time Estimate**: 1-3 days depending on model size

**See**: `docs/sft-preparation.md` for detailed implementation.

---

## Stage 2: Preference Data Generation

**Purpose**: Create high-quality preference pairs for reward model training.

**Inputs**:
- Prompts/instructions
- Base model for response generation
- Human annotators or reward model

**Process**:
1. Generate multiple responses per prompt
2. Collect preference annotations (chosen vs rejected)
3. Validate preference pairs using `training_metrics.py`:
   ```python
   from pathlib import Path
   from training_metrics import validate_dpo_pairs

   metrics = validate_dpo_pairs(
       dpo_path=Path("preference_pairs.jsonl"),
       gap_threshold=0.15
   )

   if metrics.avg_gap < 0.15:
       # Generate more diverse examples
       pass
   ```
4. Check decontamination (≥0.9) to prevent eval leakage
5. Ensure minimum pair count (≥1000)

**Outputs**:
- Validated preference pairs (JSONL format)
- Quality metrics (gap, decontamination, count)
- Data statistics report

**Quality Gate**: Preference gap ≥0.15, pairs ≥1000, decontamination ≥0.9

**Decision**: If quality gate not met, collect more diverse examples or improve annotation quality.

**Time Estimate**: 3-7 days for data collection and validation

**See**: `docs/preference-data-generation.md` for detailed implementation.

---

## Stage 3: Reward Model Training

**Purpose**: Train reward model to predict preference scores.

**Inputs**:
- Validated preference pairs
- Base model (or separate architecture for reward head)
- Training configuration

**Process**:
1. Prepare reward model architecture:
   - Option A: Add reward head to base model
   - Option B: Separate smaller model for efficiency
2. Split data (80% train, 20% validation)
3. Train reward model using binary classification:
   ```python
   reward_config = {
       "learning_rate": 1e-5,
       "batch_size": 8,
       "max_epochs": 3,
       "loss": "binary_cross_entropy"
   }
   ```
4. Monitor training metrics:
   - Training accuracy (increasing)
   - Validation accuracy (target ≥70%)
   - Loss convergence
5. Save best checkpoint based on validation accuracy

**Outputs**:
- Trained reward model checkpoint
- Training and validation accuracy metrics
- Loss curves and learning progress

**Quality Gate**: Training accuracy ≥70%, validation accuracy ≥70%

**Decision**: If accuracy <70%, improve data quality or increase model capacity.

**Time Estimate**: 1-2 days for training

**See**: `docs/reward-model-training.md` for detailed implementation.

---

## Stage 4: Reward Model Validation

**Purpose**: Validate reward model generalization and prevent overfitting.

**Inputs**:
- Trained reward model
- Held-out validation set
- Test preference pairs

**Process**:
1. Evaluate on held-out validation set
2. Check for overfitting:
   ```python
   train_val_gap = train_accuracy - val_accuracy
   if train_val_gap > 0.10:
       print("⚠️ Overfitting detected")
   ```
3. Test on diverse examples:
   - Edge cases
   - Out-of-distribution prompts
   - Adversarial examples
4. Analyze failure modes:
   - Which preference types are hard?
   - Are there systematic biases?
5. Validate reward consistency:
   - Same prompt → similar rewards
   - Clear preferences → large reward gaps

**Outputs**:
- Validation accuracy report
- Overfitting analysis
- Failure mode documentation
- Reward consistency metrics

**Quality Gate**: Val accuracy ≥70%, train/val gap <10%, reward consistency validated

**Decision**:
- If overfitting: Add regularization, more diverse data
- If low accuracy: Review data quality, increase capacity
- If inconsistent: Improve annotation guidelines

**Time Estimate**: 1-2 days for validation

**See**: `docs/reward-model-validation.md` for detailed implementation.

---

## Stage 5: RL Fine-tuning (Optimization)

**Purpose**: Fine-tune policy model using learned reward model with RL.

**Inputs**:
- Base SFT model (policy to be trained)
- Trained reward model (frozen)
- RL configuration (PPO/A2C/etc.)

**Process**:
1. Configure RL fine-tuning:
   ```python
   rl_config = {
       "algorithm": "PPO",
       "learning_rate": 1e-6,
       "kl_penalty": 0.1,  # KL constraint strength
       "entropy_bonus": 0.01,  # Maintain diversity
       "reward_scale": 1.0,
       "batch_size": 4,
       "max_steps": 1000
   }
   ```
2. Run RL training loop:
   - Generate responses from policy
   - Score with reward model
   - Update policy with RL algorithm
   - Apply KL penalty relative to base model
3. Monitor critical metrics:
   - KL divergence (target ≤0.1)
   - Entropy (target 0.5-2.0)
   - Average reward (increasing)
   - Policy loss (decreasing)
4. Save checkpoints regularly
5. Early stopping if KL exceeds threshold

**Outputs**:
- RL-trained policy model
- Training metrics and logs
- KL divergence trajectory
- Entropy trajectory

**Quality Gate**: KL divergence ≤0.1, entropy 0.5-2.0, reward improving

**Decision**:
- If KL >0.1: Reduce learning rate, increase KL penalty
- If entropy <0.5: Reduce reward scale, increase entropy bonus
- If entropy >2.0: Increase reward scale, reduce entropy bonus

**Time Estimate**: 2-5 days depending on model size

**See**: `docs/optimization.md` for detailed implementation.

---

## Stage 6: Iterative Training

**Purpose**: Refine model through multiple RL passes with improved data or rewards.

**Inputs**:
- RL-trained model from Stage 5
- Capability metrics
- Optional: New preference data

**Process**:
1. Evaluate current model on benchmarks
2. Identify weaknesses or capability gaps
3. Options for next iteration:
   - Collect additional preference data
   - Retrain reward model on combined data
   - Adjust RL hyperparameters
   - Fine-tune on specific domains
4. Run another RL training pass (Stage 5)
5. Compare metrics to previous iteration
6. Repeat until convergence or time budget exhausted

**Outputs**:
- Refined model checkpoint
- Iteration metrics comparison
- Convergence analysis

**Quality Gate**: Metrics improving or stable (no regression)

**Decision**:
- If improving: Continue iterations
- If degrading: Rollback to previous checkpoint
- If stable: Proceed to evaluation

**Time Estimate**: 1-3 weeks for multiple iterations

**See**: `docs/iterative-training.md` for detailed implementation.

---

## Stage 7: Evaluation & Monitoring

**Purpose**: Validate final model meets all quality thresholds without capability regression.

**Inputs**:
- Final SRF model
- Baseline metrics from Stage 1
- Evaluation benchmarks

**Process**:
1. Run capability benchmarks (MMLU, HumanEval, etc.)
2. Compare to baseline metrics:
   ```python
   capability_retention = (final_score / baseline_score) * 100

   if capability_retention < 95:
       print("⚠️ Capability regression detected!")
       # Rollback and adjust hyperparameters
   ```
3. Evaluate alignment improvements:
   - Human evaluation on preference tasks
   - Win rate vs baseline model
   - Reward model scores on test set
4. Check final quality thresholds:
   - Final KL divergence ≤0.1
   - Reward model accuracy maintained
   - No eval contamination
5. Analyze reward model interpretability:
   - Which behaviors are rewarded?
   - Are rewards consistent with goals?

**Outputs**:
- Final validated model
- Evaluation report
- Reward analysis
- Deployment decision

**Success Criteria**:
- ✅ All quality thresholds met
- ✅ No capability regression (≥95% retention)
- ✅ Alignment improved vs baseline
- ✅ Reward model interpretable
- ✅ Human evaluation positive

**Decision**:
- If success: Deploy model
- If capability regression: Rollback, adjust hyperparameters, retry from Stage 5
- If alignment not improved: Review reward model, consider data quality

**Time Estimate**: 2-4 days for comprehensive evaluation

**See**: `docs/evaluation-monitoring.md` for detailed implementation.

---

## Workflow Decision Tree

```
Start → Stage 1: SFT Preparation
         ↓
      Baseline OK?
         ↓ Yes
Stage 2: Preference Data Generation
         ↓
      Gap ≥0.15 & Pairs ≥1000?
         ↓ Yes
Stage 3: Reward Model Training
         ↓
      Accuracy ≥70%?
         ↓ Yes
Stage 4: Reward Model Validation
         ↓
      No overfitting & Consistent?
         ↓ Yes
Stage 5: RL Fine-tuning
         ↓
      KL ≤0.1 & Entropy 0.5-2.0?
         ↓ Yes
Stage 6: Iterative Training
         ↓
      Improving?
         ↓ Yes
Stage 7: Evaluation & Monitoring
         ↓
      No regression & Alignment improved?
         ↓ Yes
      ✅ DEPLOY

   ❌ No at any stage → Review & Iterate
```

---

## Common Failure Modes

| Failure | Stage | Solution |
|---------|-------|----------|
| Weak baseline | 1 | Improve SFT data quality |
| Low preference gap | 2 | Generate more diverse responses |
| Poor reward accuracy | 3 | Improve data quality or model capacity |
| Reward overfitting | 4 | Regularization, more diverse data |
| High KL divergence | 5 | Reduce learning rate, increase KL penalty |
| Entropy collapse | 5 | Reduce reward scale, increase entropy bonus |
| Capability regression | 7 | Rollback, smaller learning rate, adjust reward scale |

---

## Time Budget Planning

**Minimum viable SRF** (single iteration):
- Total: 1-2 weeks
- Assumes: Small model, high-quality existing data

**Production SRF** (multiple iterations):
- Total: 4-8 weeks
- Includes: Data collection, reward training, multiple RL passes, thorough evaluation

**Large-scale SRF** (research/frontier models):
- Total: 2-6 months
- Includes: Extensive data, distributed training, comprehensive evaluation

---

## Next Steps

After completing the workflow:

1. **Deploy** validated model to production
2. **Monitor** production performance and user feedback
3. **Analyze** reward model predictions for insights
4. **Collect** new preference data from production
5. **Iterate** with new data for continuous improvement

---

## Related Documentation

- `templates.md` - Configuration templates and checklists
- `docs/quality-thresholds.md` - Detailed threshold definitions
- `docs/capability-assessment.md` - Regression detection methods
- SKILL.md - High-level skill overview
