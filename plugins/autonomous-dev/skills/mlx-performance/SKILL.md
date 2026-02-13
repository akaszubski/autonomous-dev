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
| 7B | 14 GB | 14 GB | 56 GB | ~20 GB | ~104 GB | Yes | Yes |
| 14B | 28 GB | 28 GB | 112 GB | ~30 GB | **~198 GB** | **Yes (comfortable)** | No |
| 30B dense | 60 GB | 60 GB | 240 GB | ~50 GB | **~410 GB** | Tight, needs grad checkpoint | No |
| 40B+ | 80+ GB | 80+ GB | 320+ GB | ~60+ GB | 540+ GB | No | No |

**Max full FT on M3 Ultra (512GB)**: ~30B dense. **Sweet spot: 14B** (comfortable headroom).

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

#### mlx-lm Distributed Full Fine-Tuning Command

```bash
mlx.launch --hostfile hostfile.txt --backend jaccl \
  python -m mlx_lm.lora \
    --model Qwen2.5-14B \
    --fine-tune-type full \
    --data data/3_training_ready/qwen3_30b_top_quality/sft \
    --batch-size 2 \
    --iters 5000 \
    --grad-checkpoint \
    --learning-rate 1e-5
```

Internally uses `mlx.nn.utils.average_gradients()` for all-reduce across nodes.

**Constraint**: Data parallelism requires each machine to hold full model + optimizer in memory. Only ≤7B fits on both M4 Max + M3 Ultra simultaneously for distributed training.

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

## Training Method Decision Tree

```
Data < 100K examples?
├─ Yes → LoRA matches Full FT (research consensus)
│   ├─ Want uncensored baked into weights? → Full FT on base model
│   └─ Want adapter flexibility? → LoRA rank 64
└─ No (1M+) → Full FT outperforms LoRA

Model > 14B?
├─ Yes → M3 Ultra only (single machine)
└─ No (≤7B) → Both machines via data parallelism (~1.5x speedup)

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
| 30B MoE | LoRA r64 | ~2-3 days | ~1-2 weeks |

---

## Quick Reference

| Feature | Configuration |
|---------|--------------|
| MLX distributed | `mlx.launch` |
| RDMA (Apple) | JACCL backend, macOS 26.2+, Thunderbolt 5 |
| RDMA (Enterprise) | OpenShift 2.19+ |
| FlashRecovery | Async checkpoints |
| Full FT | `mlx-lm --fine-tune-type full` |
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
8. mlx-lm `--fine-tune-type full` is the production path for full fine-tuning
9. 14B is max comfortable full FT on M3 Ultra (512GB); 30B dense is theoretical max
10. For <100K examples, LoRA matches Full FT quality — Full FT only wins with 1M+
