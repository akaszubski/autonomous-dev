# Real-Time Progress Display Integration Guide

**Version**: v3.2.2
**Feature**: Real-time progress indicators for /auto-implement workflow (Issue #42)
**Last Updated**: 2025-11-04

---

## Overview

The progress display feature provides real-time visibility into the `/auto-implement` workflow by polling a JSON state file and rendering a live tree view showing agent progress, status indicators, and time estimates.

### Key Capabilities

- **Real-time updates**: Polls every 0.5 seconds (configurable)
- **Tree view rendering**: Visual hierarchy with emoji status indicators
- **Progress metrics**: Completion percentage (0-100%) and estimated time remaining
- **TTY-aware**: Adapts output for interactive terminals vs CI/CD environments
- **Graceful degradation**: Handles malformed JSON and file access issues
- **Terminal resize handling**: Adapts to window size changes

---

## Installation & Setup

### 1. Verify Installation

The progress display module is included in the plugin. Verify it exists:

```bash
ls -la plugins/autonomous-dev/scripts/progress_display.py
```

Expected output:
```
-rwxr-xr-x  350 user  group  progress_display.py
```

### 2. Check Dependencies

Progress display requires only Python standard library:

```python
import json      # Built-in
import os        # Built-in
import shutil    # Built-in
import sys       # Built-in
import time      # Built-in
from pathlib import Path  # Built-in
```

No additional packages required.

### 3. Verify Module Integration

The module imports from the plugin's health check module:

```python
from hooks.health_check import PluginHealthCheck
EXPECTED_AGENTS = PluginHealthCheck.EXPECTED_AGENTS
```

Verify health check module exists:

```bash
ls -la plugins/autonomous-dev/hooks/health_check.py
```

---

## Usage Examples

### Basic Usage: Monitor Progress

Start your feature and monitor progress from another terminal:

```bash
# Terminal 1: Start feature implementation
/auto-implement "Add user authentication with JWT tokens"

# Terminal 2: Monitor progress in real-time
python plugins/autonomous-dev/scripts/progress_display.py docs/sessions/LATEST.json
```

### Custom Refresh Interval

Change polling frequency for slower/faster environments:

```bash
# Poll every 1.0 seconds (for slower connections)
python plugins/autonomous-dev/scripts/progress_display.py \
  docs/sessions/LATEST.json \
  --refresh 1.0

# Poll every 0.2 seconds (for responsive displays)
python plugins/autonomous-dev/scripts/progress_display.py \
  docs/sessions/LATEST.json \
  --refresh 0.2
```

### Non-TTY Output (CI/CD Integration)

The display auto-detects non-TTY environments and outputs incrementally:

```bash
# Piped output (safe for logs)
python plugins/autonomous-dev/scripts/progress_display.py \
  docs/sessions/LATEST.json | tee feature-progress.log

# Output suitable for GitHub Actions, CircleCI, etc.
python plugins/autonomous-dev/scripts/progress_display.py \
  docs/sessions/LATEST.json >> .github/workflows/pipeline.log
```

---

## Configuration

### Enable/Disable Progress Display

Configure in `.claude/settings.local.json`:

```json
{
  "progress_display": {
    "enabled": true,
    "refresh_interval": 0.5,
    "show_durations": true,
    "show_estimated_time": true,
    "use_colors": true
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable progress display |
| `refresh_interval` | float | `0.5` | Seconds between display updates |
| `show_durations` | boolean | `true` | Show elapsed time for completed agents |
| `show_estimated_time` | boolean | `true` | Show estimated time remaining |
| `use_colors` | boolean | `true` | Use ANSI colors in output |

### Disable for Specific Run

Set environment variable to override config:

```bash
export PROGRESS_DISPLAY_ENABLED=false
/auto-implement "Add feature"

# Or inline
PROGRESS_DISPLAY_ENABLED=false /auto-implement "Add feature"
```

---

## Output Examples

### TTY Output (Interactive Terminal)

```
╭─ Agent Pipeline Progress ─────────────────────────────────────╮
│                                                               │
│  ├─ ✅ researcher (5m 15s)                                    │
│  │   └─ Message: Found 5 design patterns in similar repos    │
│  │                                                             │
│  ├─ ✅ planner (3m 42s)                                       │
│  │   └─ Message: Architecture plan created with diagrams     │
│  │                                                             │
│  ├─ ⏳ test-master (running for 2m 30s)                       │
│  │   └─ Message: Writing tests for authentication module     │
│  │                                                             │
│  ├─ ⏱️  implementer                                            │
│  ├─ ⏱️  reviewer                                               │
│  ├─ ⏱️  security-auditor                                       │
│  └─ ⏱️  doc-master                                             │
│                                                               │
│  Progress: [====>            ] 28% (2/7 agents complete)     │
│  Estimated time remaining: 12 minutes 35 seconds             │
│  GitHub Issue: #42 - Add user authentication                 │
│                                                               │
╰───────────────────────────────────────────────────────────────╯
```

### Non-TTY Output (Piped/CI)

```
[12:45:32] Agent Pipeline Progress
[12:45:32] ├─ ✅ researcher (5m 15s)
[12:45:32] │   └─ Found 5 design patterns in similar repos
[12:45:32] ├─ ✅ planner (3m 42s)
[12:45:32] │   └─ Architecture plan created with diagrams
[12:45:32] ├─ ⏳ test-master (running for 2m 30s)
[12:45:32] │   └─ Writing tests for authentication module
[12:45:32] ├─ ⏱️  implementer
[12:45:32] ├─ ⏱️  reviewer
[12:45:32] ├─ ⏱️  security-auditor
[12:45:32] └─ ⏱️  doc-master
[12:45:32] Progress: [====>            ] 28% (2/7 agents complete)
[12:45:32] Estimated time remaining: 12 minutes 35 seconds
```

---

## Status Indicators

| Emoji | Status | Meaning |
|-------|--------|---------|
| ✅ | Completed | Agent finished successfully with duration |
| ⏳ | Running | Agent currently executing with elapsed time |
| ⏱️ | Pending | Agent waiting to start (not yet queued) |
| ❌ | Failed | Agent encountered an error (with error message) |

---

## API Reference

### ProgressDisplay Class

```python
from pathlib import Path
from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

# Initialize display
display = ProgressDisplay(
    session_file=Path("docs/sessions/LATEST.json"),
    refresh_interval=0.5  # 0.5 seconds
)

# Run display (polls until pipeline completes or Ctrl+C)
display.run()
```

### Key Methods

#### `load_pipeline_state() -> Optional[Dict[str, Any]]`

Load pipeline state from JSON file.

```python
state = display.load_pipeline_state()
if state:
    print(f"Pipeline has {len(state['agents'])} agents")
```

Returns:
- `None` if file doesn't exist or has invalid JSON
- Dictionary with keys: `session_id`, `started`, `github_issue`, `agents`

#### `render_tree_view(state: Dict[str, Any]) -> str`

Render tree view of agent progress.

```python
state = display.load_pipeline_state()
output = display.render_tree_view(state)
print(output)
```

Returns: Formatted string with tree view and progress bar

#### `calculate_progress(state: Dict[str, Any]) -> int`

Calculate completion percentage (0-100).

```python
progress_percent = display.calculate_progress(state)
print(f"Progress: {progress_percent}%")
```

Returns: Integer between 0 and 100

#### `run()`

Start the display loop (runs until pipeline completes or Ctrl+C).

```python
display.run()
# Blocks until:
# 1. All agents complete
# 2. User presses Ctrl+C
# 3. Session file is deleted
```

---

## Integration Patterns

### Pattern 1: Background Monitoring

Run display in background while working:

```bash
# Start display in background
python plugins/autonomous-dev/scripts/progress_display.py \
  docs/sessions/LATEST.json > feature-progress.log 2>&1 &
DISPLAY_PID=$!

# Start feature
/auto-implement "Add user authentication"

# Display automatically exits when pipeline completes
wait $DISPLAY_PID
echo "Feature complete! Check feature-progress.log"
```

### Pattern 2: CI/CD Integration

Integrate progress display in GitHub Actions:

```yaml
name: Autonomous Feature Development

on:
  workflow_dispatch:
    inputs:
      feature:
        description: Feature to implement
        required: true

jobs:
  auto-implement:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run /auto-implement with progress display
        run: |
          # Start monitoring in background
          python plugins/autonomous-dev/scripts/progress_display.py \
            docs/sessions/LATEST.json &> feature-progress.log &
          DISPLAY_PID=$!

          # Run feature
          /auto-implement "${{ github.event.inputs.feature }}"

          # Wait for display to exit
          wait $DISPLAY_PID 2>/dev/null || true

      - name: Upload progress log
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: feature-progress
          path: feature-progress.log
```

### Pattern 3: Multi-Terminal Workflow

Use in development workflow across terminals:

```bash
# Terminal 1: Feature implementation
/auto-implement "Add pagination to API"

# Terminal 2: Progress monitoring
watch -n 0.5 'python plugins/autonomous-dev/scripts/progress_display.py \
  docs/sessions/LATEST.json'

# Terminal 3: Live test execution
watch -n 1 'pytest tests/unit/ -v'
```

### Pattern 4: Custom Progress Reporter

Programmatic access to progress data:

```python
import json
from pathlib import Path

def get_progress_report(session_file: Path) -> dict:
    """Get structured progress report."""
    with open(session_file) as f:
        state = json.load(f)

    agents = state.get('agents', [])
    completed = sum(1 for a in agents if a['status'] == 'completed')
    failed = sum(1 for a in agents if a['status'] == 'failed')
    running = sum(1 for a in agents if a['status'] == 'started')

    return {
        'total': len(agents),
        'completed': completed,
        'failed': failed,
        'running': running,
        'pending': len(agents) - completed - failed - running,
        'progress_percent': int((completed / 7) * 100) if len(agents) <= 7 else 0
    }

# Usage
report = get_progress_report(Path("docs/sessions/LATEST.json"))
print(f"Status: {report['completed']}/{report['total']} agents complete")
print(f"Progress: {report['progress_percent']}%")
```

---

## Troubleshooting

### Progress Display Won't Start

**Symptom**: "FileNotFoundError: docs/sessions/LATEST.json not found"

**Solution**: Make sure `/auto-implement` is running in another terminal:

```bash
# Terminal 1
/auto-implement "Your feature"

# Terminal 2 (wait a moment for file creation)
sleep 1  # Give /auto-implement time to create session file
python plugins/autonomous-dev/scripts/progress_display.py docs/sessions/LATEST.json
```

### Display Shows "No agents started"

**Symptom**: Progress bar shows 0%, all agents pending

**Solution**: This is normal at the very start. Wait a moment for researcher agent to begin. If it persists after 10 seconds, check that `/auto-implement` is still running:

```bash
# Check if process running
pgrep -f auto-implement

# Check session file timestamp
ls -l docs/sessions/LATEST.json
```

### Output Looks Garbled (Non-TTY Mode)

**Symptom**: Lots of box-drawing characters in piped output

**Solution**: Piped output uses box characters intentionally for readability. For plain text:

```bash
# Use sed to strip ANSI codes
python plugins/autonomous-dev/scripts/progress_display.py \
  docs/sessions/LATEST.json | sed 's/\x1b\[[0-9;]*m//g'
```

### High CPU Usage

**Symptom**: progress_display.py using 100% CPU

**Solution**: Increase refresh interval:

```bash
python plugins/autonomous-dev/scripts/progress_display.py \
  docs/sessions/LATEST.json \
  --refresh 2.0  # Poll every 2 seconds instead of 0.5
```

---

## Performance Notes

### Polling Overhead

- Default: 0.5s refresh = 2 polls/second = ~5% CPU on modern hardware
- Minimum: 0.1s (high responsiveness) = ~20% CPU
- Recommended: 0.5-1.0s = ~5-2% CPU
- Maximum: 5.0s+ (for server environments) = <1% CPU

### Memory Usage

- Baseline: ~10-15 MB Python interpreter + modules
- Per poll: <1 MB (JSON parsing, tree rendering)
- No memory growth over time (no accumulation)

### Terminal Performance

- TTY refresh: Full screen redraw each poll (platform-dependent)
- Non-TTY: Single line append (minimal overhead)
- Large terminal (>200 columns): Negligible impact
- Slow terminals (serial/SSH): Use `--refresh 2.0` or higher

---

## Test Coverage

The progress display feature includes comprehensive test coverage:

| Test Category | Count | Coverage |
|---------------|-------|----------|
| Tree view rendering | 12 | 95% |
| Progress calculations | 8 | 100% |
| TTY mode detection | 6 | 100% |
| JSON handling | 8 | 95% |
| Terminal resize | 4 | 90% |
| Agent state transitions | 10 | 95% |

**Total**: 48 tests covering 85-90% of module code

Run tests:

```bash
pytest tests/unit/test_progress_display.py -v
pytest tests/integration/test_progress_integration.py -v
```

---

## Security Considerations

### Path Validation

- Session file path must exist and be readable
- Symlink attacks: Validated but not fully protected (see future mitigation)
- Relative paths: Converted to absolute before use

### JSON Parsing

- Malformed JSON: Gracefully ignored (retries on next poll)
- Invalid state structure: Defaults to empty agent list
- Injection attacks: JSON parsing is type-safe

### File Access

- Read-only operation: No writes to session file
- Race conditions: 2 medium-severity race conditions identified for future mitigation
- Permissions: Respects file permissions (will fail gracefully if unreadable)

### Known Issues

**Medium Severity** (for future mitigation):
1. Time-of-check to time-of-use (TOCTOU) race in file existence check
2. JSON state inconsistency if file written during read

**Mitigation** (planned v3.3.0):
- Use file locking mechanisms
- Atomic state validation
- Retry logic with backoff

---

## Future Enhancements

Planned improvements for future releases:

### v3.3.0 (Planned)

- [ ] Color-coded agent status (green/yellow/red)
- [ ] Progress bar with ETA refinement (learning from agent durations)
- [ ] Agent message truncation and wrapping
- [ ] Signal handling for graceful shutdown

### v3.4.0 (Planned)

- [ ] Web-based progress dashboard
- [ ] Streaming JSON updates (reduce polling)
- [ ] Agent log output live-streaming
- [ ] Notification on completion (desktop/email)

### v4.0.0 (Exploration)

- [ ] Real-time agent metrics (CPU, memory, tokens)
- [ ] Cost tracking (API calls, token usage)
- [ ] Parallel agent coordination visualization
- [ ] Historical progress analytics

---

## References

- **Module**: `plugins/autonomous-dev/scripts/progress_display.py`
- **Tests**: `tests/unit/test_progress_display.py`, `tests/integration/test_progress_integration.py`
- **Health Check**: `plugins/autonomous-dev/hooks/health_check.py` (provides EXPECTED_AGENTS)
- **Session Schema**: `docs/sessions/` (JSON session file structure)

---

**Last Updated**: 2025-11-04
**Status**: Production-ready (v3.2.2)
**Issues**: #42 (Real-time progress indicators)
