# Performance Benchmarking

Practical guide for measuring RDMA vs TCP/IP speedup in distributed training.

## Overview

Performance benchmarking validates the impact of RDMA acceleration by measuring:
- **Baseline metrics**: TCP/IP networking performance
- **RDMA metrics**: InfiniBand/RoCE networking performance
- **Speedup calculation**: RDMA improvement over TCP/IP
- **Gradient sync timing**: Communication overhead measurement
- **Checkpoint throughput**: I/O performance measurement

## Baseline Metrics

Establish baseline performance with TCP/IP before enabling RDMA.

### TCP/IP Configuration

```bash
# Disable RDMA (force TCP/IP)
export NCCL_IB_DISABLE=1
export NCCL_SOCKET_IFNAME=eth0
export NCCL_DEBUG=INFO

# Run training with TCP/IP
python train.py
```

### Measurement Script

```python
import mlx.core as mx
import mlx.nn as nn
import mlx.distributed as dist
import time

def measure_tcp_ip_baseline(model, dataloader, num_epochs=5):
    """
    Measure TCP/IP baseline performance.

    Args:
        model: MLX model
        dataloader: Training dataloader
        num_epochs: Number of epochs to measure (default: 5)

    Returns:
        Dict with performance metrics
    """
    dist.init()

    total_samples = 0
    total_time = 0.0
    gradient_sync_times = []

    for epoch in range(num_epochs):
        epoch_start = time.time()

        for batch in dataloader:
            batch_start = time.time()

            # Forward pass
            logits = model(batch['x'])
            loss = nn.losses.cross_entropy(logits, batch['y'])

            # Backward pass
            loss.backward()

            # Measure gradient sync time
            sync_start = time.time()
            dist.all_reduce_grads(model.parameters())
            sync_time = time.time() - sync_start
            gradient_sync_times.append(sync_time)

            # Update weights
            optimizer.step()
            optimizer.zero_grad()

            total_samples += len(batch['x'])

        epoch_time = time.time() - epoch_start
        total_time += epoch_time

        print(f"Epoch {epoch+1}/{num_epochs}: {epoch_time:.2f}s")

    # Calculate metrics
    avg_throughput = total_samples / total_time
    avg_gradient_sync = sum(gradient_sync_times) / len(gradient_sync_times)

    return {
        "network": "TCP/IP",
        "throughput": avg_throughput,  # samples/sec
        "gradient_sync_time": avg_gradient_sync,  # seconds
        "total_time": total_time,  # seconds
        "epochs": num_epochs
    }
```

## RDMA Measurement

Enable RDMA and measure performance improvement.

### RDMA Configuration

```bash
# Enable RDMA (InfiniBand)
export NCCL_IB_DISABLE=0
export NCCL_NET_GDR_LEVEL=5
export NCCL_IB_HCA=mlx5_0
export NCCL_DEBUG=INFO

# Run training with RDMA
python train.py
```

### Measurement Script

```python
def measure_rdma_performance(model, dataloader, num_epochs=5):
    """
    Measure RDMA performance.

    Args:
        model: MLX model
        dataloader: Training dataloader
        num_epochs: Number of epochs to measure (default: 5)

    Returns:
        Dict with performance metrics
    """
    # Verify RDMA is active
    # Look for "Using network InfiniBand" in NCCL_DEBUG logs

    dist.init()

    total_samples = 0
    total_time = 0.0
    gradient_sync_times = []

    for epoch in range(num_epochs):
        epoch_start = time.time()

        for batch in dataloader:
            batch_start = time.time()

            # Forward pass
            logits = model(batch['x'])
            loss = nn.losses.cross_entropy(logits, batch['y'])

            # Backward pass
            loss.backward()

            # Measure gradient sync time (RDMA-accelerated)
            sync_start = time.time()
            dist.all_reduce_grads(model.parameters())
            sync_time = time.time() - sync_start
            gradient_sync_times.append(sync_time)

            # Update weights
            optimizer.step()
            optimizer.zero_grad()

            total_samples += len(batch['x'])

        epoch_time = time.time() - epoch_start
        total_time += epoch_time

        print(f"Epoch {epoch+1}/{num_epochs}: {epoch_time:.2f}s (RDMA)")

    # Calculate metrics
    avg_throughput = total_samples / total_time
    avg_gradient_sync = sum(gradient_sync_times) / len(gradient_sync_times)

    return {
        "network": "RDMA",
        "throughput": avg_throughput,  # samples/sec
        "gradient_sync_time": avg_gradient_sync,  # seconds
        "total_time": total_time,  # seconds
        "epochs": num_epochs
    }
```

## Interpreting Results

### Speedup Calculation

```python
def calculate_speedup(tcp_ip_metrics, rdma_metrics):
    """
    Calculate RDMA speedup over TCP/IP.

    Args:
        tcp_ip_metrics: TCP/IP performance metrics
        rdma_metrics: RDMA performance metrics

    Returns:
        Dict with speedup metrics
    """
    throughput_speedup = rdma_metrics["throughput"] / tcp_ip_metrics["throughput"]
    gradient_sync_speedup = tcp_ip_metrics["gradient_sync_time"] / rdma_metrics["gradient_sync_time"]
    total_time_speedup = tcp_ip_metrics["total_time"] / rdma_metrics["total_time"]

    return {
        "throughput_speedup": throughput_speedup,
        "gradient_sync_speedup": gradient_sync_speedup,
        "total_time_speedup": total_time_speedup,
        "expected_range": "2-10x",
        "recommendation": (
            "RDMA enabled" if total_time_speedup > 1.5
            else "RDMA not providing significant speedup, check configuration"
        )
    }
```

### Expected Results

| Metric | TCP/IP | RDMA | Expected Speedup |
|--------|--------|------|------------------|
| **Throughput** | 100 samples/sec | 500 samples/sec | 5x |
| **Gradient sync** | 100 ms | 10 ms | 10x |
| **Total time** | 1000s | 200s | 5x |

### Example Output

```python
# Run benchmarks
tcp_ip_metrics = measure_tcp_ip_baseline(model, dataloader)
rdma_metrics = measure_rdma_performance(model, dataloader)
speedup = calculate_speedup(tcp_ip_metrics, rdma_metrics)

print(f"TCP/IP throughput: {tcp_ip_metrics['throughput']:.2f} samples/sec")
print(f"RDMA throughput: {rdma_metrics['throughput']:.2f} samples/sec")
print(f"Speedup: {speedup['throughput_speedup']:.2f}x")
print(f"Recommendation: {speedup['recommendation']}")
```

**Output**:
```
TCP/IP throughput: 100.00 samples/sec
RDMA throughput: 500.00 samples/sec
Speedup: 5.00x
Recommendation: RDMA enabled
```

## Gradient Sync Timing

Measure gradient synchronization overhead in detail.

### Timing Breakdown

```python
def profile_gradient_sync(model, batch):
    """
    Profile gradient synchronization timing.

    Args:
        model: MLX model
        batch: Training batch

    Returns:
        Dict with timing breakdown
    """
    # Forward pass
    forward_start = time.time()
    logits = model(batch['x'])
    loss = nn.losses.cross_entropy(logits, batch['y'])
    forward_time = time.time() - forward_start

    # Backward pass
    backward_start = time.time()
    loss.backward()
    backward_time = time.time() - backward_start

    # Gradient synchronization
    sync_start = time.time()
    dist.all_reduce_grads(model.parameters())
    sync_time = time.time() - sync_start

    # Update weights
    update_start = time.time()
    optimizer.step()
    optimizer.zero_grad()
    update_time = time.time() - update_start

    return {
        "forward_time": forward_time,
        "backward_time": backward_time,
        "sync_time": sync_time,
        "update_time": update_time,
        "total_time": forward_time + backward_time + sync_time + update_time
    }
```

### Overhead Analysis

```python
def analyze_communication_overhead(timing_breakdown):
    """
    Analyze communication overhead as percentage of total time.

    Args:
        timing_breakdown: Dict with timing breakdown

    Returns:
        Dict with overhead analysis
    """
    total_time = timing_breakdown["total_time"]
    sync_time = timing_breakdown["sync_time"]

    overhead_percentage = (sync_time / total_time) * 100

    return {
        "sync_time": sync_time,
        "total_time": total_time,
        "overhead_percentage": overhead_percentage,
        "recommendation": (
            "Low overhead (<20%)" if overhead_percentage < 20
            else "Moderate overhead (20-40%)" if overhead_percentage < 40
            else "High overhead (>40%), consider optimization"
        )
    }
```

## Checkpoint Measurement

Measure checkpoint I/O performance for different storage backends.

### Checkpoint Timing

```python
import gzip
import pickle
from pathlib import Path

def measure_checkpoint_performance(model, optimizer, backend="local"):
    """
    Measure checkpoint save/load performance.

    Args:
        model: MLX model
        optimizer: Optimizer
        backend: Storage backend ("local", "gcs", "s3")

    Returns:
        Dict with checkpoint performance metrics
    """
    checkpoint = {
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'epoch': 0
    }

    # Measure save time
    save_start = time.time()

    if backend == "local":
        path = Path("/tmp/checkpoint.pkl.gz")
        with gzip.open(path, 'wb') as f:
            pickle.dump(checkpoint, f)

    elif backend == "gcs":
        from google.cloud import storage
        compressed = gzip.compress(pickle.dumps(checkpoint))
        client = storage.Client()
        bucket = client.bucket("training-checkpoints")
        blob = bucket.blob("checkpoint.pkl.gz")
        blob.upload_from_string(compressed)

    elif backend == "s3":
        import boto3
        compressed = gzip.compress(pickle.dumps(checkpoint))
        s3 = boto3.client('s3')
        s3.put_object(
            Bucket="training-checkpoints",
            Key="checkpoint.pkl.gz",
            Body=compressed
        )

    save_time = time.time() - save_start

    # Measure load time
    load_start = time.time()

    if backend == "local":
        with gzip.open(path, 'rb') as f:
            loaded_checkpoint = pickle.load(f)

    elif backend == "gcs":
        client = storage.Client()
        bucket = client.bucket("training-checkpoints")
        blob = bucket.blob("checkpoint.pkl.gz")
        compressed = blob.download_as_bytes()
        loaded_checkpoint = pickle.loads(gzip.decompress(compressed))

    elif backend == "s3":
        s3 = boto3.client('s3')
        obj = s3.get_object(Bucket="training-checkpoints", Key="checkpoint.pkl.gz")
        compressed = obj['Body'].read()
        loaded_checkpoint = pickle.loads(gzip.decompress(compressed))

    load_time = time.time() - load_start

    # Calculate checkpoint size
    if backend == "local":
        checkpoint_size = path.stat().st_size / (1024 ** 2)  # MB
    else:
        checkpoint_size = len(gzip.compress(pickle.dumps(checkpoint))) / (1024 ** 2)  # MB

    return {
        "backend": backend,
        "save_time": save_time,
        "load_time": load_time,
        "checkpoint_size_mb": checkpoint_size,
        "total_time": save_time + load_time
    }
```

### Benchmark All Backends

```python
def benchmark_checkpoint_backends(model, optimizer):
    """Benchmark all checkpoint storage backends."""
    backends = ["local", "gcs", "s3"]
    results = []

    for backend in backends:
        try:
            metrics = measure_checkpoint_performance(model, optimizer, backend)
            results.append(metrics)
            print(f"{backend}: Save={metrics['save_time']:.2f}s, Load={metrics['load_time']:.2f}s")
        except Exception as e:
            print(f"{backend}: Failed ({e})")

    return results
```

## NCCL Debug

Use NCCL debug output to verify RDMA usage and diagnose issues.

### Enable Debug Logging

```bash
# Maximum debug verbosity
export NCCL_DEBUG=INFO
export NCCL_DEBUG_SUBSYS=ALL
export NCCL_DEBUG_FILE=/tmp/nccl_debug.log

# Run training
python train.py

# Check logs
cat /tmp/nccl_debug.log | grep "Using network"
```

### Key Debug Messages

```bash
# RDMA detected and active
NCCL INFO Using network InfiniBand

# GPU Direct RDMA enabled
NCCL INFO NET/IB/GDR enabled

# Falling back to TCP/IP
NCCL INFO Using network Socket
NCCL WARN NET/IB : No device found

# Performance warning
NCCL WARN Topology detection failed, performance may be degraded
```

### Analyzing NCCL Logs

```python
def analyze_nccl_logs(log_path="/tmp/nccl_debug.log"):
    """
    Analyze NCCL debug logs for performance insights.

    Args:
        log_path: Path to NCCL debug log

    Returns:
        Dict with analysis results
    """
    with open(log_path) as f:
        logs = f.read()

    # Check network type
    if "Using network InfiniBand" in logs:
        network = "RDMA (InfiniBand)"
    elif "Using network Socket" in logs:
        network = "TCP/IP (fallback)"
    else:
        network = "Unknown"

    # Check GPU Direct RDMA
    gpu_direct = "NET/IB/GDR enabled" in logs

    # Check for warnings
    warnings = [line for line in logs.split('\n') if "WARN" in line]

    return {
        "network": network,
        "gpu_direct_rdma": gpu_direct,
        "warnings": warnings,
        "recommendation": (
            "RDMA configured correctly" if network == "RDMA (InfiniBand)" and gpu_direct
            else "Check RDMA configuration, see warnings"
        )
    }
```

## Troubleshooting

### Low Speedup (<2x)

**Possible causes**:
- RDMA not actually enabled (check NCCL logs)
- Network bottleneck (test with `ib_write_bw`)
- Small model (communication overhead not significant)
- CPU-bound pipeline (gradient computation slow)

**Solutions**:
```bash
# Verify RDMA active
export NCCL_DEBUG=INFO
python train.py | grep "Using network"

# Test RDMA bandwidth
ib_write_bw --port=1 --size=4194304 --iters=10000

# Increase model size or batch size
# Reduce CPU overhead (use faster dataloader)
```

### RDMA Not Detected

**Possible causes**:
- InfiniBand drivers not installed
- NCCL_IB_DISABLE set to 1
- No InfiniBand adapter present

**Solutions**:
```bash
# Check for RDMA devices
ibstat

# Verify NCCL configuration
echo $NCCL_IB_DISABLE  # Should be 0 or unset

# Install InfiniBand drivers (Ubuntu)
sudo apt-get install libibverbs1 ibverbs-utils
```

### High Gradient Sync Overhead (>40%)

**Possible causes**:
- Large model with many parameters
- Inefficient gradient synchronization
- Network congestion

**Solutions**:
```bash
# Increase NCCL buffer size
export NCCL_BUFFSIZE=8388608

# Use gradient compression (if available)
# Reduce gradient sync frequency (accumulate gradients)

# Check network utilization
ib_write_bw  # Should show >90% of theoretical bandwidth
```

## Best Practices

1. **Establish baseline**: Always measure TCP/IP performance first
2. **Verify RDMA active**: Check NCCL logs for "Using network InfiniBand"
3. **Measure gradient sync**: Profile communication overhead separately
4. **Test checkpoint performance**: Benchmark all storage backends
5. **Use NCCL debug logs**: Enable verbose logging for diagnostics
6. **Run multiple epochs**: Average over 5+ epochs for stable metrics
7. **Isolate network effects**: Test with synthetic data to eliminate I/O overhead
8. **Compare apples-to-apples**: Use identical model, batch size, and configuration
9. **Document configuration**: Record all environment variables and settings
10. **Report speedup range**: RDMA typically provides 2-10x speedup

## Related

- See `mlx-distributed.md` for MLX setup
- See `rdma-networking.md` for RDMA configuration
- See `multi-node-orchestration.md` for orchestrating 10+ nodes
- See `flash-recovery.md` for checkpoint strategies
- Agent: `distributed-training-coordinator` for automated benchmarking
