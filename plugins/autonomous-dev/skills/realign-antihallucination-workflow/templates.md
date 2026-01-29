# Anti-hallucination Workflow Templates

## Factuality Data Format (JSONL)

```jsonl
{"claim": "The Eiffel Tower is 330 meters tall.", "source": "Official Eiffel Tower website", "factual": true, "citation": "According to the official Eiffel Tower website, the tower is 330 meters tall."}
{"claim": "Paris is the capital of Germany.", "source": null, "factual": false, "citation": null}
```

## Configuration (YAML)

```yaml
# antihallucination_config.yaml
model:
  base_model: "meta-llama/Llama-2-7b-hf"
  sft_checkpoint: "checkpoints/sft_baseline"

data:
  factual_data_file: "data/factual_pairs.jsonl"
  citation_examples: "data/citation_training.jsonl"
  knowledge_base: "data/knowledge_sources/"

training:
  learning_rate: 1.0e-6
  kl_penalty: 0.1
  factuality_weight: 1.0
  batch_size: 4
  max_steps: 1000

constraints:
  kl_target: 0.1
  factuality_target: 0.90
  citation_accuracy_target: 0.85
  hallucination_rate_max: 0.10

verification:
  fact_check_api: "https://factcheck.api/verify"
  knowledge_sources: ["wikipedia", "scientific_papers"]

logging:
  wandb_project: "antihallucination-training"
  output_dir: "outputs/antihalluc-exp-001"
```

## Factuality Checker (Python)

```python
def check_factuality(claim: str, sources: list) -> dict:
    """Check if claim is supported by sources.
    
    Returns:
        {
            "factual": bool,
            "confidence": float,
            "supporting_sources": list,
            "hallucination_detected": bool
        }
    """
    # Query knowledge base
    evidence = query_knowledge_base(claim, sources)
    
    # Check support
    supported = any(ev.supports(claim) for ev in evidence)
    
    return {
        "factual": supported,
        "confidence": calculate_confidence(evidence),
        "supporting_sources": [ev.source for ev in evidence if ev.supports(claim)],
        "hallucination_detected": not supported
    }
```

**See**: `docs/hallucination-detection.md` for complete detection system.
