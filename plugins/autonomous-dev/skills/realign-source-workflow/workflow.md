# Source Attribution Workflow: 7-Stage Pipeline

Complete workflow for source attribution training from SFT preparation through final evaluation.

## Workflow Overview

```
SFT → Source Data → Citation Training → Attribution Verification → Optimization → Iteration → Evaluation
 ↓         ↓              ↓                     ↓                      ↓            ↓           ↓
Base   Source         Citation            Verification            Aligned      Refined    Validated
Model  Pairs          Model               System                  Model        Model      Model
    (retrieval      (cite ≥90%)        (coverage ≥80%)         (KL ≤0.1)
     ≥85%)
```

## Stage 1: SFT Preparation
Establish baseline model and citation metrics.
**See**: `docs/sft-preparation.md`

## Stage 2: Source Data Preparation
**Purpose**: Prepare source-grounded data with proper citations.

**Process**:
1. Index source databases
2. Create claim-source pairs
3. Validate retrieval precision ≥85%
4. Build citation examples

**Quality Gate**: Retrieval precision ≥85%, diverse sources

**See**: `docs/source-data-preparation.md`

## Stage 3: Citation Training
**Purpose**: Train model to cite sources properly.

**Process**:
1. Fine-tune on citation examples
2. Teach attribution patterns
3. Validate citation accuracy ≥90%
4. Test diverse claim types

**Quality Gate**: Citation accuracy ≥90%

**See**: `docs/citation-training.md`

## Stage 4: Attribution Verification
**Purpose**: Build system to verify source attribution.

**Process**:
1. Implement attribution checking
2. Measure coverage (claims with sources)
3. Validate attribution accuracy
4. Ensure coverage ≥80%

**Quality Gate**: Attribution coverage ≥80%, verification reliable

**See**: `docs/attribution-verification.md`

## Stage 5: Optimization
**Purpose**: Train model to improve source attribution.

**Process**:
1. Configure training with citation rewards
2. Apply KL penalty (≤0.1)
3. Monitor citation accuracy and coverage
4. Track source retrieval precision

**Quality Gate**: KL ≤0.1, citation ≥90%, coverage ≥80%

**See**: `docs/optimization.md`

## Stage 6: Iterative Training
Refine through multiple passes.
**See**: `docs/iterative-training.md`

## Stage 7: Evaluation & Monitoring
Validate source attribution improved, no capability regression.
**See**: `docs/evaluation-monitoring.md`

## Decision Tree
```
Stage 2: Retrieval ≥85%? → Yes → Continue
Stage 3: Citation ≥90%? → Yes → Continue
Stage 4: Coverage ≥80%? → Yes → Continue
Stage 5: KL ≤0.1 & metrics maintained? → Yes → Continue
Stage 7: No regression? → Yes → Deploy
```

**See**: `docs/quality-thresholds.md` for complete threshold definitions.
