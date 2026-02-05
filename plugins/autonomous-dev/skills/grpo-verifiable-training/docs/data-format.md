# GRPO Data Format and Generation

Complete guide to generating, formatting, and batching data for GRPO training.

## JSONL Format Specification

### Required Fields

```json
{
  "prompt": "Solve for x: 2x + 5 = 15",
  "responses": [
    {
      "text": "2x + 5 = 15\n2x = 10\nx = 5",
      "score": 1.0,
      "correct": true
    },
    {
      "text": "2x + 5 = 15\nx = 10",
      "score": 0.0,
      "correct": false
    }
  ]
}
```

**Field Descriptions**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | ✅ Yes | Input question or task |
| `responses` | list | ✅ Yes | Group of responses (size = group_size) |
| `responses[].text` | string | ✅ Yes | Model-generated response |
| `responses[].score` | float | ✅ Yes | Verification score (0.0-1.0) |
| `responses[].correct` | bool | ⚠️ Optional | Binary correctness flag |

### Optional Fields

```json
{
  "prompt": "Write a function to reverse a string",
  "responses": [
    {
      "text": "def reverse(s):\n    return s[::-1]",
      "score": 1.0,
      "correct": true,
      "reasoning": "Used Python slicing idiom",
      "execution_output": "Test passed: 'hello' -> 'olleh'",
      "metadata": {
        "model": "llama-3.2-1b",
        "temperature": 1.0,
        "generation_time_ms": 245
      }
    }
  ],
  "difficulty": "easy",
  "category": "string_manipulation",
  "source": "leetcode_easy"
}
```

**Optional Fields**:

| Field | Type | Purpose |
|-------|------|---------|
| `responses[].reasoning` | string | Chain-of-thought explanation |
| `responses[].execution_output` | string | Code execution result |
| `responses[].metadata` | object | Generation metadata |
| `difficulty` | string | Prompt difficulty level |
| `category` | string | Task category |
| `source` | string | Data source |

## Data Generation Pipeline

### Step 1: Prepare Prompts

```python
# prompts.jsonl
{"prompt": "Solve for x: 2x + 5 = 15", "category": "algebra"}
{"prompt": "Find derivative of x^2 + 3x + 2", "category": "calculus"}
{"prompt": "Write function to reverse string", "category": "code"}
```

### Step 2: Generate Responses

```python
import anthropic
import json

client = anthropic.Anthropic(api_key="...")
GROUP_SIZE = 16

def generate_responses(prompt: str, group_size: int = 16):
    """Generate group_size responses for a single prompt."""
    responses = []
    for _ in range(group_size):
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=1.0,  # Diversity important
            messages=[{"role": "user", "content": prompt}]
        )
        responses.append({
            "text": message.content[0].text,
            "score": None,  # Will be filled by verifier
            "correct": None
        })
    return responses

# Process all prompts
with open("prompts.jsonl") as f_in, open("generated.jsonl", "w") as f_out:
    for line in f_in:
        data = json.loads(line)
        prompt = data["prompt"]
        responses = generate_responses(prompt, GROUP_SIZE)

        output = {
            "prompt": prompt,
            "responses": responses,
            "category": data.get("category")
        }
        f_out.write(json.dumps(output) + "\n")
```

### Step 3: Verify Responses

```python
from sympy import sympify, solve

def verify_math(problem: str, answer: str) -> tuple[float, bool]:
    """Verify math answer with symbolic solver."""
    try:
        # Parse problem and answer
        expected = solve(problem)
        provided = sympify(answer.strip())

        # Check correctness
        correct = provided in expected
        score = 1.0 if correct else 0.0

        return score, correct
    except Exception as e:
        # Verification failed (malformed answer)
        return 0.0, False

# Apply verifier to all responses
with open("generated.jsonl") as f_in, open("verified.jsonl", "w") as f_out:
    for line in f_in:
        data = json.loads(line)
        prompt = data["prompt"]

        # Verify each response
        for response in data["responses"]:
            score, correct = verify_math(prompt, response["text"])
            response["score"] = score
            response["correct"] = correct

        f_out.write(json.dumps(data) + "\n")
```

## Batching Strategies

### Static Batching

**Use case**: All prompts same length

```python
BATCH_SIZE = 32

def create_static_batches(data: list, batch_size: int):
    """Create fixed-size batches."""
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]
```

### Dynamic Batching

**Use case**: Variable prompt lengths (efficient GPU use)

```python
def create_dynamic_batches(data: list, max_tokens: int = 8192):
    """Create batches by token budget."""
    current_batch = []
    current_tokens = 0

    for item in data:
        item_tokens = len(item["prompt"].split()) * 1.3  # Rough estimate

        if current_tokens + item_tokens > max_tokens:
            yield current_batch
            current_batch = [item]
            current_tokens = item_tokens
        else:
            current_batch.append(item)
            current_tokens += item_tokens

    if current_batch:
        yield current_batch
```

### Stratified Batching

**Use case**: Balance difficulty/category

```python
def create_stratified_batches(data: list, batch_size: int):
    """Create batches with balanced difficulty."""
    # Group by difficulty
    by_difficulty = {}
    for item in data:
        difficulty = item.get("difficulty", "medium")
        by_difficulty.setdefault(difficulty, []).append(item)

    # Sample from each difficulty level
    while any(by_difficulty.values()):
        batch = []
        for difficulty in ["easy", "medium", "hard"]:
            items = by_difficulty.get(difficulty, [])
            if items:
                batch.append(items.pop(0))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
```

## Data Quality Checks

### Check 1: Group Size Validation

```python
def validate_group_sizes(filepath: str, expected_size: int = 16):
    """Ensure all prompts have correct group_size."""
    with open(filepath) as f:
        for i, line in enumerate(f, 1):
            data = json.loads(line)
            actual_size = len(data["responses"])
            if actual_size != expected_size:
                print(f"Line {i}: Expected {expected_size}, got {actual_size}")
```

### Check 2: Score Validation

```python
def validate_scores(filepath: str):
    """Ensure all scores are valid (0.0-1.0)."""
    with open(filepath) as f:
        for i, line in enumerate(f, 1):
            data = json.loads(line)
            for j, response in enumerate(data["responses"]):
                score = response.get("score")
                if score is None:
                    print(f"Line {i}, Response {j}: Missing score")
                elif not (0.0 <= score <= 1.0):
                    print(f"Line {i}, Response {j}: Invalid score {score}")
```

### Check 3: Verification Coverage

```python
def check_verification_coverage(filepath: str):
    """Check percentage of successfully verified responses."""
    total_responses = 0
    verified_responses = 0

    with open(filepath) as f:
        for line in f:
            data = json.loads(line)
            for response in data["responses"]:
                total_responses += 1
                if response.get("score") is not None:
                    verified_responses += 1

    coverage = verified_responses / total_responses * 100
    print(f"Verification coverage: {coverage:.1f}%")

    if coverage < 80:
        print("WARNING: Verification coverage below 80% threshold")
```

## Data Augmentation

### Paraphrasing Prompts

```python
def paraphrase_prompt(prompt: str) -> str:
    """Generate paraphrased version of prompt."""
    # Use Claude or other LLM to paraphrase
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": f"Paraphrase this math problem (keep difficulty same):\n\n{prompt}"
        }]
    )
    return response.content[0].text
```

### Difficulty Variation

```python
def create_difficulty_variants(prompt: str):
    """Create easier and harder versions."""
    # Easier: Simpler numbers
    # Harder: More steps, larger numbers
    variants = {
        "easy": simplify_prompt(prompt),
        "medium": prompt,
        "hard": complexify_prompt(prompt)
    }
    return variants
```

## Example Complete Pipeline

```bash
# 1. Generate responses
python generate_responses.py \
    --prompts data/math_prompts.jsonl \
    --output data/generated.jsonl \
    --group_size 16 \
    --temperature 1.0

# 2. Verify responses
python verify_responses.py \
    --input data/generated.jsonl \
    --output data/verified.jsonl \
    --verifier symbolic_math

# 3. Validate data quality
python validate_data.py \
    --input data/verified.jsonl \
    --checks group_size,scores,coverage

# 4. Create training batches
python create_batches.py \
    --input data/verified.jsonl \
    --output data/batches/ \
    --batch_size 32 \
    --strategy dynamic

# 5. Train GRPO model
python train_grpo.py \
    --data data/batches/ \
    --config configs/grpo_math.yaml
```

## Best Practices

1. **Group size**: Use 16 for good variance reduction
2. **Temperature**: Use 1.0 for diverse training responses
3. **Verification**: Aim for >80% coverage
4. **Batching**: Use dynamic batching for variable-length prompts
5. **Quality checks**: Validate group sizes, scores, and coverage
6. **Augmentation**: Paraphrase prompts to increase data diversity
7. **Storage**: Use JSONL (one record per line) for streaming

## Common Issues

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Missing scores** | Validation check fails | Re-run verifier on incomplete data |
| **Low variance** | All scores 0.0 or 1.0 | Increase temperature, diversify prompts |
| **Verification failures** | Coverage <80% | Improve verifier logic, filter malformed |
| **Memory issues** | Large files won't load | Use streaming/chunked processing |

## References

1. JSONL format specification
2. DeepSeek-R1 data generation pipeline
3. HuggingFace datasets library
