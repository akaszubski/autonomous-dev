"""Automatic complexity assessment for pipeline scaling.

This module assesses feature complexity to determine optimal agent pipeline scaling.
It performs keyword-based classification, scope detection, and security indicator
analysis to recommend appropriate agent counts and time estimates.

Classes:
    ComplexityLevel: Complexity categories (SIMPLE/STANDARD/COMPLEX)
    ComplexityAssessment: Results of complexity assessment with agent/time estimates

Functions:
    ComplexityAssessor.assess: Main entry point for complexity assessment
    ComplexityAssessor._analyze_keywords: Keyword-based classification
    ComplexityAssessor._analyze_scope: Scope detection analysis
    ComplexityAssessor._analyze_security: Security indicator detection
    ComplexityAssessor._calculate_confidence: Confidence scoring (0.0-1.0)

Security:
    - Input validation for all user-provided text
    - Graceful degradation for invalid inputs
    - No external dependencies on network resources

Related:
    - GitHub Issue #181: Automatic complexity assessment for pipeline scaling

Relevant Skills:
    - error-handling-patterns: Graceful degradation for invalid inputs
    - library-design-patterns: Stateless design with class methods
"""

from enum import Enum
from typing import NamedTuple, Optional, Dict, Any, List
import re
import logging

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class ComplexityLevel(Enum):
    """Complexity categories for feature estimation.

    Values:
        SIMPLE: Simple changes (typos, docs, formatting) - 3 agents, ~8 min
        STANDARD: Standard features (bug fixes, small features) - 6 agents, ~15 min
        COMPLEX: Complex features (auth, security, APIs) - 8 agents, ~25 min
    """
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"


class ComplexityAssessment(NamedTuple):
    """Results of complexity assessment for a feature request.

    Attributes:
        level: Assessed complexity level (SIMPLE/STANDARD/COMPLEX)
        confidence: Confidence score for assessment (0.0-1.0)
        reasoning: Human-readable explanation of classification
        agent_count: Recommended number of agents (3/6/8)
        estimated_time: Estimated time in minutes (8/15/25)
    """
    level: ComplexityLevel
    confidence: float
    reasoning: str
    agent_count: int
    estimated_time: int


# ============================================================================
# Main Assessor Class
# ============================================================================

class ComplexityAssessor:
    """Stateless complexity assessor using keyword-based heuristics.

    This class provides complexity assessment for feature requests to determine
    optimal pipeline scaling (agent count and time estimates).

    Design:
        - Stateless: No instance variables, all methods can be class methods
        - Keyword-based: Fast heuristics for common patterns
        - Conservative: Defaults to STANDARD when uncertain
        - Security-first: COMPLEX keywords override SIMPLE keywords

    Usage:
        assessor = ComplexityAssessor()
        result = assessor.assess("Fix typo in README")
        print(f"Level: {result.level}, Agents: {result.agent_count}")
    """

    # Keyword sets for classification (lowercase for case-insensitive matching)
    SIMPLE_KEYWORDS = {
        "typo", "spelling", "docs", "documentation", "readme",
        "rename", "format", "formatting", "comment", "whitespace",
        "indentation", "style", "lint", "pep8", "black"
    }

    COMPLEX_KEYWORDS = {
        "auth", "authentication", "authorization", "security", "encrypt",
        "encryption", "jwt", "oauth", "oauth2", "saml", "ldap",
        "password", "credential", "token", "api", "webhook",
        "database", "migration", "schema"
    }

    # Agent count and time mapping
    AGENT_MAPPING = {
        ComplexityLevel.SIMPLE: {"agent_count": 3, "estimated_time": 8},
        ComplexityLevel.STANDARD: {"agent_count": 6, "estimated_time": 15},
        ComplexityLevel.COMPLEX: {"agent_count": 8, "estimated_time": 25},
    }

    @classmethod
    def assess(
        cls,
        feature_description: str,
        github_issue: Optional[Dict[str, Any]] = None,
        issue: Optional[Dict[str, Any]] = None
    ) -> ComplexityAssessment:
        """Assess complexity of a feature request.

        This is the main entry point for complexity assessment. It analyzes
        the feature description (and optional GitHub issue) to determine
        complexity level, agent count, and time estimates.

        Args:
            feature_description: Feature request text to analyze
            github_issue: Optional GitHub issue dict with 'title' and 'body' keys
            issue: Alias for github_issue parameter (for backward compatibility)

        Returns:
            ComplexityAssessment with level, confidence, reasoning, agent_count, time

        Example:
            >>> assessor = ComplexityAssessor()
            >>> result = assessor.assess("Fix typo in README")
            >>> print(result.level)
            ComplexityLevel.SIMPLE
        """
        # Support both github_issue and issue parameter names (issue is alias)
        if issue is not None and github_issue is None:
            github_issue = issue
        # Handle edge cases
        if feature_description is None:
            return cls._create_assessment(
                level=ComplexityLevel.STANDARD,
                confidence=0.4,
                reasoning="No input provided (None) - defaulting to STANDARD complexity"
            )

        if not feature_description or not feature_description.strip():
            return cls._create_assessment(
                level=ComplexityLevel.STANDARD,
                confidence=0.4,
                reasoning="Empty or whitespace-only input - defaulting to STANDARD complexity"
            )

        # Truncate very long input (>10000 chars) with warning
        if len(feature_description) > 10000:
            logger.warning(f"Feature description exceeds 10000 chars ({len(feature_description)}), truncating")
            feature_description = feature_description[:10000]

        # Combine feature description with GitHub issue if provided
        combined_text = feature_description
        if github_issue:
            title = github_issue.get("title", "")
            body = github_issue.get("body", "")

            # Weight body higher than title
            if body:
                combined_text = f"{title} {body} {body}"  # Duplicate body for higher weight
            elif title:
                combined_text = f"{title} {feature_description}"

        # Perform analysis
        keyword_analysis = cls._analyze_keywords(combined_text)
        scope_analysis = cls._analyze_scope(combined_text)
        security_analysis = cls._analyze_security(combined_text)

        # Combine indicators
        indicators = {
            "keywords": keyword_analysis,
            "scope": scope_analysis,
            "security": security_analysis
        }

        # Determine complexity level
        level = cls._determine_level(indicators)

        # Calculate confidence
        confidence = cls._calculate_confidence(indicators)

        # Generate reasoning
        reasoning = cls._generate_reasoning(level, indicators, confidence)

        return cls._create_assessment(level, confidence, reasoning)

    @classmethod
    def _analyze_keywords(cls, text: str) -> Dict[str, Any]:
        """Analyze text for SIMPLE and COMPLEX keyword indicators.

        Args:
            text: Text to analyze

        Returns:
            Dict with 'simple_count', 'complex_count', 'simple_keywords', 'complex_keywords'
        """
        text_lower = text.lower()

        # Count SIMPLE keywords
        simple_keywords = [kw for kw in cls.SIMPLE_KEYWORDS if kw in text_lower]
        simple_count = len(simple_keywords)

        # Count COMPLEX keywords
        complex_keywords = [kw for kw in cls.COMPLEX_KEYWORDS if kw in text_lower]
        complex_count = len(complex_keywords)

        return {
            "simple_count": simple_count,
            "complex_count": complex_count,
            "simple_keywords": simple_keywords,
            "complex_keywords": complex_keywords
        }

    @classmethod
    def _analyze_scope(cls, text: str) -> Dict[str, Any]:
        """Analyze text for scope indicators (file counts, conjunctions).

        Args:
            text: Text to analyze

        Returns:
            Dict with 'conjunction_count', 'file_type_count', 'word_count', 'alphabetic_count'
        """
        # Count conjunctions (and, or, also, plus, additionally)
        conjunction_pattern = r'\b(and|or|also|plus|additionally)\b'
        conjunctions = re.findall(conjunction_pattern, text.lower())
        conjunction_count = len(conjunctions)

        # Count file type mentions (.py, .js, .md, etc.)
        file_type_pattern = r'\.\w{2,4}\b'
        file_types = re.findall(file_type_pattern, text)
        file_type_count = len(set(file_types))  # Unique file types

        # Word count as rough scope indicator
        word_count = len(text.split())

        # Count words with alphabetic characters (not just symbols)
        alphabetic_words = [w for w in text.split() if any(c.isalpha() for c in w)]
        alphabetic_count = len(alphabetic_words)

        return {
            "conjunction_count": conjunction_count,
            "file_type_count": file_type_count,
            "word_count": word_count,
            "alphabetic_count": alphabetic_count
        }

    @classmethod
    def _analyze_security(cls, text: str) -> Dict[str, Any]:
        """Analyze text for security-related indicators.

        Args:
            text: Text to analyze

        Returns:
            Dict with 'has_security_keywords' and 'security_keyword_list'
        """
        text_lower = text.lower()

        # Security-specific keywords (subset of COMPLEX_KEYWORDS)
        security_keywords = {
            "auth", "authentication", "authorization", "security",
            "encrypt", "encryption", "jwt", "oauth", "oauth2",
            "saml", "password", "credential", "token"
        }

        found_keywords = [kw for kw in security_keywords if kw in text_lower]

        return {
            "has_security_keywords": len(found_keywords) > 0,
            "security_keyword_list": found_keywords
        }

    @classmethod
    def _determine_level(cls, indicators: Dict[str, Any]) -> ComplexityLevel:
        """Determine complexity level from indicators.

        Priority:
            1. COMPLEX keywords override SIMPLE keywords (security priority)
            2. SIMPLE keywords with no conflicts
            3. STANDARD as default fallback

        Args:
            indicators: Combined analysis results

        Returns:
            ComplexityLevel (SIMPLE/STANDARD/COMPLEX)
        """
        keyword_analysis = indicators["keywords"]
        simple_count = keyword_analysis["simple_count"]
        complex_count = keyword_analysis["complex_count"]

        # COMPLEX has priority (security-first approach)
        if complex_count > 0:
            return ComplexityLevel.COMPLEX

        # SIMPLE only if no conflicting signals
        if simple_count > 0:
            return ComplexityLevel.SIMPLE

        # Default to STANDARD
        return ComplexityLevel.STANDARD

    @classmethod
    def _calculate_confidence(cls, indicators: Dict[str, Any]) -> float:
        """Calculate confidence score (0.0-1.0) for assessment.

        Confidence factors:
            - Single keyword match: 0.85 base
            - Multiple keyword matches: +0.05 per additional
            - Conflicting signals: -0.3 penalty
            - No keywords but detailed: 0.6 (reasonable default to STANDARD)
            - No keywords and vague/garbage: 0.4-0.5 (very ambiguous)

        Args:
            indicators: Combined analysis results

        Returns:
            Confidence score between 0.0 and 1.0
        """
        keyword_analysis = indicators["keywords"]
        scope_analysis = indicators["scope"]
        simple_count = keyword_analysis["simple_count"]
        complex_count = keyword_analysis["complex_count"]
        word_count = scope_analysis["word_count"]
        alphabetic_count = scope_analysis["alphabetic_count"]

        # Start with base confidence
        if simple_count == 0 and complex_count == 0:
            # No keywords detected - check if request is detailed enough
            # Check for garbage input (mostly symbols, no real words)
            if alphabetic_count == 0:
                return 0.4  # Garbage input
            elif word_count < 5:
                return 0.5  # Very ambiguous/short
            else:
                return 0.6  # Moderate confidence for detailed requests

        # Base confidence for any keyword match
        confidence = 0.85

        # Bonus for multiple keywords (stronger signal)
        total_keywords = simple_count + complex_count
        if total_keywords >= 2:
            confidence += 0.05
        if total_keywords >= 3:
            confidence += 0.05

        # Penalty for conflicting signals
        if simple_count > 0 and complex_count > 0:
            confidence -= 0.30

        # Ensure confidence is in valid range [0.0, 1.0]
        confidence = max(0.0, min(1.0, confidence))

        return confidence

    @classmethod
    def _generate_reasoning(
        cls,
        level: ComplexityLevel,
        indicators: Dict[str, Any],
        confidence: float
    ) -> str:
        """Generate human-readable reasoning for assessment.

        Args:
            level: Determined complexity level
            indicators: Combined analysis results
            confidence: Calculated confidence score

        Returns:
            Reasoning string explaining the classification
        """
        keyword_analysis = indicators["keywords"]
        simple_keywords = keyword_analysis["simple_keywords"]
        complex_keywords = keyword_analysis["complex_keywords"]

        parts = []

        # Lead with classification
        parts.append(f"Classified as {level.value.upper()}")

        # Explain keyword matches
        if complex_keywords:
            parts.append(f"detected COMPLEX keywords: {', '.join(complex_keywords[:3])}")
        elif simple_keywords:
            parts.append(f"detected SIMPLE keywords: {', '.join(simple_keywords[:3])}")
        else:
            parts.append("no strong keyword matches, using default")

        # Mention confidence
        if confidence >= 0.85:
            parts.append("high confidence")
        elif confidence >= 0.6:
            parts.append("medium confidence")
        else:
            parts.append("low confidence")

        # Warn about conflicts
        if simple_keywords and complex_keywords:
            parts.append("(conflicting signals detected, COMPLEX takes priority)")

        return " - ".join(parts)

    @classmethod
    def _create_assessment(
        cls,
        level: ComplexityLevel,
        confidence: float,
        reasoning: str
    ) -> ComplexityAssessment:
        """Create ComplexityAssessment with agent count and time estimates.

        Args:
            level: Complexity level
            confidence: Confidence score
            reasoning: Reasoning string

        Returns:
            ComplexityAssessment with all fields populated
        """
        mapping = cls.AGENT_MAPPING[level]

        return ComplexityAssessment(
            level=level,
            confidence=confidence,
            reasoning=reasoning,
            agent_count=mapping["agent_count"],
            estimated_time=mapping["estimated_time"]
        )
