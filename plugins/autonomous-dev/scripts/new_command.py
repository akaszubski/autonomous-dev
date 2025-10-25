#!/usr/bin/env python3
"""
Generate a new slash command with proper structure.

This prevents the "command does nothing" bug by forcing you to specify
implementation type during creation.

Usage:
    python scripts/new_command.py my-command
"""

import sys
import os
from pathlib import Path


TEMPLATES = {
    "bash": """---
description: {description}
---

# {title}

{overview}

---

## Usage

```bash
/{command_name} [args]
```

**Time**: < X seconds/minutes
**Scope**: What this affects

---

## What This Does

1. First step
2. Second step
3. Third step

---

## Expected Output

```
Example output here...
```

---

## When to Use

- ✅ Use when scenario 1
- ✅ Use when scenario 2
- ✅ Use when scenario 3

---

## Implementation

Run the command:

```bash
# TODO: Add your bash commands here
# Example: pytest tests/ -v --cov=.
your-command-here
```

---

## Troubleshooting

### Issue 1
- **Symptom**: Description
- **Cause**: Why it happens
- **Solution**: How to fix

---

## Related Commands

- `/other-command` - Related functionality

---

**{closing_remark}**
""",

    "script": """---
description: {description}
---

# {title}

{overview}

---

## Usage

```bash
/{command_name} [args]
```

**Time**: < X seconds/minutes
**Scope**: What this affects

---

## What This Does

1. First step
2. Second step
3. Third step

---

## Expected Output

```
Example output here...
```

---

## When to Use

- ✅ Use when scenario 1
- ✅ Use when scenario 2
- ✅ Use when scenario 3

---

## Implementation

Run the script:

```bash
python "$(dirname "$0")/../scripts/{script_name}.py"
```

**Note**: You need to create `plugins/autonomous-dev/scripts/{script_name}.py`

---

## Troubleshooting

### Script not found
- Check: `plugins/autonomous-dev/scripts/{script_name}.py` exists
- Check: Script is executable (`chmod +x`)

---

## Related Commands

- `/other-command` - Related functionality

---

**{closing_remark}**
""",

    "agent": """---
description: {description}
---

# {title}

{overview}

---

## Usage

```bash
/{command_name} [args]
```

**Time**: X-Y minutes
**Agent**: {agent_name}
**Scope**: What this affects

---

## What This Does

1. First step
2. Second step
3. Third step

---

## Expected Output

```
Example output here...
```

---

## When to Use

- ✅ Use when scenario 1
- ✅ Use when scenario 2
- ✅ Use when scenario 3

---

## Implementation

Invoke the {agent_name} agent with prompt:

```
TODO: Add detailed agent instructions

1. Analyze X
2. Process Y
3. Report Z with specific format
```

---

## Troubleshooting

### Agent not available
- Check: Agent exists in `.claude/agents/{agent_name}.md`
- Run: `/health-check` to verify agent loaded

---

## Related Commands

- `/other-command` - Related functionality

---

**{closing_remark}**
""",
}


def prompt_user(question: str, options: list[str] = None, default: str = None) -> str:
    """Prompt user for input with optional validation."""
    if options:
        print(f"\n{question}")
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        while True:
            choice = input(f"Choice [1-{len(options)}]: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass
            print(f"Invalid choice. Enter 1-{len(options)}")
    else:
        prompt = f"{question}"
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        result = input(prompt).strip()
        return result or default


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/new_command.py <command-name>")
        print("Example: python scripts/new_command.py my-feature")
        sys.exit(1)

    command_name = sys.argv[1]

    # Validate command name
    if not command_name.replace("-", "").isalnum():
        print(f"❌ Invalid command name: {command_name}")
        print("   Use only letters, numbers, and hyphens")
        sys.exit(1)

    # Find commands directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent.parent
    commands_dir = repo_root / ".claude" / "commands"

    if not commands_dir.exists():
        print(f"❌ Commands directory not found: {commands_dir}")
        sys.exit(1)

    output_path = commands_dir / f"{command_name}.md"

    if output_path.exists():
        print(f"❌ Command already exists: {output_path}")
        sys.exit(1)

    print("=" * 70)
    print("NEW SLASH COMMAND GENERATOR")
    print("=" * 70)

    # Gather information
    description = prompt_user("One-line description", default=f"Description of {command_name}")

    title = prompt_user("Command title", default=command_name.replace("-", " ").title())

    overview = prompt_user("Brief overview", default=f"This command does X, Y, and Z.")

    closing_remark = prompt_user(
        "Closing remark",
        default=f"Use this command to accomplish the task efficiently."
    )

    # Choose implementation type
    impl_type = prompt_user(
        "Implementation type",
        options=["bash", "script", "agent"]
    )

    # Type-specific prompts
    variables = {
        "command_name": command_name,
        "description": description,
        "title": title,
        "overview": overview,
        "closing_remark": closing_remark,
    }

    if impl_type == "script":
        script_name = prompt_user(
            "Script name (without .py)",
            default=command_name.replace("-", "_")
        )
        variables["script_name"] = script_name

    elif impl_type == "agent":
        agent_name = prompt_user(
            "Agent name",
            options=[
                "orchestrator",
                "planner",
                "researcher",
                "test-master",
                "implementer",
                "reviewer",
                "security-auditor",
                "doc-master"
            ]
        )
        variables["agent_name"] = agent_name

    # Generate command file
    template = TEMPLATES[impl_type]
    content = template.format(**variables)

    with open(output_path, 'w') as f:
        f.write(content)

    print()
    print("=" * 70)
    print("✅ COMMAND CREATED!")
    print("=" * 70)
    print(f"Location: {output_path}")
    print()
    print("NEXT STEPS:")
    print()
    print("1. Edit the command file:")
    print(f"   vim {output_path}")
    print()
    print("2. Fill in the TODOs (search for 'TODO' in file)")
    print()
    print("3. Validate implementation:")
    print("   python plugins/autonomous-dev/scripts/validate_commands.py")
    print()

    if impl_type == "script":
        script_path = repo_root / "plugins" / "autonomous-dev" / "scripts" / f"{variables['script_name']}.py"
        print(f"4. Create the script: {script_path}")
        print()

    print("5. Test the command:")
    print("   - Restart Claude Code")
    print(f"   - Run /{command_name}")
    print()
    print("6. Commit:")
    print(f"   git add {output_path}")
    print("   git commit -m 'feat: add /{command_name} command'")
    print("   (Pre-commit hook will validate automatically)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
