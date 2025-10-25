#!/usr/bin/env python3
"""
Validate that all slash commands have proper implementation instructions.

This prevents the "command does nothing" bug where commands are just documentation
without any actual bash/agent invocation instructions.

Run this as part of CI/CD or pre-commit to catch missing implementations.
"""

import os
import sys
import re
from pathlib import Path


def validate_command(filepath: Path) -> tuple[bool, str]:
    """
    Validate a command file has implementation instructions.

    Returns:
        (is_valid, error_message)
    """
    with open(filepath) as f:
        content = f.read()

    # Check for bash code blocks with actual commands
    has_bash_block = bool(re.search(r'```bash\n(?!#\s*$).+', content, re.DOTALL))

    # Check for agent invocation instructions (inline or in Implementation section)
    has_agent_invoke = bool(re.search(r'Invoke (the |orchestrator|test-master|doc-master|security-auditor|implementer|planner|reviewer|researcher)', content, re.IGNORECASE))

    # Check for script execution
    has_script_exec = bool(re.search(r'python ["\']?\$\(dirname|python .+\.py', content))

    # Valid if has ANY of: bash block, agent invoke, or script exec
    # (Some commands have inline instructions, others have ## Implementation sections)
    if has_bash_block or has_agent_invoke or has_script_exec:
        return True, ""

    # Provide specific error
    return False, "No implementation found (needs bash commands, agent invocations, or script execution)"


def main():
    """Validate all commands in .claude/commands/"""

    # Find commands directory relative to this script
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent.parent
    commands_dir = repo_root / ".claude" / "commands"

    if not commands_dir.exists():
        print(f"❌ Commands directory not found: {commands_dir}")
        sys.exit(1)

    print("=" * 70)
    print("SLASH COMMAND IMPLEMENTATION VALIDATION")
    print("=" * 70)
    print()

    command_files = sorted(commands_dir.glob("*.md"))

    if not command_files:
        print(f"❌ No command files found in {commands_dir}")
        sys.exit(1)

    valid = []
    invalid = []

    for filepath in command_files:
        is_valid, error = validate_command(filepath)

        if is_valid:
            valid.append(filepath.name)
            print(f"✅ {filepath.name}")
        else:
            invalid.append((filepath.name, error))
            print(f"❌ {filepath.name}: {error}")

    print()
    print("=" * 70)
    print(f"RESULTS: {len(valid)} valid, {len(invalid)} invalid")
    print("=" * 70)

    if invalid:
        print()
        print("FAILED COMMANDS:")
        print()
        for name, error in invalid:
            print(f"  ❌ {name}")
            print(f"     {error}")
            print()

        print("TO FIX:")
        print("  Each command must have an '## Implementation' section with:")
        print("  1. Bash commands (```bash ... ```)")
        print("  2. OR Agent invocation ('Invoke the X agent with...')")
        print("  3. OR Script execution ('python script.py')")
        print()
        print("  Example bash implementation:")
        print("    ## Implementation")
        print("    ```bash")
        print("    pytest tests/ -v")
        print("    ```")
        print()
        print("  Example agent implementation:")
        print("    ## Implementation")
        print("    Invoke the test-master agent with prompt:")
        print("    ```")
        print("    Run comprehensive test analysis...")
        print("    ```")
        print()

        sys.exit(1)

    print()
    print("✅ ALL COMMANDS HAVE PROPER IMPLEMENTATIONS!")
    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
