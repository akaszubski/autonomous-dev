#!/usr/bin/env python3
"""
Validate that all hooks referenced in settings files actually exist.

This script prevents the "locked out of claude" scenario where settings
reference hooks that have been deleted or moved during refactoring.

Usage:
    python scripts/validate_hook_paths.py [--fix]

Exit codes:
    0 - All hooks validated
    1 - Missing hooks found (use --fix to repair)
"""

import json
import os
import re
import sys
from pathlib import Path

# Directories to check
SETTINGS_LOCATIONS = [
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".claude" / "settings.local.json",
    Path(".claude") / "settings.json",
    Path(".claude") / "settings.local.json",
]

# Source of truth for hooks
REPO_HOOKS_DIR = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"
GLOBAL_HOOKS_DIR = Path.home() / ".claude" / "hooks"


def extract_hook_paths(settings_path: Path) -> list[tuple[str, str]]:
    """Extract all hook file paths from a settings file."""
    if not settings_path.exists():
        return []

    try:
        with open(settings_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    hooks = []
    hook_configs = data.get("hooks", {})

    for lifecycle, hook_list in hook_configs.items():
        for hook_entry in hook_list:
            for hook in hook_entry.get("hooks", []):
                command = hook.get("command", "")
                # Extract Python file paths from command
                matches = re.findall(r'[\w./~-]+\.py', command)
                for match in matches:
                    hooks.append((lifecycle, match))

    return hooks


def resolve_path(hook_path: str) -> Path:
    """Resolve a hook path to an absolute path."""
    path = hook_path.replace("~", str(Path.home()))
    return Path(path).expanduser()


def check_hook_exists(hook_path: str) -> tuple[bool, Path]:
    """Check if a hook file exists."""
    resolved = resolve_path(hook_path)
    return resolved.exists(), resolved


def find_unified_replacement(old_hook: str) -> str | None:
    """Find the unified hook that replaces an old individual hook."""
    replacements = {
        "detect_feature_request.py": "unified_prompt_validator.py",
        "pre_tool_use.py": "unified_pre_tool.py",
        "post_tool_use_error_capture.py": "unified_post_tool.py",
        "session_tracker.py": "unified_session_tracker.py",
        "log_agent_completion.py": "unified_session_tracker.py",
        "auto_git_workflow.py": "unified_git_automation.py",
        "auto_update_project_progress.py": "unified_session_tracker.py",
        "batch_permission_approver.py": "unified_pre_tool.py",
        "enforce_implementation_workflow.py": "unified_prompt_validator.py",
    }

    hook_name = Path(old_hook).name
    return replacements.get(hook_name)


def main():
    fix_mode = "--fix" in sys.argv
    issues_found = []

    print("=" * 60)
    print("Hook Path Validation Report")
    print("=" * 60)

    for settings_path in SETTINGS_LOCATIONS:
        if not settings_path.exists():
            continue

        print(f"\n📄 {settings_path}")
        hooks = extract_hook_paths(settings_path)

        if not hooks:
            print("   No hooks configured")
            continue

        for lifecycle, hook_path in hooks:
            exists, resolved = check_hook_exists(hook_path)

            if exists:
                print(f"   ✅ [{lifecycle}] {hook_path}")
            else:
                replacement = find_unified_replacement(hook_path)
                if replacement:
                    print(f"   ❌ [{lifecycle}] {hook_path}")
                    print(f"      → Suggested replacement: ~/.claude/hooks/{replacement}")
                    issues_found.append((settings_path, lifecycle, hook_path, replacement))
                else:
                    print(f"   ❌ [{lifecycle}] {hook_path} (no replacement found)")
                    issues_found.append((settings_path, lifecycle, hook_path, None))

    # Check if unified hooks are synced to global dir
    print(f"\n📁 Unified Hooks Sync Status (~/.claude/hooks/)")
    unified_hooks = list(REPO_HOOKS_DIR.glob("unified_*.py"))

    for hook in sorted(unified_hooks):
        target = GLOBAL_HOOKS_DIR / hook.name
        if target.exists():
            print(f"   ✅ {hook.name}")
        else:
            print(f"   ❌ {hook.name} (not synced)")
            if fix_mode:
                import shutil
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(hook, target)
                print(f"      → Fixed: copied to {target}")

    print("\n" + "=" * 60)

    if issues_found:
        print(f"\n⚠️  {len(issues_found)} hook reference(s) need attention")
        if not fix_mode:
            print("\nTo fix, update your settings files to use the unified hooks:")
            print("  python3 ~/.claude/hooks/unified_prompt_validator.py")
            print("  python3 ~/.claude/hooks/unified_pre_tool.py")
            print("  python3 ~/.claude/hooks/unified_post_tool.py")
            print("\nOr run with --fix to sync unified hooks automatically:")
            print(f"  python {sys.argv[0]} --fix")
        return 1
    else:
        print("\n✅ All hook references validated successfully")
        return 0


if __name__ == "__main__":
    sys.exit(main())
