---
description: Show agent pipeline execution status for current session
---

# Pipeline Status

Display which agents have run in the current session and verify pipeline completeness.

## What This Command Does

Shows:
- Which agents have executed (researcher, planner, test-master, etc.)
- Agent status (started, completed, failed)
- Execution timestamps and duration
- Tools used by each agent
- Pipeline completeness (are all expected agents present?)

This helps you:
- ✅ **Verify workflow** - Confirm full SDLC pipeline executed
- ✅ **Debug issues** - See which agents ran and when
- ✅ **Track progress** - Monitor autonomous execution in real-time
- ✅ **Prove compliance** - Show that all required steps were followed

## How It Works

Reads the structured pipeline log file for today:
- Location: `docs/sessions/{date}-{time}-pipeline.json`
- Format: JSON with agent invocations, timestamps, status
- Created by: SubagentStop hook (automatic)
- Updated by: Orchestrator and agents during execution

## Usage

Just run the command:

```bash
/pipeline-status
```

## Example Output

```
📊 Agent Pipeline Status (20251103-143022)

Session started: 2025-11-03T14:30:22
Session file: 20251103-143022-pipeline.json

✅ researcher           COMPLETE  14:35:10 (285s) - Found 3 JWT patterns (tools: WebSearch, Grep, Read)
✅ planner              COMPLETE  14:40:25 (315s) - Created implementation plan (tools: Read)
✅ test-master          COMPLETE  14:45:40 (195s) - Wrote 12 tests (all failing) (tools: Write, Bash)
✅ implementer          COMPLETE  14:52:15 (395s) - Implemented JWT auth (tools: Edit, Write, Bash)
✅ reviewer             COMPLETE  14:54:30 (135s) - Quality approved (tools: Read, Grep)
✅ security-auditor     COMPLETE  14:56:10 (100s) - No security issues found (tools: Grep, Bash)
✅ doc-master           COMPLETE  14:57:30 (80s) - Updated README and API docs (tools: Edit)

======================================================================
Pipeline: COMPLETE ✅
Total duration: 25m 25s
```

## When Pipeline is Incomplete

```
📊 Agent Pipeline Status (20251103-103022)

Session started: 2025-11-03T10:30:22
Session file: 20251103-103022-pipeline.json

✅ researcher           COMPLETE  10:32:15 (115s) - Research findings saved
⏳ planner              RUNNING   10:34:20 - Planning architecture...

======================================================================
Pipeline: INCOMPLETE ⚠️  Missing: test-master, implementer, reviewer, security-auditor, doc-master
Total duration: 4m 58s
```

## No Pipeline File

If no pipeline file exists for today:

```
📊 Agent Pipeline Status

No pipeline file found for today.

This usually means:
- Agents haven't been invoked yet today
- Feature work was done manually (without /auto-implement)
- Session log directory doesn't exist

To create pipeline logs:
1. Use /auto-implement for feature work
2. Agents will automatically log to docs/sessions/
3. Run /pipeline-status to verify execution
```

## Implementation

This command simply wraps the `agent_tracker.py` script:

```bash
# Show pipeline status
python scripts/agent_tracker.py status
```

The script:
1. Finds today's most recent pipeline JSON file
2. Parses agent execution data
3. Displays formatted status with timestamps
4. Calculates pipeline completeness
5. Shows total duration

## Integration with Autonomous Workflow

The pipeline status is automatically tracked during `/auto-implement`:

1. **Orchestrator invokes agent** → Logs "started" to pipeline file
2. **Agent executes** → Work happens
3. **Agent completes** → SubagentStop hook logs "completed" with details
4. **User checks status** → `/pipeline-status` shows current state
5. **Commit happens** → PreCommit hook can verify pipeline (optional)

## File Format (JSON)

```json
{
  "session_id": "20251103-143022",
  "started": "2025-11-03T14:30:22",
  "agents": [
    {
      "agent": "researcher",
      "status": "completed",
      "started_at": "2025-11-03T14:30:25",
      "completed_at": "2025-11-03T14:35:10",
      "duration_seconds": 285,
      "message": "Found 3 JWT patterns",
      "tools_used": ["WebSearch", "Grep", "Read"]
    },
    {
      "agent": "planner",
      "status": "completed",
      "started_at": "2025-11-03T14:35:15",
      "completed_at": "2025-11-03T14:40:25",
      "duration_seconds": 310,
      "message": "Created implementation plan",
      "tools_used": ["Read"]
    }
  ]
}
```

## Troubleshooting

### "No pipeline file found"

Cause: Agents haven't been invoked, or manual implementation was used

Solution:
- Use `/auto-implement` for feature work
- Agents will automatically create pipeline logs
- Manual code changes don't create logs (by design)

### "Agent shows 'started' but never 'completed'"

Cause: Agent invocation failed or was interrupted

Solution:
- Check agent output for errors
- Re-run `/auto-implement` to complete workflow
- Agent will start fresh (idempotent)

### "Tools not showing in output"

Cause: Tool extraction is best-effort from agent output

Solution:
- This is expected - Claude Code doesn't provide tool usage directly
- The hook parses output for tool mentions
- Missing tools don't affect pipeline verification

## Related Commands

- `/auto-implement` - Invoke orchestrator (creates pipeline logs)
- `/status` - Show PROJECT.md goal progress
- `/health-check` - Validate all plugin components

## Benefits

1. **Transparency** - See exactly which agents ran and when
2. **Debugging** - Identify pipeline gaps or failures
3. **Compliance** - Prove that SDLC steps were followed
4. **Metrics** - Track agent usage patterns and timing
5. **Confidence** - Verify autonomous workflow executed correctly

---

**This command provides visibility into the autonomous development pipeline, ensuring all SDLC steps were completed.**
