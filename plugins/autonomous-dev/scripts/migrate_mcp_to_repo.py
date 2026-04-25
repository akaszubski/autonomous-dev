#!/usr/bin/env python3
"""
Migrate MCP Server CLI - Issue #948.

Copies a single MCP server definition from ``~/.claude/settings.json``
``mcpServers`` (global) to a per-repo ``<repo>/.mcp.json`` file. Per the
issue: per-repo ``.mcp.json`` is the recommended default — global servers
inject tool-call definitions into every prompt, regardless of relevance.

Behavior:
    - Reads global settings.json (defaults to ~/.claude/settings.json)
    - Identifies the named server in ``mcpServers``
    - Reads or initializes <repo>/.mcp.json (preserves existing servers)
    - Writes back atomically (temp file + os.rename)
    - Detects inline secrets via lib/secret_patterns.py and adds .mcp.json
      to .gitignore when secrets are found
    - Source-side global ``mcpServers`` is NOT modified (non-destructive)
    - Always exits 0; callers parse JSON output for status

Usage:
    # Migrate one server
    python3 migrate_mcp_to_repo.py --server github --repo /path/to/repo

    # Use custom global settings path
    python3 migrate_mcp_to_repo.py --server github --repo /path \
        --global ~/.claude/settings.json

    # Dry run (no writes)
    python3 migrate_mcp_to_repo.py --server github --repo /path --dry-run

    # Check-only mode (scan existing .mcp.json for secrets, no migration)
    python3 migrate_mcp_to_repo.py --check-only --repo /path

JSON return shape (success):
    {
      "success": true,
      "server": "github",
      "target": "/path/to/repo/.mcp.json",
      "secrets_detected": true,
      "secret_pattern": "GitHub personal access token",
      "gitignored": true,
      "dry_run": false,
      "message": "Migrated server 'github' to /path/.mcp.json"
    }

JSON return shape (error):
    {
      "success": false,
      "error": "server_not_found",
      "message": "Server 'foo' not found in /home/u/.claude/settings.json"
    }

Error codes:
    - server_not_found: server name not in global config
    - global_not_found: ~/.claude/settings.json missing
    - invalid_global_json: malformed JSON in global settings
    - repo_not_found: repo path doesn't exist
    - write_failed: permission denied or other write error
    - missing_args: required arguments not provided

See Also:
    plugins/autonomous-dev/lib/secret_patterns.py - reused secret detection
    plugins/autonomous-dev/scripts/configure_global_settings.py - JSON pattern
    plugins/autonomous-dev/scripts/strip_duplicate_hooks.py - atomic write pattern

Issue: #948
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import COMPILED_SECRET_PATTERNS from lib/secret_patterns.py.
# Match the dev/installed fallback pattern used by sync_validator.py:31-42
# and strip_duplicate_hooks.py:58-79.
try:
    from plugins.autonomous_dev.lib.secret_patterns import COMPILED_SECRET_PATTERNS
except ImportError:
    try:
        from autonomous_dev.lib.secret_patterns import (  # type: ignore[no-redef]
            COMPILED_SECRET_PATTERNS,
        )
    except ImportError:
        # Last-resort: add lib/ to sys.path (script run directly from
        # plugins/autonomous-dev/scripts/).
        _LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
        if str(_LIB_DIR) not in sys.path:
            sys.path.insert(0, str(_LIB_DIR))
        from secret_patterns import (  # type: ignore[no-redef]
            COMPILED_SECRET_PATTERNS,
        )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Match ${VAR} or ${VAR:-default} placeholders so we don't false-positive on
# environment indirection like "${GITHUB_TOKEN}".
_ENV_VAR_PLACEHOLDER = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*(:-[^}]*)?\}$")


# ---------------------------------------------------------------------------
# IO primitives
# ---------------------------------------------------------------------------


def load_global_mcp_servers(global_path: Path) -> Dict[str, Any]:
    """Load the ``mcpServers`` block from ``~/.claude/settings.json``.

    Args:
        global_path: Path to global settings.json.

    Returns:
        The mcpServers dict (empty if file absent or no mcpServers key).

    Raises:
        FileNotFoundError: If the global settings file does not exist.
        json.JSONDecodeError: If the global settings JSON is malformed.
    """
    if not global_path.exists():
        raise FileNotFoundError(f"Global settings not found: {global_path}")
    raw = global_path.read_text(encoding="utf-8")
    settings = json.loads(raw)
    if not isinstance(settings, dict):
        return {}
    servers = settings.get("mcpServers", {})
    if not isinstance(servers, dict):
        return {}
    return servers


def load_or_init_repo_mcp(repo_path: Path) -> Dict[str, Any]:
    """Load ``<repo>/.mcp.json`` or return a fresh ``{"mcpServers": {}}``.

    Args:
        repo_path: Path to the repo root.

    Returns:
        Parsed dict with at least ``{"mcpServers": {...}}``.
    """
    target = repo_path / ".mcp.json"
    if not target.exists():
        return {"mcpServers": {}}
    try:
        raw = target.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        # Treat unreadable / malformed .mcp.json as starting fresh.
        return {"mcpServers": {}}
    if not isinstance(data, dict):
        return {"mcpServers": {}}
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}
    return data


def merge_server(
    repo_mcp: Dict[str, Any],
    server_name: str,
    server_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Add or overwrite a server entry under ``mcpServers[server_name]``.

    Args:
        repo_mcp: Parsed repo .mcp.json content.
        server_name: Name to set under mcpServers.
        server_config: Server configuration dict (will be deep-copied).

    Returns:
        A deep copy of ``repo_mcp`` with the merge applied. The input
        dict is NOT mutated.
    """
    out = copy.deepcopy(repo_mcp)
    if "mcpServers" not in out or not isinstance(out["mcpServers"], dict):
        out["mcpServers"] = {}
    out["mcpServers"][server_name] = copy.deepcopy(server_config)
    return out


# ---------------------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------------------


def _flatten_strings(value: Any) -> List[str]:
    """Recursively yield all string values in a nested dict/list/scalar.

    Args:
        value: Arbitrary JSON-shaped value.

    Returns:
        List of every string encountered (in deterministic order).
    """
    out: List[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_flatten_strings(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_flatten_strings(v))
    # Other scalars (int, bool, None) ignored.
    return out


def contains_secret(server_config: Dict[str, Any]) -> Tuple[bool, str]:
    """Detect inline credentials anywhere in ``server_config``.

    Walks the entire structure (nested ``env`` dicts, ``args`` lists,
    arbitrary depth) and matches each string value against
    ``COMPILED_SECRET_PATTERNS`` from ``lib/secret_patterns.py``.

    False-positive guard: pure environment placeholders like
    ``${GITHUB_TOKEN}`` or ``${BRAVE_API_KEY}`` are NOT treated as secrets.

    Args:
        server_config: Server configuration dict (single server's value).

    Returns:
        ``(True, description)`` on first match, ``(False, "")`` otherwise.
    """
    for s in _flatten_strings(server_config):
        # Skip pure env-var indirection — these are NOT secrets, they are
        # references to secrets resolved at runtime.
        if _ENV_VAR_PLACEHOLDER.match(s.strip()):
            continue
        for pattern, description in COMPILED_SECRET_PATTERNS:
            if pattern.search(s):
                return True, description
    return False, ""


# ---------------------------------------------------------------------------
# Gitignore helpers
# ---------------------------------------------------------------------------


def ensure_gitignore(repo_path: Path, entry: str = ".mcp.json") -> bool:
    """Append ``entry`` to ``<repo>/.gitignore`` if not already present.

    Mirrors the setup.md (lines 99-108) bash pattern:
        - If .gitignore missing, create with the entry on its own line
        - If .gitignore exists and lacks the entry (anchored regex match),
          append it on a new line
        - If the entry is already present, no-op

    Args:
        repo_path: Path to repo root.
        entry: Line to add (default ".mcp.json").

    Returns:
        True if the file was created or modified, False if no change needed.
    """
    gitignore = repo_path / ".gitignore"
    pattern = re.compile(rf"^{re.escape(entry)}$", re.MULTILINE)

    if not gitignore.exists():
        gitignore.write_text(entry + "\n", encoding="utf-8")
        return True

    content = gitignore.read_text(encoding="utf-8")
    if pattern.search(content):
        return False

    # Append, ensuring trailing newline behaviour matches the existing file.
    if content and not content.endswith("\n"):
        content += "\n"
    content += entry + "\n"
    gitignore.write_text(content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def atomic_write_json(path: Path, data: Dict[str, Any], *, mode: int = 0o644) -> None:
    """Write JSON atomically: temp file in same dir, then ``os.rename``.

    Args:
        path: Destination path.
        data: Dictionary to serialize.
        mode: File permissions to set after write (default 0o644).

    Raises:
        OSError: If the write or rename fails.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd: Optional[int] = None
    temp_path: Optional[str] = None
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".mcp-migrate-",
            suffix=".json.tmp",
        )
        payload = json.dumps(data, indent=2, sort_keys=False) + "\n"
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
        fd = None
        os.chmod(temp_path, mode)
        os.rename(temp_path, path)
    except OSError:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _result(
    *,
    success: bool,
    server: Optional[str] = None,
    target: Optional[str] = None,
    secrets_detected: bool = False,
    secret_pattern: str = "",
    gitignored: bool = False,
    dry_run: bool = False,
    message: str = "",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the canonical JSON result dict."""
    out: Dict[str, Any] = {
        "success": success,
        "server": server,
        "target": target,
        "secrets_detected": secrets_detected,
        "secret_pattern": secret_pattern,
        "gitignored": gitignored,
        "dry_run": dry_run,
        "message": message,
    }
    if error is not None:
        out["error"] = error
    return out


def check_only(repo_path: Path) -> Dict[str, Any]:
    """Scan an existing ``<repo>/.mcp.json`` for inline secrets.

    Used by setup.md Step 1.6 to decide whether to gitignore .mcp.json
    after creating it from a template (or finding it pre-existing).

    Args:
        repo_path: Path to repo root.

    Returns:
        Result dict with ``secrets_detected`` set; success=True even if
        the file is missing (treated as "no secrets").
    """
    if not repo_path.exists() or not repo_path.is_dir():
        return _result(
            success=False,
            error="repo_not_found",
            message=f"Repo path not found or not a directory: {repo_path}",
        )

    target = repo_path / ".mcp.json"
    if not target.exists():
        return _result(
            success=True,
            target=str(target),
            message=f"No .mcp.json at {target} — nothing to check",
        )

    try:
        raw = target.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        return _result(
            success=False,
            target=str(target),
            error="invalid_repo_json",
            message=f"Cannot parse {target}: {e}",
        )

    servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
    if not isinstance(servers, dict):
        servers = {}

    detected = False
    pattern = ""
    for _, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        ok, desc = contains_secret(cfg)
        if ok:
            detected = True
            pattern = desc
            break

    return _result(
        success=True,
        target=str(target),
        secrets_detected=detected,
        secret_pattern=pattern,
        message=(
            f"Inline secret detected: {pattern}"
            if detected
            else "No inline secrets detected"
        ),
    )


def migrate(
    *,
    server_name: str,
    repo_path: Path,
    global_path: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Copy a single server from global mcpServers to <repo>/.mcp.json.

    Args:
        server_name: Server key under ``mcpServers``.
        repo_path: Path to repo root.
        global_path: Path to global settings.json.
        dry_run: If True, return planned action without writing.

    Returns:
        JSON-serializable result dict.
    """
    # Validate repo path
    if not repo_path.exists() or not repo_path.is_dir():
        return _result(
            success=False,
            server=server_name,
            error="repo_not_found",
            message=f"Repo path not found or not a directory: {repo_path}",
            dry_run=dry_run,
        )

    # Load global mcpServers
    try:
        servers = load_global_mcp_servers(global_path)
    except FileNotFoundError:
        return _result(
            success=False,
            server=server_name,
            error="global_not_found",
            message=f"Global settings not found: {global_path}",
            dry_run=dry_run,
        )
    except json.JSONDecodeError as e:
        return _result(
            success=False,
            server=server_name,
            error="invalid_global_json",
            message=f"Invalid JSON in {global_path}: {e}",
            dry_run=dry_run,
        )
    except OSError as e:
        return _result(
            success=False,
            server=server_name,
            error="global_not_found",
            message=f"Cannot read global settings {global_path}: {e}",
            dry_run=dry_run,
        )

    if server_name not in servers:
        return _result(
            success=False,
            server=server_name,
            error="server_not_found",
            message=(
                f"Server '{server_name}' not found in {global_path}. "
                f"Available servers: {sorted(servers.keys()) or '(none)'}"
            ),
            dry_run=dry_run,
        )

    server_cfg = servers[server_name]
    if not isinstance(server_cfg, dict):
        return _result(
            success=False,
            server=server_name,
            error="invalid_server_config",
            message=f"Server '{server_name}' is not a JSON object",
            dry_run=dry_run,
        )

    # Detect secrets BEFORE merging — we need to know whether to gitignore
    # and whether to use 0o600 permissions on the destination.
    secrets_detected, secret_pattern = contains_secret(server_cfg)

    # Merge into existing repo .mcp.json (preserving any prior servers).
    repo_mcp = load_or_init_repo_mcp(repo_path)
    merged = merge_server(repo_mcp, server_name, server_cfg)

    target = repo_path / ".mcp.json"
    gitignored = False

    if dry_run:
        return _result(
            success=True,
            server=server_name,
            target=str(target),
            secrets_detected=secrets_detected,
            secret_pattern=secret_pattern,
            gitignored=False,
            dry_run=True,
            message=(
                f"DRY RUN: Would migrate server '{server_name}' to {target}. "
                f"Secrets detected: {secrets_detected}"
            ),
        )

    # Write atomically. Use 0o600 when secrets are present so the file is
    # owner-readable only — defence in depth even when gitignored.
    file_mode = 0o600 if secrets_detected else 0o644
    try:
        atomic_write_json(target, merged, mode=file_mode)
    except OSError as e:
        return _result(
            success=False,
            server=server_name,
            target=str(target),
            error="write_failed",
            message=f"Failed to write {target}: {e}",
            dry_run=False,
        )

    # If secrets detected, ensure .mcp.json is in .gitignore.
    if secrets_detected:
        try:
            gitignored = ensure_gitignore(repo_path, ".mcp.json")
        except OSError as e:
            # Non-fatal: file is written, just couldn't update .gitignore.
            return _result(
                success=True,
                server=server_name,
                target=str(target),
                secrets_detected=True,
                secret_pattern=secret_pattern,
                gitignored=False,
                dry_run=False,
                message=(
                    f"Migrated '{server_name}' but could not update "
                    f".gitignore: {e}. Add '.mcp.json' to .gitignore manually."
                ),
            )

    return _result(
        success=True,
        server=server_name,
        target=str(target),
        secrets_detected=secrets_detected,
        secret_pattern=secret_pattern,
        gitignored=gitignored,
        dry_run=False,
        message=(
            f"Migrated server '{server_name}' to {target}"
            + (
                f" (inline secret detected: {secret_pattern}; "
                f".gitignore updated)"
                if secrets_detected
                else ""
            )
        ),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate an MCP server entry from global "
            "~/.claude/settings.json to <repo>/.mcp.json. Issue #948."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--server",
        type=str,
        default=None,
        help="MCP server name to migrate (key under mcpServers).",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="Path to the target repo (where .mcp.json will be written).",
    )
    parser.add_argument(
        "--global",
        dest="global_path",
        type=Path,
        default=Path.home() / ".claude" / "settings.json",
        help="Path to global settings.json (default: ~/.claude/settings.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned action without writing files.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Scan existing <repo>/.mcp.json for inline secrets and exit. "
            "No migration is performed; --server is ignored."
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Always exits 0 — callers parse JSON for status."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.check_only:
        result = check_only(args.repo)
    else:
        if not args.server:
            result = _result(
                success=False,
                error="missing_args",
                message="--server <name> is required unless --check-only is set",
            )
        else:
            result = migrate(
                server_name=args.server,
                repo_path=args.repo,
                global_path=args.global_path,
                dry_run=args.dry_run,
            )

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
