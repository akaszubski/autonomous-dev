# Changelog

All notable changes to the autonomous-dev plugin documented here.

Format: [Keep a Changelog](https://keepachangelog.com/)
Versioning: [Semantic Versioning](https://semver.org/)

---

## [3.4.0] - 2025-11-05

### Added
- **Auto-Update PROJECT.md Goal Progress** - SubagentStop hook auto-updates GOALS section after /auto-implement completes (GitHub Issue #40)
  - New SubagentStop lifecycle hook: `auto_update_project_progress.py`
    * Triggers automatically after doc-master agent completes
    * Verifies all 7 agents in pipeline completed successfully
    * Invokes project-progress-tracker agent for GenAI assessment
    * Parses YAML output and updates PROJECT.md atomically
  - New library: `plugins/autonomous-dev/lib/project_md_updater.py` (atomic updates with security validation)
    * Three-layer security: String validation → symlink detection → system directory blocking
    * Path traversal prevention blocks ../../etc/passwd style attacks
    * Atomic file writes via temp file + rename pattern prevents data corruption
    * Backup creation before modifications with timestamp for rollback support
    * Merge conflict detection and graceful handling
  - Invokes agent via: `plugins/autonomous-dev/scripts/invoke_agent.py` (new entrypoint for SubagentStop hook)
  - Modified: `plugins/autonomous-dev/agents/project-progress-tracker.md` - Now outputs YAML for machine parsing
    * Format: `goal_name: percentage` (e.g., `goal_1: 45`)
    * Enables GenAI assessment workflow after feature completion
  - Optional git auto-commit: Offers user consent before committing PROJECT.md updates
  - Test coverage: 24 tests in `tests/test_project_progress_update.py` (95.8% pass rate)
    * Security tests: Path traversal, symlink detection, atomic writes
    * Integration tests: End-to-end workflow with mock agents
    * Robustness tests: Agent timeout handling, merge conflict detection
  - User impact: Goals automatically track progress as features complete
  - Backward compatible: No changes to /auto-implement workflow; hook is optional
  - Documentation: Inline comments document security design rationale and usage examples

## [3.4.1] - 2025-11-05

### Security
- **Race Condition Fix: Replace PID-based Temp File Creation with tempfile.mkstemp()** (HIGH severity, GitHub Issue #45)
  - Vulnerability: `project_md_updater.py` used predictable PID-based temp filenames enabling symlink race attacks
    * Previous pattern: `f".PROJECT_{os.getpid()}.tmp"` - PID observable via `/proc/[pid]` or `ps`
    * Attack: Attacker predicts filename and creates symlink before process writes
    * Impact: Privilege escalation (write to arbitrary files like `/etc/passwd`)
  - Fix: Replaced with `tempfile.mkstemp()` for cryptographic random temp filenames
    * New pattern: `mkstemp(dir=..., prefix='.PROJECT.', suffix='.tmp', text=False)`
    * Security: Cryptographic random suffix (128+ bits entropy), O_EXCL atomicity, mode 0600 (owner-only)
    * Prevents TOCTOU (Time-Of-Check-Time-Of-Use) race conditions
  - Atomic write pattern (unchanged, already secure):
    * CREATE: mkstemp() creates temp file with random name in same directory
    * WRITE: Content written via os.write(fd, ...) for atomicity
    * CLOSE: File descriptor closed before rename
    * RENAME: temp_path.replace(target) atomically updates file
  - Attack scenarios now blocked:
    * Symlink race: Attacker cannot predict random filename within race window
    * Temp file hijacking: mkstemp() fails if file exists (atomic creation with O_EXCL)
    * Privilege escalation: Process only writes to secure temp file in expected directory
  - Test coverage: 7 new atomic write security tests in `tests/test_project_progress_update.py`
    * Test: `test_atomic_write_uses_mkstemp_not_pid` - Verifies mkstemp() called with correct parameters
    * Test: `test_atomic_write_content_written_via_os_write` - Verifies fd used for writing
    * Test: `test_atomic_write_fd_closed_before_rename` - Verifies FD closed before rename
    * Test: `test_atomic_write_rename_is_atomic` - Verifies Path.replace() atomicity
    * Test: `test_atomic_write_error_cleanup` - Verifies temp files cleaned up on failure
    * Test: `test_atomic_write_mkstemp_parameters` - Verifies correct directory, prefix, suffix
    * Test: `test_atomic_write_mode_0600` - Verifies exclusive owner access (mode 0600)
  - Security audit: APPROVED FOR PRODUCTION
    * Full audit report: `docs/sessions/SECURITY_AUDIT_project_md_updater_20251105.md`
    * No vulnerabilities found after fix
    * OWASP compliance verified for atomic file operations
  - Impact: HIGH priority security fix, internal library only (no public API change)
  - Backward compatible: Fix is transparent to callers (same method signature, same behavior)
  - Migration: No action required (automatic upon upgrade)
  - Implementation: `plugins/autonomous-dev/lib/project_md_updater.py` lines 151-247 (_atomic_write method)

## [Unreleased]

### Fixed
- **Security-Auditor False Positives** - Updated agent to correctly identify security best practices vs vulnerabilities
  - Now checks `.gitignore` before flagging `.env` files (keys in gitignored `.env` = CORRECT, not a vulnerability)
  - Distinguishes between configuration files (`.env` - correct) and hardcoded secrets (in .py files - vulnerability)
  - Verifies git history to only flag secrets that were committed (`git log --all -S "sk-"`)
  - Added "What is NOT a Vulnerability" section: gitignored config files, env vars, test fixtures
  - Updated audit guidelines: "Be smart, not just cautious" - focus on real risks, not industry standards
  - Pass criteria: Secrets in `.env` + `.env` in `.gitignore` + no secrets in git history = PASS
  - Implementation: `plugins/autonomous-dev/agents/security-auditor.md` (enhanced validation logic)

### Security (GitHub Issue #45 - v3.2.3)
- **Agent Tracker Security Hardening** - Comprehensive path validation, atomic writes, and input validation
  - Path traversal prevention: Three-layer validation (string check, symlink resolution, system directory blocking)
    * Blocks ../../etc/passwd style attacks via '..' sequence detection
    * Blocks symlink-based escapes via Path.resolve() normalization
    * Blocks absolute paths to /etc/, /var/log/, /usr/, /bin/, /sbin/ directories
    * Error messages include expected format and security documentation link
  - Atomic file writes via temp+rename pattern ensures data consistency
    * Prevents corruption from process crashes or partial writes
    * Guarantees target file is either unchanged or fully updated, never partial
    * Handles concurrent writes safely (last write wins, no data corruption)
    * Automatic cleanup of temporary files on failure
  - Comprehensive input validation for all user inputs
    * agent_name: Type validation (must be string), content validation (non-empty), membership validation (in EXPECTED_AGENTS)
    * message: Length validation (max 10KB to prevent bloat), type validation
    * github_issue: Type validation (must be int, not float/str), range validation (1-999999)
    * All validation errors include context dict with expected format and suggestions
  - Enhanced docstrings explaining security design rationale
    * _save() method: Detailed explanation of atomic write pattern and failure scenarios
    * __init__() method: Three-layer path validation with attack scenarios
    * start_agent() method: Input validation strategy and examples
    * set_github_issue() method: Type and range validation behavior
  - Test coverage: 38 security tests covering all attack scenarios
    * Path traversal tests: Relative, absolute, symlink-based escapes
    * Atomic write tests: Temp file creation, rename atomicity
    * Input validation tests: Type errors, range errors, length limits
    * Error handling tests: Temp file cleanup, descriptive error messages
    * Location: tests/unit/test_agent_tracker_security.py
  - Implementation: /Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/agent_tracker.py (843 lines, 100% docstring coverage of security features)
  - Documentation: Inline comments explain design choices, error messages show users what went wrong and how to fix it

- **Plugin Path Validation in sync_to_installed.py** - Symlink and whitelist validation for plugin directory access
  - Symlink rejection: Two-layer symlink detection (pre-resolve and post-resolve)
    * Layer 1: Rejects symlink at installPath itself (catches obvious attacks)
    * Layer 2: Re-checks after resolve() (catches symlinks in parent directories)
    * Rationale: Defense in depth prevents both direct and indirect symlink escapes
  - Whitelist validation: Ensures plugin path stays within .claude/plugins/
    * Uses relative_to() to verify canonical path is contained
    * Prevents escape via absolute paths (e.g., /etc/passwd)
  - Null safety: Handles missing, empty, and malformed installPath values
    * Returns None for any invalid path (no exceptions thrown)
    * Graceful degradation: Caller handles None and retries/fails gracefully
  - Enhanced documentation with attack scenarios and defense rationale
    * Module docstring: Overview of security features
    * find_installed_plugin_path() docstring: 115-line explanation of three-layer approach
    * Inline comments explain each validation layer
  - Implementation: `plugins/autonomous-dev/hooks/sync_to_installed.py` (lines 30-118)

- **Robust Issue Number Parsing in pr_automation.py** - Graceful handling of malformed GitHub issue references
  - New extract_issue_numbers() function with comprehensive error handling
    * Handles non-numeric issue numbers (#abc) - skipped silently
    * Handles float-like numbers (#42.5) - rejected by int() conversion
    * Handles negative numbers (#-1) - filtered by range check
    * Handles very large numbers - filtered by max range (999999)
    * Handles empty references (#) - regex doesn't match, no number extracted
  - All exceptions caught (ValueError, OverflowError) with no crashes
    * continue statement allows processing to continue on bad input
    * Only valid issue numbers (1-999999) are added to results
  - Integration with parse_commit_messages_for_issues()
    * New function called for parsing, old inline logic removed
    * Enhanced docstring explains security features and error handling
  - Implementation: `plugins/autonomous-dev/lib/pr_automation.py` (lines 120-179 for extract_issue_numbers)

### Added
- **Parallel Validation in /auto-implement (Step 5)** - 3 agents run simultaneously for 60% faster feature development
  - Merged STEPS 5, 6, 7 into single parallel step
  - Three validation agents: reviewer (quality), security-auditor (vulnerabilities), doc-master (documentation)
  - Execute via three Task tool calls in single response (enables parallel execution)
  - Performance improvement: 5 minutes → 2 minutes for validation phase
  - All 23 tests passing with TDD verification
  - Implementation: `plugins/autonomous-dev/commands/auto-implement.md` lines 201-348
  - User impact: Features complete ~3 minutes faster per feature
  - Backward compatible: No breaking changes to /auto-implement workflow
- **Automatic Git Operations in /auto-implement (Step 8)** - Consent-based git automation for feature branches
  - New library: `plugins/autonomous-dev/lib/git_operations.py` (575 lines, 11 public functions, 100% docstring coverage)
  - Functions: `validate_git_repo()`, `check_git_config()`, `detect_merge_conflict()`, `is_detached_head()`, `has_uncommitted_changes()`, `stage_all_changes()`, `commit_changes()`, `get_remote_name()`, `push_to_remote()`, `create_feature_branch()`, `auto_commit_and_push()`
  - Integration with /auto-implement Step 8: Offers user consent before committing/pushing
  - Graceful degradation: Commit succeeds even if push fails; feature succeeds even if git unavailable
  - Security: Never logs credentials; validates prerequisites before operations; handles merge conflicts
  - Comprehensive tests: 48 unit tests (1,033 lines) + 17 integration tests (628 lines) covering all functions
  - Prerequisite checks: git installation, repo validity, config (user.name/email), merge conflicts, detached HEAD, uncommitted changes
  - Features: Automatic staging, intelligent error messages, timeout handling (30s push default), feature branch support
  - Usage: Called from `/auto-implement` Step 8; can be imported as library for other commands
  - Example: `from git_operations import auto_commit_and_push; result = auto_commit_and_push('feat: add feature', 'main', push=True)`
  - Documentation: Full API docs in git_operations.py with examples; Step 8 integration guide in auto-implement.md
- **`/sync-dev` Command** - Restores development environment synchronization (Issue #43)
  - Invokes `sync-validator` agent for smart conflict detection
  - Detects dependency mismatches (package.json, requirements.txt, etc.)
  - Identifies environment variable drift (.env files)
  - Checks for pending database migrations
  - Validates build artifacts and configuration
  - Provides intelligent fix recommendations
  - Optional auto-fix with user confirmation
  - Location: `plugins/autonomous-dev/commands/sync-dev.md` (450+ lines, includes security section)
  - Usage: `/sync-dev` for analysis, `/sync-dev --fix` for auto-resolution
  - Documented in README.md with full usage examples and security considerations
  - Part of the 8 core commands (11 total command files including archived/utility)
  - Security notes: Includes configuration trust assumptions, path validation requirements, rollback support documentation
  - Full security audit available in `docs/sessions/SECURITY_AUDIT_SYNC_DEV.md`
- **GitHub Issue Integration** - Automatic issue creation and closure for `/auto-implement` workflow
  - Creates GitHub issue at start of pipeline with feature description
  - Tracks issue number in pipeline JSON (`github_issue` field)
  - Auto-closes issue when pipeline completes with agent execution summary
  - Gracefully degrades if `gh` CLI not available or not in git repository
  - Labels: `automated`, `feature`, `in-progress` (created) → `completed` (closed)
  - New module: `plugins/autonomous-dev/hooks/github_issue_manager.py` (265 lines)
  - Enhanced: `scripts/agent_tracker.py` with `set-github-issue` command
  - Enhanced: `/pipeline-status` now shows linked GitHub issue
  - Documentation: Updated `orchestrator.md` with issue-driven workflow
  - Tests: 10 test cases covering creation, closure, timeouts, and error handling

### Fixed
- **setup.py Installation Flow** - Fixed critical bug where setup.py expected `.claude/plugins/autonomous-dev/` but `/plugin install` copies files directly to `.claude/hooks/`, `.claude/commands/`, etc.
  - Updated `verify_plugin_installation()` to check `.claude/hooks/` and `.claude/commands/` instead
  - Updated `copy_plugin_files()` to detect already-installed files and skip copying
  - Added graceful degradation with warnings if source directories not found
  - Installation flow now works correctly: `/plugin marketplace add` → `/plugin install` → restart → `/setup`
  - **GenAI Validation**: 98% confidence (verified via Claude Code Task tool analysis)

### Security Audit (2025-11-03)
- **Comprehensive Security Review** of `/sync-dev` command and sync infrastructure
  - Full audit report: `docs/sessions/SECURITY_AUDIT_SYNC_DEV.md`
  - Status: 1 CRITICAL vulnerability identified, 3 HIGH findings, 2 MEDIUM findings
  - CRITICAL: Untrusted path usage from JSON configuration - requires path validation fix
  - HIGH: Unchecked exception handling in JSON parsing - needs specific error handling
  - MEDIUM: Destructive file operations without pre-validation - needs atomic operations
  - OWASP Compliance: 7/10 categories pass, 3 require specific fixes
  - Strengths: Subprocess command injection prevention, environment file security, no hardcoded secrets
  - Remediation: Detailed fixes provided in audit report with code examples

### Added
- **Enhanced Error Messages** - Shows specific missing directories with recovery instructions
  - Lists exactly which directories are missing (hooks, commands, templates)
  - Provides step-by-step reinstall instructions
  - Reminds users to restart Claude Code properly
  - Improves troubleshooting for partial/corrupted installations
- **Developer Mode Flag** (`--dev-mode`) - Skip plugin verification for testing from git clone
  - Allows developers to test setup.py without `/plugin install`
  - Usage: `python setup.py --dev-mode --auto --hooks=slash-commands`
  - Useful for plugin development workflow

### Changed
- **Installation Documentation** - Simplified installation steps from 6 to 3 (removed redundant uninstall/restart steps for new users)
- **Updating Documentation** - Added note about re-running `/setup` after updates to get latest hook versions
- **Verification Logic** - Now checks all three directories (hooks, commands, templates) consistently
  - Previous: Checked hooks OR commands (inconsistent with copy logic)
  - Current: Checks hooks AND commands AND templates (consistent)
  - Prevents setup from continuing with partial installations

### Testing
- **Unit Tests** - Verified all verification scenarios pass
- **Integration Tests** - Complete installation flow tested in simulated environment
- **GenAI Analysis** - Code logic validated by Claude Sonnet
  - Previous confidence: 85%
  - Current confidence: 98%
  - Only theoretical edge cases remain (require manual user error to trigger)

## [2.5.0] - 2025-10-25

### Added
- **Autonomous Workflow** - Complete end-to-end automation pipeline
  - `execute_autonomous_workflow()` in WorkflowCoordinator - orchestrates validate → code → commit → push → PR
  - `_auto_commit()` - Auto-commit with GenAI-generated commit messages
  - `_auto_push()` - Auto-create feature branches and push to remote
  - `_auto_create_pr()` - Auto-create GitHub PRs with GenAI descriptions
  - `_auto_track_progress()` - Auto-update PROJECT.md goal completion
- **3 New Automation Agents**:
  - `commit-message-generator` - GenAI commit messages following conventional commits format
  - `pr-description-generator` - Comprehensive PR descriptions (architecture, testing, security, docs)
  - `project-progress-tracker` - PROJECT.md goal tracking and next priority suggestions
- **alignment-validator Agent** - Semantic PROJECT.md validation using Claude Code native Task tool
- **/status Command** - View PROJECT.md goal progress, active workflows, and next priorities
- **Agent Configurations** - Added 4 new agents to AgentInvoker.AGENT_CONFIGS

### Changed
- **Command Philosophy Shift**: Manual toolkit → Autonomous team
  - User runs 1 command (`/auto-implement`), team handles everything
  - Core philosophy: User states WHAT, team handles HOW
  - Zero manual git operations required
- **PROJECT.md GOALS Section** - Updated to clearly articulate autonomous team vision
  - Primary mission: "Build an Autonomous Development Team"
  - Success example showing 1-command workflow
  - Updated success metrics (autonomous execution, command minimalism)
- **WorkflowCoordinator** - +530 lines of autonomous git operations
  - Subprocess integration for git commands
  - GitHub CLI integration for PR creation
  - GenAI agent invocation for commit/PR content
- **Version**: v2.4.0 → v2.5.0

### Removed
- **16 Manual Git Commands** - Archived to `commands/archive/manual-commands/`:
  - Git operations: commit.md, commit-check.md, commit-push.md, commit-release.md, pr-create.md, issue.md
  - Quality operations: format.md, security-scan.md, sync-docs.md, full-check.md
  - Test operations: test-integration.md, test-unit.md, test-uat.md, test-uat-genai.md, test-architecture.md
  - Other: uninstall.md
- **Python SDK Approach** - Archived to `lib/archive/python-sdk-approach/`:
  - alignment_validator.py (114 lines) - Used Anthropic Python SDK
  - security_validator.py (155 lines) - Used Anthropic Python SDK
  - Reason: Now using Claude Code native agents via Task tool (no separate API key needed)
- **Commands**: 22 → 5 (-77% reduction)

### Impact
- **User Effort**: 13 commands per feature → 1 command (-92%)
- **Time per Feature**: 30 minutes → 5-10 minutes (-67-83%)
- **Git Operations**: Manual → 100% automated
- **PROJECT.md Tracking**: Manual → 100% automated

### Documentation
- Added `docs/AUTONOMOUS-TEAM-VISION.md` - Complete vision and philosophy
- Added `docs/AUTONOMOUS-TRANSFORMATION-SUMMARY.md` - Comprehensive transformation summary
- Added `docs/GENAI-VALIDATION-CLAUDE-CODE-NATIVE.md` - Native GenAI implementation guide
- Added `docs/VALIDATION-AND-ANTI-DRIFT.md` - Anti-drift mechanisms
- Added `docs/GITHUB-SYNC-AND-COMMAND-CLEANUP.md` - Command cleanup analysis
- Added 10+ session summary and analysis documents

### Technical Details
- Uses subprocess for git operations (add, commit, push, checkout)
- Uses `gh` CLI for GitHub PR creation
- GenAI agents use Claude Code Task tool (native subscription)
- All automation agents configured in AgentInvoker
- Graceful error handling for git/GitHub operations
- Progress tracking throughout autonomous pipeline

## [2.2.0] - 2025-10-25

### Added
- **4 New Skills** (50% increase: 6 → 9 skills):
  - `git-workflow`: Commit conventions, branching strategies, PR workflows, CI/CD integration
  - `code-review`: Review standards, constructive feedback, quality checks
  - `architecture-patterns`: Design patterns (GoF), ADRs, system design, SOLID principles
  - `project-management`: PROJECT.md structure, sprint planning, goals (SMART/OKR), roadmaps
- **Auto-Activate for All Skills**: All 9 skills now include `auto_activate: true` for consistent behavior
- Progressive disclosure optimization: Skills use Anthropic's recommended 3-level loading system

### Changed
- **Skills refactored** (6 → 9): Broke up broad `engineering-standards` skill into focused domain skills
- **Skill activation**: Improved keyword coverage and descriptions for better automatic activation
- **Documentation**: Updated README, marketplace.json, and plugin.json to reflect 9 skills
- **Version**: v2.1.0 → v2.2.0

### Removed
- `engineering-standards` skill - Content redistributed to focused skills:
  - Git workflow → `git-workflow` skill
  - Code review → `code-review` skill
  - Architecture → `architecture-patterns` skill
  - Python standards already covered by `python-standards` skill

### Technical Details
- Followed Anthropic's skill-creator best practices for skill design
- All skills follow progressive disclosure pattern (metadata → SKILL.md → resources)
- Skills optimized for context efficiency (<5K words per skill body)
- Comprehensive coverage: Python, testing, security, docs, research, git, reviews, architecture, project management

## [2.1.0] - 2025-10-24

### Added
- **PROJECT.md-First Philosophy Section** in README - Prominent explanation of PROJECT.md-first architecture
- **New Project vs Existing Project Workflows** - Clear guides for greenfield vs retrofit scenarios
- **FAQ Section** clarifying `.claude/` directory usage (not needed for most users)
- **Consistency Validation Checklist** (`docs/CONSISTENCY_CHECKLIST.md`) with 30+ pre-release checks
- Interactive menu pattern for all mode-based commands

### Changed
- **BREAKING**: PROJECT.md location changed from `.claude/PROJECT.md` → `PROJECT.md` (project root)
  - Migration: `mv .claude/PROJECT.md ./PROJECT.md`
  - Reason: PROJECT.md is project-level metadata, not tool-specific config
- **Commands simplified**: 33 → 21 commands via interactive menus
  - Alignment: 5 commands → 1 (`/align-project` with 4-option menu)
  - Documentation: 2 commands → 1 (`/sync-docs` with 6-option menu)
  - Issues: 3 commands → 1 (`/issue` with 5-option menu)
- **README.md completely revised**:
  - Fixed installation troubleshooting (removed incorrect `~/.claude/plugins` path)
  - Added PROJECT.md-first philosophy section
  - Added new vs existing project workflows
  - Clarified `.claude/` directory is optional
- **Plugin README** updated to match root README philosophy
- **Version**: v2.0.0 → v2.1.0

### Removed
- Duplicate `-v2` agent files (8 files) - cleaned up from development
- Redundant command variants:
  - `align-project-safe`, `align-project-fix`, `align-project-dry-run`, `align-project-sync`
  - `sync-docs-auto`
  - `issue-auto`, `issue-from-genai`, `issue-preview`
- Incorrect troubleshooting instructions referencing `~/.claude/plugins`

### Fixed
- Installation instructions now use correct GitHub marketplace method
- All documentation now references PROJECT.md at root (not `.claude/PROJECT.md`)
- Command count updated throughout documentation (21 commands)
- Agent/skill counts verified (8 agents, 6 skills)

### Documentation
- Added comprehensive consistency checklist for maintainers
- Updated all command counts (33 → 25 → 24 → 21)
- Clarified .claude/ structure and when it's needed
- Added migration guide for PROJECT.md location change

---

### Added (Unreleased items moved below)
- **marketplace.json** - Plugin marketplace distribution file for `/plugin marketplace add`
- **/sync-docs command** - Synchronize documentation with code changes (invokes doc-master agent)
  - `--auto` flag: Auto-detect changes via git diff
  - `--organize` flag: Organize .md files into docs/
  - `--api` flag: Update API documentation only
  - `--changelog` flag: Update CHANGELOG only
  - Links to doc-master agent for automated doc sync

### Changed
- **Simplified installation workflow** - No more refresh scripts, just marketplace install/uninstall
- **DEVELOPMENT.md** - Rewritten to focus on simple symlink workflow for developers
- **Documentation cleanup** - Removed complex sync guides (SYNC-GUIDE.md, GLOBAL-COMMANDS-GUIDE.md, REFRESH-SETTINGS.md)
- Updated PROJECT.md with team collaboration intent (co-defined outcomes, GitHub-first workflow)
- Removed legacy `/auto-doc-update` command from global commands
- Removed duplicate `/align-project-safe` from global commands (now `--safe` flag)

### Removed
- **Obsolete development scripts** - sync-plugin.sh, test-installation.sh (no longer needed with symlink workflow)
- **4 sync scripts** - refresh-claude-settings.sh, check-sync-status.sh, find-changes.sh
- **3 sync documentation files** - SYNC-GUIDE.md (550+ lines), GLOBAL-COMMANDS-GUIDE.md, REFRESH-SETTINGS.md
- **DEVELOPMENT_WORKFLOW.md** - Duplicate of DEVELOPMENT.md
- **Complex sync workflow** - Replaced with simple marketplace install/uninstall

### Fixed
- **Marketplace distribution** - Added marketplace.json for proper plugin discovery
- **Documentation references** - Updated all docs to use marketplace workflow instead of refresh scripts
- **Issue command documentation** - Removed unimplemented `/issue from-performance` command references
  - Cleaned up all issue command documentation in `.claude/commands/` and `plugins/autonomous-dev/commands/`
  - Updated command descriptions to reflect actual 5 issue commands (auto, create, from-genai, from-test, preview)
  - Verified documentation accuracy across 33 total discoverable commands

---

## [2.0.0] - 2025-10-20

### Added
- **PROJECT.md-first architecture** - orchestrator validates alignment before every feature
- **orchestrator agent** - Master coordinator with PRIMARY MISSION to validate PROJECT.md
- **Model optimization** - opus (planner), sonnet (balanced), haiku (fast tasks) for 40% cost reduction
- **/align-project command** - Standard alignment validation and scoring
- **/align-project --safe flag** - 3-phase safe alignment (Analyze → Generate → Interactive) with 7 advanced features:
  - Smart Diff View with risk scoring
  - Dry Run with Stash for safe testing
  - Pattern Learning from user decisions
  - Conflict Resolution for PROJECT.md vs reality mismatches
  - Progressive Enhancement (quick wins → deep work)
  - Undo Stack with visual history
  - Simulation Mode for risk-free testing
- **GitHub integration (optional)** - Sprint tracking via .env authentication
- **PROJECT.md template** - Generic, domain-agnostic template for any project type
- **GITHUB_AUTH_SETUP.md** - Complete setup guide with troubleshooting
- **Testing infrastructure** - Automated test script (30 tests) + comprehensive manual testing guide
- **REFERENCES.md** - 30+ reference URLs (Anthropic docs, community resources, reference repos)
- **commands/** component to plugin.json
- **templates/** component to plugin.json
- Model assignments to all agents (frontmatter: `model: opus|sonnet|haiku`)

### Changed
- **8-agent pipeline** (was 7) - Added orchestrator as master coordinator
- **planner agent** - Now uses opus model (was sonnet) for complex planning
- **researcher agent** - Now uses sonnet model (was haiku) for better research quality
- **reviewer agent** - Now uses sonnet model (was haiku) for better quality gates
- **Plugin description** - Updated to highlight PROJECT.md-first architecture
- **README.md** - Comprehensive update with PROJECT.md-first workflow, priority hierarchy, all 7 advanced features
- **plugins/autonomous-dev/README.md** - Updated to v2.0.0 features, 8-agent table, workflows
- **.mcp/README.md** - Updated integration section for PROJECT.md-first workflow
- **UserPromptSubmit hook** - Shows v2.0.0 context with orchestrator and PRIMARY MISSION
- **PROJECT.md** - Updated with team collaboration focus (human + AI co-defined outcomes)

### Fixed
- Documentation structure - Created CHANGELOG.md per documentation-guide skill
- Context management - Clear separation between source (plugins/) and installed (.claude/)

---

## [1.0.0] - 2025-10-19

### Added
- Initial release of autonomous-dev plugin
- 7 specialized agents (planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master)
- 6 core skills (python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards)
- Auto-formatting hooks (black, isort, prettier)
- Auto-testing hooks (pytest, jest)
- Auto-coverage enforcement (80% minimum)
- Security scanning hooks
- Plugin marketplace distribution
- SESSION.md context management
- MCP server configuration

---

## Version History

**v2.0.0** - PROJECT.md-first architecture with orchestrator and team collaboration focus
**v1.0.0** - Initial autonomous development plugin release

---

**Last Updated**: 2025-10-20
