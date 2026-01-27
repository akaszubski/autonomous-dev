# RDMA (Remote Direct Memory Access) Networking

High-speed networking for distributed training with 2-10x speedup.

## Overview

RDMA provides direct memory access between nodes without CPU involvement, dramatically reducing latency and increasing throughput.

## Benefits

| Metric | TCP/IP | RDMA | Improvement |
|--------|--------|------|-------------|
| Latency | 50-100 μs | 1-5 μs | 10-100x |
| Throughput | 10 Gbps | 100+ Gbps | 10x |
| CPU usage | High | Low | 5-10x |
| Training speedup | 1x | 2-10x | 2-10x |

## Requirements

### Hardware

- **InfiniBand**: Industry standard (Mellanox/NVIDIA)
- **RoCE**: RDMA over Converged Ethernet
- **iWARP**: RDMA over TCP/IP (fallback)

### Software

- **Red Hat OpenShift AI 2.19+**: RDMA support
- **NCCL**: NVIDIA Collective Communications Library
- **RDMA drivers**: OS-level support

## Configuration

### OpenShift AI Setup

```yaml
# Pod specification with RDMA
apiVersion: v1
kind: Pod
metadata:
  name: training-pod
spec:
  containers:
  - name: trainer
    image: mlx-trainer:latest
    resources:
      limits:
        rdma/hca: 1  # Request RDMA device
    env:
    - name: NCCL_IB_DISABLE
      value: "0"  # Enable InfiniBand
    - name: NCCL_NET_GDR_LEVEL
      value: "5"  # GPU Direct RDMA
```

### NCCL Configuration

```bash
# Enable RDMA via environment variables
export NCCL_IB_DISABLE=0           # Enable InfiniBand
export NCCL_NET_GDR_LEVEL=5        # GPU Direct RDMA
export NCCL_IB_HCA=mlx5_0          # RDMA device
export NCCL_SOCKET_IFNAME=eth0     # Fallback interface
```

### MLX with NCCL

```python
import mlx.distributed as dist
import os

# Configure RDMA before initialization
os.environ['NCCL_IB_DISABLE'] = '0'
os.environ['NCCL_NET_GDR_LEVEL'] = '5'

# Initialize distributed context (will use RDMA if available)
dist.init()

# Training loop (RDMA accelerates all_reduce_grads)
for batch in dataloader:
    loss = train_step(model, batch)
    dist.all_reduce_grads(model.parameters())  # RDMA-accelerated

dist.finalize()
```

## Performance Tuning

### NCCL Tuning Parameters

```bash
# Increase buffer sizes for large models
export NCCL_BUFFSIZE=8388608        # 8 MB buffers

# Tune tree/ring algorithms
export NCCL_ALGO=Ring               # Ring algorithm
export NCCL_NTHREADS=4              # Communication threads

# GPU Direct RDMA (bypass CPU)
export NCCL_NET_GDR_LEVEL=5
export NCCL_NET_GDR_READ=1
```

### Verification

```bash
# Check RDMA devices
ibstat

# Test RDMA bandwidth
ib_write_bw

# Verify NCCL RDMA usage
NCCL_DEBUG=INFO python train.py
# Look for: "Using network InfiniBand"
```

## Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| RDMA not detected | Falls back to TCP | Check `ibstat`, verify drivers |
| Low bandwidth | <50 Gbps | Tune NCCL_BUFFSIZE, check network |
| Connection errors | Training hangs | Verify NCCL_IB_HCA, check firewall |
| GPU Direct fails | CPU bottleneck | Set NCCL_NET_GDR_LEVEL=5 |

## Best Practices

1. **Verify RDMA availability**: Run `ibstat` before training
2. **Use NCCL_DEBUG**: Monitor network selection during training
3. **Tune buffer sizes**: Larger models need larger buffers
4. **Enable GPU Direct**: Bypass CPU for maximum performance
5. **Test bandwidth**: Benchmark with `ib_write_bw`

## Fallback Strategy

If RDMA unavailable, NCCL falls back to TCP/IP:

```bash
# Disable RDMA (force TCP/IP)
export NCCL_IB_DISABLE=1

# Use socket interface
export NCCL_SOCKET_IFNAME=eth0
```

## Related

- See `mlx-distributed.md` for MLX setup
- See `flash-recovery.md` for checkpointing
- External: NCCL documentation (NVIDIA)
- External: Red Hat OpenShift AI docs
