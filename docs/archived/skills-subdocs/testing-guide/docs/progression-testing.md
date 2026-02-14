# Progression Testing

## Progression Testing

### Purpose
Track metrics over time, automatically detect regressions.

### How It Works

1. **First Run**: Establish baseline
2. **Subsequent Runs**: Compare to baseline
3. **Regression**: Test FAILS if metric drops >tolerance
4. **Progression**: Baseline updates if metric improves >2%

### Baseline File Format

```json
{
  "metric_name": "lora_accuracy",
  "baseline_value": 0.856,
  "tolerance": 0.05,
  "established_at": "2025-10-18T10:30:00",
  "history": [
    {"date": "2025-10-18", "value": 0.856, "change": "baseline established"},
    {"date": "2025-10-20", "value": 0.872, "change": "+1.9% improvement"}
  ]
}
```

### Progression Test Template

```python
# tests/progression/test_lora_accuracy.py

import json
import pytest
from pathlib import Path
from datetime import datetime

BASELINE_FILE = Path(__file__).parent / "baselines" / "lora_accuracy_baseline.json"
TOLERANCE = 0.05  # ±5%

class TestProgressionLoRAAccuracy:
    @pytest.fixture
    def baseline(self):
        if BASELINE_FILE.exists():
            return json.loads(BASELINE_FILE.read_text())
        return None

    def test_lora_accuracy_progression(self, baseline):
        # Measure current metric
        current_accuracy = self._train_and_evaluate()

        # First run - establish baseline
        if baseline is None:
            self._establish_baseline(current_accuracy)
            pytest.skip(f"Baseline established: {current_accuracy:.4f}")

        # Compare to baseline
        baseline_value = baseline["baseline_value"]
        diff_pct = ((current_accuracy - baseline_value) / baseline_value) * 100

        # Check for regression
        if diff_pct < -TOLERANCE * 100:
            pytest.fail(f"REGRESSION: {abs(diff_pct):.1f}% worse than baseline")

        # Check for progression
        if diff_pct > 2.0:
            self._update_baseline(current_accuracy, diff_pct, baseline)

        print(f"✅ Accuracy: {current_accuracy:.4f} ({diff_pct:+.1f}%)")

    def _train_and_evaluate(self) -> float:
        # Your measurement logic here
        pass

    def _establish_baseline(self, value: float):
        # Create baseline file
        pass

    def _update_baseline(self, new_value: float, improvement: float, old_baseline: dict):
        # Update baseline file
        pass
```

### Metrics to Track

| Metric | Higher Better? | Typical Tolerance |
|--------|----------------|-------------------|
| Accuracy | ✅ Yes | ±5% |
| Loss | ❌ No (lower better) | ±5% |
| Training Speed | ✅ Yes | ±10% |
| Memory Usage | ❌ No (lower better) | ±5% |
| Inference Latency | ❌ No (lower better) | ±10% |

---
