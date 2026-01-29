# Persona Workflow: 7-Stage Pipeline

Complete workflow for persona consistency training from SFT preparation through final evaluation.

## Workflow Overview

```
SFT → Persona Definition → Consistency Data → Persona Evaluation → Optimization → Iteration → Evaluation
 ↓           ↓                   ↓                   ↓                  ↓            ↓           ↓
Base     Character          Persona            Evaluation          Aligned      Refined    Validated
Model    Profile            Pairs              System              Model        Model      Model
      (traits clear)     (consist ≥85%)    (adherence ≥90%)     (KL ≤0.1)
```

## Stage 1: SFT Preparation
Establish baseline model.
**See**: `docs/sft-preparation.md`

## Stage 2: Persona Definition
**Purpose**: Define clear character profile and core traits.

**Process**:
1. Identify 5-10 core personality traits
2. Define communication style
3. Specify behavioral patterns
4. Document example interactions

**Quality Gate**: Traits clearly defined, measurable

**See**: `docs/persona-definition.md`

## Stage 3: Consistency Data Generation
**Purpose**: Create data demonstrating persona consistency.

**Process**:
1. Generate diverse scenarios
2. Create consistent persona responses
3. Contrast with inconsistent examples
4. Validate consistency score ≥85%

**Quality Gate**: Consistency ≥85%, trait coverage complete

**See**: `docs/consistency-data-generation.md`

## Stage 4: Persona Evaluation
**Purpose**: Build system to measure trait adherence.

**Process**:
1. Implement trait detection
2. Measure style consistency
3. Validate adherence ≥90%
4. Test across contexts

**Quality Gate**: Trait adherence ≥90%, style variance <15%

**See**: `docs/persona-evaluation.md`

## Stage 5: Optimization
**Purpose**: Train model to maintain persona consistency.

**Process**:
1. Configure training with consistency rewards
2. Apply KL penalty (≤0.1)
3. Monitor consistency and trait adherence
4. Track style variance

**Quality Gate**: KL ≤0.1, consistency ≥85%, adherence ≥90%

**See**: `docs/optimization.md`

## Stage 6: Iterative Training
Refine through multiple passes.
**See**: `docs/iterative-training.md`

## Stage 7: Evaluation & Monitoring
Validate persona consistency improved, no capability regression.
**See**: `docs/evaluation-monitoring.md`

## Decision Tree
```
Stage 2: Traits defined? → Yes → Continue
Stage 3: Consistency ≥85%? → Yes → Continue
Stage 4: Adherence ≥90%? → Yes → Continue
Stage 5: KL ≤0.1 & consistency maintained? → Yes → Continue
Stage 7: No regression? → Yes → Deploy
```

**See**: `docs/quality-thresholds.md` for complete threshold definitions.
