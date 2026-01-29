# DPO Workflow: 7-Stage Pipeline

Complete workflow for Direct Preference Optimization (DPO) model realignment from SFT preparation through final evaluation.

---

## Workflow Overview

```
SFT Preparation → Preference Data → Model Init → Preference Modeling
       ↓                  ↓              ↓               ↓
   Baseline           Quality        Reference       Reward Model
   Metrics            Gate 1         Model           Accuracy
                   (gap ≥0.15)    (KL calc)        (≥70%)
                                       ↓
                                  DPO Optimization → Iterative Training → Evaluation
                                       ↓                    ↓                ↓
                                   Aligned             Refined          Validated
                                   Model               Model            Model
                                  (KL ≤0.1)         (Improving)      (No regression)
```

**Decision Points**:
- After Stage 2: If preference gap below minimum, return to data generation
- After Stage 5: If KL >0.1, reduce learning rate and retry
- After Stage 7: If capability regression detected, rollback and adjust

---

## Stage 1: SFT Preparation

**Purpose**: Establish baseline model and metrics before DPO training.

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

**Purpose**: Create high-quality preference pairs with clear preference signal.

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

   MIN_GAP = 3/20  # 0.15 preference gap
   metrics = validate_dpo_pairs(
       dpo_path=Path("preference_pairs.jsonl"),
       gap_threshold=MIN_GAP
   )

   if metrics.avg_gap < MIN_GAP:
       # Generate more diverse examples
       pass
   ```
4. Check decontamination (≥0.9) to prevent eval leakage
5. Ensure minimum pair count (≥1000)
6. Handle conflicting preferences (see docs)

**Outputs**:
- Validated preference pairs (JSONL format)
- Quality metrics (gap, decontamination, count)
- Data statistics report

**Quality Gate**: Preference gap ≥0.15, pairs ≥1000, decontamination ≥0.9

**Decision**: If quality gate not met, collect more diverse examples or improve annotation quality.

**Time Estimate**: 3-7 days for data collection and validation

**See**: `docs/preference-data-generation.md` for detailed implementation.

---

## Stage 3: Model Initialization

**Purpose**: Prepare reference and policy models for DPO training.

**Inputs**:
- Base SFT model checkpoint
- DPO training configuration

**Process**:
1. Load base SFT model as reference model (frozen)
2. Clone reference model as policy model (trainable)
3. Initialize DPO trainer with KL divergence constraint
4. Verify model architectures match
5. Calculate initial KL divergence (should be ~0)

**Outputs**:
- Reference model (frozen)
- Policy model (initialized)
- DPO trainer configuration

**Quality Gate**: Models initialized successfully, initial KL divergence ≈0

**Time Estimate**: 1-2 hours for setup

**See**: `docs/model-initialization.md` for detailed implementation.

---

## Stage 4: Preference Modeling

**Purpose**: Train or validate reward model to predict preferences.

**Inputs**:
- Preference pairs
- Base model or separate reward model

**Process**:
1. Split preference data (80% train, 20% validation)
2. Train reward model to predict chosen over rejected
3. Validate reward model accuracy on held-out set
4. Check for overfitting (train/val accuracy gap)
5. Optional: Use reward model to filter low-quality pairs

**Outputs**:
- Trained reward model
- Accuracy metrics (train and validation)
- Filtered preference pairs (if applicable)

**Quality Gate**: Reward model accuracy ≥70% on validation set

**Decision**: If accuracy <70%, improve data quality or model capacity.

**Time Estimate**: 1-2 days for training and validation

**See**: `docs/preference-modeling.md` for detailed implementation.

---

## Stage 5: DPO Optimization

**Purpose**: Train policy model to optimize preferences while maintaining KL constraint.

**Inputs**:
- Policy model (trainable)
- Reference model (frozen)
- Validated preference pairs
- DPO hyperparameters

**Process**:
1. Configure DPO training:
   ```python
   dpo_config = {
       "learning_rate": 1e-6,
       "beta": 0.1,  # KL penalty strength
       "batch_size": 4,
       "max_steps": 1000,
       "kl_target": 0.1,  # Maximum KL divergence
   }
   ```
2. Run DPO training loop
3. Monitor training metrics:
   - Preference accuracy (increasing)
   - KL divergence (should stay ≤0.1)
   - Training loss (decreasing)
4. Save checkpoints regularly
5. Evaluate on validation set

**Outputs**:
- DPO-trained policy model
- Training metrics and logs
- Model checkpoints

**Quality Gate**: KL divergence ≤0.1, preference gap maintained ≥0.15

**Decision**: If KL >0.1, reduce learning rate or increase beta (KL penalty).

**Time Estimate**: 2-5 days depending on model size and data volume

**Performance Note**: Batch size and hardware selection dramatically impact training speed. M4 Max is 5.1x faster than M3 Ultra for MLX inference. Use batch_size=32 on M4 Max, batch_size=4 on M3 Ultra. See `docs/performance-optimization.md` for hardware-specific configuration.

**See**: `docs/dpo-optimization.md` for detailed implementation.

---

## Stage 6: Iterative Training

**Purpose**: Refine model through multiple DPO passes with improved data.

**Inputs**:
- DPO-trained model from Stage 5
- New preference pairs (optional)
- Capability metrics

**Process**:
1. Evaluate current model on benchmarks
2. Identify weaknesses or capability gaps
3. Collect additional preference pairs targeting weaknesses
4. Run another DPO training pass (Stage 5)
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
- Final DPO model
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
   - Qualitative response analysis
4. Check final quality thresholds:
   - KL divergence ≤0.1
   - Preference gap ≥0.15 on held-out pairs
   - No eval contamination
5. Document all results

**Outputs**:
- Final validated model
- Evaluation report
- Deployment decision

**Success Criteria**:
- ✅ All quality thresholds met
- ✅ No capability regression (≥95% retention)
- ✅ Alignment improved vs baseline
- ✅ Human evaluation positive

**Decision**:
- If success: Deploy model
- If capability regression: Rollback, adjust hyperparameters, retry from Stage 5
- If alignment not improved: Review data quality, consider alternative approaches

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
Stage 3: Model Initialization
         ↓
Stage 4: Preference Modeling
         ↓
      Accuracy ≥70%?
         ↓ Yes
Stage 5: DPO Optimization
         ↓
      KL ≤0.1?
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
| Insufficient data | 2 | Collect more pairs (target ≥1000) |
| Poor reward accuracy | 4 | Improve data quality or model capacity |
| High KL divergence | 5 | Reduce learning rate, increase beta |
| Capability regression | 7 | Rollback, smaller learning rate, more gradual training |
| No alignment improvement | 7 | Review preference data quality, consider alternative methods |

---

## Time Budget Planning

**Minimum viable DPO** (single iteration):
- Total: 1-2 weeks
- Assumes: Small model, high-quality existing data

**Production DPO** (multiple iterations):
- Total: 4-8 weeks
- Includes: Data collection, multiple refinement passes, thorough evaluation

**Large-scale DPO** (research/frontier models):
- Total: 2-6 months
- Includes: Extensive data collection, distributed training, comprehensive evaluation

---

## Next Steps

After completing the workflow:

1. **Deploy** validated model to production
2. **Monitor** production performance and user feedback
3. **Collect** new preference data from production interactions
4. **Iterate** with new data for continuous improvement
5. **Document** lessons learned and best practices

---

## Related Documentation

- `templates.md` - Configuration templates and checklists
- `docs/quality-thresholds.md` - Detailed threshold definitions
- `docs/capability-assessment.md` - Regression detection methods
- SKILL.md - High-level skill overview
