#!/usr/bin/env python3
"""
GenAI-Powered Documentation Consistency Validator

Validates that documentation accurately describes code reality.
Prevents overpromising, outdated docs, and misleading claims.

This caught the version sync issue: Docs claimed "/sync-docs updates versions"
but code only handled docstrings.

Usage:
    # Validate all documentation
    python validate_docs_genai.py --full

    # Validate specific file
    python validate_docs_genai.py --file README.md

    # Validate command documentation
    python validate_docs_genai.py --command sync-docs

    # Quick check (high-level only)
    python validate_docs_genai.py --quick
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

DOCS_TO_VALIDATE = [
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "README.md",
    PROJECT_ROOT / ".claude" / "PROJECT.md",
]

COMMANDS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands"
AGENTS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents"
HOOKS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"

# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class InconsistencyFound:
    """A documentation inconsistency."""
    file_path: str
    claim: str
    reality: str
    severity: str  # "critical", "high", "medium", "low"
    reasoning: str
    line_number: Optional[int] = None

@dataclass
class ValidationResult:
    """Result of documentation validation."""
    file_path: str
    is_consistent: bool
    confidence: str  # "high", "medium", "low"
    summary: str
    inconsistencies: List[InconsistencyFound]
    verified_claims: List[str]

# ============================================================================
# Code Analysis
# ============================================================================

def get_command_implementation(command_name: str) -> Optional[str]:
    """Get actual implementation of a command."""
    # Commands are markdown files with descriptions
    # Implementation is in hooks or agents

    command_file = COMMANDS_DIR / f"{command_name}.md"
    if not command_file.exists():
        return None

    return command_file.read_text()

def list_available_commands() -> List[str]:
    """List all available commands."""
    if not COMMANDS_DIR.exists():
        return []

    return [f.stem for f in COMMANDS_DIR.glob("*.md")]

def list_available_agents() -> List[str]:
    """List all available agents."""
    if not AGENTS_DIR.exists():
        return []

    return [f.stem for f in AGENTS_DIR.glob("*.md")]

def list_available_hooks() -> List[str]:
    """List all available hooks."""
    if not HOOKS_DIR.exists():
        return []

    return [f.stem for f in HOOKS_DIR.glob("*.py")]

def get_hook_capabilities(hook_name: str) -> Optional[str]:
    """Get what a hook actually does by reading its code."""
    hook_file = HOOKS_DIR / f"{hook_name}.py"
    if not hook_file.exists():
        return None

    content = hook_file.read_text()

    # Extract docstring
    docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
    if docstring_match:
        return docstring_match.group(1).strip()

    # Return first 50 lines as fallback
    lines = content.splitlines()[:50]
    return "\n".join(lines)

# ============================================================================
# GenAI Integration
# ============================================================================

def get_llm_client():
    """Get LLM client."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if anthropic_key:
        try:
            import anthropic
        except ImportError:
            print("❌ anthropic package not installed!")
            sys.exit(1)

        client = anthropic.Anthropic(api_key=anthropic_key)
        model = "claude-sonnet-4-5-20250929"  # Latest Sonnet 4.5 (best quality)
        return client, model, "anthropic"
    elif openrouter_key:
        try:
            import openai
        except ImportError:
            print("❌ openai package not installed!")
            sys.exit(1)

        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
        )
        model = "anthropic/claude-3.5-sonnet"
        return client, model, "openrouter"
    else:
        print("❌ No API key found!")
        print("Set: export ANTHROPIC_API_KEY=sk-ant-... or OPENROUTER_API_KEY=...")
        sys.exit(1)


def validate_documentation_with_genai(
    doc_file: Path,
    code_context: Dict[str, any]
) -> ValidationResult:
    """
    Validate documentation against code reality using GenAI.

    This catches:
    - Overpromising (claims features that don't exist)
    - Outdated docs (describes old behavior)
    - Misleading claims (technically true but misleading)
    - Count mismatches (claims "6 skills" but 13 exist)
    """
    client, model, provider = get_llm_client()

    doc_content = doc_file.read_text()

    # Build prompt
    prompt = f"""You are validating whether documentation accurately describes code reality.

**DOCUMENTATION CONTENT** ({doc_file.name}):
```
{doc_content[:8000]}
```

**CODE REALITY**:

Available commands: {len(code_context['commands'])} total
{', '.join(code_context['commands'][:20])}

Available agents: {len(code_context['agents'])} total
{', '.join(code_context['agents'])}

Available hooks: {len(code_context['hooks'])} total
{', '.join(code_context['hooks'])}

**Example Implementation** (/sync-docs command):
{code_context.get('sync_docs_impl', 'Not found')[:2000]}

**Example Hook** (auto_update_docs.py):
{code_context.get('auto_update_docs', 'Not found')[:2000]}

---

**VALIDATION TASK**:

Check if the documentation makes claims that don't match code reality.

**Common Issues to Detect**:

1. **Overpromising**: Claims features that don't exist
   - Example: "Automatically syncs versions" but code only syncs docstrings

2. **Count Mismatches**: Claims wrong numbers
   - Example: "6 core skills" but actually 13 exist

3. **Misleading Descriptions**: Technically true but misleading
   - Example: "Complete sync" but only syncs API docs, not versions

4. **Outdated Behavior**: Describes old implementation
   - Example: "Uses v2.0.0" but code updated to v2.1.0

5. **Missing Caveats**: Doesn't mention limitations
   - Example: "Team collaboration" but only solo developer tested

**IMPORTANT**: Be thorough but fair. Some claims are aspirational (roadmap), that's OK if clearly marked.

Provide analysis in JSON:

```json
{{
  "is_consistent": true/false,
  "confidence": "high/medium/low",
  "summary": "Brief summary of validation",
  "inconsistencies": [
    {{
      "claim": "What the doc claims",
      "reality": "What the code actually does",
      "severity": "critical/high/medium/low",
      "reasoning": "Why this is inconsistent",
      "line_number": null
    }}
  ],
  "verified_claims": [
    "Claim 1 that IS accurate",
    "Claim 2 that IS accurate"
  ]
}}
```

Focus on critical and high severity issues. Don't flag minor wording differences.
"""

    # Call LLM
    print(f"🤖 Validating {doc_file.name} with {provider} GenAI...")

    if provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text
    else:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content

    # Parse JSON
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text

    try:
        result_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse GenAI response: {e}")
        sys.exit(1)

    # Build result
    inconsistencies = [
        InconsistencyFound(
            file_path=str(doc_file.relative_to(PROJECT_ROOT)),
            claim=inc.get("claim", ""),
            reality=inc.get("reality", ""),
            severity=inc.get("severity", "low"),
            reasoning=inc.get("reasoning", ""),
            line_number=inc.get("line_number")
        )
        for inc in result_data.get("inconsistencies", [])
    ]

    return ValidationResult(
        file_path=str(doc_file.relative_to(PROJECT_ROOT)),
        is_consistent=result_data.get("is_consistent", True),
        confidence=result_data.get("confidence", "low"),
        summary=result_data.get("summary", ""),
        inconsistencies=inconsistencies,
        verified_claims=result_data.get("verified_claims", [])
    )


# ============================================================================
# Main Validation
# ============================================================================

def gather_code_context() -> Dict:
    """Gather code context for validation."""
    return {
        "commands": list_available_commands(),
        "agents": list_available_agents(),
        "hooks": list_available_hooks(),
        "sync_docs_impl": get_command_implementation("sync-docs"),
        "auto_update_docs": get_hook_capabilities("auto_update_docs"),
    }


def print_result(result: ValidationResult):
    """Print validation result."""
    print()
    print("=" * 70)
    if result.is_consistent:
        print(f"✅ CONSISTENT - {result.file_path}")
    else:
        print(f"❌ INCONSISTENCIES FOUND - {result.file_path}")
    print("=" * 70)
    print()
    print(f"**Confidence**: {result.confidence}")
    print()
    print(f"**Summary**:")
    print(f"  {result.summary}")
    print()

    if result.inconsistencies:
        print(f"**Inconsistencies Found** ({len(result.inconsistencies)} total):")
        print()

        # Group by severity
        critical = [i for i in result.inconsistencies if i.severity == "critical"]
        high = [i for i in result.inconsistencies if i.severity == "high"]
        medium = [i for i in result.inconsistencies if i.severity == "medium"]
        low = [i for i in result.inconsistencies if i.severity == "low"]

        for severity, issues in [("CRITICAL", critical), ("HIGH", high), ("MEDIUM", medium), ("LOW", low)]:
            if issues:
                print(f"**{severity} Severity** ({len(issues)}):")
                for issue in issues:
                    print(f"  ❌ Claim: {issue.claim}")
                    print(f"     Reality: {issue.reality}")
                    print(f"     Reason: {issue.reasoning}")
                    print()

    if result.verified_claims:
        print(f"**Verified Claims** ({len(result.verified_claims)} checked):")
        for claim in result.verified_claims[:5]:  # Show first 5
            print(f"  ✓ {claim}")
        if len(result.verified_claims) > 5:
            print(f"  ... and {len(result.verified_claims) - 5} more")
        print()

    if not result.is_consistent:
        print("❌ **RECOMMENDATION**: Update documentation to match code reality")
    else:
        print("✅ **RECOMMENDATION**: Documentation is accurate")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="GenAI-powered documentation consistency validator"
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Validate all documentation files"
    )

    parser.add_argument(
        "--file",
        help="Validate specific file"
    )

    parser.add_argument(
        "--command",
        help="Validate specific command documentation"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick validation (high-level only)"
    )

    args = parser.parse_args()

    # Gather code context
    print("📊 Gathering code context...")
    code_context = gather_code_context()
    print(f"✅ Found {len(code_context['commands'])} commands, {len(code_context['agents'])} agents, {len(code_context['hooks'])} hooks")
    print()

    # Determine what to validate
    files_to_validate = []

    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = PROJECT_ROOT / file_path
        files_to_validate.append(file_path)
    elif args.command:
        command_file = COMMANDS_DIR / f"{args.command}.md"
        if command_file.exists():
            files_to_validate.append(command_file)
        else:
            print(f"❌ Command not found: {args.command}")
            return 1
    elif args.full:
        files_to_validate = DOCS_TO_VALIDATE
    elif args.quick:
        # Just check main README
        files_to_validate = [PROJECT_ROOT / "plugins" / "autonomous-dev" / "README.md"]
    else:
        parser.print_help()
        return 1

    # Validate each file
    all_consistent = True
    critical_issues = 0

    for doc_file in files_to_validate:
        if not doc_file.exists():
            print(f"⚠️  File not found: {doc_file}")
            continue

        result = validate_documentation_with_genai(doc_file, code_context)
        print_result(result)

        if not result.is_consistent:
            all_consistent = False
            critical_issues += len([i for i in result.inconsistencies if i.severity == "critical"])

    # Summary
    if len(files_to_validate) > 1:
        print("=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Files validated: {len(files_to_validate)}")
        print(f"Critical issues: {critical_issues}")
        print()
        if all_consistent:
            print("✅ All documentation is consistent with code")
        else:
            print("❌ Documentation inconsistencies found - update docs")

    return 0 if all_consistent else 1


if __name__ == "__main__":
    sys.exit(main())
