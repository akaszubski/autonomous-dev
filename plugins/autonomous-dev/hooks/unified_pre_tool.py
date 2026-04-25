#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Unified PreToolUse Hook - Consolidated Permission & Security Validation

This hook consolidates five PreToolUse validators into a single dispatcher:
0. Sandbox Enforcer (sandbox_enforcer.py) - Command classification & sandboxing (Issue #171)
1. MCP Security Validator (pre_tool_use.py) - Path traversal, injection, SSRF protection
2. Agent Authorization (enforce_implementation_workflow.py) - Pipeline agent detection
3. Batch Permission Approver (batch_permission_approver.py) - Permission batching
5. Prompt Integrity (Issue #695) - Minimum word count for critical agents
6. Prompt Quality (Issue #842) - Anti-pattern detection for agent/command .md files

Native Tool Fast Path:
- Native Claude Code tools (Read, Write, Edit, Bash, Task, etc.) bypass all 4 validation layers
- These tools are governed by settings.json permissions, not by this hook
- This avoids unwanted permission prompts for built-in tools
- See NATIVE_TOOLS set below for complete list

Decision Logic:
- If tool is native → skip all layers, return "allow" (settings.json governs)
- If project is not autonomous-dev → skip enforcement layers, return "allow"
- If ANY validator returns "deny" → output "deny" (block operation)
- If ALL validators return "allow" → output "allow" (approve operation)
- Otherwise → output "ask" (prompt user)

Layer Execution Order (short-circuit on deny):
0. Layer 0 (Sandbox): Command classification (SAFE → auto-approve, BLOCKED → deny, NEEDS_APPROVAL → continue)
1. Layer 1 (MCP Security): Path traversal, injection, SSRF checks
2. Layer 2 (Agent Auth): Pipeline agent detection
3. Layer 3 (Batch Permission): Permission batching
5. Layer 5 (Prompt Integrity): Minimum word count for critical agents (Issue #695)
6. Layer 6 (Prompt Quality): Anti-pattern detection for agent/command .md writes (Issue #842)

Environment Variables:
- SANDBOX_ENABLED: Enable/disable sandbox layer (default: false for opt-in)
- SANDBOX_PROFILE: Sandbox profile (default: development)
- PRE_TOOL_MCP_SECURITY: Enable/disable MCP security (default: true)
- PRE_TOOL_AGENT_AUTH: Enable/disable agent authorization (default: true)
- PRE_TOOL_BATCH_PERMISSION: Enable/disable batch permission (default: false)
- MCP_AUTO_APPROVE: Enable/disable auto-approval (default: false)
- PRE_TOOL_PIPELINE_ORDERING: Enable/disable pipeline ordering gate (default: true)

Input (stdin):
{
  "tool_name": "Bash",
  "tool_input": {"command": "pytest tests/"}
}

Output (stdout):
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Combined validator reasons"
  }
}

Exit code: 0 (always - let Claude Code process the decision)

Date: 2026-01-02
Issue: GitHub #171 (Sandboxing for reduced permission prompts)
Agent: implementer
"""

import importlib.util
import json
import re
import shlex
import sys
import os
from pathlib import Path
from typing import Dict, Tuple, List

# Module-level session_id extracted from hook stdin (set in main()).
# Logging functions fall back to this when CLAUDE_SESSION_ID env var is absent.
_session_id: str = "unknown"

# Defensive import of python_write_detector (Issue #589).
# Falls back to None so inline regex continues to work if import fails.
_python_write_detector = None
try:
    _hook_path = Path(__file__).resolve().parent
    _lib_candidates = [
        _hook_path.parent / "lib",           # plugins/autonomous-dev/lib
        _hook_path.parents[2] / "lib",        # fallback
    ]
    for _lib_dir in _lib_candidates:
        _detector_path = _lib_dir / "python_write_detector.py"
        if _detector_path.exists():
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location("python_write_detector", str(_detector_path))
            if _spec and _spec.loader:
                _python_write_detector = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_python_write_detector)
            break
except Exception:
    _python_write_detector = None  # Fallback: inline regex in _extract_bash_file_writes

# Module-level agent_type extracted from hook stdin JSON (set in main()).
# Used by _get_active_agent_name() as primary identity source (Issue #591).
_agent_type: str = ""

# Defensive import of repo_detector (Issue #662).
# Uses importlib.util.spec_from_file_location to load the module relative to
# __file__ so the import resolves correctly regardless of sys.path at load time.
# Fail-closed: if the detector is unavailable, _is_adev_project_fn is None and
# _is_adev_project() returns True — enforcement is never silently skipped.
_is_adev_project_fn = None
try:
    _hook_dir = Path(__file__).resolve().parent
    _repo_detector_candidates = [
        _hook_dir.parent / "lib" / "repo_detector.py",           # plugins/autonomous-dev/lib
        _hook_dir.parents[2] / "lib" / "repo_detector.py",        # fallback
    ]
    for _rd_path in _repo_detector_candidates:
        if _rd_path.exists():
            import importlib.util as _rd_ilu
            _rd_spec = _rd_ilu.spec_from_file_location("repo_detector", str(_rd_path))
            if _rd_spec and _rd_spec.loader:
                _rd_mod = importlib.util.module_from_spec(_rd_spec)
                _rd_spec.loader.exec_module(_rd_mod)
                _is_adev_project_fn = _rd_mod.is_autonomous_dev_repo
            break
except Exception:
    _is_adev_project_fn = None  # Fallback: fail closed (always enforce)

_REPO_DETECTOR_AVAILABLE = _is_adev_project_fn is not None


def _is_adev_project() -> bool:
    """Return True if the current working directory is an autonomous-dev repo.

    Wraps the dynamically-loaded repo_detector.is_autonomous_dev_repo.
    Falls back to True (fail-closed) when the module could not be loaded,
    so enforcement is never silently skipped on import failure.
    """
    if _is_adev_project_fn is None:
        return True
    return _is_adev_project_fn()


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

def find_lib_directory(hook_path: Path) -> Path | None:
    """
    Find lib directory dynamically (Issue #113).

    Checks multiple locations in order:
    1. Development: plugins/autonomous-dev/lib (relative to hook)
    2. Local install: ~/.claude/lib
    3. Marketplace: ~/.claude/plugins/autonomous-dev/lib

    Args:
        hook_path: Path to this hook script

    Returns:
        Path to lib directory if found, None otherwise (graceful failure)
    """
    # Try development location first
    dev_lib = hook_path.parent.parent / "lib"
    if dev_lib.exists() and dev_lib.is_dir():
        return dev_lib

    # Try local install
    home = Path.home()
    local_lib = home / ".claude" / "lib"
    if local_lib.exists() and local_lib.is_dir():
        return local_lib

    # Try marketplace location
    marketplace_lib = home / ".claude" / "plugins" / "autonomous-dev" / "lib"
    if marketplace_lib.exists() and marketplace_lib.is_dir():
        return marketplace_lib

    return None


# Add lib directory to path dynamically
LIB_DIR = find_lib_directory(Path(__file__))
if LIB_DIR:
    if not is_running_under_uv():
        sys.path.insert(0, str(LIB_DIR))


def load_env():
    """Load .env file from project root if it exists."""
    env_file = Path(os.getcwd()) / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass  # Silently skip


# Agents authorized for code changes (pipeline agents)
# Issue #147: Consolidated to only active agents that write code/tests/docs
PIPELINE_AGENTS = [
    'implementer',
    'test-master',
    'doc-master',
]

# Agents authorized to create GitHub issues directly (Issue #599)
GH_ISSUE_AGENTS = {'continuous-improvement-analyst', 'issue-creator'}

# Marker file path for allowing gh issue create from commands (Issue #599)
GH_ISSUE_MARKER_PATH = "/tmp/autonomous_dev_gh_issue_allowed.marker"

# Command context file for issue-creating commands (Issue #630)
GH_ISSUE_COMMAND_CONTEXT_PATH = "/tmp/autonomous_dev_cmd_context.json"

# Commands that are authorized to create GitHub issues (Issue #630)
GH_ISSUE_COMMANDS = {'create-issue', 'plan-to-issues', 'improve', 'refactor', 'retrospective'}

# Environment variables protected from inline spoofing in Bash commands (Issue #557)
# Non-prefix vars that don't start with CLAUDE_ are listed individually
PROTECTED_ENV_VARS = {
    'PIPELINE_STATE_FILE', 'ENFORCEMENT_LEVEL', 'AUTONOMOUS_DEV_COMMAND',
}

# Prefix-based protection: any env var starting with these prefixes is protected (Issue #606)
PROTECTED_ENV_PREFIXES: "tuple[str, ...]" = ('CLAUDE_',)

# Exceptions to prefix-based protection (escape hatch for legitimate user CLAUDE_ vars)
PROTECTED_ENV_PREFIX_EXCEPTIONS: "frozenset[str]" = frozenset()

# Code file extensions subject to workflow enforcement
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
    '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
    '.kt', '.scala', '.sh', '.bash', '.zsh', '.vue', '.svelte',
}

# Language-specific pattern groups for code significance detection
PATTERN_GROUPS = {
    'python': {
        'extensions': {'.py'},
        'patterns': [
            (r'\bdef\s+\w+\s*\(', 'Python function'),
            (r'\basync\s+def\s+\w+\s*\(', 'Python async function'),
            (r'\bclass\s+\w+', 'Python class'),
        ]
    },
    'javascript': {
        'extensions': {'.js', '.ts', '.jsx', '.tsx', '.vue', '.svelte'},
        'patterns': [
            (r'\bfunction\s+\w+\s*\(', 'JavaScript function'),
            (r'\basync\s+function\s+\w+\s*\(', 'JavaScript async function'),
            (r'\bconst\s+\w+\s*=\s*(?:async\s*)?\(.*?\)\s*=>', 'Arrow function'),
            (r'\bexport\s+(?:default\s+)?(?:function|class|const)', 'JS export'),
            (r'\bclass\s+\w+', 'JavaScript class'),
        ]
    },
    'shell': {
        'extensions': {'.sh', '.bash', '.zsh'},
        'patterns': [
            (r'\bfunction\s+\w+', 'Shell function'),
        ]
    },
    'go': {
        'extensions': {'.go'},
        'patterns': [
            (r'\bfunc\s+(?:\(\w+\s+\*?\w+\)\s+)?\w+\s*\(', 'Go function'),
        ]
    },
    'rust': {
        'extensions': {'.rs'},
        'patterns': [
            (r'\bfn\s+\w+\s*[<(]', 'Rust function'),
            (r'\bimpl\s+', 'Rust impl block'),
        ]
    },
    'universal': {
        'extensions': None,  # None means applies to ALL code extensions
        'patterns': [
            (r'\btry:\s*\n\s+(?:from|import)\s+', 'Conditional import (try/except)'),
            (r'\bif\s+\w+.*:\s*\n(?:\s+.*\n){3,}else:', 'Multi-branch conditional'),
        ]
    }
}

SIGNIFICANT_LINE_THRESHOLD = 5

# Git subcommands where -n means --no-verify (not a count flag)
_GIT_VERIFY_SUBCOMMANDS = {"push", "commit", "merge"}

# Git subcommands where -f means --force (not something else)
_GIT_FORCE_PUSH_SUBCOMMANDS = {"push"}


def _detect_git_bypass(command: str) -> Tuple[bool, str]:
    """Detect git bypass patterns in a command string.

    Checks for --no-verify, --force on push, git reset --hard,
    git clean -f/-fd, and the -n shorthand on push/commit/merge.

    Handles pipes by only parsing the segment before the first pipe.

    Args:
        command: The shell command string to analyze.

    Returns:
        Tuple of (is_bypass, reason). If is_bypass is True, the command
        should be blocked.
    """
    # Only parse the first command in a pipeline
    pipe_idx = command.find("|")
    if pipe_idx >= 0:
        command = command[:pipe_idx]

    command = command.strip()
    if not command:
        return (False, "")

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    if not tokens:
        return (False, "")

    # Find the git command and subcommand
    git_idx = None
    for i, token in enumerate(tokens):
        if token == "git" or token.endswith("/git"):
            git_idx = i
            break

    if git_idx is None:
        return (False, "")

    # Extract subcommand (first non-flag token after "git")
    subcommand = ""
    for token in tokens[git_idx + 1:]:
        if not token.startswith("-"):
            subcommand = token
            break

    remaining_tokens = tokens[git_idx + 1:]

    # Check --no-verify on any git command
    if "--no-verify" in remaining_tokens:
        return (True, f"git {subcommand} --no-verify bypasses pre-commit/pre-push hooks")

    # Check -n shorthand ONLY on push/commit/merge (not log/diff where it means count)
    if subcommand in _GIT_VERIFY_SUBCOMMANDS:
        for token in remaining_tokens:
            # Match -n as standalone flag or combined flags like -fn
            if token == "-n":
                return (True, f"git {subcommand} -n bypasses verification hooks")
            # Check combined short flags (e.g., -fn, -an) but not subcommand itself
            if token.startswith("-") and not token.startswith("--") and "n" in token and token != subcommand:
                return (True, f"git {subcommand} {token} contains -n (bypasses verification hooks)")

    # Check --force / -f ONLY on push
    if subcommand in _GIT_FORCE_PUSH_SUBCOMMANDS:
        if "--force" in remaining_tokens or "--force-with-lease" in remaining_tokens:
            return (True, f"git push --force can overwrite remote history")
        for token in remaining_tokens:
            if token == "-f":
                return (True, "git push -f can overwrite remote history")

    # Check git reset --hard
    if subcommand == "reset" and "--hard" in remaining_tokens:
        return (True, "git reset --hard discards all uncommitted changes")

    # Check git clean -f or git clean -fd
    if subcommand == "clean":
        for token in remaining_tokens:
            if token.startswith("-") and not token.startswith("--") and "f" in token:
                return (True, "git clean -f permanently deletes untracked files")
        if "--force" in remaining_tokens:
            return (True, "git clean --force permanently deletes untracked files")

    return (False, "")


def validate_sandbox_layer(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate sandbox layer (Layer 0) - command classification and sandboxing.

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Check if sandbox is enabled
    enabled = os.getenv("SANDBOX_ENABLED", "false").lower() == "true"
    if not enabled:
        return ("allow", "Sandbox layer disabled - pass through")

    # Only validate Bash commands
    if tool_name != "Bash":
        return ("allow", "Sandbox layer only validates Bash commands - pass through")

    # Extract command from tool_input
    command = tool_input.get("command", "")
    if not command:
        return ("allow", "No command to validate - pass through")

    try:
        # Try to import sandbox enforcer
        try:
            from sandbox_enforcer import SandboxEnforcer, CommandClassification

            # Create enforcer
            enforcer = SandboxEnforcer(policy_path=None, profile=None)

            # Classify command
            result = enforcer.is_command_safe(command)

            if result.classification == CommandClassification.SAFE:
                # Safe command - auto-approve
                return ("allow", "Sandbox: SAFE command auto-approved")
            elif result.classification == CommandClassification.BLOCKED:
                # Blocked command - deny
                return ("deny", f"Sandbox: BLOCKED - {result.reason}")
            else:  # NEEDS_APPROVAL
                # Unknown command - continue to next layer
                return ("ask", "Sandbox: NEEDS_APPROVAL - unknown command")

        except ImportError:
            # Sandbox enforcer not available - continue to next layer
            return ("ask", "Sandbox enforcer unavailable")

    except Exception as e:
        # Error in validation - continue to next layer (don't block on errors)
        return ("ask", f"Sandbox error: {e}")


NATIVE_TOOLS = {
    "Read", "Write", "Edit", "Glob", "Grep", "Bash",
    "Task", "TaskOutput", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop",
    "AskUserQuestion", "Skill", "SlashCommand", "BashOutput", "NotebookEdit",
    "TodoWrite", "EnterPlanMode", "ExitPlanMode", "AgentOutputTool", "KillShell",
    "LSP", "WebFetch", "WebSearch",
    "Agent", "EnterWorktree", "ExitWorktree", "ToolSearch",
    "CronCreate", "CronDelete", "CronList",
}

# Tool names that represent subagent invocations (Agent tool; legacy: Task)
AGENT_TOOL_NAMES = {"Agent", "Task"}

# Infrastructure file segments protected from direct edits (Issue #483)
# Maps directory path segments to allowed file extensions within that segment.
PROTECTED_INFRA_SEGMENTS = {
    '/agents/': {'.md'},
    '/commands/': {'.md'},
    '/hooks/': {'.py'},
    '/lib/': {'.py'},
    '/skills/': {'.md'},
}

# ============================================================================
# Plan-Exit Enforcement (Issue #926)
#
# Moved from UserPromptSubmit (unified_prompt_validator.py) to PreToolUse here
# because UserPromptSubmit does not fire for in-turn tool calls by the model
# (gh issue create, Task(implementer), etc.). Enforcement at PreToolUse
# observes every tool call and cannot be bypassed by the model executing the
# plan in-turn without a user prompt.
#
# Marker writer (plan_mode_exit_detector.py) and stage advancer
# (unified_session_tracker.py) are unchanged — only the *enforcement* event
# boundary moved.
# ============================================================================

_PLAN_EXIT_MARKER_PATH = ".claude/plan_mode_exit.json"
_PLAN_EXIT_STALE_MINUTES = 30

# Bash allowlists for plan_exited stage — read-only inspection only.
# Command tokenization: `command.split()` + exact match against these sets.
# Any command with injection metacharacters is rejected before tokenization.
_PLAN_EXIT_BASH_ALLOWLIST_1TOKEN: "frozenset[str]" = frozenset({
    "ls", "cat", "head", "tail", "wc", "pwd", "which", "echo",
    "grep", "rg", "tree", "stat", "file", "date", "whoami", "id", "uname",
})

_PLAN_EXIT_BASH_ALLOWLIST_2TOKEN: "frozenset[tuple]" = frozenset({
    ("git", "status"),
    ("git", "log"),
    ("git", "diff"),
    ("git", "show"),
    ("git", "branch"),
    ("git", "blame"),
    ("git", "ls-files"),
    ("git", "rev-parse"),
    ("git", "remote"),
})

_PLAN_EXIT_BASH_ALLOWLIST_3TOKEN: "frozenset[tuple]" = frozenset({
    ("gh", "issue", "view"),
    ("gh", "issue", "list"),
    ("gh", "pr", "view"),
    ("gh", "pr", "list"),
    ("gh", "repo", "view"),
    ("gh", "auth", "status"),
})

# Injection metacharacter tokens. Checked as raw substrings — NOT via shlex.
# shlex would silently accept ';' inside single/double-quoted strings, which
# defeats the purpose of blocking injection. Longer tokens listed first for
# clarity; all matches are equivalent (any match → reject).
#
# A03 BLOCKING fix: '\n' and '\r' are bash command separators (identical to
# ';'). Without these, str.split() at line ~3601 silently splits multi-line
# payloads on whitespace, causing the first token to match the 1-token
# allowlist while subsequent commands execute. Example bypass (now blocked):
# 'ls\nrm -rf .claude/plan_mode_exit.json'.
_PLAN_EXIT_INJECTION_TOKENS: "tuple[str, ...]" = (
    "&&", "||", "$(", "<(", "<<<", "<<",
    ";", "&", "|", "`", "$", "<", ">",
    "\n", "\r",  # newline and carriage-return are bash command separators
)

# Subagents that consume the critique_done marker (allowed terminal actions).
_PLAN_EXIT_CONSUMER_AGENTS: "frozenset[str]" = frozenset({
    "issue-creator",
    "continuous-improvement-analyst",
    "implementer",
})

# MCP tools allowed at plan_exited stage — explicit allowlist (AC #21).
# Structural (regex-based) heuristics are forbidden because they produce
# false-negatives (e.g., "find_and_replace" contains "find" but is a write).
# AC #19: mcp__playwright__browser_evaluate MUST NOT be on this list
# (it executes arbitrary JS in the browser — not read-only).
_PLAN_EXIT_MCP_READONLY: "frozenset[str]" = frozenset({
    # Playwright — read-only browser inspection
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_console_messages",
    "mcp__playwright__browser_network_requests",
    # HuggingFace — read-only search and lookup
    "mcp__claude_ai_Hugging_Face__hf_doc_search",
    "mcp__claude_ai_Hugging_Face__hf_doc_fetch",
    "mcp__claude_ai_Hugging_Face__hub_repo_search",
    "mcp__claude_ai_Hugging_Face__paper_search",
    "mcp__claude_ai_Hugging_Face__space_search",
    "mcp__claude_ai_Hugging_Face__hf_whoami",
    "mcp__claude_ai_Hugging_Face__hf_hub_query",
    "mcp__claude_ai_Hugging_Face__hub_repo_details",
    # Gmail — read-only
    "mcp__claude_ai_Gmail__list_drafts",
    "mcp__claude_ai_Gmail__list_labels",
    "mcp__claude_ai_Gmail__get_thread",
    "mcp__claude_ai_Gmail__search_threads",
    # Calendar — read-only
    "mcp__claude_ai_Google_Calendar__list_calendars",
    "mcp__claude_ai_Google_Calendar__list_events",
    "mcp__claude_ai_Google_Calendar__get_event",
    # Drive — read-only
    "mcp__claude_ai_Google_Drive__list_recent_files",
    "mcp__claude_ai_Google_Drive__search_files",
    "mcp__claude_ai_Google_Drive__read_file_content",
    "mcp__claude_ai_Google_Drive__get_file_metadata",
    "mcp__claude_ai_Google_Drive__get_file_permissions",
})

# Canonical deny reason (AC #5) — same string for all plan-exit denies.
# Issue #938: surfaces all three escape hatches in the canonical reason.
_PLAN_EXIT_DENY_REASON = (
    "Run plan-critic, /implement --skip-review, or set AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1"
)


def _detect_invocation_context(prompt: str) -> "Optional[str]":
    """Detect reinvocation context from prompt text or environment.

    Checks for known markers that indicate a secondary agent invocation
    (remediation, re-review, doc-update-retry) where prompts are naturally
    shorter and should use relaxed shrinkage thresholds.

    Args:
        prompt: The prompt text to scan for markers.

    Returns:
        Context string if detected, None otherwise.
    """
    # 1. Explicit env var takes precedence (coordinator can set this)
    env_ctx = os.getenv("PIPELINE_INVOCATION_CONTEXT", "").strip().lower()
    if env_ctx:
        return env_ctx

    # 2. Scan prompt for known markers (case-insensitive)
    prompt_lower = prompt.lower()

    if "remediation mode" in prompt_lower:
        return "remediation"
    if "re-review" in prompt_lower or "re_review" in prompt_lower:
        return "re-review"
    if "doc-update-retry" in prompt_lower or "reduced context" in prompt_lower or "retry with reduced" in prompt_lower:
        return "doc-update-retry"

    return None


def validate_prompt_integrity(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """Validate agent prompt word count during active pipeline (Issue #695).

    Layer 5: Blocks agent invocations where the prompt is below the minimum
    word count for critical agents. This is deterministic enforcement — the
    coordinator cannot bypass it by ignoring prompt-level instructions.

    Args:
        tool_name: Tool being invoked.
        tool_input: Tool input parameters.

    Returns:
        Tuple of (decision, reason).
    """
    # Only check Agent/Task tool calls
    if tool_name not in AGENT_TOOL_NAMES:
        return ("allow", "Not an agent invocation")

    # Extract agent type first — needed for minimum word count check
    agent_type = tool_input.get("subagent_type", "").strip().lower()
    if not agent_type:
        return ("allow", "Could not determine agent type")

    # Only check critical agents
    try:
        from prompt_integrity import COMPRESSION_CRITICAL_AGENTS, MIN_CRITICAL_AGENT_PROMPT_WORDS
    except ImportError:
        return ("allow", "prompt_integrity module not available - skipping check")

    if agent_type not in COMPRESSION_CRITICAL_AGENTS:
        return ("allow", f"Agent '{agent_type}' is not compression-critical")

    # Extract prompt and check word count — enforced regardless of pipeline state (Issue #716)
    prompt = tool_input.get("prompt", "")
    word_count = len(prompt.split())

    if word_count < MIN_CRITICAL_AGENT_PROMPT_WORDS:
        return (
            "deny",
            f"BLOCKED: Prompt for critical agent '{agent_type}' has only {word_count} words "
            f"(minimum: {MIN_CRITICAL_AGENT_PROMPT_WORDS}). "
            f"Reconstruct the prompt with full context — include the complete implementer "
            f"output, list of changed files, and test results. "
            f"Use get_agent_prompt_template('{agent_type}') to reload the agent's base prompt from disk."
        )

    # Baseline shrinkage check — runs whenever a baseline exists (no pipeline-active gate).
    # Falls open (returns allow) when no baseline is recorded yet. Issue #723.
    # max_shrinkage is 0.20 (20%) — tightened from 0.25 in Issue #812 to catch
    # progressive compression in batch runs. Still above the library default of 15%
    # to give headroom for legitimate prompt variation at the hook level.
    #
    # Issue #764: Use PIPELINE_ISSUE_NUMBER for per-issue baseline isolation.
    # In batch mode, each issue gets its own baseline so cross-issue context
    # pressure doesn't trigger false-positive shrinkage blocks.
    try:
        from prompt_integrity import (
            get_prompt_baseline,
            record_prompt_baseline,
            validate_prompt_word_count,
        )

        # Per-issue isolation (Issue #764): use current issue number for
        # baseline lookup and seeding. When not in batch mode (no issue context),
        # issue_number=None preserves backward-compatible behavior (lowest issue).
        # Issue #779: Use file-based fallback when env var is missing.
        current_issue_num_raw = _get_current_issue_number()
        current_issue_num = current_issue_num_raw if current_issue_num_raw > 0 else None
        current_issue_str = str(current_issue_num) if current_issue_num else None

        baseline_word_count = get_prompt_baseline(
            agent_type, issue_number=current_issue_num
        )

        # Detect reinvocation context for relaxed thresholds (Issue #789, #791)
        invocation_ctx = _detect_invocation_context(prompt)

        if baseline_word_count is not None:
            result = validate_prompt_word_count(
                agent_type, prompt, baseline_word_count,
                max_shrinkage=0.20, invocation_context=invocation_ctx,
            )
            if not result.passed:
                issue_ctx = f" (issue #{current_issue_str})" if current_issue_str else ""
                return (
                    "deny",
                    f"BLOCKED: Prompt for '{agent_type}'{issue_ctx} shrank {result.shrinkage_pct:.1f}% "
                    f"from baseline ({baseline_word_count} words → {word_count} words, "
                    f"threshold: 20%). "
                    f"The agent prompt is being compressed across invocations. "
                    f"REQUIRED NEXT ACTION: Use get_agent_prompt_template('{agent_type}') "
                    f"to reload the full agent prompt from disk and reconstruct with complete context.",
                )
        else:
            # No baseline yet — seed from OBSERVED word count (Issue #759, #810).
            # Template files (~2500 words) are far larger than task-specific
            # prompts (~200-600 words) because templates contain the full agent
            # definition while the coordinator sends focused task context.
            # Template-based seeding (even at 0.70 slack) produced baselines of
            # ~1700 words, causing 25-50% false positive block rate in batch mode.
            # The observed word count is the correct baseline for cross-issue
            # shrinkage detection. seed_baselines_from_templates() is deprecated.
            #
            # Issue #764: Use current issue number instead of hardcoded 0.
            seed_issue = int(current_issue_str) if current_issue_str else 0
            record_prompt_baseline(agent_type, issue_number=seed_issue, word_count=word_count)
            import logging
            _pi_logger = logging.getLogger("unified_pre_tool.prompt_integrity")
            _pi_logger.debug(
                "Seeded baseline from observation: %s issue #%d = %d words",
                agent_type, seed_issue, word_count,
            )
            # Also record as batch observation for cumulative drift tracking (Issue #794)
            try:
                from prompt_integrity import record_batch_observation as _record_obs
                _record_obs(agent_type, seed_issue, word_count)
            except Exception:
                pass  # fail-open

    except Exception:
        # Fail open: any error in baseline check must not block the agent
        pass

    # Cumulative drift check (Issue #794) — wrapped in try/except (fail-open)
    try:
        from prompt_integrity import (
            record_batch_observation,
            get_cumulative_shrinkage,
            MAX_CUMULATIVE_SHRINKAGE,
        )
        issue_for_obs = _get_current_issue_number()
        record_batch_observation(agent_type, issue_for_obs, word_count)
        cumulative = get_cumulative_shrinkage(agent_type)
        if cumulative is not None and cumulative >= MAX_CUMULATIVE_SHRINKAGE * 100:
            return (
                "deny",
                f"BLOCKED: Cumulative prompt drift for '{agent_type}' is {cumulative:.1f}% "
                f"across this batch (threshold: {MAX_CUMULATIVE_SHRINKAGE:.0%}). "
                f"Individual issues pass but the overall trend shows progressive compression. "
                f"REQUIRED NEXT ACTION: Use get_agent_prompt_template('{agent_type}') "
                f"to reload the full agent prompt from disk and reconstruct with complete context.",
            )
    except Exception:
        pass  # fail-open — cumulative tracking failure must not block agents

    return ("allow", f"Prompt integrity OK: {agent_type} has {word_count} words (>= {MIN_CRITICAL_AGENT_PROMPT_WORDS})")


def validate_pipeline_ordering(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Layer 4: Pipeline ordering gate — enforce agent invocation order.

    Checks that Agent tool calls during an active pipeline respect the
    SEQUENTIAL_REQUIRED ordering from pipeline_intent_validator.py.
    Fail-open: any error in the check defaults to allow.

    Issues: #625, #629, #632

    Args:
        tool_name: Name of the tool being called.
        tool_input: Tool input parameters.

    Returns:
        Tuple of (decision, reason).
    """
    try:
        # Env var kill switch
        if os.getenv("PRE_TOOL_PIPELINE_ORDERING", "true").lower() != "true":
            return ("allow", "Pipeline ordering disabled via env var")

        # Only check Agent/Task tool calls
        if tool_name not in AGENT_TOOL_NAMES:
            return ("allow", f"Tool '{tool_name}' is not an agent invocation")

        # Only check during active pipeline
        if not _is_pipeline_active():
            return ("allow", "No active pipeline - ordering check skipped")

        # Extract agent type — prefer explicit subagent_type over text extraction
        # (text extraction can match wrong agent when prompt contains other agent names)
        target_agent = tool_input.get("subagent_type", "").strip().lower()
        if not target_agent:
            task_desc = tool_input.get("task_description", "") or tool_input.get("prompt", "")
            target_agent = _extract_subagent_type(task_desc)
        if not target_agent:
            return ("allow", "Could not determine target agent - allowing")

        # Import completion state and ordering gate
        from pipeline_completion_state import (
            get_completed_agents,
            get_launched_agents,
            get_validation_mode,
            record_agent_launch,
        )
        from agent_ordering_gate import check_ordering_prerequisites

        session_id = _session_id or os.getenv("CLAUDE_SESSION_ID", "unknown")
        issue_number = _get_current_issue_number()

        # Issue #686: Record agent launch BEFORE checking prerequisites.
        # This tracks that PreToolUse fired for this agent, enabling the
        # parallel-mode defense-in-depth guard to distinguish "running
        # concurrently" from "skipped entirely".
        record_agent_launch(session_id, target_agent, issue_number=issue_number)

        completed = get_completed_agents(session_id, issue_number=issue_number)
        launched = get_launched_agents(session_id, issue_number=issue_number)
        mode = get_validation_mode(session_id)

        # SKIP_PYTEST_GATE escape hatch (Issue #838)
        skip_pytest = os.environ.get("SKIP_PYTEST_GATE", "").strip().lower()
        if skip_pytest in ("1", "true", "yes"):
            completed.add("pytest-gate")

        # Issue #697: Read pipeline_mode from state file to filter prerequisites.
        # In --fix mode, planner is not part of the pipeline, so the
        # planner->implementer prerequisite must be skipped.
        pipeline_mode = _get_pipeline_mode_from_state()

        gate = check_ordering_prerequisites(
            target_agent,
            completed,
            validation_mode=mode,
            launched_agents=launched,
            pipeline_mode=pipeline_mode,
        )
        if not gate.passed:
            return ("deny", gate.reason)

        # Issue #669: Log parallel mode warnings for observability
        if gate.warning:
            import logging

            logger = logging.getLogger("unified_pre_tool.ordering")
            logger.warning("%s", gate.warning)

        return ("allow", f"Ordering OK: {target_agent} prerequisites met")

    except Exception as e:
        # Fail-open: ordering check errors must not block workflow.
        # Issue #669: Log a warning when failing open for security-critical ordering pairs,
        # since a crash in the ordering check could silently allow security-auditor
        # before reviewer completes.
        import logging

        logger = logging.getLogger("unified_pre_tool.ordering")
        logger.warning(
            "Pipeline ordering check failed open for tool='%s': %s. "
            "If this involves security-auditor, the ordering guarantee is NOT enforced. "
            "Issue #669.",
            tool_name,
            e,
        )
        return ("allow", f"Pipeline ordering check error (fail-open): {e}")


def _extract_subagent_type(task_description: str) -> str:
    """Extract agent type name from a task description string.

    Looks for patterns like:
    - "Run the implementer agent"
    - "researcher-local"
    - "You are the security-auditor"

    Args:
        task_description: The task description or prompt text.

    Returns:
        Lowercase agent type, or empty string if not found.
    """
    import re

    text = task_description.lower()

    # Known agent types to look for
    known_agents = [
        "researcher-local", "researcher", "planner", "test-master",
        "implementer", "reviewer", "security-auditor", "doc-master",
        "continuous-improvement-analyst",
    ]

    # Check for exact agent name mentions (longest first to match "researcher-local" before "researcher")
    for agent in sorted(known_agents, key=len, reverse=True):
        if agent in text:
            return agent

    return ""


def validate_mcp_security(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate MCP security (path traversal, injection, SSRF).

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Native Claude Code tools skip MCP security (not MCP tools)
    if tool_name in NATIVE_TOOLS:
        return ("allow", f"Native tool '{tool_name}' - MCP security not applicable")

    # Check if MCP security is enabled
    enabled = os.getenv("PRE_TOOL_MCP_SECURITY", "true").lower() == "true"
    if not enabled:
        return ("allow", "MCP security disabled")

    try:
        # Try to import MCP security validator
        try:
            from mcp_security_validator import validate_mcp_operation

            # Validate the operation
            is_safe, reason = validate_mcp_operation(tool_name, tool_input)

            if not is_safe:
                # Security risk detected
                return ("deny", f"MCP Security: {reason}")
            else:
                return ("allow", f"MCP Security: {reason}")

        except ImportError:
            # MCP security validator not available — default to allow.
            # Previously this fell through to auto_approval_engine which used
            # an allow-list (auto_approve_policy.json). That caused recurring
            # "Not whitelisted" regressions every time Claude Code added new
            # tools. Default-allow with deny-only-on-security is simpler and
            # eliminates that entire class of regressions (Issue #401).
            return ("allow", "MCP security validator unavailable — default allow")

    except Exception as e:
        # Error in validation — default to allow (Issue #401).
        # Security validator errors should not block the user.
        return ("allow", f"MCP security error — default allow: {e}")


def _is_exempt_path(file_path: str) -> bool:
    """Check if file is exempt from workflow enforcement (tests, docs, configs)."""
    if not file_path:
        return False
    path = Path(file_path)
    path_str = str(path).lower()
    # Test files
    if ('test_' in path_str or '_test.' in path_str or '.test.' in path_str
            or path_str.startswith('tests/') or path_str.startswith('test/')):
        return True
    # Docs, configs, hooks, scripts, lib, agents, commands
    if path.suffix.lower() in {'.md', '.txt', '.rst', '.json', '.yaml', '.yml', '.toml', '.env', '.ini', '.cfg'}:
        return True
    if any(s in path_str for s in ['.claude/hooks/', 'hooks/', '/lib/', 'lib/', '.claude/agents/',
                                    '.claude/commands/', '.claude/skills/', 'scripts/']):
        return True
    return False


def _is_autonomous_dev_repo(file_path: str) -> bool:
    """Check if file is inside a repo where autonomous-dev is installed.

    Walks up from file_path looking for .claude/commands/implement.md,
    which only exists in repos with the autonomous-dev plugin installed.

    Args:
        file_path: Absolute path to check

    Returns:
        True if file is inside an autonomous-dev-managed repo
    """
    try:
        current = Path(file_path).resolve().parent
    except (OSError, ValueError):
        return False
    # Walk up at most 10 levels to find repo root
    for _ in range(10):
        marker = current / ".claude" / "commands" / "implement.md"
        if marker.exists():
            return True
        parent = current.parent
        if parent == current:
            break
        current = parent
    return False


def _is_protected_infrastructure(file_path: str) -> bool:
    """Check if file is a protected infrastructure file (agents, commands, hooks, lib, skills).

    Protected files require the /implement pipeline for edits.
    Only applies to repos where autonomous-dev is installed — other repos are unaffected.

    Args:
        file_path: Path to the file being edited

    Returns:
        True if the file is in a protected directory with matching extension
    """
    if not file_path:
        return False
    # Resolve symlinks and normalize to absolute path for security (A01)
    try:
        resolved = str(Path(file_path).resolve())
    except (OSError, ValueError):
        resolved = file_path
    # Only protect infrastructure in autonomous-dev repos (not all repos globally)
    if not _is_autonomous_dev_repo(resolved):
        return False
    # Normalize separators to forward slashes for consistent matching
    normalized = resolved.replace("\\", "/")
    # Extensions directory is user-owned — never protected
    if "/extensions/" in normalized:
        return False
    # Test files are never protected — even if they live under hooks/ or lib/
    if "/tests/" in normalized or "/test/" in normalized:
        return False
    path_basename = Path(file_path).name
    if path_basename.startswith("test_") or path_basename.endswith("_test.py"):
        return False
    # Ensure leading slash or check for bare directory name at start
    for segment, extensions in PROTECTED_INFRA_SEGMENTS.items():
        # segment is like '/agents/' — check both embedded and path-start forms
        bare = segment.lstrip("/")  # 'agents/'
        if segment in normalized or normalized.startswith(bare):
            ext = Path(file_path).suffix.lower()
            if ext in extensions:
                return True
    return False


def _get_active_agent_name() -> str:
    """Get the active agent name from available sources (Issue #591).

    Priority order:
    1. agent_type from hook stdin JSON (available inside subagents)
    2. CLAUDE_AGENT_NAME env var (set by Claude Code in some contexts)

    Returns:
        Lowercase agent name, or empty string if not in an agent context.
    """
    if _agent_type:
        return _agent_type.strip().lower()
    env_name = os.getenv("CLAUDE_AGENT_NAME", "").strip().lower()
    return env_name


def _is_stale_session(state: dict, state_path: "Path") -> bool:
    """Check if pipeline state belongs to a different (stale) session (Issue #592).

    Compares session_id in state file against current session's _session_id.
    If different and both are non-empty/non-unknown, state is stale -- remove file.

    Args:
        state: Parsed pipeline state dict.
        state_path: Path to the state file (for removal).

    Returns:
        True if state is stale (file removed), False if current or indeterminate.

    Note: When either session_id is "unknown" or empty (e.g., first hook
    invocation before stdin parsing), this returns False (indeterminate).
    This is an accepted gap — callers fall back to safe defaults (0 for
    issue_number, "full" for mode), and the 30-min mtime TTL in
    _is_pipeline_active() provides a secondary staleness guard.
    """
    stored_sid = state.get("session_id", "")
    current_sid = os.getenv("CLAUDE_SESSION_ID") or _session_id

    if not stored_sid or stored_sid == "unknown" or not current_sid or current_sid == "unknown":
        return False  # Cannot determine, fall through to TTL/HMAC

    if stored_sid != current_sid:
        try:
            state_path.unlink(missing_ok=True)
        except OSError:
            pass
        return True

    return False


def _is_issue_command_active() -> bool:
    """Check if an issue-creating command is currently active (Issue #630).

    Reads the command context JSON file written by /create-issue, /plan-to-issues,
    /improve, /refactor, and /retrospective before they create issues.

    Fail-closed: returns False on any error (missing file, bad JSON, stale timestamp,
    unknown command).

    Returns:
        True if a recognized issue command wrote the context file within the last hour.
    """
    try:
        import json as _json
        import time as _time

        context_path = Path(GH_ISSUE_COMMAND_CONTEXT_PATH)
        if not context_path.exists():
            return False

        with open(context_path) as f:
            data = _json.load(f)

        command = data.get("command")
        if command not in GH_ISSUE_COMMANDS:
            return False

        # Use file modification time for age check (harder to spoof than JSON timestamp)
        age = _time.time() - context_path.stat().st_mtime
        if age > 3600:
            return False

        return True
    except Exception:
        return False  # Fail-closed on any error


def _get_current_issue_number() -> int:
    """Get the current pipeline issue number with file-based fallback.

    Issue #779: Env vars set via ``export`` in one Bash tool call do NOT
    persist to subsequent Bash calls because each invocation gets a fresh
    shell.  The hook process inherits env from the Claude Code parent
    process, not from a previous Bash session.

    Resolution order:
        1. ``PIPELINE_ISSUE_NUMBER`` env var (set by Claude Code process)
        2. ``issue_number`` field in the pipeline state file
           (``/tmp/implement_pipeline_state.json``, written by coordinator)
        3. Issue number extracted from ``run_id`` field in the pipeline state
           file (Issue #869: batch mode run_ids follow pattern
           ``issue-{N}-YYYYMMDD-HHMMSS``)
        4. ``0`` as a safe default (no issue context)

    Returns:
        The current issue number, or 0 if unavailable.
    """
    # 1. Env var takes precedence when available
    env_val = os.getenv("PIPELINE_ISSUE_NUMBER")
    if env_val and env_val != "0":
        try:
            return int(env_val)
        except (ValueError, TypeError):
            pass

    # 2. Fall back to pipeline state file
    pipeline_state_file = os.getenv(
        "PIPELINE_STATE_FILE", "/tmp/implement_pipeline_state.json"
    )
    try:
        state_path = Path(pipeline_state_file)
        if state_path.exists():
            import json as _json

            with open(state_path) as f:
                state = _json.load(f)
            # Session staleness check (Issue #862)
            if _is_stale_session(state, state_path):
                return 0  # Stale session — safe default
            issue_num = state.get("issue_number", 0)
            if isinstance(issue_num, int) and issue_num > 0:
                return issue_num
            # Also handle string values
            if isinstance(issue_num, str) and issue_num.isdigit():
                return int(issue_num)

            # Issue #869: Fallback — extract issue number from run_id field.
            # Batch mode run_ids follow pattern: issue-{N}-YYYYMMDD-HHMMSS
            run_id = state.get("run_id", "")
            if isinstance(run_id, str) and run_id.startswith("issue-"):
                import re as _re

                match = _re.match(r"issue-(\d+)-", run_id)
                if match:
                    return int(match.group(1))
    except Exception:
        pass  # Fail open — return 0

    # 3. Default
    return 0


def _get_pipeline_mode_from_state() -> str:
    """Read pipeline mode from the state file.

    Returns the mode field from the pipeline state file (e.g., "full", "fix", "light").
    Falls back to "full" if the state file is missing, unreadable, or lacks a mode field.

    Issue #697: Needed to filter ordering prerequisites by pipeline mode.
    In --fix mode, planner is not part of the pipeline.

    Returns:
        Pipeline mode string, defaulting to "full".
    """
    pipeline_state_file = os.getenv("PIPELINE_STATE_FILE", "/tmp/implement_pipeline_state.json")
    try:
        state_path = Path(pipeline_state_file)
        if state_path.exists():
            import json as _json

            with open(state_path) as f:
                state = _json.load(f)
            # Session staleness check (Issue #862)
            if _is_stale_session(state, state_path):
                return "full"  # Stale session — safe default
            return state.get("mode", "full")
    except Exception:
        pass
    return "full"


def _is_pipeline_active() -> bool:
    """Check if the /implement pipeline is currently active.

    Checks two sources:
    1. CLAUDE_AGENT_NAME env var against known pipeline agents (touches state file mtime)
    2. Pipeline state file (valid if mtime < 30 min old; Issue #636)

    Returns:
        True if pipeline is active
    """
    # Check agent name (Issue #591: prefer stdin agent_type over env var)
    agent_name = _get_active_agent_name()
    if agent_name in PIPELINE_AGENTS:
        # Touch state file to keep mtime current during active pipeline (Issue #636)
        pipeline_state_file = os.getenv("PIPELINE_STATE_FILE", "/tmp/implement_pipeline_state.json")
        try:
            Path(pipeline_state_file).touch()
        except OSError:
            pass
        return True

    # Check pipeline state file
    pipeline_state_file = os.getenv("PIPELINE_STATE_FILE", "/tmp/implement_pipeline_state.json")
    try:
        state_path = Path(pipeline_state_file)
        if state_path.exists():
            import json as _json
            from datetime import datetime as _datetime
            with open(state_path) as f:
                state = _json.load(f)

            # Session staleness check (Issue #592)
            if _is_stale_session(state, state_path):
                return False

            # HMAC integrity check (Issue #557)
            if state.get("hmac") is not None:
                try:
                    from pipeline_state import verify_state_hmac
                    sid = os.getenv("CLAUDE_SESSION_ID") or _session_id
                    if not verify_state_hmac(state, sid):
                        _log_deviation("pipeline_state", "hmac_check", "pipeline_state_hmac_invalid")
                        return False  # Fail closed: tampered state = not active
                except ImportError:
                    return False  # Fail closed: HMAC present but verify library unavailable

            # Use file mtime for staleness (Issue #636).
            # Pipeline agents touch this file on each hook call (see above),
            # keeping mtime fresh during legitimate runs. A failed/abandoned
            # pipeline stops invoking agents, so mtime stalls and expires.
            # 30 min TTL covers long implementer runs with margin.
            import time as _time
            mtime = state_path.stat().st_mtime
            age_seconds = _time.time() - mtime
            if age_seconds < 1800:  # 30 minutes since last agent activity
                return True
    except Exception:
        pass

    return False


def _is_explicit_implement_active() -> bool:
    """Check if /implement was explicitly invoked by the user (Issue #528).

    Reads the pipeline state file and checks for the 'explicitly_invoked' flag.
    This distinguishes user-invoked /implement from other pipeline activity,
    enabling hard blocking of coordinator code writes during explicit sessions.

    Returns:
        True if /implement was explicitly invoked and session is within TTL
    """
    pipeline_state_file = os.getenv(
        "PIPELINE_STATE_FILE", "/tmp/implement_pipeline_state.json"
    )
    try:
        state_path = Path(pipeline_state_file)
        if not state_path.exists():
            return False
        import json as _json
        from datetime import datetime as _datetime

        with open(state_path) as f:
            state = _json.load(f)

        # Session staleness check (Issue #592)
        if _is_stale_session(state, state_path):
            return False

        # HMAC integrity check (Issue #557)
        if state.get("hmac") is not None:
            try:
                from pipeline_state import verify_state_hmac
                sid = os.getenv("CLAUDE_SESSION_ID") or _session_id
                if not verify_state_hmac(state, sid):
                    _log_deviation("pipeline_state", "hmac_check", "explicit_implement_hmac_invalid")
                    return False  # Fail closed: tampered state = not active
            except ImportError:
                return False  # Fail closed: HMAC present but verify library unavailable

        # Must have explicitly_invoked flag set to true
        if not state.get("explicitly_invoked", False):
            return False
        # Check session TTL (2 hours)
        session_start = state.get("session_start", "")
        if not session_start:
            return False
        start_time = _datetime.fromisoformat(session_start)
        elapsed = (_datetime.now() - start_time).total_seconds()
        if elapsed >= 7200:  # 2 hours TTL
            return False
        return True
    except (json.JSONDecodeError, ValueError, KeyError, OSError, TypeError):
        return False


def _has_alignment_passed() -> bool:
    """Check if STEP 2 alignment has passed in the pipeline state (Issue #585).

    Reads the pipeline state file and verifies that alignment_passed is True.
    HMAC integrity is verified to prevent tampering. On any error (file missing,
    JSON invalid, HMAC fails), returns False (fail closed).

    Returns:
        True if alignment has passed and HMAC is valid
    """
    pipeline_state_file = os.getenv(
        "PIPELINE_STATE_FILE", "/tmp/implement_pipeline_state.json"
    )
    try:
        state_path = Path(pipeline_state_file)
        if not state_path.exists():
            return False
        import json as _json

        with open(state_path) as f:
            state = _json.load(f)

        # Session staleness check (Issue #592)
        if _is_stale_session(state, state_path):
            return False

        # HMAC integrity check — fail closed on any verification failure
        if state.get("hmac") is not None:
            try:
                from pipeline_state import verify_state_hmac
                sid = os.getenv("CLAUDE_SESSION_ID") or _session_id
                if not verify_state_hmac(state, sid):
                    _log_deviation(
                        "pipeline_state", "hmac_check", "alignment_gate_hmac_invalid"
                    )
                    return False
            except ImportError:
                return False  # Fail closed: HMAC present but verify library unavailable

        return state.get("alignment_passed", False) is True
    except (Exception,):
        return False  # Fail closed on any error


# Non-code file extensions exempt from explicit /implement coordinator blocking
_NON_CODE_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".md", ".txt", ".rst", ".csv", ".env",
}


def _is_code_file_target(tool_name: str, tool_input: Dict) -> bool:
    """Check if the tool operation targets a code file (Issue #528).

    Protected infrastructure files (agents/*.md, commands/*.md, skills/*.md)
    are treated as code targets regardless of their .md extension (Issue #623).
    The extension-based exemption only applies to regular docs and config files.

    Args:
        tool_name: Name of the tool (Write, Edit, Bash)
        tool_input: Tool input parameters

    Returns:
        True if the tool targets a code file or protected infrastructure file
    """
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return False
        # Issue #623: Protected infrastructure files (agents/*.md, commands/*.md,
        # skills/*.md) must be treated as code targets regardless of extension.
        if _is_protected_infrastructure(file_path):
            return True
        suffix = Path(file_path).suffix.lower()
        # Exempt non-code files (README.md, docs/*.md, config files, etc.)
        if suffix in _NON_CODE_EXTENSIONS:
            return False
        # Check against known code extensions
        return suffix in CODE_EXTENSIONS
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if not command:
            return False
        target_files = _extract_bash_file_writes(command)
        for fp in target_files:
            # Issue #623: Infrastructure .md files in Bash redirects are code targets
            if _is_protected_infrastructure(fp):
                return True
            suffix = Path(fp).suffix.lower()
            if suffix in _NON_CODE_EXTENSIONS:
                continue
            if suffix in CODE_EXTENSIONS:
                return True
        return False
    return False


def _has_significant_additions(old_string: str, new_string: str, file_path: str = "") -> tuple:
    """Check if the edit adds significant code (new functions, classes, >5 lines)."""
    import re
    old_string = old_string or ""
    new_string = new_string or ""

    file_ext = Path(file_path).suffix.lower() if file_path else ""

    # Collect applicable patterns
    applicable_patterns = []
    for group_name, group_data in PATTERN_GROUPS.items():
        extensions = group_data['extensions']
        if extensions is None:  # universal
            applicable_patterns.extend(group_data['patterns'])
        elif not file_ext:  # no file path = backward compat, use all
            applicable_patterns.extend(group_data['patterns'])
        elif file_ext in extensions:
            applicable_patterns.extend(group_data['patterns'])

    for pattern, desc in applicable_patterns:
        old_matches = len(re.findall(pattern, old_string, re.MULTILINE))
        new_matches = len(re.findall(pattern, new_string, re.MULTILINE))
        if new_matches > old_matches:
            match = re.search(pattern, new_string)
            if match:
                return True, f"New {desc} detected", match.group(0)[:60]

    old_lines = len(old_string.strip().split('\n')) if old_string.strip() else 0
    new_lines = len(new_string.strip().split('\n')) if new_string.strip() else 0
    added = max(0, new_lines - old_lines)
    if added >= SIGNIFICANT_LINE_THRESHOLD:
        return True, "Significant code change detected", f"+{added} lines"
    return False, "", ""


def _strip_quoted_segments(command: str) -> str:
    """Remove single- and double-quoted segments from a command string (Issue #590).

    This prevents false-positive env-var spoofing detection when a protected
    variable name appears inside a quoted argument (e.g., a --body flag to gh).

    Single-quoted strings in bash have no escape sequences, so the pattern is
    simple: everything between the first ``'`` and the next ``'``.

    Double-quoted strings support backslash escaping, so ``\\"`` inside a
    double-quoted segment does NOT end the string.

    On any regex error the original command is returned unchanged (fail-open for
    the stripping step, but the caller still applies the detection patterns to
    the original on error).

    Args:
        command: The raw Bash command string.

    Returns:
        Command with quoted segments replaced by empty strings.
    """
    import re

    try:
        # Remove single-quoted segments first (no escape sequences in single quotes)
        result = re.sub(r"'[^']*'", "", command)
        # Remove double-quoted segments (backslash can escape a quote inside)
        result = re.sub(r'"(?:[^"\\]|\\.)*"', "", result)
        return result
    except re.error:
        return command


def _strip_heredoc_content(command: str) -> str:
    """Remove heredoc content from a command string.

    Strips content between heredoc delimiters (<<EOF...EOF, <<'EOF'...EOF,
    <<"EOF"...EOF) to prevent false-positive detection when keywords appear
    inside heredoc bodies (e.g., commit messages passed via heredoc).

    Args:
        command: The raw Bash command string.

    Returns:
        Command with heredoc body content replaced by empty strings.
    """
    import re

    try:
        # Match heredoc start: <<EOF, <<'EOF', <<"EOF", <<-EOF, <<-'EOF', etc.
        # Capture the delimiter word, then remove everything up to the matching
        # delimiter on its own line (or end of string).
        result = re.sub(
            r"<<-?\s*['\"]?(\w+)['\"]?.*?\n(.*?\n)*?\1\b",
            "",
            command,
            flags=re.DOTALL,
        )
        return result
    except re.error:
        return command


def _is_protected_env_var(var_name: str) -> bool:
    """Check if a variable name is protected by individual listing or prefix matching.

    Args:
        var_name: The environment variable name to check.

    Returns:
        True if the variable is protected and should not be set inline.
    """
    # Check individual protected vars first
    if var_name in PROTECTED_ENV_VARS:
        return True

    # Check prefix-based protection (Issue #606)
    if var_name in PROTECTED_ENV_PREFIX_EXCEPTIONS:
        return False
    for prefix in PROTECTED_ENV_PREFIXES:
        if var_name.startswith(prefix):
            return True

    return False


def _detect_env_spoofing(command: str) -> "Optional[str]":
    """Detect inline environment variable spoofing in Bash commands (Issue #557, #606).

    Checks for patterns like:
    - CLAUDE_AGENT_NAME=implementer python3 ...
    - export CLAUDE_AGENT_NAME=implementer
    - env CLAUDE_AGENT_NAME=implementer ...
    - CLAUDE_ANY_NEW_VAR=value cmd (prefix-based, Issue #606)

    Checks variables in PROTECTED_ENV_VARS (individual) and any variable
    matching PROTECTED_ENV_PREFIXES. Legitimate env usage
    (e.g., PATH=foo, HOME=/tmp) is not blocked.

    Args:
        command: The Bash command string to inspect.

    Returns:
        Block reason string if spoofing detected, None if clean.
    """
    import re

    stripped = _strip_quoted_segments(command)

    # --- Pass 1: Check individual PROTECTED_ENV_VARS (exact match) ---
    for var in PROTECTED_ENV_VARS:
        # Pattern 1: VAR=value command (inline prefix)
        pattern1 = (
            r'(?:^|[;&|]\s*)' + re.escape(var)
            + r"""=['""]?[^\s'"";|&]*['""]?\s+\S"""
        )
        if re.search(pattern1, stripped):
            return (
                f"BLOCKED: Inline env var spoofing detected — '{var}' cannot be "
                f"set inline in Bash commands. Protected environment variables "
                f"are managed by the pipeline. (Issue #557) "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

        # Pattern 2: export VAR=value
        pattern2 = r'\bexport\s+' + re.escape(var) + r'\s*='
        if re.search(pattern2, stripped):
            return (
                f"BLOCKED: Export of protected env var '{var}' detected. "
                f"Protected environment variables cannot be overridden via "
                f"Bash export. (Issue #557) "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

        # Pattern 3: env [-flags] [--] VAR=value command
        pattern3 = r'\benv\s+(?:(?:-[a-zA-Z]+\s+(?:\S+\s+)?|--\s+)*)(?:[^\s=]+=\S+\s+)*' + re.escape(var) + r'\s*='
        if re.search(pattern3, stripped):
            return (
                f"BLOCKED: Env command spoofing detected — '{var}' cannot be "
                f"set via the env command. Protected environment variables "
                f"are managed by the pipeline. (Issue #557) "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

    # --- Pass 2: Prefix-based detection (Issue #606) ---
    # Find all VAR=value assignments in the stripped command
    # Pattern: word characters (var name) followed by = at assignment positions
    # Inline: VAR=value cmd  (start of command or after ; & |)
    inline_vars = re.findall(r'(?:^|[;&|]\s*)([A-Z_][A-Z0-9_]*)=', stripped, re.MULTILINE)
    # Export: export VAR=value
    export_vars = re.findall(r'\bexport\s+([A-Z_][A-Z0-9_]*)\s*=', stripped, re.MULTILINE)
    # Env command: env [-flags...] [--] VAR=value
    # Handles: env VAR=val, env -i VAR=val, env -u NAME VAR=val, env -- VAR=val
    env_cmd_vars = re.findall(
        r'\benv\s+(?:(?:-[a-zA-Z]+\s+(?:\S+\s+)?|--\s+)*)(?:[^\s=]+=\S+\s+)*([A-Z_][A-Z0-9_]*)=',
        stripped,
        re.MULTILINE,
    )

    all_assigned_vars = set(inline_vars + export_vars + env_cmd_vars)
    for var in all_assigned_vars:
        # Skip vars already checked in Pass 1
        if var in PROTECTED_ENV_VARS:
            continue
        if _is_protected_env_var(var):
            # Determine which pattern matched to give a specific message
            inline_pat = (
                r'(?:^|[;&|]\s*)' + re.escape(var)
                + r"""=['""]?[^\s'"";|&]*['""]?\s+\S"""
            )
            export_pat = r'\bexport\s+' + re.escape(var) + r'\s*='
            env_pat = r'\benv\s+(?:(?:-[a-zA-Z]+\s+(?:\S+\s+)?|--\s+)*)(?:[^\s=]+=\S+\s+)*' + re.escape(var) + r'\s*='

            if re.search(export_pat, stripped):
                return (
                    f"BLOCKED: Export of protected env var '{var}' detected. "
                    f"Variables matching protected prefix cannot be overridden "
                    f"via Bash export. (Issue #606) "
                    f"REQUIRED NEXT ACTION: Remove the environment variable override "
                    f"from your command. Do NOT attempt to set protected variables "
                    f"via alternative methods."
                )
            if re.search(env_pat, stripped):
                return (
                    f"BLOCKED: Env command spoofing detected — '{var}' cannot be "
                    f"set via the env command. Variables matching protected prefix "
                    f"are managed by the pipeline. (Issue #606) "
                    f"REQUIRED NEXT ACTION: Remove the environment variable override "
                    f"from your command. Do NOT attempt to set protected variables "
                    f"via alternative methods."
                )
            if re.search(inline_pat, stripped):
                return (
                    f"BLOCKED: Inline env var spoofing detected — '{var}' cannot be "
                    f"set inline in Bash commands. Variables matching protected prefix "
                    f"are managed by the pipeline. (Issue #606) "
                    f"REQUIRED NEXT ACTION: Remove the environment variable override "
                    f"from your command. Do NOT attempt to set protected variables "
                    f"via alternative methods."
                )
            # Fallback: var was found in assignment but specific pattern didn't re-match
            # (shouldn't happen, but fail safe)
            return (
                f"BLOCKED: Protected env var '{var}' assignment detected. "
                f"Variables matching protected prefix cannot be set in "
                f"Bash commands. (Issue #606) "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

    # Pattern 4: bash -c / sh -c subshell containing protected var assignments
    # Catches: bash -c 'CLAUDE_AGENT_NAME=x python3 ...'
    #          sh -c "export PIPELINE_STATE_FILE=/tmp/fake.json; ..."
    for subshell_match in re.finditer(r'(?:ba)?sh\s+-c\s+([\x27"])(.*?)\1', command, re.DOTALL):
        inner_cmd = subshell_match.group(2)
        # Recursively check the inner command for env spoofing
        inner_result = _detect_env_spoofing(inner_cmd)
        if inner_result:
            return (
                f"BLOCKED: Subshell env spoofing detected — protected environment "
                f"variable assignment found inside bash -c / sh -c subshell. "
                f"Inner violation: {inner_result} "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

    return None


def _track_spoofing_escalation(
    session_id: str,
    *,
    tracker_path: "Optional[str]" = None,
) -> bool:
    """Track spoofing attempts per session and detect escalation (Issue #606).

    Uses a file-based tracker to persist attempt counts across hook invocations
    (each hook invocation is a separate process). Returns True when 2+ attempts
    have occurred in the same session, indicating escalation.

    Args:
        session_id: The current session identifier.
        tracker_path: Optional override for the tracker file path (for testing).

    Returns:
        True if this is the 2nd or later attempt in the same session (escalation).
    """
    import json
    import tempfile
    from datetime import datetime

    if tracker_path is None:
        log_dir = Path(os.environ.get("HOME", "/tmp")) / ".claude" / "logs"
        tracker_file = log_dir / "spoofing_attempts.json"
    else:
        tracker_file = Path(tracker_path)

    try:
        tracker_file.parent.mkdir(parents=True, exist_ok=True)

        # Read existing tracker data
        data: "dict[str, list[str]]" = {}
        if tracker_file.exists():
            try:
                data = json.loads(tracker_file.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}

        # Record this attempt
        if session_id not in data:
            data[session_id] = []
        data[session_id].append(datetime.now().isoformat())

        is_escalation = len(data[session_id]) >= 2

        # Atomic write: write to tmp file, then rename
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(tracker_file.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, str(tracker_file))
        except OSError:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            # Still return the escalation result based on in-memory data
            pass

        return is_escalation
    except Exception:
        # Never block on tracker failure — fail open for tracking,
        # the spoofing block itself is already applied
        return False


def _contains_gh_issue_create_bypass(command: str) -> bool:
    """Detect subprocess-wrapped 'gh issue create' bypass patterns (Issue #618).

    Checks the RAW (unstripped) command string for patterns where 'gh issue create'
    is invoked indirectly via subprocess wrappers, shell wrappers, or backtick
    substitution. These bypasses escape the normal stripped-string detection
    because the 'gh issue create' text lives inside a quoted string argument.

    Patterns detected:
    - python3 -c "... subprocess.run(['gh', 'issue', 'create'] ...)"
    - python -c "... subprocess.call(['gh', 'issue', 'create'] ...)"
    - python3 -c "... subprocess.Popen(['gh', 'issue', 'create'] ...)"
    - python3 -c "... os.system('gh issue create ...')"
    - sh -c "gh issue create ..."
    - bash -c "gh issue create ..."
    - `gh issue create ...` (backtick substitution)
    - $(gh issue create ...) (command substitution)

    Args:
        command: The raw (unstripped) Bash command string.

    Returns:
        True if a bypass pattern is detected, False otherwise.
    """
    import re

    try:
        # Pattern 1: Python subprocess wrappers — subprocess.run/call/Popen/check_output
        # with 'gh' and 'issue' and 'create' appearing as list elements or in a string.
        # We look for the subprocess family of calls followed by gh issue create nearby.
        subprocess_pattern = (
            r'subprocess\s*\.\s*(?:run|call|Popen|check_output|check_call)'
            r'[^)]*\bgh\b[^)]*\bissue\b[^)]*\bcreate\b'
        )
        if re.search(subprocess_pattern, command, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 2: os.system('gh issue create ...') or os.system("gh issue create ...")
        os_system_pattern = r'os\s*\.\s*system\s*\([^)]*\bgh\s+issue\s+create\b'
        if re.search(os_system_pattern, command, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 3: sh -c "gh issue create ..." or bash -c "gh issue create ..."
        # Also covers: /bin/sh -c, /bin/bash -c, /usr/bin/env sh -c, etc.
        shell_wrapper_pattern = (
            r'(?:^|[|;&\s])(?:/\S+/)?(?:sh|bash|zsh|dash)\s+-c\s+'
            r'["\'](?:[^"\'\\]|\\.)*\bgh\s+issue\s+create\b'
        )
        if re.search(shell_wrapper_pattern, command, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 4: Backtick command substitution: `gh issue create ...`
        # Only matches when gh issue create is the direct command inside backticks
        # (i.e., gh appears right after the opening backtick, with optional whitespace).
        backtick_pattern = r'`\s*gh\s+issue\s+create\b'
        if re.search(backtick_pattern, command, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 5: $(...) command substitution with gh issue create as the direct command
        # e.g. $(gh issue create --title "test")
        # NOT matched: $(cat <<'EOF'\ngh issue create\nEOF\n) — heredoc body, not a command
        dollar_subst_pattern = r'\$\(\s*gh\s+issue\s+create\b'
        if re.search(dollar_subst_pattern, command, re.IGNORECASE | re.DOTALL):
            return True

        return False
    except re.error:
        return False  # Fail-open on regex error


def _detect_gh_issue_marker_creation(command: str) -> "Optional[str]":
    """Detect Bash commands that directly create the gh issue marker file (Issue #627).

    The marker file ``autonomous_dev_gh_issue_allowed.marker`` is written by the
    approved /create-issue pipeline to signal that a ``gh issue create`` call is
    authorized.  Allowing arbitrary code to create the file directly would
    short-circuit the entire bypass-prevention mechanism.

    Uses deny-by-default logic: if the marker name appears in the command and
    the operation is NOT provably read-only/delete, it is blocked.  This
    prevents bypass via novel write methods (e.g. ``python3 -c "json.dump(...)"``,
    ``dd``, ``install``, ``os.open``).

    Read-only and delete operations (``cat``, ``ls``, ``rm``, ``stat``, ``test``,
    ``head``, ``tail``, ``wc``, ``file``, ``readlink``, ``[``) are intentionally
    NOT blocked, nor are commands that merely *mention* the marker name in
    output text (``grep``, ``echo``/``printf`` without redirect to the marker).

    Allow-through conditions (same guards as ``_detect_gh_issue_create``):
    1. ``_is_pipeline_active()`` — the pipeline itself writes the marker legitimately.
    2. Agent name in ``GH_ISSUE_AGENTS`` — authorised agents may also write it.
    3. ``_is_issue_command_active()`` — issue-creating command is active.
    Note: there is deliberately NO marker-file allow-through here (circular).

    Args:
        command: The raw Bash command string to inspect.

    Returns:
        Block reason string if marker creation detected and not allowed,
        None if the command is clean or allowed.
    """
    try:
        marker_anchor = "autonomous_dev_gh_issue_allowed"

        # Fast path: marker name not mentioned at all → nothing to check
        if marker_anchor not in command.lower():
            return None

        # --- Identify the command segment that references the marker ---
        # For piped commands, only inspect the segment containing the marker.
        cmd_lower = command.lower()
        segments = command.split("|")
        relevant_segment = command  # default: whole command
        for seg in segments:
            if marker_anchor in seg.lower():
                relevant_segment = seg.strip()
                break

        seg_lower = relevant_segment.lower()
        seg_stripped = relevant_segment.strip()

        # --- Read-only / delete verbs: first token of the relevant segment ---
        # Extract the first token (the command verb) from the segment.
        # Handle leading env vars (FOO=bar cmd ...) and sudo.
        tokens = seg_stripped.split()
        verb = ""
        for tok in tokens:
            # Skip env-var assignments (VAR=value)
            if "=" in tok and not tok.startswith("-"):
                continue
            # Skip sudo
            if tok == "sudo":
                continue
            verb = tok.lower()
            break

        readonly_verbs = {
            "cat", "ls", "stat", "test", "head", "tail", "wc", "file",
            "rm", "readlink", "[",
        }
        if verb in readonly_verbs:
            return None

        # --- Reference-only mentions (grep, echo/printf without redirect to marker) ---
        if verb == "grep":
            return None

        # echo/printf: allowed UNLESS a redirect targets the marker file
        if verb in ("echo", "printf"):
            # Check if there is a redirect (> or >>) followed by the marker name
            # in the same segment
            import re
            if re.search(
                r">\s*\S*" + re.escape(marker_anchor), seg_lower
            ):
                pass  # Fall through to blocking
            else:
                return None

        # --- Allow-through conditions (unchanged) ---

        # Allow-through 1: Pipeline is active (writes the marker legitimately)
        if _is_pipeline_active():
            return None

        # Allow-through 2: Agent is authorised for issue creation
        agent_name = _get_active_agent_name()
        if agent_name in GH_ISSUE_AGENTS:
            return None

        # Allow-through 3: Issue-creating command is active (Issue #630)
        if _is_issue_command_active():
            return None

        return (
            "BLOCKED: Cannot create gh issue marker file directly.\n"
            "REQUIRED NEXT ACTION: Use /create-issue or /create-issue --quick "
            "to create issues through the approved pipeline. "
            "Do NOT create the marker file directly."
        )
    except Exception:
        return None  # Fail-open on any error


def _detect_gh_issue_create(command: str) -> "Optional[str]":
    """Detect direct 'gh issue create' usage outside approved contexts (Issue #599).

    Blocks direct GitHub issue creation via the gh CLI to enforce the
    /create-issue pipeline which includes research, duplicate detection,
    and proper formatting.

    Also detects subprocess-bypass patterns (Issue #618) where 'gh issue create'
    is wrapped inside python3 -c subprocess calls, sh/bash -c, or backtick
    substitutions to evade the normal stripped-string detection.

    Args:
        command: The raw Bash command string to inspect.

    Returns:
        Block reason string if gh issue create detected and not allowed,
        None if the command is clean or allowed.
    """
    import re

    try:
        # Strip quoted segments and heredoc content to avoid false positives
        # when 'gh issue create' appears inside commit messages, echo strings, etc.
        stripped = _strip_heredoc_content(command)
        stripped = _strip_quoted_segments(stripped)

        # Check 1: Direct 'gh issue create' in the stripped command
        direct_match = bool(re.search(r'\bgh\s+issue\s+create\b', stripped, re.IGNORECASE))

        # Check 2: Subprocess bypass patterns in the RAW command (Issue #618).
        # These wrappers embed 'gh issue create' inside quoted strings, which
        # stripping would normally remove — so we scan the original command.
        bypass_match = _contains_gh_issue_create_bypass(command)

        if not direct_match and not bypass_match:
            return None

        # Allow-through 1: Pipeline is active (implementer/test-master/doc-master)
        if _is_pipeline_active():
            return None

        # Allow-through 2: Agent is authorized for issue creation
        agent_name = _get_active_agent_name()
        if agent_name in GH_ISSUE_AGENTS:
            return None

        # Allow-through 3: Marker file exists and is fresh (< 1 hour)
        try:
            marker_path = Path(GH_ISSUE_MARKER_PATH)
            if marker_path.exists():
                import time
                age = time.time() - marker_path.stat().st_mtime
                if age < 3600:
                    return None
        except OSError:
            pass  # Marker check failed, continue to block

        # Allow-through 4: Issue-creating command is active (Issue #630)
        if _is_issue_command_active():
            return None

        return (
            "BLOCKED: Cannot create GitHub issues with 'gh issue create' directly.\n"
            "REQUIRED NEXT ACTION: Use /create-issue or /create-issue --quick instead.\n\n"
            "/create-issue includes research, duplicate detection, and ensures "
            "proper formatting.\n\n"
            "FORBIDDEN: Do NOT suggest the user run 'gh issue create' manually, "
            "including via '! gh issue create' or any other bypass method. "
            "The '!' prefix runs commands outside the hook system and defeats "
            "enforcement. The ONLY acceptable path is /create-issue."
        )
    except Exception:
        return None  # Fail-open on any error


def _check_batch_cia_completions(session_id: str) -> "Optional[str]":
    """Check if all batch issues have CIA completion.

    Loads verify_batch_cia_completions from pipeline_completion_state and
    returns a block reason string if any issues are missing CIA, or None
    if all passed (or on any error — fail-open).

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Block reason string if CIA missing for any issue, None otherwise.

    Issues: #712
    """
    try:
        hook_dir = Path(__file__).resolve().parent
        lib_candidates = [
            hook_dir.parent / "lib" / "pipeline_completion_state.py",
            hook_dir.parents[2] / "lib" / "pipeline_completion_state.py",
        ]
        mod = None
        for lib_path in lib_candidates:
            if lib_path.exists():
                spec = importlib.util.spec_from_file_location(
                    "pipeline_completion_state", str(lib_path)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                break

        if mod is None or not hasattr(mod, "verify_batch_cia_completions"):
            return None  # Fail-open

        all_passed, with_cia, missing_cia = mod.verify_batch_cia_completions(session_id)
        if all_passed:
            return None

        missing_str = ", ".join(f"#{n}" for n in missing_cia)
        return (
            f"BLOCKED: Batch CIA gate — issues missing continuous-improvement-analyst: "
            f"{missing_str}. All batch issues MUST have CIA completion before git commit. "
            f"REQUIRED NEXT ACTION: Run the continuous-improvement-analyst agent for "
            f"the missing issues before committing. "
            f"Set SKIP_BATCH_CIA_GATE=1 to bypass. (Issue #712)"
        )
    except Exception:
        return None  # Fail-open


def _check_batch_doc_master_completions(session_id: str) -> "Optional[str]":
    """Check if all batch issues have doc-master completion.

    Loads verify_batch_doc_master_completions from pipeline_completion_state and
    returns a block reason string if any issues are missing doc-master, or None
    if all passed (or on any error — fail-open).

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Block reason string if doc-master missing for any issue, None otherwise.

    Issues: #786
    """
    try:
        hook_dir = Path(__file__).resolve().parent
        lib_candidates = [
            hook_dir.parent / "lib" / "pipeline_completion_state.py",
            hook_dir.parents[2] / "lib" / "pipeline_completion_state.py",
        ]
        mod = None
        for lib_path in lib_candidates:
            if lib_path.exists():
                spec = importlib.util.spec_from_file_location(
                    "pipeline_completion_state", str(lib_path)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                break

        if mod is None or not hasattr(mod, "verify_batch_doc_master_completions"):
            return None  # Fail-open

        all_passed, with_doc_master, missing_doc_master = mod.verify_batch_doc_master_completions(session_id)
        if all_passed:
            return None

        # Differentiate "never ran" vs "ran but no valid verdict" (Issue #837).
        # Read the raw state to inspect verdict fields for each missing issue.
        never_ran: list[int] = []
        no_verdict: list[int] = []
        try:
            if hasattr(mod, "_read_state"):
                raw_state = mod._read_state(session_id)
                completions = raw_state.get("completions", {}) if raw_state else {}
                for issue_num in missing_doc_master:
                    issue_data = completions.get(str(issue_num), {})
                    if isinstance(issue_data, dict) and issue_data.get("doc-master"):
                        no_verdict.append(issue_num)
                    else:
                        never_ran.append(issue_num)
            else:
                never_ran = list(missing_doc_master)
        except Exception:
            never_ran = list(missing_doc_master)

        parts: list[str] = []
        if never_ran:
            never_ran_str = ", ".join(f"#{n}" for n in never_ran)
            parts.append(f"doc-master never ran: {never_ran_str}")
        if no_verdict:
            no_verdict_str = ", ".join(f"#{n}" for n in no_verdict)
            parts.append(f"doc-master ran but produced no valid verdict: {no_verdict_str}")

        detail = "; ".join(parts) if parts else ", ".join(f"#{n}" for n in missing_doc_master)
        return (
            f"BLOCKED: Batch doc-master gate — {detail}. "
            f"All batch issues MUST have doc-master completion with a valid verdict before git commit. "
            f"REQUIRED NEXT ACTION: Run the doc-master agent for "
            f"the missing issues before committing. "
            f"Set SKIP_BATCH_DOC_MASTER_GATE=1 to bypass. (Issue #786, #837)"
        )
    except Exception:
        return None  # Fail-open


def _check_pipeline_agent_completions(session_id: str) -> "Optional[str]":
    """Check if all required pipeline agents have completed before git commit.

    Loads verify_pipeline_agent_completions from pipeline_completion_state and
    returns a block reason string if any required agents are missing, or None
    if all passed (or on any error -- fail-open).

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Block reason string if agents missing, None otherwise.

    Issues: #802
    """
    try:
        hook_dir = Path(__file__).resolve().parent
        lib_candidates = [
            hook_dir.parent / "lib" / "pipeline_completion_state.py",
            hook_dir.parents[2] / "lib" / "pipeline_completion_state.py",
        ]
        mod = None
        for lib_path in lib_candidates:
            if lib_path.exists():
                spec = importlib.util.spec_from_file_location(
                    "pipeline_completion_state", str(lib_path)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                break

        if mod is None or not hasattr(mod, "verify_pipeline_agent_completions"):
            return None  # Fail-open

        # Determine pipeline mode from env (set by coordinator)
        pipeline_mode = os.environ.get("PIPELINE_MODE") or _get_pipeline_mode_from_state()
        issue_number = 0
        try:
            issue_number = int(os.environ.get("PIPELINE_ISSUE_NUMBER", "0"))
        except (ValueError, TypeError):
            pass

        passed, completed, missing = mod.verify_pipeline_agent_completions(
            session_id, pipeline_mode, issue_number=issue_number
        )
        if passed:
            return None

        missing_str = ", ".join(sorted(missing))
        completed_str = ", ".join(sorted(completed)) if completed else "(none)"
        return (
            f"BLOCKED: Agent completeness gate -- missing required agents: "
            f"{missing_str}. Completed: {completed_str}. "
            f"All required pipeline agents MUST complete before git commit. "
            f"REQUIRED NEXT ACTION: Run the missing agents before committing. "
            f"Set SKIP_AGENT_COMPLETENESS_GATE=1 to bypass, or run `touch /tmp/skip_agent_completeness_gate` as a SEPARATE command first, then retry the commit (Issue #802)"
        )
    except Exception:
        return None  # Fail-open


def _detect_settings_json_write(command: str) -> "Optional[str]":
    """Detect Bash commands that write to settings.json or settings.local.json.

    Only blocks during active pipeline. Called separately after pipeline check.

    Args:
        command: The Bash command string to inspect.

    Returns:
        Block reason string if settings write detected, None if clean.
    """
    import re

    settings_patterns = [
        r'settings\.json',
        r'settings\.local\.json',
    ]
    # Check redirects, tee, cp/mv targets
    write_targets = _extract_bash_file_writes(command)
    for target in write_targets:
        for pat in settings_patterns:
            if re.search(pat, target):
                return (
                    f"BLOCKED: Bash write to '{target}' during active pipeline. "
                    f"Settings files are protected during /implement sessions. (Issue #557) "
                    f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                    f"then modify settings. Do NOT write settings during an active pipeline."
                )

    # Also check sed -i and python -c patterns
    for pat in settings_patterns:
        if re.search(r'\bsed\s+.*-i.*' + pat, command):
            return (
                f"BLOCKED: In-place edit of settings file during active pipeline. "
                f"Settings files are protected during /implement sessions. (Issue #557) "
                f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                f"then modify settings. Do NOT write settings during an active pipeline."
            )

    # Detect Python -c inline commands that write to settings files (Issue #768)
    # Catches variable-based bypasses like: python3 -c "p='settings.json'; json.dump(d, open(p,'w'))"
    py_c_patterns = [
        r'python3?\s+-c\s+"([^"]+)"',
        r"python3?\s+-c\s+'([^']+)'",
    ]
    for py_c_pat in py_c_patterns:
        for match in re.finditer(py_c_pat, command):
            snippet = match.group(1)
            has_settings_ref = any(
                re.search(pat, snippet) for pat in settings_patterns
            )
            if not has_settings_ref:
                continue
            # Check for Python write patterns in the snippet
            python_write_patterns = [
                r'open\s*\(',         # open() call (could be write mode)
                r'json\.dump\s*\(',   # json.dump()
                r'\.write\s*\(',      # .write()
                r'\.write_text\s*\(', # Path.write_text()
                r'\.write_bytes\s*\(',# Path.write_bytes()
                r'shutil\.',          # shutil operations
                r'os\.rename\s*\(',   # os.rename()
                r'os\.replace\s*\(',  # os.replace()
            ]
            has_write = any(
                re.search(wp, snippet) for wp in python_write_patterns
            )
            if has_write:
                return (
                    f"BLOCKED: Python -c command writes to settings file during active pipeline. "
                    f"Settings files are protected during /implement sessions. (Issue #768) "
                    f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                    f"then modify settings. Do NOT write settings during an active pipeline."
                )

    return None


def _detect_realign_bypass(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """Detect attempts to run raw mlx_lm scripts bypassing realign CLI (Issue #754).

    RULE #1: Never run raw mlx.launch, mlx_lm.lora, or standalone scripts.
    Users must use the realign CLI wrapper instead.

    Only active when the current project contains realign markers.

    Args:
        tool_name: The Claude Code tool being invoked.
        tool_input: The tool input dictionary (command key for Bash).

    Returns:
        Tuple of (decision, reason) where decision is "deny" or "allow".
    """
    # Only inspect Bash tool calls
    if tool_name != "Bash":
        return ("allow", "")

    command = tool_input.get("command", "")
    if not command:
        return ("allow", "")

    # Patterns that indicate direct mlx_lm/mlx.launch execution (not grep/search)
    import re

    # Only match execution patterns, not grep/search/cat/echo references
    # Look for python -m mlx_lm.X or python -m mlx.launch
    bypass_patterns = [
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx_lm\.lora\b",
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx_lm\.fuse\b",
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx_lm\.generate\b",
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx_lm\b",
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx\.launch\b",
    ]

    # Exclude search/inspection commands that reference mlx_lm without executing it
    search_prefixes = (
        "grep ", "rg ", "ag ", "ack ", "find ", "cat ", "less ", "head ",
        "tail ", "echo ", "printf ", "man ", "gh ",
    )
    stripped = command.lstrip()
    if any(stripped.startswith(prefix) for prefix in search_prefixes):
        return ("allow", "")

    for pattern in bypass_patterns:
        if re.search(pattern, command):
            reason = (
                "BLOCKED: Direct use of mlx_lm/mlx.launch is not allowed. "
                "The realign CLI wraps mlx_lm with correct configuration, logging, "
                "and checkpoint management. "
                "REQUIRED NEXT ACTION: Use 'realign train' instead of 'python -m mlx_lm.lora', "
                "or 'realign generate' instead of 'python -m mlx_lm.generate'. "
                "See 'realign --help' for available commands. "
                "Do NOT run raw mlx_lm commands directly. (Issue #754)"
            )
            return ("deny", reason)

    return ("allow", "")


def _extract_bash_file_writes(command: str) -> list:
    """Extract file paths being written to by Bash command."""
    import re
    file_paths = []

    # Redirection (>, >>) — skip stderr redirects (2>, 2>>)
    redirect_pattern = r'(?<![0-9])[>]{1,2}\s+([^\s;&|]+)'
    for match in re.finditer(redirect_pattern, command):
        fp = match.group(1).strip()
        if fp not in {'/dev/null', '/dev/stderr', '/dev/stdout', '&1', '&2'}:
            file_paths.append(fp)

    # tee command
    tee_pattern = r'\btee\s+(?:-a\s+)?([^\s;&|]+)'
    for match in re.finditer(tee_pattern, command):
        file_paths.append(match.group(1).strip())

    # Heredoc redirect (heredoc >> file)
    heredoc_pattern = r'<<\s*[\'"]?\w+[\'"]?\s*[>]{1,2}\s+([^\s;&|]+)'
    for match in re.finditer(heredoc_pattern, command):
        file_paths.append(match.group(1).strip())

    # cat redirect before heredoc: cat > file << 'EOF' (Issue #558)
    cat_heredoc_pattern = r'\bcat\s+[>]{1,2}\s+([^\s;&|]+)\s+<<'
    for match in re.finditer(cat_heredoc_pattern, command):
        fp = match.group(1).strip()
        if fp not in {'/dev/null', '/dev/stderr', '/dev/stdout', '&1', '&2'}:
            file_paths.append(fp)

    # dd of=FILE (Issue #558)
    dd_pattern = r'\bdd\s+.*?\bof=([^\s;&|]+)'
    for match in re.finditer(dd_pattern, command):
        file_paths.append(match.group(1).strip())

    # sed -i (in-place edit) — Issue #589
    sed_pattern = r'\bsed\s+(?:-[^i]*)?-i[^\s]*\s+(?:[\'"][^\'"]*[\'"]\s+)?([^\s;&|]+)'
    for match in re.finditer(sed_pattern, command):
        file_paths.append(match.group(1).strip())

    # cp / mv destination (last argument) — Issue #589
    cp_mv_pattern = r'\b(?:cp|mv)\s+(?:-[^\s]+\s+)*(?:[^\s]+\s+)+([^\s;&|]+)'
    for match in re.finditer(cp_mv_pattern, command):
        file_paths.append(match.group(1).strip())

    # python3 -c with file writes — Issue #589 (enhanced with python_write_detector)
    py_c_patterns = [
        r'python3?\s+-c\s+"([^"]+)"',   # double-quoted
        r"python3?\s+-c\s+'([^']+)'",    # single-quoted
    ]
    py_c_snippets = []
    for py_c_pattern in py_c_patterns:
        for match in re.finditer(py_c_pattern, command):
            py_c_snippets.append(match.group(1))

    # python3 heredoc with file writes — Issue #589
    py_heredoc_pattern = r'python3?\s+.*?<<\s*[\'"]?(\w+)[\'"]?'
    for match in re.finditer(py_heredoc_pattern, command):
        marker = match.group(1)
        heredoc_start = match.end()
        remaining = command[heredoc_start:]
        _end_match = re.search(r'(?:^|\n)' + re.escape(marker) + r'(?:\n|$)', remaining)
        end_idx = _end_match.start() if _end_match else -1
        heredoc_body = remaining[:end_idx] if end_idx >= 0 else remaining
        py_c_snippets.append(heredoc_body)

    # Use python_write_detector if available, else fall back to inline regex
    for snippet in py_c_snippets:
        if _python_write_detector is not None:
            targets = _python_write_detector.extract_write_targets(snippet)
            for t in targets:
                if t != _python_write_detector.SUSPICIOUS_EXEC_SENTINEL:
                    file_paths.append(t)
        else:
            # Inline regex fallback (original patterns)
            open_pattern = r'open\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"][wa]'
            for open_match in re.finditer(open_pattern, snippet):
                file_paths.append(open_match.group(1))
            path_write_pattern = r"Path\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\.write_(?:text|bytes)"
            for path_match in re.finditer(path_write_pattern, snippet):
                file_paths.append(path_match.group(1))
            # shutil fallback — Issue #589
            shutil_pattern = r'(?:\w+)\.(?:copy|copy2|move|copyfile)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)'
            for shutil_match in re.finditer(shutil_pattern, snippet):
                file_paths.append(shutil_match.group(1))
            # os.rename/os.replace fallback — Issue #698 (destination is 2nd arg)
            os_rename_pattern = r'(?:\w+)\.(?:rename|replace)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]'
            for os_rename_match in re.finditer(os_rename_pattern, snippet):
                file_paths.append(os_rename_match.group(1))
            # Path(...).rename/Path(...).replace fallback — Issue #698 (destination is 1st arg)
            path_rename_pattern = r'(?:\w+)\s*\(\s*[\'"][^\'"]+[\'"]\s*\)\.(?:rename|replace)\s*\(\s*[\'"]([^\'"]+)[\'"]'
            for path_rename_match in re.finditer(path_rename_pattern, snippet):
                file_paths.append(path_rename_match.group(1))

    return file_paths


def _log_deviation(file_name: str, tool_name: str, reason: str) -> None:
    """Append deviation to .claude/logs/deviations.jsonl for analytics."""
    try:
        import json as _json
        from datetime import datetime as _dt
        log_dir = Path(os.getcwd()) / ".claude" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": _dt.now().isoformat(),
            "file": file_name,
            "tool": tool_name,
            "reason": reason,
            "session_id": os.getenv("CLAUDE_SESSION_ID") or _session_id,
        }
        with open(log_dir / "deviations.jsonl", "a") as f:
            f.write(_json.dumps(entry) + "\n")
    except Exception:
        pass  # Never fail the hook for logging


def validate_agent_authorization(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate agent authorization for code changes.

    Enforces /implement workflow for significant code changes.
    Enforcement level controlled by ENFORCEMENT_LEVEL env var:
    - off: always allow
    - warn: allow + log warning (default for backward compat)
    - suggest: ask (user-visible prompt) + include /implement suggestion in reason
    - block: deny significant changes outside pipeline

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
    """
    # Check if agent authorization is enabled
    enabled = os.getenv("PRE_TOOL_AGENT_AUTH", "true").lower() == "true"
    if not enabled:
        return ("allow", "Agent authorization disabled")

    # Check if pipeline is active (agent name or state file)
    if _is_pipeline_active():
        agent_name = _get_active_agent_name()
        if agent_name in PIPELINE_AGENTS:
            return ("allow", f"Pipeline agent '{agent_name}' authorized")
        impl_active = _is_explicit_implement_active()
        # Issue #585: Block ALL code writes before alignment passes
        if impl_active and tool_name in ("Write", "Edit", "Bash"):
            if not _has_alignment_passed():
                if _is_code_file_target(tool_name, tool_input):
                    _log_deviation(
                        tool_input.get("file_path", "unknown") if tool_name != "Bash"
                        else "bash_command",
                        tool_name,
                        "alignment_gate_not_passed",
                    )
                    return ("deny", (
                        "ALIGNMENT GATE: /implement is active but STEP 2 (PROJECT.md alignment) "
                        "has not passed yet. The coordinator must complete alignment validation "
                        "before any code changes are allowed. Complete STEP 2 first."
                    ))
        # Issue #528: If /implement was explicitly invoked, block coordinator code writes
        if impl_active and tool_name in ("Write", "Edit", "Bash"):
            level = os.getenv("ENFORCEMENT_LEVEL", "block").strip().lower()
            if level != "off" and _is_code_file_target(tool_name, tool_input):
                block_reason = (
                    "WORKFLOW ENFORCEMENT: /implement is active — code changes must be "
                    "made by pipeline agents (implementer, test-master, doc-master), "
                    "not the coordinator. Delegate this work to the appropriate agent."
                )
                _log_deviation(
                    tool_input.get("file_path", "unknown") if tool_name != "Bash"
                    else "bash_command",
                    tool_name,
                    "explicit_implement_coordinator_block",
                )
                return ("deny", block_reason)
        return ("allow", "Active /implement pipeline detected via state file")

    # Only check Edit, Write, and Bash tools
    if tool_name not in ("Edit", "Write", "Bash"):
        return ("allow", f"Tool '{tool_name}' not subject to workflow enforcement")

    # Get enforcement level (default: suggest - nudge toward /implement)
    level = os.getenv("ENFORCEMENT_LEVEL", "suggest").strip().lower()
    if level == "off":
        return ("allow", "Workflow enforcement disabled (level: off)")

    # Get file path and check exemptions
    file_path = tool_input.get("file_path", "")
    if _is_exempt_path(file_path):
        return ("allow", f"File exempt from workflow enforcement: {Path(file_path).name}")
    if file_path and Path(file_path).suffix.lower() not in CODE_EXTENSIONS:
        return ("allow", "Non-code file, no enforcement needed")

    # Analyze the change for significance
    if tool_name == "Edit":
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        is_significant, reason, details = _has_significant_additions(old_string, new_string, file_path)
    elif tool_name == "Write":
        content = tool_input.get("content", "")
        is_significant, reason, details = _has_significant_additions("", content, file_path)
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if not command:
            return ("allow", "No command to check")
        # Git bypass detection (Issue #406)
        if "git" in command:
            is_bypass, bypass_reason = _detect_git_bypass(command)
            if is_bypass:
                return ("deny", f"GIT BYPASS BLOCKED: {bypass_reason}")
        target_files = _extract_bash_file_writes(command)
        if not target_files:
            return ("allow", "No file writes detected in Bash command")
        # Check each target file for code file enforcement
        for fp in target_files:
            if _is_exempt_path(fp):
                continue
            if Path(fp).suffix.lower() not in CODE_EXTENSIONS:
                continue
            # Code file write detected via Bash
            file_name = Path(fp).name
            tip = "Tip: /implement handles testing, review, and docs automatically."
            if level == "warn":
                import sys as _sys
                _sys.stderr.write(f"WARNING: Bash file write to code file: {file_name}\n")
                _sys.stderr.flush()
                _log_deviation(file_name, tool_name, "Bash file write to code file")
                return ("allow", f"Bash file write detected ({file_name}), allowed at WARN level")
            elif level == "suggest":
                _log_deviation(file_name, tool_name, "Bash file write to code file")
                return ("ask", f"Bash file write to code file {file_name}. {tip}")
            elif level == "block":
                return ("deny", f"WORKFLOW ENFORCEMENT: Bash file write to code file {file_name}. "
                        f"Significant code changes require /implement workflow. {tip}")
        return ("allow", "Bash command writes only to non-code/exempt files")
    else:
        return ("allow", f"Tool '{tool_name}' allowed")

    if not is_significant:
        return ("allow", "Minor edit, no significant code additions detected")

    file_name = Path(file_path).name if file_path else "unknown"
    tip = "Tip: /implement handles testing, review, and docs automatically."

    if level == "warn":
        import sys as _sys
        _sys.stderr.write(f"WARNING: {reason} in {file_name}\n")
        _sys.stderr.flush()
        _log_deviation(file_name, tool_name, reason)
        return ("allow", f"{reason} in {file_name}, allowed at WARN level")

    elif level == "suggest":
        _log_deviation(file_name, tool_name, reason)
        return ("ask", f"{reason} in {file_name}. "
                f"Use /implement for this change:\n"
                f"- /implement \"description\"\n"
                f"- /implement --quick \"description\" (skip full pipeline)\n"
                f"- /implement #<issue-number>")

    elif level == "block":
        return ("deny", f"WORKFLOW ENFORCEMENT: {reason} in {file_name}. "
                f"Significant code changes require /implement workflow. "
                f"STOP coding directly and run: /implement --quick \"description\"\n"
                f"Use /implement for this change:\n"
                f"- /implement \"description\"\n"
                f"- /implement --quick \"description\" (skip full pipeline)\n"
                f"- /implement #<issue-number>")

    return ("allow", f"Tool '{tool_name}' allowed")


def validate_batch_permission(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate batch permission for auto-approval.

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Check if batch permission is enabled
    enabled = os.getenv("PRE_TOOL_BATCH_PERMISSION", "false").lower() == "true"
    if not enabled:
        return ("allow", "Batch permission disabled")

    try:
        # Try to import permission classifier
        try:
            from permission_classifier import PermissionClassifier, PermissionLevel

            # Classify operation
            classifier = PermissionClassifier()
            level = classifier.classify(tool_name, tool_input)

            if level == PermissionLevel.SAFE:
                return ("allow", f"Batch permission: SAFE operation auto-approved")
            elif level == PermissionLevel.BOUNDARY:
                return ("allow", f"Batch permission: BOUNDARY operation allowed")
            else:  # PermissionLevel.SENSITIVE
                return ("ask", f"Batch permission: SENSITIVE operation requires user approval")

        except ImportError:
            # Permission classifier not available - allow (don't block)
            return ("allow", "Batch permission classifier unavailable")

    except Exception as e:
        # Error in validation - allow (don't block on errors)
        return ("allow", f"Batch permission error: {e}")


def combine_decisions(validators_results: List[Tuple[str, str, str]]) -> Tuple[str, str]:
    """
    Combine multiple validator decisions into single decision.

    Decision Logic:
    - If ANY validator returns "deny" → "deny" (block operation)
    - If ALL validators return "allow" → "allow" (approve operation)
    - Otherwise → "ask" (prompt user)

    Args:
        validators_results: List of (validator_name, decision, reason) tuples

    Returns:
        Tuple of (final_decision, combined_reason)
    """
    decisions = []
    reasons = []

    for validator_name, decision, reason in validators_results:
        decisions.append(decision)
        reasons.append(f"[{validator_name}] {reason}")

    # If ANY deny → deny
    if "deny" in decisions:
        deny_reasons = [r for v, d, r in validators_results if d == "deny"]
        return ("deny", "; ".join(deny_reasons))

    # If ALL allow → allow
    if all(d == "allow" for d in decisions):
        return ("allow", "; ".join(reasons))

    # Otherwise → ask
    ask_reasons = [r for v, d, r in validators_results if d == "ask"]
    if ask_reasons:
        return ("ask", "; ".join(ask_reasons))
    else:
        return ("ask", "; ".join(reasons))


def _log_pretool_activity(tool_name: str, tool_input: Dict, decision: str, reason: str) -> None:
    """Log PreToolUse decision to shared activity log."""
    try:
        import json as _json
        from datetime import datetime as _dt, timezone as _tz
        log_dir = Path(os.getcwd()) / ".claude" / "logs" / "activity"
        log_dir.mkdir(parents=True, exist_ok=True)
        date_str = _dt.now().strftime("%Y-%m-%d")

        # Build a compact summary of what's being done
        summary = {"tool": tool_name}
        if tool_name in ("Edit", "Write"):
            summary["file"] = tool_input.get("file_path", "")
        elif tool_name == "Bash":
            cmd = tool_input.get("command", "")
            summary["command"] = cmd[:200] if len(cmd) > 200 else cmd
        elif tool_name in ("Task", "Agent"):
            summary["subagent"] = tool_input.get("subagent_type", "")
            summary["description"] = tool_input.get("description", "")
        elif tool_name == "Skill":
            summary["skill"] = tool_input.get("skill", "")

        entry = {
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "hook": "PreToolUse",
            "decision": decision,
            "reason": reason[:300],
            "session_id": os.getenv("CLAUDE_SESSION_ID") or _session_id,
            "agent": _get_active_agent_name() or "main",
            **summary,
        }
        with open(log_dir / f"{date_str}.jsonl", "a") as f:
            f.write(_json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass


def output_decision(decision: str, reason: str, *, system_message: str = ""):
    """Output the hook decision in required format.

    Args:
        decision: Permission decision ("allow", "deny", or "ask")
        reason: Human-readable reason for the decision
        system_message: Optional message injected into model context (visible to user)
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output))


DENY_CACHE_PATH = "/tmp/.claude_deny_cache.jsonl"

# Agent denial state for blocking coordinator workaround edits (Issue #750)
AGENT_DENY_STATE_DIR = "/tmp"
AGENT_DENY_TTL = 300  # seconds


def _sanitize_session_id(raw: str) -> str:
    """Sanitize session_id for safe use in filesystem paths.

    Defense-in-depth layers:
    1. Strip null bytes (prevents C-layer truncation bypass)
    2. Unicode NFKC normalization (prevents lookalike characters to ASCII equivalents)
    3. Allowlist regex: replace non-[a-zA-Z0-9_-] with underscore (OWASP recommended)
    4. Cap length at 128 characters (prevents PATH_MAX exhaustion)

    Args:
        raw: The raw session_id string from hook input_data dictionary.

    Returns:
        A filesystem-safe session_id string containing only [a-zA-Z0-9_-].
        Returns 'unknown' if input is empty or None after sanitization.
    """
    import re as _re
    import unicodedata
    if not isinstance(raw, str):
        raw = str(raw) if raw is not None else "unknown"
    # Layer 1: Strip null bytes — must be first before any regex processing
    raw = raw.replace('\x00', '')
    # Layer 2: Unicode NFKC normalization — collapse lookalike characters to ASCII equivalents
    raw = unicodedata.normalize('NFKC', raw)
    # Layer 3: Allowlist regex — only permit alphanumeric, underscore, hyphen characters
    sanitized = _re.sub(r'[^a-zA-Z0-9_-]', '_', raw)
    # Layer 4: Length cap — prevent PATH_MAX exhaustion on macOS (1024) and Linux (4096)
    sanitized = sanitized[:128]
    return sanitized if sanitized else 'unknown'


def _update_deny_cache(file_path: str) -> None:
    """Record a denied file path in the deny cache for escalation tracking.

    Appends a JSON line with the path and current timestamp.
    Prunes stale entries (>300s) on every 10th write, capped at 500 lines.
    Failures are silently ignored — deny cache must never block legitimate commands.

    Args:
        file_path: The file path that was denied.
    """
    import json as _json
    import time as _time
    _PRUNE_MAX_AGE = 300  # seconds
    _PRUNE_MAX_LINES = 500
    try:
        with open(DENY_CACHE_PATH, "a") as f:
            entry = {"path": file_path, "timestamp": _time.time()}
            f.write(_json.dumps(entry) + "\n")
        # Prune on every 10th write (check line count to decide)
        cache_p = Path(DENY_CACHE_PATH)
        if cache_p.exists():
            all_lines = cache_p.read_text().splitlines()
            if len(all_lines) % 10 == 0 or len(all_lines) > _PRUNE_MAX_LINES:
                now = _time.time()
                cutoff = now - _PRUNE_MAX_AGE
                kept = []
                for raw_line in all_lines:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        parsed = _json.loads(raw_line)
                        if parsed.get("timestamp", 0) >= cutoff:
                            kept.append(raw_line)
                    except (ValueError, KeyError):
                        continue
                # Cap at max lines (keep most recent)
                if len(kept) > _PRUNE_MAX_LINES:
                    kept = kept[-_PRUNE_MAX_LINES:]
                cache_p.write_text("\n".join(kept) + "\n" if kept else "")
    except Exception:
        pass  # Never fail the hook for cache writes


def _check_deny_cache(file_path: str, *, window_seconds: int = 60) -> bool:
    """Check if a file path was denied within the recent time window.

    Used to detect repeated bypass attempts and escalate messaging.
    Failures return False — deny cache must never block legitimate commands.

    Args:
        file_path: The file path to check.
        window_seconds: How far back to look in seconds (default: 60).

    Returns:
        True if the path was denied within the window, False otherwise.
    """
    import json as _json
    import time as _time
    try:
        cache_path = Path(DENY_CACHE_PATH)
        if not cache_path.exists():
            return False
        now = _time.time()
        cutoff = now - window_seconds
        with open(cache_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = _json.loads(line)
                    if entry.get("timestamp", 0) < cutoff:
                        continue
                    cached_path = entry.get("path", "")
                    # Exact match
                    if cached_path == file_path:
                        return True
                    # Basename fallback for cross-tool detection (Issue #803):
                    # Write may deny "/Users/.../agents/foo.md" while Bash uses
                    # "agents/foo.md" — match on basename as fallback.
                    if cached_path and file_path:
                        try:
                            if Path(cached_path).name == Path(file_path).name:
                                return True
                        except Exception:
                            pass
                except (ValueError, KeyError):
                    continue
    except Exception:
        pass  # Never fail the hook for cache reads
    return False


def _record_agent_denial(agent_type: str) -> None:
    """Record that an agent invocation was denied by prompt integrity (Issue #750).

    Writes a JSON file keyed by session_id so subsequent Write/Edit calls
    can detect the workaround pattern and block substantive edits to
    protected infrastructure.

    Atomic write: writes to a .tmp file first, then os.replace.
    Fail-open: exceptions are silently ignored.

    Args:
        agent_type: The agent type that was denied (e.g. 'implementer').
    """
    import json as _json
    import tempfile as _tempfile
    import time as _time
    try:
        state = {
            "agent_type": agent_type,
            "timestamp": _time.time(),
            "session_id": _session_id,
        }
        state_path = os.path.join(AGENT_DENY_STATE_DIR, f"adev-agent-deny-{_session_id}.json")
        # Path confinement: verify resolved path stays within AGENT_DENY_STATE_DIR
        resolved = os.path.realpath(state_path)
        base = os.path.realpath(AGENT_DENY_STATE_DIR)
        if not resolved.startswith(base + os.sep) and resolved != base:
            return  # Path escapes base directory — fail-open, silently refuse to write
        # Atomic creation via O_CREAT|O_EXCL prevents symlink attacks (replaces predictable .tmp)
        tmp_fd, tmp_path = _tempfile.mkstemp(dir=AGENT_DENY_STATE_DIR, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                _json.dump(state, f)
            os.replace(tmp_path, state_path)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:
        pass  # Fail-open: never block on state file errors


def _check_agent_denial(*, window_seconds: int = AGENT_DENY_TTL) -> "Optional[str]":
    """Check whether an agent invocation was recently denied (Issue #750).

    Returns the agent_type if a denial record exists within the time window
    and the session_id matches, otherwise None. Fail-open on all errors.

    Args:
        window_seconds: How far back to look for denials (default: AGENT_DENY_TTL).

    Returns:
        The denied agent_type string, or None if no recent denial.
    """
    import json as _json
    import time as _time
    try:
        state_path = os.path.join(AGENT_DENY_STATE_DIR, f"adev-agent-deny-{_session_id}.json")
        # Path confinement: verify resolved path stays within AGENT_DENY_STATE_DIR
        resolved = os.path.realpath(state_path)
        base = os.path.realpath(AGENT_DENY_STATE_DIR)
        if not resolved.startswith(base + os.sep) and resolved != base:
            return None  # Path escapes base directory — fail-open, refuse to read
        if not os.path.exists(state_path):
            return None
        with open(state_path) as f:
            state = _json.load(f)
        if state.get("session_id") != _session_id:
            return None
        if _time.time() - state.get("timestamp", 0) > window_seconds:
            return None
        return state.get("agent_type", "")
    except Exception:
        return None  # Fail-open


def _check_bash_state_deletion(command: str) -> "Optional[Tuple[str, str]]":
    """Check if a Bash command deletes or truncates pipeline state files.

    Detects rm, unlink, truncate, redirect-to-empty, and python os.remove/os.unlink/Path.unlink
    targeting pipeline state files. Pure function: caller decides whether to block based on
    pipeline-active status.

    Args:
        command: The Bash command string to inspect.

    Returns:
        None if no state file is targeted, or a tuple of (file_path, reason) if detected.
    """
    import re

    # Protected state file patterns
    _STATE_FILE_PATTERNS = [
        "/tmp/implement_pipeline_state.json",
        "/tmp/.claude_deny_cache.jsonl",
    ]
    _STATE_FILE_GLOB_PREFIXES = [
        "/tmp/pipeline_completion_state_",
        "/tmp/pipeline_secrets/",
    ]

    # Also protect whatever PIPELINE_STATE_FILE env var points to
    _env_state = os.environ.get("PIPELINE_STATE_FILE", "")
    if _env_state:
        _STATE_FILE_PATTERNS.append(_env_state)

    def _is_state_file(path: str) -> bool:
        """Check if a path matches a protected state file."""
        path = path.strip().strip("'\"")
        if not path:
            return False
        for pattern in _STATE_FILE_PATTERNS:
            if path == pattern or path.endswith("/" + Path(pattern).name):
                return True
        for prefix in _STATE_FILE_GLOB_PREFIXES:
            if path.startswith(prefix):
                return True
        # Also check for $PIPELINE_STATE_FILE variable reference
        if "$PIPELINE_STATE_FILE" in path or "${PIPELINE_STATE_FILE}" in path:
            return True
        return False

    # Strip heredoc bodies and --body/--message quoted args so that text content
    # (e.g. issue descriptions mentioning deletion commands) is not scanned.
    # Issue #866: false positive when gh issue create heredoc body mentions rm.

    # Strip heredoc bodies: <<'EOF'...EOF, <<EOF...EOF, <<"EOF"...EOF, <<-EOF...EOF
    _heredoc_pat = r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b"
    command = re.sub(_heredoc_pat, "", command, flags=re.DOTALL)

    # Strip --body '...' / --body "..." / --body "$(cat ...)" argument values
    _body_pat = r"""--body\s+(?:'[^']*'|"[^"]*"|\$\([^)]*\))"""
    command = re.sub(_body_pat, '--body ""', command)

    # Strip --message / -m quoted argument values
    _msg_pat = r"""(?:--message|-m)\s+(?:'[^']*'|"[^"]*")"""
    command = re.sub(_msg_pat, '-m ""', command)

    try:
        # 1. rm [-flags] <path>
        rm_pattern = r'\brm\s+(?:-[^\s]+\s+)*([^\s;&|]+)'
        for match in re.finditer(rm_pattern, command):
            target = match.group(1).strip().strip("'\"")
            if _is_state_file(target):
                return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

        # 2. unlink <path>
        unlink_pattern = r'\bunlink\s+([^\s;&|]+)'
        for match in re.finditer(unlink_pattern, command):
            target = match.group(1).strip().strip("'\"")
            if _is_state_file(target):
                return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

        # 3. truncate [-flags [value]] <path>
        # Handle: truncate -s 0 /path, truncate --size=0 /path, truncate /path
        truncate_pattern = r'\btruncate\s+(?:(?:-\w+\s+\S+\s+)|(?:--\w+=\S+\s+))*([^\s;&|]+)'
        for match in re.finditer(truncate_pattern, command):
            target = match.group(1).strip().strip("'\"")
            if _is_state_file(target):
                return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

        # 4. Redirect-to-empty: > /path/to/state/file (with nothing before >)
        empty_redirect_pattern = r'(?:^|;|&&|\|\|)\s*>\s*([^\s;&|]+)'
        for match in re.finditer(empty_redirect_pattern, command):
            target = match.group(1).strip().strip("'\"")
            if _is_state_file(target):
                return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

        # 5. python3 -c with os.remove/os.unlink/Path.unlink
        py_delete_patterns = [
            r'os\.remove\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'os\.unlink\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'Path\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\.unlink',
        ]
        for py_pat in py_delete_patterns:
            for match in re.finditer(py_pat, command, re.IGNORECASE):
                target = match.group(1).strip()
                if _is_state_file(target):
                    return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

    except Exception:
        pass  # Fail-open: never block legitimate commands on detection errors

    return None


def _check_spec_test_deletion_scope(file_path: str) -> "Optional[Tuple[str, str]]":
    """Check if a spec validation test deletion is outside the current batch scope.

    Spec validation tests (tests/spec_validation/test_spec_issue{N}_*.py) are
    scoped to the issue that created them. Deleting a spec test from a different
    issue is blocked unless the escape hatch env var is set.

    Args:
        file_path: Path to the file being deleted or overwritten.

    Returns:
        None if the operation is allowed, or (file_path, block_reason) if blocked.
    """
    import re

    try:
        # Escape hatch
        skip_guard = os.getenv("SKIP_SPEC_DELETION_GUARD", "").lower()
        if skip_guard in ("1", "true", "yes"):
            return None

        # Normalize path to handle traversal
        resolved = Path(file_path).resolve()
        name = resolved.name

        # Only guard files in tests/spec_validation/
        resolved_str = str(resolved)
        if "tests/spec_validation/" not in resolved_str and "tests/spec_validation\\" not in resolved_str:
            return None

        # Extract issue number from filename pattern: test_spec_issue{N}_*.py
        match = re.match(r'test_spec_issue(\d+)_', name)
        if not match:
            return None  # Not an issue-scoped spec test (e.g. test_spec_tautological_assertions.py)

        spec_issue = int(match.group(1))

        # Get current pipeline issue
        current_issue = _get_current_issue_number()

        # Fail open when no pipeline context
        if current_issue == 0:
            return None

        # Allow if same issue
        if spec_issue == current_issue:
            return None

        # Block: different issue
        block_reason = (
            f"BLOCKED: Deletion of spec test '{name}' denied (Issue #790). "
            f"This test belongs to issue #{spec_issue} but current pipeline is issue #{current_issue}. "
            f"Spec validation tests are scoped to their originating issue. "
            f"REQUIRED NEXT ACTION: If this test is truly obsolete, move it to tests/archived/ "
            f"instead of deleting it. Run: mv {file_path} tests/archived/"
        )
        return (file_path, block_reason)

    except Exception:
        pass  # Fail-open: never block legitimate commands on detection errors

    return None


def _extract_bash_spec_test_targets(command: str) -> "list[str]":
    """Extract spec validation test file paths targeted by a Bash command.

    Detects rm, unlink, truncate, redirect-to-empty, Python os.remove/Path.unlink,
    and mv commands that move spec tests outside tests/archived/.

    Args:
        command: The Bash command string to inspect.

    Returns:
        List of file paths targeting spec validation tests.
    """
    import re

    targets = []

    try:
        # Helper to check if a path looks like a spec test
        def _is_spec_test_path(path: str) -> bool:
            path = path.strip().strip("'\"")
            return bool(
                ("spec_validation" in path or "test_spec_issue" in path)
                and re.search(r'test_spec_issue\d+_', path)
            )

        # 1. rm [-flags] <paths>
        rm_pattern = r'\brm\s+(?:-[^\s]+\s+)*([^\s;&|]+(?:\s+[^\s;&|]+)*)'
        for match in re.finditer(rm_pattern, command):
            for token in match.group(1).split():
                token = token.strip("'\"")
                if _is_spec_test_path(token):
                    targets.append(token)

        # 2. unlink <path>
        unlink_pattern = r'\bunlink\s+([^\s;&|]+)'
        for match in re.finditer(unlink_pattern, command):
            target = match.group(1).strip("'\"")
            if _is_spec_test_path(target):
                targets.append(target)

        # 3. truncate [-flags [value]] <path>
        truncate_pattern = r'\btruncate\s+(?:(?:-\w+\s+\S+\s+)|(?:--\w+=\S+\s+))*([^\s;&|]+)'
        for match in re.finditer(truncate_pattern, command):
            target = match.group(1).strip("'\"")
            if _is_spec_test_path(target):
                targets.append(target)

        # 4. Redirect-to-empty: > /path/to/file
        empty_redirect_pattern = r'(?:^|;|&&|\|\|)\s*>\s*([^\s;&|]+)'
        for match in re.finditer(empty_redirect_pattern, command):
            target = match.group(1).strip("'\"")
            if _is_spec_test_path(target):
                targets.append(target)

        # 5. Python os.remove / os.unlink / Path.unlink
        py_delete_patterns = [
            r'os\.remove\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'os\.unlink\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'Path\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\.unlink',
        ]
        for py_pat in py_delete_patterns:
            for match in re.finditer(py_pat, command, re.IGNORECASE):
                target = match.group(1).strip()
                if _is_spec_test_path(target):
                    targets.append(target)

        # 6. mv to NON-archived location (mv to tests/archived/ is allowed)
        mv_pattern = r'\bmv\s+(?:-[^\s]+\s+)*([^\s;&|]+)\s+([^\s;&|]+)'
        for match in re.finditer(mv_pattern, command):
            source = match.group(1).strip("'\"")
            dest = match.group(2).strip("'\"")
            if _is_spec_test_path(source):
                # Allow mv to tests/archived/
                if "tests/archived" in dest:
                    continue
                targets.append(source)

    except Exception:
        pass  # Fail-open

    return targets


def _check_bash_infra_writes(command: str) -> "Optional[Tuple[str, str]]":
    """Check if a Bash command writes to protected infrastructure paths.

    Conservative detection: false negatives OK, false positives NOT OK.
    Returns None if allowed, or (file_name, block_reason) if blocked.

    Detects: sed -i, cp/mv to protected paths, shell redirects (>, >>),
    tee to protected paths, python3 -c with open(..., 'w'),
    cat heredoc (cat > file << EOF), dd of=FILE,
    Path.write_text/write_bytes in python3 -c,
    python3 heredoc with open()/Path.write_text inside (Issue #558).

    Args:
        command: The Bash command string to inspect.

    Returns:
        None if the command is allowed, or a tuple of (file_name, reason)
        if it should be blocked.
    """
    import re

    # If pipeline is active, allow everything (same as Write/Edit behavior)
    try:
        if _is_pipeline_active():
            return None
    except Exception:
        pass  # If check fails, continue with inspection

    # Collect candidate target file paths from various write patterns
    target_paths = []  # type: list

    # 1. sed -i (in-place edit)
    sed_pattern = r'\bsed\s+(?:-[^i]*)?-i[^\s]*\s+(?:[\'"][^\'"]*[\'\"]\s+)?([^\s;&|]+)'
    for match in re.finditer(sed_pattern, command):
        target_paths.append(match.group(1))

    # 2. cp / mv destination (last argument)
    # Match: cp [flags] source dest  OR  cp [flags] source1 source2 dest/
    cp_mv_pattern = r'\b(?:cp|mv)\s+(?:-[^\s]+\s+)*(?:[^\s]+\s+)+([^\s;&|]+)'
    for match in re.finditer(cp_mv_pattern, command):
        target_paths.append(match.group(1))

    # 3. Shell redirects (>, >>) — reuse existing helper
    redirect_targets = _extract_bash_file_writes(command)
    target_paths.extend(redirect_targets)

    # 4. python3 -c with file writes — Issue #589 (enhanced with python_write_detector)
    py_c_patterns = [
        r'python3?\s+-c\s+"([^"]+)"',   # double-quoted: python3 -c "..."
        r"python3?\s+-c\s+'([^']+)'",   # single-quoted: python3 -c '...'
    ]
    py_c_snippets = []
    for py_c_pattern in py_c_patterns:
        for match in re.finditer(py_c_pattern, command):
            py_c_snippets.append(match.group(1))

    # 5. python3 heredoc — python3 << 'EOF' with file writes inside (Issue #558, #589)
    py_heredoc_pattern = r'python3?\s+.*?<<\s*[\'"]?(\w+)[\'"]?'
    for match in re.finditer(py_heredoc_pattern, command):
        marker = match.group(1)
        heredoc_start = match.end()
        remaining = command[heredoc_start:]
        import re as _re
        _end_match = _re.search(r'(?:^|\n)' + _re.escape(marker) + r'(?:\n|$)', remaining)
        end_idx = _end_match.start() if _end_match else -1
        heredoc_body = remaining[:end_idx] if end_idx >= 0 else remaining
        py_c_snippets.append(heredoc_body)

    # Use python_write_detector if available, else fall back to inline regex
    for snippet in py_c_snippets:
        if _python_write_detector is not None:
            targets = _python_write_detector.extract_write_targets(snippet)
            for t in targets:
                if t == _python_write_detector.SUSPICIOUS_EXEC_SENTINEL:
                    # Directly block if command references protected path segments
                    for seg in ["agents/", "hooks/", "lib/", "skills/", "commands/"]:
                        if seg in command:
                            return (
                                f"__suspicious_exec__ ({seg})",
                                f"BLOCKED: Bash command contains exec/eval with dynamic arguments "
                                f"that reference protected path '{seg}'. This pattern may be "
                                f"attempting to bypass write enforcement. "
                                f"Infrastructure files require the /implement pipeline. "
                                f"Run: /implement \"description\" "
                                f"REQUIRED NEXT ACTION: Delegate file modifications to the "
                                f"implementer agent via the Agent tool. Do NOT use Bash to "
                                f"write to infrastructure files."
                            )
                else:
                    target_paths.append(t)
        else:
            # Inline regex fallback (original patterns)
            open_pattern = r'open\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"][wa]'
            for open_match in re.finditer(open_pattern, snippet):
                target_paths.append(open_match.group(1))
            path_write_pattern = r"Path\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\.write_(?:text|bytes)"
            for path_match in re.finditer(path_write_pattern, snippet):
                target_paths.append(path_match.group(1))
            # shutil fallback — Issue #589
            shutil_pattern = r'(?:\w+)\.(?:copy|copy2|move|copyfile)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)'
            for shutil_match in re.finditer(shutil_pattern, snippet):
                target_paths.append(shutil_match.group(1))
            # os.rename/os.replace fallback — Issue #698 (destination is 2nd arg)
            os_rename_pattern = r'(?:\w+)\.(?:rename|replace)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]'
            for os_rename_match in re.finditer(os_rename_pattern, snippet):
                target_paths.append(os_rename_match.group(1))
            # Path(...).rename/Path(...).replace fallback — Issue #698 (destination is 1st arg)
            path_rename_pattern = r'(?:\w+)\s*\(\s*[\'"][^\'"]+[\'"]\s*\)\.(?:rename|replace)\s*\(\s*[\'"]([^\'"]+)[\'"]'
            for path_rename_match in re.finditer(path_rename_pattern, snippet):
                target_paths.append(path_rename_match.group(1))

    # Check each target path against protected infrastructure
    for fp in target_paths:
        fp = fp.strip().strip("'\"")
        if not fp:
            continue
        try:
            if _is_protected_infrastructure(fp):
                file_name = Path(fp).name
                # Check deny cache for escalation (Issue #558)
                repeated = _check_deny_cache(fp)
                if repeated:
                    block_reason = (
                        f"BLOCKED (repeated attempt): Bash command writes to protected "
                        f"file '{file_name}'. This path was already denied recently. "
                        f"Infrastructure files (agents/, commands/, hooks/, lib/, skills/) "
                        f"require the /implement pipeline. Run: /implement \"description\" "
                        f"REQUIRED NEXT ACTION: Delegate file modifications to the "
                        f"implementer agent via the Agent tool. Do NOT use Bash to "
                        f"write to infrastructure files."
                    )
                else:
                    block_reason = (
                        f"BLOCKED: Bash command writes to protected file '{file_name}'. "
                        f"Infrastructure files (agents/, commands/, hooks/, lib/, skills/) "
                        f"require the /implement pipeline. Run: /implement \"description\" "
                        f"REQUIRED NEXT ACTION: Delegate file modifications to the "
                        f"implementer agent via the Agent tool. Do NOT use Bash to "
                        f"write to infrastructure files."
                    )
                _update_deny_cache(fp)
                return (file_name, block_reason)
        except Exception:
            continue  # Skip paths that can't be resolved

    return None


def _run_extensions(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """Run hook extension scripts that can block tool calls.

    Discovers *.py files in extensions/ directories (both alongside this hook
    and in the project's .claude/hooks/extensions/), loads each, and calls
    its ``check(tool_name, tool_input)`` function.

    Extensions survive /sync and /install — they are user-owned files in a
    directory that is never overwritten.

    Args:
        tool_name: Name of the tool being called.
        tool_input: Tool input parameters.

    Returns:
        Tuple of (decision, reason). ``("deny", reason)`` if any extension
        blocks; ``("allow", "")`` otherwise.
    """
    # Check kill-switch env var
    if os.getenv("HOOK_EXTENSIONS_ENABLED", "true").lower() == "false":
        return ("allow", "")

    # Discover extension directories
    ext_dirs: list[Path] = []

    # 1. Directory alongside this hook file (global ~/.claude/hooks/extensions/)
    hook_ext_dir = Path(__file__).parent / "extensions"
    ext_dirs.append(hook_ext_dir)

    # 2. Project-level .claude/hooks/extensions/
    project_ext_dir = Path.cwd() / ".claude" / "hooks" / "extensions"
    ext_dirs.append(project_ext_dir)

    # Collect extension files, deduplicated by filename (first occurrence wins)
    seen_names: set[str] = set()
    extension_files: list[Path] = []

    for ext_dir in ext_dirs:
        if not ext_dir.is_dir():
            continue
        try:
            py_files = sorted(ext_dir.glob("*.py"))
        except OSError:
            continue
        for py_file in py_files:
            # Skip symlinks (security)
            if py_file.is_symlink():
                continue
            if py_file.name in seen_names:
                continue
            seen_names.add(py_file.name)
            extension_files.append(py_file)

    # Execute each extension
    for ext_file in extension_files:
        try:
            module_name = f"_hook_ext_{ext_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, str(ext_file))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            check_fn = getattr(module, "check", None)
            if check_fn is None:
                continue

            result = check_fn(tool_name, tool_input)

            # Validate return type
            if not isinstance(result, (tuple, list)) or len(result) != 2:
                continue

            decision, reason = result
            if decision == "deny":
                return ("deny", f"[ext:{ext_file.name}] {reason}")

        except Exception:
            # Per-extension isolation — never crash the hook
            continue

    return ("allow", "")


def _maybe_write_issue_context(tool_input: Dict) -> None:
    """Write issue command context file when Skill invokes an issue-creating command.

    Called from the NATIVE_TOOLS fast path when tool_name == "Skill".
    Writes the context JSON that _is_issue_command_active() checks, enabling
    downstream gh issue create Bash commands to pass through the hook.

    Fails open (silently) — a write failure should not block the Skill invocation.

    Args:
        tool_input: The tool_input dict from the hook, containing "skill" and/or "args".
    """
    skill_name = (
        tool_input.get("skill", "")
        or (tool_input.get("args", "").split()[0] if tool_input.get("args") else "")
    )
    # Normalize: strip leading slash if present
    skill_name = skill_name.lstrip("/")
    if skill_name in GH_ISSUE_COMMANDS:
        try:
            import json as _json
            from datetime import datetime, timezone

            with open(GH_ISSUE_COMMAND_CONTEXT_PATH, "w") as f:
                _json.dump(
                    {
                        "command": skill_name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    f,
                )
        except Exception:
            pass  # Fail open - don't block Skill invocation on context write failure


# ============================================================================
# Plan-Exit Gate Helpers (Issue #926)
# ============================================================================


def _read_plan_exit_marker() -> "Optional[dict]":
    """Read the plan-mode-exit marker.

    Returns a dict with normalized 'stage' field, or None if no enforcement
    should occur. Handles staleness (>30 min auto-deletes and returns None),
    corruption (deletes and returns None), and missing 'stage' (back-compat:
    treated as 'critique_done'). Unknown stage values are treated as
    'plan_exited' (fail-safe).

    Returns:
        dict with at least 'stage' key (always one of 'plan_exited' or
        'critique_done'), or None if no marker exists or marker was cleared.
    """
    try:
        marker_path = Path(os.getcwd()) / _PLAN_EXIT_MARKER_PATH
        if not marker_path.exists():
            return None

        try:
            from datetime import datetime as _datetime, timezone as _timezone
            raw_data = json.loads(marker_path.read_text())
            marker_ts = _datetime.fromisoformat(raw_data.get("timestamp", ""))
            age_minutes = (_datetime.now(_timezone.utc) - marker_ts).total_seconds() / 60.0
            if age_minutes > _PLAN_EXIT_STALE_MINUTES:
                marker_path.unlink(missing_ok=True)
                return None
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            # Corrupted marker or bad timestamp — delete and pass through
            try:
                marker_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

        # Normalize stage field
        raw_stage = raw_data.get("stage")
        if raw_stage is None:
            # Back-compat: old markers without stage field
            raw_data["stage"] = "critique_done"
        elif raw_stage in ("plan_exited", "critique_done"):
            raw_data["stage"] = raw_stage
        else:
            # Unknown stage — fail-safe to plan_exited
            raw_data["stage"] = "plan_exited"

        return raw_data
    except Exception:
        # Never raise from a hook — fail open (no enforcement)
        return None


def _delete_plan_exit_marker() -> None:
    """Best-effort deletion of the plan-exit marker. Never raises."""
    try:
        marker_path = Path(os.getcwd()) / _PLAN_EXIT_MARKER_PATH
        marker_path.unlink(missing_ok=True)
    except Exception:
        pass


def _bash_command_on_allowlist(command: str) -> bool:
    """Check whether a Bash command is on the plan-exit read-only allowlist.

    Returns True iff the command:
      1. Contains zero injection metacharacters (raw substring check), AND
      2. Tokenizes via .split() to match a 1-, 2-, or 3-token allowlist entry.

    NOTE: raw substring rejection (not shlex) is intentional. shlex would
    silently accept ';' inside quoted strings, which defeats injection
    blocking.

    Args:
        command: Raw Bash command string.

    Returns:
        True if allowed (read-only, no injection), False otherwise.
    """
    if not command or not isinstance(command, str):
        return False

    # Reject injection metacharacters (raw substring check)
    for token in _PLAN_EXIT_INJECTION_TOKENS:
        if token in command:
            return False

    parts = command.split()
    if not parts:
        return False

    if len(parts) == 1:
        return parts[0] in _PLAN_EXIT_BASH_ALLOWLIST_1TOKEN

    # Check 3-token allowlist first (more specific)
    if len(parts) >= 3:
        three = (parts[0], parts[1], parts[2])
        if three in _PLAN_EXIT_BASH_ALLOWLIST_3TOKEN:
            return True

    # Check 2-token allowlist
    two = (parts[0], parts[1])
    if two in _PLAN_EXIT_BASH_ALLOWLIST_2TOKEN:
        return True

    # Check 1-token (e.g., "ls -la" — first token is "ls", 1-token allowlist)
    if parts[0] in _PLAN_EXIT_BASH_ALLOWLIST_1TOKEN:
        return True

    return False


def _check_plan_exit_native(tool_name: str, tool_input: Dict) -> "Optional[Tuple[str, str, str]]":
    """Plan-exit gate for native Claude Code tools (Issue #926).

    State matrix:
      stage=plan_exited:
        Read/Glob/Grep                           -> None (allow, fall through)
        Task(plan-critic)                        -> None
        Bash on allowlist (no injection)         -> None
        Write/Edit/NotebookEdit                  -> deny
        Task(other subagent)                     -> deny
        Bash off allowlist OR with injection     -> deny
      stage=critique_done:
        Bash(gh issue create ...)                -> allow + delete marker
        Task(implementer|issue-creator|          -> allow + delete marker
            continuous-improvement-analyst)
        anything else                            -> None (fall through)

    Race mitigation: on tentative deny, sleep 10ms and re-read the marker; if
    the stage advanced (writer hook fired during call), allow the tool.

    Args:
        tool_name: Tool being invoked.
        tool_input: Tool input parameters.

    Returns:
        (decision, reason, system_message) if gate fires, or None to fall
        through to later validators/default-allow.
    """
    import time as _time

    # Issue #938: Scope/escape guard. Precedence: escape > scope > default.
    if (os.environ.get("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "").strip().lower()
            in ("1", "true", "yes", "on")):
        return None
    if (Path(os.getcwd()) / ".claude" / "SKIP_PLAN_REVIEW").exists():
        return None
    if not (os.environ.get("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "").strip().lower()
            in ("1", "true", "yes", "on") or _is_adev_project()):
        return None

    marker = _read_plan_exit_marker()
    if marker is None:
        return None

    stage = marker.get("stage", "plan_exited")

    if stage == "critique_done":
        # Marker is primed for consumption. Only specific terminal actions
        # consume it; anything else passes through (fall to later gates).
        if tool_name == "Bash":
            command = tool_input.get("command", "") or ""
            # Detect `gh issue create` — canonical consuming command.
            # Tolerate leading whitespace and common flag positions.
            stripped = command.strip()
            if stripped.startswith("gh issue create") or stripped.startswith("gh  issue  create"):
                _delete_plan_exit_marker()
                return None  # Allow — fall through to later validators
            # Any other Bash at critique_done — fall through (normal enforcement)
            return None

        if tool_name in AGENT_TOOL_NAMES:
            subagent = (tool_input.get("subagent_type", "") or "").strip().lower()
            if subagent in _PLAN_EXIT_CONSUMER_AGENTS:
                _delete_plan_exit_marker()
                return None  # Allow — fall through to later validators
            # Other subagents at critique_done — fall through
            return None

        # Any other tool at critique_done — fall through
        return None

    # stage == "plan_exited"
    # --- Allow list (fall through, no deny) ---
    if tool_name in ("Read", "Glob", "Grep"):
        return None

    if tool_name in AGENT_TOOL_NAMES:
        subagent = (tool_input.get("subagent_type", "") or "").strip().lower()
        if subagent == "plan-critic":
            return None
        # Any other subagent is a deny candidate — apply race mitigation below

    if tool_name == "Bash":
        command = tool_input.get("command", "") or ""
        if _bash_command_on_allowlist(command):
            return None
        # Off-allowlist or has injection — deny candidate

    # --- Deny candidates ---
    # Race mitigation: 10ms re-read; if stage advanced, allow.
    # Belt-and-suspenders: catches any newly added NATIVE_TOOLS that aren't
    # explicitly handled above.
    deny_tools = ("Write", "Edit", "NotebookEdit")
    is_deny_candidate = (
        tool_name in deny_tools
        or (tool_name in AGENT_TOOL_NAMES and (tool_input.get("subagent_type", "") or "").strip().lower() != "plan-critic")
        or (tool_name == "Bash")
    )

    if not is_deny_candidate:
        # Any other unclassified tool — fall through (allow)
        return None

    # Re-read marker after 10ms to catch writer-hook advance
    try:
        _time.sleep(0.01)
    except Exception:
        pass
    refreshed = _read_plan_exit_marker()
    if refreshed is None:
        # Marker cleared during window — allow
        return None
    if refreshed.get("stage") == "critique_done":
        # Stage advanced — allow (fall through to consume-on-intent logic)
        return None

    # Build a systemMessage with clear guidance (visible to user).
    system_msg = (
        "PLAN MODE EXIT DETECTED — Plan critique required\n"
        "You just exited plan mode. Before proceeding, you MUST run the "
        "plan-critic agent on your plan. After plan-critic completes with "
        "PROCEED verdict, /implement, /create-issue, and /plan-to-issues "
        "will consume the marker and run normally.\n"
        "Escape hatches (any one):\n"
        "  - /implement --skip-review                       (one-shot)\n"
        "  - export AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1       (cross-session, recommended)\n"
        "  - touch .claude/SKIP_PLAN_REVIEW                 (local, gitignored)"
    )
    return ("deny", _PLAN_EXIT_DENY_REASON, system_msg)


def _check_plan_exit_mcp(tool_name: str) -> "Optional[Tuple[str, str]]":
    """Plan-exit gate for MCP (non-native) tools (Issue #926).

    State matrix:
      stage=plan_exited: deny unless tool_name in _PLAN_EXIT_MCP_READONLY.
      stage=critique_done: None (fall through — marker consumed by native gate).

    Same 10ms race mitigation as the native gate.

    Args:
        tool_name: MCP tool name (e.g., "mcp__ms365__send-mail").

    Returns:
        (decision, reason) if gate fires, or None to fall through.
    """
    import time as _time

    # Issue #938: Scope/escape guard. Precedence: escape > scope > default.
    if (os.environ.get("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "").strip().lower()
            in ("1", "true", "yes", "on")):
        return None
    if (Path(os.getcwd()) / ".claude" / "SKIP_PLAN_REVIEW").exists():
        return None
    if not (os.environ.get("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "").strip().lower()
            in ("1", "true", "yes", "on") or _is_adev_project()):
        return None

    marker = _read_plan_exit_marker()
    if marker is None:
        return None

    stage = marker.get("stage", "plan_exited")
    if stage == "critique_done":
        # MCP tools don't consume the marker; native gate handles consumption.
        return None

    # stage == "plan_exited"
    if tool_name in _PLAN_EXIT_MCP_READONLY:
        return None

    # Deny candidate — race mitigation
    try:
        _time.sleep(0.01)
    except Exception:
        pass
    refreshed = _read_plan_exit_marker()
    if refreshed is None:
        return None
    if refreshed.get("stage") == "critique_done":
        return None

    return ("deny", _PLAN_EXIT_DENY_REASON)


def main():
    """Main entry point - dispatch to all validators and combine decisions."""
    try:
        # Load environment variables
        load_env()

        # Read input from stdin
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            # Invalid JSON - ask user (don't block on invalid input)
            output_decision("ask", f"Invalid input JSON: {e}")
            sys.exit(0)

        # Extract session_id from hook stdin for logging functions (Issue #504).
        # The env var CLAUDE_SESSION_ID is absent in most hook contexts, so we
        # store the stdin value at module level as a fallback.
        global _session_id, _agent_type
        _session_id = _sanitize_session_id(input_data.get("session_id", "unknown"))

        # Extract agent_type from hook stdin JSON (Issue #591).
        # When fired inside a subagent, Claude Code populates agent_type in the
        # hook payload even though CLAUDE_AGENT_NAME may be absent from the
        # subprocess environment.  _get_active_agent_name() uses this as primary
        # identity source.
        _agent_type = input_data.get("agent_type", "")

        # Extract tool information
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        if not tool_name:
            # No tool name - ask user
            output_decision("ask", "No tool name provided")
            sys.exit(0)

        # =================================================================
        # FAST PATH: Native tools skip ALL hook layers.
        # Hooks run BEFORE settings.json — returning "ask" here overrides
        # settings.json "allow" rules. Native tools are governed by
        # settings.json, not by this hook.
        # =================================================================
        if tool_name in NATIVE_TOOLS:
            # Auto-write context file when Skill invokes issue-creating commands
            # (Issue #647, #663). This MUST happen before any Bash gh-issue-create
            # check, because the Skill tool fires first and sets up the context
            # that _is_issue_command_active() reads.
            if tool_name == "Skill":
                _maybe_write_issue_context(tool_input)

            # Plan-Exit Gate (Issue #926): enforce plan-critic workflow on
            # every tool call. Moved from UserPromptSubmit because in-turn
            # model tool calls bypass UserPromptSubmit. Marker writer and
            # stage advancer unchanged — only enforcement event moved.
            plan_exit_decision = _check_plan_exit_native(tool_name, tool_input)
            if plan_exit_decision is not None:
                decision, reason, system_message = plan_exit_decision
                _log_pretool_activity(tool_name, tool_input, decision, reason)
                output_decision(decision, reason, system_message=system_message)
                sys.exit(0)

            # Infrastructure protection: block direct edits to agents/, commands/,
            # hooks/, lib/, skills/ unless /implement pipeline is active (Issue #483)
            # Threat model: accidental direct edits, not malicious local attacker.
            # CLAUDE_AGENT_NAME is set by Claude Code; env var trust is by design.
            # Fail-closed: if the check itself errors, block the edit (A04 remediation).
            if tool_name in ("Write", "Edit"):
                file_path = tool_input.get("file_path", "")
                try:
                    is_protected = _is_protected_infrastructure(file_path)
                    pipeline_active = _is_pipeline_active() if is_protected else False
                except Exception:
                    # Fail closed — if protection check errors, treat as protected
                    is_protected = True
                    pipeline_active = False
                if is_protected and not pipeline_active:
                    file_name = Path(file_path).name if file_path else "unknown"
                    block_reason = (
                        f"BLOCKED: Direct edit to '{file_name}' denied. "
                        f"Infrastructure files (agents/, commands/, hooks/, lib/, skills/) "
                        f"require the /implement pipeline. Run: /implement \"description\" "
                        f"REQUIRED NEXT ACTION: Run /implement with a description of your "
                        f"change. Delegate the edit to the implementer agent. "
                        f"Do NOT write infrastructure files directly."
                    )
                    _log_deviation(file_name, tool_name, "infrastructure_protection_block")
                    _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
                    output_decision(
                        "deny", block_reason,
                        system_message=(
                            f"BLOCKED: Direct edit to '{file_name}' denied. "
                            f"Use /implement to modify infrastructure files."
                        ),
                    )
                    # Issue #803: Record denial for cross-tool workaround detection.
                    # If the agent retries via Bash heredoc, the deny cache catches it.
                    try:
                        _update_deny_cache(file_path)
                    except Exception:
                        pass  # Never fail the hook for cache writes
                    sys.exit(0)

                # Issue #557: Block settings.json writes during active pipeline
                if file_path:
                    fname = Path(file_path).name
                    if fname in ("settings.json", "settings.local.json"):
                        try:
                            if _is_pipeline_active():
                                block_reason = (
                                    f"BLOCKED: Write to '{fname}' denied during active pipeline. "
                                    f"Settings files are protected during /implement sessions. "
                                    f"(Issue #557) "
                                    f"REQUIRED NEXT ACTION: Complete the current /implement "
                                    f"pipeline first, then modify settings. "
                                    f"Do NOT write settings during an active pipeline."
                                )
                                _log_deviation(fname, tool_name, "settings_json_write_block")
                                _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
                                output_decision(
                                    "deny", block_reason,
                                    system_message=(
                                        f"BLOCKED: Write to '{fname}' denied during pipeline. "
                                        f"Complete /implement first."
                                    ),
                                )
                                sys.exit(0)
                        except Exception:
                            pass  # Don't block on check failure

                # Issue #790: Block deletion of spec validation tests outside current batch scope.
                # Detect Write with empty/whitespace content as a deletion vector.
                if file_path and tool_name == "Write":
                    try:
                        content = tool_input.get("content", "")
                        if isinstance(content, str) and content.strip() == "":
                            spec_block = _check_spec_test_deletion_scope(file_path)
                            if spec_block is not None:
                                _log_deviation(spec_block[0], tool_name, "spec_test_deletion_scope_block")
                                _log_pretool_activity(tool_name, tool_input, "deny", spec_block[1])
                                output_decision(
                                    "deny", spec_block[1],
                                    system_message=(
                                        f"BLOCKED: Spec test deletion outside batch scope. "
                                        f"Move to tests/archived/ instead."
                                    ),
                                )
                                sys.exit(0)
                    except Exception:
                        pass  # Fail-open: never block on detection errors

                # Layer 6: Prompt quality gate (Issue #842)
                # Block writes to agents/ or commands/ .md files that introduce
                # prompt anti-patterns (banned personas, casual register, oversized sections).
                # Only enforced during active pipeline — fail-open on errors.
                try:
                    if _is_pipeline_active() and file_path:
                        _pq_path = Path(file_path)
                        _pq_is_agent_or_command = (
                            _pq_path.suffix == ".md"
                            and ("/agents/" in file_path or "/commands/" in file_path)
                        )
                        if _pq_is_agent_or_command:
                            _pq_content = ""
                            if tool_name == "Write":
                                _pq_content = tool_input.get("content", "")
                            elif tool_name == "Edit":
                                # Read existing file, apply replacement in memory
                                try:
                                    _pq_existing = Path(file_path).read_text(encoding="utf-8")
                                    _pq_old = tool_input.get("old_string", "")
                                    _pq_new = tool_input.get("new_string", "")
                                    if _pq_old and _pq_old in _pq_existing:
                                        _pq_content = _pq_existing.replace(_pq_old, _pq_new, 1)
                                    else:
                                        _pq_content = _pq_existing  # Can't apply edit, check existing
                                except (OSError, UnicodeDecodeError):
                                    _pq_content = ""  # Can't read file, skip check

                            if _pq_content:
                                # Defensive import of prompt_quality_rules
                                _pq_violations = None
                                try:
                                    _pq_lib_dir = Path(__file__).resolve().parent.parent / "lib"
                                    _pq_mod_path = _pq_lib_dir / "prompt_quality_rules.py"
                                    if _pq_mod_path.exists():
                                        _pq_spec = importlib.util.spec_from_file_location(
                                            "prompt_quality_rules", str(_pq_mod_path)
                                        )
                                        if _pq_spec and _pq_spec.loader:
                                            _pq_mod = importlib.util.module_from_spec(_pq_spec)
                                            _pq_spec.loader.exec_module(_pq_mod)
                                            # Commands are coordinator prompts with extensive
                                            # step-by-step instructions — use a higher density
                                            # threshold than agent prompts (Issue #845 remediation)
                                            _pq_density_threshold = (
                                                150
                                                if "/commands/" in file_path
                                                else _pq_mod.CONSTRAINT_DENSITY_THRESHOLD
                                            )
                                            _pq_violations = (
                                                _pq_mod.check_persona(_pq_content)
                                                + _pq_mod.check_casual_register(_pq_content)
                                                + _pq_mod.check_constraint_density(
                                                    _pq_content,
                                                    threshold=_pq_density_threshold,
                                                )
                                            )
                                except Exception:
                                    _pq_violations = None  # Fail-open on import errors

                                if _pq_violations:
                                    _pq_fname = _pq_path.name
                                    _pq_summary = "; ".join(_pq_violations[:3])
                                    if len(_pq_violations) > 3:
                                        _pq_summary += f" ... and {len(_pq_violations) - 3} more"
                                    _pq_block_reason = (
                                        f"BLOCKED: Prompt quality violation in '{_pq_fname}' "
                                        f"(Issue #842). {_pq_summary} "
                                        f"REQUIRED NEXT ACTION: Fix the violations and retry. "
                                        f"Avoid banned persona openers ('You are an expert'), "
                                        f"casual register ('make sure', 'try to'), and "
                                        f"oversized constraint sections (>8 bullets). "
                                        f"Use formal directives (MUST, REQUIRED, FORBIDDEN)."
                                    )
                                    _log_pretool_activity(tool_name, tool_input, "deny", _pq_block_reason)
                                    output_decision(
                                        "deny", _pq_block_reason,
                                        system_message=(
                                            f"PROMPT QUALITY: '{_pq_fname}' has anti-pattern violations. "
                                            f"Fix and retry."
                                        ),
                                    )
                                    sys.exit(0)
                except Exception:
                    pass  # Fail-open: never block on prompt quality check errors

            # Bash command inspection: detect writes to protected paths (#502)
            if tool_name == "Bash":
                command = tool_input.get("command", "")
                if command:
                    # Issue #803: Cross-tool workaround detection.
                    # If a Write/Edit was recently denied, check if this Bash command
                    # targets the same path via heredoc, redirect, etc.
                    # Only check when pipeline is NOT active — during active pipeline,
                    # writes are legitimately allowed, so no workaround detection needed.
                    try:
                        _pipeline_active_803 = _is_pipeline_active()
                    except Exception:
                        _pipeline_active_803 = False
                    if not _pipeline_active_803:
                        try:
                            _write_targets_803 = _extract_bash_file_writes(command)
                            for _wt in _write_targets_803:
                                _wt_clean = _wt.strip().strip("'\"")
                                if not _wt_clean:
                                    continue
                                # Check full path match AND basename fallback
                                _wt_matched = _check_deny_cache(_wt_clean)
                                if not _wt_matched:
                                    # Basename fallback: Write may use absolute path,
                                    # Bash may use relative path or vice versa
                                    _wt_basename = Path(_wt_clean).name
                                    _wt_matched = _check_deny_cache(_wt_basename)
                                if _wt_matched:
                                    _xt_reason = (
                                        f"BLOCKED: Cross-tool workaround detected (Issue #803). "
                                        f"Write/Edit to '{_wt_clean}' was denied, and this Bash command "
                                        f"targets the same file. Infrastructure files require the "
                                        f"/implement pipeline. "
                                        f"REQUIRED NEXT ACTION: Run /implement to modify this file. "
                                        f"Do NOT use Bash heredoc/redirect as a workaround for denied writes."
                                    )
                                    _log_deviation(_wt_clean, tool_name, "cross_tool_workaround_block")
                                    _log_pretool_activity(tool_name, tool_input, "deny", _xt_reason)
                                    output_decision(
                                        "deny", _xt_reason,
                                        system_message="BLOCKED: Cross-tool workaround. Use /implement.",
                                    )
                                    sys.exit(0)
                        except Exception:
                            pass  # Fail-open: never block on detection errors

                    # Issue #803: Pipeline state file deletion guard.
                    # Block rm/unlink/truncate of pipeline state files during active pipeline.
                    # Issue #865: Allow cleanup when PIPELINE_CLEANUP_PHASE is set
                    # (STEP 15 / STEP B4 cleanup authorized by coordinator)
                    try:
                        _cleanup_phase = os.getenv("PIPELINE_CLEANUP_PHASE", "").lower()
                        _state_del = _check_bash_state_deletion(command)
                        if _state_del is not None and _cleanup_phase not in ("1", "true") and _is_pipeline_active():
                            _sd_reason = (
                                f"BLOCKED: {_state_del[1]} "
                                f"File: {_state_del[0]}. "
                                f"REQUIRED NEXT ACTION: Do NOT delete pipeline state files "
                                f"during an active /implement session."
                            )
                            _log_deviation(_state_del[0], tool_name, "state_file_deletion_block")
                            _log_pretool_activity(tool_name, tool_input, "deny", _sd_reason)
                            output_decision(
                                "deny", _sd_reason,
                                system_message="BLOCKED: Pipeline state file deletion during active pipeline.",
                            )
                            sys.exit(0)
                    except Exception:
                        pass  # Fail-open: never block on detection errors

                    # Issue #790: Spec test deletion scope guard.
                    # Block rm/unlink/mv of spec validation tests from other issues.
                    try:
                        _spec_targets = _extract_bash_spec_test_targets(command)
                        for _spec_path in _spec_targets:
                            _spec_block = _check_spec_test_deletion_scope(_spec_path)
                            if _spec_block is not None:
                                _log_deviation(_spec_block[0], tool_name, "spec_test_deletion_scope_block")
                                _log_pretool_activity(tool_name, tool_input, "deny", _spec_block[1])
                                output_decision(
                                    "deny", _spec_block[1],
                                    system_message="BLOCKED: Spec test deletion outside batch scope. Move to tests/archived/ instead.",
                                )
                                sys.exit(0)
                    except Exception:
                        pass  # Fail-open: never block on detection errors

                    bash_block = _check_bash_infra_writes(command)
                    if bash_block is not None:
                        _log_deviation(bash_block[0], tool_name, "bash_infrastructure_protection_block")
                        _log_pretool_activity(tool_name, tool_input, "deny", bash_block[1])
                        output_decision(
                            "deny", bash_block[1],
                            system_message="BLOCKED: Bash write to infrastructure file. Delegate to implementer agent.",
                        )
                        sys.exit(0)

                    # Issue #557, #606: Detect inline env var spoofing
                    spoof_reason = _detect_env_spoofing(command)
                    if spoof_reason is not None:
                        # Issue #606: Track escalation across attempts in same session
                        # Skip escalation tracking when session_id is unknown to
                        # prevent false escalation from unrelated invocations
                        session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
                        is_escalation = (
                            _track_spoofing_escalation(session_id)
                            if session_id != "unknown"
                            else False
                        )
                        if is_escalation:
                            spoof_reason += " [CIRCUMVENTION-ESCALATION]"
                        _log_deviation("env_spoofing", tool_name, "env_var_spoofing_block")
                        _log_pretool_activity(tool_name, tool_input, "deny", spoof_reason)
                        output_decision(
                            "deny", spoof_reason,
                            system_message="BLOCKED: Protected environment variable cannot be overridden.",
                        )
                        sys.exit(0)

                    # Issue #627: Block direct creation of gh issue marker file
                    marker_block = _detect_gh_issue_marker_creation(command)
                    if marker_block:
                        _log_deviation("gh_issue_marker", tool_name, "gh_issue_marker_creation_blocked")
                        _log_pretool_activity(tool_name, tool_input, "deny", marker_block)
                        output_decision(
                            "deny", marker_block,
                            system_message="BLOCKED: Use /create-issue to create GitHub issues.",
                        )
                        sys.exit(0)

                    # Issue #599: Block direct gh issue create outside approved contexts
                    gh_block = _detect_gh_issue_create(command)
                    if gh_block:
                        _log_deviation("gh_issue_create", tool_name, "gh_issue_create_blocked")
                        _log_pretool_activity(tool_name, tool_input, "deny", gh_block)
                        output_decision(
                            "deny", gh_block,
                            system_message="BLOCKED: Use /create-issue or /create-issue --quick.",
                        )
                        sys.exit(0)

                    # Issue #557: Block settings.json writes during active pipeline
                    try:
                        if _is_pipeline_active():
                            settings_block = _detect_settings_json_write(command)
                            if settings_block is not None:
                                _log_deviation("settings.json", tool_name, "settings_json_write_block")
                                _log_pretool_activity(tool_name, tool_input, "deny", settings_block)
                                output_decision(
                                    "deny", settings_block,
                                    system_message="BLOCKED: Settings write during pipeline. Complete /implement first.",
                                )
                                sys.exit(0)
                    except Exception:
                        pass  # Don't block on check failure

                    # Issue #712: Batch CIA completion gate
                    # Block git commit in batch worktrees when issues are missing CIA
                    if "git commit" in command or "git -c" in command and "commit" in command:
                        try:
                            cwd = os.getcwd()
                            if ".worktrees/batch-" in cwd:
                                if os.environ.get("SKIP_BATCH_CIA_GATE", "").strip().lower() not in ("1", "true", "yes"):
                                    _batch_cia_session_id = os.environ.get("CLAUDE_SESSION_ID", _session_id)
                                    _batch_cia_result = _check_batch_cia_completions(_batch_cia_session_id)
                                    if _batch_cia_result is not None:
                                        _log_pretool_activity(tool_name, tool_input, "deny", _batch_cia_result)
                                        output_decision(
                                            "deny", _batch_cia_result,
                                            system_message=(
                                                "BLOCKED: Batch CIA gate — some issues are missing "
                                                "continuous-improvement-analyst completion. "
                                                "Run CIA for all issues before committing."
                                            ),
                                        )
                                        sys.exit(0)
                        except Exception:
                            pass  # Fail-open: don't block on errors

                    # Issue #786: Batch doc-master completion gate
                    # Block git commit in batch worktrees when issues are missing doc-master
                    if "git commit" in command or "git -c" in command and "commit" in command:
                        try:
                            cwd = os.getcwd()
                            if ".worktrees/batch-" in cwd:
                                if os.environ.get("SKIP_BATCH_DOC_MASTER_GATE", "").strip().lower() not in ("1", "true", "yes"):
                                    _batch_dm_session_id = os.environ.get("CLAUDE_SESSION_ID", _session_id)
                                    _batch_dm_result = _check_batch_doc_master_completions(_batch_dm_session_id)
                                    if _batch_dm_result is not None:
                                        _log_pretool_activity(tool_name, tool_input, "deny", _batch_dm_result)
                                        output_decision(
                                            "deny", _batch_dm_result,
                                            system_message=(
                                                "BLOCKED: Batch doc-master gate — some issues are missing "
                                                "doc-master completion. "
                                                "Run doc-master for all issues before committing."
                                            ),
                                        )
                                        sys.exit(0)
                        except Exception:
                            pass  # Fail-open: don't block on errors

                    # Issue #802: Pipeline agent completeness gate
                    # Block git commit when required pipeline agents haven't completed
                    # Issue #853: In batch mode, check ALL issues rather than a single issue
                    if "git commit" in command or "git -c" in command and "commit" in command:
                        try:
                            if _is_pipeline_active():
                                # Issue #802: env var bypass + file-based bypass
                                # Env var works when set in harness; file works from Bash:
                                #   touch /tmp/skip_agent_completeness_gate
                                _skip_gate_file = Path("/tmp/skip_agent_completeness_gate")
                                _skip_gate_via_file = False
                                try:
                                    if _skip_gate_file.exists():
                                        try:
                                            _skip_gate_file.unlink()
                                        except OSError:
                                            pass  # Fail-open
                                        _skip_gate_via_file = True
                                except OSError:
                                    pass
                                # Issue #802 fix: Also check for inline env var in the command string
                                # Models naturally write "SKIP_AGENT_COMPLETENESS_GATE=1 git commit ..."
                                # but inline vars only affect the child process, not this hook's os.environ
                                # Security fix: Only match at START of command (not in commit messages)
                                _skip_gate_via_command = bool(re.match(r'(?i)SKIP_AGENT_COMPLETENESS_GATE=[1]', command.strip())) or bool(re.match(r'(?i)skip_agent_completeness_gate=true', command.strip()))
                                # Log bypass activations for audit trail
                                _skip_gate_via_env = os.environ.get("SKIP_AGENT_COMPLETENESS_GATE", "").strip().lower() in ("1", "true", "yes")
                                if _skip_gate_via_file:
                                    _log_pretool_activity(tool_name, tool_input, "allow", "bypass: file-based gate skip consumed")
                                if _skip_gate_via_command:
                                    _log_pretool_activity(tool_name, tool_input, "allow", "bypass: inline env var in command string")
                                if _skip_gate_via_env:
                                    _log_pretool_activity(tool_name, tool_input, "allow", "bypass: SKIP_AGENT_COMPLETENESS_GATE set in process environment")
                                if not _skip_gate_via_env and not _skip_gate_via_file and not _skip_gate_via_command:
                                    _agent_gate_session_id = os.environ.get("CLAUDE_SESSION_ID", _session_id)
                                    cwd = os.getcwd()
                                    if ".worktrees/batch-" in cwd:
                                        # Batch mode: check all issues in the state file
                                        try:
                                            hook_dir = Path(__file__).resolve().parent
                                            lib_candidates = [
                                                hook_dir.parent / "lib" / "pipeline_completion_state.py",
                                                hook_dir.parents[2] / "lib" / "pipeline_completion_state.py",
                                            ]
                                            _batch_agent_mod = None
                                            for lib_path in lib_candidates:
                                                if lib_path.exists():
                                                    spec = importlib.util.spec_from_file_location(
                                                        "pipeline_completion_state", str(lib_path)
                                                    )
                                                    if spec and spec.loader:
                                                        _batch_agent_mod = importlib.util.module_from_spec(spec)
                                                        spec.loader.exec_module(_batch_agent_mod)
                                                    break

                                            if _batch_agent_mod is not None and hasattr(_batch_agent_mod, "_read_state") and hasattr(_batch_agent_mod, "verify_pipeline_agent_completions"):
                                                _batch_agent_state = _batch_agent_mod._read_state(_agent_gate_session_id)
                                                _batch_agent_completions = _batch_agent_state.get("completions", {}) if _batch_agent_state else {}
                                                _batch_agent_pipeline_mode = os.environ.get("PIPELINE_MODE") or _get_pipeline_mode_from_state()
                                                _batch_agent_failures: list = []
                                                for _batch_agent_key in _batch_agent_completions:
                                                    if _batch_agent_key == "0":
                                                        continue  # skip non-batch issue 0
                                                    try:
                                                        _batch_agent_issue_num = int(_batch_agent_key)
                                                    except (ValueError, TypeError):
                                                        continue
                                                    _batch_agent_passed, _batch_agent_completed, _batch_agent_missing = _batch_agent_mod.verify_pipeline_agent_completions(
                                                        _agent_gate_session_id, _batch_agent_pipeline_mode, issue_number=_batch_agent_issue_num
                                                    )
                                                    if not _batch_agent_passed:
                                                        _batch_agent_failures.append(
                                                            f"#{_batch_agent_issue_num}: missing {', '.join(sorted(_batch_agent_missing))}"
                                                        )

                                                if _batch_agent_failures:
                                                    _batch_agent_result = (
                                                        f"BLOCKED: Batch agent completeness gate -- the following issues are missing "
                                                        f"required pipeline agents: {'; '.join(_batch_agent_failures)}. "
                                                        f"All required pipeline agents MUST complete for every issue before git commit. "
                                                        f"REQUIRED NEXT ACTION: Run the missing agents for the listed issues before committing. "
                                                        f"Set SKIP_AGENT_COMPLETENESS_GATE=1 to bypass, or run `touch /tmp/skip_agent_completeness_gate` as a SEPARATE command first, then retry the commit (Issue #853)"
                                                    )
                                                    _log_pretool_activity(tool_name, tool_input, "deny", _batch_agent_result)
                                                    output_decision(
                                                        "deny", _batch_agent_result,
                                                        system_message=(
                                                            "BLOCKED: Batch agent completeness gate -- required pipeline "
                                                            "agents have not completed for all batch issues. Run all required "
                                                            "agents before committing."
                                                        ),
                                                    )
                                                    sys.exit(0)
                                        except Exception:
                                            pass  # Fail-open: don't block on errors
                                    else:
                                        # Non-batch mode: single-issue check (existing behavior)
                                        _agent_gate_result = _check_pipeline_agent_completions(_agent_gate_session_id)
                                        if _agent_gate_result is not None:
                                            _log_pretool_activity(tool_name, tool_input, "deny", _agent_gate_result)
                                            output_decision(
                                                "deny", _agent_gate_result,
                                                system_message=(
                                                    "BLOCKED: Agent completeness gate -- required pipeline "
                                                    "agents have not completed. Run all required agents "
                                                    "before committing."
                                                ),
                                            )
                                            sys.exit(0)
                        except Exception:
                            pass  # Fail-open: don't block on errors

                    # Issue #754: Detect raw mlx_lm bypass in realign projects
                    try:
                        cwd = os.getcwd()
                        is_realign = (
                            Path(cwd, "src", "realign").is_dir()
                            or (Path(cwd, "pyproject.toml").exists()
                                and "realign" in Path(cwd, "pyproject.toml").read_text(errors="ignore"))
                        )
                        if is_realign:
                            rb_decision, rb_reason = _detect_realign_bypass(tool_name, tool_input)
                            if rb_decision == "deny":
                                _log_pretool_activity(tool_name, tool_input, "deny", rb_reason)
                                output_decision(
                                    "deny", rb_reason,
                                    system_message="BLOCKED: Use 'realign train' or 'realign generate' instead of raw mlx_lm.",
                                )
                                sys.exit(0)
                    except Exception:
                        pass  # Fail-open: don't block on project detection errors

            # Issue #528: Block coordinator code writes when /implement explicitly active
            # This is CRITICAL for external repo coverage — native tools bypass all
            # validation layers, so this check must be in the fast path.
            if tool_name in ("Write", "Edit", "Bash"):
                agent_name = _get_active_agent_name()
                impl_active = _is_explicit_implement_active()
                if (agent_name not in PIPELINE_AGENTS
                        and impl_active
                        and os.getenv("ENFORCEMENT_LEVEL", "block").strip().lower() != "off"):
                    if _is_code_file_target(tool_name, tool_input):
                        block_reason = (
                            "WORKFLOW ENFORCEMENT: /implement is active — code changes must be "
                            "made by pipeline agents (implementer, test-master, doc-master), "
                            "not the coordinator. Delegate this work to the appropriate agent. "
                            "REQUIRED NEXT ACTION: Invoke the appropriate agent (implementer, "
                            "test-master, or doc-master) via the Agent tool. "
                            "Do NOT write code directly."
                        )
                        _log_deviation(
                            tool_input.get("file_path", "bash_command")
                            if tool_name != "Bash" else "bash_command",
                            tool_name,
                            "explicit_implement_coordinator_block_native",
                        )
                        _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
                        output_decision(
                            "deny", block_reason,
                            system_message="WORKFLOW ENFORCEMENT: Delegate code changes to pipeline agents.",
                        )
                        sys.exit(0)

            # Issue #750: Block coordinator workaround edits after agent prompt-shrinkage denial
            # When validate_prompt_integrity denies an Agent call, the coordinator may
            # fall back to direct Write/Edit to protected infrastructure files.
            if tool_name in ("Write", "Edit"):
                _denied_agent = _check_agent_denial()
                if _denied_agent:
                    _deny750_path = tool_input.get("file_path", "")
                    if _is_protected_infrastructure(_deny750_path):
                        _deny750_is_substantive = False
                        if tool_name == "Edit":
                            _d750_old = tool_input.get("old_string", "")
                            _d750_new = tool_input.get("new_string", "")
                            _d750_sig, _, _ = _has_significant_additions(_d750_old, _d750_new, _deny750_path)
                            _deny750_is_substantive = _d750_sig
                        else:  # Write
                            _d750_content = tool_input.get("content", "")
                            _deny750_is_substantive = len(_d750_content.splitlines()) >= SIGNIFICANT_LINE_THRESHOLD
                        if _deny750_is_substantive:
                            _deny750_reason = (
                                f"BLOCKED: Agent '{_denied_agent}' was recently denied by prompt integrity. "
                                f"Direct edits to protected infrastructure ({_deny750_path}) are not allowed "
                                f"as a workaround. "
                                f"REQUIRED NEXT ACTION: Use get_agent_prompt_template('{_denied_agent}') "
                                f"to reload the full agent prompt from disk and retry the agent invocation. "
                                f"Do NOT attempt direct edits as a workaround."
                            )
                            _log_pretool_activity(tool_name, tool_input, "deny", _deny750_reason)
                            output_decision(
                                "deny", _deny750_reason,
                                system_message=(
                                    f"AGENT DENIAL WORKAROUND BLOCKED: Reload agent prompt and retry. "
                                    f"Do not edit infrastructure files directly."
                                ),
                            )
                            # Issue #803: Record denial for cross-tool workaround detection.
                            try:
                                _update_deny_cache(_deny750_path)
                            except Exception:
                                pass  # Never fail the hook for cache writes
                            sys.exit(0)

            # Layer 4: Pipeline ordering gate (Issues #625, #629, #632)
            # Only applies to Agent/Task tool calls during active pipeline.
            if tool_name in AGENT_TOOL_NAMES:
                ord_decision, ord_reason = validate_pipeline_ordering(tool_name, tool_input)
                if ord_decision == "deny":
                    _log_pretool_activity(tool_name, tool_input, "deny", ord_reason)
                    output_decision(
                        "deny", ord_reason,
                        system_message="ORDERING: Wait for prerequisite agents to complete.",
                    )
                    sys.exit(0)

            # Layer 5: Prompt integrity gate (Issue #695)
            # Blocks critical agents with sub-minimum prompts during pipeline.
            if tool_name in AGENT_TOOL_NAMES:
                pi_decision, pi_reason = validate_prompt_integrity(tool_name, tool_input)
                if pi_decision == "deny":
                    # Issue #750: Record denial so subsequent Write/Edit workarounds are blocked
                    _pi_agent_type = tool_input.get("subagent_type", "")
                    _record_agent_denial(_pi_agent_type)
                    _log_pretool_activity(tool_name, tool_input, "deny", pi_reason)
                    output_decision(
                        "deny", pi_reason,
                        system_message=(
                            "PROMPT INTEGRITY: Your prompt for this agent is too short. "
                            "Include the full implementer output, changed files list, and test results. "
                            "Re-read the agent source from disk if needed."
                        ),
                    )
                    sys.exit(0)

            # Run extensions even for native tools
            ext_decision, ext_reason = _run_extensions(tool_name, tool_input)
            if ext_decision == "deny":
                _log_pretool_activity(tool_name, tool_input, "deny", ext_reason)
                output_decision("deny", ext_reason, system_message=ext_reason)
                sys.exit(0)

            reason = f"Native tool '{tool_name}' - hook bypass (settings.json governs)"
            _log_pretool_activity(tool_name, tool_input, "allow", reason)
            output_decision("allow", reason)
            sys.exit(0)

        # =================================================================
        # PROJECT GUARD: Non-autonomous-dev projects skip enforcement.
        # Only non-native (MCP) tools reach this point. For projects
        # without autonomous-dev, these don't need pipeline enforcement.
        # Fail-closed: if repo_detector is unavailable, _is_adev_project()
        # returns True so enforcement continues rather than being silently
        # skipped. (Issue #662)
        # =================================================================
        if not _is_adev_project():
            reason = "Non-autonomous-dev project - enforcement skipped"
            _log_pretool_activity(tool_name, tool_input, "allow", reason)
            output_decision("allow", reason)
            sys.exit(0)

        # Plan-Exit Gate for MCP tools (Issue #926): enforce plan-critic
        # workflow on non-native tool calls (MCP servers). Uses explicit
        # read-only allowlist (no regex heuristics — AC #21).
        plan_exit_mcp_decision = _check_plan_exit_mcp(tool_name)
        if plan_exit_mcp_decision is not None:
            decision, reason = plan_exit_mcp_decision
            _log_pretool_activity(tool_name, tool_input, decision, reason)
            output_decision(decision, reason)
            sys.exit(0)

        # Run all validators in sequence (Layer 0 → Layer 1 → Layer 2 → Layer 3)
        validators_results = []

        # 0. Sandbox Layer (Layer 0) - Command classification & sandboxing
        decision, reason = validate_sandbox_layer(tool_name, tool_input)
        validators_results.append(("Sandbox", decision, reason))

        # 1. MCP Security Validator (Layer 1)
        decision, reason = validate_mcp_security(tool_name, tool_input)
        validators_results.append(("MCP Security", decision, reason))

        # 2. Agent Authorization (Layer 2)
        decision, reason = validate_agent_authorization(tool_name, tool_input)
        validators_results.append(("Agent Auth", decision, reason))

        # 3. Batch Permission Approver (Layer 3)
        decision, reason = validate_batch_permission(tool_name, tool_input)
        validators_results.append(("Batch Permission", decision, reason))

        # Layer 4: Hook extensions
        ext_decision, ext_reason = _run_extensions(tool_name, tool_input)
        if ext_decision == "deny":
            validators_results.append(("Extensions", "deny", ext_reason))

        # Combine all decisions
        final_decision, combined_reason = combine_decisions(validators_results)

        # Log the enforcement decision
        _log_pretool_activity(tool_name, tool_input, final_decision, combined_reason)

        # Output final decision
        output_decision(final_decision, combined_reason)

    except Exception as e:
        # Error in hook - ask user (don't block on hook errors)
        output_decision("ask", f"Hook error: {e}")

    # Always exit 0 - let Claude Code process the decision
    sys.exit(0)


if __name__ == "__main__":
    main()
