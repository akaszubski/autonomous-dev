# Flaw Types for Rejected Responses

Complete taxonomy of intentional flaws for generating high-quality DPO rejected responses.

## Core Principle

**Diverse, realistic flaws create stronger preference signals.**

Rejected responses should represent common failure modes, not random noise.

---

## Flaw Type Taxonomy

### 1. Risky Advice

**Definition**: Dangerous or harmful recommendations

**Finance Examples**:
- "Invest your entire savings in a single penny stock"
- "Max out all your credit cards to invest in crypto"
- "Never diversify - put everything in one asset"

**Generation Strategy**:
```python
def generate_risky_advice(prompt: str) -> str:
    """Generate overly risky financial advice."""
    # Remove risk warnings
    # Suggest extreme concentration
    # Ignore downside scenarios
    return rejected_response
```

**Quality Check**: Advice should be clearly dangerous, not subtly flawed.

---

### 2. Oversimplified

**Definition**: Correct but missing critical nuance

**Finance Examples**:
- "Just buy low, sell high" (no strategy for timing)
- "Invest in index funds" (no risk assessment, timeline, allocation)
- "Save 10% of income" (no emergency fund, debt payoff priority)

**Generation Strategy**:
```python
def generate_oversimplified(response: str) -> str:
    """Remove critical caveats and context."""
    # Strip conditional statements
    # Remove "it depends" qualifiers
    # Delete risk warnings
    return rejected_response
```

**Quality Check**: Response should be technically correct but dangerously incomplete.

---

### 3. Incomplete

**Definition**: Partial answer, stops mid-explanation

**Finance Examples**:
- "Calculate ROI by dividing..." (stops before formula)
- "To determine risk tolerance, consider..." (lists one factor, stops)
- "Diversification means..." (definition only, no implementation)

**Generation Strategy**:
```python
def generate_incomplete(response: str) -> str:
    """Truncate response at critical point."""
    # Find key explanatory section
    # Truncate mid-explanation
    # Leave reader without actionable info
    return rejected_response
```

**Quality Check**: Should feel frustratingly incomplete, not just short.

---

### 4. Hallucinated

**Definition**: Incorrect facts, formulas, or procedures

**Finance Examples**:
- "Interest = Principal × 2" (wrong formula)
- "401(k) contribution limit is $50,000" (incorrect number)
- "Stocks always recover within 6 months" (false claim)

**Generation Strategy**:
```python
def generate_hallucinated(response: str) -> str:
    """Introduce factual errors."""
    # Corrupt formulas
    # Invent statistics
    # State false historical patterns
    return rejected_response
```

**Quality Check**: Error should be subtle enough to seem plausible.

---

### 5. Irrelevant

**Definition**: Off-topic or tangential response

**Finance Examples**:
- "Finance is like cooking - you need the right ingredients..." (extended metaphor, no finance advice)
- "Let me tell you about my investment journey..." (personal story, not answering question)
- "The history of banking dates back to..." (historical tangent)

**Generation Strategy**:
```python
def generate_irrelevant(prompt: str) -> str:
    """Generate tangentially related content."""
    # Start with metaphor, never return to topic
    # Answer different question
    # Provide generic wisdom instead of specific advice
    return rejected_response
```

**Quality Check**: Should start on-topic, then drift irretrievably.

---

### 6. Overconfident

**Definition**: Certainty about uncertain or unknowable facts

**Finance Examples**:
- "Tesla stock WILL rise 50% next year"
- "Housing market will definitely crash in Q3"
- "This investment has ZERO risk"

**Generation Strategy**:
```python
def generate_overconfident(response: str) -> str:
    """Replace hedges with absolute statements."""
    # "might" → "will"
    # "likely" → "definitely"
    # "could" → "must"
    # Remove conditional language
    return rejected_response
```

**Quality Check**: Predictions should be stated as facts, not probabilities.

---

## Flaw Distribution

### Recommended Mix

```python
FLAW_DISTRIBUTION = {
    "risky_advice": 0.20,      # 20% - Safety-critical
    "oversimplified": 0.25,    # 25% - Most common real failure
    "incomplete": 0.20,        # 20% - Frustrating but common
    "hallucinated": 0.15,      # 15% - Factual errors
    "irrelevant": 0.10,        # 10% - Off-topic responses
    "overconfident": 0.10      # 10% - Unwarranted certainty
}
```

### Rationale

| Flaw Type | Percentage | Rationale |
|-----------|-----------|-----------|
| **Oversimplified** | 25% | Most common real-world failure mode |
| **Risky Advice** | 20% | Safety-critical for high-stakes domains |
| **Incomplete** | 20% | Common but less severe than risky advice |
| **Hallucinated** | 15% | Factual errors, detectable but subtle |
| **Irrelevant** | 10% | Less common in fine-tuned models |
| **Overconfident** | 10% | Smaller category, still important |

---

## Generation Examples

### Example 1: Risky Advice

**Prompt**: "How should I invest my emergency fund?"

**Chosen (Quality 9.5)**:
```
Your emergency fund should remain in highly liquid, low-risk accounts
like high-yield savings or money market funds. The priority is
accessibility and capital preservation, not returns. Aim for 3-6 months
of expenses. Only after establishing this safety net should you consider
higher-return investments.
```

**Rejected (Quality 4.0, Flaw: risky_advice)**:
```
Invest your emergency fund in high-growth tech stocks for maximum returns.
You can always sell quickly if you need the money. Don't waste it sitting
in a savings account earning nothing.
```

**Preference Gap**: 9.5 - 4.0 = 5.5 ✅ (target ≥3.0)

---

### Example 2: Oversimplified

**Prompt**: "What's dollar-cost averaging?"

**Chosen (Quality 9.0)**:
```
Dollar-cost averaging (DCA) is investing a fixed amount at regular intervals
regardless of market conditions. For example, investing $500 monthly into an
index fund. Benefits include emotional discipline and buying more shares when
prices are low. However, DCA historically underperforms lump-sum investing
in rising markets. It's most useful when you receive income periodically or
want to reduce timing risk and emotional stress.
```

**Rejected (Quality 5.5, Flaw: oversimplified)**:
```
Dollar-cost averaging means investing the same amount regularly. It's a good
strategy that reduces risk.
```

**Preference Gap**: 9.0 - 5.5 = 3.5 ✅ (target ≥3.0)

---

## Validation Checklist

Before finalizing rejected responses:

- [ ] Flaw is realistic (not absurd)
- [ ] Quality score ≤6.0 (enforced threshold)
- [ ] Preference gap ≥3.0 vs chosen response
- [ ] Flaw type matches target category
- [ ] Response is grammatically correct (flaw is conceptual, not linguistic)
- [ ] Rejected response could plausibly fool someone

---

## Anti-Patterns

### ❌ Don't Do This

**Random corruption**:
```
"ivnset in stcoks" (typos don't teach preference)
```

**Absurdly wrong**:
```
"Stocks are vegetables" (too obviously wrong)
```

**Multiple flaw types**:
```
"Invest everything in crypto (risky), stocks always go up (overconfident),
like cooking (irrelevant)" (confuses the signal)
```

### ✅ Do This

**Single, realistic flaw**:
```
"Invest heavily in a single sector for maximum growth potential"
(risky_advice - realistic but dangerous)
```

---

## Integration with Quality Scoring

From **quality-scoring** skill:

- **Chosen threshold**: ≥9.0
- **Rejected threshold**: ≤6.0
- **Preference gap**: ≥3.0

Use `training_metrics.py`:

```python
from training_metrics import validate_dpo_pairs

metrics = validate_dpo_pairs(
    dpo_path=Path("pairs.jsonl"),
    gap_threshold=3.0
)

# Check flaw distribution
flaw_counts = count_flaw_types(metrics)
assert flaw_counts["oversimplified"] >= 0.20 * total_pairs
```

---

## Key Takeaways

1. **6 flaw types**: risky_advice, oversimplified, incomplete, hallucinated, irrelevant, overconfident
2. **Distribution**: 25% oversimplified, 20% risky_advice, 20% incomplete, 15% hallucinated, 10% irrelevant, 10% overconfident
3. **Realistic flaws**: Should represent common failures, not absurd errors
4. **Single flaw per response**: Don't mix multiple flaw types
5. **Quality enforcement**: Rejected ≤6.0, preference gap ≥3.0
6. **Validation**: Use training_metrics library
