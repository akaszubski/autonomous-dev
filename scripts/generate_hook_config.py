#!/usr/bin/env python3
"""Generate hook config from .hook.json sidecar metadata files.

Reads .hook.json sidecar files from the hooks directory and generates:
1. install_manifest.json ``components.hooks.files`` array
2. global_settings_template.json ``hooks`` object

Timeouts (Issue #1704)
----------------------
Hook timeouts are NOT declared here and NOT declared in the sidecars. They come
from ``config/hook_time_budgets.json``, the canonical source. This module
previously carried ``reg.get("timeout", 5)`` -- a hard-coded generator default
that was the ORIGIN of the sprawl: every sidecar and every settings surface
simply repeated it, and the resulting 5s ceiling silently discarded all ~51
checks on 23 ``unified_pre_tool.py`` invocations in one week.

``--sync-timeouts`` propagates the canonical budgets to EVERY settings surface,
discovered BY CONTENT rather than by a ``settings*.json`` glob -- a glob misses
``config/global_settings_template.json`` entirely, which alone carries 16
bindings.

Usage:
    python scripts/generate_hook_config.py --check           # Report drift
    python scripts/generate_hook_config.py --write           # Update config files
    python scripts/generate_hook_config.py --check-timeouts  # Report timeout drift
    python scripts/generate_hook_config.py --sync-timeouts   # Write canonical timeouts
    python scripts/generate_hook_config.py --check -v        # Verbose drift report

Exit codes:
    0 - Success (no drift in check mode, or write succeeded)
    1 - Drift detected (check mode) or validation errors
    2 - CLI/usage errors
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

# Auto-detect project root from script location
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = PROJECT_ROOT / "plugins/autonomous-dev"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
MANIFEST_PATH = PLUGIN_ROOT / "config/install_manifest.json"
SETTINGS_PATH = PLUGIN_ROOT / "config/global_settings_template.json"
SCHEMA_PATH = PLUGIN_ROOT / "config/hook-metadata.schema.json"

# Issue #1704: the canonical budget source and its loader.
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
try:
    import hook_budgets  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - only when lib/ is absent
    hook_budgets = None  # type: ignore[assignment]

# Matches the hook script basename inside a settings ``command`` string.
_COMMAND_SCRIPT_RE = re.compile(r"([\w\-.]+)\.(py|sh)(?:\"|'|\s|$)")

# Extension mapping from interpreter to file extension
INTERPRETER_EXTENSIONS = {
    "python3": ".py",
    "bash": ".sh",
}

# Optional jsonschema support
try:
    from jsonschema import Draft202012Validator

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def discover_sidecars(hooks_dir: Path) -> list[Path]:
    """Find all *.hook.json in hooks_dir (excluding archived/), sorted by name.

    Args:
        hooks_dir: Directory to search for sidecar files.

    Returns:
        Sorted list of Path objects for each discovered .hook.json file.

    Raises:
        FileNotFoundError: If hooks_dir does not exist.
    """
    if not hooks_dir.is_dir():
        raise FileNotFoundError(
            f"Hooks directory not found: {hooks_dir}\n"
            f"Expected: directory containing .hook.json sidecar files\n"
            f"See: docs/ARCHITECTURE-OVERVIEW.md"
        )

    sidecars = []
    for path in hooks_dir.glob("*.hook.json"):
        # Exclude anything under archived/
        if "archived" not in path.parts:
            sidecars.append(path)

    return sorted(sidecars, key=lambda p: p.name)


def load_and_validate_sidecar(path: Path, schema: dict | None = None) -> dict:
    """Load sidecar JSON and validate against schema.

    Args:
        path: Path to the .hook.json sidecar file.
        schema: JSON Schema dict for validation. If None, skips validation.

    Returns:
        Parsed sidecar data as a dict.

    Raises:
        ValueError: If JSON is invalid or schema validation fails.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in sidecar: {path}\n"
            f"Parse error: {e}\n"
            f"Expected: valid JSON matching hook-metadata.schema.json"
        ) from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Sidecar must be a JSON object: {path}\n"
            f"Got: {type(data).__name__}\n"
            f"Expected: object with 'name', 'type', 'interpreter' keys"
        )

    # Validate required fields even without jsonschema
    for field in ("name", "type", "interpreter"):
        if field not in data:
            raise ValueError(
                f"Missing required field '{field}' in sidecar: {path}\n"
                f"Required fields: name, type, interpreter\n"
                f"See: plugins/autonomous-dev/config/hook-metadata.schema.json"
            )

    # Schema validation with jsonschema if available
    if schema is not None and HAS_JSONSCHEMA:
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(data))
        if errors:
            error_messages = "; ".join(e.message for e in errors)
            raise ValueError(
                f"Schema validation failed for sidecar: {path}\n"
                f"Errors: {error_messages}\n"
                f"See: plugins/autonomous-dev/config/hook-metadata.schema.json"
            )
    elif schema is not None and not HAS_JSONSCHEMA:
        print(
            f"WARNING: jsonschema not installed, skipping schema validation for {path.name}",
            file=sys.stderr,
        )

    return data


def detect_orphans(hooks_dir: Path, sidecars: list[dict]) -> dict[str, list[str]]:
    """Find hooks without sidecars and sidecars without hooks.

    Args:
        hooks_dir: Directory containing hook scripts and sidecars.
        sidecars: List of loaded sidecar data dicts.

    Returns:
        Dict with 'hooks_without_sidecars' and 'sidecars_without_hooks' lists.
    """
    # Collect sidecar names
    sidecar_names = set()
    for s in sidecars:
        sidecar_names.add(s["name"])

    # Find hook scripts (excluding archived, __init__.py, __pycache__, and .hook.json files)
    hook_scripts = set()
    for path in hooks_dir.iterdir():
        if path.is_file() and not path.name.startswith("__") and "archived" not in path.parts:
            if path.suffix in (".py", ".sh") and not path.name.endswith(".hook.json"):
                hook_scripts.add(path.stem)

    hooks_without_sidecars = sorted(hook_scripts - sidecar_names)
    sidecars_without_hooks = sorted(sidecar_names - hook_scripts)

    return {
        "hooks_without_sidecars": hooks_without_sidecars,
        "sidecars_without_hooks": sidecars_without_hooks,
    }


def generate_manifest_hooks(sidecars: list[dict]) -> list[str]:
    """Generate sorted list of file paths for manifest.

    Includes BOTH hook scripts AND .hook.json files.
    Maps interpreter to extension: python3 -> .py, bash -> .sh.

    Args:
        sidecars: List of loaded sidecar data dicts.

    Returns:
        Sorted list of file paths in 'plugins/autonomous-dev/hooks/{name}.{ext}' format.
    """
    files = []
    for sidecar in sidecars:
        name = sidecar["name"]
        interpreter = sidecar["interpreter"]
        ext = INTERPRETER_EXTENSIONS.get(interpreter, ".py")

        # Add the sidecar file itself
        files.append(f"plugins/autonomous-dev/hooks/{name}.hook.json")
        # Add the hook script
        files.append(f"plugins/autonomous-dev/hooks/{name}{ext}")

    return sorted(files)


def build_command_string(sidecar: dict) -> str:
    """Build command string from sidecar metadata.

    Sorted env vars + interpreter + ~/.claude/hooks/{name}.{ext}

    Args:
        sidecar: Loaded sidecar data dict.

    Returns:
        Command string, e.g.:
        'MCP_AUTO_APPROVE=true SANDBOX_ENABLED=false python3 ~/.claude/hooks/unified_pre_tool.py'

    Examples:
        No env: 'python3 ~/.claude/hooks/name.py'
        Bash: 'bash ~/.claude/hooks/name.sh'
    """
    name = sidecar["name"]
    interpreter = sidecar["interpreter"]
    ext = INTERPRETER_EXTENSIONS.get(interpreter, ".py")
    script_path = f"~/.claude/hooks/{name}{ext}"

    env_vars = sidecar.get("env", {})
    if env_vars:
        # Sort env vars alphabetically
        sorted_env = " ".join(
            f"{key}={value}" for key, value in sorted(env_vars.items())
        )
        return f"{sorted_env} {interpreter} {script_path}"

    return f"{interpreter} {script_path}"


def resolve_timeout(hook_name: str, budgets: dict | None = None) -> int:
    """Return the canonical budget for ``hook_name``, in seconds.

    Issue #1704. This function replaced ``reg.get("timeout", 5)``. The sidecar
    is NO LONGER consulted for a timeout: a sidecar-declared timeout would be a
    second declaration of a number the budget file owns, which is the exact
    defect being removed. ``test_no_sidecar_declares_a_timeout`` refuses any
    sidecar that declares one.

    Args:
        hook_name: Hook identifier from the sidecar ``name`` field.
        budgets: Pre-loaded budget config (from
            ``hook_budgets.load_budget_config``). Loaded from disk when None.

    Returns:
        Budget in seconds.

    Raises:
        RuntimeError: If the ``hook_budgets`` library is unavailable. Silently
            substituting a literal here is how the original 5 propagated to
            every surface, so this fails loudly instead.
    """
    if hook_budgets is None:
        raise RuntimeError(
            f"Cannot resolve a timeout for {hook_name!r}: the hook_budgets "
            f"library is unavailable.\n"
            f"Expected: plugins/autonomous-dev/lib/hook_budgets.py on sys.path\n"
            f"See: plugins/autonomous-dev/config/hook_time_budgets.json (Issue #1704)"
        )
    return hook_budgets.get_hook_budget(hook_name, budgets)


def generate_settings_hooks(
    sidecars: list[dict], *, budgets: dict | None = None
) -> dict[str, list[dict]]:
    """Generate settings hooks object from LIFECYCLE sidecars only.

    Utility hooks are excluded. Inactive hooks are excluded.
    Groups by event. Builds command strings. Sorts events alphabetically.
    Within each event, specific matchers come before wildcard "*".

    Timeouts come from the canonical budget file (Issue #1704), never from the
    sidecar and never from a literal default in this module.

    Args:
        sidecars: List of loaded sidecar data dicts.
        budgets: Pre-loaded budget config. Loaded from disk when None.

    Returns:
        Settings hooks dict matching global_settings_template.json format.
    """
    # Filter to active lifecycle hooks only
    lifecycle_sidecars = [
        s for s in sidecars
        if s.get("type") == "lifecycle" and s.get("active", True) is True
    ]

    # Group registrations by event
    events: dict[str, list[dict]] = {}
    for sidecar in lifecycle_sidecars:
        command = build_command_string(sidecar)
        timeout = resolve_timeout(sidecar["name"], budgets)
        for reg in sidecar.get("registrations", []):
            event = reg["event"]
            matcher = reg.get("matcher", "*")

            if event not in events:
                events[event] = []

            events[event].append({
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                        "timeout": timeout,
                    }
                ],
            })

    # Sort: events alphabetically, within each event specific matchers before wildcard
    result: dict[str, list[dict]] = {}
    for event in sorted(events.keys()):
        entries = events[event]
        # Specific matchers (non-"*") first, then wildcards
        specific = [e for e in entries if e["matcher"] != "*"]
        wildcards = [e for e in entries if e["matcher"] == "*"]
        # Sort within each group by matcher name for determinism
        specific.sort(key=lambda e: e["matcher"])
        wildcards.sort(key=lambda e: e["hooks"][0]["command"])
        result[event] = specific + wildcards

    return result


# ---------------------------------------------------------------------------
# Cross-surface timeout sync (Issue #1704)
# ---------------------------------------------------------------------------


def _is_registration_block(hooks_value: Any) -> bool:
    """Report whether a JSON ``hooks`` value is a real registration block.

    Discrimination matters: ``plugin.json`` carries ``"hooks": {"active": 27,
    "archived": 61}`` -- a component COUNT, not registrations -- and a naive
    "has a hooks key" sweep counts it as a settings surface. It is not one.

    Args:
        hooks_value: The value of a top-level ``hooks`` key.

    Returns:
        True when the value maps event names to lists of matcher entries.
    """
    if not isinstance(hooks_value, dict) or not hooks_value:
        return False
    for entries in hooks_value.values():
        if not isinstance(entries, list):
            return False
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                return False
    return True


def discover_settings_surfaces(root: Path) -> list[Path]:
    """Find every JSON file under ``root`` carrying hook registrations.

    Discovery is BY CONTENT, never by a ``settings*.json`` glob. A glob misses
    ``config/global_settings_template.json`` -- which alone carries 16
    bindings -- and would silently leave it at the old value.

    Args:
        root: Directory to search beneath (normally the plugin root).

    Returns:
        Sorted list of paths whose top-level ``hooks`` key is a registration
        block. Files whose ``hooks`` key holds something else are excluded.

    Raises:
        FileNotFoundError: If ``root`` does not exist.
    """
    if not root.is_dir():
        raise FileNotFoundError(
            f"Settings-surface root not found: {root}\n"
            f"Expected: the plugin directory containing config/ and templates/\n"
            f"See: docs/HOOKS.md"
        )

    surfaces: list[Path] = []
    for path in sorted(root.rglob("*.json")):
        if any(part in ("__pycache__", "archived", "node_modules") for part in path.parts):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and _is_registration_block(data.get("hooks")):
            surfaces.append(path)
    return surfaces


def _hook_name_from_command(command: str) -> str | None:
    """Extract the hook basename (no extension) from a settings command string.

    Args:
        command: The ``command`` field of a settings hook entry.

    Returns:
        The hook name, or None when the command runs no script (e.g. a bare
        ``echo`` banner, which carries no budget and must not be rewritten).
    """
    match = _COMMAND_SCRIPT_RE.search(str(command))
    if match is None:
        return None
    return match.group(1)


def collect_timeout_drift(
    surfaces: list[Path], budgets: dict | None = None
) -> list[tuple[Path, str, str, int | None, int]]:
    """Return every settings entry whose timeout differs from the canonical one.

    Args:
        surfaces: Paths returned by :func:`discover_settings_surfaces`.
        budgets: Pre-loaded budget config. Loaded from disk when None.

    Issue #1704 remediation (W6). An entry whose hook HAS a declared budget but
    carries NO bound on this surface is DRIFT, not a warning: the budget exists
    and the surface is ignoring it. Only an entry with neither a budget nor a
    bound is a warning (:func:`collect_unbounded_entries`) -- there is nothing
    declared to sync, and adding an unjustified bound is a different change
    with different risk (``auto_format`` running black on a large file may
    legitimately need longer).

    Entries whose hook has NO budget entry at all are returned by
    :func:`collect_unbudgeted_entries` and are a hard error, never defaulted.

    Returns:
        List of ``(path, event, hook_name, current_timeout, canonical_timeout)``
        tuples. ``current_timeout`` is None for the "budgeted but unbound" case.
    """
    drift: list[tuple[Path, str, str, int | None, int]] = []
    for path, event, hook_name, hook_entry in _iter_hook_entries(surfaces):
        if not _has_budget(hook_name, budgets):
            continue  # collect_unbudgeted_entries owns this class
        current = hook_entry.get("timeout")
        canonical = resolve_timeout(hook_name, budgets)
        if current != canonical:
            drift.append((path, event, hook_name, current, canonical))
    return drift


def collect_unbudgeted_entries(
    surfaces: list[Path], budgets: dict | None = None
) -> list[tuple[Path, str, str, int | None]]:
    """Return entries whose hook has NO entry in the canonical budget file.

    Issue #1704 remediation (BLOCKING-1). ``sync_timeouts`` previously called
    ``resolve_timeout`` for these and got the silent default -- rewriting a
    declared bound down to 5 across every surface and exiting 0. That is
    ``reg.get("timeout", 5)``, the line this issue names as the origin of the
    sprawl, reintroduced in the WRITE path. An undeclared hook is now refused,
    never defaulted.

    Args:
        surfaces: Paths returned by :func:`discover_settings_surfaces`.
        budgets: Pre-loaded budget config. Loaded from disk when None.

    Returns:
        List of ``(path, event, hook_name, current_timeout)`` tuples.
    """
    return [
        (path, event, hook_name, hook_entry.get("timeout"))
        for path, event, hook_name, hook_entry in _iter_hook_entries(surfaces)
        if not _has_budget(hook_name, budgets)
        and hook_entry.get("timeout") is not None
    ]


def collect_unbounded_entries(
    surfaces: list[Path], budgets: dict | None = None
) -> list[tuple[Path, str, str]]:
    """Return entries with NEITHER a declared budget NOR a bound.

    Nothing is declared for these, so there is nothing to sync and no evidence
    on which to invent a bound. Reported, never auto-filled. An entry with a
    budget but no bound is DRIFT (see :func:`collect_timeout_drift`), not this.

    Args:
        surfaces: Paths returned by :func:`discover_settings_surfaces`.
        budgets: Pre-loaded budget config. Loaded from disk when None.

    Returns:
        List of ``(path, event, hook_name)`` tuples.
    """
    return [
        (path, event, hook_name)
        for path, event, hook_name, hook_entry in _iter_hook_entries(surfaces)
        if hook_entry.get("timeout") is None and not _has_budget(hook_name, budgets)
    ]


def _display_path(path: Path) -> str:
    """Return ``path`` relative to the project root, or absolute if outside it.

    ``Path.relative_to`` RAISES for a path outside the anchor, so the reporting
    loops crashed on any surface that is not under ``PROJECT_ROOT`` -- which is
    every surface in a test fixture, and any absolute path a caller passes in.
    A reporter that crashes while printing a violation loses the violation.

    Args:
        path: Path to render.

    Returns:
        A display string. Never raises.
    """
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _has_budget(hook_name: str, budgets: dict | None = None) -> bool:
    """Report whether ``hook_name`` has an explicit canonical budget entry.

    Args:
        hook_name: Hook identifier.
        budgets: Pre-loaded budget config. Loaded from disk when None.

    Returns:
        True when an explicit entry exists.

    Raises:
        RuntimeError: If the ``hook_budgets`` library is unavailable.
    """
    if hook_budgets is None:
        raise RuntimeError(
            f"Cannot determine whether {hook_name!r} is budgeted: the "
            f"hook_budgets library is unavailable.\n"
            f"Expected: plugins/autonomous-dev/lib/hook_budgets.py on sys.path\n"
            f"See: plugins/autonomous-dev/config/hook_time_budgets.json (Issue #1704)"
        )
    return hook_budgets.has_hook_budget(hook_name, budgets)


def _iter_hook_entries(surfaces: list[Path]):
    """Yield ``(path, event, hook_name, hook_entry)`` for every script entry.

    Entries whose command runs no script (a bare ``echo`` banner, for example)
    are skipped: they carry no budget and must not be rewritten.

    Args:
        surfaces: Paths returned by :func:`discover_settings_surfaces`.

    Yields:
        Tuples of surface path, event name, hook name and the mutable entry.
    """
    for path in surfaces:
        data = json.loads(path.read_text(encoding="utf-8"))
        for event, entries in data.get("hooks", {}).items():
            for entry in entries:
                for hook_entry in entry.get("hooks", []):
                    hook_name = _hook_name_from_command(hook_entry.get("command", ""))
                    if hook_name is None:
                        continue
                    yield path, event, hook_name, hook_entry


def sync_timeouts(
    surfaces: list[Path], budgets: dict | None = None, *, verbose: bool = False
) -> int:
    """Rewrite the ``timeout`` field of every hook entry from the canonical source.

    Only the ``timeout`` field is touched. Hook SELECTION per template is
    hand-curated on purpose (``settings.strict-mode.json`` and
    ``settings.granular-bash.json`` deliberately register different subsets),
    so regenerating those files wholesale would destroy intent.

    Two refusals guard the write (Issue #1704 remediation, BLOCKING-1):

    1. **Nothing is written until the config validates.** ``check_ceiling``,
       ``check_nesting`` and ``check_declared_hosts_match_derived`` run FIRST.
       Previously this function validated nothing before touching 7 files, so a
       config that violated the very constraints this issue added would still be
       propagated everywhere.
    2. **An undeclared hook is refused, not defaulted.** A missing or mistyped
       key used to resolve to the silent default and rewrite that hook down to
       5 across every surface, exiting 0 -- the sprawl's origin line
       reintroduced in the write path. Note the asymmetry that made it easy to
       miss: this function refused to ADD an unjustified bound while happily
       REMOVING a justified one.

    Args:
        surfaces: Paths returned by :func:`discover_settings_surfaces`.
        budgets: Pre-loaded budget config. Loaded from disk when None.
        verbose: Print each rewritten entry.

    Returns:
        Number of entries updated.

    Raises:
        RuntimeError: If the canonical config fails validation, or if any
            surface registers a hook with no budget entry.
    """
    violations: list[str] = []
    for checker in (
        hook_budgets.check_ceiling,
        hook_budgets.check_nesting,
        hook_budgets.check_declared_hosts_match_derived,
    ):
        violations.extend(f"{checker.__name__}: {v}" for v in checker(budgets))
    if violations:
        raise RuntimeError(
            "Refusing to write: the canonical budget config does not validate.\n"
            + "\n".join(f"  {v}" for v in violations)
            + "\nExpected: check_ceiling, check_nesting and "
            "check_declared_hosts_match_derived all clean before any surface "
            "is touched.\nSee: docs/HOOKS.md (Issue #1704)"
        )

    unbudgeted = collect_unbudgeted_entries(surfaces, budgets)
    if unbudgeted:
        raise RuntimeError(
            "Refusing to overwrite a declared bound with an undeclared "
            "default. These registrations carry a timeout but have NO entry in "
            "hook_time_budgets.json:\n"
            + "\n".join(
                f"  {p}: {ev}/{hk} has timeout={cur}" for p, ev, hk, cur in unbudgeted
            )
            + "\nExpected: add each hook to the 'hooks' object with a measured "
            "budget, or correct the spelling.\n"
            "See: docs/HOOKS.md (Issue #1704)"
        )

    updated = 0
    for path in surfaces:
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for event, entries in data.get("hooks", {}).items():
            for entry in entries:
                for hook_entry in entry.get("hooks", []):
                    hook_name = _hook_name_from_command(hook_entry.get("command", ""))
                    if hook_name is None:
                        continue
                    current = hook_entry.get("timeout")
                    if current is None and not _has_budget(hook_name, budgets):
                        # Neither declared nor bound: nothing to sync, and no
                        # evidence on which to invent a bound. See
                        # collect_unbounded_entries.
                        continue
                    canonical = resolve_timeout(hook_name, budgets)
                    if current != canonical:
                        if verbose:
                            print(
                                f"  {path.name}: {event}/{hook_name} "
                                f"{current} -> {canonical}"
                            )
                        hook_entry["timeout"] = canonical
                        changed = True
                        updated += 1
        if changed:
            # Key ORDER is preserved here (unlike atomic_write_json, which
            # sorts): these are hand-curated files and a wholesale re-key would
            # bury a one-field change in a whole-file diff.
            atomic_write_json(path, data, sort_keys=False)
    return updated


def atomic_write_json(file_path: Path, data: Any, *, sort_keys: bool = True) -> None:
    """Write JSON data to file atomically.

    Uses tempfile + os.replace for atomic write to prevent corruption.

    Args:
        file_path: Target file path.
        data: Data to serialize as JSON.
        sort_keys: Sort object keys. True for generated files (deterministic
            output); False for hand-curated settings surfaces, where a
            wholesale re-key would bury a one-field timeout change.

    Raises:
        OSError: If file cannot be written.
    """
    temp_fd, temp_path = tempfile.mkstemp(
        dir=str(file_path.parent), suffix=".json"
    )
    try:
        with os.fdopen(temp_fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=sort_keys)
            f.write("\n")  # trailing newline
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, str(file_path))
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def load_schema(schema_path: Path) -> dict | None:
    """Load JSON Schema from file if it exists.

    Args:
        schema_path: Path to the schema file.

    Returns:
        Parsed schema dict, or None if file does not exist.
    """
    if schema_path.is_file():
        with open(schema_path, encoding="utf-8") as f:
            return json.load(f)
    return None


def check_drift(
    *,
    hooks_dir: Path,
    manifest_path: Path,
    settings_path: Path,
    schema_path: Path,
    verbose: bool = False,
) -> int:
    """Check for drift between sidecars and config files.

    Args:
        hooks_dir: Directory containing hook scripts and sidecars.
        manifest_path: Path to install_manifest.json.
        settings_path: Path to global_settings_template.json.
        schema_path: Path to hook-metadata.schema.json.
        verbose: Print detailed comparison info.

    Returns:
        0 if no drift, 1 if drift detected.
    """
    schema = load_schema(schema_path)

    try:
        sidecar_paths = discover_sidecars(hooks_dir)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1

    sidecars = []
    errors = []
    for path in sidecar_paths:
        try:
            data = load_and_validate_sidecar(path, schema)
            sidecars.append(data)
        except ValueError as e:
            errors.append(str(e))

    if errors:
        print("Sidecar validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    # Check orphans
    orphans = detect_orphans(hooks_dir, sidecars)
    has_orphans = False
    if orphans["hooks_without_sidecars"]:
        has_orphans = True
        if verbose:
            print(f"Hooks without sidecars: {orphans['hooks_without_sidecars']}")
    if orphans["sidecars_without_hooks"]:
        has_orphans = True
        if verbose:
            print(f"Sidecars without hooks: {orphans['sidecars_without_hooks']}")

    # Generate expected config
    expected_manifest_hooks = generate_manifest_hooks(sidecars)
    expected_settings_hooks = generate_settings_hooks(sidecars)

    drift_found = False

    # Compare manifest
    if manifest_path.is_file():
        with open(manifest_path, encoding="utf-8") as f:
            current_manifest = json.load(f)
        current_hooks = current_manifest.get("components", {}).get("hooks", {}).get("files", [])
        if current_hooks != expected_manifest_hooks:
            drift_found = True
            if verbose:
                current_set = set(current_hooks)
                expected_set = set(expected_manifest_hooks)
                added = sorted(expected_set - current_set)
                removed = sorted(current_set - expected_set)
                if added:
                    print(f"Manifest: would add {added}")
                if removed:
                    print(f"Manifest: would remove {removed}")
            else:
                print("Manifest hooks.files: DRIFT DETECTED")
    else:
        drift_found = True
        print(f"Manifest file not found: {manifest_path}")

    # Compare settings
    if settings_path.is_file():
        with open(settings_path, encoding="utf-8") as f:
            current_settings = json.load(f)
        current_hooks_section = current_settings.get("hooks", {})
        if current_hooks_section != expected_settings_hooks:
            drift_found = True
            if verbose:
                current_events = set(current_hooks_section.keys())
                expected_events = set(expected_settings_hooks.keys())
                added_events = sorted(expected_events - current_events)
                removed_events = sorted(current_events - expected_events)
                if added_events:
                    print(f"Settings: would add events {added_events}")
                if removed_events:
                    print(f"Settings: would remove events {removed_events}")
                # Show per-event drift
                for event in sorted(expected_events & current_events):
                    if current_hooks_section[event] != expected_settings_hooks[event]:
                        print(f"Settings: event '{event}' has drift")
            else:
                print("Settings hooks: DRIFT DETECTED")
    else:
        drift_found = True
        print(f"Settings file not found: {settings_path}")

    if not drift_found and not has_orphans:
        print("No drift detected.")
        return 0

    if has_orphans and verbose:
        print("Orphan hooks/sidecars detected (not blocking).")

    if drift_found:
        print("Drift detected. Run with --write to update.")
        return 1

    return 0


def write_config(
    *,
    hooks_dir: Path,
    manifest_path: Path,
    settings_path: Path,
    schema_path: Path,
    verbose: bool = False,
) -> int:
    """Update config files from sidecar metadata.

    Only replaces the hooks sections. Preserves all other content.

    Args:
        hooks_dir: Directory containing hook scripts and sidecars.
        manifest_path: Path to install_manifest.json.
        settings_path: Path to global_settings_template.json.
        schema_path: Path to hook-metadata.schema.json.
        verbose: Print detailed update info.

    Returns:
        0 on success, 1 on validation errors.
    """
    schema = load_schema(schema_path)
    sidecar_paths = discover_sidecars(hooks_dir)

    sidecars = []
    errors = []
    for path in sidecar_paths:
        try:
            data = load_and_validate_sidecar(path, schema)
            sidecars.append(data)
        except ValueError as e:
            errors.append(str(e))

    if errors:
        print("Sidecar validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    # Generate configs
    manifest_hooks = generate_manifest_hooks(sidecars)
    settings_hooks = generate_settings_hooks(sidecars)

    # Update manifest - preserve everything except components.hooks.files
    if manifest_path.is_file():
        with open(manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)
    else:
        manifest_data = {"components": {"hooks": {"files": []}}}

    if "components" not in manifest_data:
        manifest_data["components"] = {}
    if "hooks" not in manifest_data["components"]:
        manifest_data["components"]["hooks"] = {}

    manifest_data["components"]["hooks"]["files"] = manifest_hooks
    atomic_write_json(manifest_path, manifest_data)
    if verbose:
        print(f"Updated manifest: {manifest_path} ({len(manifest_hooks)} hook files)")

    # Update settings - preserve everything except hooks
    if settings_path.is_file():
        with open(settings_path, encoding="utf-8") as f:
            settings_data = json.load(f)
    else:
        settings_data = {}

    settings_data["hooks"] = settings_hooks
    atomic_write_json(settings_path, settings_data)
    if verbose:
        print(f"Updated settings: {settings_path} ({len(settings_hooks)} events)")

    print("Config files updated successfully.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace object.
    """
    parser = argparse.ArgumentParser(
        description="Generate hook config from .hook.json sidecars"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--check",
        action="store_true",
        help="Report drift without modifying",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="Update config files",
    )
    group.add_argument(
        "--check-timeouts",
        action="store_true",
        help="Report timeout drift across every settings surface (Issue #1704)",
    )
    group.add_argument(
        "--sync-timeouts",
        action="store_true",
        help="Write canonical timeouts into every settings surface (Issue #1704)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output",
    )
    parser.add_argument(
        "--allow-skew",
        action="store_true",
        help=(
            "Acknowledge a known pre-deploy window: report skew between the "
            "canonical budgets and the INSTALLED settings without failing. "
            "Skew is normally exit 1 (Issue #1704)."
        ),
    )
    parser.add_argument(
        "--hooks-dir",
        type=Path,
        default=None,
        help="Path to hooks directory (default: auto-detect)",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Path to install_manifest.json (default: auto-detect)",
    )
    parser.add_argument(
        "--settings-path",
        type=Path,
        default=None,
        help="Path to global_settings_template.json (default: auto-detect)",
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=None,
        help="Path to hook-metadata.schema.json (default: auto-detect)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0=success, 1=drift/errors, 2=CLI errors.
    """
    try:
        args = parse_args(argv)
    except SystemExit as e:
        return 2 if e.code != 0 else 0

    hooks_dir = args.hooks_dir or HOOKS_DIR
    manifest_path = args.manifest_path or MANIFEST_PATH
    settings_path = args.settings_path or SETTINGS_PATH
    schema_path = args.schema_path or SCHEMA_PATH

    if args.check:
        return check_drift(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=schema_path,
            verbose=args.verbose,
        )
    elif args.write:
        return write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=schema_path,
            verbose=args.verbose,
        )
    elif args.check_timeouts or args.sync_timeouts:
        surfaces = discover_settings_surfaces(PLUGIN_ROOT)
        if not surfaces:
            # A sweep that finds nothing is a broken sweep, not a clean repo.
            print(
                f"No settings surfaces found beneath {PLUGIN_ROOT}. Expected at "
                f"least config/global_settings_template.json.",
                file=sys.stderr,
            )
            return 1
        if args.verbose:
            print(f"Surfaces discovered by content ({len(surfaces)}):")
            for surface in surfaces:
                print(f"  {_display_path(surface)}")
        if args.sync_timeouts:
            try:
                updated = sync_timeouts(surfaces, verbose=args.verbose)
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"Timeout sync complete: {updated} entr(y/ies) updated.")
            return 0

        unbudgeted = collect_unbudgeted_entries(surfaces)
        if unbudgeted:
            print(
                f"REFUSED: {len(unbudgeted)} registration(s) carry a timeout "
                f"but have NO canonical budget entry:"
            )
            for path, event, hook_name, current in unbudgeted:
                print(
                    f"  {_display_path(path)}: {event}/{hook_name} "
                    f"has timeout={current}, budget=UNDECLARED"
                )
            print("  --sync-timeouts would overwrite these with a default. Fixed?")
            return 1

        skew = hook_budgets.check_installed_settings_skew()
        if skew:
            print(
                f"SKEW between the canonical config and the INSTALLED settings "
                f"({len(skew)}):"
            )
            for message in skew:
                print(f"  {message}")
            if not args.allow_skew:
                print(
                    "  Run `bash scripts/deploy-all.sh --global-settings`, or "
                    "pass --allow-skew to acknowledge a known pre-deploy window."
                )
                return 1
            print("  ACKNOWLEDGED via --allow-skew (pre-deploy window).")

        unbounded = collect_unbounded_entries(surfaces)
        if unbounded:
            print(f"WARNING: {len(unbounded)} entr(y/ies) declare NO timeout:")
            for path, event, hook_name in unbounded:
                print(f"  {_display_path(path)}: {event}/{hook_name}")
            print(
                "  These are bounded only by the runtime default, which this "
                "repo has never measured. Reported, not auto-filled."
            )
        drift = collect_timeout_drift(surfaces)
        if not drift:
            print(f"No timeout drift across {len(surfaces)} settings surface(s).")
            return 0
        print(f"Timeout drift detected in {len(drift)} entr(y/ies):")
        for path, event, hook_name, current, canonical in drift:
            print(
                f"  {_display_path(path)}: {event}/{hook_name} "
                f"has {current}, canonical is {canonical}"
            )
        print("Run with --sync-timeouts to update.")
        return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
