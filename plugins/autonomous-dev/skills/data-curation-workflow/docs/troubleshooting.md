# Troubleshooting

Common issues and solutions for the data curation pipeline.

## Stage-Specific Issues

### Stage 1: Extract

**Issue**: No data extracted
```
Error: No valid examples found in input directory
```

**Solutions**:
1. Check input file formats (JSONL, Parquet, CSV supported)
2. Verify file permissions
3. Check for schema mismatches

```bash
# Validate input format
head -1 input.jsonl | python -m json.tool
```

---

### Stage 2: Prefilter (KenLM)

**Issue**: KenLM model not found
```
Error: KenLM model not found at models/kenlm.bin
```

**Solution**: Download or train KenLM model
```bash
# Download pre-trained model
wget https://huggingface.co/kenlm/models/english.bin -O models/kenlm.bin

# Or train custom model
kenlm/build/bin/lmplz -o 5 <corpus.txt >model.arpa
kenlm/build/bin/build_binary model.arpa model.bin
```

**Issue**: Memory error with large dataset
```
Error: MemoryError during perplexity calculation
```

**Solution**: Reduce batch size
```bash
python -m realign.data.kenlm_filter --batch-size 1000  # Default: 10000
```

---

### Stage 3: Score

**Issue**: API rate limits
```
Error: Rate limit exceeded for anthropic/claude-3.5-sonnet
```

**Solutions**:
1. Reduce batch size
2. Add retry logic with backoff
3. Use cached scores

```python
# Enable caching
scorer = MultiDimensionalScorer(cache_path="scores_cache.json")
```

**Issue**: Scoring timeout
```
Error: Timeout after 60s for batch scoring
```

**Solution**: Increase timeout or reduce batch size
```python
scorer = FastIFDScorer(timeout=120, batch_size=50)
```

---

### Stage 4: Deduplicate

**Issue**: Bloom filter memory error
```
Error: Cannot allocate 8GB for Bloom filter
```

**Solutions**:
1. Increase false positive rate (reduces memory)
2. Process in chunks

```python
# Higher FPR = less memory
dedup = BloomDeduplicator(
    expected_items=100_000_000,
    false_positive_rate=0.05  # 5% instead of 1%
)  # ~500MB instead of 1GB
```

**Issue**: Too many duplicates removed
```
Warning: 50% of data removed as duplicates
```

**Solutions**:
1. Check if data is actually duplicated
2. Adjust similarity threshold for fuzzy dedup

```python
# More permissive threshold
dedup = MinHashDeduplicator(threshold=0.95)  # Default: 0.85
```

---

### Stage 5: Decontaminate

**Issue**: Benchmark data not loaded
```
Error: Benchmark 'mmlu' not found
```

**Solution**: Download benchmark data
```bash
python -m realign.data.download_benchmarks --benchmarks mmlu,gsm8k,humaneval
```

**Issue**: Too much data removed as contaminated
```
Warning: 20% removed as benchmark contamination
```

**Solutions**:
1. Check n-gram size (13 is standard, higher = less aggressive)
2. Check threshold (0.1 = 10% overlap max)

```python
# Less aggressive decontamination
decontam = BenchmarkDecontaminator(
    ngram_size=20,    # Higher = fewer matches
    threshold=0.15    # Allow up to 15% overlap
)
```

---

### Stage 6: Filter

**Issue**: Too much data filtered out
```
Warning: Only 30% of data passing quality threshold
```

**Solutions**:
1. Lower quality thresholds
2. Check quality score distribution first

```bash
# Analyze distribution before filtering
python -m realign.data.analyze --input scored.jsonl --histogram quality_score
```

---

### Stage 7: Generate

**Issue**: DPO pairs have low gap
```
Warning: 40% of DPO pairs below minimum gap threshold
```

**Solutions**:
1. Lower minimum gap requirement
2. Regenerate with different temperature

```python
# Lower gap threshold
generator = RefusalDPOPairGenerator(min_gap=2.0)  # Default: 3.0
```

**Issue**: RLVR verification failing
```
Error: Verifier returned error for 30% of traces
```

**Solutions**:
1. Check verifier configuration
2. Review domain-specific verification rules
3. Increase timeout for complex verifications

---

### Stage 8: Mix

**Issue**: Imbalanced domain distribution
```
Warning: Domain 'code' underrepresented (5% vs target 25%)
```

**Solution**: Adjust weights or use domain-balanced curriculum
```python
mixer = DatasetMixer(curriculum="domain-balanced")
```

---

### Stage 9: Validate

**Issue**: Validation failures
```
Error: 5% of data failed format validation
```

**Solution**: Run format fixer
```bash
python -m realign.data.fix_format --input mixed.jsonl --output fixed.jsonl
```

**Issue**: Poisoning detected
```
CRITICAL: Potential data poisoning detected (confidence: 0.92)
```

**Actions**:
1. DO NOT use the dataset for training
2. Review flagged examples manually
3. Trace back to source data
4. Re-run pipeline with clean data

---

## General Issues

### Pipeline Crashes

**Solution**: Resume from checkpoint
```python
checkpoint = CheckpointManager("pipeline_checkpoint.json")
resume_stage = checkpoint.get_resume_stage()
pipeline.run(start_stage=resume_stage)
```

### Out of Memory

**Solution**: Process in streaming mode
```bash
python -m realign.data.pipeline \
  --streaming \
  --chunk-size 10000 \
  --input large_dataset.jsonl
```

### Slow Processing

**Solutions**:
1. Enable multiprocessing
2. Use GPU acceleration for scoring
3. Reduce batch size for API calls

```bash
python -m realign.data.pipeline \
  --workers 8 \
  --gpu \
  --input data.jsonl
```

---

## Getting Help

1. Check logs: `logs/pipeline_YYYYMMDD.log`
2. Review checkpoint: `checkpoint.json`
3. Run diagnostics: `python -m realign.data.diagnose`
4. See `data-curator` agent for automated pipeline orchestration
