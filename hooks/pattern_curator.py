#!/usr/bin/env python3
"""
Auto-learn coding patterns from codebase.

Automatically extracts recurring patterns and updates PATTERNS.md.
Promotes patterns seen 3+ times to "Validated Patterns" section.

Language-agnostic pattern detection.
"""

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set


def detect_language() -> str:
    """Detect primary project language."""
    if Path("pyproject.toml").exists() or Path("setup.py").exists():
        return "python"
    elif Path("package.json").exists():
        return "javascript"
    elif Path("go.mod").exists():
        return "go"
    else:
        return "unknown"


def extract_python_patterns(file_path: Path) -> Set[str]:
    """Extract Python coding patterns."""
    patterns = set()

    try:
        content = file_path.read_text(encoding="utf-8")

        # Class definitions
        for match in re.finditer(r"class\s+(\w+).*:", content):
            patterns.add(f"Class: {match.group(1)}")

        # Function definitions with type hints
        for match in re.finditer(r"def\s+(\w+)\([^)]*\)\s*->\s*(\w+):", content):
            patterns.add(f"Function with type hint: {match.group(1)}() -> {match.group(2)}")

        # Docstring style
        if '"""' in content:
            patterns.add("Docstring style: Google (triple quotes)")

        # Error handling patterns
        if "try:" in content and "except" in content:
            patterns.add("Error handling: try/except blocks")

        # Type hints usage
        if " -> " in content:
            patterns.add("Type hints: return types")
        if ": " in content and any(t in content for t in ["str", "int", "bool", "List", "Dict"]):
            patterns.add("Type hints: parameter types")

        # Import organization
        if "from typing import" in content:
            patterns.add("Imports: typing module used")
        if "from pathlib import Path" in content:
            patterns.add("Imports: pathlib.Path preferred over os.path")

    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}", file=sys.stderr)

    return patterns


def extract_javascript_patterns(file_path: Path) -> Set[str]:
    """Extract JavaScript/TypeScript patterns."""
    patterns = set()

    try:
        content = file_path.read_text(encoding="utf-8")

        # Class definitions
        for match in re.finditer(r"class\s+(\w+)", content):
            patterns.add(f"Class: {match.group(1)}")

        # Arrow functions
        if "=>" in content:
            patterns.add("Functions: arrow functions used")

        # Async/await
        if "async " in content and "await " in content:
            patterns.add("Async: async/await pattern")

        # TypeScript interfaces
        for match in re.finditer(r"interface\s+(\w+)", content):
            patterns.add(f"TypeScript: interface {match.group(1)}")

        # JSDoc comments
        if "/**" in content:
            patterns.add("Documentation: JSDoc comments")

        # Module exports
        if "export " in content:
            patterns.add("Modules: ES6 exports")

    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}", file=sys.stderr)

    return patterns


def extract_go_patterns(file_path: Path) -> Set[str]:
    """Extract Go coding patterns."""
    patterns = set()

    try:
        content = file_path.read_text(encoding="utf-8")

        # Struct definitions
        for match in re.finditer(r"type\s+(\w+)\s+struct", content):
            patterns.add(f"Struct: {match.group(1)}")

        # Interface definitions
        for match in re.finditer(r"type\s+(\w+)\s+interface", content):
            patterns.add(f"Interface: {match.group(1)}")

        # Error handling
        if "if err != nil" in content:
            patterns.add("Error handling: if err != nil pattern")

        # Table-driven tests
        if "tests := []struct" in content:
            patterns.add("Testing: table-driven tests")

    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}", file=sys.stderr)

    return patterns


def analyze_codebase(language: str) -> Counter:
    """Analyze codebase and count pattern occurrences."""
    pattern_counts = Counter()

    # Language-specific extractors
    extractors = {
        "python": (extract_python_patterns, ["**/*.py"]),
        "javascript": (extract_javascript_patterns, ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"]),
        "go": (extract_go_patterns, ["**/*.go"]),
    }

    if language not in extractors:
        return pattern_counts

    extractor, patterns = extractors[language]

    # Scan source directories
    for source_dir in ["src", "lib", "pkg", "app"]:
        dir_path = Path(source_dir)
        if not dir_path.exists():
            continue

        for pattern in patterns:
            for file_path in dir_path.glob(pattern):
                if file_path.is_file():
                    file_patterns = extractor(file_path)
                    pattern_counts.update(file_patterns)

    return pattern_counts


def update_patterns_md(language: str, validated_patterns: List[str], candidate_patterns: List[str]):
    """Update .claude/PATTERNS.md with learned patterns."""
    patterns_file = Path(".claude/PATTERNS.md")

    if not patterns_file.exists():
        # Create initial PATTERNS.md
        content = f"""---
language: {language}
pattern_count: {len(validated_patterns)}
last_updated: {Path('.').stat().st_mtime}
---

# Validated Patterns

Patterns seen 3+ times in the codebase.

"""
        for pattern in validated_patterns:
            content += f"- {pattern}\n"

        content += "\n## Candidate Patterns\n\n"
        content += "Patterns seen 1-2 times (need more evidence).\n\n"

        for pattern in candidate_patterns:
            content += f"- {pattern}\n"

        patterns_file.write_text(content)
        print(f"✅ Created PATTERNS.md with {len(validated_patterns)} validated patterns")
    else:
        # Update existing file
        content = patterns_file.read_text()

        # Add new validated patterns
        if validated_patterns:
            # Find or create Validated Patterns section
            if "# Validated Patterns" not in content:
                content += "\n## Validated Patterns\n\n"

            for pattern in validated_patterns:
                if pattern not in content:
                    # Add after Validated Patterns header
                    content = content.replace(
                        "# Validated Patterns", f"# Validated Patterns\n\n- {pattern}"
                    )

        patterns_file.write_text(content)
        print(f"✅ Updated PATTERNS.md")


def main():
    """Run pattern curation."""
    language = detect_language()

    if language == "unknown":
        print("⚠️  Could not detect language. Skipping pattern learning.")
        sys.exit(0)

    print(f"📚 Learning {language} patterns from codebase...")

    # Analyze codebase
    pattern_counts = analyze_codebase(language)

    if not pattern_counts:
        print("ℹ️  No patterns detected yet (need more code)")
        sys.exit(0)

    # Split into validated (3+) and candidate (1-2) patterns
    validated = [p for p, count in pattern_counts.items() if count >= 3]
    candidates = [p for p, count in pattern_counts.items() if 1 <= count < 3]

    print(f"   Found {len(validated)} validated patterns (seen 3+ times)")
    print(f"   Found {len(candidates)} candidate patterns (seen 1-2 times)")

    if validated:
        print(f"\n📋 Validated patterns:")
        for pattern in sorted(validated)[:10]:
            count = pattern_counts[pattern]
            print(f"   • {pattern} (seen {count}x)")

    # Update PATTERNS.md
    update_patterns_md(language, validated, candidates)


if __name__ == "__main__":
    main()
