# Stage 4: Verifiable Data Generation

Generate diverse training tasks with ground truth verification.

## Overview
Create comprehensive task suite for RLVR training.

## Process

1. **Generate Prompts**: Diverse task prompts
2. **Create Ground Truth**: Solutions with verification
3. **Validate Coverage**: Ensure domain diversity
4. **Split Data**: Train/validation sets

## Format

```jsonl
{"task": "Write a function to reverse a string", "tests": ["assert reverse('hello') == 'olleh'"], "expected_behavior": "correct_reversal"}
{"task": "Calculate 15% of 80", "answer": "12", "verification": "exact_match"}
```

## Quality Gate
- Task diversity validated
- Ground truth verified
- Coverage adequate (≥1000 tasks recommended)

**See**: `verifiable-task-design.md` for task design patterns.
