#!/usr/bin/env python3
"""Issue Scope Detector - Detect broad issue scope for granularity enforcement.

This module detects when GitHub issues cover too much scope (multiple providers,
components, or features) and should be split into smaller, focused issues.

Philosophy: One issue = one implementation session (< 30 min)

Classes:
    ScopeLevel: Scope categories (FOCUSED/BROAD/VERY_BROAD)
    ScopeDetection: Results of scope detection with reasoning and suggestions

Functions:
    IssueScopeDetector.detect: Main entry point for scope detection
    IssueScopeDetector._detect_multiple_providers: Detect multiple providers
    IssueScopeDetector._detect_multiple_components: Detect multiple components
    IssueScopeDetector._detect_multiple_features: Detect multiple features
    IssueScopeDetector._detect_broad_patterns: Detect broad patterns like "all", "every"
    IssueScopeDetector.suggest_splits: Suggest how to split broad issues

Security:
    - Input validation for all user-provided text
    - Graceful degradation for invalid inputs
    - No external dependencies on network resources

Usage:
    from issue_scope_detector import IssueScopeDetector, ScopeLevel

    detector = IssueScopeDetector()
    result = detector.detect("Replace mock log streaming with real SSH/API implementation")

    if result.level != ScopeLevel.FOCUSED:
        print(f"Scope: {result.level}")
        print(f"Reasoning: {result.reasoning}")
        for split in result.suggested_splits:
            print(f"  - {split}")

Related:
    - complexity_assessor.py: Similar pattern for complexity detection
    - validation.py: Input validation patterns

Relevant Skills:
    - error-handling-patterns: Graceful degradation for invalid inputs
    - library-design-patterns: Stateless design with class methods
"""

from enum import Enum
from typing import NamedTuple, List, Dict, Any, Optional
import re
import os
import sys
import logging
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# GenAI imports (graceful degradation if unavailable)
# ============================================================================

# Add hooks directory to path so genai_utils and genai_prompts are importable.
# This is the canonical location for these utilities in the autonomous-dev plugin.
_hooks_path = Path(__file__).parent.parent / "hooks"
if _hooks_path.exists() and str(_hooks_path) not in sys.path:
    sys.path.insert(0, str(_hooks_path))

try:
    from genai_utils import GenAIAnalyzer, parse_classification_response, should_use_genai
    from genai_prompts import SCOPE_ASSESSMENT_PROMPT
    _GENAI_AVAILABLE = True
except ImportError:
    # GenAI utilities unavailable (anthropic SDK not installed, or hooks not on path).
    # Scope detection falls back to pattern heuristics transparently.
    _GENAI_AVAILABLE = False
    GenAIAnalyzer = None  # type: ignore[assignment]
    parse_classification_response = None  # type: ignore[assignment]
    should_use_genai = None  # type: ignore[assignment]
    SCOPE_ASSESSMENT_PROMPT = ""  # type: ignore[assignment]


# ============================================================================
# Enums and Data Classes
# ============================================================================

class ScopeLevel(Enum):
    """Scope categories for issue granularity.

    Values:
        FOCUSED: Single provider/component/feature - ready to implement
        BROAD: Multiple providers/components/features - should be split
        VERY_BROAD: Many providers/components or broad patterns - must be split
    """
    FOCUSED = "focused"
    BROAD = "broad"
    VERY_BROAD = "very_broad"


class ScopeDetection(NamedTuple):
    """Results of scope detection for an issue.

    Attributes:
        level: Detected scope level (FOCUSED/BROAD/VERY_BROAD)
        reasoning: Human-readable explanation of why it's broad
        indicators: Dict of detected indicators (providers, components, etc.)
        suggested_splits: List of suggested issue titles if scope is broad
        should_warn: Whether to warn the user before creating
    """
    level: ScopeLevel
    reasoning: str
    indicators: Dict[str, Any]
    suggested_splits: List[str]
    should_warn: bool


# ============================================================================
# Main Detector Class
# ============================================================================

class IssueScopeDetector:
    """Stateless scope detector for issue granularity enforcement.

    This class provides scope detection for GitHub issues to enforce
    granularity requirements (one issue = one session < 30 min).

    Design:
        - Stateless: No instance variables, all methods can be class methods
        - Pattern-based: Fast heuristics for common patterns
        - Conservative: Flags potential issues, user makes final decision
        - Actionable: Provides split suggestions when scope is broad

    Usage:
        detector = IssueScopeDetector()
        result = detector.detect("Wire orchestration to real provider APIs")
        if result.should_warn:
            print(f"Warning: {result.reasoning}")
    """

    # Provider patterns (cloud providers, services, tools)
    PROVIDER_PATTERNS = {
        "aws lambda", "lambda", "runpod", "modal", "vast.ai", "vastai",
        "paperspace", "together.ai", "togetherai", "replicate",
        "openai", "anthropic", "huggingface", "hf",
        "github", "gitlab", "bitbucket",
        "docker", "kubernetes", "k8s",
        "postgres", "mysql", "mongodb", "redis",
        "ssh", "sftp", "http", "https", "api", "rest", "graphql"
    }

    # Component patterns (system parts, modules)
    COMPONENT_PATTERNS = {
        "log streaming", "logging", "result download", "results",
        "authentication", "auth", "authorization",
        "database", "cache", "storage", "filesystem",
        "ui", "frontend", "backend", "api",
        "orchestration", "scheduler", "queue", "worker",
        "monitoring", "metrics", "alerting", "notifications",
        "config", "configuration", "settings"
    }

    # Feature patterns (functionality)
    FEATURE_PATTERNS = {
        "add", "implement", "create", "build",
        "update", "modify", "change", "refactor",
        "fix", "resolve", "debug",
        "remove", "delete", "deprecate",
        "integrate", "wire", "connect", "link"
    }

    # Broad patterns (keywords indicating wide scope)
    BROAD_KEYWORDS = {
        "all", "every", "complete", "full", "entire", "whole",
        "comprehensive", "end-to-end", "e2e",
        "multiple", "various", "several",
        "system-wide", "global", "across"
    }

    # Conjunction patterns (indicate multiple items)
    CONJUNCTION_PATTERN = r'\b(and|or|plus|\+|,)\b'

    @classmethod
    def _detect_genai(cls, text: str) -> "Optional[ScopeDetection]":
        """Attempt GenAI-based scope detection.

        Uses Claude Haiku (via GenAIAnalyzer) to semantically classify scope as
        FOCUSED/BROAD/VERY_BROAD. Returns None to signal that the heuristic
        path should run instead.

        This method never raises exceptions - all failures result in None (fallback).

        Args:
            text: Issue text (capped at 2000 chars internally)

        Returns:
            ScopeDetection if GenAI succeeds, None to trigger heuristic fallback

        Example:
            >>> result = IssueScopeDetector._detect_genai("Add rate limiting and timeout")
            >>> if result is None:
            ...     # GenAI unavailable or disabled, use heuristic
            ...     pass
        """
        # Check module-level availability flag (set at import time)
        if not _GENAI_AVAILABLE:
            return None

        # Check feature flag env var (default: enabled)
        flag_value = os.environ.get("GENAI_SCOPE", "true").lower()
        if flag_value == "false":
            return None

        try:
            # Cap text length to avoid large API requests
            capped_text = text[:2000] if len(text) > 2000 else text

            # Initialize analyzer with Haiku-optimized settings
            analyzer = GenAIAnalyzer(max_tokens=150, timeout=5)

            # Call GenAI with the scope assessment prompt
            response = analyzer.analyze(
                SCOPE_ASSESSMENT_PROMPT,
                issue_text=capped_text,
            )

            if response is None:
                return None

            # Parse the classification response
            label = parse_classification_response(response, ["FOCUSED", "BROAD", "VERY_BROAD"])
            if label is None:
                return None

            # Map label to ScopeLevel
            level_map = {
                "FOCUSED": ScopeLevel.FOCUSED,
                "BROAD": ScopeLevel.BROAD,
                "VERY_BROAD": ScopeLevel.VERY_BROAD,
            }
            level = level_map[label]

            # GenAI classifications use fixed high confidence and clear reasoning
            reasoning = f"GenAI classification: {label} (Haiku semantic analysis)"

            return cls._create_detection(
                level=level,
                reasoning=reasoning,
                indicators={"genai_scope": label},
                suggested_splits=[],
            )

        except Exception as exc:
            logger.debug("GenAI scope detection failed, using heuristic: %s", exc)
            return None

    @classmethod
    def detect(
        cls,
        issue_title: str,
        issue_body: str = "",
        github_issue: Optional[Dict[str, Any]] = None
    ) -> ScopeDetection:
        """Detect scope level of an issue.

        This is the main entry point for scope detection. It analyzes
        the issue title and body to determine if the scope is too broad.

        Args:
            issue_title: Issue title to analyze
            issue_body: Optional issue body for additional context
            github_issue: Optional GitHub issue dict with 'title' and 'body' keys

        Returns:
            ScopeDetection with level, reasoning, indicators, and suggested splits

        Example:
            >>> detector = IssueScopeDetector()
            >>> result = detector.detect("Replace mock log streaming with real SSH/API implementation")
            >>> print(result.level)
            ScopeLevel.BROAD
            >>> print(result.reasoning)
            Detected multiple components (log streaming, ssh, api) - should split into focused issues
        """
        # Handle GitHub issue dict
        if github_issue:
            issue_title = github_issue.get("title", issue_title)
            issue_body = github_issue.get("body", issue_body)

        # Handle edge cases
        if not issue_title or not issue_title.strip():
            return cls._create_detection(
                level=ScopeLevel.FOCUSED,
                reasoning="Empty title - cannot assess scope",
                indicators={},
                suggested_splits=[]
            )

        # Truncate very long input (>10000 chars) with warning
        combined_text = f"{issue_title} {issue_body}"
        if len(combined_text) > 10000:
            logger.warning(f"Issue text exceeds 10000 chars ({len(combined_text)}), truncating")
            combined_text = combined_text[:10000]

        # Try GenAI-first classification (semantic understanding beats keyword matching)
        genai_result = cls._detect_genai(combined_text)
        if genai_result is not None:
            # For broad/very_broad results, generate split suggestions using heuristics
            if genai_result.level in (ScopeLevel.BROAD, ScopeLevel.VERY_BROAD):
                providers = cls._detect_multiple_providers(combined_text)
                components = cls._detect_multiple_components(combined_text)
                features = cls._detect_multiple_features(combined_text)
                heuristic_indicators = {
                    "providers": providers,
                    "components": components,
                    "features": features,
                    "broad_patterns": [],
                    "conjunction_count": cls._count_conjunctions(combined_text),
                }
                suggested_splits = cls.suggest_splits(issue_title, heuristic_indicators)
                return cls._create_detection(
                    level=genai_result.level,
                    reasoning=genai_result.reasoning,
                    indicators={**genai_result.indicators, **heuristic_indicators},
                    suggested_splits=suggested_splits,
                )
            return genai_result

        # Perform analysis
        providers = cls._detect_multiple_providers(combined_text)
        components = cls._detect_multiple_components(combined_text)
        features = cls._detect_multiple_features(combined_text)
        broad_patterns = cls._detect_broad_patterns(combined_text)
        conjunctions = cls._count_conjunctions(combined_text)

        # Combine indicators
        indicators = {
            "providers": providers,
            "components": components,
            "features": features,
            "broad_patterns": broad_patterns,
            "conjunction_count": conjunctions
        }

        # Determine scope level
        level = cls._determine_level(indicators)

        # Generate reasoning
        reasoning = cls._generate_reasoning(level, indicators)

        # Generate split suggestions if broad
        suggested_splits = []
        if level in [ScopeLevel.BROAD, ScopeLevel.VERY_BROAD]:
            suggested_splits = cls.suggest_splits(issue_title, indicators)

        return cls._create_detection(level, reasoning, indicators, suggested_splits)

    @classmethod
    def _detect_multiple_providers(cls, text: str) -> List[str]:
        """Detect multiple providers mentioned in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected provider names (deduplicated)
        """
        text_lower = text.lower()
        detected_set = set()

        for provider in cls.PROVIDER_PATTERNS:
            if provider in text_lower:
                detected_set.add(provider)

        # Deduplicate overlapping patterns (e.g., "aws lambda" and "lambda")
        # Keep longer patterns, remove substrings
        detected = list(detected_set)
        filtered = []

        for provider in detected:
            # Check if this provider is a substring of any other provider
            is_substring = False
            for other in detected:
                if provider != other and provider in other:
                    is_substring = True
                    break

            if not is_substring:
                filtered.append(provider)

        return filtered

    @classmethod
    def _detect_multiple_components(cls, text: str) -> List[str]:
        """Detect multiple components mentioned in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected component names (deduplicated)
        """
        text_lower = text.lower()
        detected_set = set()

        for component in cls.COMPONENT_PATTERNS:
            if component in text_lower:
                detected_set.add(component)

        # Deduplicate overlapping patterns (e.g., "auth", "authentication", "authorization")
        # Keep longer patterns, remove substrings
        detected = list(detected_set)
        filtered = []

        for component in detected:
            # Check if this component is a substring of any other component
            is_substring = False
            for other in detected:
                if component != other and component in other:
                    is_substring = True
                    break

            if not is_substring:
                filtered.append(component)

        return filtered

    @classmethod
    def _detect_multiple_features(cls, text: str) -> List[str]:
        """Detect multiple features mentioned in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected feature actions
        """
        text_lower = text.lower()
        detected = []

        for feature in cls.FEATURE_PATTERNS:
            # Look for feature as a word boundary (not substring)
            pattern = r'\b' + re.escape(feature) + r'\b'
            if re.search(pattern, text_lower):
                detected.append(feature)

        return detected

    @classmethod
    def _detect_broad_patterns(cls, text: str) -> List[str]:
        """Detect broad patterns like "all", "every", "complete".

        Args:
            text: Text to analyze

        Returns:
            List of detected broad keywords
        """
        text_lower = text.lower()
        detected = []

        for keyword in cls.BROAD_KEYWORDS:
            # Look for keyword as a word boundary
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                detected.append(keyword)

        return detected

    @classmethod
    def _count_conjunctions(cls, text: str) -> int:
        """Count conjunctions in text (indicates lists).

        Args:
            text: Text to analyze

        Returns:
            Count of conjunctions
        """
        conjunctions = re.findall(cls.CONJUNCTION_PATTERN, text.lower())
        return len(conjunctions)

    @classmethod
    def _determine_level(cls, indicators: Dict[str, Any]) -> ScopeLevel:
        """Determine scope level from indicators.

        Priority:
            1. VERY_BROAD: 3+ providers OR 4+ components OR broad patterns + multiple items
            2. BROAD: 2+ providers OR 3+ components OR 2+ features with conjunctions OR broad patterns alone
            3. FOCUSED: Single provider/component/feature

        Args:
            indicators: Combined analysis results

        Returns:
            ScopeLevel (FOCUSED/BROAD/VERY_BROAD)
        """
        providers = indicators["providers"]
        components = indicators["components"]
        features = indicators["features"]
        broad_patterns = indicators["broad_patterns"]
        conjunctions = indicators["conjunction_count"]

        # VERY_BROAD: Many items or broad patterns with multiple items
        if len(providers) >= 3:
            return ScopeLevel.VERY_BROAD
        if len(components) >= 4:
            return ScopeLevel.VERY_BROAD
        if broad_patterns and (len(providers) >= 2 or len(components) >= 2):
            return ScopeLevel.VERY_BROAD

        # BROAD: Multiple items or broad patterns alone
        if len(providers) >= 2:
            return ScopeLevel.BROAD
        if len(components) >= 3:
            return ScopeLevel.BROAD
        if len(features) >= 2 and conjunctions >= 2:
            return ScopeLevel.BROAD
        # Broad patterns alone (e.g., "all providers", "complete system")
        if broad_patterns:
            return ScopeLevel.BROAD

        # FOCUSED: Default
        return ScopeLevel.FOCUSED

    @classmethod
    def _generate_reasoning(
        cls,
        level: ScopeLevel,
        indicators: Dict[str, Any]
    ) -> str:
        """Generate human-readable reasoning for detection.

        Args:
            level: Determined scope level
            indicators: Combined analysis results

        Returns:
            Reasoning string explaining the classification
        """
        if level == ScopeLevel.FOCUSED:
            return "Focused on a single provider/component/feature - ready to implement"

        parts = []
        providers = indicators["providers"]
        components = indicators["components"]
        features = indicators["features"]
        broad_patterns = indicators["broad_patterns"]

        if broad_patterns:
            parts.append(f"broad patterns detected ({', '.join(broad_patterns[:3])})")

        if len(providers) >= 2:
            parts.append(f"multiple providers ({', '.join(providers[:3])})")

        if len(components) >= 3:
            parts.append(f"multiple components ({', '.join(components[:3])})")

        if len(features) >= 2:
            parts.append(f"multiple features ({', '.join(features[:3])})")

        if level == ScopeLevel.VERY_BROAD:
            prefix = "Detected "
            suffix = " - must split into focused issues (< 30 min each)"
        else:
            prefix = "Detected "
            suffix = " - should split into focused issues (< 30 min each)"

        return prefix + " and ".join(parts) + suffix

    @classmethod
    def suggest_splits(
        cls,
        _issue_title: str,  # Kept for API compatibility, may be used in future
        indicators: Dict[str, Any]
    ) -> List[str]:
        """Suggest how to split a broad issue into focused issues.

        Args:
            _issue_title: Original issue title (reserved for future use)
            indicators: Detection indicators

        Returns:
            List of suggested issue titles
        """
        suggestions = []
        providers = indicators["providers"]
        components = indicators["components"]
        features = indicators["features"]

        # If multiple providers, suggest splitting by provider
        if len(providers) >= 2:
            for provider in providers[:3]:  # Limit to first 3
                suggestions.append(f"Implement {provider} integration")

        # If multiple components, suggest splitting by component
        elif len(components) >= 3:
            for component in components[:3]:
                suggestions.append(f"Implement {component}")

        # If multiple features, suggest splitting by feature
        elif len(features) >= 2:
            for feature in features[:3]:
                suggestions.append(f"{feature.capitalize()} [specific component]")

        # Generic fallback
        if not suggestions:
            suggestions = [
                "Issue 1: [First component/feature]",
                "Issue 2: [Second component/feature]",
                "Issue 3: [Third component/feature]"
            ]

        return suggestions

    @classmethod
    def _create_detection(
        cls,
        level: ScopeLevel,
        reasoning: str,
        indicators: Dict[str, Any],
        suggested_splits: List[str]
    ) -> ScopeDetection:
        """Create ScopeDetection with all fields.

        Args:
            level: Scope level
            reasoning: Reasoning string
            indicators: Detection indicators
            suggested_splits: Suggested issue titles

        Returns:
            ScopeDetection with all fields populated
        """
        should_warn = level in [ScopeLevel.BROAD, ScopeLevel.VERY_BROAD]

        return ScopeDetection(
            level=level,
            reasoning=reasoning,
            indicators=indicators,
            suggested_splits=suggested_splits,
            should_warn=should_warn
        )
