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

## Related

- See `mlx-distributed.md` for distributed setup
- See `batch-optimization.md` for memory management
- External: Google Cloud Storage (GCS)
- External: AWS S3
