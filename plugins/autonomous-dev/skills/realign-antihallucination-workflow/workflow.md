# Anti-hallucination Workflow: 7-Stage Pipeline

Complete workflow for anti-hallucination training from SFT preparation through final evaluation.

## Workflow Overview

```
SFT → Factuality Data → Citation Training → Hallucination Detection → Optimization → Iteration → Evaluation
 ↓          ↓                ↓                      ↓                    ↓             ↓           ↓
Base    Factual         Citation              Detection            Aligned       Refined    Validated
Model   Pairs           Model                 System               Model         Model      Model
     (cite ≥85%)     (fact ≥90%)          (halluc <10%)         (KL ≤0.1)
```

## Stage 1: SFT Preparation
Establish baseline model and hallucination rate.
**See**: `docs/sft-preparation.md`

## Stage 2: Factuality Data Collection
**Purpose**: Collect factual data with proper citations.

**Process**:
1. Gather factual claims with sources
2. Create factual/unfactual pairs
3. Validate citation accuracy ≥85%
4. Build knowledge-grounded dataset

**Quality Gate**: Citation accuracy ≥85%, diverse sources

**See**: `docs/factuality-data-collection.md`

## Stage 3: Citation Training
**Purpose**: Train model to cite sources properly.

**Process**:
1. Fine-tune on citation examples
2. Teach source attribution patterns
3. Validate factuality score ≥90%
4. Test on diverse claims

**Quality Gate**: Factuality score ≥90%

**See**: `docs/citation-training.md`

## Stage 4: Hallucination Detection
**Purpose**: Build system to detect unsupported claims.

**Process**:
1. Implement hallucination detection
2. Test on known hallucinations
3. Measure detection rate
4. Ensure hallucination rate <10%

**Quality Gate**: Detection reliable, hallucination rate <10%

**See**: `docs/hallucination-detection.md`

## Stage 5: Optimization
**Purpose**: Train model to reduce hallucinations.

**Process**:
1. Configure training with factuality rewards
2. Apply KL penalty (≤0.1)
3. Monitor factuality improving
4. Track hallucination rate decreasing

**Quality Gate**: KL ≤0.1, factuality improving, hallucination <10%

**See**: `docs/optimization.md`

## Stage 6: Iterative Training
Refine through multiple passes.
**See**: `docs/iterative-training.md`

## Stage 7: Evaluation & Monitoring
Validate factuality improved, no capability regression.
**See**: `docs/evaluation-monitoring.md`

## Decision Tree
```
Stage 2: Citation ≥85%? → Yes → Continue
Stage 3: Factuality ≥90%? → Yes → Continue
Stage 4: Hallucination <10%? → Yes → Continue
Stage 5: KL ≤0.1 & factuality improving? → Yes → Continue
Stage 7: No regression? → Yes → Deploy
```

**See**: `docs/quality-thresholds.md` for complete threshold definitions.
