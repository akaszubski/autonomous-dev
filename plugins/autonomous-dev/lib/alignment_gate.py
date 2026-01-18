#!/usr/bin/env python3
"""
Strict PROJECT.md Alignment Gate - Gatekeeper for feature validation.

Enforces strict alignment validation using GenAI with score-based gating.
Features must EXPLICITLY match SCOPE items (not just be "related to") and
score >= 7 to pass through the gate.

Key Features:
1. Score-based gating (7+ = pass, <7 = fail)
2. Explicit SCOPE membership required (not "related to")
3. Constraint violation detection (blocks even high-scoring features)
4. Decision tracking to alignment_history.jsonl
5. Meta-validation statistics

Strict Gatekeeper Rules:
- Ambiguous features get scores 4-6 (require clarification)
- "Related to" scope is NOT sufficient (must be explicit)
- Constraint violations block approval regardless of score
- Empty/vague descriptions are rejected

Usage:
    from alignment_gate import validate_alignment_strict, AlignmentGateResult

    # Validate feature against PROJECT.md
    result = validate_alignment_strict(
        "Add new CLI command for git status",
        Path(".claude/PROJECT.md")
    )

    if result.aligned and result.score >= 7:
        print("Feature approved!")
    else:
        print(f"Feature blocked: {result.reasoning}")
        for violation in result.violations:
            print(f"  - {violation}")

Date: 2026-01-19
Issue: #251 (Strict PROJECT.md Alignment Gate)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import security utilities for audit logging
sys.path.insert(0, str(Path(__file__).parent))
from security_utils import audit_log  # type: ignore[import-not-found]

# ============================================================================
# CONSTANTS
# ============================================================================

# Score threshold for alignment approval (7+)
ALIGNMENT_SCORE_THRESHOLD = 7

# Project root detection (same pattern as security_utils.py)
def _detect_project_root() -> Path:
    """Dynamically detect project root from current working directory."""
    start = Path.cwd()

    # Priority 1: Search for .git (git repos take precedence)
    current = start
    for _ in range(10):
        if (current / ".git").exists():
            return current.resolve()
        if current.parent == current:
            break
        current = current.parent

    # Priority 2: Search for .claude if no .git found
    current = start
    for _ in range(10):
        if (current / ".claude").exists():
            return current.resolve()
        if current.parent == current:
            break
        current = current.parent

    # Fall back to current working directory
    return Path.cwd().resolve()

PROJECT_ROOT = _detect_project_root()
ALIGNMENT_HISTORY_PATH = PROJECT_ROOT / "logs" / "alignment_history.jsonl"

# ============================================================================
# EXCEPTIONS
# ============================================================================

class AlignmentError(Exception):
    """Base exception for alignment validation errors."""
    pass

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AlignmentGateResult:
    """Result of strict alignment validation.

    Attributes:
        aligned: Whether feature aligns with PROJECT.md (score >= 7, no constraints)
        score: Alignment score 0-10 (7+ = pass, <7 = fail)
        violations: List of scope/goal violations
        reasoning: Detailed reasoning for alignment decision
        relevant_scope: List of SCOPE items that match
        suggestions: Suggestions for improving alignment
        constraint_violations: List of CONSTRAINT violations (blocks approval)
        confidence: Confidence level (high/medium/low)
    """
    aligned: bool
    score: int
    violations: List[str]
    reasoning: str
    relevant_scope: List[str]
    suggestions: List[str]
    constraint_violations: List[str]
    confidence: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

# ============================================================================
# GenAI LLM Client (from genai_validate.py pattern)
# ============================================================================

def get_llm_client():
    """Get LLM client (prefer Anthropic for accuracy)."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if anthropic_key:
        try:
            import anthropic
        except ImportError:
            raise AlignmentError(
                "anthropic package not installed!\n"
                "Install with: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=anthropic_key)
        model = "claude-sonnet-4-5-20250929"
        return client, model, "anthropic"
    elif openrouter_key:
        try:
            import openai
        except ImportError:
            raise AlignmentError(
                "openai package not installed!\n"
                "Install with: pip install openai"
            )

        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
        )
        model = "anthropic/claude-sonnet-4.5"
        return client, model, "openrouter"
    else:
        raise AlignmentError(
            "No API key found!\n"
            "Set one of:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "  export OPENROUTER_API_KEY=sk-or-v1-..."
        )

def call_llm(prompt: str) -> str:
    """Call LLM with prompt, return response."""
    client, model, provider = get_llm_client()

    if provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    else:  # openrouter
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

def parse_json_response(response_text: str) -> dict:
    """Parse JSON from LLM response (handles markdown formatting)."""
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise AlignmentError(
            f"Failed to parse GenAI response: {e}\n"
            f"Response: {response_text[:500]}"
        )

# ============================================================================
# PROJECT.md PARSING
# ============================================================================

def read_project_md(project_md_path: Path) -> Dict[str, str]:
    """Read and parse PROJECT.md into sections.

    Args:
        project_md_path: Path to PROJECT.md file

    Returns:
        Dict mapping section names to content

    Raises:
        AlignmentError: If PROJECT.md not found or malformed
    """
    if not project_md_path.exists():
        raise AlignmentError(
            f"PROJECT.md not found: {project_md_path}\n"
            f"Expected: .claude/PROJECT.md in project root\n"
            f"See: docs/PROJECT-ALIGNMENT.md"
        )

    content = project_md_path.read_text()
    sections = {}

    # Parse sections (GOALS, SCOPE, CONSTRAINTS, CURRENT_SPRINT)
    for section_name in ['GOALS', 'SCOPE', 'CONSTRAINTS', 'CURRENT_SPRINT']:
        match = re.search(
            rf'## {section_name}\s*\n(.*?)(?=\n##|\Z)',
            content,
            re.DOTALL
        )
        if match:
            sections[section_name] = match.group(1).strip()

    # Validate required sections
    if 'GOALS' not in sections or 'SCOPE' not in sections:
        raise AlignmentError(
            f"Malformed PROJECT.md: {project_md_path}\n"
            f"Missing required sections: GOALS and/or SCOPE\n"
            f"Found sections: {list(sections.keys())}\n"
            f"Expected: ## GOALS and ## SCOPE sections\n"
            f"See: docs/PROJECT-ALIGNMENT.md"
        )

    return sections

# ============================================================================
# STRICT ALIGNMENT VALIDATION
# ============================================================================

def validate_alignment_strict(
    feature_desc: str,
    project_md_path: Optional[Path] = None
) -> AlignmentGateResult:
    """
    Strict alignment validation using GenAI.

    This is a STRICT GATEKEEPER that:
    - Requires EXPLICIT SCOPE match (not "related to")
    - Scores ambiguous features 4-6 (not 7+)
    - Blocks constraint violations even if score is high
    - Requires score >= 7 to pass

    Args:
        feature_desc: Feature description to validate
        project_md_path: Path to PROJECT.md (default: .claude/PROJECT.md)

    Returns:
        AlignmentGateResult with validation decision

    Raises:
        AlignmentError: If feature description is empty/invalid or PROJECT.md issues

    Examples:
        >>> result = validate_alignment_strict("Add CLI command", Path("PROJECT.md"))
        >>> result.aligned
        True
        >>> result.score >= 7
        True
    """
    # Validate feature description
    if not feature_desc or not feature_desc.strip():
        raise AlignmentError(
            "Feature description is empty or invalid\n"
            "Expected: Non-empty feature description\n"
            f"Got: '{feature_desc}'"
        )

    feature_desc = feature_desc.strip()

    # Default PROJECT.md path
    if project_md_path is None:
        project_md_path = PROJECT_ROOT / ".claude" / "PROJECT.md"

    # Read PROJECT.md sections
    sections = read_project_md(project_md_path)

    # Build STRICT prompt with gatekeeper instructions
    prompt = f"""You are a STRICT GATEKEEPER validating whether a proposed feature aligns with PROJECT.md.

**CRITICAL: This is STRICT MODE - be a critical gatekeeper, not a helpful assistant.**

**PROJECT CONTEXT**

**GOALS** (What success looks like):
{sections.get('GOALS', 'Not specified')}

**SCOPE** (What's included/excluded):
{sections.get('SCOPE', 'Not specified')}

**CONSTRAINTS** (Technical, resource, philosophical limits):
{sections.get('CONSTRAINTS', 'Not specified')}

**CURRENT SPRINT** (Active focus):
{sections.get('CURRENT_SPRINT', 'Not specified')}

---

**PROPOSED FEATURE**:
{feature_desc}

---

**STRICT VALIDATION RULES**:

1. **EXPLICIT SCOPE MEMBERSHIP REQUIRED**
   - Feature must EXPLICITLY match a SCOPE item
   - "Related to" or "similar to" is NOT sufficient
   - Example: If SCOPE says "Git automation", then "Mercurial support" is OUT OF SCOPE
   - Example: If SCOPE says "CLI commands", then "Web dashboard" is OUT OF SCOPE

2. **AMBIGUOUS FEATURES GET MID-RANGE SCORES (4-6)**
   - Vague descriptions like "improve performance" → score 4-6
   - One-word descriptions → score 4-6
   - Missing context or metrics → score 4-6
   - Needs clarification → score 4-6

3. **CONSTRAINT VIOLATIONS BLOCK APPROVAL**
   - Even if score is 8-10, constraint violations block approval
   - Set aligned=false if any constraint violations detected
   - Examples: breaking changes, performance violations, platform-specific

4. **SCORING SCALE**:
   - 9-10: Perfect explicit match to SCOPE + GOALS, no violations
   - 7-8: Good explicit match to SCOPE, minor concerns
   - 4-6: Ambiguous, needs clarification, or only tangentially related
   - 1-3: Clearly out of scope, not aligned with GOALS
   - 0: Completely unrelated or harmful

5. **BE CRITICAL, NOT HELPFUL**
   - You are a gatekeeper, not a helpful assistant
   - When in doubt, reject (score < 7)
   - Require explicit evidence of alignment
   - Don't stretch to find connections

---

**OUTPUT FORMAT** (JSON):

```json
{{
  "aligned": true/false,
  "score": 0-10,
  "violations": ["Violation 1 if any", "Violation 2..."],
  "reasoning": "Detailed explanation of why this aligns or doesn't (cite specific SCOPE/GOALS items)",
  "relevant_scope": ["SCOPE item 1 that matches", "SCOPE item 2..."],
  "suggestions": ["How to make it align better", "Alternative approach..."],
  "constraint_violations": ["CONSTRAINT violation 1 if any", "CONSTRAINT violation 2..."],
  "confidence": "high/medium/low"
}}
```

**ANALYZE NOW** - Apply strict gatekeeper rules:
"""

    # Call GenAI
    response = call_llm(prompt)
    data = parse_json_response(response)

    # Build result
    result = AlignmentGateResult(
        aligned=data.get("aligned", False),
        score=data.get("score", 0),
        violations=data.get("violations", []),
        reasoning=data.get("reasoning", "No reasoning provided"),
        relevant_scope=data.get("relevant_scope", []),
        suggestions=data.get("suggestions", []),
        constraint_violations=data.get("constraint_violations", []),
        confidence=data.get("confidence", "low")
    )

    # Override aligned=False if constraint violations exist (strict gatekeeper)
    if len(result.constraint_violations) > 0:
        result.aligned = False

    # Override aligned=False if score < threshold
    if result.score < ALIGNMENT_SCORE_THRESHOLD:
        result.aligned = False

    # Audit log
    audit_log(
        "alignment_validation",
        "approved" if result.aligned else "rejected",
        {
            "feature_description": feature_desc[:200],
            "score": result.score,
            "aligned": result.aligned,
            "violations": len(result.violations),
            "constraint_violations": len(result.constraint_violations),
            "confidence": result.confidence,
        }
    )

    return result

# ============================================================================
# SCOPE MEMBERSHIP CHECKING
# ============================================================================

def check_scope_membership(feature: str, scope_section: str) -> bool:
    """
    Check if feature EXPLICITLY matches an IN SCOPE item.

    This is STRICT matching - "related to" is not sufficient.
    Uses case-insensitive keyword matching with word boundary awareness.

    Args:
        feature: Feature description
        scope_section: SCOPE section content from PROJECT.md

    Returns:
        True if explicit match found, False otherwise

    Examples:
        >>> check_scope_membership("Add CLI command", "- CLI commands\\n- Git automation")
        True
        >>> check_scope_membership("Add blockchain", "- CLI commands\\n- Git automation")
        False
    """
    if not scope_section or not scope_section.strip():
        return False

    if not feature or not feature.strip():
        return False

    # Normalize for case-insensitive matching
    feature_lower = feature.lower()
    scope_lower = scope_section.lower()

    # Extract scope items (lines starting with -, exclude sub-items with extra indentation)
    scope_items = []
    for line in scope_lower.split('\n'):
        stripped = line.lstrip()
        # Only include top-level items (one dash at start after stripping)
        if stripped.startswith('-') and not line.startswith('  -'):
            # Remove leading dash and whitespace
            item = stripped[1:].strip()
            scope_items.append(item)

    # Check for explicit keyword matches
    for item in scope_items:
        # Extract significant words (length > 2, not common stopwords)
        # Split on both spaces and hyphens to handle "agent-based" -> ["agent", "based"]
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'for', 'with', 'of', 'to', 'in', 'on', 'at', 'based'}
        raw_words = re.findall(r'\w+', item)  # Split on non-word characters (spaces, hyphens, etc.)
        words = [w for w in raw_words if len(w) > 2 and w not in stopwords]

        if not words:
            continue

        # Normalize singular/plural by removing trailing 's'
        # This allows "workflow" to match "workflows" and vice versa
        normalized_scope_words = []
        for word in words:
            normalized = word.rstrip('s') if len(word) > 3 else word
            normalized_scope_words.append(normalized)

        # Check word boundaries to avoid false positives
        # "CLI-like" should NOT match "CLI" because "-like" changes the meaning
        feature_words = set(re.findall(r'\b\w+\b', feature_lower))

        # Normalize feature words too
        normalized_feature_words = set()
        for word in feature_words:
            normalized = word.rstrip('s') if len(word) > 3 else word
            normalized_feature_words.add(normalized)

        # Count matches using normalized words
        matches = sum(1 for scope_word in normalized_scope_words if scope_word in normalized_feature_words)

        # Require at least 50% of significant words to match
        # But for compound terms (like "CLI commands"), both parts should match
        if len(words) > 0 and matches >= len(words) * 0.5:
            # Additional check: if scope has multiple words, require >1 match
            # to avoid "CLI-like" matching "CLI commands"
            if len(words) > 1 and matches < 2:
                continue
            return True

    return False

# ============================================================================
# DECISION TRACKING
# ============================================================================

def track_alignment_decision(result: AlignmentGateResult) -> None:
    """
    Track alignment decision to history file (JSONL format).

    Appends decision to logs/alignment_history.jsonl for meta-validation analysis.

    Args:
        result: AlignmentGateResult to track
    """
    # Ensure logs directory exists
    ALIGNMENT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Build decision record
    record = result.to_dict()
    record["timestamp"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    # Append to history file (JSONL format)
    with open(ALIGNMENT_HISTORY_PATH, 'a') as f:
        f.write(json.dumps(record) + '\n')

    # Audit log
    audit_log(
        "alignment_decision_tracked",
        "success",
        {
            "aligned": result.aligned,
            "score": result.score,
            "history_path": str(ALIGNMENT_HISTORY_PATH),
        }
    )

# ============================================================================
# META-VALIDATION STATISTICS
# ============================================================================

def get_alignment_stats() -> Dict[str, Any]:
    """
    Get meta-validation statistics from alignment history.

    Returns:
        Dict with keys:
        - total_decisions: Total number of alignment decisions
        - approved_count: Number of approved features
        - rejected_count: Number of rejected features
        - approval_rate: Percentage of approved features (0.0-1.0)
        - average_score: Average alignment score
        - constraint_violation_count: Number of decisions with constraint violations

    Examples:
        >>> stats = get_alignment_stats()
        >>> stats["approval_rate"]
        0.75
    """
    if not ALIGNMENT_HISTORY_PATH.exists():
        return {
            "total_decisions": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "approval_rate": 0.0,
            "average_score": 0.0,
            "constraint_violation_count": 0,
        }

    # Read history
    decisions = []
    with open(ALIGNMENT_HISTORY_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                decision = json.loads(line)
                decisions.append(decision)
            except json.JSONDecodeError:
                # Skip malformed lines
                continue

    if not decisions:
        return {
            "total_decisions": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "approval_rate": 0.0,
            "average_score": 0.0,
            "constraint_violation_count": 0,
        }

    # Calculate statistics
    total = len(decisions)
    approved = sum(1 for d in decisions if d.get("aligned", False))
    rejected = total - approved
    approval_rate = approved / total if total > 0 else 0.0

    scores = [d.get("score", 0) for d in decisions]
    average_score = sum(scores) / len(scores) if scores else 0.0

    constraint_violations = sum(
        1 for d in decisions
        if len(d.get("constraint_violations", [])) > 0
    )

    return {
        "total_decisions": total,
        "approved_count": approved,
        "rejected_count": rejected,
        "approval_rate": approval_rate,
        "average_score": average_score,
        "constraint_violation_count": constraint_violations,
    }

# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "AlignmentGateResult",
    "validate_alignment_strict",
    "check_scope_membership",
    "track_alignment_decision",
    "get_alignment_stats",
    "AlignmentError",
    "ALIGNMENT_SCORE_THRESHOLD",
]
