#!/usr/bin/env python3
"""
GenAI Utilities for Claude Code Hooks

This module provides reusable utilities for GenAI analysis across all hooks.
Centralizing SDK handling, error management, and common patterns enables:
- Consistent SDK initialization and error handling
- Graceful degradation if SDK unavailable
- Unified timeout and configuration management
- Reduced code duplication (70% less code per hook)
- Easy to test SDK integration independently

Core class: GenAIAnalyzer
- Handles Anthropic SDK instantiation
- Manages fallback chains (SDK → heuristics)
- Implements timeout and error handling
- Provides logging for debugging
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import html
import os
import sys
from typing import Optional
from genai_prompts import DEFAULT_MODEL, DEFAULT_MAX_TOKENS, DEFAULT_TIMEOUT


def _wrap_user_input(text: str) -> str:
    """Wrap user-supplied text in XML delimiters with HTML escaping.

    Defends against prompt-injection attacks where user input contains
    structural tokens like ``</user_input>`` or ``<system>`` that could
    escape a delimited prompt context.

    Uses ``html.escape(text, quote=False)`` per OWASP XML escape guidance:
    - Escapes structurally dangerous chars: ``&``, ``<``, ``>``.
    - Preserves apostrophes (``'``) and double-quotes (``"``) which are
      common in legitimate prompts (e.g., ``"it's working"`` should not
      become ``"it&#x27;s working"``).

    Issue #960 Phase 2 (security-deferred from intent classifier Phase 1).
    Currently used by ``intent_classifier.py``; can be adopted by other
    ``analyzer.analyze()`` callers via follow-up issues.

    Args:
        text: User-controlled input text to wrap.

    Returns:
        ``f"<user_input>\\n{escaped_text}\\n</user_input>"``.
    """
    return f"<user_input>\n{html.escape(text, quote=False)}\n</user_input>"


def _safe_wrap(text: str) -> str:
    """Best-effort wrap of user-controlled text. Returns text unchanged on any failure.

    Issue #1007 Phase 3: simplifies adoption across ``analyzer.analyze()`` callers.
    Callers should use this rather than direct ``_wrap_user_input`` to avoid
    try/except boilerplate at every call site.

    The helper applies the same delimiter+HTML-escape defense as
    ``_wrap_user_input`` (see Phase 2, Issue #960) but is structurally
    guaranteed never to raise:

    - On any exception, returns the input string unchanged.
    - For non-string input, coerces with ``str()`` and returns that.

    This makes adoption a one-line replacement at every caller — wrap the
    repo-content kwarg in ``_safe_wrap(...)`` and the caller's prompt-injection
    posture matches the intent classifier's Phase 2 baseline.

    Args:
        text: User-controlled input text to wrap.

    Returns:
        Wrapped string on success; coerced ``str`` on failure (NEVER raises).
    """
    try:
        return _wrap_user_input(text)
    except Exception:
        return text if isinstance(text, str) else str(text)


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ
# Fallback for non-UV environments (placeholder - this hook doesn't use lib imports)
if not is_running_under_uv():
    # This hook doesn't import from autonomous-dev/lib
    # But we keep sys.path.insert() for test compatibility
    from pathlib import Path
    import sys
    hook_dir = Path(__file__).parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))


class GenAIAnalyzer:
    """Reusable GenAI analysis engine for hooks.

    Handles:
    - Anthropic SDK initialization
    - API error handling and retries
    - Graceful fallback if SDK unavailable
    - Timeout management
    - Optional feature flagging
    - Debug logging

    Usage:
        analyzer = GenAIAnalyzer(use_genai=True)
        response = analyzer.analyze(PROMPT_TEMPLATE, variable=value)
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: int = DEFAULT_TIMEOUT,
        use_genai: bool = True,
    ):
        """Initialize GenAI analyzer.

        Args:
            model: Claude model to use (default: Haiku for speed/cost)
            max_tokens: Maximum response tokens (default: 100)
            timeout: API call timeout in seconds (default: 5)
            use_genai: Whether to enable GenAI (default: True)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.use_genai = use_genai
        self.client = None
        self.debug = os.environ.get("DEBUG_GENAI", "").lower() == "true"

    def analyze(self, prompt_template: str, **variables) -> Optional[str]:
        """Analyze using GenAI with prompt template.

        Args:
            prompt_template: Prompt string with {variable} placeholders
            **variables: Values for template variables

        Returns:
            GenAI response text, or None if GenAI disabled/failed
        """
        if not self.use_genai:
            return None

        try:
            # Lazy initialization of SDK client
            if not self.client:
                self._initialize_client()

            if not self.client:
                return None

            # Format prompt with variables
            try:
                formatted_prompt = prompt_template.format(**variables)
            except KeyError as e:
                if self.debug:
                    print(f"⚠️  Prompt template missing variable: {e}", file=sys.stderr)
                return None

            # Call GenAI API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": formatted_prompt}],
                timeout=self.timeout,
            )

            response = message.content[0].text.strip()
            if self.debug:
                print(
                    f"✅ GenAI analysis successful ({len(response)} chars)",
                    file=sys.stderr,
                )

            return response

        except Exception as e:
            if self.debug:
                print(f"⚠️  GenAI analysis failed: {e}", file=sys.stderr)
            return None

    def _initialize_client(self):
        """Initialize Anthropic SDK client.

        Handles:
        - SDK import errors
        - Authentication errors
        - Environment configuration
        """
        try:
            from anthropic import Anthropic

            self.client = Anthropic()
            if self.debug:
                print("✅ Anthropic SDK initialized", file=sys.stderr)

        except ImportError:
            if self.debug:
                print(
                    "⚠️  Anthropic SDK not installed: pip install anthropic",
                    file=sys.stderr,
                )
            self.client = None
        except Exception as e:
            if self.debug:
                print(f"⚠️  Failed to initialize Anthropic SDK: {e}", file=sys.stderr)
            self.client = None


def should_use_genai(feature_flag_var: str) -> bool:
    """Check if GenAI should be enabled for this feature.

    Args:
        feature_flag_var: Environment variable name (e.g., "GENAI_SECURITY_SCAN")

    Returns:
        True if GenAI enabled (default: True unless explicitly disabled)

    Usage:
        use_genai = should_use_genai("GENAI_SECURITY_SCAN")
        analyzer = GenAIAnalyzer(use_genai=use_genai)
    """
    env_value = os.environ.get(feature_flag_var, "true").lower()
    return env_value != "false"


def parse_classification_response(response: str, expected_values: list) -> Optional[str]:
    """Parse classification response.

    For prompts that respond with one of a set of values (e.g., REAL/FAKE).

    Args:
        response: Raw response text from GenAI
        expected_values: List of expected values (case-insensitive)

    Returns:
        Matched value (uppercase), or None if no match

    Usage:
        response = analyzer.analyze(PROMPT, ...)
        intent = parse_classification_response(response, ["IMPLEMENT", "REFACTOR", "DOCS", "TEST", "OTHER"])
    """
    if not response:
        return None

    response_upper = response.upper().strip()

    for expected in expected_values:
        expected_upper = expected.upper()
        if expected_upper in response_upper:
            return expected_upper

    return None


def parse_binary_response(
    response: str, true_keywords: list, false_keywords: list
) -> Optional[bool]:
    """Parse binary (yes/no) response.

    For prompts that respond with approval/rejection (e.g., REAL/FAKE, SIMPLE/COMPLEX).

    Args:
        response: Raw response text from GenAI
        true_keywords: Keywords indicating True (e.g., ["REAL", "YES", "ACCURATE"])
        false_keywords: Keywords indicating False (e.g., ["FAKE", "NO", "MISLEADING"])

    Returns:
        True/False if match found, None if ambiguous

    Usage:
        response = analyzer.analyze(PROMPT, ...)
        is_real = parse_binary_response(response, ["REAL", "LIKELY_REAL"], ["FAKE"])
    """
    if not response:
        return None

    response_upper = response.upper()

    # Check for true keywords first
    for keyword in true_keywords:
        if keyword.upper() in response_upper:
            return True

    # Check for false keywords
    for keyword in false_keywords:
        if keyword.upper() in response_upper:
            return False

    # Ambiguous response
    return None


def main() -> int:
    """Smoke-test GenAI utilities (CLI entry point)."""
    # Test utilities
    print("GenAI Utilities Module")
    print("======================\n")

    # Test GenAIAnalyzer initialization
    analyzer = GenAIAnalyzer(use_genai=False)
    print(f"Analyzer (GenAI disabled): {analyzer}")
    print(f"  Model: {analyzer.model}")
    print(f"  Max tokens: {analyzer.max_tokens}")
    print(f"  Timeout: {analyzer.timeout}s\n")

    # Test parsing functions
    print("Parsing Functions:")
    print(f"  parse_classification_response('REFACTOR', ...): {parse_classification_response('REFACTOR', ['IMPLEMENT', 'REFACTOR', 'DOCS'])}")
    print(
        f"  parse_binary_response('FAKE', ...): {parse_binary_response('FAKE', ['REAL'], ['FAKE'])}"
    )
    return 0



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():  # type: ignore[no-redef]
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _safe_main_953(_timed_main)
