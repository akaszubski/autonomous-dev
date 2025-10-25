#!/usr/bin/env python3
"""
Deploy command workflow - ensures commands become visible.

This script enforces the complete workflow:
1. Validates command implementation
2. Syncs to runtime location
3. Reminds to restart Claude Code
4. Verifies deployment

Usage:
    python plugins/autonomous-dev/scripts/deploy_command.py <command-name>

    Or deploy all:
    python plugins/autonomous-dev/scripts/deploy_command.py --all
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd: list[str], description: str) -> tuple[bool, str]:
    """Run a command and return success status."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            print(f"✅ {description}")
            return True, result.stdout
        else:
            print(f"❌ {description} failed")
            print(result.stderr)
            return False, result.stderr
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, str(e)


def main():
    if len(sys.argv) < 2:
        print("Usage: python deploy_command.py <command-name>")
        print("   Or: python deploy_command.py --all")
        sys.exit(1)

    command_name = sys.argv[1]
    is_all = command_name == "--all"

    # Get paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent.parent

    print("=" * 70)
    if is_all:
        print("DEPLOYING ALL COMMANDS")
    else:
        print(f"DEPLOYING COMMAND: /{command_name}")
    print("=" * 70)
    print()

    # Step 1: Validate
    print("STEP 1: VALIDATION")
    print("-" * 70)

    validate_script = script_dir / "validate_commands.py"
    success, output = run_command(
        ["python3", str(validate_script)],
        "Validating all commands"
    )

    if not success:
        print()
        print("❌ VALIDATION FAILED")
        print()
        print("Fix the errors above before deploying.")
        print("See: plugins/autonomous-dev/docs/COMMAND_CHECKLIST.md")
        sys.exit(1)

    if not is_all:
        # Check specific command
        if f"✅ {command_name}.md" not in output:
            print(f"❌ Command '{command_name}' not found or invalid")
            print()
            print(f"Available commands:")
            for line in output.split('\n'):
                if line.startswith('✅'):
                    print(f"  {line}")
            sys.exit(1)
        print(f"✅ Command /{command_name} validated")

    print()

    # Step 2: Sync
    print("STEP 2: SYNC TO RUNTIME")
    print("-" * 70)

    sync_script = script_dir / "sync_to_installed.py"
    success, output = run_command(
        ["python3", str(sync_script)],
        "Syncing to installed location"
    )

    if not success:
        print()
        print("❌ SYNC FAILED")
        print()
        print("Check that plugin is installed:")
        print("  /plugin list")
        sys.exit(1)

    print()

    # Step 3: Remind to restart
    print("STEP 3: RESTART REQUIRED")
    print("-" * 70)
    print()
    print("⚠️  YOU MUST RESTART CLAUDE CODE FOR CHANGES TO TAKE EFFECT")
    print()
    print("How to restart:")
    print("  • Mac: Press Cmd+Q, then reopen Claude Code")
    print("  • Linux/Windows: Press Ctrl+Q, then reopen Claude Code")
    print()
    print("After restarting, continue to Step 4...")
    print()

    # Step 4: Verification steps
    print("STEP 4: VERIFICATION (After Restart)")
    print("-" * 70)
    print()

    if is_all:
        print("Verify all commands are visible:")
        print()
        print("  1. Type '/' in Claude Code")
        print("     → Should see all 23+ commands")
        print()
        print("  2. Run: /health-check")
        print("     → Should show: Commands: 23/23 present")
        print()
    else:
        print(f"Verify /{command_name} is visible:")
        print()
        print(f"  1. Type '/{command_name}' in Claude Code")
        print("     → Should autocomplete")
        print()
        print(f"  2. Run: /{command_name}")
        print("     → Should execute (not just show docs)")
        print()
        print("  3. Run: /health-check")
        print(f"     → Should list /{command_name} as PASS")
        print()

    # Step 5: Commit reminder
    print("STEP 5: COMMIT (After Verifying)")
    print("-" * 70)
    print()

    if is_all:
        print("Commit all changes:")
        print()
        print("  git add .claude/commands/")
        print('  git commit -m "feat: update commands"')
    else:
        print(f"Commit the new command:")
        print()
        print(f"  git add .claude/commands/{command_name}.md")
        print(f'  git commit -m "feat: add /{command_name} command"')

    print()
    print("  (Pre-commit hook will validate automatically)")
    print()

    # Summary
    print("=" * 70)
    print("DEPLOYMENT SUMMARY")
    print("=" * 70)
    print()
    print("✅ Validation passed")
    print("✅ Synced to runtime location")
    print("⏸️  Waiting for restart")
    print()
    print("NEXT: Restart Claude Code, then verify the command works!")
    print()


if __name__ == "__main__":
    main()
