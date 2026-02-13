---
name: Training Operations
version: 1.0.0
type: knowledge
description: Training run management, monitoring, crash recovery, hardware-specific configs for MLX fine-tuning
keywords: [training, operations, monitoring, recovery, checkpoint, mlx, fine-tuning]
auto_activate: false
---

# Training Operations

Run management, monitoring, crash recovery, and hardware-specific validated configs for MLX fine-tuning.

## When Activates

Training run start/stop, monitoring, crash recovery, checkpoint management, hardware config selection

---

## Pre-Launch Checklist (MANDATORY)

1. Verify `num_layers` matches model's `num_hidden_layers` (for full FT): `python -c "import json; print(json.load(open('config.json'))['num_hidden_layers'])"`
2. Verify `save_every` ≤ 1000 (rule: `min(1000, iters/20)`)
3. Verify trainable parameter % in first output line (~95-100% for full FT)
4. Verify peak memory is stable (check iter 10-20)
5. Verify loss is decreasing (check iter 50-100)
6. Verify sequence length distribution — if >30% truncated, fix data first

---

## Training Run Management

### Starting a Run

```bash
# Via realign train (RECOMMENDED — wraps mlx-lm, handles format/config/metrics)
realign train --method full-ft --fine-tune-type full \
  --model ~/Models/qwen3-4b-base \
  --data data/3_training_ready/sft/train.jsonl \
  --output models/qwen3-4b-full-ft/sft \
  --batch-size 4 \
  --grad-accumulation-steps 8 \
  --learning-rate 2.8e-5 \
  --iters 20000 \
  --max-seq-length 4096 \
  --grad-checkpoint \
  --num-layers 36 \
  --save-every 500 \
  --steps-per-eval 5000 \
  --val-batches 10

# Background with logging
nohup realign train [args] > data/experiments/run_$(date +%Y%m%d_%H%M).log 2>&1 &
```

### Monitoring a Run

```bash
# Live progress
tail -f data/experiments/run_*.log

# Extract iterations and loss
grep "^Iter" data/experiments/run_*.log | tail -20

# Check GPU memory
python -c "import mlx.core as mx; print(f'{mx.metal.get_active_memory()/1e9:.1f}GB active, {mx.metal.get_peak_memory()/1e9:.1f}GB peak')"

# Check if still running
ps aux | grep mlx_lm | grep -v grep
```

### Resuming from Checkpoint

mlx-lm auto-resumes from the adapter directory if checkpoints exist:
```bash
# Same command as original — it detects existing checkpoints
realign train --method full-ft --fine-tune-type full \
  --model ~/Models/qwen3-4b-base \
  --output models/qwen3-4b-full-ft/sft \  # contains checkpoint files
  [same args as original run]
```

---

## Hardware-Specific Validated Configs

### M3 Ultra (512GB) — Solo, 4B Full FT

| Config | Value | Notes |
|--------|-------|-------|
| batch_size | 4 | tokens/sec constant regardless of batch size |
| grad_accumulation_steps | 8 | effective batch 32, free speedup |
| learning_rate | 2.8e-5 | sqrt scaled from 1e-5 base |
| max_seq_length | 4096 | 41GB peak, captures most examples |
| grad_checkpoint | yes | saves ~15GB |
| num_layers | 36 (match config.json) | CRITICAL: default 16 only trains top layers |
| save_every | 500 | NEVER > 1000 — lost 1,780 iters twice |
| steps_per_eval | 5000 | validate every 5K iters |
| val_batches | 10 | lighter validation |
| **Speed** | 0.045 it/sec (4096 ctx), 0.08 it/sec (2048 ctx) | |
| **Memory** | 41GB (4096 ctx), 25GB (2048 ctx) | |

### M3 Ultra (512GB) — Solo, 14B Full FT

| Config | Value | Notes |
|--------|-------|-------|
| batch_size | 2 | ~198GB total |
| grad_checkpoint | yes | required |
| learning_rate | 1e-5 | |
| max_seq_length | 2048 | 4096 may OOM |
| save_every | 500 | more frequent — longer per iter |

### M3 Ultra (512GB) — Solo, 32B Full FT

| Config | Value | Notes |
|--------|-------|-------|
| batch_size | 2 | ~320GB with grad checkpoint |
| grad_checkpoint | **required** | without: ~448GB (OOM) |
| learning_rate | 1e-5 | |
| max_seq_length | 2048 | 4096 will OOM |
| save_every | 200 | very long per iter |

### M4 Max (128GB) — NOT recommended for full FT

- **GPU Timeout on 4B+ full FT**: Metal's 5s watchdog kills single forward pass (hardware speed limit, not memory)
- No software workaround — mlx-lm 0.30.2 already has fixes, individual `loss()` call exceeds 5s
- Options: M3 Ultra solo, distributed LoRA (adapter-only forward pass is fast), or ≤1.5B models

---

## Crash Recovery Patterns

### GPU Timeout During Validation (M4 Max)
**Symptom**: Process hangs then dies with "GPU Timeout"
**Cause**: Metal's hardcoded ~5s watchdog timer — a single 4B+ full FT forward pass exceeds it on M4 Max. NOT a memory issue (17.6GB on 128GB machine). mlx-lm 0.30.2 already has per-batch `mx.eval()` — the `loss(model, *batch)` call itself takes >5s.
**Fix**: No software workaround. Use M3 Ultra solo, distributed LoRA instead of full FT, or smaller models (≤1.5B might work on M4 Max)

### Only Top Layers Training (num_layers trap)
**Symptom**: Trainable parameters show ~40-50% instead of ~95-100%
**Cause**: mlx-lm defaults `num_layers: 16` even for `--fine-tune-type full`
**Fix**: Always pass `--num-layers <total>` (check `config.json` → `num_hidden_layers`)

### Lost Iterations (checkpoint too infrequent)
**Symptom**: Crash loses hours of training progress
**Cause**: `save_every` set too high (5000 or 2000)
**Fix**: Use `--save-every 500` (max 1000). Rule: `min(1000, iters/20)`

### OOM (Out of Memory)
**Symptom**: Process killed, no error output
**Fix**: Add `--grad-checkpoint`, reduce `--max-seq-length` to 2048, reduce `--batch-size`

### NaN Loss
**Symptom**: Loss becomes NaN after N iters
**Fix**: Reduce learning rate by 2-5x, add warmup steps, check data for anomalies

### Checkpoint Corruption
**Symptom**: Resume fails with shape mismatch or key error
**Fix**: Delete latest checkpoint dir, resume from previous `--save-every` checkpoint

---

## Run Logging

Log training runs to `data/experiments/training_runs.jsonl`:

```json
{
  "run_id": "sft_4b_20260213_1430",
  "model": "qwen3-4b-base",
  "method": "full-ft",
  "hardware": "m3-ultra-512gb",
  "config": {"batch_size": 4, "lr": 2.8e-5, "seq_len": 4096, "grad_accum": 8},
  "started_at": "2026-02-13T14:30:00Z",
  "status": "completed",
  "final_loss": 0.42,
  "iters_completed": 20000,
  "wall_time_hours": 123.5
}
```

---

## Related

- **mlx-performance**: Hardware constraints, memory tables, distributed setup
- **training-methods**: SFT vs DPO vs RLVR methodology
- **data-distillation**: Data preparation for training
- Issue #582: Training observability database (planned)
- Issue #583: realign train CLI options
- Issue #584: Pipeline parallel full FT

---

## Key Takeaways

1. Always use `realign train` — wraps mlx-lm with format/config/metrics handling
2. M3 Ultra solo is the reliable path for full FT (distributed crashes on validation)
3. Use `--grad-accumulation-steps` instead of increasing batch_size (same effect, no extra memory)
4. **Always set `--num-layers` explicitly** — default 16 silently trains only top layers
5. **Always set `--save-every ≤ 1000`** — we lost 1,780 iters twice with higher values
6. **Verify trainable parameters** in first output line — stop immediately if ~40-50%
7. Monitor with `grep "^Iter" log | tail` — simple and effective
