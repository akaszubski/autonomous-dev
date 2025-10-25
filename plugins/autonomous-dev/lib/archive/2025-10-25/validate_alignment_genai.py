#!/usr/bin/env python3
"""
GenAI-Powered PROJECT.md Alignment Validator

Validates that proposed features, changes, and implementations align with
the strategic goals, scope, and constraints defined in PROJECT.md.

Uses LLM to understand semantic alignment, not just keyword matching.

Usage:
    # Validate a feature description
    python validate_alignment_genai.py --feature "Add OAuth authentication"

    # Validate from interactive prompt
    python validate_alignment_genai.py --interactive

    # Validate current git diff
    python validate_alignment_genai.py --diff

    # Batch validation
    python validate_alignment_genai.py --batch features.txt
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
PROJECT_MD = PROJECT_ROOT / ".claude" / "PROJECT.md"

# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class AlignmentResult:
    """Result of alignment validation."""
    feature_description: str
    aligned: bool  # True = aligned, False = misaligned
    confidence: str  # "high", "medium", "low"
    reasoning: str
    alignment_score: int  # 0-10
    concerns: List[str]
    suggestions: List[str]
    relevant_goals: List[str]
    scope_violations: List[str]
    constraint_violations: List[str]

    def is_acceptable(self) -> bool:
        """Check if alignment is acceptable (7+ score, no critical violations)."""
        has_critical_violations = (
            len(self.scope_violations) > 0 or
            len(self.constraint_violations) > 0
        )
        return self.alignment_score >= 7 and not has_critical_violations

    def summary(self) -> str:
        """Generate summary string."""
        if self.is_acceptable():
            return f"✅ ALIGNED ({self.alignment_score}/10) - {self.confidence} confidence"
        else:
            return f"❌ MISALIGNED ({self.alignment_score}/10) - {self.confidence} confidence"


# ============================================================================
# PROJECT.md Parser
# ============================================================================

def read_project_md() -> Dict[str, str]:
    """Read and parse PROJECT.md into sections."""
    if not PROJECT_MD.exists():
        print(f"❌ PROJECT.md not found at: {PROJECT_MD}")
        sys.exit(1)

    content = PROJECT_MD.read_text()

    # Extract key sections
    sections = {}

    # Extract GOALS
    goals_match = re.search(
        r'## GOALS\s*\n(.*?)(?=\n##|\Z)',
        content,
        re.DOTALL
    )
    if goals_match:
        sections['GOALS'] = goals_match.group(1).strip()

    # Extract SCOPE
    scope_match = re.search(
        r'## SCOPE\s*\n(.*?)(?=\n##|\Z)',
        content,
        re.DOTALL
    )
    if scope_match:
        sections['SCOPE'] = scope_match.group(1).strip()

    # Extract CONSTRAINTS
    constraints_match = re.search(
        r'## CONSTRAINTS\s*\n(.*?)(?=\n##|\Z)',
        content,
        re.DOTALL
    )
    if constraints_match:
        sections['CONSTRAINTS'] = constraints_match.group(1).strip()

    # Extract CURRENT SPRINT (optional)
    sprint_match = re.search(
        r'## CURRENT SPRINT\s*\n(.*?)(?=\n##|\Z)',
        content,
        re.DOTALL
    )
    if sprint_match:
        sections['CURRENT_SPRINT'] = sprint_match.group(1).strip()

    return sections


# ============================================================================
# GenAI Integration
# ============================================================================

def get_llm_client():
    """Get LLM client (prefer Anthropic for accuracy)."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if anthropic_key:
        try:
            import anthropic
        except ImportError:
            print("❌ anthropic package not installed!")
            print("Install with: pip install anthropic")
            sys.exit(1)

        client = anthropic.Anthropic(api_key=anthropic_key)
        model = "claude-sonnet-4-5-20250929"  # Latest Sonnet 4.5 (best quality)
        return client, model, "anthropic"
    elif openrouter_key:
        try:
            import openai
        except ImportError:
            print("❌ openai package not installed!")
            print("Install with: pip install openai")
            sys.exit(1)

        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
        )
        model = "anthropic/claude-3.5-sonnet"
        return client, model, "openrouter"
    else:
        print("❌ No API key found!")
        print()
        print("Set one of:")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        print("  export OPENROUTER_API_KEY=sk-or-v1-...")
        sys.exit(1)


def validate_alignment_with_genai(
    feature_description: str,
    project_sections: Dict[str, str]
) -> AlignmentResult:
    """
    Validate feature alignment using GenAI.

    This is far superior to keyword matching - understands:
    - Semantic alignment (not just word overlap)
    - Scope creep vs legitimate extensions
    - Strategic fit vs tactical distractions
    - Constraint violations (technical, resource, philosophical)
    """
    client, model, provider = get_llm_client()

    # Build comprehensive prompt
    prompt = f"""You are validating whether a proposed feature aligns with a project's strategic goals and constraints.

**PROJECT CONTEXT**

**GOALS** (What success looks like):
{project_sections.get('GOALS', 'Not specified')}

**SCOPE** (What's included/excluded):
{project_sections.get('SCOPE', 'Not specified')}

**CONSTRAINTS** (Technical, resource, philosophical limits):
{project_sections.get('CONSTRAINTS', 'Not specified')}

**CURRENT SPRINT** (Active focus):
{project_sections.get('CURRENT_SPRINT', 'Not specified')}

---

**PROPOSED FEATURE**:
{feature_description}

---

**VALIDATION TASK**:

Analyze whether this feature aligns with the project's strategic direction.

Consider:

1. **Goal Alignment**: Does this serve the stated goals? Which ones? How directly?

2. **Scope Fit**: Is this within declared scope? Or is it scope creep disguised as enhancement?

3. **Constraint Compliance**: Does it violate any constraints (technical, resource, philosophical)?

4. **Strategic Value**: Is this solving the right problem? Or a distraction?

5. **Sprint Relevance**: Does it align with current sprint focus? If not, should it wait?

**IMPORTANT NUANCES**:
- "Authentication" could align with "security" goal OR be overengineering
- "Team features" might violate "solo developer" scope
- "Complex UI" might violate "simplicity" constraint
- Feature might be good but WRONG TIMING (not current sprint)

Provide your analysis in JSON format:

```json
{{
  "aligned": true/false,
  "confidence": "high/medium/low",
  "alignment_score": 0-10,
  "reasoning": "Detailed explanation of why this aligns or doesn't",
  "relevant_goals": ["Goal 1 that this serves", "Goal 2..."],
  "concerns": ["Concern 1 if any", "Concern 2..."],
  "scope_violations": ["Violation 1 if any", "Violation 2..."],
  "constraint_violations": ["Violation 1 if any", "Violation 2..."],
  "suggestions": ["How to make it better align", "Alternative approach..."]
}}
```

Be strict but fair. If it's borderline, say so (medium confidence). If it clearly violates goals/scope/constraints, reject it.
"""

    # Call LLM
    print(f"🤖 Validating alignment with {provider} GenAI...")

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
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text

    try:
        result_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse GenAI response: {e}")
        print(f"Response: {response_text[:500]}")
        sys.exit(1)

    # Build result
    return AlignmentResult(
        feature_description=feature_description,
        aligned=result_data.get("aligned", False),
        confidence=result_data.get("confidence", "low"),
        reasoning=result_data.get("reasoning", "No reasoning provided"),
        alignment_score=result_data.get("alignment_score", 0),
        concerns=result_data.get("concerns", []),
        suggestions=result_data.get("suggestions", []),
        relevant_goals=result_data.get("relevant_goals", []),
        scope_violations=result_data.get("scope_violations", []),
        constraint_violations=result_data.get("constraint_violations", [])
    )


# ============================================================================
# CLI
# ============================================================================

def print_result(result: AlignmentResult):
    """Print alignment result in human-readable format."""
    print()
    print("=" * 70)
    print(result.summary())
    print("=" * 70)
    print()
    print(f"**Feature**: {result.feature_description}")
    print()
    print(f"**Score**: {result.alignment_score}/10")
    print(f"**Confidence**: {result.confidence}")
    print()
    print(f"**Reasoning**:")
    print(f"  {result.reasoning}")
    print()

    if result.relevant_goals:
        print(f"**Serves Goals**:")
        for goal in result.relevant_goals:
            print(f"  ✓ {goal}")
        print()

    if result.concerns:
        print(f"**Concerns**:")
        for concern in result.concerns:
            print(f"  ⚠️  {concern}")
        print()

    if result.scope_violations:
        print(f"**Scope Violations**:")
        for violation in result.scope_violations:
            print(f"  ❌ {violation}")
        print()

    if result.constraint_violations:
        print(f"**Constraint Violations**:")
        for violation in result.constraint_violations:
            print(f"  ❌ {violation}")
        print()

    if result.suggestions:
        print(f"**Suggestions**:")
        for suggestion in result.suggestions:
            print(f"  💡 {suggestion}")
        print()

    if result.is_acceptable():
        print("✅ **RECOMMENDATION**: Proceed with implementation")
    else:
        print("❌ **RECOMMENDATION**: Reject or revise to align with PROJECT.md")

    print()


def get_git_diff() -> Optional[str]:
    """Get current git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        return None
    except Exception as e:
        print(f"⚠️  Could not get git diff: {e}")
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="GenAI-powered PROJECT.md alignment validator"
    )

    parser.add_argument(
        "--feature",
        help="Feature description to validate"
    )

    parser.add_argument(
        "--diff",
        action="store_true",
        help="Validate current git diff"
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode (prompt for feature)"
    )

    parser.add_argument(
        "--batch",
        help="Batch file with features (one per line)"
    )

    args = parser.parse_args()

    # Read PROJECT.md
    print("📖 Reading PROJECT.md...")
    project_sections = read_project_md()
    print(f"✅ Loaded {len(project_sections)} sections")
    print()

    # Determine what to validate
    features_to_validate = []

    if args.feature:
        features_to_validate.append(args.feature)
    elif args.diff:
        diff = get_git_diff()
        if diff:
            features_to_validate.append(f"Git diff changes:\n{diff[:2000]}")
        else:
            print("No git diff found")
            return 0
    elif args.batch:
        batch_file = Path(args.batch)
        if batch_file.exists():
            features_to_validate = [
                line.strip()
                for line in batch_file.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            ]
        else:
            print(f"❌ Batch file not found: {args.batch}")
            return 1
    elif args.interactive:
        print("Enter feature description (Ctrl+D when done):")
        feature = sys.stdin.read().strip()
        if feature:
            features_to_validate.append(feature)
    else:
        parser.print_help()
        return 1

    # Validate each feature
    all_acceptable = True

    for i, feature in enumerate(features_to_validate, 1):
        if len(features_to_validate) > 1:
            print(f"\n{'=' * 70}")
            print(f"Feature {i}/{len(features_to_validate)}")
            print(f"{'=' * 70}\n")

        result = validate_alignment_with_genai(feature, project_sections)
        print_result(result)

        if not result.is_acceptable():
            all_acceptable = False

    # Exit code
    return 0 if all_acceptable else 1


if __name__ == "__main__":
    sys.exit(main())
