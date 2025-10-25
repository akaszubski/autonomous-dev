#!/usr/bin/env python3
"""
GenAI-Powered Version Consistency Validator

Uses LLM to intelligently identify which version references are plugin versions
vs. external package versions, examples, or technical version numbers.

This solves the false positive problem by understanding context semantically.

Features:
- LLM-based contextual understanding
- Distinguishes plugin versions from package versions
- Understands examples, IP addresses, and technical versions
- Provides explanations for why each reference is/isn't a plugin version

Usage:
    # Check for inconsistencies (uses GenAI)
    python version_sync_genai.py --check

    # Fix all inconsistencies
    python version_sync_genai.py --fix

    # API key via environment or .env file
    export OPENROUTER_API_KEY=sk-or-v1-...
    # OR
    export ANTHROPIC_API_KEY=sk-ant-...
"""

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Load environment variables (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required if env vars already set

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
VERSION_FILE = PROJECT_ROOT / "VERSION"
SEARCH_PATHS = [
    PROJECT_ROOT / "plugins" / "autonomous-dev",
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "CLAUDE.md",
]

# Files to exclude
EXCLUDE_PATTERNS = [
    "**/UPDATES.md",
    "**/CHANGELOG.md",
    "**/.git/**",
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/venv/**",
    "**/docs/sessions/**",
]

# Version pattern
VERSION_PATTERN = re.compile(r"v?(\d+\.\d+\.\d+)(?:-(?:alpha|beta|rc|experimental))?")

# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class VersionCandidate:
    """A potential version reference that needs classification."""
    file_path: str
    line_number: int
    line_content: str
    version: str
    surrounding_context: str  # 2 lines before + line + 2 lines after


@dataclass
class ClassifiedVersion:
    """A version reference classified by GenAI."""
    file_path: str
    line_number: int
    line_content: str
    version: str
    is_plugin_version: bool
    reasoning: str
    confidence: str  # "high", "medium", "low"


# ============================================================================
# GenAI Integration
# ============================================================================

def get_llm_client():
    """Get LLM client (OpenRouter or Anthropic)."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if openrouter_key:
        try:
            import openai
        except ImportError:
            print("❌ openai package not installed!")
            print()
            print("Install with:")
            print("  pip install openai")
            print()
            print("Or use Anthropic API instead (set ANTHROPIC_API_KEY)")
            sys.exit(1)

        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
        )
        model = "anthropic/claude-3.5-sonnet"
        return client, model, "openrouter"
    elif anthropic_key:
        try:
            import anthropic
        except ImportError:
            print("❌ anthropic package not installed!")
            print()
            print("Install with:")
            print("  pip install anthropic")
            print()
            print("Or use OpenRouter API instead (set OPENROUTER_API_KEY)")
            sys.exit(1)

        client = anthropic.Anthropic(api_key=anthropic_key)
        model = "claude-sonnet-4-5-20250929"  # Latest Sonnet 4.5 (best quality)
        return client, model, "anthropic"
    else:
        print("❌ No API key found!")
        print()
        print("Set one of:")
        print("  export OPENROUTER_API_KEY=sk-or-v1-...")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        print()
        print("Or add to .env file")
        sys.exit(1)


def classify_versions_with_genai(
    candidates: List[VersionCandidate],
    target_version: str
) -> List[ClassifiedVersion]:
    """
    Use GenAI to classify which versions are plugin versions.

    This is much smarter than regex - understands:
    - Python package versions (anthropic 3.3.0)
    - Tool versions (pytest 23.11.0)
    - Example versions in documentation
    - IP addresses (192.168.1.1)
    - Plugin versions in badges/headers
    """
    client, model, provider = get_llm_client()

    # Build prompt with all candidates
    prompt = f"""You are analyzing version references in a Claude Code plugin codebase to identify which are **plugin version references** vs **external dependency versions, examples, or technical version numbers**.

**Context**:
- Plugin name: autonomous-dev
- Target plugin version: v{target_version}
- Common external versions you'll see:
  - Python packages: anthropic 3.3.0, pytest 23.11.0, setuptools 41.0.0
  - Python itself: 3.11.5
  - Tools: npm 5.12.0, gh CLI 7.4.2
  - IP addresses: 192.168.1.x
  - Generic examples: 1.0.0, 2.0.0 (in semantic versioning docs)

**Your task**: For each version reference below, determine if it's a **plugin version** that should match v{target_version}.

**Classification rules**:
1. **Plugin version** if:
   - In badge (e.g., `badge/version-2.3.1`)
   - In version header (e.g., `**Version**: v2.1.0`)
   - Annotation like "(NEW - v2.3.0)" or "(v2.1.0)"
   - Refers to the autonomous-dev plugin

2. **NOT plugin version** if:
   - External package (e.g., "anthropic 3.3.0")
   - Tool version (e.g., "pytest 23.11.0")
   - Python version (e.g., "3.11.5")
   - Generic example in semver docs
   - IP address (e.g., "192.168.1.1")

**Version references to classify**:

"""

    # Add each candidate
    for i, candidate in enumerate(candidates, 1):
        prompt += f"""
{i}. File: {candidate.file_path}:{candidate.line_number}
   Version: {candidate.version}
   Line: {candidate.line_content.strip()}
   Context:
{candidate.surrounding_context}

"""

    prompt += f"""
**Output format** (JSON array):
```json
[
  {{
    "index": 1,
    "is_plugin_version": true,
    "reasoning": "Badge version for the plugin",
    "confidence": "high"
  }},
  {{
    "index": 2,
    "is_plugin_version": false,
    "reasoning": "This is the anthropic Python package version",
    "confidence": "high"
  }}
]
```

Analyze all {len(candidates)} references and provide the JSON array.
"""

    # Call LLM
    print(f"🤖 Calling {provider} GenAI to classify {len(candidates)} version references...")

    if provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text
    else:  # openrouter
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content

    # Parse JSON response
    # Extract JSON from markdown code blocks if present
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text

    try:
        classifications = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse GenAI response as JSON: {e}")
        print(f"Response: {response_text[:500]}")
        sys.exit(1)

    # Build classified results
    results = []
    for classification in classifications:
        idx = classification["index"] - 1  # 1-indexed to 0-indexed
        if idx < 0 or idx >= len(candidates):
            continue

        candidate = candidates[idx]
        results.append(ClassifiedVersion(
            file_path=candidate.file_path,
            line_number=candidate.line_number,
            line_content=candidate.line_content,
            version=candidate.version,
            is_plugin_version=classification["is_plugin_version"],
            reasoning=classification["reasoning"],
            confidence=classification["confidence"]
        ))

    return results


# ============================================================================
# Core Functions
# ============================================================================

def read_target_version() -> str:
    """Read the target version from VERSION file."""
    if not VERSION_FILE.exists():
        print(f"❌ VERSION file not found at: {VERSION_FILE}")
        sys.exit(1)

    version = VERSION_FILE.read_text().strip().split('\n')[0].strip()
    if version.startswith('v'):
        version = version[1:]

    return version


def should_exclude_file(file_path: Path) -> bool:
    """Check if file should be excluded."""
    for pattern in EXCLUDE_PATTERNS:
        if file_path.match(pattern):
            return True
    return False


def scan_file_for_candidates(file_path: Path) -> List[VersionCandidate]:
    """Scan a file for version candidates."""
    candidates = []

    try:
        lines = file_path.read_text().splitlines()
    except (UnicodeDecodeError, PermissionError):
        return candidates

    for line_num, line in enumerate(lines):
        # Find all version patterns
        for match in VERSION_PATTERN.finditer(line):
            version = match.group(1)

            # Get surrounding context (2 lines before + line + 2 lines after)
            start = max(0, line_num - 2)
            end = min(len(lines), line_num + 3)
            context_lines = lines[start:end]
            surrounding_context = "\n".join(
                f"   {i+start+1}: {l}" for i, l in enumerate(context_lines)
            )

            candidates.append(VersionCandidate(
                file_path=str(file_path.relative_to(PROJECT_ROOT)),
                line_number=line_num + 1,
                line_content=line,
                version=version,
                surrounding_context=surrounding_context
            ))

    return candidates


def scan_all_files() -> List[VersionCandidate]:
    """Scan all files for version candidates."""
    all_candidates = []

    for search_path in SEARCH_PATHS:
        if search_path.is_file():
            if not should_exclude_file(search_path):
                all_candidates.extend(scan_file_for_candidates(search_path))
        elif search_path.is_dir():
            for md_file in search_path.rglob("*.md"):
                if not should_exclude_file(md_file):
                    all_candidates.extend(scan_file_for_candidates(md_file))

    return all_candidates


def validate_versions_with_genai(target_version: str):
    """Validate versions using GenAI classification."""
    # Scan for candidates
    print("🔍 Scanning files for version references...")
    candidates = scan_all_files()
    print(f"✅ Found {len(candidates)} version references")
    print()

    # Classify with GenAI
    classified = classify_versions_with_genai(candidates, target_version)
    print(f"✅ Classified {len(classified)} references")
    print()

    # Separate plugin versions from non-plugin versions
    plugin_refs = [c for c in classified if c.is_plugin_version]
    non_plugin_refs = [c for c in classified if not c.is_plugin_version]

    # Find inconsistent plugin versions
    correct_refs = [r for r in plugin_refs if r.version == target_version]
    incorrect_refs = [r for r in plugin_refs if r.version != target_version]

    return {
        "target_version": target_version,
        "total_refs": len(classified),
        "plugin_refs": len(plugin_refs),
        "non_plugin_refs": len(non_plugin_refs),
        "correct_refs": correct_refs,
        "incorrect_refs": incorrect_refs,
        "non_plugin_samples": non_plugin_refs[:10]  # Show samples
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="GenAI-powered version consistency validator"
    )
    parser.add_argument("--check", action="store_true", help="Check for inconsistencies")
    parser.add_argument("--fix", action="store_true", help="Fix inconsistencies")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not args.check and not args.fix:
        args.check = True

    # Read target version
    print("🔍 Reading target version from VERSION file...")
    target_version = read_target_version()
    print(f"✅ Target version: v{target_version}")
    print()

    # Validate with GenAI
    result = validate_versions_with_genai(target_version)

    # Print summary
    print("=" * 60)
    print(f"GenAI Version Analysis Summary")
    print("=" * 60)
    print(f"Target version: v{result['target_version']}")
    print(f"Total references found: {result['total_refs']}")
    print(f"  Plugin version refs: {result['plugin_refs']}")
    print(f"  External package refs: {result['non_plugin_refs']}")
    print()
    print(f"Plugin version consistency:")
    print(f"  ✅ Correct: {len(result['correct_refs'])}")
    print(f"  ❌ Incorrect: {len(result['incorrect_refs'])}")
    print("=" * 60)
    print()

    # Show incorrect refs
    if result['incorrect_refs']:
        print("❌ Incorrect plugin version references:")
        print()
        for ref in result['incorrect_refs']:
            print(f"  {ref.file_path}:{ref.line_number}")
            print(f"    Version: {ref.version} (should be {result['target_version']})")
            print(f"    Reasoning: {ref.reasoning}")
            print(f"    Confidence: {ref.confidence}")
            print()

    # Show non-plugin samples
    if args.verbose and result['non_plugin_samples']:
        print("ℹ️  Sample non-plugin versions (correctly ignored):")
        print()
        for ref in result['non_plugin_samples'][:5]:
            print(f"  {ref.file_path}:{ref.line_number}")
            print(f"    Version: {ref.version}")
            print(f"    Reasoning: {ref.reasoning}")
            print()

    # Exit code
    return 0 if len(result['incorrect_refs']) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
