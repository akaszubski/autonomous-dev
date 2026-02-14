# Multi-Node Orchestration

Comprehensive guide for orchestrating distributed training across 10+ nodes with MLX, RDMA, and ReAlign patterns.

## Overview

Multi-node orchestration coordinates training across multiple machines with:
- **Hostfile configuration**: Define node topology
- **Pre-RDMA sync**: Ensure codebase consistency
- **Hardware calibration**: Measure node performance
- **Worker consistency**: Validate training script integrity
- **Pre-flight checklist**: 8-point validation before launch

## Setup

### 1. Node Preparation

**Requirements**:
- MLX installed on all nodes
- SSH access between nodes (passwordless)
- Shared filesystem (NFS) or object storage (GCS/S3)
- RDMA adapter (InfiniBand or RoCE) on all nodes

**Verify connectivity**:
```bash
# From coordinator node, test SSH to all workers
for node in worker-1 worker-2 worker-3; do
  ssh $node "echo Ping from $node"
done
```

### 2. Hostfile Configuration

Create hostfile with node topology:

```bash
# /path/to/hostfile
# Format: hostname:num_gpus_per_node
coordinator.example.com:4
worker-1.example.com:4
worker-2.example.com:4
worker-3.example.com:4
```

**Environment variables**:
```bash
export MLX_HOSTFILE=/path/to/hostfile
export MLX_WORLD_SIZE=16  # Total GPUs (4 nodes × 4 GPUs)
```

### 3. Launch Multi-Node Training

```bash
# Launch from coordinator node
mlx.launch --gpus 4 --hostfile /path/to/hostfile train.py

# Alternatively, use environment variable
export MLX_HOSTFILE=/path/to/hostfile
mlx.launch --gpus 4 train.py
```

## Coordinator Patterns

The `distributed-training-coordinator` agent automates multi-node orchestration through 5 enhanced phases.

### Phase 1.5: Pre-RDMA Sync

**Purpose**: Ensure codebase consistency across all workers before training.

```bash
#!/bin/bash
# ~/Dev/sync-dev.sh - Example sync script

set -e  # Exit on error

# Define workers
WORKERS=("worker-1" "worker-2" "worker-3")
CODEBASE="/path/to/training/code"

echo "Starting pre-RDMA sync..."

for worker in "${WORKERS[@]}"; do
  echo "Syncing to $worker..."
  rsync -avz --delete $CODEBASE $worker:$CODEBASE
done

echo "Pre-RDMA sync complete!"
```

**Coordinator integration**:
```json
{
  "pre_rdma_sync": {
    "sync_script": "~/Dev/sync-dev.sh",
    "validation_checks": ["script_exists", "execution_success"],
    "block_on_failure": true,
    "sync_status": "success",
    "sync_output": "All workers synchronized"
  }
}
```

**Failure handling**:
- If sync script exits with non-zero code → **block training launch**
- If sync script not found → log warning, continue (graceful degradation)

### Phase 2.5: Hardware Calibration

**Purpose**: Measure actual hardware performance and optimize workload distribution.

```python
import mlx.core as mx
import mlx.nn as nn
import time

def calibrate_node(node_id, calibration_time=120):
    """
    Measure node throughput during calibration period.

    Args:
        node_id: Node identifier (e.g., "worker-0")
        calibration_time: Calibration duration in seconds (default: 120s)

    Returns:
        Throughput in examples/sec (e.g., 0.85 ex/s)
    """
    # Load calibration dataset
    calibration_data = load_calibration_dataset()

    # Measure throughput
    start_time = time.time()
    examples_processed = 0

    while time.time() - start_time < calibration_time:
        batch = next(calibration_data)
        logits = model(batch['x'])
        loss = loss_fn(logits, batch['y'])
        loss.backward()

        examples_processed += len(batch['x'])

    elapsed = time.time() - start_time
    throughput = examples_processed / elapsed

    print(f"Node {node_id}: {throughput:.2f} ex/s")
    return throughput


def calculate_workload_distribution(measured_performance):
    """
    Calculate proportional workload distribution based on measured performance.

    Args:
        measured_performance: Dict mapping node_id to throughput (ex/s)

    Returns:
        Dict mapping node_id to workload fraction (0.0-1.0)
    """
    total_throughput = sum(measured_performance.values())

    workload_distribution = {
        node_id: throughput / total_throughput
        for node_id, throughput in measured_performance.items()
    }

    return workload_distribution
```

**Coordinator integration**:
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
    },
    "macos_qos_api": "user_interactive",
    "calibration_notes": "Equal performance measured across all workers. Pipeline is overhead-bound, not compute-bound."
  }
}
```

**Key Insights** (from Issue #280):
- **Equal performance**: Machines show equal throughput (~0.85 ex/s per worker)
- **Overhead-bound pipeline**: Bottlenecked by I/O, synchronization, not compute
- **Typical speedup**: 1.2-1.8x for 4 workers (not linear due to overhead)
- **Expected overhead**: <105s per epoch

### Phase 3.5: Worker Consistency Validation

**Purpose**: Detect divergent workers and Byzantine behavior before training begins.

```python
import hashlib
from pathlib import Path

def validate_worker_consistency(training_script_path, workers):
    """
    Validate training script consistency across all workers.

    Args:
        training_script_path: Path to training script
        workers: List of worker node IDs

    Returns:
        Dict with validation results
    """
    # Compute coordinator hash
    coordinator_hash = compute_sha256(training_script_path)

    # Query worker hashes
    worker_hashes = {}
    for worker in workers:
        worker_hash = query_worker_hash(worker, training_script_path)
        worker_hashes[worker] = worker_hash

    # Check consistency
    consistent_workers = [
        worker for worker, hash_val in worker_hashes.items()
        if hash_val == coordinator_hash
    ]

    consistency_ratio = len(consistent_workers) / len(workers)

    # Byzantine detection using Krum algorithm
    divergent_workers = [
        worker for worker in workers
        if worker not in consistent_workers
    ]

    return {
        "script_hash": coordinator_hash,
        "is_consistent": consistency_ratio >= 0.95,
        "consistency_threshold": 0.95,
        "divergent_workers": divergent_workers,
        "consistency_ratio": consistency_ratio
    }


def compute_sha256(file_path):
    """Compute SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
```

**Coordinator integration**:
```json
{
  "worker_consistency": {
    "validation_checks": ["script_hash_sha256", "consistency_threshold"],
    "script_hash": "abc123def456789...",
    "is_consistent": true,
    "consistency_threshold": 0.95,
    "byzantine_detection": {
      "enabled": true,
      "divergent_workers": [],
      "krum_aggregation": "N/A (all workers consistent)"
    }
  }
}
```

**Enforcement**:
- Consistency < 95% → **block training launch**
- Log divergent workers with fix commands
- Exclude Byzantine workers from training

### Phase 4.5: Coordinator-Level Chunking

**Purpose**: Manage memory for large datasets by processing in chunks.

```python
import mlx.core as mx
import gc

def train_with_chunking(model, dataset, chunk_size=50000):
    """
    Train with coordinator-level chunking for large datasets.

    Args:
        model: MLX model
        dataset: Training dataset
        chunk_size: Number of examples per chunk (default: 50,000)
    """
    if len(dataset) < chunk_size:
        print("Dataset below threshold, chunking disabled")
        return train_without_chunking(model, dataset)

    num_chunks = (len(dataset) + chunk_size - 1) // chunk_size
    print(f"Chunking enabled: {num_chunks} chunks of {chunk_size} examples")

    for chunk_idx in range(num_chunks):
        start = chunk_idx * chunk_size
        end = min(start + chunk_size, len(dataset))
        chunk = dataset[start:end]

        print(f"Processing chunk {chunk_idx+1}/{num_chunks} ({(chunk_idx+1)*100//num_chunks}% complete)")

        # Train on chunk
        for batch in chunk:
            train_step(model, batch)

        # Memory management after each chunk
        gc.collect()
        mx.clear_cache()

        # Save checkpoint after each chunk
        save_checkpoint(model, optimizer, f"chunk_{chunk_idx}")
```

**Boundary conditions**:
- Dataset == 50,000 → Enable chunking (>= threshold)
- Dataset == 49,999 → Disable chunking (< threshold)
- Dataset <= 0 → Raise ValueError (invalid)

### Phase 5: Pre-Flight Checklist

**Purpose**: Run comprehensive validation before launching distributed training.

```python
def run_pre_flight_checklist():
    """
    Run 8-point pre-flight checklist.

    Returns:
        Dict with validation results for all checks
    """
    checks = []

    # 1. Hardware Layer
    checks.append(validate_hardware_layer())

    # 2. Worker Layer
    checks.append(validate_worker_layer())

    # 3. Checkpoint Layer
    checks.append(validate_checkpoint_layer())

    # 4. Gradient Layer
    checks.append(validate_gradient_layer())

    # 5. Performance Layer
    checks.append(validate_performance_layer())

    # 6. Health Check
    checks.append(run_health_checks())

    # 7. Pre-RDMA Sync
    checks.append(validate_pre_rdma_sync())

    # 8. Worker Consistency
    checks.append(validate_worker_consistency_layer())

    # Determine overall status
    overall_status = "pass" if all(c["status"] == "pass" for c in checks) else "fail"

    return {
        "checks": checks,
        "overall_status": overall_status,
        "block_on_failure": True
    }
```

**Example check implementation**:
```python
def validate_hardware_layer():
    """Validate hardware layer: GPU count, RDMA devices, memory."""
    # Check GPU count
    gpu_count = mx.metal.device_count()
    if gpu_count == 0:
        return {
            "name": "hardware_layer",
            "status": "fail",
            "error": "No GPUs detected",
            "fix_command": "Check GPU drivers and MLX installation"
        }

    # Check RDMA devices
    rdma_available = check_rdma_devices()  # Run `ibstat`
    if not rdma_available:
        return {
            "name": "hardware_layer",
            "status": "warning",
            "warning": "RDMA not available, falling back to TCP/IP",
            "fix_command": "Install InfiniBand drivers or use NCCL_IB_DISABLE=1"
        }

    return {"name": "hardware_layer", "status": "pass"}
```

## Worker Consistency

### SHA256 Hash Validation

```bash
# On coordinator
sha256sum train.py
# Output: abc123def456789... train.py

# On workers
for worker in worker-1 worker-2 worker-3; do
  ssh $worker "sha256sum /path/to/train.py"
done
```

### Byzantine Worker Detection

Use Krum algorithm to detect outlier workers:

```python
def krum_aggregation(worker_hashes, n_workers, f_byzantine):
    """
    Krum algorithm for Byzantine-robust aggregation.

    Args:
        worker_hashes: Dict mapping worker_id to hash
        n_workers: Total number of workers
        f_byzantine: Maximum number of Byzantine workers to tolerate

    Returns:
        Selected worker hash (most consistent)
    """
    # Calculate pairwise distances (Hamming distance for hashes)
    distances = {}
    for w1 in worker_hashes:
        distances[w1] = 0
        for w2 in worker_hashes:
            if w1 != w2:
                distances[w1] += hamming_distance(worker_hashes[w1], worker_hashes[w2])

    # Select worker with minimum distance (most consistent)
    selected_worker = min(distances, key=distances.get)
    return worker_hashes[selected_worker]
```

## Hardware Calibration

### macOS QoS API (Issue #280)

**DO NOT use `nice()`** on macOS 10.10+. Apple silently ignores `nice()` for thread scheduling (see Apple TN2169).

**Use `pthread_set_qos_class_self_np()` instead**:

```python
import ctypes
import platform

def set_macos_qos_priority():
    """Set macOS QoS priority for training process."""
    if platform.system() != "Darwin":
        return  # Not macOS

    # Load libpthread
    libpthread = ctypes.CDLL("/usr/lib/libpthread.dylib")

    # QoS constants
    QOS_CLASS_USER_INTERACTIVE = 0x21

    # Set QoS class
    result = libpthread.pthread_set_qos_class_self_np(
        QOS_CLASS_USER_INTERACTIVE,
        0  # relative priority
    )

    if result == 0:
        print("macOS QoS set to USER_INTERACTIVE")
    else:
        print(f"Failed to set macOS QoS: {result}")
```

## Monitoring

### Training Progress

```bash
# Monitor GPU utilization
watch -n 1 'mlx.metal.device_memory()'

# Monitor network bandwidth
ib_write_bw --port=1 --size=4194304 --iters=10000

# Monitor NCCL communication
export NCCL_DEBUG=INFO
python train.py
```

### Log Aggregation

```bash
# Collect logs from all workers
for worker in worker-1 worker-2 worker-3; do
  ssh $worker "cat /tmp/training.log" > logs/${worker}.log
done
```

## Failure Recovery

### Checkpoint-Based Recovery

```python
def train_with_recovery(model, dataloader, checkpoint_dir):
    """Training loop with automatic recovery from checkpoints."""
    checkpoint_dir = Path(checkpoint_dir)

    # Try to load latest checkpoint
    checkpoints = sorted(checkpoint_dir.glob("checkpoint_*.pkl"))
    start_epoch = 0

    if checkpoints:
        latest = checkpoints[-1]
        print(f"Recovering from {latest}")
        start_epoch = load_checkpoint(model, optimizer, latest)
        start_epoch += 1

    # Training loop
    for epoch in range(start_epoch, num_epochs):
        try:
            for batch in dataloader:
                train_step(model, batch)
        except Exception as e:
            print(f"Training error: {e}")
            # Reload last checkpoint and continue
            if checkpoints:
                load_checkpoint(model, optimizer, checkpoints[-1])
            continue

        # Save checkpoint every epoch
        save_checkpoint(model, optimizer, epoch, checkpoint_dir / f"checkpoint_{epoch}.pkl")
```

### Worker Failure Detection

```python
def detect_worker_failures(workers, timeout=60):
    """
    Detect worker failures by pinging each worker.

    Args:
        workers: List of worker node IDs
        timeout: Ping timeout in seconds

    Returns:
        List of failed workers
    """
    failed_workers = []

    for worker in workers:
        try:
            # Ping worker
            result = subprocess.run(
                ["ssh", worker, "echo", "pong"],
                timeout=timeout,
                capture_output=True
            )
            if result.returncode != 0:
                failed_workers.append(worker)
        except subprocess.TimeoutExpired:
            failed_workers.append(worker)

    return failed_workers
```

## Best Practices

1. **Pre-RDMA sync**: Always run sync script before training to ensure consistency
2. **Hardware calibration**: Measure actual performance, don't assume equal distribution
3. **Worker consistency**: Validate training script hash across all workers
4. **Pre-flight checklist**: Run all 8 validation checks before launch
5. **Chunking for large datasets**: Enable for >50K examples to prevent OOM
6. **Monitor continuously**: Track GPU utilization, network bandwidth, training loss
7. **Checkpoint frequently**: Every epoch or every N steps for fault tolerance
8. **Log aggregation**: Collect logs from all workers for debugging
9. **Use macOS QoS API**: Set priority with `pthread_set_qos_class_self_np()`, not `nice()`
10. **Graceful degradation**: Handle missing validators/libraries with warnings

## Related

- See `mlx-distributed.md` for MLX setup
- See `rdma-networking.md` for RDMA configuration
- See `batch-optimization.md` for batch tuning
- See `flash-recovery.md` for checkpoint strategies
- See `performance-benchmarking.md` for measuring speedup
- Agent: `distributed-training-coordinator` for automated orchestration
