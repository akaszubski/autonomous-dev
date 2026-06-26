"""GOA (Governance, Observability, Audit) CLI entry point.

Provides subcommands: start | stop | status | watch.

Usage (from repo root)::

    python3 plugins/autonomous-dev/lib/goa_cli.py start
    python3 plugins/autonomous-dev/lib/goa_cli.py start --record-trigger-id id1,id2,id3
    python3 plugins/autonomous-dev/lib/goa_cli.py stop
    python3 plugins/autonomous-dev/lib/goa_cli.py status
    python3 plugins/autonomous-dev/lib/goa_cli.py watch

Issue #1320 — MVP implementation, conservative-mode only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _import_goa_modules() -> tuple[Any, Any]:
    """Import goa_state and goa_watcher, adding lib dir to sys.path if needed."""
    _lib = Path(__file__).resolve().parent
    if str(_lib) not in sys.path:
        sys.path.insert(0, str(_lib))
    import goa_state  # type: ignore[import-untyped]
    import goa_watcher  # type: ignore[import-untyped]

    return goa_state, goa_watcher


# ---------------------------------------------------------------------------
# Subcommand: start
# ---------------------------------------------------------------------------

_CRON_WATCHER = "*/30 * * * *"
_CRON_PING = "*/15 * * * *"


def goa_start(args: argparse.Namespace) -> int:
    """Write the GOA manifest and print /schedule create lines.

    If ``--record-trigger-id id1,id2,id3`` is provided, updates the manifest
    with those cron trigger IDs.

    Args:
        args: Parsed CLI arguments.

    Returns:
        0 on success, 1 on error.
    """
    goa_state, _ = _import_goa_modules()

    manifest = goa_state.load_manifest()
    if manifest is None:
        manifest = {
            "version": goa_state.MANIFEST_VERSION,
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "trigger_ids": {"watcher": "", "ping": "", "deadman": ""},
            "thresholds": goa_state.DEFAULT_THRESHOLDS.copy(),
            "healthcheck_uuid": "",
        }
        goa_state.save_manifest(manifest)
        print("GOA: manifest created.")
    else:
        print("GOA: manifest already exists (reusing).")

    # Record trigger IDs if supplied
    if hasattr(args, "record_trigger_id") and args.record_trigger_id:
        parts = [p.strip() for p in args.record_trigger_id.split(",")]
        ids = (parts + ["", "", ""])[:3]
        manifest["trigger_ids"] = {
            "watcher": ids[0],
            "ping": ids[1],
            "deadman": ids[2],
        }
        goa_state.save_manifest(manifest)
        print(f"GOA: trigger IDs recorded: {manifest['trigger_ids']}")

    # Print /schedule create instructions
    goa_cli_cmd = "python3 plugins/autonomous-dev/lib/goa_cli.py watch"
    ping_url = "${HEALTHCHECKS_PING_URL:-<your-ping-url>}"

    print()
    print("Run these /schedule create commands to activate GOA monitoring:")
    print()
    print(f"  /schedule create --name goa-watcher --cron '{_CRON_WATCHER}' --cmd '{goa_cli_cmd}'")
    print(f"  /schedule create --name goa-ping    --cron '{_CRON_PING}'    --cmd 'curl -fsS {ping_url}'")
    print(
        "  # Deadman check: create a healthchecks.io check manually, set grace period to "
        "20 min, and paste the UUID into the manifest's healthcheck_uuid field."
    )
    print()
    print("After /schedule create runs, copy the trigger IDs and run:")
    print("  /goa start --record-trigger-id <watcher-id>,<ping-id>,<deadman-id>")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: stop
# ---------------------------------------------------------------------------


def goa_stop(args: argparse.Namespace) -> int:
    """Print /schedule cancel commands and delete the manifest.

    Args:
        args: Parsed CLI arguments.

    Returns:
        0 on success, 1 when manifest is missing.
    """
    goa_state, _ = _import_goa_modules()

    manifest = goa_state.load_manifest()
    if manifest is None:
        print("GOA: no active manifest found — nothing to stop.")
        return 1

    trigger_ids = manifest.get("trigger_ids", {})
    watcher_id = trigger_ids.get("watcher", "")
    ping_id = trigger_ids.get("ping", "")

    print("Run these /schedule cancel commands to deactivate GOA monitoring:")
    print()
    if watcher_id:
        print(f"  /schedule cancel {watcher_id}  # goa-watcher")
    else:
        print("  # goa-watcher trigger ID not recorded — cancel manually")
    if ping_id:
        print(f"  /schedule cancel {ping_id}  # goa-ping")
    else:
        print("  # goa-ping trigger ID not recorded — cancel manually")
    print()

    goa_state.delete_manifest()
    print("GOA: manifest deleted.")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------


def goa_status(args: argparse.Namespace) -> int:
    """Print GOA status: manifest contents and open GOA issues.

    Args:
        args: Parsed CLI arguments.

    Returns:
        0 on success.
    """
    goa_state, _ = _import_goa_modules()

    manifest = goa_state.load_manifest()
    if manifest is None:
        print("GOA: inactive (no manifest). Run '/goa start' to activate.")
        return 0

    print("GOA: active")
    print(f"  Created:    {manifest.get('created_utc', 'unknown')}")
    print(f"  Thresholds: {manifest.get('thresholds', {})}")
    print(f"  Triggers:   {manifest.get('trigger_ids', {})}")
    hc_uuid = manifest.get("healthcheck_uuid", "")
    print(f"  HC UUID:    {hc_uuid if hc_uuid else '(not set)'}")

    # List open GOA issues
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--label", "goa", "--state", "open",
             "--json", "number,title", "--limit", "50"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            if issues:
                print(f"\nOpen GOA issues ({len(issues)}):")
                for issue in issues:
                    print(f"  #{issue['number']} {issue['title']}")
            else:
                print("\nNo open GOA issues.")
        else:
            print("\n(Could not fetch open issues — gh CLI unavailable or not authenticated)")
    except Exception:
        print("\n(Could not fetch open issues)")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: watch
# ---------------------------------------------------------------------------


def goa_watch(args: argparse.Namespace) -> int:
    """Run one GOA health-check cycle.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code from ``goa_watcher.run_watch()``.
    """
    _, goa_watcher = _import_goa_modules()
    return goa_watcher.run_watch()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the appropriate subcommand.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]`` when ``None``).

    Returns:
        Integer exit code (0 = success).
    """
    parser = argparse.ArgumentParser(
        prog="goa",
        description=(
            "GOA — Governance, Observability, Audit. "
            "Autonomous infrastructure-health observer for autonomous-dev."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # start
    start_parser = subparsers.add_parser("start", help="Activate GOA monitoring")
    start_parser.add_argument(
        "--record-trigger-id",
        metavar="ID1,ID2,ID3",
        help=(
            "Comma-separated cron trigger IDs (watcher,ping,deadman) returned by "
            "/schedule create — updates the manifest so /goa stop can cancel them."
        ),
    )

    # stop
    subparsers.add_parser("stop", help="Deactivate GOA monitoring and delete manifest")

    # status
    subparsers.add_parser("status", help="Show GOA status and open issues")

    # watch (internal — called by cron)
    subparsers.add_parser("watch", help="Run one health-check cycle (called by cron)")

    parsed = parser.parse_args(argv)

    if parsed.subcommand is None:
        parser.print_help()
        return 1

    dispatch = {
        "start": goa_start,
        "stop": goa_stop,
        "status": goa_status,
        "watch": goa_watch,
    }
    handler = dispatch.get(parsed.subcommand)
    if handler is None:
        print(f"Unknown subcommand: {parsed.subcommand}", file=sys.stderr)
        return 1

    return handler(parsed)


if __name__ == "__main__":
    sys.exit(main())
