---
name: Data Distillation
version: 1.0.0
type: knowledge
description: IFD methodology, KenLM filtering, deduplication
keywords: [ifd, kenlm, distillation, deduplication]
auto_activate: true
---

# Data Distillation

High-quality training data through IFD and KenLM filtering.

## When Activates

IFD scoring, KenLM filtering, deduplication, training data prep

---

## Core Concepts

### IFD (Instruction-Following Data)

Quality thresholds:
- High: 0.8+
- Medium: 0.6-0.8
- Low: <0.6

### KenLM Perplexity Filtering

- **Speedup**: 45-100x vs model-based
- **Retention**: 5-10% (highest quality)
- **Threshold**: 0.6-0.8

### Deduplication

- Exact: Remove exact duplicates
- Near: MinHash/LSH (0.9+ similarity)
- Semantic: Embedding-based

---

## Quick Reference

| Task | Tool | Threshold |
|------|------|-----------|
| IFD scoring | `calculate_ifd_score()` | 0.6+ |
| Perplexity | KenLM | 0.6-0.8 |
| Dedup | MinHash/LSH | 0.9+ |

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
- `training_metrics.py` library

---

## Key Takeaways

1. IFD 0.6+ threshold
2. KenLM 45-100x speedup
3. Retain 5-10% highest quality
4. Pipeline: IFD → KenLM → Dedup
