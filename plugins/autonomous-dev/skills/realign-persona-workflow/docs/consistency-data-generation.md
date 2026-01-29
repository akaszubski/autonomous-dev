# Stage 3: Consistency Data Generation

Create data demonstrating consistent persona across diverse contexts.

## Overview
Generate examples of persona-consistent responses across various scenarios.

## Process
1. **Diverse Scenarios**: Cover different contexts (questions, errors, celebrations)
2. **Consistent Responses**: Apply persona traits uniformly
3. **Contrast Examples**: Show inconsistent responses for comparison
4. **Validate Coverage**: Ensure all traits represented

## Format
```jsonl
{"scenario": "...", "consistent_response": "...", "inconsistent_response": "...", "trait": "..."}
```

## Quality Gate
- Consistency score ≥85%
- All traits covered
- Diverse scenarios

**See**: `../templates.md` for data format examples.
