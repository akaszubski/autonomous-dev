# Source Attribution Workflow Templates

## Source Data Format (JSONL)

```jsonl
{"claim": "The Eiffel Tower was completed in 1889.", "source": "Official Eiffel Tower history - eiffel-tower.com", "citation": "According to the official Eiffel Tower website, construction was completed in 1889.", "url": "https://www.eiffel-tower.com/history"}
{"claim": "Python was created by Guido van Rossum.", "source": "Python official documentation", "citation": "As stated in the Python documentation, the language was created by Guido van Rossum.", "url": "https://docs.python.org/3/faq/general.html"}
```

## Configuration (YAML)

```yaml
# source_attribution_config.yaml
model:
  base_model: "meta-llama/Llama-2-7b-hf"
  sft_checkpoint: "checkpoints/sft_baseline"

data:
  source_database: "data/indexed_sources/"
  citation_examples: "data/citation_training.jsonl"
  source_pairs: "data/claim_source_pairs.jsonl"

retrieval:
  system: "RAG"  # RAG, dense retrieval, etc.
  top_k: 5
  precision_threshold: 0.85

training:
  learning_rate: 1.0e-6
  kl_penalty: 0.1
  citation_weight: 1.0
  batch_size: 4
  max_steps: 1000

constraints:
  kl_target: 0.1
  citation_accuracy_target: 0.90
  retrieval_precision_target: 0.85
  attribution_coverage_target: 0.80

verification:
  check_source_validity: true
  validate_urls: true
  citation_format: "inline"  # inline, footnote, bibliography

logging:
  wandb_project: "source-attribution-training"
  output_dir: "outputs/source-exp-001"
```

## Citation Evaluation Script (Python)

```python
def evaluate_source_attribution(output: str, knowledge_base) -> dict:
    """Evaluate source attribution in model output.
    
    Returns:
        {
            "citation_accuracy": float,  # Correct citations (0-1)
            "retrieval_precision": float,  # Source retrieval quality
            "attribution_coverage": float,  # % claims with sources
            "cited_claims": list,  # Claims with sources
            "uncited_claims": list  # Claims without sources
        }
    """
    # Extract claims and citations
    claims = extract_claims(output)
    citations = extract_citations(output)
    
    # Match citations to claims
    cited_claims = match_citations_to_claims(claims, citations)
    uncited_claims = [c for c in claims if c not in cited_claims]
    
    # Validate citation accuracy
    accurate_citations = []
    for claim, citation in cited_claims.items():
        source = retrieve_source(citation, knowledge_base)
        if source and source.supports(claim):
            accurate_citations.append((claim, citation))
    
    citation_accuracy = len(accurate_citations) / len(cited_claims) if cited_claims else 0
    attribution_coverage = len(cited_claims) / len(claims) if claims else 0
    
    # Measure retrieval precision
    retrieval_precision = calculate_retrieval_precision(citations, knowledge_base)
    
    return {
        "citation_accuracy": citation_accuracy,
        "retrieval_precision": retrieval_precision,
        "attribution_coverage": attribution_coverage,
        "cited_claims": list(cited_claims.keys()),
        "uncited_claims": uncited_claims
    }
```

**See**: `docs/attribution-verification.md` for complete verification system.
