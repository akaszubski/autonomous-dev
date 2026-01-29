# Stage 4: Attribution Verification

Build system to verify source attribution quality.

## Overview
Implement automated verification of citation accuracy and coverage.

## Verification Components
1. **Citation Extraction**: Identify cited sources in output
2. **Source Validation**: Verify sources exist and support claims
3. **Coverage Measurement**: % claims with attribution
4. **Accuracy Checking**: Correct source-claim matching

## Implementation
```python
def verify_attribution(output: str, knowledge_base) -> dict:
    """Verify source attribution quality."""
    claims = extract_claims(output)
    citations = extract_citations(output)
    
    # Check coverage
    coverage = len([c for c in claims if has_citation(c, citations)]) / len(claims)
    
    # Check accuracy
    accurate = sum(1 for c in citations if validates_against_source(c, knowledge_base))
    accuracy = accurate / len(citations) if citations else 0
    
    return {
        "coverage": coverage,
        "accuracy": accuracy
    }
```

## Quality Gate
- Attribution coverage ≥80%
- Citation accuracy ≥90%
- Verification system reliable

**See**: `../templates.md` for verification implementation.
