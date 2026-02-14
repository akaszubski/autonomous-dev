# Generation Workflows

Complete pipelines for anti-hallucination data generation.

## Multi-Stage Pipeline

```
Stage 1: Source Data → Stage 2: Generate → Stage 3: Validate → Stage 4: Output
```

### Stage 1: Source Data Collection

```bash
# Collect questions requiring factual answers
python scripts/collect_questions.py \
  --sources "wikipedia,news,academic" \
  --count 50000 \
  --output questions.jsonl
```

### Stage 2: Generate Responses

```bash
# Generate anti-hallucination data
python -m realign.data.antihallucination_generator \
  --input questions.jsonl \
  --output antihall_raw.jsonl \
  --refusal-ratio 0.4 \
  --num-examples 10000
```

### Stage 3: Validate Quality

```bash
# Validate generated data
python scripts/validate_antihall.py \
  --input antihall_raw.jsonl \
  --output antihall_validated.jsonl \
  --min-confidence-accuracy 0.8
```

### Stage 4: Format for Training

```bash
# Convert to DPO format if needed
python scripts/format_dpo.py \
  --input antihall_validated.jsonl \
  --output antihall_dpo.jsonl
```

## Quality Gates

| Gate | Threshold | Action if Failed |
|------|-----------|------------------|
| Data type balance | ±5% of target | Rebalance |
| Confidence accuracy | ≥80% | Filter low-quality |
| JSON validity | 100% | Fix or discard |

## Integration with Training

```
anti-hallucination-training skill (DATA GENERATION)
           ↓
   antihall.jsonl output
           ↓
realign-antihallucination-workflow skill (TRAINING)
           ↓
   Trained model with reduced hallucinations
```
