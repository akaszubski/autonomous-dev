"""Scope detection and complexity analysis for issue decomposition.

This module analyzes feature requests to detect large scope and determine if
decomposition into atomic issues is needed. It performs keyword detection,
anti-pattern identification, and effort estimation.

Classes:
    EffortSize: Effort size categories (XS/S/M/L/XL)
    ComplexityAnalysis: Results of complexity analysis with effort estimation

Functions:
    analyze_complexity: Main analysis function for feature requests
    estimate_atomic_count: Estimate number of atomic sub-issues needed
    generate_decomposition_prompt: Generate prompt for issue decomposition
    load_config: Load configuration from file with fallback to defaults

Security:
    - Input validation for all user-provided text
    - Graceful degradation for invalid inputs
    - No external dependencies on network resources

Related:
    - GitHub Issue #XXX: Scope detection for auto-decomposition

Relevant Skills:
    - error-handling-patterns: Graceful degradation for invalid inputs
    - library-design-patterns: Configuration loading and default fallback
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import re
import json
from pathlib import Path
import logging

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class EffortSize(Enum):
    """Effort size categories for feature estimation.

    Values align with t-shirt sizing for time estimation:
    - XS: < 1 hour
    - S: 1-4 hours
    - M: 4-8 hours
    - L: 1-2 days
    - XL: > 2 days
    """
    XS = "xs"
    S = "s"
    M = "m"
    L = "l"
    XL = "xl"


@dataclass
class ComplexityAnalysis:
    """Results of complexity analysis for a feature request.

    Attributes:
        effort: Estimated effort size (XS/S/M/L/XL)
        indicators: Dictionary of detected complexity indicators
        needs_decomposition: Whether request should be broken into sub-issues
        confidence: Confidence score for analysis (0.0-1.0)
    """
    effort: EffortSize
    indicators: Dict[str, Any]
    needs_decomposition: bool
    confidence: float


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_CONFIG = {
    "decomposition_threshold": "M",
    "max_atomic_issues": 5,
    "keyword_sets": {
        "complexity_high": ["refactor", "redesign", "migrate", "overhaul", "rewrite", "architect"],
        "complexity_medium": ["add", "implement", "create", "build", "integrate"],
        "vague_indicators": ["improve", "enhance", "optimize", "better", "faster", "cleaner"],
        "domain_terms": ["authentication", "oauth", "saml", "ldap", "jwt", "api", "database", "security"],
        "breadth_indicators": ["complete", "entire", "full", "comprehensive", "system", "platform"]
    },
    "anti_patterns": {
        "conjunction_limit": 3,
        "file_type_limit": 3
    }
}


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from file with fallback to defaults.

    Args:
        config_path: Path to JSON configuration file (optional)

    Returns:
        Configuration dictionary with all required fields

    Examples:
        >>> config = load_config()  # Uses defaults
        >>> config = load_config(Path("scope_thresholds.json"))
    """
    if config_path is None:
        return DEFAULT_CONFIG.copy()

    try:
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return DEFAULT_CONFIG.copy()

        with open(config_path, 'r') as f:
            loaded_config = json.load(f)

        # Merge with defaults to ensure all required fields exist
        config = DEFAULT_CONFIG.copy()
        config.update(loaded_config)

        # Deep merge keyword_sets and anti_patterns
        if "keyword_sets" in loaded_config:
            config["keyword_sets"] = DEFAULT_CONFIG["keyword_sets"].copy()
            config["keyword_sets"].update(loaded_config["keyword_sets"])

        if "anti_patterns" in loaded_config:
            config["anti_patterns"] = DEFAULT_CONFIG["anti_patterns"].copy()
            config["anti_patterns"].update(loaded_config["anti_patterns"])

        return config

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading config from {config_path}: {e}, using defaults")
        return DEFAULT_CONFIG.copy()


# ============================================================================
# Detection Functions
# ============================================================================

def detect_keywords(text: str, keyword_sets: Dict[str, List[str]]) -> Dict[str, int]:
    """Detect and count keyword occurrences in text.

    Performs case-insensitive matching using word boundaries to avoid
    partial matches. For domain terms, allows partial matches (e.g., "OAuth2" matches "oauth").

    Args:
        text: Input text to analyze
        keyword_sets: Dictionary of keyword categories and their keywords

    Returns:
        Dictionary mapping category names to match counts

    Examples:
        >>> keywords = {"high": ["refactor", "migrate"]}
        >>> detect_keywords("Refactor and migrate system", keywords)
        {'high': 2}
    """
    if not text:
        return {category: 0 for category in keyword_sets.keys()}

    text_lower = text.lower()
    counts = {}

    for category, keywords in keyword_sets.items():
        count = 0
        for keyword in keywords:
            keyword_lower = keyword.lower()

            # For domain terms, allow partial matches (OAuth2 matches oauth)
            if category == "domain_terms":
                # Use looser pattern - just check if keyword is in text as substring
                if keyword_lower in text_lower:
                    count += 1
            else:
                # Use word boundaries for other categories
                pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                count += len(re.findall(pattern, text_lower))

        counts[category] = count

    return counts


def detect_anti_patterns(text: str, anti_patterns: Dict[str, int]) -> Dict[str, Any]:
    """Detect anti-patterns in feature requests.

    Detects:
    - Excessive conjunctions ("and" count)
    - Multiple file types mentioned
    - Vague requirement keywords

    Args:
        text: Input text to analyze
        anti_patterns: Configuration for anti-pattern thresholds

    Returns:
        Dictionary with detected anti-pattern counts

    Examples:
        >>> detect_anti_patterns("Update .py and .js and .md", {"file_type_limit": 3})
        {'conjunction_count': 2, 'file_types': 3, 'vague_keywords': 0}
    """
    if not text:
        return {
            "conjunction_count": 0,
            "file_types": 0,
            "vague_keywords": 0
        }

    text_lower = text.lower()

    # Count "and" conjunctions with word boundaries
    conjunction_count = len(re.findall(r'\band\b', text_lower))

    # Detect file type extensions
    file_extensions = ['.py', '.js', '.md', '.json', '.yaml', '.yml', '.sh', '.ts', '.tsx', '.jsx']
    file_types_found = set()
    for ext in file_extensions:
        if ext in text_lower:
            file_types_found.add(ext)

    # Count vague keywords from config
    vague_keywords = DEFAULT_CONFIG["keyword_sets"]["vague_indicators"]
    vague_count = 0
    for keyword in vague_keywords:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        vague_count += len(re.findall(pattern, text_lower))

    return {
        "conjunction_count": conjunction_count,
        "file_types": len(file_types_found),
        "vague_keywords": vague_count
    }


# ============================================================================
# Effort Estimation
# ============================================================================

def estimate_effort(indicators: Dict[str, Any]) -> EffortSize:
    """Estimate effort size based on complexity indicators.

    Estimation logic:
    - XS: No high keywords, <=1 medium keyword, no anti-patterns
    - S: <=2 medium keywords, no high keywords, <=1 anti-pattern
    - M: 1-2 high keywords OR 3-4 medium keywords OR 2 anti-patterns
    - L: 3+ high keywords OR 5+ medium keywords OR 3+ anti-patterns
    - XL: Multiple high indicators + multiple anti-patterns

    Args:
        indicators: Dictionary of detected complexity indicators

    Returns:
        Estimated effort size

    Examples:
        >>> indicators = {"keyword_matches": {"complexity_high": 0, "complexity_medium": 1},
        ...               "anti_patterns": {"conjunction_count": 0}}
        >>> estimate_effort(indicators)
        <EffortSize.XS: 'xs'>
    """
    keyword_matches = indicators.get("keyword_matches", {})
    high_count = keyword_matches.get("complexity_high", 0)
    medium_count = keyword_matches.get("complexity_medium", 0)
    domain_count = keyword_matches.get("domain_terms", 0)
    breadth_count = keyword_matches.get("breadth_indicators", 0)

    anti_patterns = indicators.get("anti_patterns", {})
    conjunction_count = anti_patterns.get("conjunction_count", 0)
    file_types = anti_patterns.get("file_types", 0)
    vague_keywords = anti_patterns.get("vague_keywords", 0)

    # Count total anti-pattern indicators
    total_anti_patterns = sum([
        1 if conjunction_count >= 3 else 0,
        1 if file_types >= 3 else 0,
        1 if vague_keywords >= 3 else 0
    ])

    # Additional complexity boosters (2 conjunctions indicates complexity)
    complexity_boost = 0
    if conjunction_count >= 2:
        complexity_boost += 1
    if file_types >= 2:
        complexity_boost += 1
    if domain_count >= 3:  # Multiple domain terms = complex feature
        complexity_boost += 1
    if breadth_count >= 2:  # Breadth indicators = complex scope
        complexity_boost += 1

    # XL: Multiple high indicators + multiple anti-patterns
    if high_count >= 3 and total_anti_patterns >= 2:
        return EffortSize.XL

    # L: High complexity signals
    if high_count >= 3 or medium_count >= 5 or total_anti_patterns >= 3:
        return EffortSize.L

    # L: Multiple high keywords with conjunctions or domain complexity
    if high_count >= 2 and (conjunction_count >= 2 or domain_count >= 3):
        return EffortSize.L

    # L: High keyword with significant domain complexity
    if high_count >= 1 and domain_count >= 3 and conjunction_count >= 2:
        return EffortSize.L

    # L: High keyword with very high domain complexity (4+ domain terms)
    if high_count >= 1 and domain_count >= 4:
        return EffortSize.L

    # L: Medium complexity with high domain and conjunction complexity
    if medium_count >= 1 and domain_count >= 2 and conjunction_count >= 2:
        return EffortSize.L

    # M: Medium-high complexity
    if high_count >= 1 or medium_count >= 3 or total_anti_patterns >= 2:
        return EffortSize.M

    # M: Medium keywords with complexity boosters (domain terms, conjunctions)
    if medium_count >= 1 and (complexity_boost >= 1 or domain_count >= 2):
        return EffortSize.M

    # S: <=2 medium keywords, no high keywords
    if medium_count >= 1 and high_count == 0:
        return EffortSize.S

    # XS: Minimal complexity
    return EffortSize.XS


def calculate_confidence(indicators: Dict[str, Any]) -> float:
    """Calculate confidence score for complexity analysis.

    Higher confidence when:
    - Clear keyword indicators present
    - Multiple anti-patterns detected
    - Consistent signals across indicators

    Lower confidence when:
    - No clear indicators
    - Empty or vague input
    - Mixed signals

    Args:
        indicators: Dictionary of detected complexity indicators

    Returns:
        Confidence score between 0.0 and 1.0

    Examples:
        >>> indicators = {"keyword_matches": {"complexity_high": 3}}
        >>> calculate_confidence(indicators)
        0.85
    """
    keyword_matches = indicators.get("keyword_matches", {})
    high_count = keyword_matches.get("complexity_high", 0)
    medium_count = keyword_matches.get("complexity_medium", 0)
    vague_count = keyword_matches.get("vague_indicators", 0)
    domain_count = keyword_matches.get("domain_terms", 0)

    anti_patterns = indicators.get("anti_patterns", {})
    total_anti_patterns = sum([
        1 if anti_patterns.get("conjunction_count", 0) >= 3 else 0,
        1 if anti_patterns.get("file_types", 0) >= 3 else 0,
        1 if anti_patterns.get("vague_keywords", 0) >= 3 else 0
    ])

    # Calculate total indicators
    total_indicators = high_count + medium_count + total_anti_patterns

    # Empty input = low confidence
    if total_indicators == 0 and domain_count == 0:
        return 0.3 if vague_count > 0 else 0.4

    # High indicators = high confidence
    if high_count >= 3:
        return 0.9
    if high_count >= 2:
        return 0.85
    if high_count >= 1:
        return 0.75

    # Medium indicators + domain terms = medium-high confidence
    if medium_count >= 1 and domain_count >= 2:
        return 0.65
    if medium_count >= 3 and total_anti_patterns >= 1:
        return 0.7
    if medium_count >= 2:
        return 0.65

    # Some indicators = medium confidence
    if total_indicators >= 2:
        return 0.6

    # Few indicators = lower confidence
    return 0.5


# ============================================================================
# Main Analysis Functions
# ============================================================================

def analyze_complexity(request: str, config: Optional[Dict] = None) -> ComplexityAnalysis:
    """Analyze complexity of a feature request.

    Main analysis function that:
    1. Detects keywords (high/medium complexity, vague indicators)
    2. Detects anti-patterns (conjunctions, file types, vague terms)
    3. Estimates effort size
    4. Calculates confidence
    5. Determines if decomposition needed

    Args:
        request: Feature request text to analyze
        config: Optional configuration dictionary (uses defaults if None)

    Returns:
        ComplexityAnalysis with effort, indicators, decomposition flag, and confidence

    Examples:
        >>> result = analyze_complexity("Add type hints to utils.py")
        >>> result.effort
        <EffortSize.XS: 'xs'>
        >>> result.needs_decomposition
        False
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Handle edge cases - empty/None/whitespace
    if not request or not request.strip():
        return ComplexityAnalysis(
            effort=EffortSize.M,
            indicators={
                "keyword_matches": {},
                "anti_patterns": {}
            },
            needs_decomposition=False,
            confidence=0.4
        )

    # Truncate very long input to prevent performance issues
    max_length = 10000
    if len(request) > max_length:
        logger.warning(f"Request truncated from {len(request)} to {max_length} characters")
        request = request[:max_length]

    # Step 1: Detect keywords
    keyword_matches = detect_keywords(request, config["keyword_sets"])

    # Step 2: Detect anti-patterns
    anti_patterns = detect_anti_patterns(request, config["anti_patterns"])

    # Combine indicators
    indicators = {
        "keyword_matches": keyword_matches,
        "anti_patterns": anti_patterns
    }

    # Step 3: Estimate effort
    effort = estimate_effort(indicators)

    # Step 4: Calculate confidence
    confidence = calculate_confidence(indicators)

    # Step 5: Determine if decomposition needed
    threshold = config.get("decomposition_threshold", "M")
    threshold_enum = EffortSize[threshold] if threshold in ["XS", "S", "M", "L", "XL"] else EffortSize.M

    # Map enum to ordinal for comparison
    effort_order = {"xs": 0, "s": 1, "m": 2, "l": 3, "xl": 4}
    effort_value = effort_order[effort.value]
    threshold_value = effort_order[threshold_enum.value]

    # Decompose if effort >= threshold OR anti-patterns trigger
    needs_decomposition = effort_value >= threshold_value

    # Anti-pattern override: excessive conjunctions always trigger decomposition
    if anti_patterns.get("conjunction_count", 0) >= 3:
        needs_decomposition = True

    return ComplexityAnalysis(
        effort=effort,
        indicators=indicators,
        needs_decomposition=needs_decomposition,
        confidence=confidence
    )


def estimate_atomic_count(request: str, complexity: ComplexityAnalysis, config: Optional[Dict] = None) -> int:
    """Estimate number of atomic sub-issues needed.

    Returns:
    - 1 for simple requests (XS/S) that don't need decomposition
    - 2-5 for complex requests based on effort size
    - Respects max_atomic_issues configuration limit

    Args:
        request: Original feature request
        complexity: ComplexityAnalysis result
        config: Optional configuration dictionary

    Returns:
        Estimated number of atomic sub-issues (1-5)

    Examples:
        >>> analysis = analyze_complexity("Add feature")
        >>> estimate_atomic_count("Add feature", analysis)
        1
    """
    if config is None:
        config = DEFAULT_CONFIG

    max_issues = config.get("max_atomic_issues", 5)

    # Simple requests don't need decomposition
    if not complexity.needs_decomposition:
        return 1

    # Map effort size to sub-issue count
    effort_to_count = {
        EffortSize.XS: 1,
        EffortSize.S: 1,
        EffortSize.M: 3,
        EffortSize.L: 4,
        EffortSize.XL: 5
    }

    base_count = effort_to_count.get(complexity.effort, 3)

    # Cap at max_atomic_issues
    return min(base_count, max_issues)


def generate_decomposition_prompt(request: str, count: int) -> str:
    """Generate prompt for decomposing request into atomic sub-issues.

    Creates a structured prompt that:
    - Preserves original request context
    - Specifies target number of sub-issues
    - Provides decomposition guidance

    Args:
        request: Original feature request
        count: Target number of atomic sub-issues

    Returns:
        Formatted decomposition prompt

    Examples:
        >>> prompt = generate_decomposition_prompt("Implement auth", 3)
        >>> "atomic" in prompt.lower()
        True
    """
    prompt = f"""The following feature request requires decomposition into {count} atomic sub-issues:

**Original Request:**
{request}

**Instructions:**
Break this down into {count} atomic, independently implementable sub-issues. Each sub-issue should:
- Be small enough to complete in 1-4 hours
- Have clear acceptance criteria
- Be testable independently
- Minimize dependencies on other sub-issues

**Output Format:**
For each sub-issue, provide:
1. Title (concise, actionable)
2. Description (what needs to be done)
3. Acceptance criteria (how to verify completion)
4. Estimated effort (XS/S/M)

Generate the {count} atomic sub-issues now.
"""
    return prompt
