---
name: MLX Performance
version: 3.0.0
type: knowledge
description: MLX distributed training, RDMA, hardware constraints, full fine-tuning feasibility, parallelism matrix
keywords: [mlx, rdma, distributed, batch, performance, realign, full-finetune, apple-silicon]
auto_activate: false
---

# MLX Performance

Distributed training with MLX, RDMA, hardware planning, full fine-tuning feasibility.

## When Activates

MLX distributed, RDMA config, batch optimization, checkpointing, training hardware planning, model size feasibility

---

## Core Concepts

### MLX Distributed (Aug 2025+)

- `mlx.launch`: Multi-GPU launcher
- `all_reduce_grads`: Gradient sync
- Unified memory: Efficient CPU-GPU
- MLX env vars: `MLX_RANK`, `MLX_WORLD_SIZE`, `MLX_HOSTFILE` (Issue #279)

### Full Fine-Tuning Memory (bf16)

Formula: `params × 2B (weights) + params × 2B (grads) + params × 8B (Adam m+v in fp32) + activations`

| Model | Weights | Grads | Adam | ~Activations | Total | M3 Ultra (512GB)? | M4 Max (128GB)? |
|-------|---------|-------|------|-------------|-------|-------------------|-----------------|
| **4B** | 8 GB | 8 GB | 32 GB | ~10 GB | ~58 GB | Yes | **Yes (validated, 41GB @ 4096 ctx)** |
| 7B | 14 GB | 14 GB | 56 GB | ~20 GB | ~104 GB | Yes | **No (GPU Timeout even with grad-checkpoint)** |
| 14B | 28 GB | 28 GB | 112 GB | ~30 GB | **~198 GB** | **Yes (comfortable)** | No |
| 30B dense | 60 GB | 60 GB | 240 GB | ~50 GB | **~410 GB** | Tight, needs grad checkpoint | No |
| **32B dense** | 65 GB | 65 GB | 261 GB | ~57 GB | **~448 GB** | **Yes with --grad-checkpoint (~320GB)** | No |
| 40B+ | 80+ GB | 80+ GB | 320+ GB | ~60+ GB | 540+ GB | No | No |

**Max full FT on M3 Ultra (512GB)**: 32B dense with `--grad-checkpoint` (~320GB, ~190GB headroom). **Sweet spot: 14B** (comfortable headroom).

**M4 Max (128GB) limitation**: GPU Timeout on 4B+ full FT. Root cause: **Metal's hardcoded ~5s watchdog timer** — a single forward pass with 4B+ full FT params exceeds it on M4 Max (NOT a memory issue, 17.6GB on 128GB machine). No software workaround exists. mlx-lm 0.30.2 already has per-batch `mx.eval()` and `stream=mx.cpu` fixes — the individual `loss(model, *batch)` call itself takes >5s. Options: M3 Ultra solo, distributed LoRA instead of full FT, or smaller models (≤1.5B might work).

### Validated Configurations (Feb 2026)

| Setup | Config | Speed | Memory | Stability |
|-------|--------|-------|--------|-----------|
| 4B full FT, distributed (ring) | M3 Ultra + M4 Max | 0.22 it/sec | 17.6GB | **CRASHES on validation** |
| 4B full FT, solo M3 Ultra | 4096 ctx, bs=4 | 0.045 it/sec | 41GB | **STABLE** |
| 4B full FT, solo M3 Ultra | 2048 ctx, bs=4 | 0.08 it/sec | 25.4GB | **STABLE** |

**Conclusion**: Distributed full FT is unusable with M4 Max (validation always crashes). Use M3 Ultra solo for all full FT.

### max_seq_length Tradeoff

| Seq Length | Memory | Speed | Data Coverage |
|------------|--------|-------|---------------|
| 2048 | 25GB | 0.08 it/sec | Truncates ~10% examples |
| 4096 | 41GB | 0.045 it/sec | Captures most examples |

Increasing `batch_size` does NOT help — tokens/sec stays constant (~340 tok/s on M3 Ultra).

### MLX Parallelism Support Matrix

| Parallelism | Inference | Training | Package |
|-------------|-----------|----------|---------|
| **Data parallel** | Yes | **Yes** | `mlx.distributed` + `jaccl` backend |
| **Tensor parallel** | Yes | Experimental (no standard workflow) | `mlx.nn.AllToShardedLinear`, `ShardedToAllLinear` |
| **Pipeline parallel** | Yes | **No** full FT (LoRA only via mattbeton/mlx-train) | `mlx_sharding` (inference), `mattbeton/mlx-train` (LoRA training) |

**No ZeRO/FSDP equivalent exists for MLX.** No optimizer state sharding across machines.

#### Key Packages

| Package | Training? | Parallelism | Full FT? |
|---------|-----------|-------------|----------|
| **mlx-lm** (official, v0.30+) | Yes | Data parallel | **Yes** (`--fine-tune-type full`) |
| **mattbeton/mlx-train** | Yes (beta, 39 commits) | Pipeline + Data + Tensor | **No** — calls `model.freeze()`, LoRA adapters only |
| mzbac/mlx_sharding | Inference only | Pipeline | N/A |
| exo | Inference only | Pipeline (P2P) | N/A |

#### Production CLI: `realign train` (wraps mlx-lm)

**Always use `realign train`** — it wraps mlx-lm, handles format conversion, config building, and metric parsing:

```bash
# SFT (Phase 1)
realign train --method full-ft --fine-tune-type full \
  --model ~/Models/qwen3-32b-base \
  --data data/3_training_ready/sft/train.jsonl \
  --output models/qwen3-32b-full-ft/sft \
  --batch-size 2 --learning-rate 1e-5 --epochs 1

# DPO (Phase 3, after RLVR)
realign train --method dpo --fine-tune-type full \
  --model models/qwen3-32b-full-ft/sft \
  --data data/3_training_ready/dpo/train.jsonl \
  --output models/qwen3-32b-full-ft/dpo \
  --batch-size 2 --learning-rate 5e-6 --epochs 1
```

#### Raw mlx-lm (distributed only)

```bash
mlx.launch --hostfile hostfile.txt --backend jaccl \
  python -m mlx_lm.lora \
    --model Qwen2.5-14B \
    --fine-tune-type full \
    --data data/3_training_ready/sft \
    --batch-size 2 \
    --iters 5000 \
    --grad-checkpoint \
    --learning-rate 1e-5
```

Internally uses `mlx.nn.utils.average_gradients()` for all-reduce across nodes.

**Constraint**: Data parallelism requires each machine to hold full model + optimizer in memory. Only ≤4B fits on both M4 Max + M3 Ultra simultaneously for distributed training (7B causes GPU Timeout on M4 Max).

#### Hostfile Format

Hostfile is a JSON array (NOT the old dict format):
```json
[{"ssh": "user@host", "ips": ["192.168.1.10"]}]
```

### RDMA Networking

- **Apple Silicon (macOS 26.2+)**: RDMA over Thunderbolt 5 via JACCL backend
  - ~50μs latency (vs 300μs TCP Ring) — 6x improvement
  - ~5 GB/s bandwidth (vs ~800 GB/s memory bandwidth — network is 160x slower)
  - Requires: `rdma_ctl enable` (one-time, Recovery OS), Thunderbolt 5 cable
  - Env: `MLX_METAL_FAST_SYNCH=1`, `TOKENIZERS_PARALLELISM=false`
- **Enterprise**: Red Hat OpenShift AI 2.19+, NCCL + InfiniBand, GPU Direct RDMA

### FlashRecovery

- Recovery: 150s for 4,800 devices
- Async checkpoints + compression
- Storage backends: GCS, S3, NFS

### ReAlign Patterns (Issues #279-#284)

- **Issue #279**: MLX native env vars (MLX_RANK, MLX_HOSTFILE)
- **Issue #280**: Hardware calibration for workload distribution
- **Issue #281**: Worker consistency validation (SHA256, Byzantine detection)
- **Issue #282**: 8-point pre-flight checklist
- **Issue #283**: distributed-training-coordinator enhancements (5 new phases)

---

## Training Speed Optimizations (Validated Feb 2026)

### Gradient Accumulation (FREE speedup)
```
--grad-accumulation-steps 8  → effective batch = batch_size × 8
```
- No additional memory
- More stable gradients, faster convergence
- Reduce total iters proportionally (50K → 20K with 8x accumulation)

### Learning Rate Scaling with Batch Size
When increasing effective batch via grad accumulation:
- Linear scaling: `lr × accumulation_steps` (aggressive)
- Sqrt scaling: `lr × sqrt(accumulation_steps)` (**RECOMMENDED** for full FT)
- Example: base lr 1e-5, accum 8 → lr = 1e-5 × sqrt(8) = 2.8e-5

### Validation Cost Reduction
Each validation pass costs 70-200s depending on val_batches and seq_length:
- `--steps-per-eval 5000` (validate every 5K iters, not every 200)
- `--val-batches 10` (lighter validation, still meaningful signal)
- On M4 Max: validation **ALWAYS** crashes with 4B+ full FT (skip entirely)

### What Does NOT Help
- **Increasing batch_size**: tokens/sec stays CONSTANT on M3 Ultra (~340 tok/s)
  - bs=4: 0.08 it/sec, 340 tok/s, 25GB
  - bs=16: 0.037 it/sec, 330 tok/s, 57GB
  - Use grad accumulation instead (same effect, no extra memory)
- **Mixed precision**: MLX already uses bf16 by default
- **Quantized full FT**: Not supported in MLX (QLoRA is LoRA only)

### Optimal Config Template (M3 Ultra Solo, 4B Full FT)
```bash
--batch-size 4
--grad-accumulation-steps 8     # effective batch 32
--learning-rate 2.8e-5          # sqrt scaled from 1e-5
--iters 20000                   # reduced from 50K (8x larger effective batch)
--max-seq-length 4096           # better quality (41GB peak)
--grad-checkpoint               # saves ~15GB memory
--save-every 500                # NEVER > 1000 — we lost 1,780 iters twice
--steps-per-eval 5000           # validate every 5K iters
--val-batches 10                # lighter validation
--num-layers 36                 # MUST match model's num_hidden_layers (check config.json)
```

### num_layers Default Trap (CRITICAL)

mlx-lm defaults `num_layers: 16` even for `--fine-tune-type full`. This means **only the top 16 layers get trained**, NOT the full model.

**For true full FT, ALWAYS pass `--num-layers <total_layers>`**:
```bash
# Check your model's layer count:
python -c "import json; print(json.load(open('config.json'))['num_hidden_layers'])"
# e.g., Qwen3-4B = 36 layers → --num-layers 36
```

**Verification**: After launching, check the "Trainable parameters" line in output:
- Full FT should show **~95-100% trainable** (embeddings may be frozen)
- If it shows ~40-50%, `num_layers` is wrong — **stop and fix immediately**

### Checkpoint Frequency Rule

**NEVER use `--save-every > 1000` for long runs.** We lost 1,780 iterations twice (once with save_every=5000, once with 2000).

Rule of thumb: `save_every = min(1000, iters / 20)`

| Total Iters | save_every |
|-------------|-----------|
| < 5K | 250 |
| 5K-20K | 500 |
| 20K+ | 1000 |

### Pipeline Parallel Full FT (Issue #584)

MattBeton/mlx-train has working pipeline parallel for LoRA. For full FT:
- Skip LoRA injection, save full weights instead of adapters
- Layer split for heterogeneous memory: proportional to available RAM
- M4 Max can handle ~8 layers of 4B full FT (~11GB) — stays under Metal 5s timeout
- M3 Ultra handles remaining layers (e.g., 28 of 36)
- CLI: `--strategy pipeline --layer-split 0-8,8-36`
- 50% bubble overhead with naive scheduling (realistic speedup: 1.3-1.5x, not 2x)

---

## Training Method Decision Tree

```
Data < 100K examples?
├─ Yes → LoRA matches Full FT (research consensus)
│   ├─ Want uncensored baked into weights? → Full FT on base model
│   └─ Want adapter flexibility? → LoRA rank 64
└─ No (100K-858K) → 8B LoRA r64 all layers may beat 4B full FT (95-98% of full FT, 5-10x faster)
    └─ No (1M+) → Full FT on largest model that fits solo on M3 Ultra

Model sizing?
├─ ≤4B → Both machines (but M4 Max can't validate during full FT)
├─ 5-14B → M3 Ultra solo only
└─ 15-32B → M3 Ultra solo with --grad-checkpoint

Need uncensored behavior?
├─ Full FT on base model (no RLHF to fight, uncensored data reshapes weights directly)
└─ OR LoRA rank 64 (still effective for this, faster)
```

### Training Time Estimates (M3 Ultra, 512GB)

| Model | Method | 35K examples | 150K examples |
|-------|--------|-------------|---------------|
| 7B | Full FT | ~1.5 days | ~6 days |
| 14B | Full FT | ~4-5 days | ~2-3 weeks |
| 30B dense | Full FT | ~10-12 days | Months |
| **32B dense** | Full FT (grad ckpt) | ~10-12 days | ~3-4 weeks (1M ex) |
| 30B MoE | LoRA r64 | ~2-3 days | ~1-2 weeks |

---

## Quick Reference

| Feature | Configuration |
|---------|--------------|
| MLX distributed | `mlx.launch` |
| RDMA (Apple) | JACCL backend, macOS 26.2+, Thunderbolt 5 |
| RDMA (Enterprise) | OpenShift 2.19+ |
| FlashRecovery | Async checkpoints |
| Full FT | `realign train --method full-ft` (wraps mlx-lm) |
| Batch size | Critical size tuning |

---

## Progressive Disclosure

**Detailed guides**: See `docs/*.md`

### Core Guides
- `docs/mlx-distributed.md` - MLX setup
- `docs/rdma-networking.md` - RDMA config
- `docs/batch-optimization.md` - Batch tuning
- `docs/flash-recovery.md` - Checkpoints

### Comprehensive Guides
- `docs/multi-node-orchestration.md` - Orchestrating 10+ nodes
- `docs/performance-benchmarking.md` - Measuring RDMA vs TCP/IP speedup

---

## Related

- **python-standards** skill
- **data-distillation** skill
- **training-methods** skill
- **preference-data-quality** skill

---

## Key Takeaways

1. MLX native distributed (Aug 2025+)
2. RDMA: 6x latency improvement (JACCL) but network is 160x slower than memory bandwidth
3. FlashRecovery 150s for 4.8K devices
4. Small batches more robust
5. Apple Silicon unified memory
6. **Training = data parallel only** (each machine needs full model copy)
7. Tensor/pipeline parallel = inference only (can shard post-training for serving)
8. `realign train --method full-ft` is the production path (wraps mlx-lm)
9. 32B dense fits with `--grad-checkpoint` (~320GB); 14B is comfortable sweet spot
10. For <100K examples, LoRA matches Full FT quality — Full FT only wins with 1M+
11. **M4 Max cannot do 4B+ full FT validation** — GPU Timeout, distributed unusable
12. **batch_size increase does NOT speed up** M3 Ultra — use `--grad-accumulation-steps` instead
13. **8B LoRA r64 all layers** achieves 95-98% of full FT at 5-10x faster
