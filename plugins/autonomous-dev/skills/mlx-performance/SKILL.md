---
name: MLX Performance
version: 1.0.0
type: knowledge
description: MLX distributed training, RDMA, batch optimization
keywords: [mlx, rdma, distributed, batch, performance]
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

### RDMA Networking

- Red Hat OpenShift AI 2.19+
- NCCL + InfiniBand
- Speedup: 2-10x vs TCP/IP

### FlashRecovery

- Recovery: 150s for 4,800 devices
- Async checkpoints + compression

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

- `docs/mlx-distributed.md` - MLX setup
- `docs/rdma-networking.md` - RDMA config
- `docs/batch-optimization.md` - Batch tuning
- `docs/flash-recovery.md` - Checkpoints

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
