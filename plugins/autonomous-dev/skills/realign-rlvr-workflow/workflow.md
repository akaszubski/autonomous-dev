# RLVR Workflow: 7-Stage Pipeline

Complete workflow for Reinforcement Learning with Verifiable Rewards from SFT preparation through final evaluation.

## Workflow Overview

```
SFT → Task Design → Verification → Data Generation → RLVR → Iteration → Evaluation
 ↓         ↓            ↓              ↓              ↓         ↓           ↓
Base   Verifiable  Verification   Training       Aligned   Refined    Validated
Model  Tasks       System         Tasks          Model     Model      Model
     (≥80%)      (FP <5%)                    (KL ≤0.1)
```

## Stage 1: SFT Preparation
Same as other workflows - establish baseline model and metrics.
**See**: `docs/sft-preparation.md`

## Stage 2: Verifiable Task Design
**Purpose**: Create tasks with automated verification.

**Process**:
1. Select verifiable domain (coding, math, formal reasoning)
2. Design task format with clear success criteria
3. Implement verification function
4. Validate verifiability score ≥80% using `assess_rlvr_verifiability()`

**Quality Gate**: Verifiability ≥80%

**See**: `docs/verifiable-task-design.md`

## Stage 3: Automated Verification
**Purpose**: Build robust verification system.

**Process**:
1. Implement verification logic (test execution, proof checking)
2. Test on diverse examples
3. Measure false positive/negative rates
4. Ensure false positive <5%

**Quality Gate**: False positive rate <5%, verification reliable

**See**: `docs/automated-verification.md`

## Stage 4: Verifiable Data Generation
**Purpose**: Create diverse training tasks.

**Process**:
1. Generate task prompts
2. Collect ground truth solutions
3. Validate verification coverage
4. Create train/val splits

**Quality Gate**: Task diversity validated, coverage adequate

**See**: `docs/preference-data-generation.md`

## Stage 5: RLVR Optimization
**Purpose**: Train model with verifiable rewards.

**Process**:
1. Configure RL (PPO/A2C)
2. Training loop:
   - Generate solution
   - Verify outcome (reward = pass/fail)
   - Update policy with RL
   - Apply KL penalty
3. Monitor: KL ≤0.1, verification success rate

**Quality Gate**: KL ≤0.1, verification rate improving

**See**: `docs/optimization.md`

## Stage 6: Iterative Training
Refine through multiple passes.
**See**: `docs/iterative-training.md`

## Stage 7: Evaluation & Monitoring
Validate no capability regression, verified task performance improved.
**See**: `docs/evaluation-monitoring.md`

## Decision Tree
```
Stage 2: Verifiability ≥80%? → Yes → Continue
Stage 3: FP <5%? → Yes → Continue
Stage 5: KL ≤0.1? → Yes → Continue
Stage 7: No regression? → Yes → Deploy
```

**See**: `docs/quality-thresholds.md` for complete threshold definitions.
