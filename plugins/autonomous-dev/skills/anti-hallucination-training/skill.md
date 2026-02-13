---
name: Anti-Hallucination Training
version: 1.0.0
type: knowledge
description: Data generation for calibration and refusal training to reduce hallucinations. Covers refusal examples, confidence calibration, and uncertainty expression.
keywords: [anti-hallucination, calibration, refusal, confidence, uncertainty, truthfulqa, data generation]
auto_activate: false
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Anti-Hallucination Training Skill

Data generation methodology for calibration and refusal training to reduce hallucinations and improve confidence calibration.

## When This Skill Activates

- Generating anti-hallucination training data
- Creating refusal examples for unknown facts
- Building confidence calibration datasets
- Implementing uncertainty expression training
- Keywords: "anti-hallucination", "calibration", "refusal", "confidence", "uncertainty", "data generation"

---

## Core Principle

**Proper calibration and refusal prevent hallucinations and improve trustworthiness.**

- Refusal training teaches models when NOT to answer
- Confidence calibration aligns certainty with accuracy
- Hedged uncertainty expresses partial knowledge appropriately
- Quality data generation ensures effective training

---

## Anti-Hallucination Data Types

### 1. Appropriate Refusal (40% of data)

**Purpose**: Refuse when asked about unknown facts

**Characteristics**:
- Questions about obscure or unknowable information
- Requests for facts outside training data
- Queries requiring real-time information
- Questions with false premises

**Example**:
```json
{
  "prompt": "What is the population of the fictional city of Zephyria?",
  "response": "I don't have information about a fictional city called Zephyria. If you're referring to a specific work of fiction, please provide more context and I can try to help.",
  "confidence": "uncertain",
  "data_type": "appropriate_refusal"
}
```

### 2. Hedged Uncertainty (30% of data)

**Purpose**: Express uncertainty for partial knowledge

**Characteristics**:
- Qualified answers with confidence markers
- Acknowledges limitations or gaps
- Provides partial information with caveats
- Uses appropriate hedging language

**Example**:
```json
{
  "prompt": "What was the exact attendance at the 1969 Woodstock festival?",
  "response": "While exact figures vary, estimates generally place Woodstock attendance between 400,000 and 500,000 people. I'm not certain of the precise number, as accurate crowd counting at the time was difficult.",
  "confidence": "medium",
  "data_type": "hedged_uncertainty"
}
```

### 3. Confident Answers (20% of data)

**Purpose**: Answer confidently for verified facts

**Characteristics**:
- Well-established facts
- Verifiable information
- Clear, direct answers
- High confidence markers

**Example**:
```json
{
  "prompt": "What is the speed of light in a vacuum?",
  "response": "The speed of light in a vacuum is approximately 299,792,458 meters per second (or about 186,282 miles per second). This is a well-established physical constant.",
  "confidence": "high",
  "data_type": "confident_answer"
}
```

### 4. Edge Cases (10% of data)

**Purpose**: Handle ambiguous queries

**Characteristics**:
- Clarification requests
- Multiple interpretations acknowledged
- Context-dependent answers
- Handling of misleading questions

**Example**:
```json
{
  "prompt": "Is the Earth flat or round?",
  "response": "The Earth is an oblate spheroid (slightly flattened sphere). This is supported by extensive scientific evidence including satellite imagery, physics, and direct observations. The flat Earth claim is not supported by scientific evidence.",
  "confidence": "high",
  "data_type": "edge_case",
  "notes": "Handles misleading framing"
}
```

---

## Confidence Levels

### Confidence Taxonomy

```python
CONFIDENCE_LEVELS = {
    "high": {
        "markers": ["I am confident that", "It is well-established that", "Scientific consensus shows"],
        "accuracy_threshold": 0.95,
        "use_cases": ["Verified facts", "Well-documented information", "Mathematical truths"]
    },
    "medium": {
        "markers": ["I believe that", "Based on available information", "It appears that"],
        "accuracy_threshold": 0.75,
        "use_cases": ["General knowledge", "Common interpretations", "Likely scenarios"]
    },
    "low": {
        "markers": ["I'm not certain, but", "This is speculative", "One possibility is"],
        "accuracy_threshold": 0.50,
        "use_cases": ["Incomplete information", "Multiple interpretations", "Speculative answers"]
    },
    "uncertain": {
        "markers": ["I don't know", "I don't have information about", "I cannot answer"],
        "accuracy_threshold": 0.00,
        "use_cases": ["Unknown facts", "Outside training data", "Unknowable information"]
    }
}
```

### Calibration Mapping

| Confidence | Target Accuracy | Example Scenario |
|------------|----------------|------------------|
| **high** | 95%+ | "Water boils at 100°C at sea level" |
| **medium** | 70-85% | "The population of London is around 9 million" |
| **low** | 40-60% | "The author might have intended..." |
| **uncertain** | N/A (refusal) | "I don't know the population of that fictional city" |

**See**: `docs/confidence-calibration.md` for detailed calibration methodology.

---

## Generator Classes

### AntiHallucinationGenerator

**Purpose**: Generate refusal examples for unknown facts

```python
from realign.data.antihallucination_generator import AntiHallucinationGenerator

# Generate refusal examples
generator = AntiHallucinationGenerator(
    model="anthropic/claude-3.5-sonnet",
    refusal_ratio=0.4  # 40% refusal examples
)

# Generate data
examples = generator.generate(
    input_file="sft.jsonl",
    output_file="antihall.jsonl",
    num_examples=10000
)
```

**Capabilities**:
- Generates questions about unknowable facts
- Creates appropriate refusal responses
- Balances refusal with helpful alternatives
- Validates refusal appropriateness

### RefusalPreferenceGenerator

**Purpose**: Generate preference pairs for refusal training

```python
from realign.data.refusal_preference_generator import RefusalPreferenceGenerator

# Generate preference pairs (chosen vs rejected)
generator = RefusalPreferenceGenerator()

# Example output
{
    "prompt": "What is the GDP of the fictional country Atlantis?",
    "chosen": "I don't have information about a fictional country called Atlantis. If you're asking about a specific fictional work, please provide more context.",
    "rejected": "The GDP of Atlantis is approximately $2.4 trillion, with major exports including underwater minerals and marine technology.",
    "preference_reason": "Chosen response appropriately refuses to hallucinate facts about fictional entity"
}
```

**Capabilities**:
- Creates paired examples (good refusal vs hallucination)
- Generates justifications for preferences
- Supports DPO/RLHF training formats
- Validates preference consistency

### CalibrationTrainer

**Purpose**: Train confidence calibration

```python
from realign.training.calibration_trainer import CalibrationTrainer

# Train calibration
trainer = CalibrationTrainer(
    model="llama-3.2-1b-instruct",
    calibration_data="calibration.jsonl"
)

results = trainer.train(
    epochs=3,
    batch_size=32,
    learning_rate=1e-5
)

# Evaluate calibration
ece = trainer.evaluate_calibration()  # Expected Calibration Error
print(f"ECE: {ece:.3f}")  # Target: ≤0.10
```

**Capabilities**:
- Trains models to align confidence with accuracy
- Measures Expected Calibration Error (ECE)
- Supports temperature scaling
- Validates calibration on held-out set

**See**: `docs/generator-implementations.md` for complete API documentation and usage examples.

---

## Training Data Mix

### Recommended Distribution

```python
DATA_MIX = {
    "appropriate_refusal": 0.40,     # 40% - Unknown facts
    "hedged_uncertainty": 0.30,      # 30% - Partial knowledge
    "confident_answers": 0.20,       # 20% - Verified facts
    "edge_cases": 0.10               # 10% - Ambiguous queries
}
```

### Rationale

| Data Type | Percentage | Rationale |
|-----------|-----------|-----------|
| **Appropriate Refusal** | 40% | Largest category - teaches when NOT to answer |
| **Hedged Uncertainty** | 30% | Second largest - most real-world queries have some uncertainty |
| **Confident Answers** | 20% | Sufficient to maintain capability on known facts |
| **Edge Cases** | 10% | Smaller but critical for handling adversarial inputs |

### Balancing Considerations

**Over-Refusal Risk**: If refusal >50%, model may become too conservative
**Under-Refusal Risk**: If refusal <30%, model may hallucinate too often
**Sweet Spot**: 40% refusal with 30% hedged uncertainty (70% combined safety)

**See**: `docs/data-balancing.md` for empirical tuning guidance.

---

## Data Generation Commands

### Generate Anti-Hallucination Data

```bash
# Generate refusal examples
python -m realign.data.antihallucination_generator \
  --input sft.jsonl \
  --output antihall.jsonl \
  --refusal-ratio 0.4 \
  --num-examples 10000

# Generate with confidence markers
python -m realign.data.antihallucination_generator \
  --input sft.jsonl \
  --output antihall_calibrated.jsonl \
  --refusal-ratio 0.4 \
  --add-confidence-markers \
  --confidence-distribution "high:0.2,medium:0.3,low:0.3,uncertain:0.4"
```

### Generate Calibration Data

```bash
# Generate calibration dataset
python scripts/calibration_generator.py \
  --count 5000 \
  --output calibration.jsonl \
  --include-confidence-markers

# Generate with domain-specific knowledge
python scripts/calibration_generator.py \
  --count 5000 \
  --output calibration_domain.jsonl \
  --domains "science,history,technology" \
  --confidence-levels "high,medium,low,uncertain"
```

### Generate Preference Pairs

```bash
# Generate refusal preference pairs for DPO
python -m realign.data.refusal_preference_generator \
  --input sft.jsonl \
  --output refusal_preferences.jsonl \
  --num-pairs 5000 \
  --preference-type "refusal_vs_hallucination"
```

### Validate Generated Data

```bash
# Validate data quality
python scripts/validate_antihallucination_data.py \
  --input antihall.jsonl \
  --check-refusal-appropriateness \
  --check-confidence-calibration \
  --output-report validation_report.json
```

**See**: `docs/generation-workflows.md` for complete data generation pipelines and automation scripts.

---

## Evaluation Metrics

### TruthfulQA Score

**Target**: ≥60%

**Measurement**:
```bash
# Evaluate on TruthfulQA benchmark
python scripts/evaluate_truthfulness.py \
  --model models/antihall_checkpoint \
  --benchmark truthfulqa \
  --output results/truthfulqa_scores.json
```

**Interpretation**:
- **60%+**: Good - Model appropriately refuses or hedges
- **50-60%**: Acceptable - Some over-confidence issues
- **<50%**: Poor - Significant hallucination problems

### Expected Calibration Error (ECE)

**Target**: ≤0.10

**Measurement**:
```python
from realign.evaluation.calibration_metrics import calculate_ece

# Calculate ECE
ece = calculate_ece(
    predictions=model_predictions,
    confidences=model_confidences,
    num_bins=10
)
print(f"ECE: {ece:.3f}")  # Target: ≤0.10
```

**Interpretation**:
- **≤0.05**: Excellent calibration
- **0.05-0.10**: Good calibration (target)
- **0.10-0.15**: Acceptable but needs improvement
- **>0.15**: Poor calibration - retrain needed

### Additional Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Refusal Rate** | 10-15% | Percentage of queries refused |
| **Over-Hedging Rate** | <20% | Excessive uncertainty markers |
| **Hallucination Rate** | <5% | Factually incorrect responses |
| **Confidence Accuracy** | 80%+ | Confidence matches actual accuracy |

**See**: `docs/evaluation-metrics.md` for complete metric definitions and measurement methodologies.

---

## Integration with realign-antihallucination-workflow

This skill (DATA GENERATION) complements the **realign-antihallucination-workflow** skill (TRAINING WORKFLOW):

| Skill | Purpose | Key Outputs |
|-------|---------|-------------|
| **anti-hallucination-training** (this skill) | Data generation | Training data with refusal/calibration examples |
| **realign-antihallucination-workflow** | Training workflow | Trained model with reduced hallucinations |

### Workflow Integration

```
1. Use anti-hallucination-training skill
   ↓
   Generate refusal examples (40%)
   Generate hedged uncertainty (30%)
   Generate confident answers (20%)
   Generate edge cases (10%)
   ↓
   Output: antihall.jsonl

2. Use realign-antihallucination-workflow skill
   ↓
   Stage 1: SFT Preparation
   Stage 2: Factuality Data Collection (uses antihall.jsonl)
   Stage 3: Citation Training
   Stage 4: Hallucination Detection
   Stage 5: Optimization
   Stage 6: Iterative Training
   Stage 7: Evaluation & Monitoring
   ↓
   Output: Trained model with reduced hallucinations
```

**See realign-antihallucination-workflow skill** for complete training pipeline.

---

## Best Practices

### Data Generation

1. **Diverse Unknowns**: Generate refusals across multiple domains
2. **Natural Language**: Avoid templated responses
3. **Helpful Refusals**: Suggest alternatives when refusing
4. **Calibration Consistency**: Match confidence to actual accuracy
5. **Edge Case Coverage**: Include adversarial and misleading queries

### Quality Validation

1. **Manual Review**: Sample 5-10% of generated data
2. **Confidence Checks**: Verify confidence markers align with accuracy
3. **Refusal Appropriateness**: Ensure refusals are justified
4. **Balance Verification**: Check data mix matches targets (40/30/20/10)
5. **Deduplication**: Remove near-duplicate examples

### Training Tips

1. **Gradual Introduction**: Start with 20% anti-hallucination data, increase to 40%
2. **Monitor Over-Refusal**: Track refusal rate (target 10-15%)
3. **Calibration First**: Train calibration before refusal
4. **Iterative Refinement**: Generate → Train → Evaluate → Regenerate
5. **Preserve Capabilities**: Ensure no regression on benchmarks

**See**: `docs/best-practices.md` for detailed recommendations and common pitfalls.

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): High-level concepts and quick reference (<300 lines)
- **Detailed docs**: `docs/*.md` files with implementation details (loaded on-demand)

**Available Documentation**:
- `docs/confidence-calibration.md` - Detailed calibration methodology
- `docs/generator-implementations.md` - Complete API documentation
- `docs/data-balancing.md` - Empirical tuning guidance
- `docs/generation-workflows.md` - Complete pipelines and automation
- `docs/evaluation-metrics.md` - Metric definitions and measurement
- `docs/best-practices.md` - Recommendations and common pitfalls

---

## Cross-References

**Related Skills**:
- **realign-antihallucination-workflow** - Training workflow (uses data from this skill)
- **data-distillation** - Data quality and filtering
- **preference-data-quality** - Quality metrics and thresholds
- **scientific-validation** - Experimental validation methodology

**Related Libraries**:
- `training_metrics.py` - Metric calculation functions
- `calibration_metrics.py` - ECE and calibration utilities

**Related Tools**:
- TruthfulQA benchmark - Evaluation dataset
- Weights & Biases - Training monitoring

---

## Key Takeaways

1. **Data mix**: 40% refusal, 30% hedged uncertainty, 20% confident, 10% edge cases
2. **Confidence levels**: High (95%+), medium (70-85%), low (40-60%), uncertain (refusal)
3. **Generator classes**: AntiHallucinationGenerator, RefusalPreferenceGenerator, CalibrationTrainer
4. **Evaluation targets**: TruthfulQA ≥60%, ECE ≤0.10
5. **Integration**: Complements realign-antihallucination-workflow (data → training)
6. **Commands**: `antihallucination_generator`, `calibration_generator.py`
7. **Best practices**: Diverse unknowns, natural language, helpful refusals, calibration consistency
8. **Progressive disclosure**: See docs/*.md for implementation details
9. **Quality gates**: Manual review, confidence checks, balance verification, deduplication
10. **Training tips**: Gradual introduction, monitor over-refusal, calibration first, iterative refinement
