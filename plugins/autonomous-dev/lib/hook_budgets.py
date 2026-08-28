"""Canonical hook time budgets (Issue #1704).

One home for two numbers that were previously declared independently in at
least four places: the execution budget the Claude Code runtime applies to a
hook, and the subprocess/API timeout of a library that hook hosts.

Why a sibling file rather than an extension of
``config/pipeline_time_budgets.json``
-------------------------------------------------------------------------
The repo rule is *extend one proven mechanism before adding a second*, so the
field names (``budget_seconds`` / ``warning_pct``), the ``_``-prefixed comment
convention and the fall-back-to-default loader shape are lifted verbatim from
``pipeline_timing_analyzer.load_time_budgets``. Only the namespace is new, for
three reasons the existing loader structurally cannot accommodate:

1. ``load_time_budgets`` unconditionally merges ``STATIC_THRESHOLDS`` -- the
   eight pipeline agent names -- into every result it returns. A hook name
   added to that file would come back accompanied by eight agent budgets, and
   a settings generator iterating the result would try to register
   ``researcher`` as a hook. The merge is neither optional nor parameterised.
2. The validity ranges differ and are enforced elsewhere. Hook budgets are
   hard-capped at 60 by ``hook-metadata.schema.json``; agent budgets run to
   480s. One flat file cannot carry both ranges without a per-entry
   discriminator, and a discriminator is a second pattern anyway.
3. Agent budgets are read at runtime only. Hook budgets are additionally
   GENERATED into every settings surface by ``scripts/generate_hook_config.py``
   -- a write path the agent file has no notion of.

The 60-second ceiling
---------------------
It is NOT re-declared here. :func:`schema_max_seconds` reads it out of
``hook-metadata.schema.json``, which is the file that actually refuses a larger
value, so the ceiling has exactly one home too. Whether the runtime would
honour a value above 60 is UNTESTED; the schema refuses it, which makes the
question moot until the schema changes.

The nesting constraint
----------------------
A library subprocess timeout must be *strictly less* than the budget of every
hook that can host it. Otherwise the runtime discards the hook at the same
instant the library gives up, and a library timeout is indistinguishable from
a hook crash. :func:`check_nesting` is the single authority on that ordering.

Countable skips
---------------
When a hook overruns its budget the runtime stops waiting for it, but -- proven
against ``~/.claude/logs/hook_timings_*.jsonl``, which contains COMPLETED rows
at 13,139.7ms for a hook budgeted at 5s -- the hook PROCESS survives and
finishes. So the overrun is recordable from inside the hook.
:func:`record_budget_overrun` routes it to the existing refusal sink
(``hook_telemetry.log_block_event``) under the non-refusal shape
``budget_overrun``. No second sink is introduced.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

#: Canonical budget source. Every other declaration of these numbers is drift.
BUDGET_CONFIG_PATH: Path = _CONFIG_DIR / "hook_time_budgets.json"

#: The file that actually enforces the ceiling. Read, never mirrored.
HOOK_SCHEMA_PATH: Path = _CONFIG_DIR / "hook-metadata.schema.json"

#: Used only when :data:`HOOK_SCHEMA_PATH` is unreadable. Deliberately equal to
#: the schema's current ``maximum`` so a missing schema cannot silently widen
#: the ceiling; ``test_ceiling_is_read_from_the_schema_not_redeclared``
#: locks the two together.
FALLBACK_SCHEMA_MAX_SECONDS: int = 60

#: Used only when :data:`BUDGET_CONFIG_PATH` is unreadable. This is the number
#: the whole issue is about -- it survives ONLY as a fail-safe floor.
FALLBACK_DEFAULT_BUDGET_SECONDS: int = 5
FALLBACK_DEFAULT_WARNING_PCT: float = 0.8

#: ``decision_shape`` written for an overrun. NOT in
#: ``hook_telemetry.BLOCK_SHAPES``: an overrun is enforcement *skipped*, the
#: opposite of a refusal, and must never inflate a refusal count.
SHAPE_BUDGET_OVERRUN: str = "budget_overrun"

#: ``metadata.event_type`` for an overrun row, so one query finds them all.
EVENT_TYPE_BUDGET_OVERRUN: str = "hook_budget_overrun"

#: Multiple of measured p99 a budget must clear. 3x, because a budget equal to
#: a measured percentile fails at that percentile by construction.
P99_SAFETY_MARGIN: float = 3.0

#: Smallest budget for which an overrun can still be RECORDED (Issue #1704
#: remediation, WARNING-D). ``hook_timing`` short-circuits below this duration
#: before importing anything, so a hook budgeted under it would overrun
#: silently and forever -- passing every check while being structurally
#: incapable of producing the countable record this issue added.
#:
#: This module is the authority; ``hook_timing.MIN_BUDGET_SECONDS`` mirrors it
#: as a literal (it cannot import this module without paying the cost the
#: short-circuit exists to avoid) and
#: ``test_the_floor_authority_and_its_mirror_agree`` locks the two together. :func:`check_ceiling` refuses any budget below it, so the
#: constraint lives where it is CHECKED rather than in a comment a consumer
#: repo never runs.
OVERRUN_FLOOR_SECONDS: int = 3

#: Matches a hook script basename inside a settings ``command`` string.
_COMMAND_SCRIPT_RE = re.compile(r"([\w\-.]+)\.(py|sh)(?:\"|'|\s|$)")

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_HOOKS_DIR = _PLUGIN_ROOT / "hooks"

_cached_config: Optional[Dict[str, Any]] = None


class BudgetConfigError(ValueError):
    """The canonical budget config is present but unusable."""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _strip_comment_keys(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Return ``raw`` without ``_``-prefixed comment/metadata keys.

    Args:
        raw: A JSON object loaded from the budget config.

    Returns:
        The same mapping without documentation keys.
    """
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def load_budget_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and normalise the canonical budget config.

    Args:
        config_path: Override path. Defaults to :data:`BUDGET_CONFIG_PATH`.
            Results are cached only for the default path.

    Returns:
        Dict with keys ``default`` (dict), ``hooks`` (dict) and ``libraries``
        (dict). Never raises; a missing or malformed file degrades to the
        fail-safe default with empty ``hooks``/``libraries``.
    """
    global _cached_config

    use_cache = config_path is None
    if use_cache and _cached_config is not None:
        return _cached_config

    path = config_path if config_path is not None else BUDGET_CONFIG_PATH
    fallback: Dict[str, Any] = {
        "default": {
            "budget_seconds": FALLBACK_DEFAULT_BUDGET_SECONDS,
            "warning_pct": FALLBACK_DEFAULT_WARNING_PCT,
            "class": "fast_local",
        },
        "hooks": {},
        "libraries": {},
    }

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return fallback

    if not isinstance(raw, dict):
        return fallback

    default = raw.get("default")
    if not isinstance(default, dict) or "budget_seconds" not in default:
        default = fallback["default"]

    hooks = raw.get("hooks")
    hooks = _strip_comment_keys(hooks) if isinstance(hooks, dict) else {}

    libraries = raw.get("libraries")
    libraries = _strip_comment_keys(libraries) if isinstance(libraries, dict) else {}

    config: Dict[str, Any] = {
        "default": default,
        "hooks": {k: v for k, v in hooks.items() if isinstance(v, dict)},
        "libraries": {k: v for k, v in libraries.items() if isinstance(v, dict)},
    }

    if use_cache:
        _cached_config = config
    return config


def clear_cache() -> None:
    """Drop the module-level config cache. Used by tests."""
    global _cached_config
    _cached_config = None


def schema_max_seconds(schema_path: Optional[Path] = None) -> int:
    """Return the maximum hook timeout the sidecar schema will accept.

    Read from ``hook-metadata.schema.json`` rather than re-declared, so the
    ceiling has one home. Falls back to :data:`FALLBACK_SCHEMA_MAX_SECONDS`
    when the schema cannot be read.

    Args:
        schema_path: Override path. Defaults to :data:`HOOK_SCHEMA_PATH`.

    Returns:
        The ``registrations.items.properties.timeout.maximum`` value.
    """
    path = schema_path if schema_path is not None else HOOK_SCHEMA_PATH
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        maximum = schema["properties"]["registrations"]["items"]["properties"][
            "timeout"
        ]["maximum"]
        return int(maximum)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return FALLBACK_SCHEMA_MAX_SECONDS


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def normalize_hook_name(hook_name: str) -> str:
    """Strip a ``.py``/``.sh`` extension so callers may pass either form.

    Args:
        hook_name: Hook identifier, with or without an extension.

    Returns:
        The bare hook name.
    """
    name = str(hook_name)
    for suffix in (".py", ".sh"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def get_hook_budget(hook_name: str, config: Optional[Dict[str, Any]] = None) -> int:
    """Return the budget in whole seconds for ``hook_name``.

    Args:
        hook_name: Hook identifier, with or without a ``.py``/``.sh`` suffix.
        config: Pre-loaded config. Loaded from disk when None.

    Returns:
        Budget in seconds. Unknown hooks get the configured default -- never
        zero, so a typo cannot silently disable a hook.
    """
    cfg = config if config is not None else load_budget_config()
    entry = cfg["hooks"].get(normalize_hook_name(hook_name))
    if isinstance(entry, dict) and "budget_seconds" in entry:
        try:
            return int(entry["budget_seconds"])
        except (TypeError, ValueError):
            pass
    try:
        return int(cfg["default"]["budget_seconds"])
    except (KeyError, TypeError, ValueError):
        return FALLBACK_DEFAULT_BUDGET_SECONDS


def has_hook_budget(hook_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Report whether ``hook_name`` has an explicit entry (not the default).

    Distinguishing "budgeted at the default" from "not budgeted at all" is what
    keeps :func:`record_budget_overrun` silent for processes that merely borrow
    ``HookTimer``: ``scripts/mutation_witness_gate.py`` emits 375 timing rows
    into the production sink and is registered nowhere (that pollution is
    tracked separately as Issue #1645 and is deliberately NOT fixed here).

    Args:
        hook_name: Hook identifier, with or without an extension.
        config: Pre-loaded config. Loaded from disk when None.

    Returns:
        True when the hook has its own entry under ``hooks``.
    """
    cfg = config if config is not None else load_budget_config()
    return normalize_hook_name(hook_name) in cfg["hooks"]


def get_library_timeout(
    library_key: str, config: Optional[Dict[str, Any]] = None
) -> int:
    """Return the declared subprocess timeout for a library, in seconds.

    Args:
        library_key: Key under ``libraries`` (e.g. ``"semantic_gate.TIMEOUT_S"``).
        config: Pre-loaded config. Loaded from disk when None.

    Returns:
        Declared ``timeout_seconds``.

    Raises:
        BudgetConfigError: When the key is absent or malformed. Unlike hook
            budgets there is no safe default here: silently substituting one
            would re-create the untracked constant this module exists to
            remove.
    """
    cfg = config if config is not None else load_budget_config()
    entry = cfg["libraries"].get(library_key)
    if not isinstance(entry, dict) or "timeout_seconds" not in entry:
        raise BudgetConfigError(
            f"No library timeout declared for {library_key!r} in "
            f"{BUDGET_CONFIG_PATH}\n"
            f"Expected: an entry under 'libraries' with 'timeout_seconds' and "
            f"'host_hooks'\n"
            f"See: docs/HOOKS.md (Issue #1704)"
        )
    try:
        return int(entry["timeout_seconds"])
    except (TypeError, ValueError) as exc:
        raise BudgetConfigError(
            f"Malformed timeout_seconds for {library_key!r} in "
            f"{BUDGET_CONFIG_PATH}: {entry['timeout_seconds']!r}\n"
            f"Expected: an integer number of seconds\n"
            f"See: docs/HOOKS.md (Issue #1704)"
        ) from exc


def library_timeout_or(library_key: str, fallback: int) -> int:
    """Return a library timeout, degrading to ``fallback`` if unavailable.

    The module-level constants in ``genai_prompts``, ``intent_classifier`` and
    ``semantic_gate`` bind at import time inside hook subprocesses, where a
    missing or unreadable config must not raise. They call this rather than
    :func:`get_library_timeout` so a broken config cannot break the hook.

    The degrade path is NOISY (one stderr line). A silent fallback returns a
    number that LOOKS configured while the canonical file is being ignored --
    which is the same class of invisible substitution this module exists to
    remove. Only :class:`BudgetConfigError` and :class:`OSError` are caught; a
    programming error still propagates.

    Args:
        library_key: Key under ``libraries``.
        fallback: Value to use when the config cannot supply one. This is a
            FAIL-SAFE, not the normal value. Because this function DISCARDS
            ``fallback`` whenever the config is readable, a runtime check on
            the caller's attribute cannot verify the literal -- it compares
            X to X. ``TestRemediation3FallbackLiteralsAreReallyLocked``
            therefore parses each call site's literal out of the SOURCE.

    Returns:
        The declared timeout, or ``fallback``.
    """
    try:
        return get_library_timeout(library_key)
    except (BudgetConfigError, OSError) as exc:
        try:
            sys.stderr.write(
                f"[hook-budgets] DEGRADED: {library_key} could not be read from "
                f"{BUDGET_CONFIG_PATH}; using fail-safe {fallback}s. "
                f"Cause: {exc.__class__.__name__}\n"
            )
        except Exception:
            pass
        return int(fallback)


def min_declared_budget_seconds(config: Optional[Dict[str, Any]] = None) -> int:
    """Return the smallest ``budget_seconds`` any hook declares.

    ``hook_timing`` uses this bound to short-circuit the overrun check before
    paying for an import and a JSON read on every hook exit. It cannot import
    this module to obtain the number (that is the cost being avoided), so it
    carries a literal that ``test_min_budget_ns_matches_the_canonical_minimum``
    locks to this function.

    Args:
        config: Pre-loaded config. Loaded from disk when None.

    Returns:
        The minimum declared budget, or :data:`FALLBACK_DEFAULT_BUDGET_SECONDS`
        when nothing is declared.
    """
    cfg = config if config is not None else load_budget_config()
    values = []
    for entry in cfg["hooks"].values():
        try:
            values.append(int(entry["budget_seconds"]))
        except (KeyError, TypeError, ValueError):
            continue
    return min(values) if values else FALLBACK_DEFAULT_BUDGET_SECONDS


def budgeted_hook_count(config: Optional[Dict[str, Any]] = None) -> int:
    """Return how many hooks carry an explicit budget entry.

    The anti-vacuity companion for :func:`check_ceiling` and
    :func:`check_nesting`, mirroring what :func:`measured_hook_count` does for
    :func:`check_measured_headroom`. A checker returning ``[]`` over an empty
    config is a pass over zero.

    Args:
        config: Pre-loaded config. Loaded from disk when None.

    Returns:
        Number of entries under ``hooks``.
    """
    cfg = config if config is not None else load_budget_config()
    return len(cfg["hooks"])


def _empty_config_violation(cfg: Dict[str, Any], checker: str) -> List[str]:
    """Return a violation when ``cfg`` carries nothing to check.

    Args:
        cfg: A loaded budget config.
        checker: Name of the calling checker, for the message.

    Returns:
        A single-element list when the config is empty; ``[]`` otherwise.
    """
    if cfg["hooks"]:
        return []
    return [
        f"{checker}: the budget config loaded ZERO hooks from "
        f"{BUDGET_CONFIG_PATH}. This is a pass over nothing, not a pass. "
        f"Expected: a 'hooks' object with at least one entry. "
        f"See: docs/HOOKS.md (Issue #1704)"
    ]


# ---------------------------------------------------------------------------
# The three constraints
# ---------------------------------------------------------------------------


def check_ceiling(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Return one message per budget above the schema ceiling (or below 1).

    Args:
        config: Pre-loaded config. Loaded from disk when None.

    Returns:
        List of violation messages; empty when every budget is in range.
    """
    cfg = config if config is not None else load_budget_config()
    empty = _empty_config_violation(cfg, "check_ceiling")
    if empty:
        return empty
    ceiling = schema_max_seconds()
    violations: List[str] = []
    for name, entry in sorted(cfg["hooks"].items()):
        try:
            budget = int(entry["budget_seconds"])
        except (KeyError, TypeError, ValueError):
            violations.append(f"{name}: budget_seconds missing or non-integer")
            continue
        if budget < 1:
            violations.append(
                f"{name}: budget_seconds={budget} is below 1 -- raising a "
                f"ceiling must not remove it"
            )
        elif budget < OVERRUN_FLOOR_SECONDS:
            violations.append(
                f"{name}: budget_seconds={budget} is below the overrun floor "
                f"of {OVERRUN_FLOOR_SECONDS}s. hook_timing short-circuits "
                f"below that duration, so this hook could overrun forever "
                f"without ever producing a countable record -- passing every "
                f"check while being incapable of the enforcement it declares."
            )
        elif budget > ceiling:
            violations.append(
                f"{name}: budget_seconds={budget} exceeds the schema maximum "
                f"of {ceiling} (hook-metadata.schema.json)"
            )
    return violations


def check_nesting(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Return one message per library timeout not strictly inside its host.

    A library's timeout must be ``<`` every host hook's budget. Equality is a
    violation, not a pass: at equality the runtime discards the hook at the
    same instant the library gives up, so the library can never report its own
    timeout.

    Args:
        config: Pre-loaded config. Loaded from disk when None.

    Returns:
        List of violation messages; empty when every pair nests correctly.
    """
    cfg = config if config is not None else load_budget_config()
    empty = _empty_config_violation(cfg, "check_nesting")
    if empty:
        return empty
    violations: List[str] = []
    if not cfg["libraries"]:
        return [
            "check_nesting: ZERO libraries declared, so no nesting pair was "
            "examined. A checker with nothing to check has not passed. "
            "Expected: a 'libraries' object with at least one entry. "
            "See: docs/HOOKS.md (Issue #1704)"
        ]

    for key, entry in sorted(cfg["libraries"].items()):
        try:
            lib_timeout = int(entry["timeout_seconds"])
        except (KeyError, TypeError, ValueError):
            violations.append(f"{key}: timeout_seconds missing or non-integer")
            continue

        hosts = entry.get("host_hooks")
        if not isinstance(hosts, list) or not hosts:
            violations.append(
                f"{key}: no host_hooks declared -- a library timeout with no "
                f"named host cannot be checked against anything"
            )
            continue

        for host in hosts:
            if not has_hook_budget(host, cfg):
                violations.append(
                    f"{key}: host_hook {host!r} has no entry under 'hooks', so "
                    f"its budget is the default and the nesting claim is "
                    f"unverifiable"
                )
                continue
            host_budget = get_hook_budget(host, cfg)
            if lib_timeout >= host_budget:
                violations.append(
                    f"{key}: timeout_seconds={lib_timeout}s is NOT strictly "
                    f"less than host hook {host!r} budget={host_budget}s. The "
                    f"runtime would discard {host} before the library could "
                    f"fail cleanly and report."
                )
    return violations


#: Callables whose first string argument names a module loaded dynamically.
#: ``importlib`` is this repo's PRIMARY loader for hook->lib edges -- CLAUDE.md
#: names it as the reason LSP cannot follow them -- so a walk that sees only
#: ``import`` statements under-credits badly. ``unified_pre_tool.py`` alone
#: loads at least eight modules via ``spec_from_file_location``.
_DYNAMIC_IMPORT_FUNCS = frozenset(
    {"spec_from_file_location", "import_module", "__import__", "load_module"}
)


def _module_imports(path: Path) -> Set[str]:
    """Return every module name ``path`` imports, statically or dynamically.

    Walks the whole AST rather than only ``tree.body``: this repo imports
    lazily inside functions and inside ``try``/``except ImportError`` guards
    (``intent_classifier`` and ``semantic_gate`` both bridge ``sys.path`` and
    import ``genai_utils`` that way), so a top-level-only walk misses the very
    edges that matter.

    Three edge kinds are collected:

    1. ``import x`` / ``import x.y`` -- first segment.
    2. ``from x import y`` (absolute) -- the module; and ``from . import y``
       (relative) -- the imported NAMES, since the module is the package
       itself. The previous version filtered these out via ``node.level == 0``
       and under-credited every relative import.
    3. Dynamic loads: a string literal argument to any name in
       :data:`_DYNAMIC_IMPORT_FUNCS`, plus the stem of any ``.py`` path
       literal. This is what makes ``importlib`` edges visible.

    KNOWN REMAINING BLIND SPOT, declared rather than silently resolved: a
    dynamic load whose module name is COMPUTED at runtime (an f-string, a
    variable, a loop over a list) is invisible to any static walk. A guard
    built on this can under-credit; it does not over-credit, which is the
    direction that matters for :func:`check_declared_hosts_match_derived` --
    an omitted host is refused, an extra declared host is permitted.

    Args:
        path: A Python source file.

    Returns:
        Set of module names, first segment only.
    """
    names: Set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return names

    def _add_from_string(value: str) -> None:
        text = value.strip()
        if not text:
            return
        if text.endswith(".py"):
            text = Path(text).stem
        names.add(text.split(".")[0].split("/")[-1])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    names.add(node.module.split(".")[0])
            else:
                # ``from . import x`` / ``from .pkg import x``: the module is
                # the package, so the EDGE is each imported name.
                if node.module:
                    names.add(node.module.split(".")[0])
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            func_name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name) else ""
            )
            if func_name not in _DYNAMIC_IMPORT_FUNCS:
                continue
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    _add_from_string(arg.value)
    return names


def _local_module_index() -> Dict[str, Path]:
    """Return ``{module_name: path}`` for every hook and lib module.

    Returns:
        Mapping of importable module name to its source path.
    """
    index: Dict[str, Path] = {}
    for directory in (_HOOKS_DIR, _PLUGIN_ROOT / "lib"):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.py"):
            if path.name.startswith("__"):
                continue
            index.setdefault(path.stem, path)
    return index


def reaches_module(start_module: str, target_module: str) -> bool:
    """Report whether ``start_module`` transitively imports ``target_module``.

    Args:
        start_module: Module name to start the walk from.
        target_module: Module name to look for.

    Returns:
        True when a path exists in the local import graph.
    """
    index = _local_module_index()
    if start_module not in index:
        return False
    seen: Set[str] = set()
    stack = [start_module]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        if current == target_module and current != start_module:
            return True
        for name in _module_imports(index[current]):
            if name == target_module:
                return True
            if name in index:
                stack.append(name)
    return False


def derive_host_hooks(
    source_module: str, registered_hooks: Optional[Set[str]] = None
) -> Set[str]:
    """Return every REGISTERED hook whose import closure reaches ``source_module``.

    Issue #1704 remediation (W5). ``host_hooks`` was hand-maintained and was
    already wrong: ``auto_fix_docs`` reaches ``genai_prompts`` through
    ``genai_utils`` and IS registered (``.claude-plugin/default-settings.json``,
    ``PreCommit``), so a 15s library sat under a host the nesting guard never
    looked at. A literal list is a comment; a derived one is a guard.

    Args:
        source_module: Module that defines the timeout constant (e.g.
            ``"genai_prompts"``).
        registered_hooks: Hook names known to be registered. Defaults to every
            hook discovered in the repo's settings surfaces.

    Returns:
        Set of registered hook names that transitively import ``source_module``.
    """
    hooks = (
        registered_hooks
        if registered_hooks is not None
        else registered_hook_names()
    )
    return {name for name in hooks if reaches_module(name, source_module)}


def registered_hook_names(plugin_root: Optional[Path] = None) -> Set[str]:
    """Return every hook name registered in any in-repo settings surface.

    Discovery is BY CONTENT: a ``settings*.json`` glob misses
    ``config/global_settings_template.json`` and
    ``.claude-plugin/default-settings.json``, and the second is exactly where
    the missed ``auto_fix_docs`` host lives.

    Args:
        plugin_root: Directory to search. Defaults to the plugin root.

    Returns:
        Set of hook names with the extension stripped.
    """
    root = plugin_root if plugin_root is not None else _PLUGIN_ROOT
    names: Set[str] = set()
    for path in root.rglob("*.json"):
        if any(p in ("__pycache__", "archived", "node_modules") for p in path.parts):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        hooks = data.get("hooks")
        if not isinstance(hooks, dict) or not hooks:
            continue
        for entries in hooks.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for hook_entry in entry.get("hooks", []) or []:
                    if not isinstance(hook_entry, dict):
                        continue
                    match = _COMMAND_SCRIPT_RE.search(
                        str(hook_entry.get("command", ""))
                    )
                    if match is not None:
                        names.add(normalize_hook_name(match.group(1)))
    return names


def check_declared_hosts_match_derived(
    config: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Return one message per library whose ``host_hooks`` misses a real host.

    The declared list must COVER the derived one. Declaring extra hosts is
    permitted (a conservative over-declaration only tightens the nesting
    constraint); omitting a real one is refused, because an omitted host is a
    host the nesting guard never looks at.

    Args:
        config: Pre-loaded budget config. Loaded from disk when None.

    Returns:
        List of coverage violations; empty when every real host is declared.
    """
    cfg = config if config is not None else load_budget_config()
    empty = _empty_config_violation(cfg, "check_declared_hosts_match_derived")
    if empty:
        return empty

    registered = registered_hook_names()
    violations: List[str] = []
    for key, entry in sorted(cfg["libraries"].items()):
        source_module = str(entry.get("source_module") or key.split(".")[0])
        declared = set(entry.get("host_hooks") or [])
        derived = derive_host_hooks(source_module, registered)
        missing = sorted(derived - declared)
        if missing:
            violations.append(
                f"{key}: host_hooks omits {missing}, which the import graph "
                f"shows DO reach {source_module} and which are registered. "
                f"An omitted host is a host check_nesting never examines."
            )
    return violations


def check_measured_headroom(
    config: Optional[Dict[str, Any]] = None,
    *,
    margin: float = P99_SAFETY_MARGIN,
) -> List[str]:
    """Return one message per hook budgeted below its own measured behaviour.

    A budget must clear ``max(measured_p99_ms * margin, measured_max_ms)``.
    Hooks with ``measured_p99_ms: null`` are UNMEASURED and skipped -- an
    absence of measurement is not a measurement of zero. Callers MUST pair this
    with :func:`measured_hook_count` so an empty result cannot be mistaken for
    a pass over nothing.

    Args:
        config: Pre-loaded config. Loaded from disk when None.
        margin: Multiple of p99 the budget must clear.

    Returns:
        List of violation messages; empty when every measured hook has
        headroom.
    """
    cfg = config if config is not None else load_budget_config()
    violations: List[str] = []
    for name, entry in sorted(cfg["hooks"].items()):
        p99 = entry.get("measured_p99_ms")
        max_ms = entry.get("measured_max_ms")
        if p99 is None or max_ms is None:
            continue
        try:
            required_ms = max(float(p99) * margin, float(max_ms))
            budget_ms = float(entry["budget_seconds"]) * 1000.0
        except (KeyError, TypeError, ValueError):
            violations.append(f"{name}: measurement fields are non-numeric")
            continue
        if budget_ms < required_ms:
            violations.append(
                f"{name}: budget {budget_ms / 1000:.0f}s is below the required "
                f"{required_ms / 1000:.2f}s (max of p99 {float(p99):.1f}ms x "
                f"{margin:g} and observed max {float(max_ms):.1f}ms). A budget "
                f"under its own measured tail discards enforcement on every "
                f"slow call."
            )
    return violations


def find_project_root(start: Optional[Path] = None) -> Path:
    """Return the nearest ancestor of ``start`` containing ``.claude`` or ``.git``.

    Issue #1704 remediation (WARNING-B). The previous implementation anchored
    the project tier on ``Path.cwd()``, so running the check from a
    subdirectory silently dropped that tier entirely -- the CWD-dependence class
    of Issue #1697. Walking up finds the same root from anywhere in the tree.

    ``.git`` is preferred over ``.claude`` and the two passes are ORDERED, not
    combined. A combined "first ancestor with either marker" walk anchors on
    ``plugins/autonomous-dev/`` inside this very repo, because a ``.claude/``
    log-artifact directory exists there -- measured, not hypothesised. That
    would silently drop the real project tier while looking like it worked.

    Args:
        start: Directory to walk up from. Defaults to the current directory.

    Returns:
        The project root, or ``start`` itself when no marker is found.
    """
    current = (start if start is not None else Path.cwd()).resolve()
    chain = [current, *current.parents]
    for candidate in chain:
        if (candidate / ".git").exists():
            return candidate
    for candidate in chain:
        if (candidate / ".claude").is_dir():
            return candidate
    return current


def installed_settings_paths(project_root: Optional[Path] = None) -> List[Path]:
    """Return the settings files that ACTUALLY govern hook execution.

    Deliberately NOT the in-repo templates. Editing a template changes nothing
    at runtime: ``~/.claude/settings.json`` is written by ``deploy-all.sh``, and
    the project-tier file is written per repo. A checker that reads the
    templates is validating the declaration and calling it enforcement.

    Args:
        project_root: Repository root for the project tier. Defaults to
            :func:`find_project_root`, which walks UP rather than trusting
            the current directory.

    Returns:
        Existing installed settings paths, user tier first.
    """
    root = project_root if project_root is not None else find_project_root()
    candidates = [
        Path.home() / ".claude" / "settings.json",
        Path.home() / ".claude" / "settings.local.json",
        root / ".claude" / "settings.json",
        root / ".claude" / "settings.local.json",
    ]
    seen: Set[Path] = set()
    ordered: List[Path] = []
    for path in candidates:
        resolved = path.resolve() if path.is_file() else path
        if path.is_file() and resolved not in seen:
            seen.add(resolved)
            ordered.append(path)
    return ordered


def read_installed_timeouts(path: Path) -> "tuple[Dict[str, int], Optional[str]]":
    """Return ``({hook_name: timeout}, error)`` for an installed settings file.

    Entries with no ``timeout`` are reported as ``-1`` so an unbounded
    registration is visible rather than absent. Commands that run no script
    (a bare ``echo`` banner) are skipped.

    Issue #1704 remediation (WARNING-B). This used to swallow
    ``json.JSONDecodeError`` and return ``{}``, so a CORRUPT
    ``~/.claude/settings.json`` -- a file that still governs execution -- read
    as clean. ``{}`` could mean "no hooks registered" or "unparseable" and the
    caller could not tell the two apart. The error is now returned so it can be
    reported as a violation.

    Args:
        path: An installed settings JSON file.

    Returns:
        Tuple of the timeout mapping and an error string (``None`` on success).
    """
    result: Dict[str, int] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return result, f"unreadable ({exc.__class__.__name__})"
    except json.JSONDecodeError as exc:
        return result, f"MALFORMED JSON at line {exc.lineno}: {exc.msg}"
    if not isinstance(data, dict):
        return result, f"root is {type(data).__name__}, expected an object"
    hooks = data.get("hooks")
    if hooks is None:
        return result, None
    if not isinstance(hooks, dict):
        return result, f"'hooks' is {type(hooks).__name__}, expected an object"
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook_entry in entry.get("hooks", []) or []:
                if not isinstance(hook_entry, dict):
                    continue
                match = _COMMAND_SCRIPT_RE.search(str(hook_entry.get("command", "")))
                if match is None:
                    continue
                # group(1) is the bare stem. group(0) carries the trailing
                # delimiter the pattern consumes ('"' or a space), which
                # defeats normalize_hook_name and yields 'foo.py"' -- a name
                # that matches no budget entry and makes every check pass
                # vacuously. Caught by the auto_fix_docs positive control.
                name = normalize_hook_name(match.group(1))
                timeout = hook_entry.get("timeout")
                result[name] = int(timeout) if isinstance(timeout, int) else -1
    return result, None


def inspected_settings_count(paths: Optional[List[Path]] = None) -> int:
    """Return how many installed settings files the skew check would read.

    The anti-vacuity companion for :func:`check_installed_settings_skew`,
    mirroring :func:`budgeted_hook_count` and :func:`measured_hook_count`.
    Zero means the checker examined nothing, which is not a clean bill.

    Args:
        paths: Settings files. Defaults to :func:`installed_settings_paths`.

    Returns:
        Number of files that will be inspected.
    """
    return len(paths if paths is not None else installed_settings_paths())


def check_installed_settings_skew(
    paths: Optional[List[Path]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Return one message per hook whose ENFORCED budget differs from the declared one.

    Issue #1704 remediation (BLOCKING-3). The overrun recorder compares a
    measured duration against the budget in :data:`BUDGET_CONFIG_PATH`. If the
    installed settings still carry a smaller number, the runtime discards the
    hook's decision at the SMALLER value while the recorder stays silent --
    the countability mechanism under-reports every real skip, precisely when
    skips are most likely.

    Deploying libraries without ``--global-settings`` produces exactly that
    skew, so this check is the other half of the deploy instruction.

    Args:
        paths: Settings files to inspect. Defaults to
            :func:`installed_settings_paths`.
        config: Pre-loaded budget config. Loaded from disk when None.

    Returns:
        List of skew messages; empty when every installed timeout matches, or
        when the hook has no installed registration at all (not skew -- simply
        not deployed).
    """
    cfg = config if config is not None else load_budget_config()
    targets = paths if paths is not None else installed_settings_paths()
    violations: List[str] = []

    # Anti-vacuity, shape A (Issue #1704 remediation, WARNING-B). A checker
    # whose whole purpose is catching undeployed state must not hand a clean
    # bill to a machine with nothing deployed. This is the consumer-repo case.
    if not targets:
        return [
            "check_installed_settings_skew: ZERO installed settings files were "
            f"found (searched ~/.claude/ and {find_project_root()}/.claude/). "
            "Nothing was inspected, so this is a pass over nothing. "
            "Expected: at least one settings.json governing hook execution. "
            "See: docs/HOOKS.md (Issue #1704)"
        ]

    for path in targets:
        installed, error = read_installed_timeouts(path)
        # Anti-vacuity, shape C. A corrupt settings file still governs
        # execution; reading it as an empty mapping reports it as clean.
        if error is not None:
            violations.append(
                f"{path}: could not be read -- {error}. This file still "
                f"governs hook execution; its enforced bounds are UNKNOWN, "
                f"not absent."
            )
            continue
        # Anti-vacuity, shape B. A settings file with no registrations is a
        # real state, but it is not evidence that the budgets took effect.
        if not installed:
            violations.append(
                f"{path}: parsed cleanly but registers ZERO hooks, so no "
                f"declared budget is enforced through it. If this file is "
                f"meant to carry registrations, deploy has not run."
            )
            continue
        for name, enforced in sorted(installed.items()):
            if not has_hook_budget(name, cfg):
                violations.append(
                    f"{path}: {name} is REGISTERED and executing but has no "
                    f"entry in {BUDGET_CONFIG_PATH.name}; its enforced bound "
                    f"({'none' if enforced < 0 else str(enforced) + 's'}) is "
                    f"governed by nothing."
                )
                continue
            declared = get_hook_budget(name, cfg)
            if enforced < 0:
                violations.append(
                    f"{path}: {name} declares {declared}s but the INSTALLED "
                    f"registration carries NO timeout. The enforced bound is "
                    f"the runtime default, which is unmeasured here."
                )
            elif enforced != declared:
                violations.append(
                    f"{path}: {name} declares {declared}s but the INSTALLED "
                    f"registration enforces {enforced}s. A run between "
                    f"{enforced}s and {declared}s is discarded by the runtime "
                    f"and records NO overrun row. Run "
                    f"`bash scripts/deploy-all.sh --global-settings`."
                )
    return violations


def measured_hook_count(config: Optional[Dict[str, Any]] = None) -> int:
    """Return how many hooks carry a non-null p99 measurement.

    Exists so callers can refuse to trust :func:`check_measured_headroom`
    returning an empty list when it in fact examined nothing.

    Args:
        config: Pre-loaded config. Loaded from disk when None.

    Returns:
        Count of hooks with a usable measurement.
    """
    cfg = config if config is not None else load_budget_config()
    return sum(
        1 for entry in cfg["hooks"].values() if entry.get("measured_p99_ms") is not None
    )


# ---------------------------------------------------------------------------
# Countable skips
# ---------------------------------------------------------------------------


def record_budget_overrun(
    *,
    hook_name: str,
    duration_ms: float,
    budget_seconds: int,
    session_id: Optional[str] = None,
    start_dir: Optional[Path] = None,
) -> bool:
    """Append one overrun row to the canonical refusal sink.

    Routed through :func:`hook_telemetry.log_block_event` -- the sink from
    Issue #1588 -- under ``decision_shape="budget_overrun"``, which is NOT in
    ``BLOCK_SHAPES`` and therefore never inflates a refusal count while still
    appearing in every reader's shape breakdown.

    NEVER raises. Telemetry must not be able to break a hook.

    Args:
        hook_name: Hook whose decision the runtime discarded.
        duration_ms: Measured wall time of the invocation, in milliseconds.
        budget_seconds: The budget it blew.
        session_id: Optional session id; defaults to ``CLAUDE_SESSION_ID``.
        start_dir: Project-root anchor for the log file.

    Returns:
        True when a row was written, False when the sink was unavailable or
        the write failed.
    """
    try:
        lib_dir = str(Path(__file__).resolve().parent)
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        from hook_telemetry import log_block_event  # type: ignore[import-not-found]
    except Exception:
        return False

    try:
        overrun_ms = float(duration_ms) - (int(budget_seconds) * 1000.0)
        log_block_event(
            hook_name=str(hook_name),
            decision_shape=SHAPE_BUDGET_OVERRUN,
            reason=(
                f"{hook_name} ran {float(duration_ms):.1f}ms against a "
                f"{int(budget_seconds)}s budget ({overrun_ms:.1f}ms over). The "
                f"runtime stopped waiting, so this hook's decision was "
                f"DISCARDED and its checks did not apply to the tool call."
            ),
            metadata={
                "event_type": EVENT_TYPE_BUDGET_OVERRUN,
                "duration_ms": round(float(duration_ms), 1),
                "budget_seconds": int(budget_seconds),
                "overrun_ms": round(overrun_ms, 1),
                # Issue #1704 remediation: the budget compared against is the
                # DECLARED one. If the installed settings enforce something
                # smaller, this row's threshold is not the threshold the
                # runtime applied -- so the row carries where its number came
                # from. check_installed_settings_skew() detects that gap.
                "budget_source": str(BUDGET_CONFIG_PATH),
                "issue": 1704,
            },
            session_id=(
                session_id
                if session_id is not None
                else os.environ.get("CLAUDE_SESSION_ID", "")
            ),
            start_dir=start_dir,
        )
        return True
    except Exception:
        return False
