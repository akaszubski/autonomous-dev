# FlashRecovery Checkpoint Strategy

Fast checkpoint and restore for fault-tolerant distributed training.

## Overview

FlashRecovery enables rapid recovery from failures:
- **Recovery time**: 150 seconds for 4,800 devices
- **Strategy**: Asynchronous checkpointing with compression
- **Storage**: Distributed filesystem (GCS, S3, NFS)

## Why FlashRecovery Matters

### Problem: Long Recovery Times

Traditional checkpointing:
- **Synchronous**: Training pauses during checkpoint
- **Slow**: Minutes to hours for large models
- **Disruptive**: Impacts training throughput

### Solution: Async + Compression

FlashRecovery:
- **Asynchronous**: Training continues during checkpoint
- **Compressed**: 5-10x smaller checkpoint files
- **Distributed**: Parallel writes to shared storage

## Implementation

### Basic Checkpointing

```python
import mlx.core as mx
import mlx.nn as nn
import pickle
from pathlib import Path

def save_checkpoint(model, optimizer, epoch, path):
    """Save model checkpoint."""
    checkpoint = {
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'epoch': epoch
    }

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'wb') as f:
        pickle.dump(checkpoint, f)

def load_checkpoint(model, optimizer, path):
    """Load model checkpoint."""
    with open(path, 'rb') as f:
        checkpoint = pickle.load(f)

    model.load_state_dict(checkpoint['model'])
    optimizer.load_state_dict(checkpoint['optimizer'])

    return checkpoint['epoch']
```

### Asynchronous Checkpointing

```python
import threading

class AsyncCheckpointer:
    """Asynchronous checkpoint writer."""

    def __init__(self, checkpoint_dir):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.queue = []
        self.thread = None

    def save_async(self, model, optimizer, epoch):
        """Queue checkpoint for async save."""
        # Copy state (non-blocking)
        checkpoint = {
            'model': {k: v.copy() for k, v in model.state_dict().items()},
            'optimizer': optimizer.state_dict(),
            'epoch': epoch
        }

        # Start background thread
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(
                target=self._write_checkpoint,
                args=(checkpoint,)
            )
            self.thread.start()

    def _write_checkpoint(self, checkpoint):
        """Write checkpoint in background."""
        path = self.checkpoint_dir / f"checkpoint_{checkpoint['epoch']}.pkl"
        with open(path, 'wb') as f:
            pickle.dump(checkpoint, f)

# Usage
checkpointer = AsyncCheckpointer('checkpoints/')

for epoch in range(num_epochs):
    for batch in dataloader:
        train_step(model, batch)

    # Non-blocking checkpoint
    checkpointer.save_async(model, optimizer, epoch)
```

### Compressed Checkpointing

```python
import gzip

def save_compressed_checkpoint(model, optimizer, epoch, path):
    """Save compressed checkpoint (5-10x smaller)."""
    checkpoint = {
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'epoch': epoch
    }

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(path, 'wb', compresslevel=6) as f:
        pickle.dump(checkpoint, f)

def load_compressed_checkpoint(model, optimizer, path):
    """Load compressed checkpoint."""
    with gzip.open(path, 'rb') as f:
        checkpoint = pickle.load(f)

    model.load_state_dict(checkpoint['model'])
    optimizer.load_state_dict(checkpoint['optimizer'])

    return checkpoint['epoch']
```

## Distributed Checkpointing

### Coordinator-Based

Single node coordinates checkpoint:

```python
import mlx.distributed as dist

def save_distributed_checkpoint(model, optimizer, epoch, path):
    """Save checkpoint from rank 0 only."""
    if dist.get_rank() == 0:
        checkpoint = {
            'model': model.state_dict(),
            'optimizer': optimizer.state_dict(),
            'epoch': epoch
        }

        with gzip.open(path, 'wb') as f:
            pickle.dump(checkpoint, f)

    # Barrier to ensure all ranks wait
    dist.barrier()
```

### Parallel Writes

Each rank writes subset of model:

```python
def save_parallel_checkpoint(model, rank, world_size, epoch, dir_path):
    """Each rank saves its portion of the model."""
    checkpoint = {
        'model_shard': {
            k: v for i, (k, v) in enumerate(model.state_dict().items())
            if i % world_size == rank
        },
        'rank': rank,
        'epoch': epoch
    }

    path = Path(dir_path) / f"checkpoint_{epoch}_rank{rank}.pkl"

    with gzip.open(path, 'wb') as f:
        pickle.dump(checkpoint, f)
```

## Recovery Strategy

### Automatic Recovery

```python
def train_with_recovery(model, dataloader, checkpoint_dir):
    """Training loop with automatic recovery."""
    checkpoint_dir = Path(checkpoint_dir)

    # Try to load latest checkpoint
    checkpoints = sorted(checkpoint_dir.glob("checkpoint_*.pkl"))
    start_epoch = 0

    if checkpoints:
        latest = checkpoints[-1]
        print(f"Recovering from {latest}")
        start_epoch = load_compressed_checkpoint(model, optimizer, latest)
        start_epoch += 1

    # Training loop
    for epoch in range(start_epoch, num_epochs):
        for batch in dataloader:
            try:
                train_step(model, batch)
            except Exception as e:
                print(f"Training error: {e}")
                print("Attempting recovery...")
                # Reload last checkpoint
                if checkpoints:
                    load_compressed_checkpoint(model, optimizer, checkpoints[-1])
                continue

        # Save checkpoint every epoch
        save_compressed_checkpoint(
            model, optimizer, epoch,
            checkpoint_dir / f"checkpoint_{epoch}.pkl"
        )
```

## Best Practices

1. **Checkpoint frequently**: Every epoch or every N steps
2. **Keep multiple checkpoints**: Last 3-5 for rollback
3. **Use compression**: 5-10x storage savings
4. **Async checkpointing**: Don't block training
5. **Distributed storage**: GCS, S3, or shared NFS

## Performance Metrics

| Configuration | Recovery Time | Throughput Impact |
|---------------|---------------|-------------------|
| Sync, uncompressed | 10+ min | 20-30% slowdown |
| Sync, compressed | 5 min | 10-15% slowdown |
| Async, compressed | 150s | <5% slowdown |

## Checkpoint Storage Backend Selection

Choose the right storage backend based on your infrastructure:

### GCS (Google Cloud Storage)

**Best for**: Google Cloud infrastructure, large-scale training

```python
def save_checkpoint_gcs(model, optimizer, epoch, bucket_name):
    """Save checkpoint to Google Cloud Storage."""
    from google.cloud import storage
    import pickle
    import gzip

    checkpoint = {
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'epoch': epoch
    }

    # Compress checkpoint
    compressed = gzip.compress(pickle.dumps(checkpoint))

    # Upload to GCS
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"checkpoints/checkpoint_{epoch}.pkl.gz")
    blob.upload_from_string(compressed)
```

### S3 (AWS Simple Storage Service)

**Best for**: AWS infrastructure, multi-region replication

```python
def save_checkpoint_s3(model, optimizer, epoch, bucket_name):
    """Save checkpoint to AWS S3."""
    import boto3
    import pickle
    import gzip

    checkpoint = {
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'epoch': epoch
    }

    # Compress checkpoint
    compressed = gzip.compress(pickle.dumps(checkpoint))

    # Upload to S3
    s3 = boto3.client('s3')
    s3.put_object(
        Bucket=bucket_name,
        Key=f"checkpoints/checkpoint_{epoch}.pkl.gz",
        Body=compressed
    )
```

### NFS (Network File System)

**Best for**: On-premise clusters, low latency access

```python
def save_checkpoint_nfs(model, optimizer, epoch, nfs_path):
    """Save checkpoint to NFS mount."""
    from pathlib import Path
    import pickle
    import gzip

    checkpoint = {
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'epoch': epoch
    }

    # Write to NFS mount
    path = Path(nfs_path) / f"checkpoints/checkpoint_{epoch}.pkl.gz"
    path.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(path, 'wb') as f:
        pickle.dump(checkpoint, f)
```

### Decision Matrix

| Backend | Latency | Throughput | Cost | Durability | Best For |
|---------|---------|------------|------|------------|----------|
| **GCS** | Medium (100-200ms) | High (5-10 GB/s) | Low | 99.999999999% | Google Cloud clusters |
| **S3** | Medium (100-200ms) | High (5-10 GB/s) | Low | 99.999999999% | AWS clusters |
| **NFS** | Low (10-50ms) | Medium (1-5 GB/s) | N/A | Depends on RAID | On-premise, low-latency |

## Integration with distributed-training-coordinator

The coordinator automates checkpoint strategy selection:

```json
{
  "checkpoint_strategy": {
    "approach": "FlashRecovery",
    "async": true,
    "compression": "gzip",
    "storage": "gs://training-checkpoints/",
    "frequency": "every_epoch",
    "retention": "last_3_checkpoints",
    "expected_recovery_time": "150s for 4800 devices"
  }
}
```

### Coordinator-Level Chunking Checkpoint Pattern

For large datasets (>50K examples), the coordinator enables chunking:

```json
{
  "coordinator_chunking": {
    "enabled": true,
    "chunk_size": 50000,
    "num_chunks": 10,
    "memory_management": {
      "gc_collect": true,
      "mx_clear_cache": true
    },
    "progress_reporting": "Processing chunk 3/10 (30% complete)"
  }
}
```

**Implementation**:

```python
import mlx.core as mx
import gc

def train_with_coordinator_chunking(model, dataset, chunk_size=50000):
    """Train with coordinator-level chunking for large datasets."""
    num_chunks = (len(dataset) + chunk_size - 1) // chunk_size

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

**Benefits**:
- **Memory efficiency**: Process large datasets without OOM
- **Fault tolerance**: Checkpoint after each chunk (resume from chunk boundary)
- **Progress tracking**: Clear progress reporting per chunk

## Related

- See `mlx-distributed.md` for distributed setup
- See `batch-optimization.md` for memory management
- See `multi-node-orchestration.md` for coordinator patterns
- External: Google Cloud Storage (GCS)
- External: AWS S3
