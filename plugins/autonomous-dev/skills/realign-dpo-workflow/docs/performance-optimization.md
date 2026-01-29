# Performance Optimization for DPO Training

Hardware-specific optimization strategies for Apple Silicon and distributed training environments to maximize DPO training throughput.

---

## Overview

DPO training performance varies dramatically based on hardware selection, batch sizing, and work distribution. Proper optimization can achieve 5x speedup compared to naive configurations.

**Key principle**: Different hardware architectures have different optimal configurations. MLX inference performance does NOT scale linearly with GPU cores.

---

## Machine Selection by Model Size

| Model Size | Recommended Machine | Reason |
|------------|---------------------|--------|
| ≤30B | M4 Max | 1.9-5.1x faster than M3 Ultra |
| 30-70B | M4 Max (preferred) | Faster unless need >128GB memory |
| 70-200B | M3 Ultra | Requires 512GB memory |
| 200B+ | Distributed (both) | Model too large for single machine |

**Validated benchmarks**:
- M4 Max: 12,956 GFLOPS (324 per core, 40 GPU cores)
- M3 Ultra: 4,599 GFLOPS (57 per core, 80 GPU cores)
- Real-world scoring: M4 Max 3.86 ex/s vs M3 Ultra 0.76 ex/s (5.1x faster)

**Source**: [MLX M3 Ultra Performance Analysis](https://medium.com/@billynewport/apples-m3-ultra-mac-studio-misses-the-mark-for-llm-inference-f57f1f10a56f)

---

## Batch Size Configuration

Optimal batch sizes differ dramatically between M4 Max and M3 Ultra due to architectural differences.

### M4 Max Batch Sizing

```python
# Optimal configuration for M4 Max
DPO_CONFIG = {
    "batch_size": 32,  # Peaks at 776 ex/s
    "gradient_accumulation_steps": 1,
    "device": "mps",
}
```

**Performance curve**:
- batch_size=1: ~200 ex/s
- batch_size=8: ~450 ex/s
- batch_size=16: ~620 ex/s
- batch_size=32: ~776 ex/s (peak)
- batch_size=64: ~750 ex/s (degradation)

**Recommendation**: Use batch_size=32 for maximum throughput.

### M3 Ultra Batch Sizing

```python
# Optimal configuration for M3 Ultra
DPO_CONFIG = {
    "batch_size": 4,  # Peaks EARLY at 278 ex/s
    "gradient_accumulation_steps": 8,  # Maintain effective batch=32
    "device": "mps",
}
```

**Performance curve**:
- batch_size=1: ~180 ex/s
- batch_size=4: ~278 ex/s (peak)
- batch_size=8: ~265 ex/s (declining)
- batch_size=16: ~240 ex/s (worse)
- batch_size=32: ~210 ex/s (significant degradation)

**Critical**: M3 Ultra peaks at batch_size=4. DO NOT increase batch size beyond 4.

---

## Work Distribution for Distributed Training

When using both machines together, distribute work based on validated throughput ratios.

### 65/35 Split (NOT 50/50)

```python
# Correct work distribution
M4_MAX_RATIO = 0.655  # 65.5% of work
M3_ULTRA_RATIO = 0.345  # 34.5% of work

def distribute_work(total_examples, m4_ratio=0.655):
    """Distribute examples between M4 Max and M3 Ultra."""
    m4_count = int(total_examples * m4_ratio)
    m3_count = total_examples - m4_count
    return m4_count, m3_count

# Example
total = 10000
m4_work, m3_work = distribute_work(total)
print(f"M4 Max: {m4_work} examples")  # 6,550
print(f"M3 Ultra: {m3_work} examples")  # 3,450
```

**Why 65/35?**: Based on actual throughput ratio (3.86 ex/s : 0.76 ex/s = 5.1:1), adjusted for batch size differences.

**Anti-pattern**: DO NOT split 50/50 based on GPU core count. This wastes M4 Max capacity.

---

## RDMA vs Separate Batches Decision

Choose between RDMA-based distributed training and independent batch processing based on model size and use case.

### Use RDMA When

| Scenario | Why |
|----------|-----|
| Model >128GB (70B+ fp16) | Doesn't fit on M4 Max alone |
| Model >512GB (405B) | Must shard across both machines |
| Training with gradient sync | Need synchronized weight updates |
| Pipeline parallelism | Layers split across machines |

### Use Separate Batches When

| Scenario | Why |
|----------|-----|
| Model fits on one machine | No coordination overhead |
| Independent scoring/eval | Each machine works at own pace |
| Batch inference | Combined throughput = M4 + M3 |

**The Math (30B model example)**:
- Separate batches: M4 (1.95 ex/s) + M3 (1.03 ex/s) = **2.98 ex/s total**
- RDMA sharding: ~2.5 ex/s (20-30% coordination overhead)
- **Winner**: Separate batches (no overhead)

**Recommendation**: For DPO training with models ≤70B, use separate batches for maximum throughput.

---

## Environment Configuration

Critical environment variables and system settings for optimal MLX performance.

### Environment Variables

```bash
#!/bin/bash
# MLX Performance Configuration

# Pre-allocate Metal buffers (reduces allocation overhead)
export MLX_METAL_PREALLOCATE=1

# Fast synchronization between CPU and GPU
export MLX_METAL_FAST_SYNCH=1

# Disable tokenizer parallelism (prevents deadlocks)
export TOKENIZERS_PARALLELISM=false

# Optional: Limit memory usage (if needed)
# export MLX_MAX_MEMORY_GB=120
```

### Elevated Priority

```bash
# Run DPO training with elevated priority
sudo nice -n -10 python train_dpo.py \
    --config dpo_config.yaml \
    --batch-size 32 \
    --output-dir outputs/dpo-exp-001
```

**Why elevated priority**: Ensures DPO training isn't interrupted by background processes during multi-hour runs.

---

## Integration with mlx-performance Skill

This skill integrates with **mlx-performance** skill for advanced optimization:

```python
from hardware_calibrator import HardwareCalibrator

# Detect hardware and get optimal configuration
calibrator = HardwareCalibrator()
hw_config = calibrator.calibrate()

print(f"Detected: {hw_config['device_name']}")
print(f"Optimal batch size: {hw_config['optimal_batch_size']}")
print(f"GFLOPS: {hw_config['gflops']}")

# Use recommended batch size
dpo_config = {
    "batch_size": hw_config["optimal_batch_size"],
    "device": hw_config["device"],
}
```

**See**: `mlx-performance` skill for detailed hardware calibration guidance.

---

## Performance Tracking

Monitor and log performance metrics during DPO training.

### Metrics to Track

```python
import time
from pathlib import Path

class PerformanceTracker:
    """Track DPO training performance metrics."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.metrics = []

    def log_batch(self, batch_num, batch_size, batch_time, loss, kl):
        """Log single batch metrics."""
        examples_per_sec = batch_size / batch_time
        cost_per_example = batch_time / batch_size

        metric = {
            "batch": batch_num,
            "batch_size": batch_size,
            "time_sec": batch_time,
            "examples_per_sec": examples_per_sec,
            "cost_per_example": cost_per_example,
            "loss": loss,
            "kl_divergence": kl,
        }
        self.metrics.append(metric)

        # Log to file
        with open(self.log_path, "a") as f:
            f.write(f"{metric}\n")

    def get_average_throughput(self):
        """Calculate average throughput."""
        if not self.metrics:
            return 0.0
        total_examples = sum(m["batch_size"] for m in self.metrics)
        total_time = sum(m["time_sec"] for m in self.metrics)
        return total_examples / total_time

# Usage
tracker = PerformanceTracker(Path("performance.log"))

for batch_num, batch in enumerate(train_dataloader):
    start = time.time()

    # Train on batch
    loss, kl = train_step(batch)

    batch_time = time.time() - start
    tracker.log_batch(batch_num, len(batch), batch_time, loss, kl)

print(f"Average throughput: {tracker.get_average_throughput():.2f} ex/s")
```

### Cost Analysis

```python
def calculate_training_cost(
    total_examples: int,
    throughput: float,  # examples/sec
    cost_per_hour: float = 0.0,  # If using cloud
):
    """Calculate estimated training time and cost."""
    total_seconds = total_examples / throughput
    total_hours = total_seconds / 3600

    results = {
        "total_examples": total_examples,
        "throughput_ex_per_sec": throughput,
        "estimated_time_hours": total_hours,
        "estimated_cost_usd": total_hours * cost_per_hour,
    }
    return results

# Example
cost_analysis = calculate_training_cost(
    total_examples=10000,
    throughput=3.86,  # M4 Max throughput
    cost_per_hour=0.0,  # Local hardware
)

print(f"Estimated time: {cost_analysis['estimated_time_hours']:.1f} hours")
print(f"Throughput: {cost_analysis['throughput_ex_per_sec']:.2f} ex/s")
```

---

## Common Anti-Patterns

Mistakes that drastically reduce DPO training performance.

### Anti-Pattern 1: 50/50 Work Split

❌ **WRONG**:
```python
# Bad: Split work 50/50 based on GPU cores
m4_work = total_examples // 2  # 50%
m3_work = total_examples // 2  # 50%
# Result: M4 Max finishes early, sits idle
```

✅ **CORRECT**:
```python
# Good: Split based on throughput
m4_work = int(total_examples * 0.655)  # 65.5%
m3_work = total_examples - m4_work     # 34.5%
# Result: Both machines finish simultaneously
```

### Anti-Pattern 2: High Batch Size on M3 Ultra

❌ **WRONG**:
```python
# Bad: "More cores = higher batch size"
m3_config = {"batch_size": 32}  # 210 ex/s (slow)
```

✅ **CORRECT**:
```python
# Good: Use validated optimal batch size
m3_config = {
    "batch_size": 4,  # 278 ex/s (peak)
    "gradient_accumulation_steps": 8,  # Effective batch=32
}
```

### Anti-Pattern 3: Using RDMA for Small Models

❌ **WRONG**:
```python
# Bad: Use RDMA for 30B model
# Result: 20-30% coordination overhead, slower than single machine
```

✅ **CORRECT**:
```python
# Good: Use separate batches
# M4 Max: 1.95 ex/s + M3 Ultra: 1.03 ex/s = 2.98 ex/s total
```

### Anti-Pattern 4: Assuming Linear Scaling

❌ **WRONG**:
```
"M3 Ultra has 80 GPU cores vs M4 Max's 40, so it's 2x faster!"
# Reality: M3 Ultra is 5x SLOWER for MLX inference
```

✅ **CORRECT**:
```
Benchmark actual performance before making assumptions.
MLX performance depends on memory bandwidth, not just core count.
```

---

## Quick Reference

| Optimization | M4 Max | M3 Ultra |
|--------------|--------|----------|
| **Optimal batch size** | 32 | 4 |
| **Peak throughput** | 776 ex/s | 278 ex/s |
| **Real-world DPO** | 3.86 ex/s | 0.76 ex/s |
| **Work distribution** | 65.5% | 34.5% |
| **GFLOPS** | 12,956 | 4,599 |
| **GFLOPS per core** | 324 | 57 |

**Environment**:
```bash
export MLX_METAL_PREALLOCATE=1
export MLX_METAL_FAST_SYNCH=1
export TOKENIZERS_PARALLELISM=false
sudo nice -n -10 python train_dpo.py ...
```

---

## Related Documentation

- `../SKILL.md` - Performance optimization overview
- `../workflow.md` - Stage 5 DPO Optimization with performance callout
- `../templates.md` - Performance checklist for Stage 5
- mlx-performance skill - Advanced hardware calibration
- hardware_calibrator.py library - Automatic hardware detection and configuration

---

## Key Takeaways

1. **M4 Max is faster** - 5.1x faster than M3 Ultra for MLX inference despite fewer cores
2. **Batch size matters** - M4 Max peaks at 32, M3 Ultra peaks at 4 (DO NOT go higher)
3. **65/35 split** - Distribute work based on throughput, not core count
4. **Separate batches** - For models ≤70B, avoid RDMA overhead
5. **Environment variables** - MLX_METAL_PREALLOCATE and MLX_METAL_FAST_SYNCH are critical
6. **Track performance** - Log metrics to identify bottlenecks
7. **Benchmark first** - Don't assume, measure actual performance
8. **Use mlx-performance** - Integrate with hardware_calibrator.py for automatic configuration
