# MLX Distributed Training

Apple's MLX framework for distributed training on Apple Silicon.

## Overview

MLX provides native distributed training support (August 2025+) with:
- Simple launcher (`mlx.launch`)
- Gradient synchronization (`all_reduce_grads`)
- Unified memory architecture
- Apple Silicon GPU optimization

## Basic Setup

### Single GPU Training

```python
import mlx.core as mx
import mlx.nn as nn

# Define model
model = nn.Linear(784, 10)

# Training loop
for batch in dataloader:
    x, y = batch
    logits = model(x)
    loss = nn.losses.cross_entropy(logits, y)

    # Backward pass
    loss.backward()

    # Update weights
    optimizer.step()
```

### Multi-GPU Training (Distributed)

```python
import mlx.core as mx
import mlx.nn as nn
import mlx.distributed as dist

def train_step(model, batch):
    x, y = batch
    logits = model(x)
    loss = nn.losses.cross_entropy(logits, y)

    # Backward pass
    loss.backward()

    # Synchronize gradients across GPUs
    dist.all_reduce_grads(model.parameters())

    return loss

# Launch distributed training
# Command: mlx.launch --gpus 4 train.py
if __name__ == "__main__":
    dist.init()  # Initialize distributed context
    model = nn.Linear(784, 10)

    for batch in dataloader:
        loss = train_step(model, batch)

    dist.finalize()  # Cleanup
```

## Launcher Usage

### mlx.launch Command

```bash
# Single node, 4 GPUs
mlx.launch --gpus 4 train.py

# Multi-node, 8 GPUs per node, 2 nodes
mlx.launch --gpus 8 --nodes 2 --node-rank 0 train.py
```

### Environment Variables

```bash
# Distributed configuration
export MLX_WORLD_SIZE=4       # Total number of processes
export MLX_LOCAL_RANK=0       # GPU index on this machine
export MLX_GLOBAL_RANK=0      # Process index across all machines

# MLX native environment variables (Issue #279)
export MLX_RANK=0             # Process rank (0-N), alternative to MLX_GLOBAL_RANK
export MLX_HOSTFILE=/path/to/hostfile  # Path to hostfile for multi-node training
export MLX_METAL_FAST_SYNCH=1 # Enable faster GPU synchronization on Apple Silicon
```

## Gradient Synchronization

### all_reduce_grads

```python
# Automatic gradient synchronization
dist.all_reduce_grads(model.parameters())

# Manual control
for param in model.parameters():
    if param.grad is not None:
        param.grad = dist.all_reduce(param.grad, op='sum')
        param.grad /= dist.get_world_size()
```

## Unified Memory Benefits

MLX's unified memory architecture:
- **Zero-copy CPU-GPU transfer**: No explicit data movement
- **Automatic memory management**: MLX handles allocation
- **Efficient for large models**: Share memory between CPU and GPU

## Best Practices

1. **Use mlx.launch**: Simplest way to distribute
2. **Synchronize gradients**: Call all_reduce_grads after backward pass
3. **Balance batch size**: Scale linearly with GPU count
4. **Monitor GPU utilization**: Use `mlx.metal.device_memory()`
5. **Checkpoint regularly**: Save model state for recovery

## Performance Tips

- **Batch size scaling**: 4 GPUs = 4x batch size
- **Learning rate scaling**: Scale LR proportionally with batch size
- **Gradient accumulation**: For large models that don't fit
- **Mixed precision**: Use float16 for faster training

## Multi-Node Orchestration

For distributed training across 10+ nodes, MLX provides native multi-node support through hostfile configuration and environment variables.

### Hostfile Configuration

```bash
# hostfile format: one host per line, optionally with process count
# /path/to/hostfile:
node1.example.com:4
node2.example.com:4
node3.example.com:4
node4.example.com:4
```

### Multi-Node Launch

```bash
# Launch multi-node training with hostfile
export MLX_HOSTFILE=/path/to/hostfile
mlx.launch --gpus 4 train.py

# Alternatively, specify hostfile in command
mlx.launch --gpus 4 --hostfile /path/to/hostfile train.py
```

### Integration with distributed-training-coordinator

The `distributed-training-coordinator` agent automates multi-node setup:
- Generates hostfile from available nodes
- Validates worker consistency before training
- Performs hardware calibration for workload distribution
- Runs pre-flight checklist (8 validation checks)
- Monitors training progress across all nodes

See comprehensive guide: `multi-node-orchestration.md`

## Related

- See `batch-optimization.md` for batch size tuning
- See `flash-recovery.md` for checkpointing
- See `multi-node-orchestration.md` for orchestrating 10+ nodes
- See `rdma-networking.md` for RDMA configuration
- External: MLX documentation (ml-explore/mlx)
