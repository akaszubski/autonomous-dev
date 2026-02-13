# CLI Reference

Complete command documentation and examples for DPO and RLVR data generation.

## DPO Pair Generation Commands

### refusal_dpo_generator

Generate refusal vs compliance preference pairs.

**Basic Usage**:
```bash
python -m realign.data.refusal_dpo_generator \
  --input sft.jsonl \
  --output dpo_pairs.jsonl \
  --num-pairs 1000
```

**Options**:
- `--input PATH` - Input SFT dataset (JSONL format)
- `--output PATH` - Output DPO pairs (JSONL format)
- `--num-pairs INT` - Number of pairs to generate (default: 1000)
- `--refusal-style STR` - Refusal style: "polite", "direct", "explanatory" (default: "polite")
- `--model STR` - Model for generation (default: "anthropic/claude-3.5-sonnet")

**Example**:
```bash
# Generate 5000 pairs with explanatory refusal style
python -m realign.data.refusal_dpo_generator \
  --input sft_data.jsonl \
  --output refusal_pairs.jsonl \
  --num-pairs 5000 \
  --refusal-style explanatory \
  --model anthropic/claude-3-opus-20240229
```

---

### finance_dpo_generator

Generate domain-specific pairs with intentional flaws.

**Basic Usage**:
```bash
python -m realign.data.finance_dpo_generator \
  --input finance_sft.jsonl \
  --output finance_dpo.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0
```

**Options**:
- `--input PATH` - Input domain-specific dataset (JSONL format)
- `--output PATH` - Output DPO pairs (JSONL format)
- `--chosen-threshold FLOAT` - Minimum quality for chosen (default: 9.0)
- `--rejected-threshold FLOAT` - Maximum quality for rejected (default: 6.0)
- `--gap-threshold FLOAT` - Minimum preference gap (default: 3.0)
- `--flaw-distribution STR` - Flaw type distribution JSON (default: balanced)
- `--num-pairs INT` - Number of pairs to generate (default: 1000)

**Flaw Distribution Format**:
```json
{
  "risky_advice": 0.20,
  "oversimplified": 0.25,
  "incomplete": 0.20,
  "hallucinated": 0.15,
  "irrelevant": 0.10,
  "overconfident": 0.10
}
```

**Example**:
```bash
# Generate finance pairs with custom flaw distribution
python -m realign.data.finance_dpo_generator \
  --input finance_qa.jsonl \
  --output finance_dpo.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0 \
  --gap-threshold 3.0 \
  --flaw-distribution '{"risky_advice": 0.3, "oversimplified": 0.3, "incomplete": 0.2, "hallucinated": 0.2}' \
  --num-pairs 2000
```

---

### validate_dpo

Validate DPO pairs against quality thresholds.

**Basic Usage**:
```bash
python -m training_metrics validate_dpo \
  --input dpo_pairs.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0 \
  --gap-threshold 3.0
```

**Options**:
- `--input PATH` - DPO pairs dataset (JSONL format)
- `--chosen-threshold FLOAT` - Minimum quality for chosen (default: 9.0)
- `--rejected-threshold FLOAT` - Maximum quality for rejected (default: 6.0)
- `--gap-threshold FLOAT` - Minimum preference gap (default: 3.0)
- `--min-pairs INT` - Minimum number of pairs (default: 1000)
- `--output PATH` - Output validation report (JSON format)

**Output Format**:
```json
{
  "avg_chosen": 9.3,
  "avg_rejected": 5.2,
  "avg_gap": 4.1,
  "total_pairs": 1250,
  "passes_thresholds": true,
  "violations": []
}
```

**Example**:
```bash
# Validate and save report
python -m training_metrics validate_dpo \
  --input dpo_pairs.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0 \
  --gap-threshold 3.0 \
  --min-pairs 1000 \
  --output validation_report.json
```

---

## RLVR Data Generation Commands

### finance_rlvr_generator

Generate finance calculations with automated verification.

**Basic Usage**:
```bash
python -m realign.data.finance_rlvr_generator \
  --input finance_data.jsonl \
  --output rlvr.jsonl \
  --domain finance
```

**Options**:
- `--input PATH` - Input finance dataset (JSONL format)
- `--output PATH` - Output RLVR data (JSONL format)
- `--domain STR` - Domain: "finance", "math", "code" (default: "finance")
- `--num-tasks INT` - Number of tasks to generate (default: 1000)
- `--verification-type STR` - Verification type: "math", "code", "custom" (default: "math")
- `--tolerance FLOAT` - Numerical tolerance for verification (default: 0.01)

**Example**:
```bash
# Generate 2000 finance RLVR tasks with tight tolerance
python -m realign.data.finance_rlvr_generator \
  --input finance_problems.jsonl \
  --output finance_rlvr.jsonl \
  --domain finance \
  --num-tasks 2000 \
  --verification-type math \
  --tolerance 0.001
```

---

### code_rlvr_generator

Generate code tasks with sandbox verification.

**Basic Usage**:
```bash
python -m realign.data.code_rlvr_generator \
  --input coding_tasks.jsonl \
  --output code_rlvr.jsonl \
  --verification-type code
```

**Options**:
- `--input PATH` - Input coding tasks (JSONL format)
- `--output PATH` - Output RLVR data (JSONL format)
- `--verification-type STR` - Always "code" for this generator
- `--test-cases INT` - Number of test cases per task (default: 3)
- `--timeout INT` - Execution timeout in seconds (default: 5)
- `--num-tasks INT` - Number of tasks to generate (default: 1000)

**Example**:
```bash
# Generate code tasks with 5 test cases each
python -m realign.data.code_rlvr_generator \
  --input coding_problems.jsonl \
  --output code_rlvr.jsonl \
  --verification-type code \
  --test-cases 5 \
  --timeout 10 \
  --num-tasks 1500
```

---

### math_rlvr_generator

Generate math problems with symbolic verification.

**Basic Usage**:
```bash
python -m realign.data.math_rlvr_generator \
  --input math_problems.jsonl \
  --output math_rlvr.jsonl \
  --verification-type math
```

**Options**:
- `--input PATH` - Input math problems (JSONL format)
- `--output PATH` - Output RLVR data (JSONL format)
- `--verification-type STR` - Always "math" for this generator
- `--symbolic-validation` - Use symbolic equivalence (default: True)
- `--tolerance FLOAT` - Numerical tolerance if needed (default: 1e-6)
- `--num-tasks INT` - Number of tasks to generate (default: 1000)

**Example**:
```bash
# Generate math tasks with symbolic validation
python -m realign.data.math_rlvr_generator \
  --input algebra_problems.jsonl \
  --output math_rlvr.jsonl \
  --verification-type math \
  --symbolic-validation \
  --num-tasks 3000
```

---

### assess_rlvr

Assess RLVR data verifiability.

**Basic Usage**:
```bash
python -m training_metrics assess_rlvr \
  --input rlvr.jsonl \
  --domain math \
  --threshold 0.8
```

**Options**:
- `--input PATH` - RLVR dataset (JSONL format)
- `--domain STR` - Domain: "math", "code", "finance", "general" (default: "general")
- `--threshold FLOAT` - Minimum verifiability threshold (default: 0.8)
- `--output PATH` - Output assessment report (JSON format)

**Output Format**:
```json
{
  "verifiability_score": 0.92,
  "false_positive_rate": 0.03,
  "total_tasks": 1000,
  "passes_threshold": true,
  "domain": "math"
}
```

**Example**:
```bash
# Assess math RLVR data with strict threshold
python -m training_metrics assess_rlvr \
  --input math_rlvr.jsonl \
  --domain math \
  --threshold 0.95 \
  --output rlvr_assessment.json
```

---

## Batch Processing

### Batch DPO Generation

Generate multiple DPO datasets in parallel.

```bash
# Process multiple domains
for domain in finance healthcare legal; do
  python -m realign.data.finance_dpo_generator \
    --input data/${domain}_sft.jsonl \
    --output data/${domain}_dpo.jsonl \
    --chosen-threshold 9.0 \
    --rejected-threshold 6.0 &
done
wait

# Validate all
for domain in finance healthcare legal; do
  python -m training_metrics validate_dpo \
    --input data/${domain}_dpo.jsonl \
    --output data/${domain}_validation.json
done
```

### Batch RLVR Generation

Generate multiple RLVR datasets in parallel.

```bash
# Process multiple task types
for type in math code finance; do
  python -m realign.data.${type}_rlvr_generator \
    --input data/${type}_tasks.jsonl \
    --output data/${type}_rlvr.jsonl \
    --verification-type ${type} &
done
wait

# Assess all
for type in math code finance; do
  python -m training_metrics assess_rlvr \
    --input data/${type}_rlvr.jsonl \
    --domain ${type} \
    --output data/${type}_assessment.json
done
```

---

## Pipeline Integration

### Complete DPO Pipeline

```bash
#!/bin/bash
set -e

# Step 1: Generate DPO pairs
python -m realign.data.finance_dpo_generator \
  --input sft.jsonl \
  --output dpo_pairs.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0 \
  --num-pairs 2000

# Step 2: Validate pairs
python -m training_metrics validate_dpo \
  --input dpo_pairs.jsonl \
  --output validation.json

# Step 3: Check validation passed
if [ $(jq -r '.passes_thresholds' validation.json) == "true" ]; then
  echo "✅ DPO pairs validated - ready for training"
  # Proceed to DPO training workflow
else
  echo "❌ Validation failed - regenerate data"
  exit 1
fi
```

### Complete RLVR Pipeline

```bash
#!/bin/bash
set -e

# Step 1: Generate RLVR data
python -m realign.data.math_rlvr_generator \
  --input math_problems.jsonl \
  --output rlvr.jsonl \
  --num-tasks 2000

# Step 2: Assess verifiability
python -m training_metrics assess_rlvr \
  --input rlvr.jsonl \
  --domain math \
  --threshold 0.95 \
  --output assessment.json

# Step 3: Check assessment passed
if [ $(jq -r '.passes_threshold' assessment.json) == "true" ]; then
  echo "✅ RLVR data validated - ready for training"
  # Proceed to RLVR training workflow
else
  echo "❌ Assessment failed - redesign tasks"
  exit 1
fi
```

---

## Key Takeaways

1. **DPO generators**: `refusal_dpo_generator`, `finance_dpo_generator`
2. **RLVR generators**: `finance_rlvr_generator`, `code_rlvr_generator`, `math_rlvr_generator`
3. **Validation**: `validate_dpo`, `assess_rlvr`
4. **Thresholds**: Chosen ≥9.0, Rejected ≤6.0, Gap ≥3.0, Verifiability ≥80%
5. **Batch processing**: Parallel generation with `&` and `wait`
6. **Pipeline integration**: Generate → Validate → Proceed to training
7. **Output formats**: JSON for validation/assessment reports
