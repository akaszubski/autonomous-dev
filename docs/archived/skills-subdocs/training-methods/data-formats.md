# Data Format Specifications

Complete data format specifications for all 8 training methods with validation rules, examples, and conversion utilities.

---

## Format Summary Table

| Method | Format | Required Fields | Optional Fields |
|--------|--------|-----------------|-----------------|
| **SFT/LoRA** | JSONL | `instruction`, `output` | `system`, `metadata` |
| **DPO** | JSONL | `prompt`, `chosen`, `rejected` | `metadata`, `gap_score` |
| **ORPO** | JSONL | `prompt`, `chosen`, `rejected` | `metadata`, `gap_score` |
| **GRPO** | JSONL | `prompt`, `responses` | `metadata` |
| **CPO** | JSONL | `prompt`, `chosen`, `rejected` | `metadata`, `kl_weight` |
| **RLVR** | JSONL | `problem`, `solution`, `responses` | `steps`, `metadata` |
| **Abliteration** | None | N/A | N/A |
| **Activation Steering** | JSONL | `text`, `label` | `strength`, `metadata` |

---

## SFT/LoRA Format

### Schema

```json
{
  "instruction": "string (required)",
  "output": "string (required)",
  "system": "string (optional)",
  "metadata": {
    "source": "string (optional)",
    "quality_score": "float (optional)"
  }
}
```

### Example

```jsonl
{"instruction": "Explain quantum computing", "output": "Quantum computing uses quantum mechanics principles like superposition and entanglement to perform computations exponentially faster than classical computers for certain problems.", "system": "You are a helpful physics tutor.", "metadata": {"source": "physics_textbook", "quality_score": 0.95}}
{"instruction": "Write a Python function to reverse a string", "output": "def reverse_string(s):\n    return s[::-1]", "metadata": {"source": "coding_exercises", "quality_score": 0.88}}
```

### Validation Rules

- `instruction`: Non-empty string, <10,000 chars
- `output`: Non-empty string, <32,768 chars
- `system`: Optional string, <1,000 chars
- `metadata.quality_score`: 0.0-1.0

---

## DPO/ORPO/CPO Format

### Schema

```json
{
  "prompt": "string (required)",
  "chosen": "string (required)",
  "rejected": "string (required)",
  "metadata": {
    "gap_score": "float (optional)",
    "source": "string (optional)"
  }
}
```

### Example

```jsonl
{"prompt": "Explain AI ethics", "chosen": "AI ethics considers fairness, accountability, transparency, and privacy in AI systems. It addresses bias in training data, algorithmic discrimination, and responsible deployment.", "rejected": "AI ethics is just a buzzword. Companies use it for PR without making real changes.", "metadata": {"gap_score": 0.42, "source": "ethics_dataset"}}
{"prompt": "Write a function to check if a number is prime", "chosen": "def is_prime(n):\n    if n < 2: return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0: return False\n    return True", "rejected": "def is_prime(n):\n    return n % 2 != 0", "metadata": {"gap_score": 0.65, "source": "code_quality"}}
```

### Validation Rules

- `prompt`: Non-empty string, <10,000 chars
- `chosen`: Non-empty string, <32,768 chars
- `rejected`: Non-empty string, <32,768 chars
- `metadata.gap_score`: Should be ≥0.15 (quality threshold)
- `chosen` and `rejected` must be different

### Quality Thresholds

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Preference gap** | ≥0.15 | Clear preference signal |
| **KL divergence** | ≤0.1 | Prevent model drift |
| **Minimum pairs** | ≥1000 | Adequate training data |
| **Decontamination** | ≥0.9 | No eval leakage |

**See**: `realign-dpo-workflow` skill for complete DPO pipeline

---

## GRPO Format

### Schema

```json
{
  "prompt": "string (required)",
  "responses": [
    {
      "text": "string (required)",
      "score": "float (required, 0.0-1.0)"
    }
  ],
  "metadata": {
    "group_size": "int (optional)",
    "verifier": "string (optional)"
  }
}
```

### Example

```jsonl
{"prompt": "Solve for x: 2x + 5 = 15", "responses": [{"text": "2x + 5 = 15\n2x = 10\nx = 5", "score": 1.0}, {"text": "2x + 5 = 15\nx = 10", "score": 0.0}, {"text": "2x = 10\nx = 5 ✓", "score": 1.0}, {"text": "x = 15 - 5 / 2 = 5", "score": 0.8}], "metadata": {"group_size": 4, "verifier": "symbolic_math"}}
{"prompt": "Write a function to find the maximum element in a list", "responses": [{"text": "def find_max(lst):\n    return max(lst)", "score": 1.0}, {"text": "def find_max(lst):\n    return sorted(lst)[-1]", "score": 0.9}, {"text": "def find_max(lst):\n    m = lst[0]\n    for x in lst:\n        if x > m: m = x\n    return m", "score": 1.0}, {"text": "def find_max(lst):\n    return lst[-1]", "score": 0.0}], "metadata": {"group_size": 4, "verifier": "execution_sandbox"}}
```

### Validation Rules

- `prompt`: Non-empty string, <10,000 chars
- `responses`: List with 4-32 items (typical group_size: 16)
- `responses[].text`: Non-empty string, <32,768 chars
- `responses[].score`: Float 0.0-1.0 (verification score)
- Score variance should be >0.3 (sufficient signal)

### Quality Thresholds

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Verifiability** | >80% | Tasks objectively verifiable |
| **Advantage variance** | 0.5-1.5 | Sufficient signal diversity |
| **Mean reward** | Increasing | Model improving |
| **KL divergence** | <0.1 | No model drift |

**See**: `grpo-verifiable-training` skill for complete GRPO workflow

---

## RLVR Format

### Schema

```json
{
  "problem": "string (required)",
  "solution": "string (required)",
  "responses": [
    {
      "text": "string (required)",
      "correct": "bool (required)"
    }
  ],
  "steps": [
    {
      "description": "string (optional)",
      "verification": "bool (optional)"
    }
  ],
  "metadata": {
    "verifier": "string (optional)",
    "difficulty": "string (optional)"
  }
}
```

### Example

```jsonl
{"problem": "Write a function to check if a string is a palindrome", "solution": "def is_palindrome(s):\n    s = s.lower().replace(' ', '')\n    return s == s[::-1]", "responses": [{"text": "def is_palindrome(s):\n    return s == s[::-1]", "correct": false}, {"text": "def is_palindrome(s):\n    s = s.lower().replace(' ', '')\n    return s == s[::-1]", "correct": true}], "steps": [{"description": "Normalize string (lowercase, remove spaces)", "verification": true}, {"description": "Compare with reversed string", "verification": true}], "metadata": {"verifier": "execution_sandbox", "difficulty": "medium"}}
```

### Validation Rules

- `problem`: Non-empty string, <10,000 chars
- `solution`: Non-empty string, <32,768 chars (reference solution)
- `responses`: List with 2-16 items
- `responses[].text`: Non-empty string, <32,768 chars
- `responses[].correct`: Boolean (true = correct, false = incorrect)
- `steps`: Optional list of verification steps

### Quality Thresholds

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Step correctness** | >80% | Intermediate steps verified |
| **Final correctness** | >90% | Final answer correct |
| **Verification coverage** | 100% | All steps verifiable |

**See**: `realign-rlvr-workflow` skill for complete RLVR workflow

---

## Activation Steering Format

### Schema

```json
{
  "text": "string (required)",
  "label": "string (required)",
  "strength": "float (optional, default 1.0)",
  "metadata": {
    "category": "string (optional)"
  }
}
```

### Example

```jsonl
{"text": "I appreciate your perspective, but I must respectfully disagree.", "label": "polite", "strength": 1.0, "metadata": {"category": "tone"}}
{"text": "That's completely wrong and you should know better.", "label": "rude", "strength": 0.8, "metadata": {"category": "tone"}}
{"text": "The research indicates that the hypothesis is supported by empirical evidence.", "label": "formal", "strength": 1.2, "metadata": {"category": "style"}}
```

### Validation Rules

- `text`: Non-empty string, <10,000 chars
- `label`: Non-empty string, <100 chars (steering direction)
- `strength`: Float 0.1-2.0 (steering magnitude)
- Need ≥50 examples per label for stable steering vector

---

## Format Conversion

### SFT → DPO

Convert SFT dataset to DPO by generating rejected responses:

```python
def sft_to_dpo(sft_example):
    """Convert SFT example to DPO format."""
    # Use model to generate rejected response
    rejected = generate_low_quality_response(
        sft_example["instruction"]
    )

    return {
        "prompt": sft_example["instruction"],
        "chosen": sft_example["output"],
        "rejected": rejected
    }
```

### SFT → GRPO

Convert SFT dataset to GRPO by generating multiple responses:

```python
def sft_to_grpo(sft_example, group_size=16):
    """Convert SFT example to GRPO format."""
    # Generate multiple responses
    responses = []
    for _ in range(group_size):
        text = generate_response(sft_example["instruction"])
        score = verify_response(text, sft_example["output"])
        responses.append({"text": text, "score": score})

    return {
        "prompt": sft_example["instruction"],
        "responses": responses
    }
```

### DPO → GRPO

Convert DPO pairs to GRPO format:

```python
def dpo_to_grpo(dpo_example, num_extra=14):
    """Convert DPO example to GRPO format."""
    # Start with chosen/rejected as group members
    responses = [
        {"text": dpo_example["chosen"], "score": 1.0},
        {"text": dpo_example["rejected"], "score": 0.0}
    ]

    # Generate additional responses
    for _ in range(num_extra):
        text = generate_response(dpo_example["prompt"])
        score = score_response(text, dpo_example["chosen"])
        responses.append({"text": text, "score": score})

    return {
        "prompt": dpo_example["prompt"],
        "responses": responses
    }
```

---

## Validation Functions

### Python Validation

```python
import json
from pathlib import Path

def validate_sft(example: dict) -> bool:
    """Validate SFT format."""
    required = ["instruction", "output"]
    if not all(k in example for k in required):
        return False
    if len(example["instruction"]) > 10000:
        return False
    if len(example["output"]) > 32768:
        return False
    return True

def validate_dpo(example: dict) -> bool:
    """Validate DPO format."""
    required = ["prompt", "chosen", "rejected"]
    if not all(k in example for k in required):
        return False
    if example["chosen"] == example["rejected"]:
        return False
    if "metadata" in example and "gap_score" in example["metadata"]:
        if example["metadata"]["gap_score"] < 0.15:
            print("Warning: gap_score < 0.15 (low preference signal)")
    return True

def validate_grpo(example: dict) -> bool:
    """Validate GRPO format."""
    if "prompt" not in example or "responses" not in example:
        return False
    if not (4 <= len(example["responses"]) <= 32):
        return False
    for resp in example["responses"]:
        if "text" not in resp or "score" not in resp:
            return False
        if not (0.0 <= resp["score"] <= 1.0):
            return False
    return True

def validate_rlvr(example: dict) -> bool:
    """Validate RLVR format."""
    required = ["problem", "solution", "responses"]
    if not all(k in example for k in required):
        return False
    for resp in example["responses"]:
        if "text" not in resp or "correct" not in resp:
            return False
        if not isinstance(resp["correct"], bool):
            return False
    return True
```

### Command-Line Validation

```bash
# Validate SFT dataset
python -c "
import json
with open('data/sft.jsonl') as f:
    for i, line in enumerate(f, 1):
        example = json.loads(line)
        assert 'instruction' in example, f'Line {i}: missing instruction'
        assert 'output' in example, f'Line {i}: missing output'
        print(f'Line {i}: OK')
"

# Validate DPO dataset
python -c "
import json
with open('data/dpo.jsonl') as f:
    for i, line in enumerate(f, 1):
        example = json.loads(line)
        assert 'prompt' in example, f'Line {i}: missing prompt'
        assert 'chosen' in example, f'Line {i}: missing chosen'
        assert 'rejected' in example, f'Line {i}: missing rejected'
        assert example['chosen'] != example['rejected'], f'Line {i}: chosen == rejected'
        print(f'Line {i}: OK')
"
```

---

## Common Issues

### Issue 1: Missing Required Fields

**Symptom**: Training fails with KeyError

**Cause**: JSONL missing required fields

**Fix**: Validate dataset before training

```bash
python validate_dataset.py data/sft.jsonl --format sft
```

---

### Issue 2: Low Preference Gap (DPO)

**Symptom**: DPO training unstable, no improvement

**Cause**: `chosen` and `rejected` too similar (gap <0.15)

**Fix**: Filter low-gap pairs

```python
with open("data/dpo.jsonl") as f, open("data/dpo_filtered.jsonl", "w") as out:
    for line in f:
        example = json.loads(line)
        if "metadata" in example and example["metadata"].get("gap_score", 0) >= 0.15:
            out.write(line)
```

---

### Issue 3: Low Advantage Variance (GRPO)

**Symptom**: GRPO training unstable, no signal

**Cause**: All responses have similar scores (variance <0.3)

**Fix**: Increase temperature, diversify responses

```python
# Generate responses with higher temperature
responses = generate_group(
    prompt,
    group_size=16,
    temperature=1.2  # Increase from 1.0
)
```

---

## Dataset Statistics

### Recommended Dataset Sizes

| Method | Minimum | Recommended | Notes |
|--------|---------|-------------|-------|
| **SFT/LoRA** | 100 | 1000+ | More = better coverage |
| **DPO** | 1000 | 5000+ | Need diverse preferences |
| **ORPO** | 1000 | 5000+ | Same as DPO |
| **GRPO** | 500 | 2000+ | Each with 16 responses |
| **CPO** | 1000 | 5000+ | Same as DPO |
| **RLVR** | 500 | 2000+ | Each with steps |
| **Activation Steering** | 50 | 200+ | Per steering direction |

---

**See**: Main skill file for method selection and backend support.
