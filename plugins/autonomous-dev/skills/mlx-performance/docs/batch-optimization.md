# Batch Size Optimization

Find optimal batch size for memory efficiency and training stability.

## Overview

Batch size affects:
- **Memory usage**: Larger batches use more GPU memory
- **Training stability**: Smaller batches more robust to hyperparameters
- **Throughput**: Larger batches faster per-sample

## Critical Batch Size

The "critical batch size" is where:
- Larger batches don't improve generalization
- Memory usage becomes prohibitive
- Training becomes unstable

**Finding critical size**:
1. Start small (32-64)
2. Double until memory fills (64 → 128 → 256 → 512)
3. Measure validation performance
4. Select size where performance plateaus

## Batch Size vs Model Quality

Research shows smaller batches often better:

| Batch Size | Generalization | Training Time | Memory |
|------------|----------------|---------------|--------|
| 32 | Best | Slow | Low |
| 128 | Good | Medium | Medium |
| 512 | Acceptable | Fast | High |
| 2048+ | Poor | Very Fast | Very High |

**Key insight**: Small batches (~32-128) more robust to learning rate, regularization choices.

## Scaling Rules

### Linear Scaling Rule

When increasing batch size, scale learning rate proportionally:

```python
# Baseline
batch_size = 64
lr = 0.001

# Scaled (4x batch)
batch_size = 256
lr = 0.004  # 4x learning rate
```

### Gradual Warmup

For large batches, gradually increase learning rate:

```python
def warmup_lr(epoch, warmup_epochs=5, target_lr=0.01):
    """Linear warmup for first N epochs."""
    if epoch < warmup_epochs:
        return target_lr * (epoch + 1) / warmup_epochs
    return target_lr
```

## Gradient Accumulation

Simulate large batches without memory cost:

```python
import mlx.core as mx

def train_with_accumulation(model, dataloader, accumulation_steps=4):
    """Accumulate gradients over multiple mini-batches."""
    optimizer.zero_grad()

    for i, batch in enumerate(dataloader):
        logits = model(batch['x'])
        loss = loss_fn(logits, batch['y'])

        # Scale loss by accumulation steps
        loss = loss / accumulation_steps
        loss.backward()

        if (i + 1) % accumulation_steps == 0:
            # Update weights after accumulating gradients
            optimizer.step()
            optimizer.zero_grad()
```

**Effective batch size** = `mini_batch_size × accumulation_steps`

## Memory Profiling

### Check GPU Memory

```python
import mlx.metal as metal

def profile_memory(model, batch_size):
    """Profile GPU memory usage for batch size."""
    # Allocate batch
    x = mx.random.normal((batch_size, 784))

    # Forward pass
    logits = model(x)

    # Check memory
    used = metal.device_memory_used()
    total = metal.device_memory_available()

    print(f"Batch {batch_size}: {used / 1e9:.2f} GB / {total / 1e9:.2f} GB")

# Find maximum batch size
for batch_size in [32, 64, 128, 256, 512]:
    try:
        profile_memory(model, batch_size)
    except MemoryError:
        print(f"OOM at batch size {batch_size}")
        break
```

## Best Practices

1. **Start small**: Begin with batch size 32-64
2. **Scale conservatively**: Double until hitting memory limits
3. **Use warmup**: Gradual LR increase for large batches
4. **Consider generalization**: Smaller batches often generalize better
5. **Profile memory**: Monitor GPU utilization

## Distributed Batch Scaling

With N GPUs, scale batch size accordingly:

```python
# Single GPU
batch_size_per_gpu = 64

# 4 GPUs distributed
total_batch_size = batch_size_per_gpu * 4  # 256
```

**Learning rate scaling**: Scale proportionally with total batch size

## Troubleshooting

| Issue | Symptom | Solution |
|-------|---------|----------|
| OOM errors | Training crashes | Reduce batch size or use gradient accumulation |
| Training unstable | Loss spikes | Reduce batch size or increase warmup |
| Slow convergence | Many epochs needed | Increase batch size (with LR scaling) |
| Poor generalization | Low val accuracy | Reduce batch size |

## Distributed Training Coordinator Integration

The `distributed-training-coordinator` agent provides automated batch optimization:

### Batch Configuration Output

The coordinator generates JSON output with optimized batch settings:

```json
{
  "batch_configuration": {
    "per_gpu_batch_size": 64,
    "total_batch_size": 512,
    "gradient_accumulation_steps": 1,
    "learning_rate": 0.004,
    "warmup_epochs": 5
  }
}
```

### Mapping to Optimization Strategies

| Coordinator Output | Optimization Strategy | Implementation |
|--------------------|-----------------------|----------------|
| `per_gpu_batch_size` | Memory-constrained batch size | Start small, double until OOM |
| `gradient_accumulation_steps` | Simulate larger batches | Accumulate gradients over N steps |
| `learning_rate` | Scaled LR for batch size | Linear scaling rule |
| `warmup_epochs` | Large batch stabilization | Gradual LR increase |

### Hardware Calibration Integration

The coordinator measures actual hardware performance and adjusts batch sizes:

```json
{
  "hardware_calibration": {
    "measured_performance": {
      "worker-0": 0.85,
      "worker-1": 0.85,
      "worker-2": 0.85,
      "worker-3": 0.85
    },
    "workload_distribution": {
      "worker-0": 0.25,
      "worker-1": 0.25,
      "worker-2": 0.25,
      "worker-3": 0.25
    }
  }
}
```

**Key Insights**:
- **Equal performance**: Machines show equal throughput (~0.85 ex/s per worker)
- **Overhead-bound pipeline**: Bottlenecked by I/O, synchronization, not compute
- **Typical speedup**: 1.2-1.8x for 4 workers (not linear due to overhead)
- **Expected overhead**: <105s per epoch

### Using Coordinator Output

```python
import json
from pathlib import Path

# Load coordinator output
with open("training_plan.json") as f:
    plan = json.load(f)

# Extract batch configuration
batch_config = plan["batch_configuration"]
per_gpu_batch = batch_config["per_gpu_batch_size"]
accumulation_steps = batch_config["gradient_accumulation_steps"]
learning_rate = batch_config["learning_rate"]

# Apply to training
effective_batch = per_gpu_batch * accumulation_steps * num_gpus
print(f"Effective batch size: {effective_batch}")
print(f"Learning rate: {learning_rate}")
```

## Related

- See `mlx-distributed.md` for multi-GPU training
- See `flash-recovery.md` for checkpointing large models
- See `multi-node-orchestration.md` for coordinator patterns
- External: "On Large-Batch Training for Deep Learning" (Keskar et al.)
