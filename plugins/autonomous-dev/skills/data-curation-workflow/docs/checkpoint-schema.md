# Checkpoint Schema

State management for pipeline resume capability.

## Checkpoint Manager

```python
from pathlib import Path
import json
from datetime import datetime

class CheckpointManager:
    """Manage pipeline checkpoint state for crash recovery."""

    def __init__(self, checkpoint_path: Path):
        self.path = checkpoint_path
        self.state = self._load_or_create()

    def _load_or_create(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return self._create_initial_state()

    def _create_initial_state(self) -> dict:
        return {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "last_updated": None,
            "current_stage": None,
            "completed_stages": [],
            "stage_stats": {},
            "layer_progress": {
                "bronze": {"status": "pending", "stages": []},
                "silver": {"status": "pending", "stages": []},
                "gold": {"status": "pending", "stages": []}
            }
        }

    def save_stage(self, stage: str, stats: dict):
        """Save checkpoint after stage completion."""
        self.state["current_stage"] = stage
        self.state["completed_stages"].append(stage)
        self.state["stage_stats"][stage] = {
            **stats,
            "completed_at": datetime.utcnow().isoformat() + "Z"
        }
        self.state["last_updated"] = datetime.utcnow().isoformat() + "Z"
        self._write()

    def get_resume_stage(self) -> str:
        """Get next stage to execute (after last completed)."""
        all_stages = [
            "1_extract", "2_prefilter", "3_score", "4_dedup",
            "5_decontaminate", "6_filter", "7_generate", "8_mix", "9_validate"
        ]
        completed = set(self.state["completed_stages"])
        for stage in all_stages:
            if stage not in completed:
                return stage
        return None  # All stages complete

    def _write(self):
        self.path.write_text(json.dumps(self.state, indent=2))
```

## Full Checkpoint Schema

```json
{
  "version": "1.0",
  "created_at": "2025-01-31T10:00:00Z",
  "last_updated": "2025-01-31T15:30:00Z",
  "current_stage": "6_filter",
  "completed_stages": [
    "1_extract",
    "2_prefilter",
    "3_score",
    "4_dedup",
    "5_decontaminate"
  ],
  "stage_stats": {
    "1_extract": {
      "input_files": 42,
      "output_examples": 100000,
      "duration_sec": 120,
      "completed_at": "2025-01-31T10:02:00Z"
    },
    "2_prefilter": {
      "input": 100000,
      "output": 68000,
      "filtered": 32000,
      "perplexity_mean": 245.3,
      "perplexity_threshold": 500,
      "duration_sec": 85,
      "completed_at": "2025-01-31T10:03:25Z"
    },
    "3_score": {
      "input": 68000,
      "scored": 68000,
      "quality_mean": 7.8,
      "quality_std": 1.2,
      "ifd_mean": 0.65,
      "duration_sec": 480,
      "completed_at": "2025-01-31T10:11:25Z"
    },
    "4_dedup": {
      "input": 68000,
      "output": 61200,
      "exact_duplicates": 4800,
      "fuzzy_duplicates": 2000,
      "duplicate_rate": 0.10,
      "duration_sec": 120,
      "completed_at": "2025-01-31T10:13:25Z"
    },
    "5_decontaminate": {
      "input": 61200,
      "output": 59976,
      "contaminated": 1224,
      "benchmarks_checked": ["mmlu", "gsm8k", "humaneval"],
      "duration_sec": 180,
      "completed_at": "2025-01-31T10:16:25Z"
    }
  },
  "layer_progress": {
    "bronze": {
      "status": "completed",
      "stages": ["1_extract", "2_prefilter"],
      "total_retention": 0.68
    },
    "silver": {
      "status": "in_progress",
      "stages": ["3_score", "4_dedup", "5_decontaminate"],
      "remaining": ["6_filter"]
    },
    "gold": {
      "status": "pending",
      "stages": []
    }
  },
  "pipeline_config": {
    "input_dir": "raw_data/",
    "output_dir": "curated_data/",
    "quality_threshold": 8.0,
    "ifd_threshold": 0.6,
    "perplexity_threshold": 500
  }
}
```

## Resume Workflow

```python
from realign.data.pipeline import DataPipeline
from realign.data.checkpoint import CheckpointManager

# Initialize with checkpoint
checkpoint = CheckpointManager("pipeline_checkpoint.json")
pipeline = DataPipeline(checkpoint=checkpoint)

# Resume from last checkpoint
resume_stage = checkpoint.get_resume_stage()
if resume_stage:
    print(f"Resuming from stage: {resume_stage}")
    pipeline.run(start_stage=resume_stage)
else:
    print("Pipeline already complete")
```

## Error Recovery

```python
def recover_from_error(checkpoint: CheckpointManager, error: Exception):
    """Recover from pipeline error."""
    current_stage = checkpoint.state["current_stage"]

    # Log error
    checkpoint.state["errors"] = checkpoint.state.get("errors", [])
    checkpoint.state["errors"].append({
        "stage": current_stage,
        "error": str(error),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
    checkpoint._write()

    # Retry logic
    if len([e for e in checkpoint.state["errors"] if e["stage"] == current_stage]) < 3:
        print(f"Retrying stage {current_stage} (attempt {len(checkpoint.state['errors'])})")
        return current_stage
    else:
        print(f"Stage {current_stage} failed after 3 attempts")
        raise error
```

## Stage Dependencies

```
1_extract ──────┐
                │
2_prefilter ────┤
                │
3_score ────────┤
                │
4_dedup ────────┤── Sequential dependency
                │
5_decontaminate ┤
                │
6_filter ───────┤
                │
7_generate ─────┤
                │
8_mix ──────────┤
                │
9_validate ─────┘
```

All stages are sequential - each depends on the previous stage's output.
