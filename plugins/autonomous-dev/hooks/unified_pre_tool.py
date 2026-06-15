#!/usr/bin/env python3
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
from typing import Any, Dict, Tuple, List, Optional

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

# Defensive import of tool_intent (Issue #971) — shell+tool classifier that
# delegates python -c parsing to python_write_detector. _extract_bash_file_writes
# is now a thin shim around tool_intent.write_targets when available.
# Falls back to legacy regex via _extract_bash_file_writes_legacy on import failure.
_tool_intent = None
try:
    _hook_path_ti = Path(__file__).resolve().parent
    _lib_candidates_ti = [
        _hook_path_ti.parent / "lib",           # plugins/autonomous-dev/lib
        _hook_path_ti.parents[2] / "lib",        # fallback
    ]
    for _lib_dir_ti in _lib_candidates_ti:
        _ti_path = _lib_dir_ti / "tool_intent.py"
        if _ti_path.exists():
            import importlib.util as _ilu_ti
            _spec_ti = _ilu_ti.spec_from_file_location("tool_intent", str(_ti_path))
            if _spec_ti and _spec_ti.loader:
                _tool_intent = importlib.util.module_from_spec(_spec_ti)
                _spec_ti.loader.exec_module(_tool_intent)
            break
except Exception:
    _tool_intent = None  # Fallback: _extract_bash_file_writes_legacy retains old behavior

# Defensive import of hook_recovery (Issue #970).
# Telemetry-only. If unavailable, log_block_with_recovery becomes a no-op so
# the hook gate continues to function unchanged.
try:
    _hook_path_hr = Path(__file__).resolve().parent
    _lib_candidates_hr = [
        _hook_path_hr.parent / "lib",           # plugins/autonomous-dev/lib
        _hook_path_hr.parents[2] / "lib",        # fallback
        Path.home() / ".claude" / "lib",        # user-global install
    ]
    _hr_loaded = False
    for _lib_dir_hr in _lib_candidates_hr:
        _hr_path = _lib_dir_hr / "hook_recovery.py"
        if _hr_path.exists():
            import importlib.util as _ilu_hr
            _spec_hr = _ilu_hr.spec_from_file_location("hook_recovery", str(_hr_path))
            if _spec_hr and _spec_hr.loader:
                _hook_recovery_mod = importlib.util.module_from_spec(_spec_hr)
                _spec_hr.loader.exec_module(_hook_recovery_mod)
                log_block_with_recovery = _hook_recovery_mod.log_block_with_recovery
                is_recovery_disabled = _hook_recovery_mod.is_recovery_disabled
                _hr_loaded = True
            break
    if not _hr_loaded:
        raise ImportError("hook_recovery.py not found in any candidate location")
except Exception:
    def log_block_with_recovery(**kwargs):  # type: ignore[no-redef]
        return None

    def is_recovery_disabled() -> bool:  # type: ignore[no-redef]
        return False

# Defensive import of hook_telemetry (Issue #972, #942-D capstone).
# Provides a decorator that emits a structured JSONL row on every "deny"
# decision flowing through ``output_decision``. Falls back to a no-op
# decorator if the library is unavailable so the hook continues to
# function unchanged.
try:
    _hook_path_ht = Path(__file__).resolve().parent
    _lib_candidates_ht = [
        _hook_path_ht.parent / "lib",           # plugins/autonomous-dev/lib
        _hook_path_ht.parents[2] / "lib",        # fallback
        Path.home() / ".claude" / "lib",        # user-global install
    ]
    _ht_loaded = False
    for _lib_dir_ht in _lib_candidates_ht:
        _ht_path = _lib_dir_ht / "hook_telemetry.py"
        if _ht_path.exists():
            import importlib.util as _ilu_ht
            _spec_ht = _ilu_ht.spec_from_file_location("hook_telemetry", str(_ht_path))
            if _spec_ht and _spec_ht.loader:
                _hook_telemetry_mod = importlib.util.module_from_spec(_spec_ht)
                _spec_ht.loader.exec_module(_hook_telemetry_mod)
                block_event_decorator = _hook_telemetry_mod.block_event_decorator
                log_block_event = _hook_telemetry_mod.log_block_event
                _ht_loaded = True
            break
    if not _ht_loaded:
        raise ImportError("hook_telemetry.py not found in any candidate location")
except Exception:
    def block_event_decorator(hook_name):  # type: ignore[no-redef]
        def _decorator(fn):
            return fn
        return _decorator

    def log_block_event(**kwargs):  # type: ignore[no-redef]
        return None

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

# Issue #1178: Prompt-integrity recovery telemetry — paired block + recovery
# events written to hook-blocks.jsonl via log_block_event. The classifier is
# inlined at the emission site (no helper); this constant only encodes the
# substring -> category mapping in priority order.
_PI_CATEGORY_MAP = (
    ("shrank", "shrinkage_pct_over_threshold"),
    ("slot", "slot_missing"),
    ("below baseline", "word_count_below_baseline"),
)
_PI_BLOCK_EVENT_TYPE = "prompt_integrity_block"
_PI_RECOVERY_EVENT_TYPE = "prompt_integrity_recovery"


# Phase 1 (Issue #1142): defensive import of edit_tier_classifier for the
# default-on Write/Edit gate. Replaces the old `.enforce` opt-in marker check
# and the line-count-only "significant additions" heuristic.
_classify_edit_tier_fn = None
_detect_bash_code_file_write_fn = None
# Phase 2 remediation (Issue #1154): helpers for upgrading the tier of a
# Bash fresh-file write by feeding the heredoc body through the AST
# classifier. Defensively bound — if absent (older lib/), the hook falls
# back to the previous line-count behavior.
_extract_heredoc_body_fn = None
_is_fresh_file_write_pattern_fn = None
try:
    _etc_path = Path(__file__).resolve().parent.parent / "lib" / "edit_tier_classifier.py"
    if _etc_path.exists():
        import importlib.util as _etc_ilu
        _etc_spec = _etc_ilu.spec_from_file_location("edit_tier_classifier", str(_etc_path))
        if _etc_spec and _etc_spec.loader:
            _etc_mod = importlib.util.module_from_spec(_etc_spec)
            _etc_spec.loader.exec_module(_etc_mod)
            _classify_edit_tier_fn = _etc_mod.classify_edit_tier
            _detect_bash_code_file_write_fn = _etc_mod.detect_bash_code_file_write
            _extract_heredoc_body_fn = getattr(
                _etc_mod, "extract_heredoc_body_for_redirect", None
            )
            _is_fresh_file_write_pattern_fn = getattr(
                _etc_mod, "is_fresh_file_write_pattern", None
            )
except Exception:
    # Fail-closed: if classifier is unavailable, the gate degrades to a
    # conservative "always full" decision via the local helper below.
    _classify_edit_tier_fn = None
    _detect_bash_code_file_write_fn = None
    _extract_heredoc_body_fn = None
    _is_fresh_file_write_pattern_fn = None


# Phase 2 (Issue #1153): defensive import of the shared heredoc-strip
# utility. Mirrors the pattern above. The shared module is used here at
# three call sites (formerly the private `_strip_heredoc_content` at the
# two sites that called it + the inline-duplicated regex inside the
# state-file deletion check). When the shared module fails to load we
# fall back to a no-op strip — preserving existing behavior with one
# minor false-positive risk that was already there before this refactor.
_strip_heredoc_fn = None
try:
    _heredoc_path = (
        Path(__file__).resolve().parent.parent / "lib" / "heredoc_utils.py"
    )
    if _heredoc_path.exists():
        import importlib.util as _heredoc_ilu
        _heredoc_spec = _heredoc_ilu.spec_from_file_location(
            "heredoc_utils", str(_heredoc_path)
        )
        if _heredoc_spec and _heredoc_spec.loader:
            _heredoc_mod = importlib.util.module_from_spec(_heredoc_spec)
            _heredoc_spec.loader.exec_module(_heredoc_mod)
            _strip_heredoc_fn = _heredoc_mod.strip_heredoc_content
except Exception:
    _strip_heredoc_fn = None


def _is_adev_project() -> bool:
    """Return True if the current working directory is an autonomous-dev repo.

    Wraps the dynamically-loaded repo_detector.is_autonomous_dev_repo.
    Falls back to True (fail-closed) when the module could not be loaded,
    so enforcement is never silently skipped on import failure.
    """
    if _is_adev_project_fn is None:
        return True
    return _is_adev_project_fn()


def _safe_classify_edit_tier(file_path: str, old_string: str, new_string: str) -> tuple:
    """Defensive wrapper around classify_edit_tier.

    Returns (tier, reason). On classifier unavailability or exception,
    fails CLOSED with ("full", "classifier_unavailable") so the gate
    routes the model to the full /implement pipeline (most conservative).
    """
    if _classify_edit_tier_fn is None:
        return ("full", "classifier_unavailable")
    try:
        return _classify_edit_tier_fn(file_path, old_string, new_string)
    except Exception:
        return ("full", "classifier_error")


# Phase 2 (Issue #1146): sliding-window helpers.
#
# Tier-2 threshold mirrored locally so the hook does not need to import the
# constant from the classifier module — easier wiring under the defensive-
# import scheme above. Kept in sync with
# ``edit_tier_classifier.py:TIER_LIGHT_LINE_THRESHOLD``.
_TIER_LIGHT_LINE_THRESHOLD_LOCAL = 20

# Defensive dynamic-load of the sliding-window ring-buffer API from
# ``pipeline_completion_state``. Module is already loaded elsewhere in this
# file, but we cannot guarantee the import has happened by the time the
# helpers are called. We resolve lazily on first call to dodge import-order
# issues with the existing late-import pattern in this file.
def _count_added_lines_for_sliding_window(old_string: str, new_string: str) -> int:
    """Compute lines-added for the sliding-window record.

    Mirrors the classifier's ``_count_added_lines`` but kept local to the
    hook so the sliding-window mechanism is self-contained — the classifier
    must remain a pure module with no state.
    """
    old_lines = len(old_string.splitlines()) if old_string else 0
    new_lines = len(new_string.splitlines()) if new_string else 0
    return max(0, new_lines - old_lines)


# #1166: module-level cache so we resolve the ring-buffer API exactly
# once per process. Previously every Write/Edit/Bash classification ran
# the full importlib lookup, which was measurable in tight gate loops.
# Module is shared with the cache helpers below — module-private by
# convention, not enforcement.
_PCS_MODULE_CACHE = None  # type: ignore[var-annotated]
_PCS_API_CACHE: Tuple = (None, None, None)
_PCS_RESOLVED = False


def _load_tier1_ring_buffer_api():
    """Lazy resolve the ring-buffer API from ``pipeline_completion_state``.

    Returns a 3-tuple ``(record, get, clear)`` of callables, or ``(None,
    None, None)`` when the module is not importable. Callers MUST treat
    a ``None`` triple as "skip the sliding-window check" — failures here
    never worsen the gate behavior.

    The triple is cached at module level after the first successful OR
    failed resolution (#1166). Subsequent calls return the cached value
    without re-importing. The failure path also sets the sentinel so we
    do not pay the importlib cost every gate invocation when the module
    is genuinely unavailable.
    """
    global _PCS_MODULE_CACHE, _PCS_API_CACHE, _PCS_RESOLVED
    if _PCS_RESOLVED:
        return _PCS_API_CACHE
    try:
        import pipeline_completion_state as _pcs  # type: ignore[import-not-found]
        _PCS_MODULE_CACHE = _pcs
        _PCS_API_CACHE = (
            getattr(_pcs, "record_tier1_allow", None),
            getattr(_pcs, "get_recent_tier1_allows", None),
            getattr(_pcs, "clear_tier1_ring_buffer", None),
        )
    except Exception:
        _PCS_API_CACHE = (None, None, None)
    finally:
        # Set even on the failure path so subsequent calls skip the
        # import attempt — the gate must not re-pay importlib cost on
        # every classification when the module is missing.
        _PCS_RESOLVED = True
    return _PCS_API_CACHE


def _record_tier1_allow(session_id: str, file_path: str, lines_added: int) -> None:
    """Record a Tier-1 (fix-tier) classifier decision into the ring buffer."""
    rec, _, _ = _load_tier1_ring_buffer_api()
    if rec is None:
        return
    try:
        rec(session_id, file_path, lines_added)
    except Exception:
        pass


def _get_recent_tier1_allows(
    session_id: str, file_path: str, *, window_seconds: int = 60
) -> list:
    """Return the recent Tier-1 ring-buffer entries for ``(session_id, file_path)``."""
    _, get, _ = _load_tier1_ring_buffer_api()
    if get is None:
        return []
    try:
        return get(session_id, file_path, window_seconds=window_seconds)
    except Exception:
        return []


def _clear_tier1_ring_buffer(session_id: str, file_path: str) -> None:
    """Drop the ring buffer for ``(session_id, file_path)`` after escalation."""
    _, _, clr = _load_tier1_ring_buffer_api()
    if clr is None:
        return
    try:
        clr(session_id, file_path)
    except Exception:
        pass


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

# Issue #953: Hook safety helpers — graceful failure on missing deps and
# slash-command precondition checks. Wrapped in try/except so the hook still
# loads (with no-op fallbacks) if hook_safety is unavailable.
try:
    from hook_safety import command_registered as _hook_command_registered
    from hook_safety import safe_main as _hook_safe_main
except ImportError:
    def _hook_command_registered(_name: str) -> bool:  # fail-CLOSED stub
        return True

    def _hook_safe_main(fn):  # no-op stub: preserves int return semantics
        result = fn()
        if isinstance(result, int):
            sys.exit(result)
        sys.exit(0)


# Issue #1206: per-repo sentinel path. Import from lib.pipeline_state so the
# hook subprocess resolves the same sentinel path the coordinator session uses
# (subject to CWD inheritance — see tests/integration/test_hook_pwd_inheritance.py).
try:
    from pipeline_state import get_legacy_sentinel_path  # type: ignore
except ImportError:
    def get_legacy_sentinel_path(repo_root=None):  # type: ignore
        # Fallback: behave like the pre-#1206 hardcoded path so hooks still
        # function in degraded environments where lib/ is not on sys.path.
        return Path("/tmp/implement_pipeline_state.json")


# Issue #1206: state-file write-protection tuple. Both the legacy machine-global
# literal AND the new per-repo path must be protected:
# - The legacy literal (``/tmp/implement_pipeline_state.json``) is retained so
#   that orphaned sentinel files from pre-#1206 sessions still receive
#   write-protection during the transition window.
# - The new per-repo path is added so the current sentinel is protected at its
#   actual location.
LEGACY_SENTINEL_LITERALS: tuple = (
    "/tmp/implement_pipeline_state.json",  # legacy orphan: pre-#1206 sessions
    str(get_legacy_sentinel_path()),        # new per-repo: current sentinel
)


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

# Command context file for issue-creating commands (Issue #630).
# Issue #1203: support env-var override (GH_ISSUE_CMD_CONTEXT_PATH) so subprocess
# runtime tests can isolate the path without writing the real /tmp file. Mirrors
# the PIPELINE_STATE_FILE precedent (see line ~1758).
GH_ISSUE_COMMAND_CONTEXT_PATH = os.getenv(
    "GH_ISSUE_CMD_CONTEXT_PATH",
    "/tmp/autonomous_dev_cmd_context.json",
)

# Commands that are authorized to create GitHub issues (Issue #630).
# Issue #1203: 'plan' added — plan.md STEP 6 files issues by design per its own
# HARD GATE (>=2 independent work items). Whitelisting here is the minimal fix
# vs rerouting plan.md to use a different mechanism.
GH_ISSUE_COMMANDS = {'create-issue', 'plan-to-issues', 'improve', 'refactor', 'retrospective', 'plan'}

# Environment variables protected from inline spoofing in Bash commands (Issue #557)
# Non-prefix vars that don't start with CLAUDE_ are listed individually
PROTECTED_ENV_VARS = {
    'PIPELINE_STATE_FILE', 'ENFORCEMENT_LEVEL', 'AUTONOMOUS_DEV_COMMAND',
    'INTENT_CLASSIFIER_ENFORCE',
}

# Prefix-based protection: any env var starting with these prefixes is protected (Issue #606)
PROTECTED_ENV_PREFIXES: "tuple[str, ...]" = ('CLAUDE_',)

# Issue #1137: CLAUDE_SESSION_ID is non-privileged framework correlation metadata
# (Claude Code-generated UUID, NOT an authentication token). Legitimate tooling
# (baseline failure capture, activity-log scoping, nested subshell propagation per
# Issue #904) needs to export it. The compensating control against log-attribution
# spoofing is _SAFE_SESSION_ID_RE sanitization in unified_prompt_validator.py
# (around lines 554-558, Issue #1024).
# REVOCATION CONDITION: remove from this exceptions set if CLAUDE_SESSION_ID
# ever gains authentication, authorization, or other privilege-bearing semantics.
PROTECTED_ENV_PREFIX_EXCEPTIONS: "frozenset[str]" = frozenset({"CLAUDE_SESSION_ID"})

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

# Per-file protected entries (Issue #980) — relative paths from autonomous-dev
# repo root. Matched via endswith against normalized absolute paths.
PROTECTED_INFRA_FILES = {
    "plugins/autonomous-dev/config/install_manifest.json",
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
    # Don't let the walk-up reach the user's home directory: the global
    # autonomous-dev install at ~/.claude/commands/implement.md is meant for
    # the user's tooling, not to mark every project under ~ as autonomous-dev.
    try:
        home = Path.home().resolve()
    except (OSError, ValueError):
        home = None
    # Walk up at most 10 levels to find repo root
    for _ in range(10):
        if home is not None and current == home:
            break
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
    # Per-file protection (Issue #980): explicit file allowlist with strict
    # suffix matching — prevents partial-basename false positives.
    for protected_file in PROTECTED_INFRA_FILES:
        # Match both absolute paths ending with the suffix AND a bare relative path.
        # endswith with leading "/" prevents partial-basename false positives
        # (e.g., "foo_install_manifest.json" must not match).
        if normalized.endswith("/" + protected_file) or normalized == protected_file:
            return True
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
    # #1171: sanitize untrusted env-var input before equality compare.
    current_sid = _resolve_session_id_safe(_session_id) or "unknown"

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
           (``<repo>/.claude/local/implement_pipeline_state.json`` since
           Issue #1206; was ``/tmp/implement_pipeline_state.json``)
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
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
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
    Issue #849: PIPELINE_MODE env-var takes precedence at all call-sites.
    Issue #1173: mtime-TTL fallback closes the indeterminate-session gap where
    stale fix-mode state would leak into a fresh --light run.

    Returns:
        Pipeline mode string, defaulting to "full".
    """
    # Issue #849/#1173: env-var takes precedence (eliminates call-site asymmetry
    # where line 1108 honors PIPELINE_MODE but other call-sites went through this
    # function and silently ignored it).
    env_mode = os.getenv("PIPELINE_MODE", "").strip()
    if env_mode:
        return env_mode

    pipeline_state_file = os.getenv("PIPELINE_STATE_FILE", str(get_legacy_sentinel_path()))
    try:
        state_path = Path(pipeline_state_file)
        if state_path.exists():
            import json as _json

            with open(state_path) as f:
                state = _json.load(f)
            # Session staleness check (Issue #862)
            if _is_stale_session(state, state_path):
                return "full"  # Stale session — safe default
            # Issue #1173: mtime-TTL fallback. When session_id is indeterminate
            # (e.g. 'unknown'), _is_stale_session() returns False and stale mode
            # would otherwise leak. Treat state older than the TTL as expired
            # regardless of session identity.
            import time as _time
            mtime = state_path.stat().st_mtime
            if _time.time() - mtime >= _PIPELINE_STATE_TTL_SECONDS:
                return "full"
            return state.get("mode", "full")
    except Exception:
        pass
    return "full"


_SELF_MAINT_CACHE: "dict[str, bool]" = {}


def _is_self_maintenance_mode() -> bool:
    """Detect if we are operating inside the canonical autonomous-dev source.

    Returns True iff a parent of the current working directory (up to 30
    levels) contains ``plugins/autonomous-dev/.claude-plugin/marketplace.json``
    — the canonical-source marker. This identifies the autonomous-dev repo
    itself (where maintainers edit the framework) versus any consumer repo
    where the plugin is installed via ``.claude/``.

    Used to relax gates whose enforcement intent is "consumer protections"
    rather than "framework correctness". The test gate, security audit,
    doc-master verdict, and prompt-integrity baselines remain enforced —
    they are dogfooding requirements. Only the gates that exist to keep
    consumer-repo maintainers from accidentally editing installed framework
    files relax here, because in autonomous-dev itself those files ARE the
    work product.

    Result is cached per-cwd within this process (the cwd rarely changes
    mid-hook-invocation and the walk is cheap, but the cache keeps it from
    showing up in flamegraphs).

    Returns:
        True if cwd is inside the canonical autonomous-dev source tree.
    """
    try:
        key = str(Path.cwd().resolve())
    except (OSError, RuntimeError):
        return False
    cached = _SELF_MAINT_CACHE.get(key)
    if cached is not None:
        return cached

    marker = Path("plugins") / "autonomous-dev" / ".claude-plugin" / "marketplace.json"
    try:
        current = Path(key)
        for _ in range(30):
            if (current / marker).exists():
                _SELF_MAINT_CACHE[key] = True
                return True
            parent = current.parent
            if parent == current:
                break
            current = parent
    except (OSError, RuntimeError):
        pass

    _SELF_MAINT_CACHE[key] = False
    return False


def _is_settings_template_path(file_path: str) -> bool:
    """Return True iff file_path is a plugin-source settings template path.

    Used to short-circuit the Issue #557 settings guard for template files under
    plugins/*/templates/ — these are work products (template source), not the
    runtime settings files the guard is designed to protect. Issue #1001.

    Tightened after security-auditor MEDIUM (A01 Broken Access Control):
    the helper previously matched any path with a ``templates`` component,
    which would also bypass the guard for runtime paths like
    ``.claude/templates/settings.local.json``. The check now requires
    ``"plugins"`` to appear as a path component BEFORE ``"templates"`` in
    the resolved parts tuple, scoping the bypass to genuine plugin
    template-source paths only.

    Args:
        file_path: The path string from tool_input["file_path"].

    Returns:
        True if the resolved path has a ``templates`` component preceded
        somewhere by a ``plugins`` component. False on empty input,
        resolution error, missing ``templates`` component, or
        ``templates`` not preceded by ``plugins``.
    """
    if not file_path:
        return False
    try:
        parts = Path(file_path).resolve().parts
        if "templates" not in parts:
            return False
        templates_idx = parts.index("templates")
        return "plugins" in parts[:templates_idx]
    except (OSError, RuntimeError, ValueError):
        return False


def _is_plugin_source_path(file_path: str) -> bool:
    """Return True iff file_path resolves under a real autonomous-dev source tree.

    Used by the Issue #557 settings-write guard self-maintenance branch
    (Issue #1111) to detect writes that target the canonical
    autonomous-dev plugin source tree. The previous substring check
    (``"plugins/autonomous-dev/" in str(file_path)``) would also match
    unrelated paths like ``/tmp/plugins/autonomous-dev/...`` (security-
    auditor LOW, A01).

    The tightened check has TWO requirements (both must hold):

    1. ``"plugins"`` and ``"autonomous-dev"`` appear as ADJACENT
       components (in that order) in the resolved path parts.
    2. An ancestor of that ``plugins/autonomous-dev/`` directory contains
       the canonical marker
       ``plugins/autonomous-dev/.claude-plugin/marketplace.json`` — i.e.
       the path actually lives inside a real autonomous-dev source tree,
       not a look-alike directory layout under ``/tmp`` or similar.

    Args:
        file_path: The path string from tool_input["file_path"].

    Returns:
        True iff both conditions above hold. False on empty input,
        resolution error, missing adjacency, or no canonical marker.
    """
    if not file_path:
        return False
    try:
        parts = Path(file_path).resolve().parts
        adj_idx: int | None = None
        for i, p in enumerate(parts):
            if p == "plugins" and i + 1 < len(parts) and parts[i + 1] == "autonomous-dev":
                adj_idx = i
                break
        if adj_idx is None:
            return False
        # Verify a real autonomous-dev source tree by checking for the
        # canonical marker file at the ancestor that owns the
        # plugins/autonomous-dev/ directory.
        repo_root = Path(*parts[:adj_idx]) if adj_idx > 0 else Path(parts[0])
        marker = repo_root / "plugins" / "autonomous-dev" / ".claude-plugin" / "marketplace.json"
        return marker.exists()
    except (OSError, RuntimeError):
        return False


def _is_batch_context(cwd: str) -> bool:
    """Return True when the current invocation is part of a batch.

    Issue #1133: Batch context can be signaled two ways:

    1. **Worktree mode** (the original): the current working directory is
       inside a ``.worktrees/batch-*`` directory. This is the default for
       ``/implement --batch`` and ``/implement --issues`` in repos where
       ``.claude/*`` is NOT gitignored.
    2. **In-place mode** (no-worktree, Issue #1133): the environment
       variable ``BATCH_NO_WORKTREE`` is set to ``1`` / ``true`` / ``yes``.
       This mirrors the ``BATCH_AUTO_APPROVE`` precedent (Issue #323) for
       repos like autonomous-dev where ``.claude/`` is gitignored.

    Centralizing the check ensures all three batch-context gates (CIA
    completion, doc-master completion, agent completeness) fire
    consistently regardless of which batch mode is active.

    Args:
        cwd: Current working directory string.

    Returns:
        True if either signal indicates batch context.
    """
    if ".worktrees/batch-" in cwd:
        return True
    return os.environ.get("BATCH_NO_WORKTREE", "").strip().lower() in ("1", "true", "yes")


# Issue #1173 — 30-min TTL for pipeline state staleness. Used by
# _is_pipeline_active() (mtime liveness check) and _get_pipeline_mode_from_state()
# (mtime-based fallback when session-id is indeterminate).
_PIPELINE_STATE_TTL_SECONDS = 1800


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
        # Issue #941: refresh mtime ONLY when this session OWNS the state file.
        # Previously this was unconditional (Issue #636) which let concurrent
        # sessions inadvertently keep a foreign session's stale state alive.
        # Preserves #636: the owning session keeps its own mtime fresh.
        # Fixes #941: a parallel pipeline run does not refresh another
        # session's sentinel.
        pipeline_state_file = os.getenv(
            "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
        )
        try:
            current_sid = os.environ.get("CLAUDE_SESSION_ID", "")
            should_touch = True  # default: preserve #636 if we cannot read state
            state_path = Path(pipeline_state_file)
            if state_path.exists():
                try:
                    import json as _json_touch
                    with open(state_path) as _fh_touch:
                        _state_for_touch = _json_touch.load(_fh_touch)
                    state_sid = _state_for_touch.get("session_id", "") if isinstance(_state_for_touch, dict) else ""
                    if state_sid and current_sid and state_sid != current_sid:
                        should_touch = False  # foreign-owned: do not refresh
                except (OSError, ValueError, json.JSONDecodeError):
                    pass  # Unreadable/corrupt: fall back to touch (preserves #636)
            if should_touch:
                Path(pipeline_state_file).touch()
        except OSError:
            pass
        return True

    # Check pipeline state file
    pipeline_state_file = os.getenv("PIPELINE_STATE_FILE", str(get_legacy_sentinel_path()))
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
                    # #1171: sanitize untrusted env-var before HMAC verify.
                    sid = _resolve_session_id_safe(_session_id) or "unknown"
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
            if age_seconds < _PIPELINE_STATE_TTL_SECONDS:  # 30 minutes since last agent activity
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
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
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
                # #1171: sanitize untrusted env-var before HMAC verify.
                sid = _resolve_session_id_safe(_session_id) or "unknown"
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
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
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
                # #1171: sanitize untrusted env-var before HMAC verify.
                sid = _resolve_session_id_safe(_session_id) or "unknown"
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


def _check_write_pipeline_required(
    tool_name: str,
    file_path: str,
    old_string: str,
    new_string: str,
    *,
    session_id: "Optional[str]" = None,
) -> "tuple[bool, str, str]":
    """Decide if a Write/Edit on production code requires the /implement pipeline.

    Args:
        tool_name: The tool name ("Write" or "Edit").
        file_path: The target file path.
        old_string: The pre-edit content (empty string for new-file Write).
        new_string: The post-edit content.
        session_id: Optional pipeline session id used by the Phase 2
            sliding-window check. When provided, ``fix`` tier blocks are
            recorded into the per-session ring buffer; when the rolling
            cumulative-lines-added across the last 60 s window for the
            same ``(session_id, file_path)`` crosses
            ``TIER_LIGHT_LINE_THRESHOLD`` the returned tier label is
            escalated from ``fix`` to ``light`` with reason marker
            ``cumulative_sliding_window``. When ``None`` the sliding
            window is skipped — preserving the Phase 1 contract for
            callers that have not been updated yet (#1146).

    Returns:
        (block, tier_label, directive)
        - block: True means caller MUST emit a deny decision.
        - tier_label: one of "pipeline_active", "operator_bypass", "no_path",
          "tier0_non_code", "tier0_test_file", "fix", "light", "full",
          "wpg_check_error".
        - directive: human-readable REQUIRED NEXT ACTION (empty when block False).

    Phase 1 (Issue #1142+): default-on. The previous opt-IN check via
    `.claude/.enforce` was removed; per-repo opt-OUT is now via the existing
    `.claude/.bypass` marker (already short-circuited at line ~4532). The old
    line-count heuristic is replaced by `classify_edit_tier()` which returns
    one of three tiers — `fix` / `light` / `full` — each mapped to the
    matching `/implement` variant in the directive.

    Phase 2 (Issue #1146): sliding-window escalation for emergent bypass via
    tool-call granularity mismatch. See ``session_id`` arg above.
    """
    # Tier 0b: pipeline already active — already in-flow, allow
    try:
        if _is_pipeline_active():
            return (False, "pipeline_active", "")
    except Exception:
        pass  # fall through; if we cannot tell, continue with other checks

    # Tier 0c: one-shot operator bypass (mirrors /tmp/skip_agent_completeness_gate pattern)
    skip_file = Path("/tmp/skip_write_pipeline_gate")
    try:
        if skip_file.exists():
            try:
                skip_file.unlink()
            except OSError:
                pass  # fail-open on unlink — bypass still consumed
            return (False, "operator_bypass", "")
    except OSError:
        pass

    # Tier 0d: no path provided
    if not file_path:
        return (False, "no_path", "")

    # Tier 0e: non-code extension — not applicable
    suffix = Path(file_path).suffix.lower()
    if suffix not in CODE_EXTENSIONS:
        return (False, "tier0_non_code", "")

    # Tier 0f: test file — excluded (reuse pattern from _is_protected_infrastructure)
    fp_lower = file_path.lower()
    if "/tests/" in fp_lower or "/test/" in fp_lower:
        return (False, "tier0_test_file", "")
    basename = Path(file_path).name
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return (False, "tier0_test_file", "")

    # Tier 0g: ephemeral / scratch paths — excluded. Files at these
    # absolute locations are never committed (covered by .gitignore +
    # repo discipline) and never user-facing, so the /implement pipeline
    # review adds no value but charges a UX tax every time the agent
    # needs a one-off helper script or scratch file. Restricted to
    # ABSOLUTE prefixes so a literal ``/tmp/foo.sh`` is exempt but
    # ``./tmp/foo.sh`` inside a project named ``tmp`` is NOT.
    #
    # NOTE: this is orthogonal to the security guard in
    # :func:`_is_plugin_source_path` (which prevents an attacker
    # placing a look-alike ``/tmp/plugins/autonomous-dev/...`` tree to
    # be trusted as a plugin source). Pipeline gating is about review
    # discipline, not trust elevation; the two concerns don't overlap.
    try:
        resolved = str(Path(file_path).expanduser())
    except Exception:
        resolved = file_path
    EPHEMERAL_PREFIXES = (
        "/tmp/",
        "/private/tmp/",      # macOS canonicalises /tmp -> /private/tmp
        "/var/folders/",      # macOS pytest tmp_path / mkdtemp default
        str(Path.home() / "tmp") + "/",
        str(Path.home() / ".cache") + "/",
    )
    if any(resolved.startswith(p) for p in EPHEMERAL_PREFIXES):
        return (False, "tier0_ephemeral_path", "")

    # Tier classification via AST-based classifier (Phase 1, #1142+).
    tier, reason = _safe_classify_edit_tier(file_path, old_string or "", new_string or "")

    # Phase 2 (Issue #1146): sliding-window cumulative escalation.
    # When the classifier returns ``fix`` (Tier-1) AND a session_id is
    # available, query the per-(session, file) ring buffer. If the rolling
    # sum of lines-added in the last 60 s plus this edit's added lines
    # crosses the Tier-2 threshold (20), ESCALATE the returned tier label
    # from ``fix`` to ``light`` and tag the reason. The ring buffer is
    # then dropped so a single threshold trigger does not keep firing on
    # subsequent edits.
    #
    # On allow paths (``fix`` not escalated): record this edit's added
    # lines so the NEXT call sees the cumulative.
    escalated_by_sliding_window = False
    if tier == "fix" and session_id:
        try:
            new_lines = _count_added_lines_for_sliding_window(old_string or "", new_string or "")
            existing = _get_recent_tier1_allows(session_id, file_path, window_seconds=60)
            existing_sum = sum(int(e.get("lines", 0)) for e in existing)
            if existing_sum + new_lines >= _TIER_LIGHT_LINE_THRESHOLD_LOCAL:
                tier = "light"
                reason = (
                    f"cumulative_sliding_window: existing_sum={existing_sum} "
                    f"new={new_lines} >= threshold={_TIER_LIGHT_LINE_THRESHOLD_LOCAL}"
                )
                escalated_by_sliding_window = True
                # Reset so the deny does not keep firing on subsequent edits.
                _clear_tier1_ring_buffer(session_id, file_path)
            else:
                _record_tier1_allow(session_id, file_path, new_lines)
        except Exception:
            # Sliding-window check failures must NEVER worsen the gate.
            pass

    # Map tier -> /implement variant (the 3-door menu).
    file_name = Path(file_path).name
    if tier == "fix":
        flag = "--fix "
    elif tier == "light":
        flag = "--light "
    else:
        # full (or unknown fallback) -> bare /implement
        tier = "full" if tier not in ("fix", "light", "full") else tier
        flag = ""
    directive = (
        f"Run /implement {flag}\"<brief description of change to {file_name}>\". "
        f"Per-repo opt-out: touch .claude/.bypass && git commit. "
        f"Operator one-shot bypass: touch /tmp/skip_write_pipeline_gate."
    )
    if escalated_by_sliding_window:
        directive = (
            f"cumulative_sliding_window: {reason}. " + directive
        )
    return (True, tier, directive)


def _check_bash_code_file_pipeline_required(
    command: str,
    *,
    session_id: "Optional[str]" = None,
) -> "tuple[bool, str, str, str]":
    """Decide if a Bash command writing to a code file requires /implement.

    Mirrors `_check_write_pipeline_required` for the Bash tool path. Detects
    cat >, sed -i, tee, heredocs, python -c open(), awk redirects, etc.,
    targeting code files (CODE_EXTENSIONS).

    Args:
        command: The raw Bash command string.
        session_id: Optional pipeline session id used by the Phase 2
            sliding-window check. When provided and the detected tier is
            ``fix``-equivalent (the classifier's safe default for empty
            old/new is ``light``, so this rarely fires through this path —
            see ``_check_write_pipeline_required`` for the primary site).

    Returns:
        (block, tier_label, directive, target_path)
        - target_path: the detected code-file path (empty when no match).
        Block is False when the command does not target a code file, the
        command is excluded user-patch tooling (`git apply`, `patch < diff`),
        or the pipeline is already active / operator bypass is set.

    Phase 1 (Issue #1142+).
    Phase 2 (Issue #1146): ``session_id`` arg for sliding-window symmetry.
    """
    if not command:
        return (False, "no_command", "", "")

    # Pipeline active — allow (the model is in-flow).
    try:
        if _is_pipeline_active():
            return (False, "pipeline_active", "", "")
    except Exception:
        pass

    # One-shot operator bypass.
    skip_file = Path("/tmp/skip_write_pipeline_gate")
    try:
        if skip_file.exists():
            try:
                skip_file.unlink()
            except OSError:
                pass
            return (False, "operator_bypass", "", "")
    except OSError:
        pass

    # Detect the code-file write target.
    if _detect_bash_code_file_write_fn is None:
        return (False, "detector_unavailable", "", "")
    try:
        target, pattern = _detect_bash_code_file_write_fn(command)
    except Exception:
        return (False, "detector_error", "", "")

    if not target:
        return (False, "no_code_target", "", "")

    # Test files: pass.
    target_lower = target.lower()
    if "/tests/" in target_lower or "/test/" in target_lower:
        return (False, "tier0_test_file", "", target)
    basename = Path(target).name
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return (False, "tier0_test_file", "", target)

    # Classify — for in-place edits like sed -i we cannot see the patch,
    # so we pass empty old/new and let the classifier return its safe
    # default (`light` for non-Python, classifier behavior for .py).
    #
    # Phase 2 remediation (Issue #1154): for fresh-file write patterns
    # (cat redirect, heredoc redirect, etc.) we additionally try to extract
    # the heredoc body and run the AST classifier against it. The body IS
    # the new file's content, so a `class X: pass` body correctly upgrades
    # to ``tier=full`` (new class) — matching the spec for the chained
    # heredoc form `OUT=foo.py; cat > "$OUT" << EOF\nclass X: pass\nEOF`.
    #
    # Constraints honored:
    # - The detector (``detect_bash_code_file_write``) already strips heredoc
    #   bodies before scanning patterns 1/2/3/6/7/8 (Issue #1153), so this
    #   re-classify ONLY fires AFTER a code-file target has been detected
    #   from the SHELL syntax (not the body). AC2 is preserved: a
    #   `gh issue create --body-file - <<HD ... HD` payload returns
    #   ``target=""`` from the detector and never reaches this branch.
    # - On any extraction or classification error we silently fall back to
    #   the original (empty-old, empty-new) tier — same as pre-remediation.
    tier, _reason = _safe_classify_edit_tier(target, "", "")
    body_classified = False
    if (
        _extract_heredoc_body_fn is not None
        and _is_fresh_file_write_pattern_fn is not None
        and _is_fresh_file_write_pattern_fn(pattern)
    ):
        try:
            body = _extract_heredoc_body_fn(command)
        except Exception:
            body = ""
        if body:
            body_tier, _body_reason = _safe_classify_edit_tier(target, "", body)
            # Only ELEVATE the tier — never weaken. fix < light < full.
            _ranks = {"fix": 0, "light": 1, "full": 2}
            if _ranks.get(body_tier, 0) > _ranks.get(tier, 0):
                tier = body_tier
                body_classified = True
    # For Bash patterns we conservatively floor at `light` — a one-shot
    # `sed -i X.py` or `cat > X.py` is not a "fix-tier" edit. Body-classified
    # decisions are already >= light (we only elevate), so this floor is a
    # no-op for them; the explicit check keeps the invariant readable.
    if tier == "fix":
        tier = "light"
    # body_classified is captured for future telemetry / debug-log integration
    # (Phase 3 — Issue #1155). Not yet wired into the directive text.
    _ = body_classified

    if tier == "light":
        flag = "--light "
    elif tier == "full":
        flag = ""
    else:
        flag = "--light "
        tier = "light"
    directive = (
        f"Run /implement {flag}\"<brief description of change to {basename}>\" "
        f"instead of Bash-writing to code files (pattern: {pattern}). "
        f"Per-repo opt-out: touch .claude/.bypass && git commit. "
        f"Operator one-shot bypass: touch /tmp/skip_write_pipeline_gate."
    )
    return (True, tier, directive, target)


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

    Thin wrapper around the shared ``heredoc_utils.strip_heredoc_content``
    helper. Kept under the original private name so existing internal call
    sites (``_detect_env_spoofing`` and ``_detect_gh_issue_create``) do not
    need to be touched as part of the Phase 2 extraction.

    Args:
        command: The raw Bash command string.

    Returns:
        Command with heredoc body content replaced by empty strings. Falls
        back to the input unchanged when the shared module failed to load
        (no-op strip) to preserve the existing scan behavior.

    Issue: #1153
    """
    if _strip_heredoc_fn is None:
        return command
    try:
        return _strip_heredoc_fn(command)
    except Exception:
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

    # Issue #1032: Strip heredoc content before quoted segments so that
    # protected env-var names appearing inside heredoc bodies (e.g. when
    # writing a Markdown file that documents PIPELINE_STATE_FILE) do not
    # produce false-positive blocks. Mirrors the pattern used by
    # _detect_gh_issue_create at lines 2172-2173.
    stripped = _strip_heredoc_content(command)
    stripped = _strip_quoted_segments(stripped)

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


# ---------------------------------------------------------------------------
# Module-level body/message flag helpers (hoisted from
# _contains_gh_issue_create_bypass per Issue #1215 so both the bypass detector
# AND the direct detector can use them).
#
# BODY_FLAGS lists argument flags whose VALUES carry user-authored prose
# (commit messages, issue/PR bodies, titles). False positives lived in these
# values pre-#1203:
#   - --body / --title / --body-file are gh's body-content flags
#   - -m / --message / -F / --file are git commit's message flags
# A single combined set is harmless: stripping a flag the current tool does
# not recognize is a no-op (the loop just skips the next token), and the
# union covers every body/message false-positive surface.
# ---------------------------------------------------------------------------

GH_ISSUE_BODY_FLAGS: "tuple[str, ...]" = (
    # gh issue / pr family
    "--body",
    "--title",
    "--body-file",
    # git commit family (Issue #1215)
    "-m",
    "--message",
    "-F",
    "--file",
)


def _strip_body_arg_values(cmd: str) -> "tuple[str, list[str]]":
    """Strip body/title/message argument VALUES from a tokenized command.

    Tokenize via shlex.split(posix=True). Drop VALUE tokens that immediately
    follow a body flag (separate-value form), and drop ``--flag=VALUE`` /
    ``--body=VALUE`` attached-value tokens entirely. Rejoin remaining tokens
    with single spaces. The resulting string preserves command structure
    (the leading verb, the flags, the rest of argv) but no longer contains
    the body's prose content where false-positive substring matches would
    live.

    The flag set is the union of gh-family flags
    (``--body``/``--title``/``--body-file``) and git-commit-family flags
    (``-m``/``--message``/``-F``/``--file``). Applying a foreign-flag strip
    is harmless because shlex tokenization only treats a token as a flag
    when it appears in flag position; unrecognized flags simply pass
    through as normal tokens.

    Args:
        cmd: The raw Bash command string (will be tokenized).

    Returns:
        Tuple ``(stripped_command, dropped_values)`` where dropped_values
        are the raw VALUE tokens that were removed. Callers may inspect
        dropped_values for embedded bypass patterns (Tier-B scan in
        ``_contains_gh_issue_create_bypass``).

    Raises:
        ValueError: When shlex.split fails (malformed shell, unterminated
            quotes). Callers must catch and fall back to raw-regex behavior
            to preserve fail-closed blocking on garbled input.
    """
    toks = shlex.split(cmd, posix=True)  # may raise ValueError; let caller catch
    out: list[str] = []
    dropped: list[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in GH_ISSUE_BODY_FLAGS:
            # drop flag AND its value; capture the value for embedded-bypass scan
            if i + 1 < len(toks):
                dropped.append(toks[i + 1])
            i += 2
            continue
        attached_flag = next(
            (flag for flag in GH_ISSUE_BODY_FLAGS if t.startswith(flag + "=")),
            None,
        )
        if attached_flag is not None:
            # drop --body=VALUE / --message=VALUE attached form;
            # capture VALUE portion (everything after the '=') for the scan
            dropped.append(t[len(attached_flag) + 1:])
            i += 1
            continue
        out.append(t)
        i += 1
    return " ".join(out), dropped


# Shell wrappers whose -c argument carries a sub-command. When the leading
# verb (argv[0]) is one of these AND argv[1] == "-c", the substring scan
# inside argv[2] is handled by _contains_gh_issue_create_bypass — do not
# double-flag from _detect_gh_issue_create's direct-match argv check.
_SHELL_WRAPPERS: "frozenset[str]" = frozenset({
    "sh", "bash", "zsh", "dash", "ksh",
    "/bin/sh", "/bin/bash", "/bin/zsh", "/bin/dash", "/bin/ksh",
    "/usr/bin/sh", "/usr/bin/bash", "/usr/bin/zsh",
    "/usr/local/bin/sh", "/usr/local/bin/bash", "/usr/local/bin/zsh",
})


_STATEMENT_SEPARATORS: "frozenset[str]" = frozenset({"|", ";", "&&", "||", "&", "\n"})


def _split_statements(command: str) -> "list[str]":
    """Split a Bash command string into top-level statement strings.

    Walks the source command character-by-character respecting single and
    double quotes (so a separator inside a quoted body is NOT a split point).
    Recognized top-level separators: ``;``, ``&&``, ``||``, ``|``, ``&``,
    and newline. The resulting statement strings preserve their interior
    structure (quoting, flags, values) for the caller to feed to shlex.

    Args:
        command: The raw Bash command string.

    Returns:
        List of statement substrings with surrounding whitespace stripped.
        Empty statements are dropped.
    """
    out: "list[str]" = []
    buf: "list[str]" = []
    i = 0
    n = len(command)
    in_single = False
    in_double = False
    while i < n:
        c = command[i]
        # Quote handling: single quotes are literal (no escapes); double
        # quotes honor backslash escapes for the closing quote.
        if c == "'" and not in_double:
            in_single = not in_single
            buf.append(c)
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            buf.append(c)
            i += 1
            continue
        if in_single or in_double:
            # Inside a quoted region, preserve everything verbatim
            # (including backslash-escapes inside double quotes).
            if c == "\\" and in_double and i + 1 < n:
                buf.append(c)
                buf.append(command[i + 1])
                i += 2
                continue
            buf.append(c)
            i += 1
            continue
        # Two-character separators take precedence over single-char ones.
        if i + 1 < n and command[i:i + 2] in ("&&", "||"):
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 2
            continue
        if c in (";", "|", "&", "\n"):
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _gh_issue_create_at_command_position(command: str) -> bool:
    """Argv-position check: is ``gh issue create`` the command at argv[0]?

    Per Issue #1215, a raw substring scan of the Bash command falsely matched
    the gh-issue-create command name when it appeared in prose inside a
    ``git commit -m "..."`` body. This helper mirrors the shlex-aware
    treatment that ``_contains_gh_issue_create_bypass`` uses for backtick/$()
    detection and applies it to the direct ``gh issue create`` match path.

    Detection rules:
    1. Split the raw command into top-level statements on Bash statement
       separators (``;``, ``&&``, ``||``, ``|``, ``&``, newline) that live
       OUTSIDE quoted regions. This catches multi-statement forms like
       ``cat <<EOF ... EOF; gh issue create ...`` where the gh call is the
       leading verb of a later statement.
    2. For each statement, strip body/message argument VALUES via
       ``_strip_body_arg_values`` so prose inside ``-m``/``--body``/``-F``
       cannot match.
    3. Tokenize via shlex.split(posix=True). Take argv[0] as the command
       verb (skipping leading env-var assignments like ``FOO=bar``). If
       verb is ``gh`` AND the next two argv tokens are ``issue`` then
       ``create`` (case-insensitive), the command IS at command position →
       return True.
    4. If the verb is a shell wrapper (``sh``, ``bash``, ``/bin/sh``...) with
       ``-c`` followed by a sub-command, leave detection to the bypass
       detector — skip this statement here. (The bypass detector already
       catches this pattern with shlex-stripping.)
    5. Any other verb (``git``, ``python3``, ``cat``, etc.) → skip statement.

    Args:
        command: The raw Bash command string.

    Returns:
        True if ``gh issue create`` is at argv command position in at least
        one statement, False otherwise. Raises no exceptions — on
        shlex.ValueError for a given statement, that statement is skipped
        (caller's raw-regex fallback preserves fail-closed blocking for the
        whole-command malformed case).
    """
    statements = _split_statements(command)
    for stmt in statements:
        try:
            stripped_cmd, _dropped = _strip_body_arg_values(stmt)
        except ValueError:
            # Malformed statement — skip; whole-command fallback handles it.
            continue
        try:
            seg = shlex.split(stripped_cmd, posix=True)
        except ValueError:
            continue
        if not seg:
            continue

        # Skip leading env-var assignments (FOO=bar gh issue create ...).
        idx = 0
        while idx < len(seg) and "=" in seg[idx] and not seg[idx].startswith("-"):
            idx += 1
        if idx >= len(seg):
            continue
        verb = seg[idx]

        # Shell-wrapper case (sh -c "gh issue create ..."): handled by the
        # bypass detector — do NOT double-flag here.
        if verb in _SHELL_WRAPPERS:
            continue

        # The only case that counts as command-position is verb == "gh"
        # with the next two tokens "issue" then "create" (case-insensitive).
        if verb.lower() == "gh":
            if (
                idx + 2 < len(seg)
                and seg[idx + 1].lower() == "issue"
                and seg[idx + 2].lower() == "create"
            ):
                return True

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

        # Patterns 4 and 5: backtick / $() command substitution at command position.
        # Issue #1203: previously these were RAW regex scans, which produced
        # false positives when the user passed a backtick-quoted body to
        # `gh issue comment` (live-confirmed). Make argv-aware: tokenize via
        # shlex.split, strip the VALUE token that follows --body/--title/
        # --body-file (and the --body=VALUE attached-value form), rejoin, then
        # apply the original regex on the reconstructed string. The reconstructed
        # form still contains the bypass when it lives at command position (e.g.
        # `RESULT=\`gh issue create...\``) but no longer contains backtick/$()
        # substrings that were merely body-argument content.
        # Mirrors _detect_git_bypass shlex precedent (~line 624). `sh -c
        # "gh issue create..."` and subprocess wrappers are caught by Patterns
        # 1-3 above and remain blocked unchanged. On shlex ValueError
        # (malformed shell), fall back to the original raw-regex behavior so
        # we never weaken blocking on garbled inputs.
        # Argv-aware body-value stripping is handled by the module-level
        # _strip_body_arg_values helper (hoisted in Issue #1215 so both this
        # bypass detector AND _detect_gh_issue_create can share it). The flag
        # set GH_ISSUE_BODY_FLAGS combines gh's --body/--title/--body-file
        # with git commit's -m/--message/-F/--file to cover the union of
        # false-positive surfaces.
        try:
            stripped_for_subst, dropped_values = _strip_body_arg_values(command)
        except ValueError:
            # Malformed shell — fall back to the original raw-regex behavior
            # so we never weaken blocking on garbled inputs.
            backtick_pattern = r'`\s*gh\s+issue\s+create\b'
            if re.search(backtick_pattern, command, re.IGNORECASE | re.DOTALL):
                return True
            dollar_subst_pattern = r'\$\(\s*gh\s+issue\s+create\b'
            if re.search(dollar_subst_pattern, command, re.IGNORECASE | re.DOTALL):
                return True
            return False

        # Patterns 4 & 5 (Tier A — command-position substitution).
        # After body-value stripping, any remaining backtick/$() substitution is
        # at command position (e.g. RESULT=`gh issue create...` or
        # FOO=$(gh issue create...)). These ALWAYS execute at shell runtime
        # and must be blocked.
        # Pattern 4: Backtick command substitution: `gh issue create ...`
        backtick_cmd_pos = r'`\s*gh\s+issue\s+create\b'
        if re.search(backtick_cmd_pos, stripped_for_subst, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 5: $(...) command substitution with gh issue create as the
        # direct command, e.g. $(gh issue create --title "test").
        # NOT matched: $(cat <<'EOF'\ngh issue create\nEOF\n) — heredoc body.
        dollar_subst_cmd_pos = r'\$\(\s*gh\s+issue\s+create\b'
        if re.search(dollar_subst_cmd_pos, stripped_for_subst, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 6 (Tier B — FINDING-1 fix, Issue #1203 remediation cycle 1).
        # Substitution inside body-flag VALUES. In POSIX shell, both $() and
        # backticks INSIDE DOUBLE QUOTES execute (and create the issue). Inside
        # single quotes they do NOT execute (single quotes are literal).
        # shlex.split(posix=True) discards quote-type info, so we cannot tell
        # which quoting style produced each dropped value. Per the FINDING-1
        # guidance, we fail closed: any dropped value containing a backtick or
        # $() substitution with `gh issue create` AT COMMAND POSITION inside
        # the substitution is blocked. Match the same precision as the
        # Tier-A command-position scan (`\s*gh\s+issue\s+create` at the start
        # of the substitution opener) so that:
        #   - `--body "$(gh issue create -t x)"`     → BLOCKED (real bypass)
        #   - `--body "$(echo x)"`                    → ALLOWED (benign)
        #   - `--body "see \`some helper\`"`           → ALLOWED (no create pattern)
        #   - `git commit -m "$(cat <<EOF ... EOF)"` → ALLOWED (cat is command;
        #       gh issue create inside heredoc body is just text)
        # Tradeoff: a single-quoted body containing literal
        # `` `gh issue create` `` as code-formatted prose will be blocked even
        # though shell would not execute it. The fail-closed posture is the
        # safer choice — the live-confirmed false positive (prose backticks
        # or $() WITHOUT the create pattern at command position in the
        # substitution) is still allowed.
        value_backtick_cmd_pos = r'`\s*gh\s+issue\s+create\b'
        value_dollar_cmd_pos = r'\$\(\s*gh\s+issue\s+create\b'
        for val in dropped_values:
            if re.search(value_backtick_cmd_pos, val, re.IGNORECASE | re.DOTALL):
                return True
            if re.search(value_dollar_cmd_pos, val, re.IGNORECASE | re.DOTALL):
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

        # Check 1: Direct 'gh issue create' in the stripped command.
        #
        # Issue #1215: the raw substring scan produced a false positive when
        # the substring appeared in prose inside a git-commit body that
        # escaped the simple quote stripper (e.g., shell-escaped quotes,
        # ANSI-C $'...' quoting, or unquoted prose between -m and the next
        # argument). The fix is argv-position-aware: require that
        # ``gh issue create`` lives at argv[0] of some pipeline segment, NOT
        # merely as a substring of the rendered command. The shlex-aware
        # helper mirrors the bypass detector's #1203 treatment.
        #
        # Fail-closed: on malformed shell (shlex ValueError), the helper
        # returns False AND we then check the raw-regex fallback against the
        # quote-stripped command. This preserves blocking on garbled input
        # where a true bypass form like
        # ``RESULT=`gh issue create --title 'unterminated`` would still trip
        # the regex scan even though shlex cannot parse it. The bypass
        # detector independently scans the raw command for the same family
        # of forms.
        argv_match = _gh_issue_create_at_command_position(command)

        # Raw-regex fallback ONLY when the shlex-aware path could not parse.
        # We detect the unparseable case by attempting the same shlex call
        # and catching ValueError. When shlex parses cleanly but argv_match
        # is False, the substring is genuinely NOT at command position and
        # the direct-match path stays False (true argv-blind false positive
        # avoided).
        try:
            shlex.split(command, posix=True)
            shlex_parsed = True
        except ValueError:
            shlex_parsed = False

        if shlex_parsed:
            direct_match = argv_match
        else:
            # Malformed shell — fall back to the original raw-regex behavior
            # on the quote-stripped command so true bypass forms with garbled
            # syntax still trip the gate.
            direct_match = bool(
                re.search(r'\bgh\s+issue\s+create\b', stripped, re.IGNORECASE)
            )

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

        # Allow-through 3: Issue-creating command is active (Issue #630).
        # Prior-call ordering contract (Issue #1203): the command context file
        # MUST be written in a PRIOR Bash tool call (separate from the gh issue
        # create call), because PreToolUse evaluates each Bash invocation BEFORE
        # it runs — bundling "write context && gh issue create" into one Bash
        # call leaves the context absent at hook-evaluation time and blocks.
        # See #1203 plan and the six issue-creating command markdowns.
        # Out-of-scope caveat: cross-session /tmp context leak between concurrent
        # sessions is tracked separately as Issue #1206.
        # NOTE: a prior marker-file READ allow-through (writing
        # GH_ISSUE_MARKER_PATH would grant a 1h pass) was removed in #1203
        # because nothing writes the marker anymore (the WRITE has been blocked
        # by _detect_gh_issue_marker_creation since #627) — that allow-through
        # was dead code. The WRITE blocker is kept as defense-in-depth.
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

        # Determine pipeline mode. #1177: env-var handled internally by
        # _get_pipeline_mode_from_state() since #1173 — the previous
        # outer `os.environ.get("PIPELINE_MODE") or ...` short-circuit
        # was dead code (the helper already reads the same env var at
        # its first line).
        pipeline_mode = _get_pipeline_mode_from_state()
        issue_number = 0
        try:
            # NOTE(#1177-followup): env-var read here may also be dead; audit deferred.
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
            f"BYPASS (in order of reliability): "
            f"(1) `touch /tmp/skip_agent_completeness_gate` as a SEPARATE command first, "
            f"then retry the commit — file-based, works mid-session "
            f"(chaining with && WILL NOT WORK — the hook intercepts compound commands before touch executes); "
            f"(2) export SKIP_AGENT_COMPLETENESS_GATE=1 BEFORE launching claude "
            f"(env vars don't propagate mid-session — Issue #779). (Issue #802)"
        )
    except Exception:
        return None  # Fail-open


def _detect_settings_json_write(command: str) -> "Optional[str]":
    """Detect Bash commands that write to settings.json or settings.local.json.

    Only blocks during active pipeline. Called separately after pipeline check.

    Issue #971: Primary detection routes through ``_extract_bash_file_writes``
    (which delegates to ``tool_intent.write_targets``) for AST-accurate
    classification. The legacy regex duplicate that flagged ``open()`` calls
    (and produced false positives on ``json.load(open(...))``) is removed.

    A narrow defense-in-depth check is retained for the variable-indirection
    case (``p='settings.json'; json.dump(d, open(p, 'w'))``) where the AST
    detector cannot statically resolve the path. This check requires BOTH a
    settings reference AND a true python write keyword (``json.dump``,
    ``.write_text``, ``.write_bytes``, ``shutil.``, ``os.rename``,
    ``os.replace``), or a non-trivial ``.write(`` call. We deliberately do
    NOT match ``open\\s*\\(`` alone — that was the source of the
    ``json.load(open(...))`` false positive in the legacy code (Issue #971).

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
    # Check ALL write targets — the shim covers redirects, tee, cp/mv,
    # sed -i, dd, tools like rm/touch/chmod, AND python -c snippets via
    # python_write_detector AST analysis. (Issue #557, #768, #971)
    write_targets = _extract_bash_file_writes(command)
    # Issue #958: Allow writes to tempfile directories — these paths cannot
    # affect real settings files under ~/.claude/ or any project root.
    _TEMP_PREFIXES = ("/tmp/", "/var/folders/", "/private/tmp/")
    for target in write_targets:
        if any(target.startswith(prefix) for prefix in _TEMP_PREFIXES):
            continue  # Safe: tempfile directory, not a real settings location
        for pat in settings_patterns:
            if re.search(pat, target):
                if re.search(r'\bsed\s+.*-i', command):
                    return (
                        f"BLOCKED: In-place edit of settings file during active pipeline. "
                        f"Settings files are protected during /implement sessions. (Issue #557) "
                        f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                        f"then modify settings. Do NOT write settings during an active pipeline."
                    )
                if re.search(r'\bpython3?\s+-c\b', command) or re.search(r'\bpython3?\s+.*?<<', command):
                    return (
                        f"BLOCKED: Python -c command writes to settings file during active pipeline. "
                        f"Settings files are protected during /implement sessions. (Issue #768) "
                        f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                        f"then modify settings. Do NOT write settings during an active pipeline."
                    )
                return (
                    f"BLOCKED: Bash write to '{target}' during active pipeline. "
                    f"Settings files are protected during /implement sessions. (Issue #557) "
                    f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                    f"then modify settings. Do NOT write settings during an active pipeline."
                )

    # Defense-in-depth: variable-indirection case for python -c snippets
    # (Issue #768). The AST detector cannot resolve ``p`` in:
    #   python3 -c "p='settings.json'; json.dump({}, open(p,'w'))"
    # so we fall back to a narrow regex check that requires BOTH a settings
    # reference AND a true write keyword. We deliberately do NOT match
    # ``open\s*\(`` alone — that was the false-positive trigger removed in
    # Issue #971 (it flagged read-only ``json.load(open(...))``).
    #
    # Issue #958: Skip the defense-in-depth block entirely when ALL resolved
    # write targets that reference settings patterns are in temp directories.
    # This prevents false-positives on python -c snippets that write to
    # /private/tmp/, /tmp/, or /var/folders/ (e.g. pytest fixtures).
    _all_settings_writes_are_temp = (
        len(write_targets) > 0
        and all(
            any(target.startswith(prefix) for prefix in _TEMP_PREFIXES)
            for target in write_targets
            if any(re.search(pat, target) for pat in settings_patterns)
        )
        and any(
            any(re.search(pat, target) for pat in settings_patterns)
            for target in write_targets
        )
    )
    if _all_settings_writes_are_temp:
        return None
    py_c_patterns = [
        r'python3?\s+-c\s+"([^"]+)"',
        r"python3?\s+-c\s+'([^']+)'",
    ]
    # Narrow write-keyword patterns: each one is a *true* write operation,
    # not an ambiguous expression. open(...) is excluded by design.
    python_write_keywords = [
        r'\bjson\.dump\s*\(',
        r'\.write_text\s*\(',
        r'\.write_bytes\s*\(',
        r'\bshutil\.(copy|copy2|move|copyfile)\s*\(',
        r'\bos\.rename\s*\(',
        r'\bos\.replace\s*\(',
        # Match .write( only when it follows a variable obtained from open()
        # in WRITE mode — heuristic: the snippet contains both an open(...,
        # 'w'/'a'/'wb'/'ab') call AND a .write( call somewhere.
    ]
    for py_c_pat in py_c_patterns:
        for match in re.finditer(py_c_pat, command):
            snippet = match.group(1)
            if not any(re.search(p, snippet) for p in settings_patterns):
                continue
            if any(re.search(wp, snippet) for wp in python_write_keywords):
                return (
                    f"BLOCKED: Python -c command writes to settings file during active pipeline. "
                    f"Settings files are protected during /implement sessions. (Issue #768) "
                    f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                    f"then modify settings. Do NOT write settings during an active pipeline."
                )
            # ``f = open(p, 'w'); f.write(x)`` pattern: open() in write mode
            # AND a separate .write() call. We DO NOT trigger on .write()
            # alone because that's also how strings/streams are constructed.
            if re.search(r"open\s*\([^)]*,\s*['\"][wa]", snippet) and re.search(r"\.write\s*\(", snippet):
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
    """Extract file paths being written to by Bash command.

    Issue #971: This is now a thin compatibility shim that delegates to
    ``tool_intent.write_targets`` when the tool_intent module is loaded.
    Falls back to the legacy regex-based implementation if the new
    classifier is unavailable.

    The shim preserves the public signature (``command: str -> list``) so
    all 5 existing callers continue to work unchanged. SUSPICIOUS_EXEC_SENTINEL
    handling is preserved — when present, it is excluded from the returned
    list (callers that need the sentinel use the dedicated path in
    ``_check_bash_infra_writes`` which calls ``tool_intent`` directly).
    """
    if _tool_intent is None:
        return _extract_bash_file_writes_legacy(command)
    try:
        targets = _tool_intent.write_targets("Bash", {"command": command})
    except Exception:
        return _extract_bash_file_writes_legacy(command)
    # Strip the SUSPICIOUS_EXEC_SENTINEL — historical callers of this
    # function never saw it, only _check_bash_infra_writes did.
    if _python_write_detector is not None:
        sentinel = getattr(_python_write_detector, "SUSPICIOUS_EXEC_SENTINEL", None)
        if sentinel is not None:
            targets = [t for t in targets if t != sentinel]
    return targets


def _extract_bash_file_writes_legacy(command: str) -> list:
    """Legacy regex-based implementation (preserved for fallback).

    Used only when the ``tool_intent`` module fails to load. Returns the
    same shape (``list`` of file path strings) as the shim.
    """
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
            # #1171: sanitize untrusted env-var before writing to JSON log.
            "session_id": _resolve_session_id_safe(_session_id) or "unknown",
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
            # NOTE(#1177-followup): env-var read here may also be dead; audit deferred.
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
            # #1171: sanitize untrusted env-var before writing to JSON log.
            "session_id": _resolve_session_id_safe(_session_id) or "unknown",
            "agent": _get_active_agent_name() or "main",
            **summary,
        }
        with open(log_dir / f"{date_str}.jsonl", "a") as f:
            f.write(_json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass


@block_event_decorator("unified_pre_tool.py")
def output_decision(decision: str, reason: str, *, system_message: str = ""):
    """Output the hook decision in required format.

    Args:
        decision: Permission decision ("allow", "deny", or "ask")
        reason: Human-readable reason for the decision
        system_message: Optional message injected into model context (visible to user)

    Telemetry (Issue #972): when ``decision == "deny"``, the
    ``block_event_decorator`` appends one structured JSONL row to
    ``.claude/logs/hook-blocks.jsonl`` so the per-hook block count and
    deny-reason text can be reconstructed without grepping session
    transcripts. The decorator is idempotent and never raises.
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


def _resolve_session_id_safe(input_session_id: Optional[str]) -> Optional[str]:
    """Resolve and sanitize the active session id.

    Centralizes the "read CLAUDE_SESSION_ID env var, fall back to the
    already-sanitized module-level ``_session_id``, then sanitize the
    result" pattern that was previously duplicated at 8 sites. The env
    var is untrusted process input — without sanitizing here, the raw
    value would flow into filesystem paths and HMAC computations.

    Args:
        input_session_id: Fallback session id when the env var is unset
            (typically ``_session_id`` from the hook's per-invocation
            scope, which is itself already sanitized at line 4856).

    Returns:
        A sanitized session id string, OR ``None`` if the resolved value
        is empty or the literal ``"unknown"`` after sanitization. Callers
        that need ``"unknown"`` semantics use ``... or "unknown"`` at the
        call site to preserve prior behavior.

    Issues: #1171
    """
    env_raw = os.getenv("CLAUDE_SESSION_ID") or input_session_id or ""
    sanitized = _sanitize_session_id(env_raw)
    return sanitized if sanitized and sanitized != "unknown" else None


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


def _record_agent_denial(
    agent_type: str,
    *,
    block_event_id: "Optional[str]" = None,
    block_timestamp_iso: "Optional[str]" = None,
) -> None:
    """Record that an agent invocation was denied by prompt integrity (Issue #750).

    Writes a JSON file keyed by session_id so subsequent Write/Edit calls
    can detect the workaround pattern and block substantive edits to
    protected infrastructure.

    Atomic write: writes to a .tmp file first, then os.replace.
    Fail-open: exceptions are silently ignored.

    Args:
        agent_type: The agent type that was denied (e.g. 'implementer').
        block_event_id: Optional uuid4 identifier paired with the
            ``prompt_integrity_block`` telemetry row (Issue #1178). When set,
            the recovery emission joins back to the original block via this id.
        block_timestamp_iso: Optional ISO-8601 UTC timestamp captured at
            block emission time (Issue #1178). When set, the recovery
            emission computes block->recovery latency from this anchor.
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
        # Issue #1178: telemetry fields are additive. _check_agent_denial only
        # reads agent_type/session_id/timestamp; the new helpers below read
        # the full dict. Unknown-key safety is verified by regression test.
        if block_event_id is not None:
            state["block_event_id"] = block_event_id
        if block_timestamp_iso is not None:
            state["block_timestamp_iso"] = block_timestamp_iso
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
            # Issue #1051: deny file from a different session is orphaned — clean it up
            try:
                os.unlink(state_path)
            except OSError:
                pass  # fail-open — cleanup failure must not block agents
            return None
        if _time.time() - state.get("timestamp", 0) > window_seconds:
            # Issue #1051: stale deny file beyond TTL — clean it up so subsequent
            # agent invocations are not blocked by manual `rm` requirements
            try:
                os.unlink(state_path)
            except OSError:
                pass  # fail-open — cleanup failure must not block agents
            return None
        return state.get("agent_type", "")
    except Exception:
        return None  # Fail-open


def _read_agent_denial_record() -> "Optional[Dict[str, Any]]":
    """Read the full agent-denial state dict for the current session (Issue #1178).

    Mirrors ``_check_agent_denial`` for path resolution and session-id
    matching, but returns the full state dict (including #1178 telemetry
    fields ``block_event_id`` and ``block_timestamp_iso``) instead of just
    the agent_type. Used by the recovery emission path to compute
    block->recovery latency.

    Fail-open: returns None on missing file, parse error, session mismatch,
    or path-confinement violation.

    Returns:
        The full state dict, or None on any error / no record.
    """
    import json as _json
    try:
        state_path = os.path.join(
            AGENT_DENY_STATE_DIR, f"adev-agent-deny-{_session_id}.json"
        )
        resolved = os.path.realpath(state_path)
        base = os.path.realpath(AGENT_DENY_STATE_DIR)
        if not resolved.startswith(base + os.sep) and resolved != base:
            return None
        if not os.path.exists(state_path):
            return None
        with open(state_path) as f:
            state = _json.load(f)
        if not isinstance(state, dict):
            return None
        if state.get("session_id") != _session_id:
            return None
        return state
    except Exception:
        return None


def _consume_agent_denial_record() -> None:
    """Delete the agent-denial state file after a successful recovery (Issue #1178).

    Enforces the single-emit invariant: once a ``prompt_integrity_recovery``
    event has been written for a given block, the denial state must be
    cleared so subsequent allow-path invocations do not re-emit.

    Fail-open: silently ignores OSError (e.g. file already removed).
    """
    try:
        state_path = os.path.join(
            AGENT_DENY_STATE_DIR, f"adev-agent-deny-{_session_id}.json"
        )
        resolved = os.path.realpath(state_path)
        base = os.path.realpath(AGENT_DENY_STATE_DIR)
        if not resolved.startswith(base + os.sep) and resolved != base:
            return
        if os.path.exists(state_path):
            os.unlink(state_path)
    except Exception:
        pass


# Issue #1178: regex for extracting the three numerics from a typical
# prompt-integrity deny reason, e.g.
#   "Prompt for 'researcher-local' shrank 27.6% from baseline (399 words -> 289 words)"
# Capture groups: (1) shrinkage percent, (2) baseline words, (3) current words.
# The arrow byte may be ASCII "->", a literal unicode "->", or a UTF-8 right-arrow.
_PI_NUMERICS_RE = re.compile(
    r"shrank\s+([0-9]+(?:\.[0-9]+)?)\s*%[^()]*\(\s*([0-9]+)\s*words\s*[^0-9]+\s*([0-9]+)\s*words",
    re.IGNORECASE,
)


def _parse_pi_numerics(
    reason: str,
) -> "Tuple[Optional[float], Optional[int], Optional[int]]":
    """Extract (shrinkage_pct, baseline_words, current_words) from a PI reason (Issue #1178).

    Fail-open: returns ``(None, None, None)`` on any parse failure. Never raises.

    Args:
        reason: The deny reason string emitted by ``validate_prompt_integrity``.

    Returns:
        Tuple of (shrinkage_pct: float|None, baseline_words: int|None,
        current_words: int|None). Any element that could not be parsed is None.
    """
    try:
        if not isinstance(reason, str):
            return (None, None, None)
        m = _PI_NUMERICS_RE.search(reason)
        if m is None:
            return (None, None, None)
        try:
            pct = float(m.group(1))
        except (TypeError, ValueError):
            pct = None
        try:
            baseline = int(m.group(2))
        except (TypeError, ValueError):
            baseline = None
        try:
            current = int(m.group(3))
        except (TypeError, ValueError):
            current = None
        return (pct, baseline, current)
    except Exception:
        return (None, None, None)


def _emit_prompt_integrity_event(
    event_type: str,
    *,
    agent_type: str,
    block_event_id: str,
    **kwargs: "Any",
) -> None:
    """Emit prompt-integrity telemetry row to hook-blocks.jsonl (Issue #1178).

    Thin wrapper around ``log_block_event`` with privacy gating: the
    ``block_reason_detail`` field is stripped unless the
    ``HOOK_TELEMETRY_VERBOSE=1`` env var is set. Never raises — telemetry
    must never break the underlying hook decision path.

    Args:
        event_type: One of ``_PI_BLOCK_EVENT_TYPE`` or
            ``_PI_RECOVERY_EVENT_TYPE``.
        agent_type: The agent type involved (e.g. ``"researcher-local"``).
        block_event_id: uuid4 string joining the block and recovery rows.
        **kwargs: Additional fields to include in the metadata payload.
    """
    try:
        metadata = {
            "event_type": event_type,
            "block_event_id": block_event_id,
            "agent_type": agent_type,
            "session_id": _session_id,
        }
        metadata.update(kwargs)
        if os.environ.get("HOOK_TELEMETRY_VERBOSE") != "1":
            metadata.pop("block_reason_detail", None)
        log_block_event(
            hook_name="unified_pre_tool.py",
            decision_shape="dict",
            reason=f"{event_type}:{agent_type}",
            metadata=metadata,
        )
    except Exception:
        # Telemetry must never break the hook decision path.
        pass


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
    # Issue #1206: include both the legacy /tmp literal (orphan protection for
    # pre-#1206 sessions) and the new per-repo path via LEGACY_SENTINEL_LITERALS.
    _STATE_FILE_PATTERNS = [
        *LEGACY_SENTINEL_LITERALS,
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
    # Issue #1153 (Phase 2): inline regex unified with shared heredoc_utils.

    # Strip heredoc bodies: <<'EOF'...EOF, <<EOF...EOF, <<"EOF"...EOF, <<-EOF...EOF
    command = _strip_heredoc_content(command)

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


def _check_rm_rf_unresolved_vars(command: str) -> "Optional[Tuple[str, str]]":
    """Detect `rm -rf` (or `rm -f`/`rm -Rf` etc.) with unquoted variable expansion.

    Catastrophic-prevention guard (Issue #1008). When a variable used as the
    deletion target is unset or empty, `rm -rf $VAR/subpath` expands to
    `rm -rf /subpath` — which can erase critical filesystem paths. Quoting the
    variable (`"$VAR"`) makes the empty case safe (`rm -rf ""` is a harmless
    no-op), so the rule is: flag UNQUOTED variable expansions only.

    Detection scope:
        - `rm -rf $VAR` / `rm -rf ${VAR}` — unquoted variable
        - `rm -rf $VAR/anything` — unquoted variable with suffix
        - `rm -f $VAR` — single-file `rm -f` with unquoted var is also dangerous
        - `rm -Rf $VAR`, `rm -fr $VAR`, etc. — any combo of [rRfF] flags

    Safe (NOT flagged):
        - `rm -rf "$VAR"` / `rm -rf "${VAR}"` — quoted variable
        - `rm -rf /tmp/foo` — literal path
        - `ls -la` — not an `rm` command
        - heredoc bodies and `--body "..."` quoted args (stripped before scanning)

    Args:
        command: The Bash command string to inspect.

    Returns:
        ``None`` if the command is safe, or a tuple of ``(decision, reason)``
        where ``decision == "deny"`` and ``reason`` carries the user-facing
        message. The tuple shape matches the deny-pipeline contract used by
        the caller in ``main()``.
    """
    import re

    try:
        # Strip heredoc bodies and --body/--message quoted args so user-supplied
        # text content (issue descriptions, PR bodies, etc.) doesn't trigger a
        # false positive. Mirrors the sanitization in _check_bash_state_deletion.
        # Issue #1153 (Phase 2): inline regex unified with shared heredoc_utils.
        scrubbed = _strip_heredoc_content(command)

        _body_pat = r"""--body\s+(?:'[^']*'|"[^"]*"|\$\([^)]*\))"""
        scrubbed = re.sub(_body_pat, '--body ""', scrubbed)

        _msg_pat = r"""(?:--message|-m)\s+(?:'[^']*'|"[^"]*")"""
        scrubbed = re.sub(_msg_pat, '-m ""', scrubbed)

        # Core detection: `rm` + one or more flag tokens (each containing at
        # least one of r/R/f/F) + a bareword variable expansion.
        #
        # The negative lookahead `(?!["\'])` is the safety hinge: if the next
        # character is a quote, the variable is being expanded safely and we
        # do NOT flag.
        rm_rf_var_pattern = (
            r"\brm\s+(?:-[a-zA-Z]*[rRfF][a-zA-Z]*\s+)+"
            r"(?![\"'])"
            r"(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)"
        )
        match = re.search(rm_rf_var_pattern, scrubbed)
        if match is not None:
            var_expr = match.group(1)
            reason = (
                f"BLOCKED: rm -rf with unquoted variable expansion detected: "
                f"{var_expr}. If the variable is unset or empty, the command "
                f"expands to a catastrophic deletion (e.g. `rm -rf /subpath` "
                f"or `rm -rf /`). Quote the variable to make the empty case "
                f"a safe no-op: rm -rf \"{var_expr}\". "
                f"REQUIRED NEXT ACTION: Re-issue the command with the "
                f"variable double-quoted."
            )
            return ("deny", reason)
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


def _phase_e_skip(
    function_name: str,
    input_data: "Optional[Dict]" = None,
    session_id: "Optional[str]" = None,
) -> "Optional[Tuple[bool, str]]":
    """Phase E gate (Issue #999) — should the named check be skipped?

    Wraps the pure policy in :mod:`enforcement_decision` with the local
    telemetry surface and a session_id resolution that prefers the caller's
    explicit value, then falls back to ``input_data`` via :mod:`hook_stdin`.

    Returns:
        ``None`` on import failure (transitional deploy / cross-cwd /
        partial uninstall) — caller MUST treat None as "fall through to
        existing logic".
        ``(skip, reason)`` otherwise. ``skip == True`` means the named
        check SHOULD be bypassed; ``skip == False`` means run it as today.
        On skip, this helper emits a single ``mode_skip`` telemetry row.
        The enforce path is silent — preserves the pre-Phase-E baseline.

    NEVER raises — every exception path returns either None (import error)
    or ``(False, "exception_safety")`` (runtime error → fail-safe enforce).
    """
    try:
        from enforcement_decision import should_skip_enforcement
        from hook_telemetry import log_block_event

        sid = session_id
        if sid is None and input_data is not None:
            try:
                from hook_stdin import extract_session_id
                sid = extract_session_id(input_data)
            except ImportError:
                pass

        skip, reason = should_skip_enforcement(
            hook_name="unified_pre_tool.py",
            function_name=function_name,
            session_id=sid,
        )
        if skip:
            log_block_event(
                hook_name="unified_pre_tool.py",
                decision_shape="mode_skip",
                reason=reason,
                metadata={"function": function_name},
                session_id=sid,
            )
        return (skip, reason)
    except ImportError:
        # Phase E libs not yet deployed in this environment — fall through.
        return None
    except Exception:
        # Fail-safe: any unexpected exception → enforce. The hook decision
        # path is load-bearing; we never want to skip a gate because we hit
        # a weird exception inside the policy layer.
        return (False, "exception_safety")


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

        # =================================================================
        # UNIVERSAL BYPASS (Issue #969): AUTONOMOUS_DEV_BYPASS=1 OR
        # .claude/.bypass file in cwd-or-ancestor falls through to allow.
        # Checked BEFORE any other validation so a deadlocked harness can
        # always be unstuck by setting either signal from outside.
        # =================================================================
        try:
            from hook_bypass import is_bypassed, log_bypass_used
            if is_bypassed():
                log_bypass_used(
                    hook_name=Path(__file__).name,
                    tool_name=tool_name,
                )
                output_decision("allow", "Universal bypass active (#969)")
                sys.exit(0)
        except ImportError:
            pass  # bypass library unavailable - continue with normal hook logic

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
            #
            # Phase E (Issue #999): wrap with session-mode gate so low-risk
            # session classes skip the plan-exit nudge. Hard-floor checks
            # are NOT wrapped.
            _phase_e = _phase_e_skip(
                "_check_plan_exit_native",
                input_data=input_data,
                session_id=_session_id,
            )
            if _phase_e is None or not _phase_e[0]:
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
            #
            # Issue #971: This block is the canonical Edit/Write tool gate.
            # Tool-name dispatch is sufficient here — no command parsing needed.
            # The settings.json sub-gate at lines ~3989+ handles the per-pipeline
            # restriction. Verified correct by Issue #971 plan; no functional
            # change required, only this clarifying comment.
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

                # Issue #1142+ (Phase 1 polarity flip): Default-on production-code
                # Write/Edit gate. Replaces the previous opt-IN check via
                # `.claude/.enforce`. Per-repo opt-out is now via the existing
                # `.claude/.bypass` marker (already short-circuited at line ~4532).
                # The gate runs unless the pipeline is active, a one-shot operator
                # bypass is set, the file is non-code or a test, or the edit
                # classifies as no-change. Tier is one of "fix" / "light" / "full"
                # and is mapped to the matching /implement variant in the directive.
                try:
                    # Phase 2 (Issue #1146): pass session_id so the
                    # sliding-window can scope its ring buffer per session.
                    # #1171: sanitize untrusted env-var before use.
                    _wpg_session_id = _resolve_session_id_safe(_session_id)
                    _wpg_block, _wpg_tier, _wpg_directive = _check_write_pipeline_required(
                        tool_name,
                        file_path,
                        tool_input.get("old_string", ""),
                        tool_input.get("new_string", tool_input.get("content", "")),
                        session_id=_wpg_session_id,
                    )
                except Exception:
                    # Fail-closed on any unexpected exception
                    _wpg_block, _wpg_tier, _wpg_directive = (
                        True,
                        "wpg_check_error",
                        "Run /implement to make changes. Production-code gate detection errored; defaulting to enforce.",
                    )

                if _wpg_block:
                    _wpg_file_name = Path(file_path).name if file_path else "unknown"
                    _wpg_block_reason = (
                        f"BLOCKED: Write/Edit to code file '{_wpg_file_name}' requires the /implement pipeline. "
                        f"File: {file_path} "
                        f"Tier: {_wpg_tier}. "
                        f"REQUIRED NEXT ACTION: {_wpg_directive} "
                        f"Per-repo opt-out: touch .claude/.bypass && git commit."
                    )
                    _log_deviation(_wpg_file_name, tool_name, f"write_pipeline_gate_block:{_wpg_tier}")
                    _log_pretool_activity(tool_name, tool_input, "deny", _wpg_block_reason)
                    output_decision(
                        "deny", _wpg_block_reason,
                        system_message=(
                            f"BLOCKED: Write/Edit to '{_wpg_file_name}' denied (tier: {_wpg_tier}). "
                            f"Run /implement to make changes. "
                            f"Per-repo opt-out: touch .claude/.bypass && git commit."
                        ),
                    )
                    try:
                        _update_deny_cache(file_path)  # telemetry — does NOT prevent multi-Edit bypass
                    except Exception:
                        pass
                    sys.exit(0)
                elif _wpg_tier in ("operator_bypass", "pipeline_active"):
                    # Telemetry: log fast-path allows so we can detect over-bypass.
                    try:
                        _log_pretool_activity(tool_name, tool_input, "allow",
                                              f"write_pipeline_gate: {_wpg_tier}")
                    except Exception:
                        pass

                # Issue #557: Block settings.json writes during active pipeline
                if file_path:
                    fname = Path(file_path).name
                    if fname in ("settings.json", "settings.local.json"):
                        # Issue #1001: template paths are work products
                        # (plugins/*/templates/...) — bypass the guard.
                        if _is_settings_template_path(file_path):
                            pass
                        # Issue #1111: self-maintenance on plugin source — when
                        # we are inside the canonical autonomous-dev tree AND
                        # touching plugins/autonomous-dev/ paths, the maintainer
                        # IS the runtime settings author and the consumer-side
                        # guard does not apply. Tightened (security-auditor LOW,
                        # A01) from a substring check to a component-adjacency
                        # check via _is_plugin_source_path to avoid matching
                        # unrelated paths like /tmp/plugins/autonomous-dev/...
                        elif (
                            _is_self_maintenance_mode()
                            and _is_plugin_source_path(file_path)
                        ):
                            pass
                        else:
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
                            _pq_existing = ""  # Pre-edit content (empty for Write)
                            _pq_is_edit = False
                            if tool_name == "Write":
                                _pq_content = tool_input.get("content", "")
                            elif tool_name == "Edit":
                                _pq_is_edit = True
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
                                    _pq_existing = ""

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
                                            # Issue #1038: Make Edit checks diff-aware so
                                            # pre-existing oversized sections / pre-existing
                                            # persona/casual phrases do not block edits that
                                            # don't touch them.  Write (full overwrite) uses
                                            # the standard check — everything is "new".
                                            if _pq_is_edit and _pq_existing:
                                                _pre_persona = set(
                                                    _pq_mod.check_persona(_pq_existing)
                                                )
                                                _pre_casual = set(
                                                    _pq_mod.check_casual_register(_pq_existing)
                                                )
                                                _new_persona = [
                                                    v
                                                    for v in _pq_mod.check_persona(_pq_content)
                                                    if v not in _pre_persona
                                                ]
                                                _new_casual = [
                                                    v
                                                    for v in _pq_mod.check_casual_register(
                                                        _pq_content
                                                    )
                                                    if v not in _pre_casual
                                                ]
                                                _new_density = (
                                                    _pq_mod.check_constraint_density_diff(
                                                        _pq_existing,
                                                        _pq_content,
                                                        threshold=_pq_density_threshold,
                                                    )
                                                )
                                                _pq_violations = (
                                                    _new_persona + _new_casual + _new_density
                                                )
                                            else:
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
                    # Phase 1 (Issue #1142+): Bash-to-code-file gate.
                    # Mirror the default-on Write/Edit gate above for Bash
                    # commands that write to code files (cat>, sed -i, tee,
                    # heredocs, python -c open(), awk redirect, base64 -d).
                    # User-driven patch tooling (`git apply`, `patch < diff`)
                    # is excluded by the detector. The gate respects the
                    # universal `.claude/.bypass` (checked at line ~4532
                    # earlier) and the one-shot operator bypass.
                    try:
                        # Phase 2 (Issue #1146): pass session_id for symmetry.
                        # #1171: sanitize untrusted env-var before use.
                        _b2b_session_id = _resolve_session_id_safe(_session_id)
                        (
                            _b2b_block,
                            _b2b_tier,
                            _b2b_directive,
                            _b2b_target,
                        ) = _check_bash_code_file_pipeline_required(
                            command, session_id=_b2b_session_id
                        )
                    except Exception:
                        _b2b_block = False
                        _b2b_tier = "wpg_check_error"
                        _b2b_directive = ""
                        _b2b_target = ""
                    if _b2b_block:
                        _b2b_basename = Path(_b2b_target).name if _b2b_target else "unknown"
                        _b2b_reason = (
                            f"BLOCKED: Bash command writes to code file '{_b2b_basename}' "
                            f"which requires the /implement pipeline. "
                            f"File: {_b2b_target} "
                            f"Tier: {_b2b_tier}. "
                            f"REQUIRED NEXT ACTION: {_b2b_directive} "
                            f"Per-repo opt-out: touch .claude/.bypass && git commit."
                        )
                        _log_deviation(_b2b_basename, tool_name, f"bash_code_file_gate_block:{_b2b_tier}")
                        _log_pretool_activity(tool_name, tool_input, "deny", _b2b_reason)
                        output_decision(
                            "deny", _b2b_reason,
                            system_message=(
                                f"BLOCKED: Bash write to code file '{_b2b_basename}' denied (tier: {_b2b_tier}). "
                                f"Run /implement to make changes. "
                                f"Per-repo opt-out: touch .claude/.bypass && git commit."
                            ),
                        )
                        try:
                            _update_deny_cache(_b2b_target)
                        except Exception:
                            pass
                        sys.exit(0)

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

                    # Issue #1008: rm -rf with unresolved (unquoted) variable
                    # expansion. ALWAYS fires (hard-floor) regardless of pipeline
                    # status — `rm -rf $UNSET_VAR/path` expanding to `rm -rf /path`
                    # is catastrophic in any session mode. Fires BEFORE the
                    # state-deletion guard because it is a stronger gate.
                    try:
                        _rm_rf_var = _check_rm_rf_unresolved_vars(command)
                        if _rm_rf_var is not None:
                            _rrv_decision, _rrv_reason = _rm_rf_var
                            _log_deviation(
                                "rm_rf_unresolved_var", tool_name,
                                "rm_rf_unresolved_var_block",
                            )
                            _log_pretool_activity(tool_name, tool_input, "deny", _rrv_reason)
                            output_decision(
                                _rrv_decision, _rrv_reason,
                                system_message=(
                                    "BLOCKED: rm -rf with unquoted variable. "
                                    "Quote the variable to avoid catastrophic deletion."
                                ),
                            )
                            sys.exit(0)
                    except SystemExit:
                        raise
                    except Exception:
                        pass  # Fail-open: never block on detection errors

                    # Issue #803: Pipeline state file deletion guard.
                    # Block rm/unlink/truncate of pipeline state files during active pipeline.
                    # Issue #865: Allow cleanup when PIPELINE_CLEANUP_PHASE is set
                    # (STEP 15 / STEP B4 cleanup authorized by coordinator)
                    # Issue #1083: Allow cleanup in self-maintenance mode (autonomous-dev
                    # source repo). Mid-session env-var bypasses don't propagate to hook
                    # subprocesses (Issue #779), so maintainers working on the framework
                    # itself were deadlocked when a /implement session left stuck state.
                    try:
                        _cleanup_phase = os.getenv("PIPELINE_CLEANUP_PHASE", "").lower()
                        _state_del = _check_bash_state_deletion(command)
                        _self_maint = _is_self_maintenance_mode()
                        if (
                            _state_del is not None
                            and _cleanup_phase not in ("1", "true")
                            and not _self_maint
                            and _is_pipeline_active()
                        ):
                            _sd_reason = (
                                f"BLOCKED: {_state_del[1]} "
                                f"File: {_state_del[0]}. "
                                f"REQUIRED NEXT ACTION: Do NOT delete pipeline state files "
                                f"during an active /implement session. "
                                f"BYPASS (in order of reliability): "
                                f"(1) `touch .claude/.bypass` then retry — file-based, "
                                f"works mid-session; (2) export PIPELINE_CLEANUP_PHASE=1 "
                                f"BEFORE launching claude (env vars don't propagate "
                                f"mid-session — Issue #779)."
                            )
                            _log_deviation(_state_del[0], tool_name, "state_file_deletion_block")
                            _log_pretool_activity(tool_name, tool_input, "deny", _sd_reason)
                            output_decision(
                                "deny", _sd_reason,
                                system_message="BLOCKED: Pipeline state file deletion during active pipeline.",
                            )
                            sys.exit(0)
                        elif _state_del is not None and _self_maint and _is_pipeline_active():
                            # Log the relaxation for the audit trail (Issue #1083).
                            _log_pretool_activity(
                                tool_name, tool_input, "allow",
                                "self-maintenance: state cleanup permitted (autonomous-dev source repo)"
                            )
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
                        # Issue #970: recovery telemetry for env-var spoofing block.
                        log_block_with_recovery(
                            hook_name="unified_pre_tool.py",
                            tool_name=tool_name,
                            block_reason=spoof_reason,
                            recovery_hint=(
                                "Remove the protected env-var override from your command. "
                                "Set the variable in your shell profile if persistence is "
                                "needed. To bypass enforcement: AUTONOMOUS_DEV_BYPASS=1."
                            ),
                        )
                        output_decision(
                            "deny", spoof_reason,
                            system_message="BLOCKED: Protected environment variable cannot be overridden.",
                        )
                        sys.exit(0)

                    # Issue #627: Block direct creation of gh issue marker file
                    marker_block = _detect_gh_issue_marker_creation(command)
                    if marker_block:
                        # Issue #953: Downgrade deny → warning when /create-issue
                        # is not registered. Otherwise the user is wedged.
                        if not _hook_command_registered("create-issue"):
                            print(
                                f"[hook warning] Would block ({marker_block}) but "
                                f"/create-issue is not registered; allowing direct call. "
                                f"Re-register: /plugin install autonomous-dev@autonomous-dev",
                                file=sys.stderr,
                            )
                            # Fall through — do not deny.
                        else:
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
                        # Issue #953: Downgrade deny → warning when /create-issue
                        # is not registered. Otherwise the user is wedged.
                        if not _hook_command_registered("create-issue"):
                            print(
                                f"[hook warning] Would block ({gh_block}) but "
                                f"/create-issue is not registered; allowing direct call. "
                                f"Re-register: /plugin install autonomous-dev@autonomous-dev",
                                file=sys.stderr,
                            )
                            # Fall through — do not deny.
                        else:
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

                    # Issue #1139: Warn when git stash is used mid-pipeline without
                    # a recorded baseline_cmd.  Advisory only — NEVER blocks.
                    try:
                        _gs_cmd = command.lstrip()
                        # Strip leading VAR=val env prefixes (e.g. "FOO=bar git stash ...")
                        while _gs_cmd and "=" in _gs_cmd.split(" ", 1)[0] and "/" not in _gs_cmd.split(" ", 1)[0]:
                            _gs_cmd = _gs_cmd.split(" ", 1)[1] if " " in _gs_cmd else ""
                        if _gs_cmd.startswith("git stash"):
                            _gs_state_path = os.environ.get(
                                "PIPELINE_STATE_FILE",
                                str(get_legacy_sentinel_path()),
                            )
                            if Path(_gs_state_path).exists():
                                _bg_lib_dir = Path(__file__).resolve().parent.parent / "lib"
                                _bg_spec = importlib.util.spec_from_file_location(
                                    "baseline_guardrail",
                                    str(_bg_lib_dir / "baseline_guardrail.py"),
                                )
                                if _bg_spec and _bg_spec.loader:
                                    _bg_mod = importlib.util.module_from_spec(_bg_spec)
                                    _bg_spec.loader.exec_module(_bg_mod)
                                    _bg_mod.warn_if_baseline_missing(_gs_state_path)
                    except Exception:
                        pass  # Never block the hook on guardrail errors

                    # Issue #712: Batch CIA completion gate
                    # Block git commit in batch worktrees when issues are missing CIA
                    # Phase E (Issue #999): session-mode wrap — low-risk
                    # classes skip this commit gate.
                    if "git commit" in command or "git -c" in command and "commit" in command:
                        _phase_e_cia = _phase_e_skip(
                            "_check_batch_cia_completions",
                            input_data=input_data,
                            session_id=_session_id,
                        )
                        if _phase_e_cia is None or not _phase_e_cia[0]:
                            try:
                                cwd = os.getcwd()
                                if _is_batch_context(cwd):
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
                    # Phase E (Issue #999): session-mode wrap.
                    if "git commit" in command or "git -c" in command and "commit" in command:
                        _phase_e_dm = _phase_e_skip(
                            "_check_batch_doc_master_completions",
                            input_data=input_data,
                            session_id=_session_id,
                        )
                        if _phase_e_dm is None or not _phase_e_dm[0]:
                            try:
                                cwd = os.getcwd()
                                if _is_batch_context(cwd):
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
                    # Phase E (Issue #999): session-mode wrap.
                    _phase_e_pa = _phase_e_skip(
                        "_check_pipeline_agent_completions",
                        input_data=input_data,
                        session_id=_session_id,
                    )
                    if ("git commit" in command or "git -c" in command and "commit" in command) and (
                        _phase_e_pa is None or not _phase_e_pa[0]
                    ):
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
                                # NOTE(#1177-followup): env-var read here may also be dead; audit deferred.
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
                                    if _is_batch_context(cwd):
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
                                                # #1177: env-var handled internally by
                                                # _get_pipeline_mode_from_state() since #1173 — outer
                                                # `os.environ.get("PIPELINE_MODE") or ...` was dead.
                                                _batch_agent_pipeline_mode = _get_pipeline_mode_from_state()
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
                                                        f"BYPASS (in order of reliability): "
                                                        f"(1) `touch /tmp/skip_agent_completeness_gate` as a SEPARATE command first, "
                                                        f"then retry the commit — file-based, works mid-session "
                                                        f"(chaining with && WILL NOT WORK — the hook intercepts compound commands before touch executes); "
                                                        f"(2) export SKIP_AGENT_COMPLETENESS_GATE=1 BEFORE launching claude "
                                                        f"(env vars don't propagate mid-session — Issue #779). (Issue #853)"
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
                        # Issue #970: recovery telemetry for #528 workflow enforcement.
                        log_block_with_recovery(
                            hook_name="unified_pre_tool.py",
                            tool_name=tool_name,
                            block_reason=block_reason,
                            recovery_hint=(
                                "Delegate the change to a pipeline agent (implementer, "
                                "test-master, doc-master) via the Task tool. To bypass for "
                                "an emergency direct-edit: set ENFORCEMENT_LEVEL=off or "
                                "AUTONOMOUS_DEV_BYPASS=1."
                            ),
                        )
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
                    # Issue #1178: paired block + recovery telemetry. Generate a
                    # uuid4 block_event_id and capture a UTC anchor timestamp;
                    # the recovery path joins back via the same id and computes
                    # latency from this anchor.
                    import uuid as _uuid
                    from datetime import datetime as _dt, timezone as _tz
                    _pi_agent_type = tool_input.get("subagent_type", "")
                    _block_event_id = str(_uuid.uuid4())
                    _block_ts_iso = _dt.now(_tz.utc).isoformat()
                    _pi_reason_lower = pi_reason.lower() if isinstance(pi_reason, str) else ""
                    _category = next(
                        (cat for substr, cat in _PI_CATEGORY_MAP if substr in _pi_reason_lower),
                        "other",
                    )
                    _shrink_pct, _baseline_w, _current_w = _parse_pi_numerics(pi_reason)
                    _emit_prompt_integrity_event(
                        _PI_BLOCK_EVENT_TYPE,
                        agent_type=_pi_agent_type,
                        block_event_id=_block_event_id,
                        timestamp=_block_ts_iso,
                        block_reason_category=_category,
                        shrinkage_pct=_shrink_pct,
                        baseline_words=_baseline_w,
                        current_words=_current_w,
                        retry_count=0,
                        block_reason_detail=pi_reason,
                    )
                    # Issue #750: Record denial so subsequent Write/Edit workarounds are blocked.
                    # Issue #1178: persist block_event_id + ISO anchor for the recovery emission.
                    _record_agent_denial(
                        _pi_agent_type,
                        block_event_id=_block_event_id,
                        block_timestamp_iso=_block_ts_iso,
                    )
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

            # Layer 5 (continued): Prompt-integrity recovery emission (Issue #1178).
            # If we reach this point with an Agent dispatch, pi_decision != "deny"
            # (the deny branch sys.exit'd above). If a denial record exists for the
            # same agent_type in this session, this dispatch IS the recovery — emit
            # the paired recovery row and consume the state file to enforce the
            # single-emit invariant.
            if tool_name in AGENT_TOOL_NAMES:
                _denial_record = _read_agent_denial_record()
                if _denial_record and _denial_record.get("agent_type") == tool_input.get(
                    "subagent_type", ""
                ):
                    from datetime import datetime as _dt, timezone as _tz
                    _block_ts_iso = _denial_record.get("block_timestamp_iso")
                    _block_event_id = _denial_record.get("block_event_id")
                    if _block_ts_iso and _block_event_id:
                        _now = _dt.now(_tz.utc)
                        try:
                            _block_dt = _dt.fromisoformat(_block_ts_iso)
                            _latency_ms = int((_now - _block_dt).total_seconds() * 1000)
                        except Exception:
                            _latency_ms = None
                        _emit_prompt_integrity_event(
                            _PI_RECOVERY_EVENT_TYPE,
                            agent_type=_denial_record.get("agent_type", ""),
                            block_event_id=_block_event_id,
                            timestamp=_now.isoformat(),
                            recovery_strategy="template_reload+reconstruct",
                            retry_count=1,
                            latency_ms_from_block_to_recovery=_latency_ms,
                        )
                        _consume_agent_denial_record()  # single-emit invariant

            # Run extensions even for native tools
            ext_decision, ext_reason = _run_extensions(tool_name, tool_input)
            if ext_decision == "deny":
                _log_pretool_activity(tool_name, tool_input, "deny", ext_reason)
                # Issue #970: emit recovery hint for blocks raised by extensions.
                log_block_with_recovery(
                    hook_name="unified_pre_tool.py",
                    tool_name=tool_name,
                    block_reason=ext_reason,
                    recovery_hint=(
                        "Review the extension that raised this deny. To temporarily disable "
                        "all hooks: set AUTONOMOUS_DEV_BYPASS=1 or `touch .claude/.bypass`. "
                        "See docs/TROUBLESHOOTING.md (#970)."
                    ),
                )
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
        # Phase E (Issue #999): session-mode wrap. Hard-floor checks are
        # NOT wrapped; this is a non-hard-floor gate.
        _phase_e_mcp = _phase_e_skip(
            "_check_plan_exit_mcp",
            input_data=input_data,
            session_id=_session_id,
        )
        if _phase_e_mcp is None or not _phase_e_mcp[0]:
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



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = Path(__file__).name


def _timed_main():
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _hook_safe_main(_timed_main)
