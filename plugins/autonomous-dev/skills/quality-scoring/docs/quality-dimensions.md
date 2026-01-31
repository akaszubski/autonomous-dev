# Quality Dimensions

Six quality dimensions for comprehensive training data assessment. Each dimension captures a specific aspect of data quality critical for effective model training.

---

## Overview

Quality dimensions provide orthogonal measurements of training data quality. Combining multiple dimensions gives a comprehensive assessment that single metrics miss.

---

## Dimension Comparison

| Dimension | Range | Measures | Critical For |
|-----------|-------|----------|--------------|
| **IFD Score** | 0.0-1.0 | Instruction-following difficulty | All training types |
| **Factuality** | 0.0-1.0 | Verifiable accuracy | Factual domains |
| **Reasoning** | 0.0-1.0 | Logical coherence | Math, code, logic |
| **Diversity** | 0.0-1.0 | Coverage breadth | Dataset-level quality |
| **Domain** | 0.0-1.0 | Specialized knowledge | Domain-specific training |
| **LLM Quality** | 1-10 | Overall response quality | General assessment |

---

## 1. IFD Score (Instruction-Following Difficulty)

**Range**: 0.0-1.0 (higher = more challenging)

**Definition**: Ratio of response perplexity to conditional response perplexity

**Formula**:
```
IFD = PPL(response) / PPL(response | instruction)

Where:
- PPL(response) = perplexity of response alone
- PPL(response | instruction) = perplexity of response given instruction
```

**Interpretation**:
- **0.0-0.3**: Easy (simple instructions, straightforward responses)
- **0.3-0.6**: Medium (moderate complexity)
- **0.6-0.8**: Hard (complex instructions, nuanced responses)
- **0.8-1.0**: Very hard (specialized knowledge, multi-step reasoning)

**Calculation Example**:
```python
from training_metrics import calculate_ifd_score

ifd = calculate_ifd_score(
    instruction="Explain the Riemann hypothesis",
    response="The Riemann hypothesis states that all non-trivial zeros..."
)
# Returns: 0.75 (high difficulty)
```

**Use Cases**:
- **SFT**: IFD ≥0.3 (avoid trivial examples)
- **DPO chosen**: IFD ≥0.5 (challenging, high-quality)
- **DPO rejected**: Any IFD (quality matters, not difficulty)
- **RLVR**: IFD ≥0.5 (complex reasoning required)

**Why It Matters**:
- Higher IFD = more informative training examples
- Models learn more from challenging data
- Prevents overfitting on simple patterns

**Limitations**:
- Perplexity-based (depends on reference model)
- May not capture all difficulty aspects
- Requires good reference model

---

## 2. Factuality Score

**Range**: 0.0-1.0 (higher = more factual)

**Definition**: Proportion of verifiable claims that are accurate

**Calculation Method**:
```python
from training_metrics import assess_factuality

factuality = assess_factuality({
    "response": "Water boils at 100°C at sea level. Mars has two moons.",
    "domain": "science"
})
# Returns: {
#   "factuality_score": 1.0,
#   "claims": 2,
#   "verified": 2,
#   "false_claims": 0
# }
```

**Claim Detection**:
1. Extract verifiable statements from response
2. Check against knowledge base or web sources
3. Score: verified_claims / total_claims

**Thresholds**:
- **≥0.9**: Highly factual (science, history, medicine)
- **≥0.8**: Acceptable (general knowledge)
- **≥0.7**: Borderline (creative domains)
- **<0.7**: Unreliable (exclude from training)

**Use Cases**:
- Factual domains (science, medicine, law)
- Preventing hallucination in training data
- DPO rejected examples (factuality <0.5)

**Detection Methods**:
- **Knowledge base lookup** - Wikipedia, Wikidata
- **Web search verification** - Google, Bing fact-check
- **LLM-based assessment** - GPT-4, Claude for complex claims

**Example (Low Factuality)**:
```python
response = "The moon is made of cheese. It orbits Earth every 27 days."
factuality = assess_factuality({"response": response})
# Returns: 0.5 (1 true, 1 false out of 2 claims)
```

**Why It Matters**:
- Training on false information degrades model reliability
- Critical for domains requiring accuracy
- Prevents propagation of misinformation

---

## 3. Reasoning Score

**Range**: 0.0-1.0 (higher = better reasoning)

**Definition**: Quality of step-by-step logical reasoning

**Evaluation Criteria**:
1. **Logical coherence** - Steps follow logically
2. **Completeness** - All necessary steps present
3. **Correctness** - Each step is valid
4. **Clarity** - Reasoning is explained clearly

**Calculation Example**:
```python
from training_metrics import assess_reasoning

reasoning = assess_reasoning({
    "instruction": "Solve: If 2x + 5 = 15, what is x?",
    "response": """
    Step 1: Subtract 5 from both sides: 2x = 10
    Step 2: Divide both sides by 2: x = 5
    Step 3: Verify: 2(5) + 5 = 15 ✓
    """
})
# Returns: {
#   "reasoning_score": 0.95,
#   "logical_coherence": 1.0,
#   "completeness": 0.95,
#   "correctness": 1.0,
#   "clarity": 0.90
# }
```

**Thresholds**:
- **≥0.9**: Excellent reasoning (math, code, logic)
- **≥0.8**: Good reasoning (general problem-solving)
- **≥0.7**: Acceptable (simple tasks)
- **<0.7**: Poor reasoning (exclude)

**Use Cases**:
- **Math reasoning** - Chain-of-thought training
- **Code generation** - Algorithmic problem-solving
- **Logic puzzles** - Multi-step inference
- **RLVR** - Verifiable reasoning traces

**Reasoning Patterns**:
```python
# Good reasoning pattern
"""
1. Identify the problem
2. Break into sub-problems
3. Solve each sub-problem
4. Combine solutions
5. Verify result
"""

# Poor reasoning pattern
"""
The answer is X.
(No explanation or steps)
"""
```

**Why It Matters**:
- Strong reasoning enables model to generalize
- Critical for math, code, and logic domains
- Enables RLVR training (verifiable rewards)

---

## 4. Diversity Score

**Range**: 0.0-1.0 (higher = more diverse)

**Definition**: Dataset-level metric for topic and style coverage

**Calculation Method**:
```python
from training_metrics import calculate_diversity

diversity = calculate_diversity(dataset=[
    {"instruction": "Explain photosynthesis", "response": "..."},
    {"instruction": "Write a haiku", "response": "..."},
    {"instruction": "Debug this code", "response": "..."},
    # ... more examples
])
# Returns: {
#   "diversity_score": 0.75,
#   "topic_diversity": 0.80,
#   "style_diversity": 0.70,
#   "unique_topics": 45
# }
```

**Components**:
1. **Topic diversity** - Range of subjects covered
2. **Style diversity** - Variety of response formats
3. **Vocabulary diversity** - Unique word usage
4. **Difficulty diversity** - Range of IFD scores

**Measurement Approaches**:
- **Embedding clustering** - Semantic space coverage
- **N-gram analysis** - Vocabulary richness
- **Domain classification** - Distribution across domains

**Thresholds**:
- **≥0.8**: Highly diverse (production datasets)
- **≥0.6**: Moderate diversity (domain-specific)
- **≥0.4**: Low diversity (specialized tasks)
- **<0.4**: Homogeneous (risk of overfitting)

**Example (Low Diversity)**:
```python
# All examples are nearly identical
dataset = [
    {"instruction": "Add 1+1", "response": "2"},
    {"instruction": "Add 2+2", "response": "4"},
    {"instruction": "Add 3+3", "response": "6"},
]
diversity = calculate_diversity(dataset)
# Returns: 0.15 (very low diversity)
```

**Why It Matters**:
- Prevents overfitting to narrow patterns
- Ensures broad capability coverage
- Critical for general-purpose models

---

## 5. Domain Score

**Range**: 0.0-1.0 (higher = more domain-relevant)

**Definition**: Relevance to target domain (math, code, medicine, etc.)

**Calculation Example**:
```python
from training_metrics import assess_domain_relevance

domain_score = assess_domain_relevance(
    example={
        "instruction": "Implement binary search in Python",
        "response": "def binary_search(arr, target): ..."
    },
    target_domain="coding"
)
# Returns: {
#   "domain_score": 0.95,
#   "domain_confidence": 0.98,
#   "detected_domain": "coding"
# }
```

**Domain Categories**:
- **Math** - Equations, proofs, word problems
- **Code** - Programming, algorithms, debugging
- **Science** - Physics, chemistry, biology
- **Medicine** - Clinical, pharmacology, anatomy
- **Law** - Legal reasoning, case analysis
- **Creative** - Writing, art, design
- **General** - Mixed or unspecified

**Use Cases**:
- **Domain-specific training** - Curate high-relevance data
- **Mixed datasets** - Balance domain distribution
- **Quality filtering** - Exclude off-topic examples

**Thresholds**:
- **≥0.9**: Highly relevant (domain-specific training)
- **≥0.7**: Relevant (acceptable for general training)
- **≥0.5**: Marginally relevant (review manually)
- **<0.5**: Irrelevant (exclude)

**Detection Method**:
```python
# Domain classifier (trained on labeled data)
from training_metrics.classifiers import DomainClassifier

classifier = DomainClassifier()
domains = classifier.classify_batch([
    "Solve for x: 2x + 5 = 15",
    "Write a function to reverse a list",
    "Explain photosynthesis"
])
# Returns: ["math", "coding", "science"]
```

**Why It Matters**:
- Domain-specific models need high domain scores
- General models need balanced domain distribution
- Prevents domain drift in training

---

## 6. LLM Quality Score

**Range**: 1-10 (higher = better overall quality)

**Definition**: Comprehensive LLM-based quality assessment

**Components** (Tulu3 method):
1. **Helpfulness** (1-5) - Addresses instruction
2. **Accuracy** (1-5) - Factually correct
3. **Clarity** (1-5) - Well-explained
4. **Completeness** (1-5) - All aspects covered

**Composite Score**:
```
LLM Quality = (Helpfulness + Accuracy + Clarity + Completeness) / 2.0
Range: 1-10
```

**Calculation Example**:
```python
from training_metrics import Tulu3Scorer

scorer = Tulu3Scorer()
quality = scorer.score({
    "instruction": "Explain recursion in programming",
    "response": "Recursion is when a function calls itself..."
})
# Returns: {
#   "helpfulness": 4,
#   "accuracy": 5,
#   "clarity": 4,
#   "completeness": 4,
#   "llm_quality": 8.5
# }
```

**Thresholds**:
- **≥9.0**: Excellent (DPO chosen, RLVR)
- **≥8.0**: Good (SFT, general training)
- **≥7.0**: Acceptable (augmentation needed)
- **≤6.0**: Poor (DPO rejected)

**Training Type Guidance**:
- **SFT**: Quality ≥8.0 (good baseline)
- **DPO chosen**: Quality ≥9.0 (high quality only)
- **DPO rejected**: Quality ≤6.0 (low quality)
- **RLVR**: Quality ≥9.0 (verified solutions)
- **Calibration**: Quality ≥8.0 (uncertainty examples)

**Why It Matters**:
- Single metric for overall quality assessment
- Balanced across multiple quality aspects
- Standard metric for dataset comparison

---

## Multi-Dimensional Assessment

### Composite Scoring

Combine dimensions for comprehensive quality:

```python
from training_metrics import MultiDimensionalScorer

scorer = MultiDimensionalScorer()
assessment = scorer.score({
    "instruction": "Prove the Pythagorean theorem",
    "response": "For a right triangle with sides a, b, c: a² + b² = c²..."
})
# Returns: {
#   "ifd_score": 0.72,
#   "factuality": 1.0,
#   "reasoning": 0.95,
#   "diversity": 0.60,
#   "domain": 0.90,
#   "llm_quality": 9.2,
#   "composite": 0.83  # Weighted average
# }
```

### Weighting Strategy

**Default weights** (general training):
```python
composite = (
    0.25 * ifd_score +
    0.30 * factuality +
    0.25 * reasoning +
    0.10 * diversity +
    0.10 * domain
)
```

**Domain-specific weights**:
```python
# Math/reasoning domain
math_composite = (
    0.20 * ifd_score +
    0.15 * factuality +
    0.40 * reasoning +  # Emphasize reasoning
    0.10 * diversity +
    0.15 * domain
)

# Factual domain (science, medicine)
factual_composite = (
    0.15 * ifd_score +
    0.50 * factuality +  # Emphasize accuracy
    0.15 * reasoning +
    0.10 * diversity +
    0.10 * domain
)
```

---

## Implementation Guidance

### Security (CWE-20: Input Validation)

```python
def validate_scores(scores: dict) -> bool:
    """Validate score ranges before using."""
    range_checks = {
        "ifd_score": (0.0, 1.0),
        "factuality": (0.0, 1.0),
        "reasoning": (0.0, 1.0),
        "diversity": (0.0, 1.0),
        "domain": (0.0, 1.0),
        "llm_quality": (1, 10)
    }

    for key, (min_val, max_val) in range_checks.items():
        if key in scores:
            if not min_val <= scores[key] <= max_val:
                raise ValueError(
                    f"Score {key}={scores[key]} out of range [{min_val}, {max_val}]"
                )

    return True
```

### Efficient Batch Scoring

```python
from training_metrics import MultiDimensionalScorer

scorer = MultiDimensionalScorer(batch_size=32)

# Score large dataset efficiently
scores = scorer.score_batch(
    dataset=train_data,
    num_workers=4,  # Parallel processing
    progress=True   # Show progress bar
)
```

---

## Related Documentation

- `quality-scorers.md` - Scorer implementations
- `training-thresholds.md` - Threshold guidance by training type
- **data-distillation** skill - IFD methodology details
- **preference-data-quality** skill - DPO/RLVR specific metrics
