---
name: MLX Performance
version: 2.0.0
type: knowledge
description: MLX distributed training, RDMA, batch optimization, ReAlign patterns (Issues #279-#284)
keywords: [mlx, rdma, distributed, batch, performance, realign]
auto_activate: true
---

# MLX Performance

Distributed training with MLX, RDMA, FlashRecovery.

## When Activates

MLX distributed, RDMA config, batch optimization, checkpointing

---

## Core Concepts

### MLX Distributed (Aug 2025+)

- `mlx.launch`: Multi-GPU launcher
- `all_reduce_grads`: Gradient sync
- Unified memory: Efficient CPU-GPU
- MLX env vars: `MLX_RANK`, `MLX_WORLD_SIZE`, `MLX_HOSTFILE` (Issue #279)

### RDMA Networking

- Red Hat OpenShift AI 2.19+
- NCCL + InfiniBand
- Speedup: 2-10x vs TCP/IP
- GPU Direct RDMA: Bypass CPU

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

## Quick Reference

| Feature | Configuration |
|---------|--------------|
| MLX distributed | `mlx.launch` |
| RDMA | OpenShift 2.19+ |
| FlashRecovery | Async checkpoints |
| Batch size | Critical size tuning |

---

## Progressive Disclosure

**Detailed guides**: See `docs/*.md`

### Core Guides
- `docs/mlx-distributed.md` - MLX setup
- `docs/rdma-networking.md` - RDMA config
- `docs/batch-optimization.md` - Batch tuning
- `docs/flash-recovery.md` - Checkpoints

### Comprehensive Guides (NEW)
- `docs/multi-node-orchestration.md` - Orchestrating 10+ nodes
- `docs/performance-benchmarking.md` - Measuring RDMA vs TCP/IP speedup

---

## Related

- **python-standards** skill
- **data-distillation** skill

---

## Key Takeaways

1. MLX native distributed (Aug 2025+)
2. RDMA 2-10x speedup
3. FlashRecovery 150s for 4.8K devices
4. Small batches more robust
5. Apple Silicon unified memory
