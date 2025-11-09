# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-11-09
**Project**: Autonomous Development Plugin for Claude Code 2.0
**Version**: v3.10.0 (Automatic GitHub Issue Creation with Research - Issue #58)

> **📘 Maintenance Guide**: See `docs/MAINTAINING-PHILOSOPHY.md` for how to keep the core philosophy active as you iterate

---

## Project Overview

**autonomous-dev** - Plugin repository for autonomous development in Claude Code.

**Core Plugin**: `autonomous-dev` - 19 AI agents, 19 skills, automation hooks, and slash commands for autonomous feature development

**Install**:
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code (Cmd+Q or Ctrl+Q)
# Done! All commands work: /auto-implement, /align-project, /align-claude, /setup, /sync, /status, /health-check, /pipeline-status, /update-plugin, /create-issue, /uninstall
```

**Commands (19 active, includes /create-issue for GitHub issue automation - Issue #58)**:

**Core Workflow (9)**:
- `/auto-implement` - Autonomous feature development (Claude coordinates 7 agents)
- `/align-project` - Fix PROJECT.md conflicts (alignment-analyzer agent)
- `/align-claude` - Fix documentation drift (validation script)
- `/setup` - Interactive setup wizard (project-bootstrapper agent)
- `/sync` - Unified sync command (smart auto-detection: dev environment, marketplace, or plugin dev) - GitHub #47
- `/status` - Track project progress (project-progress-tracker agent)
- `/health-check` - Validate plugin integrity and marketplace version (Python validation) - GitHub #50
- `/pipeline-status` - Track /auto-implement workflow (Python script)
- `/update-plugin` - Interactive plugin update with backup and rollback (Python CLI) - GitHub #50 Phase 2

**Individual Agents (8)** - GitHub #44, #58:
- `/research <feature>` - Research patterns and best practices (2-5 min)
- `/plan <feature>` - Architecture and implementation planning (3-5 min)
- `/test-feature <feature>` - TDD test generation (2-5 min)
- `/implement <feature>` - Code implementation to make tests pass (5-10 min)
- `/review` - Code quality review and feedback (2-3 min)
- `/security-scan` - Security vulnerability scan and OWASP compliance (1-2 min)
- `/update-docs` - Documentation synchronization (1-2 min)
- `/create-issue <request>` - Create GitHub issue with research integration (3-8 min) - GitHub #58

**Utility Commands (2)**:
- `/test` - Run automated tests (pytest wrapper)
- `/uninstall` - Remove or disable plugin features (advanced)

---

## Context Management (CRITICAL!)

### Why This Matters

- ❌ Without clearing: Context bloats to 50K+ tokens after 3-4 features → System fails
- ✅ With clearing: Context stays under 8K tokens → Works for 100+ features

### After Each Feature: Clear Context

```bash
/clear
```

**What this does**: Clears conversation (not files!), resets context budget, maintains performance

**When to clear**:
- ✅ After each feature completes (recommended for optimal performance)
- ✅ Before starting unrelated feature
- ✅ If responses feel slow

### Session Files Strategy

Agents log to `docs/sessions/` instead of context:

```bash
# Log action
python scripts/session_tracker.py agent_name "message"

# View latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

**Result**: Context stays small (200 tokens vs 5,000+ tokens)

---

## PROJECT.MD - Goal Alignment

[`.claude/PROJECT.md`](.claude/PROJECT.md) defines GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE

**Before starting work**:

```bash
# Check alignment
cat .claude/PROJECT.md | grep -A 5 "## GOALS"

# Verify:
# - Does feature serve GOALS?
# - Is feature IN SCOPE?
# - Does feature respect CONSTRAINTS?
```

**Update when strategic direction changes**:
```bash
vim .claude/PROJECT.md
git add .claude/PROJECT.md
git commit -m "docs: Update project goals"
```

---

## Autonomous Development Workflow

1. **Alignment Check**: Verify feature aligns with PROJECT.md
2. **Research**: researcher agent finds patterns (Haiku model - optimized for speed)
3. **Planning**: planner agent creates plan
4. **TDD Tests**: test-master writes failing tests FIRST
5. **Implementation**: implementer makes tests pass
6. **Parallel Validation (3 agents simultaneously)**:
   - reviewer checks code quality
   - security-auditor scans for vulnerabilities
   - doc-master updates documentation
   - Execution: Three Task tool calls in single response enables parallel execution
   - Performance: 5 minutes → 2 minutes (60% faster)
7. **Automated Git Operations (SubagentStop hook - consent-based)**:
   - Triggers when quality-validator agent completes
   - Check environment variables for consent: `AUTO_GIT_ENABLED`, `AUTO_GIT_PUSH`, `AUTO_GIT_PR`
   - Invoke commit-message-generator agent (creates conventional commit)
   - Automatically stage changes, create commit, push, and optionally create PR
   - Graceful degradation: If prerequisites fail (git not available, config missing), feature is still successful
   - Hook file: `plugins/autonomous-dev/hooks/auto_git_workflow.py` (SubagentStop lifecycle)
8. **Context Clear (Optional)**: `/clear` for next feature (recommended for performance)

**Performance Baseline (Issue #46 - Multi-Phase Optimization - Phases 4-7 Complete)**:
- **Phase 4 (Model Optimization - COMPLETE)**: Researcher agent switched to Haiku model (25-39 min baseline)
  - Savings: 3-5 minutes from 28-44 minute baseline
  - Quality: No degradation - Haiku excels at pattern discovery tasks
  - File: `plugins/autonomous-dev/agents/researcher.md` (model: haiku)
- **Phase 5 (Prompt Simplification - COMPLETE)**: Streamlined researcher and planner prompts (22-36 min baseline)
  - Researcher: 59 significant lines (40% reduction from 99 lines)
  - Planner: 73 significant lines (39% reduction from 119 lines)
  - Savings: 2-4 minutes per workflow through faster token processing
  - Quality: Essential guidance preserved, PROJECT.md alignment maintained
- **Phase 6 (Profiling Infrastructure - COMPLETE)**: Performance measurement and bottleneck detection
  - New library: `plugins/autonomous-dev/lib/performance_profiler.py` (539 lines)
  - Features: PerformanceTimer context manager, JSON logging, aggregate metrics, bottleneck detection
  - Test coverage: 71/78 tests passing (91%)
  - Integration: Agents wrapped in PerformanceTimer for automatic timing
  - Enables Phase 7+ optimization decisions based on real data
- **Phase 7 (Parallel Validation Checkpoint - COMPLETE)**: Validates reviewer, security-auditor, doc-master parallel execution
  - New method: `AgentTracker.verify_parallel_validation()` in `scripts/agent_tracker.py`
  - Parallel detection: 5-second window for agent start times
  - Metrics: sequential_time, parallel_time, time_saved_seconds, efficiency_percent
  - Helper methods: `_detect_parallel_execution_three_agents()`, `_record_incomplete_validation()`, `_record_failed_validation()`
  - Integration: CHECKPOINT 4.1 added to `plugins/autonomous-dev/commands/auto-implement.md`
  - Test coverage: 23 unit tests covering success, parallelization detection, incomplete/failed agents
  - Infrastructure: Validation checkpoints enable Phase 8+ bottleneck detection
- **Cumulative Improvement**: 5-9 minutes saved per workflow (15-32% faster, 24% overall improvement)

---

## Git Automation Control

Automatic git operations (commit, push, PR creation) can be optionally enabled after `/auto-implement` completes.

**Status**: Optional feature (disabled by default for safety)

**Environment Variables** (set in `.env` file):

```bash
# Master switch - enables automatic git operations after /auto-implement
AUTO_GIT_ENABLED=true        # Default: false

# Enable automatic push to remote (requires AUTO_GIT_ENABLED=true)
AUTO_GIT_PUSH=true           # Default: false

# Enable automatic PR creation (requires AUTO_GIT_ENABLED=true and gh CLI)
AUTO_GIT_PR=true             # Default: false
```

**How It Works**:

1. `/auto-implement` completes STEP 6 (parallel validation)
2. quality-validator agent completes (last validation agent)
3. SubagentStop hook triggers `auto_git_workflow.py`
4. Hook checks consent via environment variables (non-blocking if disabled)
5. If enabled, invokes commit-message-generator agent to create conventional commit message
6. Stages changes, commits with agent-generated message, optionally pushes and creates PR
7. If any prerequisite fails (git not configured, merge conflicts, etc.), provides manual fallback instructions
8. Feature is successful regardless of git operation outcome (graceful degradation)

**Consent-Based Design**:

- Disabled by default - no behavior change without explicit opt-in
- Validates all prerequisites before attempting operations
- Non-blocking - git automation failures don't affect feature completion
- Always provides manual fallback instructions if automation fails

**Security**:

- Uses `security_utils.validate_path()` for all file path validation (CWE-22, CWE-59)
- Audit logs all operations to `logs/security_audit.log`
- No credential logging - never exposes API keys or passwords
- Subprocess calls prevent command injection attacks
- Safe JSON parsing (no arbitrary code execution)

**Implementation Files**:

- Hook: `/plugins/autonomous-dev/hooks/auto_git_workflow.py` (588 lines) - SubagentStop lifecycle hook
- Library: `/plugins/autonomous-dev/lib/auto_implement_git_integration.py` (1,466 lines) - Core integration logic
  - Functions: `execute_step8_git_operations()` (main entry point), `check_consent_via_env()`, `validate_git_state()`, `create_commit_with_agent_message()`, `push_and_create_pr()`
  - Validation: `validate_agent_output()`, `validate_git_state()`, `validate_branch_name()`, `validate_commit_message()`, `check_git_credentials()`, `check_git_available()`, `check_gh_available()`
  - Agents: Invokes commit-message-generator and pr-description-generator agents with workflow context

**Related GitHub Issues**:
- Issue #58: Automatic git operations integration (feature implementation)

**For detailed usage**: See `plugins/autonomous-dev/README.md` "Enable automatic git operations in /auto-implement workflow" section

---

## Architecture

### Agents (19 specialists with active skill integration - GitHub Issue #35, #58)

Located: `plugins/autonomous-dev/agents/`

**Core Workflow Agents (9)** with skill references (orchestrator deprecated v3.2.2 - Claude coordinates directly):
- **researcher**: Web research for patterns and best practices - Uses research-patterns skill
- **planner**: Architecture planning and design - Uses architecture-patterns, api-design, database-design, testing-guide skills
- **test-master**: TDD specialist (writes tests first) - Uses testing-guide, security-patterns skills
- **implementer**: Code implementation (makes tests pass) - Uses python-standards, observability skills
- **reviewer**: Quality gate (code review) - Uses code-review, consistency-enforcement, python-standards skills
- **security-auditor**: Security scanning and vulnerability detection - Uses security-patterns, python-standards skills
- **doc-master**: Documentation synchronization - Uses documentation-guide, consistency-enforcement, git-workflow, cross-reference-validation, documentation-currency skills
- **advisor**: Critical thinking and validation (v3.0+) - Uses semantic-validation, advisor-triggers, research-patterns skills
- **quality-validator**: GenAI-powered feature validation (v3.0+) - Uses testing-guide, code-review skills

**Utility Agents (10)** with skill references:
- **alignment-validator**: PROJECT.md alignment checking - Uses semantic-validation, file-organization skills
- **commit-message-generator**: Conventional commit generation - Uses git-workflow, code-review skills
- **pr-description-generator**: Pull request descriptions - Uses github-workflow, documentation-guide, code-review skills
- **issue-creator**: Generate well-structured GitHub issue descriptions (v3.10.0+, GitHub #58) - Uses github-workflow, documentation-guide, research-patterns skills
- **project-progress-tracker**: Track progress against goals - Uses project-management skill
- **alignment-analyzer**: Detailed alignment analysis - Uses research-patterns, semantic-validation, file-organization skills
- **project-bootstrapper**: Tech stack detection and setup (v3.0+) - Uses research-patterns, file-organization, python-standards skills
- **setup-wizard**: Intelligent setup - analyzes tech stack, recommends hooks (v3.1+) - Uses research-patterns, file-organization skills
- **project-status-analyzer**: Real-time project health - goals, metrics, blockers (v3.1+) - Uses project-management, code-review, semantic-validation skills
- **sync-validator**: Smart dev sync - detects conflicts, validates compatibility (v3.1+) - Uses consistency-enforcement, file-organization, python-standards, security-patterns skills

**Note on Orchestrator Removal (v3.2.2)**:
The "orchestrator" agent was removed because it created a logical impossibility - it was Claude coordinating Claude. When `/auto-implement` invoked the orchestrator agent, it just loaded orchestrator.md as Claude's system prompt, but it was still the same Claude instance making decisions. This allowed Claude to skip agents by reasoning they weren't needed.

**Solution**: Moved all coordination logic directly into `commands/auto-implement.md`. Now Claude explicitly coordinates the 7-agent workflow without pretending to be a separate orchestrator. Same checkpoints, simpler architecture, more reliable execution. See `agents/archived/orchestrator.md` for history.

### Skills (19 Active - Progressive Disclosure + Agent Integration)

**Status**: 19 active skill packages using Claude Code 2.0+ progressive disclosure architecture

**Why Active**:
- Skills are **first-class citizens** in Claude Code 2.0+ (fully supported pattern)
- Progressive disclosure solves context bloat elegantly
- Metadata stays in context, full content loads only when needed
- Can scale to 100+ skills without performance issues
- **NEW (v3.5+)**: All 18 agents explicitly reference relevant skills for enhanced decision-making (Issue #35)

**19 Active Skills** (organized by category):
- **Core Development** (6): api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns
- **Workflow & Automation** (4): git-workflow, github-workflow, project-management, documentation-guide
- **Code & Quality** (4): python-standards, observability, consistency-enforcement, file-organization
- **Validation & Analysis** (5): research-patterns, semantic-validation, cross-reference-validation, documentation-currency, advisor-triggers

**How It Works**:
1. **Progressive Disclosure**: Skills auto-activate based on task keywords. Claude loads full SKILL.md content only when relevant, keeping context efficient.
2. **Agent Integration** (NEW): Each agent's prompt includes a "Relevant Skills" section listing specialized knowledge available for that agent's domain. This helps agents recognize when to apply specialized skills.
3. **Combined Effect**: Agent + skill integration prevents hallucination while scaling to 100+ skills without context bloat.

**Agent-Skill Mapping** (all 18 agents now have skill references):
- See agent prompts in `plugins/autonomous-dev/agents/` for "Relevant Skills" sections
- See `docs/SKILLS-AGENTS-INTEGRATION.md` for comprehensive mapping table

See `docs/SKILLS-AGENTS-INTEGRATION.md` for complete architecture details and agent-skill mapping table.

### Libraries (12 Shared Libraries - v3.4.0+, Enhanced v3.8.1+ with Parity Validation, Enhanced v3.9.0+ with Git Integration, Enhanced v3.10.0+ with Issue Automation)

**Location**: `plugins/autonomous-dev/lib/`

**Core Libraries**:

1. **security_utils.py** (628 lines, v3.4.3+) - Centralized security validation and audit logging
   - Functions: `validate_path()`, `validate_pytest_path()`, `validate_input_length()`, `validate_agent_name()`, `validate_github_issue()`, `audit_log()`
   - Security coverage: CWE-22 (path traversal), CWE-59 (symlink resolution), CWE-117 (log output neutralization)
   - Path validation: 4-layer whitelist defense (string checks → symlink detection → path resolution → whitelist validation)
   - Test mode support: Auto-detects pytest, allows system temp while blocking system directories
   - Audit logging: Thread-safe JSON logging to `logs/security_audit.log` (10MB rotation, 5 backups)
   - Used by: agent_tracker.py, project_md_updater.py, version_detector.py, orphan_file_cleaner.py, and all security-critical operations
   - Test coverage: 638 unit tests (98.3% coverage)
   - Documentation: See `docs/SECURITY.md` for comprehensive guide

2. **project_md_updater.py** (247 lines, v3.4.0+) - Atomic PROJECT.md updates with security validation
   - Functions: `update_goal_progress()`, `_atomic_write()`, `_validate_update()`, `_backup_before_update()`, `_detect_merge_conflicts()`
   - Security: Uses security_utils.validate_path() for whitelist validation, mkstemp() for atomic writes
   - Atomic writes: Temp file creation (mkstemp) → content writing → atomic rename
   - Merge conflict detection: Prevents data loss if PROJECT.md changed during update
   - Test coverage: 24 unit tests (95.8% coverage)
   - Used by: auto_update_project_progress.py hook (SubagentStop)

3. **version_detector.py** (531 lines, v3.7.1+) - Semantic version detection and comparison
   - Classes: `Version` (semantic version object with comparison operators), `VersionComparison` (result dataclass)
   - Functions: `VersionDetector` class (low-level API), `detect_version_mismatch()` (convenience function)
   - Features: Parse semantic versions, compare marketplace vs project versions, detect upgrades/downgrades, handle pre-release versions
   - Security: Path validation via security_utils, audit logging (CWE-22, CWE-59 protection)
   - Error handling: Clear error messages with context and expected format
   - Pre-release support: Correctly handles `MAJOR.MINOR.PATCH` and `MAJOR.MINOR.PATCH-PRERELEASE` patterns
   - Test coverage: 20 unit tests (version parsing, comparison, edge cases)
   - Used by: sync_dispatcher.py for marketplace version detection
   - Related: GitHub Issue #50

4. **orphan_file_cleaner.py** (514 lines, v3.7.1+) - Orphaned file detection and cleanup
   - Classes: `OrphanFile` (orphan representation), `CleanupResult` (result with summary), `OrphanFileCleaner` (low-level API)
   - Functions: `detect_orphans()` (detection only), `cleanup_orphans()` (cleanup with mode control)
   - Features: Detect orphans in commands/hooks/agents, dry-run mode (safe), confirm mode (user approval), auto mode (non-interactive)
   - Security: Path validation via security_utils, audit logging to `logs/orphan_cleanup_audit.log` (JSON format)
   - Error handling: Graceful per-file failures (one orphan failure doesn't block others)
   - Modes: `dry_run=True` (report only), `confirm=True` (ask per file), auto-delete (no prompts)
   - Test coverage: 22 unit tests (detection, cleanup, permissions, dry-run)
   - Used by: sync_dispatcher.py for marketplace sync cleanup
   - Related: GitHub Issue #50

5. **sync_dispatcher.py** (976 lines, v3.7.1+) - Intelligent sync orchestration with version detection and cleanup
   - Classes: `SyncMode` (enum: MARKETPLACE, ENV, PLUGIN_DEV), `SyncResult` (dataclass with version/cleanup attributes), `SyncDispatcher` (main coordinator)
   - High-level API: `sync_marketplace()` convenience function for marketplace sync with enhancements
   - Features: Version detection (project vs marketplace), orphan cleanup (optional), non-blocking error handling, comprehensive audit logging
   - SyncResult attributes:
     - `success`: Whether sync succeeded
     - `mode`: Which sync mode executed
     - `message`: Human-readable result
     - `details`: Additional details (files updated, conflicts, etc.)
     - `version_comparison`: VersionComparison object (NEW, v3.7.1+) with upgrade/downgrade status
     - `orphan_cleanup`: CleanupResult object (NEW, v3.7.1+) with orphan detection/cleanup summary
   - SyncResult.summary property: Auto-generates comprehensive summary including version and cleanup info
   - Marketplace sync enhancement: Integrates version_detector and orphan_file_cleaner
     - Version detection: Runs detect_version_mismatch() for marketplace vs. project comparison
     - Orphan cleanup: Conditional (cleanup_orphans parameter), with dry-run support
     - Error handling: Non-blocking - enhancements don't block core sync
     - Messaging: Shows upgrade/downgrade/up-to-date status and cleanup results
   - Audit logging: All operations logged to security audit (marketplace_sync events)
   - Security: All paths validated via security_utils
   - Test coverage: Comprehensive testing of all sync modes
   - Used by: /sync command, sync_marketplace() high-level API
   - Related: GitHub Issues #47, #50, #51

6. **validate_marketplace_version.py** (371 lines, v3.7.2+) - CLI script for /health-check marketplace integration
   - Purpose: Detects version differences between marketplace plugin and local project plugin
   - Features: CLI interface, version comparison reporting, non-blocking error handling, security validation
   - Functions: `validate_marketplace_version()` (main function), `_parse_version()`, `_format_output()`
   - CLI Arguments:
     - `--project-root`: Project root path (required)
     - `--verbose`: Verbose output
     - `--json`: Machine-readable JSON output format
   - Output Formats:
     - Human-readable: "Project v3.7.0 vs Marketplace v3.7.1 - Update available"
     - JSON: Structured result with version comparison data
   - Return types: `VersionComparison` object (from version_detector.py) with upgrade/downgrade status
   - Security: Path validation via security_utils.validate_path(), audit logging to security audit
   - Error handling: Non-blocking errors (marketplace not found is not fatal), exit code 1 on errors
   - Integration: Called by health_check.py `_validate_marketplace_version()` method
   - Test coverage: 7 unit tests (version comparison, output formatting, error cases)
   - Used by: health-check command (CLI invocation), /health-check validation
   - Related: GitHub Issue #50 Phase 1 (marketplace version validation integration into /health-check)

7. **plugin_updater.py** (868 lines, v3.8.2+) - Interactive plugin update with version detection, backup, rollback, and security hardening
   - Classes: `UpdateError` (base exception), `BackupError` (backup failures), `VerificationError` (verification failures), `UpdateResult` (result dataclass), `PluginUpdater` (main coordinator)
   - Key Methods:
     - `check_for_updates()` - Check for available updates without performing update
     - `update()` - Perform interactive or non-interactive update with options
     - `_create_backup()` - Create timestamped backup (security: 0o700 permissions, symlink detection)
     - `_rollback()` - Restore from backup on failure (with path validation and symlink blocking)
     - `_cleanup_backup()` - Remove backup after successful update
     - `_verify_update()` - Verify update succeeded (version + file validation)
     - `_activate_hooks()` - Activate hooks from new plugin version (added v3.8.1)
   - Features:
     - Interactive confirmation prompts (customizable)
     - Automatic backup before update (timestamped, in /tmp, 0o700 permissions)
     - Automatic rollback on any failure (sync, verification, unexpected errors)
     - Verification: checks version matches expected, validates critical files exist
     - Cleanup: removes backup after successful update
     - Hook activation: Auto-activates hooks from new version (first install only)
   - Error handling: UpdateError base class with specific exceptions (BackupError, VerificationError) for recovery
   - UpdateResult attributes: success, updated, message, old_version, new_version, backup_path, rollback_performed, hooks_activated, hooks_added, details
   - Integration: Uses version_detector.py for version comparison, sync_dispatcher.py for sync operations, hook_activator.py for activation
   - Security (GitHub Issue #52 - 5 CWE vulnerabilities addressed):
     - CWE-22 (Path Traversal): Marketplace path validation, rollback path validation, user home directory check
     - CWE-78 (Command Injection): Plugin name length + format validation (alphanumeric, dash, underscore only)
     - CWE-59 (Symlink Following/TOCTOU): Backup path re-validation after creation, symlink detection
     - CWE-117 (Log Injection): Audit log input sanitization, audit log signature standardized
     - CWE-732 (Permissions): Backup directory permissions 0o700 (user-only)
   - All validations use security_utils module for consistency
   - Audit logging for all security operations to security_audit.log
   - Test coverage: 53 unit tests (39 existing + 14 new security tests, 46 passing, 7 design issues to fix)
   - Used by: update_plugin.py CLI script, /update-plugin command
   - Related: GitHub Issue #50 Phase 2 (interactive plugin update), GitHub Issue #52 (security hardening)

8. **update_plugin.py** (380 lines, v3.8.0+) - CLI script for interactive plugin updates
   - Purpose: Command-line interface for plugin_updater.py with user-friendly prompts and output
   - Functions: `parse_args()` (CLI argument parsing), `main()` (entry point), `_format_version_output()` (display formatting), `_prompt_for_confirmation()` (interactive prompts)
   - CLI Arguments:
     - `--check-only`: Check for updates without performing update (dry-run)
     - `--yes`, `-y`: Skip confirmation prompts (non-interactive mode)
     - `--auto-backup`: Create backup before update (default: enabled)
     - `--no-backup`: Skip backup creation (advanced users only)
     - `--verbose`, `-v`: Enable verbose logging
     - `--json`: Output JSON for scripting (machine-readable)
     - `--project-root`: Path to project root (default: current directory)
     - `--plugin-name`: Name of plugin to update (default: autonomous-dev)
   - Exit codes:
     - `0`: Success (update performed or already up-to-date)
     - `1`: Error (update failed)
     - `2`: No update needed (when --check-only)
   - Output modes:
     - Human-readable: Rich ASCII tables with status indicators and progress
     - JSON: Machine-readable structured output for scripting
     - Verbose: Detailed logging of all operations (backups, verifications, rollbacks)
   - Interactive prompts: Confirmation before update (customizable via --yes flag)
   - Integration: Invokes PluginUpdater from plugin_updater.py
   - Security: Path validation via security_utils, audit logging
   - Error handling: Clear error messages with context and guidance
   - Test coverage: Comprehensive unit tests (argument parsing, output formatting, interactive flow)
   - Used by: /update-plugin command (bash invocation)
   - Related: GitHub Issue #50 Phase 2 (interactive plugin update command)

9. **hook_activator.py** (539 lines, v3.8.1+) - Automatic hook activation during plugin updates
   - Classes: `ActivationError` (base exception), `SettingsValidationError` (validation failures), `ActivationResult` (result dataclass), `HookActivator` (main coordinator)
   - Key Methods:
     - `activate_hooks()` - Activate hooks from new plugin version (main entry point)
     - `detect_first_install()` - Check if settings.json exists (first install vs update detection)
     - `_read_settings()` - Read and parse existing settings.json (with error handling)
     - `_merge_hooks()` - Merge new hooks with existing settings (preserve customizations)
     - `_validate_settings()` - Validate settings structure and content
     - `_ensure_claude_dir()` - Create .claude directory if missing (with permissions)
     - `_atomic_write()` - Write settings.json atomically (tempfile + rename pattern)
   - Features:
     - First install detection: Checks for existing settings.json file
     - Automatic hook activation: Activates hooks from plugin.json on first install
     - Smart merging: Preserves existing customizations when updating
     - Atomic writes: Prevents corruption via tempfile + rename pattern
     - Validation: Structure validation (required fields, hook format)
     - Error recovery: Graceful handling of malformed JSON, permissions issues
   - ActivationResult attributes: activated, first_install, message, hooks_added, settings_path, details
   - Integration: Called by plugin_updater.py `_activate_hooks()` method after successful sync
   - Security: Path validation via security_utils, audit logging to `logs/security_audit.log`, secure permissions (0o600)
   - Error handling: Non-blocking (activation failures don't block plugin update)
   - Test coverage: 41 unit tests (first install, updates, merge logic, error cases, malformed JSON)
   - Used by: plugin_updater.py for /update-plugin command
   - Related: GitHub Issue #50 Phase 2.5 (automatic hook activation)

10. **validate_documentation_parity.py** (880 lines, v3.8.1+) - Documentation consistency validation across CLAUDE.md, PROJECT.md, README.md, and CHANGELOG.md
   - Classes: `ValidationLevel` (enum: ERROR, WARNING, INFO), `ParityIssue` (issue representation), `ParityReport` (validation result), `DocumentationParityValidator` (main coordinator)
   - Validation Categories:
     - `validate_version_consistency()` - Detect when CLAUDE.md date != PROJECT.md date
     - `validate_count_discrepancies()` - Detect when documented counts != actual counts (agents, commands, skills, hooks)
     - `validate_cross_references()` - Detect when documented features don't exist in codebase (or vice versa)
     - `validate_changelog_parity()` - Detect when plugin.json version missing from CHANGELOG.md
     - `validate_security_documentation()` - Detect missing or incomplete security documentation
   - High-level API: `validate_documentation_parity()` convenience function
   - ParityReport attributes:
     - `version_issues`: Version consistency violations
     - `count_issues`: Count discrepancy violations
     - `cross_reference_issues`: Cross-reference validation violations
     - `changelog_issues`: CHANGELOG parity violations
     - `security_issues`: Security documentation violations
     - `has_errors`: Whether report has critical errors
     - `exit_code`: Exit code for CLI use (0=success, 1=warnings, 2=errors)
   - Features: Prevents documentation drift, enforces accuracy, supports CLI with JSON output
   - Security: File size limits (max 10MB per file), path validation via security_utils, safe file reading (no execution)
   - Error handling: Graceful handling of malformed content, missing files, corrupted JSON
   - CLI Arguments:
     - `--project-root`: Project root path (default: current directory)
     - `--verbose`, `-v`: Verbose output
     - `--json`: Machine-readable JSON output format
   - Integration: Integrated into validate_claude_alignment.py hook for automatic parity validation on commit
   - Test coverage: 1,145 unit tests (97%+ coverage), 666 integration tests (doc-master integration, hook blocking, end-to-end workflows)
   - Used by: doc-master agent (parity checklist), validate_claude_alignment.py hook (automatic validation), CLI validation scripts
   - Related: GitHub Issue #56 (automatic documentation parity validation in /auto-implement workflow)

11. **auto_implement_git_integration.py** (1,466 lines, v3.9.0+) - Automatic git operations orchestration
   - Purpose: Core Step 8 integration for /auto-implement workflow (commit, push, PR creation)
   - Key Functions:
     - `execute_step8_git_operations()` - Main entry point orchestrating complete workflow (workflow_id, request, branch, push, create_pr, base_branch)
     - `check_consent_via_env()` - Parse consent from environment variables (AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR)
     - `invoke_commit_message_agent()` - Call commit-message-generator agent (generates conventional commit message)
     - `invoke_pr_description_agent()` - Call pr-description-generator agent (generates PR description)
     - `create_commit_with_agent_message()` - Stage changes and commit with agent-generated message
     - `push_and_create_pr()` - Push to remote and optionally create PR via gh CLI
     - `validate_agent_output()` - Verify agent response is usable (success key, message length, format)
     - `validate_git_state()` - Check repository state (not detached, no merge conflicts, clean working directory)
     - `validate_branch_name()` - Ensure branch name follows conventions
     - `validate_commit_message()` - Validate commit message format (conventional commits)
     - `check_git_credentials()`, `check_git_available()`, `check_gh_available()` - Prerequisite checks
     - `build_manual_git_instructions()`, `build_fallback_pr_command()` - Fallback instruction generation
   - Features:
     - Consent-based automation via environment variables (defaults: all disabled for safety)
     - Agent-driven commit and PR descriptions (uses existing agents)
     - Graceful degradation with manual fallback instructions (non-blocking)
     - Prerequisite validation before operations
     - Subprocess safety (command injection prevention)
     - Comprehensive error handling with actionable messages
   - ExecutionResult attributes: success, commit_sha, pushed, pr_created, pr_url, error, details, manual_instructions
   - Security: Uses security_utils.validate_path() for all paths, audit logs to security_audit.log, safe subprocess calls
   - Integration: Invoked by auto_git_workflow.py hook (SubagentStop lifecycle) after quality-validator completes
   - Error handling: Non-blocking - git operation failures don't affect feature completion (graceful degradation)
   - Used by: auto_git_workflow.py hook, /auto-implement Step 8 (automatic git operations)
   - Related: GitHub Issue #58 (automatic git operations integration)

12. **github_issue_automation.py** (645 lines, v3.10.0+) - Automated GitHub issue creation with research integration
   - Classes: `IssueCreationError` (base exception), `GhCliError` (gh CLI failures), `ValidationError` (input validation), `IssueCreationResult` (result dataclass)
   - Key Functions:
     - `create_github_issue()` - Main entry point orchestrating complete workflow (title, body, labels, assignee, project_root)
     - `validate_issue_title()` - Validate title for security and format
     - `validate_issue_body()` - Validate body length and content (max 65,000 characters - GitHub limit)
     - `check_gh_cli_installed()` - Verify gh CLI available
     - `check_gh_cli_authenticated()` - Verify GitHub authentication
     - `create_issue_via_gh_cli()` - Execute gh issue create command
     - `parse_issue_response()` - Parse gh CLI JSON output
     - `format_fallback_instructions()` - Generate manual fallback steps
   - Features:
     - Research integration: Accepts issue body generated by issue-creator agent
     - Label support: Optional labels from repository defaults or custom
     - Assignee support: Optional assignee assignment
     - Error handling: Non-blocking with detailed fallback instructions
     - Timeout handling: Network timeout recovery
     - JSON output: Machine-readable result format
   - IssueCreationResult attributes: success, issue_number, issue_url, error, details
   - Security: Input validation (CWE-78, CWE-117, CWE-20), subprocess safety, audit logging
   - Integration: Called by create_issue.py CLI script, /create-issue command STEP 3
   - Error handling: Graceful with manual fallback instructions
   - Used by: create_issue.py script, /create-issue command
   - Related: GitHub Issue #58 (GitHub issue automation)

**Design Pattern**: Progressive enhancement (string → path → whitelist) allows graceful error recovery. Non-blocking enhancements (version detection, orphan cleanup, hook activation, parity validation, git automation, issue automation) don't block core operations. Two-tier library design: plugin_updater.py (core logic), update_plugin.py (CLI interface); auto_implement_git_integration.py (core logic), auto_git_workflow.py (hook integration); github_issue_automation.py (core logic), create_issue.py (CLI interface) enables reuse and testing. Feature automation and other enhancements are optional (controlled by flags/hooks).

### Hooks (30 total automation)

Located: `plugins/autonomous-dev/hooks/`

**Core Hooks (10)**:
- `auto_format.py`: black + isort (Python), prettier (JS/TS)
- `auto_test.py`: pytest on related tests
- `security_scan.py`: Secrets detection, vulnerability scanning
- `validate_project_alignment.py`: PROJECT.md validation
- `validate_claude_alignment.py`: CLAUDE.md alignment checking (v3.0.2+)
- `enforce_file_organization.py`: Standard structure enforcement
- `enforce_pipeline_complete.py`: Validates all 7 agents ran (v3.2.2+)
- `enforce_tdd.py`: Validates tests written before code (v3.0+)
- `detect_feature_request.py`: Auto-detect feature requests
- `auto_git_workflow.py`: Automatic git operations after /auto-implement (v3.9.0+, SubagentStop lifecycle)

**Optional/Extended Hooks (20)**:
- `auto_enforce_coverage.py`: 80% minimum coverage
- `auto_fix_docs.py`: Documentation consistency
- `auto_add_to_regression.py`: Regression test tracking
- `auto_track_issues.py`: GitHub issue tracking
- `auto_generate_tests.py`: Auto-generate test boilerplate
- `auto_sync_dev.py`: Sync development changes
- `auto_tdd_enforcer.py`: Strict TDD enforcement
- `auto_update_docs.py`: Auto-update documentation
- `auto_update_project_progress.py`: Auto-update PROJECT.md goals after /auto-implement (v3.4.0+)
- `detect_doc_changes.py`: Detect documentation changes
- `enforce_bloat_prevention.py`: Prevent context bloat
- `enforce_command_limit.py`: Command count limits
- `post_file_move.py`: Post-move validation
- `validate_documentation_alignment.py`: Doc alignment checking
- `validate_session_quality.py`: Session quality validation
- Plus 5 others for extended enforcement and validation

**Lifecycle Hooks**:
- `UserPromptSubmit`: Display project context
- `SubagentStop`: Log agent completion to session; auto-update PROJECT.md progress (v3.4.0+); auto-detect Task tool agents (v3.8.3+)

---

## CLAUDE.md Alignment (New in v3.0.2)

**What it is**: System to detect and prevent drift between documented standards and actual codebase

**Why it matters**: CLAUDE.md defines development practices. If it drifts from reality, new developers follow outdated practices.

**Check alignment**:
```bash
# Automatic (via hook)
git commit -m "feature"  # Hook validates CLAUDE.md is in sync

# Manual check
python .claude/hooks/validate_claude_alignment.py
```

**What it validates**:
- Version consistency (global vs project CLAUDE.md vs PROJECT.md)
- Agent counts match reality (currently 18 agents, orchestrator removed v3.2.2)
- Command counts match installed commands (currently 17 active commands per GitHub #47 /sync unification)
- Documented features actually exist
- Security requirements documented
- Best practices are up-to-date

**If drift detected**:
1. Run validation to see specific issues
2. Update CLAUDE.md with actual current state
3. Commit the alignment fix
4. Hooks ensure all features stay in sync

## Troubleshooting

### "Context budget exceeded"

```bash
/clear  # Then retry
```

### "Feature doesn't align with PROJECT.md"

1. Check goals: `cat .claude/PROJECT.md | grep GOALS`
2. Either: Modify feature to align
3. Or: Update PROJECT.md if direction changed

### "CLAUDE.md alignment drift detected"

This means CLAUDE.md is outdated. Fix it:
```bash
# See what's drifted
python .claude/hooks/validate_claude_alignment.py

# Update CLAUDE.md based on findings
vim CLAUDE.md  # Update version, counts, descriptions

# Commit the fix
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md alignment"
```

### "Agent can't use tool X"

Tool restrictions are intentional (security). If genuinely needed:
```bash
vim plugins/autonomous-dev/agents/[agent].md
# Add to tools: [...] list in frontmatter
```

### "Commands not updating after plugin changes"

**CRITICAL**: `/exit` does NOT reload commands! You need a full restart.

**The Problem**:
- `/exit` - Only ends the current conversation, process keeps running
- Closing window - Process may still run in background
- `/clear` - Only clears conversation history

**The Solution**:
1. **Fully quit Claude Code** - Press `Cmd+Q` (Mac) or `Ctrl+Q` (Linux/Windows)
2. **Verify it's dead**: `ps aux | grep claude | grep -v grep` should return nothing
3. **Wait 5 seconds** for process to fully exit
4. **Restart Claude Code**
5. **Verify**: Commands should now be updated

**Why**: Claude Code caches command definitions in memory at startup. The only way to reload commands is to completely restart the application process.

**When you need a full restart**:
- After installing/updating plugins
- After modifying command files
- After syncing plugin changes
- When new commands don't appear in autocomplete

---

## MCP Server (Optional)

For enhanced Claude Desktop integration, configure the MCP server:

**Location**: `.mcp/config.json`

**Provides**:
- Filesystem access (read/write repository files)
- Shell commands (git, python, npm, etc.)
- Git operations (status, diff, commit)
- Python interpreter (with virtualenv)

**Setup**:
```bash
# See .mcp/README.md for full setup instructions
```

---

## Quick Reference

### Installation
```bash
# 1. Add marketplace
/plugin marketplace add akaszubski/autonomous-dev

# 2. Install plugin
/plugin install autonomous-dev

# 3. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)
```

**Done!** All commands immediately work.

### Optional Setup
```bash
# Only if you want automatic hooks (auto-format on save, etc.)
python .claude/hooks/setup.py
```

### Updating
```bash
# 1. Uninstall
/plugin uninstall autonomous-dev

# 2. Exit and restart Claude Code (REQUIRED!)

# 3. Reinstall
/plugin install autonomous-dev

# 4. Exit and restart again
```

### Daily Workflow
```bash
# Start feature
# (describe feature to Claude)

# After feature completes (optional - for optimal performance)
/clear
```

### Check Session Logs
```bash
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### Update Goals
```bash
vim .claude/PROJECT.md
```

---

## Philosophy

**Automation > Reminders > Hope**

- Automate repetitive tasks (formatting, testing, security, docs)
- Use agents, skills, hooks to enforce quality automatically
- Focus on creative work, not manual checks

**Research First, Test Coverage Required**

- Always research before implementing
- Always write tests first (TDD)
- Always document changes
- Make quality automatic, not optional

**Context is Precious**

- Clear context after features (`/clear` - recommended for optimal performance)
- Use session files for communication
- Stay under 8K tokens per feature
- Scale to 100+ features

---

**For detailed guides**:
- **Users**: See `plugins/autonomous-dev/README.md` for installation and usage
- **Contributors**: See `docs/DEVELOPMENT.md` for dogfooding setup and development workflow

**For code standards**: See CLAUDE.md best practices, agent prompts, and skills for guidance

**For security**: See `docs/SECURITY.md` for security audit and hardening guidance

**Last Updated**: 2025-11-09 (Documentation Parity Validation Added - GitHub Issue #56)
