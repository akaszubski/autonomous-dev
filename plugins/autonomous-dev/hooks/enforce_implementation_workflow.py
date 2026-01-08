#!/usr/bin/env python3
"""
Enforce Implementation Workflow Hook - Opt-In Workflow Discipline Enforcement

This PreToolUse hook detects when Claude is attempting to make significant code
changes (new functions, methods, classes, or >10 lines) outside of the /implement
pipeline, when strict enforcement is enabled.

Philosophy (Issue #141):
- Default: OFF (persuasion via CLAUDE.md, not enforcement)
- Opt-in: ENFORCE_WORKFLOW_STRICT=true for teams that want it
- Smart detection: Reduces false positives (allows tests, docs, configs, hooks)

How it works:
1. Intercepts Edit and Write tool calls on code files
2. Checks if enforcement is enabled (opt-in)
3. Analyzes changes for significant additions (new functions, classes, >10 lines)
4. If significant: DENIES with message guiding Claude to use /implement
5. If minor (typos, small fixes): ALLOWS through

Input (stdin):
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/path/to/file.py",
    "old_string": "...",
    "new_string": "..."
  }
}

Output (stdout):
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",  # or "allow"
    "permissionDecisionReason": "reason"
  }
}

Exit code: 0 (always - let Claude Code process the decision)

Environment Variables:
- ENFORCE_WORKFLOW_STRICT: Enable strict enforcement (default: false, opt-in)
- ENFORCE_IMPLEMENTATION_WORKFLOW: Legacy variable (deprecated, use ENFORCE_WORKFLOW_STRICT)
- CLAUDE_AGENT_NAME: If set to allowed agent, permits significant changes
"""

import json
import sys
import os
import re
from pathlib import Path


# Patterns that indicate significant code additions
SIGNIFICANT_PATTERNS = [
    # Python
    (r'\bdef\s+\w+\s*\(', 'Python function'),
    (r'\basync\s+def\s+\w+\s*\(', 'Python async function'),
    (r'\bclass\s+\w+', 'Python/JS class'),

    # JavaScript/TypeScript
    (r'\bfunction\s+\w+\s*\(', 'JavaScript function'),
    (r'\basync\s+function\s+\w+\s*\(', 'JavaScript async function'),
    (r'\bconst\s+\w+\s*=\s*(?:async\s*)?\(.*?\)\s*=>', 'Arrow function'),
    (r'\bexport\s+(?:default\s+)?(?:function|class|const)', 'JS export'),

    # Go
    (r'\bfunc\s+(?:\(\w+\s+\*?\w+\)\s+)?\w+\s*\(', 'Go function'),

    # Rust
    (r'\bfn\s+\w+\s*[<(]', 'Rust function'),
    (r'\bimpl\s+', 'Rust impl block'),

    # Java/Kotlin
    (r'\b(?:public|private|protected)\s+(?:static\s+)?(?:\w+\s+)+\w+\s*\(', 'Java method'),
]

# Agents allowed to make significant changes (part of /auto-implement workflow)
ALLOWED_AGENTS = [
    'implementer',
    'test-master',
    'brownfield-analyzer',
    'setup-wizard',
    'project-bootstrapper',
]

# Code file extensions
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
    '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
    '.kt', '.scala', '.sh', '.bash', '.zsh', '.vue', '.svelte',
}

# Minimum lines to be considered "significant"
SIGNIFICANT_LINE_THRESHOLD = 10


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
            pass


def count_new_lines(old_string: str, new_string: str) -> int:
    """Count how many lines were added."""
    old_lines = len(old_string.strip().split('\n')) if old_string.strip() else 0
    new_lines = len(new_string.strip().split('\n')) if new_string.strip() else 0
    return max(0, new_lines - old_lines)


def has_significant_additions(old_string: str, new_string: str) -> tuple:
    """
    Check if the edit adds significant code structures.

    Returns:
        (is_significant, reason, details)
    """
    old_string = old_string or ""
    new_string = new_string or ""

    # Check for new function/class definitions
    for pattern, desc in SIGNIFICANT_PATTERNS:
        # Count matches in old vs new
        old_matches = len(re.findall(pattern, old_string, re.MULTILINE))
        new_matches = len(re.findall(pattern, new_string, re.MULTILINE))

        if new_matches > old_matches:
            # New definitions added - find what was added
            match = re.search(pattern, new_string)
            if match:
                snippet = match.group(0)[:60]
                return True, f"New {desc} detected", snippet

    # Check for significant line additions
    added_lines = count_new_lines(old_string, new_string)
    if added_lines >= SIGNIFICANT_LINE_THRESHOLD:
        return True, f"Significant addition ({added_lines} new lines)", f"+{added_lines} lines"

    return False, "", ""


def is_exempt_path(file_path: str) -> bool:
    """
    Check if the file path is exempt from workflow enforcement.

    Exempt paths (allowed without /implement):
    - Test files (tests/, test_*.py, *_test.py, *.test.js)
    - Documentation (.md files)
    - Configuration (.json, .yaml, .toml, .env)
    - Hooks (.claude/hooks/)
    - Library infrastructure (lib/, plugins/autonomous-dev/lib/)
    - Agent and command files (.claude/agents/, .claude/commands/)
    - Scripts (scripts/)

    Args:
        file_path: Path to the file being modified

    Returns:
        True if file is exempt, False otherwise
    """
    if not file_path:
        return False

    path = Path(file_path)
    path_str = str(path).lower()

    # Test files (TDD workflow - test-master can write tests)
    if (path_str.startswith('tests/') or
        path_str.startswith('test/') or
        '/test_' in path_str or
        path_str.startswith('test_') or
        path_str.endswith('_test.py') or
        path_str.endswith('.test.js') or
        path_str.endswith('.test.ts')):
        return True

    # Documentation files
    if path.suffix.lower() in {'.md', '.txt', '.rst'}:
        return True

    # Configuration files
    if path.suffix.lower() in {'.json', '.yaml', '.yml', '.toml', '.env', '.ini', '.cfg'}:
        return True

    # Hooks directory
    if '.claude/hooks/' in path_str or path_str.startswith('hooks/'):
        return True

    # Library infrastructure
    if (path_str.startswith('lib/') or
        '/lib/' in path_str or
        'plugins/autonomous-dev/lib/' in path_str):
        return True

    # Agents and commands
    if ('.claude/agents/' in path_str or
        '.claude/commands/' in path_str or
        '.claude/skills/' in path_str):
        return True

    # Scripts directory
    if path_str.startswith('scripts/'):
        return True

    return False


def is_code_file(file_path: str) -> bool:
    """Check if the file is a code file (not config, docs, etc.)."""
    if not file_path:
        return False
    return Path(file_path).suffix.lower() in CODE_EXTENSIONS


def output_decision(decision: str, reason: str):
    """Output the hook decision in required format."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }))


def main():
    """Main entry point."""
    try:
        # Load environment
        load_env()

        # Check if strict enforcement is enabled (opt-in, default: false)
        # Support both new and legacy variable names
        strict_enforce = os.getenv("ENFORCE_WORKFLOW_STRICT", "false").lower() == "true"
        legacy_enforce = os.getenv("ENFORCE_IMPLEMENTATION_WORKFLOW", "false").lower() == "true"

        enforce_enabled = strict_enforce or legacy_enforce

        if not enforce_enabled:
            output_decision("allow", "Workflow enforcement disabled (opt-in with ENFORCE_WORKFLOW_STRICT=true)")
            sys.exit(0)

        # Check if running inside allowed agent (part of /implement workflow)
        agent_name = os.getenv("CLAUDE_AGENT_NAME", "").strip().lower()
        if agent_name in ALLOWED_AGENTS:
            output_decision("allow", f"Agent '{agent_name}' authorized for implementation")
            sys.exit(0)

        # Read input from stdin
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Only check Edit and Write tools
        if tool_name not in ("Edit", "Write"):
            output_decision("allow", f"Tool '{tool_name}' not subject to workflow enforcement")
            sys.exit(0)

        # Get file path
        file_path = tool_input.get("file_path", "")

        # Check if file is exempt (tests, docs, configs, hooks, lib)
        if is_exempt_path(file_path):
            output_decision("allow", f"File exempt from workflow enforcement: {Path(file_path).name}")
            sys.exit(0)

        # Only check code files
        if not is_code_file(file_path):
            output_decision("allow", "Non-code file, no enforcement needed")
            sys.exit(0)

        # Analyze the change
        if tool_name == "Edit":
            old_string = tool_input.get("old_string", "")
            new_string = tool_input.get("new_string", "")
            is_significant, reason, details = has_significant_additions(old_string, new_string)
        else:  # Write
            content = tool_input.get("content", "")
            # For new files, treat as adding everything
            is_significant, reason, details = has_significant_additions("", content)

        if is_significant:
            # Block with guidance to use proper workflow
            file_name = Path(file_path).name

            # Updated message with /implement command and how to disable
            output_decision("deny", f"""
WORKFLOW ENFORCEMENT ACTIVE

{reason}: {details}
File: {file_name}

You are attempting to implement code directly. Strict workflow enforcement is enabled.

RECOMMENDED: Use /implement for better quality

The /implement pipeline provides:
- Automatic research (finds existing patterns)
- TDD enforcement (tests written first)
- Security audit (catches vulnerabilities)
- Documentation sync (keeps docs updated)
- 85% fewer bugs vs direct implementation

HOW TO USE:

1. For new features or fixes:
   /implement "description of feature/fix"

2. Quick mode (skip pipeline, just implement):
   /implement --quick "description"

3. If there's already a GitHub issue:
   /implement #123

TO DISABLE THIS ENFORCEMENT:

Add to your .env file:
ENFORCE_WORKFLOW_STRICT=false

Or remove it entirely (enforcement is opt-in by default).

See docs/WORKFLOW-DISCIPLINE.md for data on why /implement is recommended.
""")
        else:
            # Minor change - allow
            output_decision("allow", "Minor edit, no significant code additions detected")

    except json.JSONDecodeError as e:
        # Can't parse input - allow (don't block on parse errors)
        output_decision("allow", f"Input parse error: {e}")
    except Exception as e:
        # Error - allow (don't block on hook errors)
        output_decision("allow", f"Hook error: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
