# Issue #390: Agent Teams vs Worktrees for Batch Processing

## Executive Summary

**Decision: KEEP WORKTREES** as the primary batch processing mechanism. Claude Code's Agent Teams feature is not suitable as a replacement for worktree-based batch processing due to three critical blockers: no file-level locking, no session resumption, and one team per session limitation. Agent Teams remains appropriate for research-heavy and read-only use cases.

## Current Batch Architecture

The autonomous-dev plugin uses git worktrees for batch processing via `/implement --batch`. Each issue in a batch gets its own worktree -- a separate filesystem copy of the repository created by `git worktree add`. The pipeline processes issues sequentially through the full 9-agent SDLC pipeline (researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master, continuous-improvement-analyst).

Key properties of the current approach:

- **Full filesystem isolation**: Each worktree is an independent copies of the repo. Changes in one worktree cannot affect another.
- **Crash recovery**: If a batch run fails mid-way, state persists in the worktree. `/implement --resume` picks up where it left off.
- **Parallel batches**: Multiple worktree-based batches can run simultaneously in separate terminal sessions.
- **HARD GATE enforcement**: Each issue passes through all 9 agents with explicit quality gates. No issue can skip steps.

## Agent Teams Capabilities

Claude Code's Agent Teams feature (introduced in 2025) enables parallel sub-agent sessions within a single Claude Code instance. Key capabilities:

- **Parallel sessions**: Multiple agents work simultaneously on different tasks
- **Shared task list**: A coordinator distributes work items to teammates
- **Messaging**: Agents can communicate results back to the coordinator
- **Natural language orchestration**: Teams are defined conversationally, not via configuration files
- **Speed**: Parallel execution can be ~3x faster than sequential processing

## Comparison Matrix

| Dimension | Worktrees | Agent Teams | Winner |
|-----------|-----------|-------------|--------|
| File isolation | Full (separate filesystem) | None (shared, last write wins) | Worktrees |
| Session resumption | Yes (`/implement --resume`) | No (teammates lost on interruption) | Worktrees |
| Parallel batches | Yes (multiple worktrees) | No (one team per session) | Worktrees |
| Crash recovery | Reliable (state persists in worktree) | Unreliable (teammates vanish on crash) | Worktrees |
| Enforcement gates | Per-issue HARD GATE (9 agents) | Implicit task completion | Worktrees |
| Speed | Sequential (~1x) | Parallel (~3x faster) | Agent Teams |
| Setup complexity | Medium (git worktree paths) | Low (natural language) | Agent Teams |
| Token cost | Lower (sequential, no coordination overhead) | ~3-4x higher (parallel agents + coordination) | Worktrees |

**Score: Worktrees 6, Agent Teams 2.**

## Critical Blockers

These three issues prevent Agent Teams from replacing worktree-based batch processing:

### 1. No File-Level Locking

Agent Teams operates on a shared filesystem. When multiple agents modify files concurrently, there is no file locking mechanism -- the last write wins. In batch processing, multiple issues frequently touch overlapping files (e.g., `package.json`, shared utilities, test configuration). Without file-level locking, concurrent writes cause silent data loss and write conflicts that are difficult to diagnose.

Worktrees solve this entirely: each issue gets its own filesystem, making concurrent write conflicts impossible by design.

### 2. No Session Resumption

If a batch run is interrupted (crash, timeout, network issue, user cancellation), Agent Teams provides no way to resume. The `/implement --resume` flag that works with worktrees has no equivalent for Agent Teams -- teammates are lost when the session ends or is interrupted. The entire batch must be restarted from scratch.

With worktrees, each issue's progress is preserved in its worktree directory. The `--resume` flag detects completed vs. incomplete issues and picks up exactly where processing stopped.

### 3. One Team Per Session

Claude Code supports only one active Agent Team per session. This means you cannot run multiple batches in parallel using Agent Teams. With worktrees, a user can open multiple terminal sessions and run independent batches simultaneously, each with its own set of worktrees.

This single team limitation also prevents scaling -- a 20-issue batch must be processed by one team in one session, with no ability to split across concurrent teams.

## Where Agent Teams Fits

Despite being unsuitable for batch processing replacement, Agent Teams is a good fit for specific use cases within the autonomous-dev workflow:

- **Research phases**: Multiple agents can explore different aspects of a codebase simultaneously. Analysis and exploration tasks are read-only and conflict-free.
- **Architectural review and debates**: Agents can independently analyze different subsystems and synthesize findings without filesystem writes.
- **Hypothesis testing**: Agents can investigate alternative approaches in parallel, reporting findings to a coordinator for decision-making.
- **Code review**: Multiple reviewers can examine different files or aspects (security, performance, style) simultaneously since review is a read-only operation.
- **Documentation generation**: When generating independent documents that do not overlap, Agent Teams can parallelize the work.

The common thread: tasks that are primarily read-only or produce non-overlapping outputs are appropriate for Agent Teams.

## Recommendation

**Keep worktrees as the primary batch processing mechanism.** The filesystem isolation, crash recovery, and session resumption capabilities are essential for reliable multi-issue batch processing. These are architectural properties of worktrees that Agent Teams cannot replicate without fundamental changes to its shared-filesystem model.

**Consider Agent Teams as an optional enhancement** for research-heavy phases of the pipeline where parallelism provides clear speed benefits and filesystem isolation is not required. A hybrid approach -- using Agent Teams for the research/review steps and worktrees for implementation -- could be explored in a future iteration, but the core batch orchestration must continue using worktree-based isolation.

The worktrees remain the foundation because they provide the guarantees (isolation, resumption, parallel batches) that batch processing requires for production reliability.

## Sources

- Claude Code Agent Teams documentation: https://docs.anthropic.com/en/docs/claude-code/agent-teams
- Claude Code official documentation: https://docs.anthropic.com/en/docs/claude-code
- Anthropic blog - Claude Code updates: https://www.anthropic.com/engineering/claude-code
- autonomous-dev batch processing documentation: [docs/BATCH-PROCESSING.md](../BATCH-PROCESSING.md)
- Git worktree documentation: https://git-scm.com/docs/git-worktree
