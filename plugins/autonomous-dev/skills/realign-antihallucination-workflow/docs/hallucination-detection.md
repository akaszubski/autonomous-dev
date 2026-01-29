# Stage 4: Hallucination Detection

Build system to detect unsupported claims and hallucinations.

## Overview
Implement automated detection of claims without factual support.

## Detection Methods
1. **Knowledge Base Query**: Check if claim in verified sources
2. **Fact-checking APIs**: External verification
3. **Consistency Checking**: Internal contradictions
4. **Citation Analysis**: Unsupported claims flagged

## Implementation
```python
def detect_hallucination(output: str, knowledge_base) -> dict:
    claims = extract_claims(output)
    hallucinations = []
    
    for claim in claims:
        if not knowledge_base.supports(claim):
            hallucinations.append(claim)
    
    hallucination_rate = len(hallucinations) / len(claims)
    return {
        "rate": hallucination_rate,
        "detected": hallucinations
    }
```

## Quality Gate
- Hallucination detection reliable
- False positive rate <5%
- Hallucination rate <10%

**See**: `../templates.md` for detection implementation.
