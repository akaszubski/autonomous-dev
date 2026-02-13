---
name: Data Distillation
version: 2.0.0
type: knowledge
description: IFD scoring, quality filtering, training mix assembly, score-based selection
keywords: [ifd, kenlm, distillation, deduplication, training-mix, curation, quality-scoring]
auto_activate: false
---

# Data Distillation & Curation

High-quality training data through IFD scoring, quality filtering, and score-based selection.

## When Activates

IFD scoring, KenLM filtering, deduplication, training data prep, mix assembly, data selection

---

## Core Concepts

### IFD (Instruction-Following Difficulty) — Cherry_LLM Method

`IFD = PPL(response) / PPL(response|instruction)` — higher = more informative

```python
from realign.data.ifd_scorer_fast import FastIFDScorer
scorer = FastIFDScorer()  # Uses Qwen2.5-0.5B-Instruct-4bit, ~25 ex/sec
scored = scorer.score_batch(examples)  # NOTE: method is score_batch(), NOT calculate_ifd()
```

- **Top 20%** by IFD score is the sweet spot for distillation
- Run on both machines in parallel (split data 50/50, merge after)
- Checkpoint every 1000 examples for resume
- **Dependency**: `scikit-learn` required for FastIFDScorer import chain

### KenLM Perplexity Filtering

- **Speedup**: 45-100x vs model-based
- **Retention**: 5-10% (highest quality)
- **Threshold**: 0.6-0.8

### Deduplication

- Exact: Remove exact duplicates
- Near: MinHash/LSH (0.9+ similarity)
- Semantic: Embedding-based

### Multi-Dimensional SFT Scoring

```python
from realign.data.quality.multi_scorer import MultiDimensionalScorer
# Dimensions: factuality (0.4), reasoning (0.3), diversity (0.3)
# Output: quality_composite score (0-1)
```

### Quality Score Fields Reference

| Dataset | Score Key | Scale | Top Selection Threshold |
|---------|-----------|-------|------------------------|
| Dolci general (1.4M) | `quality_score` | 1-10+ | Top 1% ≥ 10.0 |
| Finance SFT (18K IFD-distilled) | `quality_composite` | 0-1 | Top 25% ≥ 0.755 |
| Math/Coding/Tool Use (scored) | `quality_score` | 1-10+ | Top 5K ≥ 9.0-10.0 |
| DPO pairs | `quality_gap` | 0-1 | Top 10% ≥ 0.133 |
| IFD scored | `ifd_score` | float | Top 20% |

### Data Selection Pattern

Always use scores for selection — never train on unscored data:

```python
def top_scored(examples, score_key, n):
    """Select top N examples by score."""
    scored = [(ex, float(ex.get(score_key, 0) or 0)) for ex in examples]
    scored.sort(key=lambda x: -x[1])
    return [ex for ex, _ in scored[:n]]
```

---

## Training Mix Design (Research-Backed)

### Optimal SFT Mix (~35K for LoRA or Full FT under 100K examples)

| Domain | % | Purpose |
|--------|---|---------|
| General | 43% | Prevent catastrophic forgetting |
| Domain specialty | 14% | Core expertise (IFD-distilled) |
| Math | 14% | Reasoning ability |
| Coding | 11% | Code generation |
| Tool Use | 9% | Function calling |
| Calibration | 6% | Anti-hallucination ("I don't know" responses) |
| Uncensored | 3% | Reduce refusals |

### 1M+ Full FT Mix (for baking behavior into weights)

At 1M+ examples, full FT outperforms LoRA. Use `realign train --method full-ft`.

| Domain | Target | Actual (post-dedup) | Source |
|--------|--------|---------------------|--------|
| General | 1.2M (over-select) | ~595K (62%) | dolci_sft_scored — **loses ~19% to dedup** |
| Math | 100K | ~57K (6%) | math_qwen3_scored |
| Coding | 69K | ~69K (7%) | coding_qwen3_scored |
| Tool Use | 90K | ~71K (7.4%) | tool_use_qwen3_scored |
| Finance | 151K combined | ~149K (16%) | finance_sft + curated + books |
| Calibration | all available | ~12K (1.3%) | Domain calibration files |

**Key lessons from 1M assembly**:
- **Over-select general by ~20%** — dolci has ~19% internal dedup rate
- **Uncensored data may overlap with tool_use** — verify before including (100% overlap found in practice)
- **DPO scales with full FT**: 240K pairs used (not capped at 5-20K — saturation guidance applies to LoRA only)
- **RLVR**: ~25K verifiable examples across math/coding/tool_use/finance
- Final mix lands at ~62% general / 38% domain (close to 70/30 target)

### Key Research Findings

- **Quality > Quantity**: 5-10K top-scored examples > 100K unfiltered
- **LoRA vs Full FT thresholds**: See **mlx-performance** skill for model size feasibility
- **DPO saturates** at 5-20K pairs for LoRA; scales to 240K for 1M+ full FT
- **70% general + 30% domain** prevents catastrophic forgetting
- **1 epoch SFT for 1M+, 3 epochs for 35K** — more data = fewer epochs needed
- **Dedup before counting** — always over-select to hit targets after dedup

### Training Phases (Order Matters)

```
Phase 1: SFT (35K-1M, 1-3 epochs) → Learn domain knowledge + general capability
Phase 2: RLVR (10-25K, 1 epoch) → Verifiable reward alignment
Phase 3: DPO (10-240K, 1 epoch) → Preference optimization (last, most fragile)
```

### Production CLI

**Always use `realign train`** — wraps mlx-lm with format conversion, config, and metrics.

For complete training configurations, hardware-specific flags, and batch size guidance, see **mlx-performance** and **training-operations** skills.

---

## Quick Reference

| Task | Tool | Threshold |
|------|------|-----------|
| IFD scoring | `FastIFDScorer.score_batch()` | Top 20% |
| Perplexity | KenLM | 0.6-0.8 |
| Dedup | MinHash/LSH | 0.9+ |
| SFT scoring | `MultiDimensionalScorer` | composite > 0.3 |
| DPO scoring | Heuristic quality scorer | gap ≥ 0.08 |

---

## ReAlign Data Paths

| Data | Path |
|------|------|
| Scored general (1.4M) | `data/2_processed/dolci_qwen3_scored/` |
| Scored math (100K) | `data/2_processed/math_qwen3_scored/` |
| Scored coding (69K) | `data/2_processed/coding_qwen3_scored/` |
| Scored tool_use (90K) | `data/2_processed/tool_use_qwen3_scored/` |
| IFD-distilled finance (18K) | `data/2_processed/ifd_distilled/` |
| Top-quality mix (55K) | `data/3_training_ready/qwen3_30b_top_quality/` |
| Full mix (307K) | `data/3_training_ready/qwen3_30b_full_mix/` |
| **1M full FT mix (1.2M)** | `data/3_training_ready/qwen3_32b_1m_full/` |

---

## Common Pitfalls

- `FastIFDScorer` method is `score_batch()` — NOT `calculate_ifd()`
- `scikit-learn` required for FastIFDScorer import chain
- SSH to M3 Ultra: user is `andrewkaszubski` at `10.55.0.2` — NOT `akaszubski`
- Both machines need `.venv/bin/python` — system python doesn't have MLX
- RLVR schema varies by domain — always normalize before mixing (`problem/answer` vs `verification_question/expected_verification`)

### Training Data Validation (BEFORE Launch)

Check sequence length distribution BEFORE training, not after seeing truncation warnings:
```bash
# Check token length distribution
python -c "
import json
lens = [len(json.loads(l).get('text','').split()) for l in open('train.jsonl')]
over = sum(1 for l in lens if l > 4096)
print(f'{over}/{len(lens)} ({100*over/len(lens):.0f}%) exceed 4096 tokens')
"
```

- If **>30% of sequences exceed `max_seq_length`**: pre-truncate or increase `max_seq_length`
- Current dataset has many sequences 10K-30K tokens being truncated to 4096 — significant data loss
- Truncation silently discards training signal — always check BEFORE starting

---

## Progressive Disclosure

**Detailed guides**: See `docs/*.md`

- `docs/ifd-methodology.md` - IFD scoring
- `docs/kenlm-filtering.md` - KenLM filtering
- `docs/deduplication.md` - Deduplication

---

## Related

- **python-standards** skill
- **preference-data-quality** skill
- **mlx-performance** skill
- `training_metrics.py` library

---

## Key Takeaways

1. **Score everything, select the best** — don't train on unscored data
2. IFD top 20% + quality_score top N per domain = optimal selection strategy
3. DPO length bias is real — always check if 100% chosen > rejected length
4. Multi-domain mix (70/30 general/domain) prevents catastrophic forgetting
5. Calibration data (5-6%) is critical for anti-hallucination
6. 35K sufficient for LoRA; **1M+ needed for full FT to outperform LoRA**
7. Pipeline: IFD → Quality Score → Top-N Select → Mix → Dedup → Split → Train
8. **Over-select general by ~20%** to compensate for dedup losses
9. **Verify uncensored data isn't a subset** of another domain (tool_use overlap found)
10. **Use `realign train`** CLI — wraps mlx-lm with config/format handling
