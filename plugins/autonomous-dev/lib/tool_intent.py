"""Shell command and tool-call intent classifier (Issue #971).

Provides a single, principled classifier that decides whether a tool call is a
READ, WRITE, or EXEC operation, and extracts the file paths it would write to.

Replaces ad-hoc substring matching against command strings with a proper
shell-aware classifier that handles:

- Native Claude Code tools (Read/Write/Edit/Glob/Grep/...) by tool name dispatch
- Bash commands via ``shlex.split`` — env-var prefixes, redirections,
  pipes, sequential operators, and ``bash -c`` / ``sh -c`` recursion
- ``python -c`` snippets via the AST-based ``python_write_detector`` library

The module is consumed by ``unified_pre_tool.py`` (settings-write protection,
infrastructure protection) and by ``scripts/audit_tool_intent_coverage.py``
(CI gate for tool-name coverage).

Design principles:
- Conservative: false negatives are acceptable; false positives are not.
  When in doubt, return EXEC + [] so the existing path-substring logic in
  the hook continues to apply (no regression vs. pre-Issue #971 behavior).
- Defensive: never raise — every error path returns a safe default.
- Composable: ``classify`` and ``write_targets`` are pure functions of inputs.

Issue #1503 widened the module to be TRANSPORT-INDEPENDENT: enforcement sites
previously asked ``tool_name in ("Write", "Edit")``, which let MultiEdit,
NotebookEdit, and every MCP editor (serena et al.) walk straight through the
Issue #1435 protected-infrastructure hard floor. ``is_write`` and
``changed_content`` are the canonical answers to "is this a write?" and "what
content does it write?" for every enforcement site.

Public API:
    classify(tool_name, tool_input) -> Literal["READ","WRITE","EXEC"]
    write_targets(tool_name, tool_input) -> List[str]
    is_write(tool_name, tool_input) -> bool
    changed_content(tool_name, tool_input) -> str
    may_be_declared_optional(tool_name) -> bool
    has_suspicious_exec(command) -> bool

Constants:
    READ_TOOLS, WRITE_TOOLS — native tool name sets
    MCP_READ_TOOLS, MCP_WRITE_TOOLS — MCP tool name registries (#1503)
    MCP_OPTIONAL_DECLARABLE_TOOLS — agent ``optional_mcp:`` allowlist (#1546)
    PATH_KEYS, CONTENT_KEYS — tool_input key names used by the shape fallback
    BASH_READ_BINS, BASH_WRITE_BINS — common shell utilities
"""

from __future__ import annotations

import importlib.util
import re
import shlex
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

try:
    from typing import Literal
    Intent = Literal["READ", "WRITE", "EXEC"]
except ImportError:  # pragma: no cover — Python <3.8 not supported
    Intent = str  # type: ignore[misc,assignment]

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Native Claude Code tools that only read.
READ_TOOLS: Set[str] = {"Read", "Glob", "Grep", "NotebookRead"}

# Native Claude Code tools that write/modify files.
WRITE_TOOLS: Set[str] = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# ---------------------------------------------------------------------------
# MCP tool registries (Issue #1503)
# ---------------------------------------------------------------------------
#
# CRITICAL DESIGN CONSTRAINT (relocated verbatim from the
# ``_PLAN_EXIT_MCP_READONLY`` comment in unified_pre_tool.py, which this
# registry supersedes):
#
#   "Structural (regex-based) heuristics are forbidden because they produce
#    false-negatives (e.g., "find_and_replace" contains "find" but is a write)."
#
# The registries below are therefore EXPLICIT and authoritative. The
# path+content shape test in ``_looks_like_write`` is ONLY a fail-closed
# fallback for tools that are not registered at all — it is never consulted
# for a registered tool.
#
# The registry is load-bearing rather than belt-and-braces: four verified
# serena writers carry NO content argument at all, so the shape fallback
# provably cannot catch them (a deletion or a rename has nothing to
# shape-match on):
#   replace_in_files    relative_path defaults to "" — no REQUIRED path
#   rename_symbol       (name_path, relative_path, new_name) — no content key
#   safe_delete_symbol  (name_path_pattern, relative_path) — no content key
#   delete_lines        (relative_path, start_line, end_line) — no content key

# MCP tools that only read. Strict SUPERSET of the legacy
# ``_PLAN_EXIT_MCP_READONLY`` frozenset that used to live in
# unified_pre_tool.py (all 24 entries copied verbatim), plus the serena
# read-side surface.
#
# AC #19: mcp__playwright__browser_evaluate MUST NOT appear here — it
# executes arbitrary JS in the browser and is therefore not read-only.
MCP_READ_TOOLS: "frozenset[str]" = frozenset({
    # --- Legacy _PLAN_EXIT_MCP_READONLY (24 entries, verbatim) -------------
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
    # --- serena (LSP) read surface (Issue #1503) --------------------------
    # Several of these are excluded in the ide-assistant context today (via
    # claude-code.yml excluded_tools, and get_diagnostics_for_symbol via a
    # ToolMarkerOptional default-off marker). They are registered defensively
    # so that enabling them later cannot reopen the hole.
    "mcp__serena__find_symbol",
    "mcp__serena__find_referencing_symbols",
    "mcp__serena__find_declaration",
    "mcp__serena__find_implementations",
    "mcp__serena__get_symbols_overview",
    "mcp__serena__get_diagnostics_for_file",
    "mcp__serena__get_diagnostics_for_symbol",
    "mcp__serena__read_memory",
    "mcp__serena__list_memories",
    "mcp__serena__initial_instructions",
    "mcp__serena__onboarding",
    "mcp__serena__read_file",
    "mcp__serena__list_dir",
    "mcp__serena__find_file",
    "mcp__serena__search_for_pattern",
})

# MCP tools that mutate files or persisted state.
MCP_WRITE_TOOLS: "frozenset[str]" = frozenset({
    # serena — symbol/content editors
    "mcp__serena__replace_symbol_body",
    "mcp__serena__insert_after_symbol",
    "mcp__serena__insert_before_symbol",
    "mcp__serena__replace_content",
    "mcp__serena__replace_in_files",
    "mcp__serena__rename_symbol",
    "mcp__serena__safe_delete_symbol",
    "mcp__serena__delete_lines",
    "mcp__serena__create_text_file",
    "mcp__serena__insert_at_line",
    # serena — memory writers
    "mcp__serena__write_memory",
    "mcp__serena__edit_memory",
    "mcp__serena__delete_memory",
    "mcp__serena__rename_memory",
})

# MCP tools an agent MAY name under the ``optional_mcp:`` frontmatter key --
# a POSITIVE allowlist of reviewed tools whose effect is bounded and
# enumerable, which neither mutate the local filesystem nor execute
# caller-supplied code.
#
# WHY A THIRD REGISTRY (Issue #1546). ``optional_mcp:`` entries were checked
# against MCP_WRITE_TOOLS and against a wildcard ban, but never against any
# allowlist. Any concrete token from a server with zero MCP_WRITE_TOOLS
# entries therefore passed every invariant with zero violations, regardless
# of what the tool actually did. ``optional_mcp:`` grants no capability, but
# it is not inert: it licenses the agent's prose to ATTEMPT the tool, and
# unified_pre_tool.py default-allows every ``mcp__*`` call, so the attempt
# succeeds whenever the user happens to have that server installed.
#
# The weaker rule "every declared tool must be CLASSIFIED" does NOT close
# this. ``mcp__playwright__browser_evaluate`` is already classified today --
# scripts/audit_tool_intent_coverage.py lists it in MCP_KNOWN_EXEC_TOOLS --
# and it must still be refused. Declarability is its own allowlist, not a
# corollary of classification.
#
# NOT the same set as MCP_KNOWN_EXEC_TOOLS in
# scripts/audit_tool_intent_coverage.py. That set answers "has anyone
# classified this tool name we observed in the activity logs?" and
# deliberately INCLUDES browser_evaluate. This set answers "may an agent be
# instructed to attempt this tool?" and deliberately EXCLUDES it. The two
# have different purposes and different membership -- do not merge them.
#
# NOT consulted by ``classify()``. Every member is READ or EXEC in this
# module's three-intent vocabulary, and ``classify`` already returns EXEC by
# fallthrough. A branch placed AHEAD of the fail-closed ``_looks_like_write``
# shape test would disable that fallback for members; a branch placed AFTER
# it would be dead code. Membership here confers no runtime authority -- and
# that is exactly why a plausibly-read-only tool whose surface we cannot
# verify belongs here rather than in MCP_READ_TOOLS, whose membership DOES
# grant plan-exit passage in unified_pre_tool.py.
#
# Appium caveat: no appium MCP server is configured in this repo (.mcp.json
# lists serena only), so the appium classifications below are judgements
# derived from WebDriver protocol semantics, NOT from an inspected tool
# schema. They are held out of MCP_READ_TOOLS for that reason.
MCP_OPTIONAL_DECLARABLE_TOOLS: "frozenset[str]" = frozenset({
    # --- appium (mobile-tester) ------------------------------------------
    # MUTATES device state: dispatches a touch event to the app under test.
    "mcp__appium__tap",
    # MUTATES device state: dispatches keystrokes to the focused element.
    "mcp__appium__type",
    # Observation only (stated judgement, not a guess): resolves a locator to
    # an element handle. WebDriver findElement performs no input and changes
    # no user-visible state; it does populate a server-side element cache,
    # which is bookkeeping rather than state mutation.
    "mcp__appium__find_element",
    # Observation only: captures the current screen. Same shape as
    # mcp__playwright__browser_take_screenshot, already in MCP_READ_TOOLS.
    "mcp__appium__screenshot",
    # Observation only: returns the session id and negotiated capabilities.
    "mcp__appium__get_session",
    # --- playwright (ui-tester, reviewer) --------------------------------
    # EFFECTFUL but bounded (stated judgement, not a guess): loads one
    # caller-named URL. Navigation is not an observation -- the request can
    # trigger arbitrary side effects on the remote server -- so it does not
    # belong in MCP_READ_TOOLS. It executes no caller-supplied code and
    # touches no local file, so it is not a writer either.
    "mcp__playwright__browser_navigate",
    # mcp__playwright__browser_snapshot is deliberately NOT repeated here:
    # it is already in MCP_READ_TOOLS and the declarability rule accepts the
    # UNION of the two sets. The registries are kept disjoint.
    #
    # DELIBERATELY ABSENT: mcp__playwright__browser_evaluate. It executes
    # caller-supplied JavaScript, so no availability check can bound its
    # effect. See the AC #19 exclusion note on MCP_READ_TOOLS above.
})

# tool_input keys that may carry a filesystem target, in resolution order.
PATH_KEYS: "tuple[str, ...]" = ("file_path", "notebook_path", "relative_path", "path")

# tool_input keys that may carry the content being written, in resolution
# order. Verified against the real tool schemas:
#   replace_content / replace_in_files ........ ``repl``   (NOT ``content``)
#   replace_symbol_body / insert_*_symbol ..... ``body``
#   NotebookEdit .............................. ``new_source``
# Deliberately EXCLUDED: ``url`` / ``prompt`` (WebFetch is not a filesystem
# path) and ``subject`` / ``to`` (mcp__ms365__send-mail carries ``body`` but
# NO path key, so the both-keys conjunction below keeps it EXEC).
CONTENT_KEYS: "tuple[str, ...]" = ("content", "new_string", "body", "repl", "new_source")

# Common shell binaries that only read.
BASH_READ_BINS: Set[str] = {
    "cat", "grep", "rg", "head", "tail", "less", "more", "wc",
    "jq", "sort", "uniq", "diff", "file", "stat", "ls", "tree",
    "echo", "printf",
}

# Common shell binaries that write/modify files.
BASH_WRITE_BINS: Set[str] = {
    "rm", "rmdir", "mv", "cp", "tee", "truncate", "dd", "touch",
    "install", "ln", "mkdir", "chmod", "chown",
}

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Shells that recurse via -c "<cmd>".
_BASH_RECURSIVE_BINS: Set[str] = {"bash", "sh", "zsh"}

# Env-prefix wrappers (the binary that follows is the real command).
_BASH_ENV_PREFIXES: Set[str] = {"env"}

# Python interpreters that may run inline code via -c.
_BASH_PYTHON_BINS: Set[str] = {
    "python", "python3", "python3.11", "python3.12", "python3.13",
}

# Maximum recursion depth for nested ``bash -c`` / ``sh -c``.
_MAX_RECURSION_DEPTH: int = 3

# Maximum command length we will attempt to classify (DoS guard).
_MAX_COMMAND_LENGTH: int = 64_000

# Env-var assignment prefix (e.g. ``FOO=bar``).
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Patterns for python -c "<snippet>" / 'snippet' inside a single shell token.
# These run on the RAW command string (post env-prefix stripping is not
# meaningful here — we want the raw quoted snippet body).
_PY_C_DOUBLE = re.compile(r'python(?:[\d.]*)?\s+-c\s+"([^"]+)"')
_PY_C_SINGLE = re.compile(r"python(?:[\d.]*)?\s+-c\s+'([^']+)'")

# python heredoc: ``python3 << EOF ... EOF``.
_PY_HEREDOC_HEAD = re.compile(r'python(?:[\d.]*)?\s+.*?<<\s*[\'"]?(\w+)[\'"]?')

# ---------------------------------------------------------------------------
# Defensive import of python_write_detector
# ---------------------------------------------------------------------------

# Mirrors the loader pattern in unified_pre_tool.py:78-97 so that this module
# is importable from any of: tests, the hook, or the audit script.
_pwd = None
try:
    _here = Path(__file__).resolve().parent
    _detector_candidates = [
        _here / "python_write_detector.py",                    # same directory
        _here.parent / "lib" / "python_write_detector.py",     # parent/lib
        _here.parents[2] / "lib" / "python_write_detector.py", # fallback
    ]
    for _candidate in _detector_candidates:
        if _candidate.exists():
            _spec = importlib.util.spec_from_file_location(
                "python_write_detector", str(_candidate)
            )
            if _spec and _spec.loader:
                _pwd = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_pwd)
            break
except Exception:  # pragma: no cover — defensive
    _pwd = None


def _suspicious_exec_sentinel() -> Optional[str]:
    """Return the SUSPICIOUS_EXEC_SENTINEL constant, if available."""
    if _pwd is None:
        return None
    return getattr(_pwd, "SUSPICIOUS_EXEC_SENTINEL", None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify(tool_name: str, tool_input: dict) -> Intent:
    """Classify a tool call as READ, WRITE, or EXEC.

    Args:
        tool_name: The tool name (e.g. ``"Bash"``, ``"Read"``).
        tool_input: The tool input dict. For Bash: ``{"command": "..."}``;
            for Read/Write/Edit: ``{"file_path": "..."}``.

    Returns:
        ``"READ"`` for read-only tools/commands, ``"WRITE"`` for tools/commands
        that modify the filesystem, ``"EXEC"`` for everything else
        (orchestration tools, unknown binaries, malformed input).
    """
    if not isinstance(tool_name, str) or not tool_name:
        return "EXEC"

    if tool_name in READ_TOOLS:
        return "READ"

    if tool_name in WRITE_TOOLS:
        return "WRITE"

    if tool_name == "Bash":
        command = ""
        if isinstance(tool_input, dict):
            command = tool_input.get("command", "") or ""
        if not isinstance(command, str) or not command.strip():
            return "EXEC"
        intent, _targets = _classify_bash(command, depth=0)
        return intent

    # --- MCP registries (Issue #1503) — registry FIRST, fallback LAST -------
    if tool_name in MCP_READ_TOOLS:
        return "READ"

    if tool_name in MCP_WRITE_TOOLS:
        return "WRITE"

    # Fail-closed shape fallback for UNREGISTERED tools only: a tool that
    # carries BOTH a filesystem path AND content is writing that content
    # somewhere. The conjunction is what keeps reads unblocked —
    # mcp__serena__find_symbol carries ``relative_path`` but no content
    # argument, so it stays EXEC (and therefore unblocked). Over-correcting
    # into a gate that blocks reads is an explicit failure condition of
    # Issue #1503.
    if _looks_like_write(tool_input):
        return "WRITE"

    # Unknown native tool, MCP tool, orchestration tool — EXEC by default.
    # The hook applies its own per-tool rules to these.
    return "EXEC"


def is_write(tool_name: str, tool_input: dict) -> bool:
    """Return True if a tool call would mutate the filesystem (Issue #1503).

    This is the canonical, TRANSPORT-INDEPENDENT replacement for the
    hard-coded ``tool_name in ("Write", "Edit")`` tests that used to guard
    every enforcement site. Any new file-mutating transport is covered by
    registering it in ``WRITE_TOOLS`` / ``MCP_WRITE_TOOLS`` once, here.

    Args:
        tool_name: The tool name (e.g. ``"NotebookEdit"``,
            ``"mcp__serena__replace_symbol_body"``).
        tool_input: The tool input dict.

    Returns:
        True when the call classifies as ``"WRITE"``. Never raises — any
        malformed input returns False (fail-open on classification errors is
        required because these callers also gate reads).
    """
    try:
        return classify(tool_name, tool_input) == "WRITE"
    except Exception:  # pragma: no cover — defensive; classify never raises
        return False


def changed_content(tool_name: str, tool_input: dict) -> str:
    """Return the content a tool call would write, as a single string.

    Used by complexity gates (e.g. ``plan_gate``'s simple-edit exemption) so
    the exemption is about the CHANGE, not about the TRANSPORT.

    Resolution order:
        1. ``MultiEdit`` — concatenate every ``edits[].new_string``.
        2. The first non-empty value found under ``CONTENT_KEYS``.

    Args:
        tool_name: The tool name.
        tool_input: The tool input dict.

    Returns:
        The content string, or ``""`` when no content key is present or the
        input is malformed. Never raises.
    """
    if not isinstance(tool_input, dict):
        return ""

    try:
        if tool_name == "MultiEdit" or isinstance(tool_input.get("edits"), list):
            parts: List[str] = []
            for edit in tool_input.get("edits") or []:
                if not isinstance(edit, dict):
                    continue
                new_string = edit.get("new_string")
                if isinstance(new_string, str) and new_string:
                    parts.append(new_string)
            if parts:
                return "\n".join(parts)

        for key in CONTENT_KEYS:
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                return value
    except Exception:  # pragma: no cover — defensive
        return ""

    return ""


def may_be_declared_optional(tool_name: str) -> bool:
    """Return True if an agent may name this tool under ``optional_mcp:``.

    The canonical answer to "is this MCP tool declarable?" (Issue #1546).
    Declarable is the UNION of two positive allowlists -- ``MCP_READ_TOOLS``
    (observation, no effect) and ``MCP_OPTIONAL_DECLARABLE_TOOLS`` (reviewed,
    bounded, non-filesystem effect). Everything else is refused, including:

    - unclassified tokens from any server (fail closed on unknown);
    - arbitrary-code-execution tools such as
      ``mcp__playwright__browser_evaluate``, which ARE classified elsewhere
      in the repo but are still not safe to attempt;
    - every ``MCP_WRITE_TOOLS`` member;
    - wildcards, which are not tool names at all.

    An allowlist is used rather than a denylist of dangerous tools for the
    same reason INV-2 is an allowlist: a denylist only refuses what has
    already been noticed, which is precisely how the gap this closes shipped.

    Args:
        tool_name: A fully qualified MCP tool name, e.g.
            ``"mcp__appium__tap"``.

    Returns:
        True when the tool is on either allowlist. False for any other
        value, including non-strings and wildcard patterns. Never raises.
    """
    if not isinstance(tool_name, str) or not tool_name:
        return False
    return (
        tool_name in MCP_READ_TOOLS
        or tool_name in MCP_OPTIONAL_DECLARABLE_TOOLS
    )


def _looks_like_write(tool_input: dict) -> bool:
    """Shape test: does this input carry BOTH a path AND content?

    The fail-closed fallback for tools absent from every registry. Both
    conditions must hold — a path alone is a read (serena's ``find_symbol``
    carries ``relative_path``), and content alone is not a filesystem write
    (``mcp__ms365__send-mail`` carries ``body`` but no path).

    Args:
        tool_input: The tool input dict.

    Returns:
        True when a non-empty string exists under some ``PATH_KEYS`` entry
        AND a non-empty string exists under some ``CONTENT_KEYS`` entry.
    """
    if not isinstance(tool_input, dict):
        return False
    has_path = any(
        isinstance(tool_input.get(k), str) and tool_input.get(k)
        for k in PATH_KEYS
    )
    if not has_path:
        return False
    return any(
        isinstance(tool_input.get(k), str) and tool_input.get(k)
        for k in CONTENT_KEYS
    )


def _first_path(tool_input: dict) -> Optional[str]:
    """Return the first non-empty string value under ``PATH_KEYS``."""
    if not isinstance(tool_input, dict):
        return None
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def write_targets(tool_name: str, tool_input: dict) -> List[str]:
    """Return the list of file paths a tool call would write to.

    For Read/Glob/Grep/NotebookRead: returns ``[]``.
    For Write/Edit/MultiEdit/NotebookEdit: returns the ``file_path`` if set.
    For Bash: walks the command tree and returns all observed write targets.

    The returned list MAY include the ``SUSPICIOUS_EXEC_SENTINEL`` from
    ``python_write_detector`` — callers (e.g. ``_check_bash_infra_writes``)
    inspect this value to apply their own block-escalation rules.

    Args:
        tool_name: The tool name.
        tool_input: The tool input dict.

    Returns:
        List of file path strings. Empty list when no writes are detected
        or when classification fails (false negatives are acceptable).
    """
    if not isinstance(tool_name, str) or not tool_name:
        return []

    if tool_name in READ_TOOLS or tool_name in MCP_READ_TOOLS:
        return []

    if tool_name in WRITE_TOOLS:
        fp = _first_path(tool_input)
        return [fp] if fp else []

    if tool_name == "Bash":
        command = ""
        if isinstance(tool_input, dict):
            command = tool_input.get("command", "") or ""
        if not isinstance(command, str) or not command.strip():
            return []
        _intent, targets = _classify_bash(command, depth=0)
        return targets

    # Issue #1503: MCP writers carry their target under ``relative_path`` or
    # ``path`` rather than ``file_path``. Unregistered tools that pass the
    # fail-closed shape test resolve their target the same way.
    if tool_name in MCP_WRITE_TOOLS or _looks_like_write(tool_input):
        fp = _first_path(tool_input)
        return [fp] if fp else []

    return []


def has_suspicious_exec(command: str) -> bool:
    """Return True if a Bash command contains exec/eval with dynamic args.

    Used by ``_check_bash_infra_writes`` to apply its block-escalation path
    when a python ``-c`` snippet uses ``exec(variable)`` near a protected
    path segment.

    Args:
        command: The Bash command string to inspect.

    Returns:
        True if the SUSPICIOUS_EXEC_SENTINEL is among the write targets.
    """
    if not isinstance(command, str) or not command.strip():
        return False
    sentinel = _suspicious_exec_sentinel()
    if sentinel is None:
        return False
    try:
        _intent, targets = _classify_bash(command, depth=0)
    except Exception:
        return False
    return sentinel in targets


# ---------------------------------------------------------------------------
# Bash classification
# ---------------------------------------------------------------------------


def _classify_bash(command: str, *, depth: int) -> Tuple[Intent, List[str]]:
    """Classify a Bash command and return (intent, write_targets).

    Walks pipes, sequential operators, redirections, env prefixes, nested
    shells, and python ``-c`` snippets.

    Args:
        command: The shell command string.
        depth: Current recursion depth (for ``bash -c`` nesting).

    Returns:
        A tuple of (intent, list of write target paths). Returns
        ``("EXEC", [])`` for any malformed/unparseable input.
    """
    if depth > _MAX_RECURSION_DEPTH:
        return ("EXEC", [])
    if not isinstance(command, str):
        return ("EXEC", [])
    if len(command) > _MAX_COMMAND_LENGTH:
        try:
            sys.stderr.write(
                f"tool_intent: command exceeds max length "
                f"({len(command)} > {_MAX_COMMAND_LENGTH}); classifying as EXEC\n"
            )
        except Exception:
            pass
        return ("EXEC", [])

    # Scan the raw command for python -c snippets and python heredocs FIRST.
    # These bypass shlex token splitting on quoted bodies (shlex would split
    # the inner code into tokens, losing structure for AST analysis).
    py_snippets = _extract_python_snippets(command)
    py_targets: List[str] = []
    py_intent_is_write = False
    for snippet in py_snippets:
        snip_intent, snip_targets = _classify_python_inline(snippet)
        if snip_intent == "WRITE":
            py_intent_is_write = True
        py_targets.extend(snip_targets)

    # Split the raw command on sequential operators (;, &&, ||) BEFORE
    # shlex tokenisation. shlex.split treats ``;`` as part of the previous
    # token in posix mode, so we must split first, then tokenise per segment.
    raw_segments = _split_sequential_raw(command)

    overall_intent: Optional[Intent] = "WRITE" if py_intent_is_write else None
    overall_targets: List[str] = list(py_targets)

    for raw_seg in raw_segments:
        if not raw_seg.strip():
            continue
        try:
            tokens = shlex.split(raw_seg, posix=True, comments=False)
        except ValueError:
            # Malformed quoting in this segment — skip but keep going.
            continue
        if not tokens:
            continue
        seg_intent, seg_targets = _classify_segment(tokens, depth=depth)
        overall_targets.extend(seg_targets)
        if seg_intent == "WRITE":
            overall_intent = "WRITE"
        elif seg_intent == "READ":
            if overall_intent is None or overall_intent == "EXEC":
                overall_intent = "READ"
        elif seg_intent == "EXEC":
            if overall_intent is None:
                overall_intent = "EXEC"

    if overall_intent is None:
        return ("EXEC", overall_targets)
    return (overall_intent, overall_targets)


def _split_sequential_raw(command: str) -> List[str]:
    """Split a raw command string on sequential shell operators (``;``, ``&&``, ``||``).

    Respects single/double quotes — operators inside quoted strings are not
    split points. Backslash-escaped operators are also preserved.
    """
    segments: List[str] = []
    buf: List[str] = []
    i = 0
    n = len(command)
    in_single = False
    in_double = False
    while i < n:
        c = command[i]
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(command[i + 1])
            i += 2
            continue
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
        if not in_single and not in_double:
            # Operators: ;, &&, ||, & (background)
            if c == ";":
                segments.append("".join(buf))
                buf = []
                i += 1
                continue
            if c == "&" and i + 1 < n and command[i + 1] == "&":
                segments.append("".join(buf))
                buf = []
                i += 2
                continue
            if c == "|" and i + 1 < n and command[i + 1] == "|":
                segments.append("".join(buf))
                buf = []
                i += 2
                continue
            # Bare ``&`` (background) — treat as segment break.
            if c == "&" and (i + 1 >= n or command[i + 1] not in ("&", ">")):
                segments.append("".join(buf))
                buf = []
                i += 1
                continue
        buf.append(c)
        i += 1
    if buf:
        segments.append("".join(buf))
    return segments


def _classify_segment(tokens: List[str], *, depth: int) -> Tuple[Intent, List[str]]:
    """Classify a single command segment (no ; / && / || at this level)."""
    # Split on pipes — classify each pipe stage independently.
    pipe_stages = _split_pipes(tokens)
    overall_intent: Intent = "READ"
    overall_targets: List[str] = []
    classified_any = False

    for stage in pipe_stages:
        if not stage:
            continue
        # Extract redirections from the stage; remaining tokens are the command.
        cleaned, redirect_targets = _extract_redirections(stage)
        if redirect_targets:
            overall_targets.extend(redirect_targets)
            overall_intent = "WRITE"
            classified_any = True
        if not cleaned:
            continue
        stage_intent, stage_targets = _classify_command_tokens(
            cleaned, depth=depth
        )
        overall_targets.extend(stage_targets)
        if stage_intent == "WRITE":
            overall_intent = "WRITE"
            classified_any = True
        elif stage_intent == "READ" and overall_intent != "WRITE":
            overall_intent = "READ"
            classified_any = True
        elif stage_intent == "EXEC" and overall_intent != "WRITE":
            if not classified_any:
                overall_intent = "EXEC"

    if not classified_any and not overall_targets:
        return ("EXEC", [])
    return (overall_intent, overall_targets)


def _split_pipes(tokens: List[str]) -> List[List[str]]:
    """Split a token list on the ``|`` pipe operator."""
    stages: List[List[str]] = []
    current: List[str] = []
    for tok in tokens:
        if tok == "|" or tok == "|&":
            if current:
                stages.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        stages.append(current)
    return stages


def _extract_redirections(tokens: List[str]) -> Tuple[List[str], List[str]]:
    """Extract write redirections from a token list.

    Recognises ``>``, ``>>``, ``&>``, ``&>>``, ``N>``, ``N>>`` (where N>0
    is a numeric fd), and the ``cat <<EOF > file`` heredoc-then-redirect
    pattern. Stderr-only redirections (``2>``, ``2>>``) are NOT treated as
    write targets for our purposes; the hook does not protect stderr files.

    Args:
        tokens: A list of shell tokens (one segment, no pipes/sequencers).

    Returns:
        A tuple of (cleaned_tokens, write_target_paths).
    """
    cleaned: List[str] = []
    targets: List[str] = []
    skip_next = False

    for i, tok in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue

        # Stderr-only redirections we deliberately ignore.
        if tok in ("2>", "2>>"):
            skip_next = True
            continue
        # The fd-merge form ``2>&1`` is not a file write.
        if tok == "2>&1" or tok == "1>&2":
            continue

        # Plain redirections (>, >>, &>, &>>) and numeric-fd write redirections.
        is_write_redir = (
            tok in (">", ">>", "&>", "&>>")
            or re.match(r"^\d*>>?$", tok) is not None
            or re.match(r"^&>>?$", tok) is not None
        )
        if is_write_redir:
            if i + 1 < len(tokens):
                target = tokens[i + 1]
                if target not in (
                    "/dev/null", "/dev/stderr", "/dev/stdout", "&1", "&2"
                ):
                    targets.append(target)
                skip_next = True
            continue

        # cat <<EOF > file form: the heredoc body is data, the redirect target is the write.
        # Heredocs alone (<<EOF without subsequent >) don't write anywhere — they
        # feed stdin. We don't emit a target for the heredoc itself.
        if tok in ("<<", "<<-") or re.match(r"^<<-?$", tok):
            # Skip the heredoc terminator token but keep walking — a later
            # > token will still be picked up.
            skip_next = True
            continue
        if tok.startswith("<<") and len(tok) > 2:
            # Compact ``<<EOF`` form (no space) — single token.
            continue
        # Plain stdin redirection: ``< file`` — not a write.
        if tok == "<":
            skip_next = True
            continue

        cleaned.append(tok)

    return (cleaned, targets)


def _classify_command_tokens(
    tokens: List[str], *, depth: int
) -> Tuple[Intent, List[str]]:
    """Classify a single command (after redirections + pipes are removed).

    Handles:
    - env-var prefixes (``FOO=bar python ...``)
    - the ``env`` wrapper
    - nested shells (``bash -c "..."``)
    - python ``-c <snippet>`` (note: pipe-stage form; the raw-string scan
      in ``_extract_python_snippets`` covers the more common case)
    - per-binary classification via ``BASH_READ_BINS`` / ``BASH_WRITE_BINS``
    - special-case write binaries with non-trivial argument shapes
      (``sed -i``, ``awk -i inplace``, ``find -delete``)

    Returns:
        (intent, write_targets).
    """
    # Strip env-var assignment prefixes.
    idx = _strip_env_prefix(tokens)
    if idx >= len(tokens):
        return ("EXEC", [])

    binary = tokens[idx]
    # ``env [-FLAGS] CMD ARGS...`` — recurse on the underlying command.
    if Path(binary).name in _BASH_ENV_PREFIXES:
        # Skip env's own flags (start with -) and KEY=VALUE pairs.
        j = idx + 1
        while j < len(tokens):
            t = tokens[j]
            if t.startswith("-") or _ENV_ASSIGN_RE.match(t):
                j += 1
                continue
            break
        if j >= len(tokens):
            return ("EXEC", [])
        return _classify_command_tokens(tokens[j:], depth=depth)

    # Strip the leading path on the binary so /usr/bin/python3 -> python3.
    bin_name = Path(binary).name

    # Nested shell: ``bash -c "<inner>"`` / ``sh -c ...``
    if bin_name in _BASH_RECURSIVE_BINS:
        inner = _find_dash_c_arg(tokens[idx + 1:])
        if inner is not None:
            return _classify_bash(inner, depth=depth + 1)
        # ``bash some-script.sh`` — we can't analyse, but it's likely EXEC.
        return ("EXEC", [])

    # python -c "<snippet>"
    if bin_name in _BASH_PYTHON_BINS:
        inner = _find_dash_c_arg(tokens[idx + 1:])
        if inner is not None:
            return _classify_python_inline(inner)
        # python script.py — we can't read the file, so EXEC.
        return ("EXEC", [])

    # Special-case write binaries with non-trivial argument shapes.
    if bin_name == "sed":
        if any(_is_sed_inplace_flag(t) for t in tokens[idx + 1:]):
            target = _last_non_flag_token(tokens[idx + 1:])
            return ("WRITE", [target] if target else [])
        return ("READ", [])

    if bin_name == "awk":
        if any(t == "-i" or t.startswith("-i=") for t in tokens[idx + 1:]):
            # ``awk -i inplace ... file`` — last positional is the file.
            target = _last_non_flag_token(tokens[idx + 1:])
            return ("WRITE", [target] if target else [])
        return ("READ", [])

    if bin_name == "find":
        if "-delete" in tokens[idx + 1:]:
            return ("WRITE", [])  # destructive but no specific target
        # find writes via -fprint / -fls — rare; treat as EXEC to be safe.
        if any(t in ("-fprint", "-fls", "-fprint0") for t in tokens[idx + 1:]):
            return ("EXEC", [])
        return ("READ", [])

    # Generic per-binary classification.
    if bin_name in BASH_READ_BINS:
        return ("READ", [])

    if bin_name in BASH_WRITE_BINS:
        targets = _extract_simple_write_targets(bin_name, tokens[idx + 1:])
        return ("WRITE", targets)

    return ("EXEC", [])


def _strip_env_prefix(tokens: List[str]) -> int:
    """Return the index of the first non-env-assignment token."""
    i = 0
    while i < len(tokens) and _ENV_ASSIGN_RE.match(tokens[i]):
        i += 1
    return i


def _find_dash_c_arg(tokens: List[str]) -> Optional[str]:
    """Find the argument that follows a ``-c`` flag, if any."""
    for i, t in enumerate(tokens):
        if t == "-c" and i + 1 < len(tokens):
            return tokens[i + 1]
        if t.startswith("-c") and len(t) > 2 and t != "--":
            # Compact form ``-cprint(1)`` is rare but technically legal.
            return t[2:]
    return None


def _is_sed_inplace_flag(token: str) -> bool:
    """Detect ``-i``, ``-i.bak``, ``--in-place``, or combined short flags like ``-rie``."""
    if token == "--in-place" or token.startswith("--in-place="):
        return True
    if token.startswith("-i"):
        return True
    # Combined short flags: ``-rie`` includes ``i`` (in-place).
    if token.startswith("-") and not token.startswith("--") and "i" in token[1:]:
        # Avoid false positive on ``--include=...`` (handled above by --in-place).
        # And on long options we already returned early.
        return True
    return False


def _last_non_flag_token(tokens: List[str]) -> Optional[str]:
    """Return the last token that doesn't look like a flag."""
    for tok in reversed(tokens):
        if not tok.startswith("-"):
            return tok
    return None


def _extract_simple_write_targets(
    bin_name: str, args: List[str]
) -> List[str]:
    """Extract write targets for simple write binaries (cp, mv, tee, rm, ...).

    For ``cp`` / ``mv`` / ``install`` / ``ln``: the destination is the last
    positional arg. For ``tee`` / ``truncate`` / ``touch`` / ``mkdir`` /
    ``chmod`` / ``chown`` / ``rm`` / ``rmdir``: every positional arg is a
    target. For ``dd``: parse ``of=PATH``.
    """
    if bin_name == "dd":
        targets = []
        for a in args:
            if a.startswith("of="):
                targets.append(a[3:])
        return targets

    positionals = [a for a in args if not a.startswith("-")]
    if not positionals:
        return []

    if bin_name in {"cp", "mv", "install", "ln"}:
        # Last positional is the destination.
        return [positionals[-1]]

    # tee, truncate, touch, mkdir, chmod, chown, rm, rmdir: every positional
    # is a target (or in chmod/chown's case the second-onward, but we keep
    # the first too — extra paths are conservative, not breaking).
    if bin_name in {"chmod", "chown"} and len(positionals) > 1:
        # First positional is the mode/owner spec, not a path.
        return positionals[1:]

    return positionals


# ---------------------------------------------------------------------------
# Python -c snippet extraction & classification
# ---------------------------------------------------------------------------


def _extract_python_snippets(command: str) -> List[str]:
    """Extract all python ``-c`` snippets and python heredoc bodies from a command.

    This scans the RAW command string (before shlex tokenisation) so that
    quoted snippet bodies survive intact. Returns a list of snippet strings
    suitable for AST analysis.
    """
    snippets: List[str] = []

    for m in _PY_C_DOUBLE.finditer(command):
        snippets.append(m.group(1))
    for m in _PY_C_SINGLE.finditer(command):
        snippets.append(m.group(1))

    for m in _PY_HEREDOC_HEAD.finditer(command):
        marker = m.group(1)
        start = m.end()
        remaining = command[start:]
        end_match = re.search(
            r'(?:^|\n)' + re.escape(marker) + r'(?:\n|$)', remaining
        )
        end_idx = end_match.start() if end_match else -1
        body = remaining[:end_idx] if end_idx >= 0 else remaining
        snippets.append(body)

    return snippets


def _classify_python_inline(snippet: str) -> Tuple[Intent, List[str]]:
    """Classify a python ``-c`` / heredoc snippet via the AST detector.

    Args:
        snippet: The python source code snippet.

    Returns:
        ``("WRITE", [paths...])`` if the AST detector finds writes,
        ``("READ", [])`` otherwise. May include the SUSPICIOUS_EXEC_SENTINEL
        among the targets when applicable.
    """
    if _pwd is None:
        # Detector unavailable — be conservative and return READ + [] so the
        # caller's other heuristics still apply.
        return ("READ", [])

    try:
        targets = _pwd.extract_write_targets(snippet)
    except Exception:
        return ("EXEC", [])

    if not targets:
        return ("READ", [])

    sentinel = _suspicious_exec_sentinel()
    real_targets = [t for t in targets if t != sentinel]
    if real_targets:
        return ("WRITE", list(targets))  # preserve sentinel if present
    # Only sentinel was returned — write classification still appropriate
    # because the snippet contains exec/eval with dynamic args.
    return ("WRITE", list(targets))


__all__ = [
    "READ_TOOLS",
    "WRITE_TOOLS",
    "MCP_READ_TOOLS",
    "MCP_WRITE_TOOLS",
    "MCP_OPTIONAL_DECLARABLE_TOOLS",
    "may_be_declared_optional",
    "PATH_KEYS",
    "CONTENT_KEYS",
    "BASH_READ_BINS",
    "BASH_WRITE_BINS",
    "classify",
    "write_targets",
    "is_write",
    "changed_content",
    "has_suspicious_exec",
]
