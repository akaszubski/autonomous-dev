"""Context window management for multi-backend support.

This module provides configurable context window management for different LLM backends
(Claude, OpenAI, Gemini, Ollama, custom). It handles:
- Backend-specific context window sizes
- Compaction threshold detection
- Custom compaction strategy selection

Usage:
    from plugins.autonomous_dev.lib.context_window_manager import (
        get_context_window_size,
        should_trigger_compaction,
        needs_custom_compaction
    )

    # Check if compaction needed
    if should_trigger_compaction(current_tokens=150000):
        # Trigger compaction strategy
        pass

Environment Variables:
    CONTEXT_WINDOW_SIZE: Max tokens (default: backend-specific)
    COMPACTION_THRESHOLD_PCT: Trigger compaction at this % (default: 85)
    BACKEND: Backend name (claude, openai, gemini, ollama, custom)
    CUSTOM_CONTEXT_COMPACTION: Enable custom compaction (default: false for Claude)
    COMPACTION_STRATEGY: Strategy name (auto, summarize, truncate, clustering)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Backend-specific defaults
BACKEND_DEFAULTS: Dict[str, Dict[str, any]] = {
    "claude": {
        "context_window": 200_000,
        "needs_custom_compaction": False,
        "default_strategy": "auto",
        "description": "Claude with native auto-compaction"
    },
    "openai": {
        "context_window": 128_000,
        "needs_custom_compaction": True,
        "default_strategy": "summarize",
        "description": "OpenAI GPT-4 (128K context)"
    },
    "gemini": {
        "context_window": 1_000_000,
        "needs_custom_compaction": True,
        "default_strategy": "summarize",
        "description": "Google Gemini 1.5 (1M context)"
    },
    "ollama": {
        "context_window": 8_192,  # Conservative default, user should set
        "needs_custom_compaction": True,
        "default_strategy": "truncate",
        "description": "Ollama local models (varies by model)"
    },
    "vllm": {
        "context_window": 32_768,  # Common default, user should set
        "needs_custom_compaction": True,
        "default_strategy": "summarize",
        "description": "vLLM self-hosted (varies by model)"
    },
    "custom": {
        "context_window": 32_768,  # Conservative default
        "needs_custom_compaction": True,
        "default_strategy": "truncate",
        "description": "Custom backend (configure CONTEXT_WINDOW_SIZE)"
    }
}

# Valid context window range
MIN_CONTEXT_WINDOW = 1_000
MAX_CONTEXT_WINDOW = 2_000_000

# Default threshold percentage
DEFAULT_THRESHOLD_PCT = 85


def _sanitize_backend_name(name: str) -> str:
    """Sanitize backend name to prevent log injection (CWE-117).

    Args:
        name: Raw backend name from environment.

    Returns:
        str: Sanitized backend name (alphanumeric + underscore only).
    """
    # Only allow alphanumeric and underscore
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name.lower())
    return sanitized[:50]  # Limit length


def get_backend_name() -> str:
    """Get configured backend name.

    Returns:
        str: Backend name (lowercase, sanitized).
    """
    raw_backend = os.environ.get("BACKEND", "claude")
    backend = _sanitize_backend_name(raw_backend)

    if backend not in BACKEND_DEFAULTS:
        logger.warning(
            f"Unknown backend '{backend}', using 'custom' defaults. "
            f"Valid backends: {', '.join(BACKEND_DEFAULTS.keys())}"
        )
        return "custom"

    return backend


def get_backend_config() -> Dict[str, any]:
    """Get configuration for current backend.

    Returns:
        dict: Backend configuration including context_window, needs_custom_compaction, etc.
    """
    backend = get_backend_name()
    return BACKEND_DEFAULTS.get(backend, BACKEND_DEFAULTS["custom"])


def get_context_window_size() -> int:
    """Get configured or auto-detected context window size.

    Priority:
    1. CONTEXT_WINDOW_SIZE environment variable
    2. Backend-specific default

    Returns:
        int: Context window size in tokens.

    Raises:
        ValueError: If configured size is out of valid range.
    """
    # Check environment variable first
    env_size = os.environ.get("CONTEXT_WINDOW_SIZE")
    if env_size:
        try:
            size = int(env_size)
            if not MIN_CONTEXT_WINDOW <= size <= MAX_CONTEXT_WINDOW:
                raise ValueError(
                    f"CONTEXT_WINDOW_SIZE={size} out of valid range.\n"
                    f"Valid range: {MIN_CONTEXT_WINDOW:,} - {MAX_CONTEXT_WINDOW:,} tokens.\n"
                    f"Fix: Set CONTEXT_WINDOW_SIZE to a value within range."
                )
            return size
        except ValueError as e:
            if "out of valid range" in str(e):
                raise
            logger.warning(
                f"Invalid CONTEXT_WINDOW_SIZE='{env_size}', using backend default. "
                f"Expected integer value."
            )

    # Fall back to backend default
    config = get_backend_config()
    return config["context_window"]


def get_compaction_threshold_pct() -> int:
    """Get compaction threshold percentage.

    Returns:
        int: Percentage at which to trigger compaction (default: 85).
    """
    env_pct = os.environ.get("COMPACTION_THRESHOLD_PCT")
    if env_pct:
        try:
            pct = int(env_pct)
            if 50 <= pct <= 99:
                return pct
            logger.warning(
                f"COMPACTION_THRESHOLD_PCT={pct} out of valid range (50-99), "
                f"using default {DEFAULT_THRESHOLD_PCT}%."
            )
        except ValueError:
            logger.warning(
                f"Invalid COMPACTION_THRESHOLD_PCT='{env_pct}', "
                f"using default {DEFAULT_THRESHOLD_PCT}%."
            )

    return DEFAULT_THRESHOLD_PCT


def get_compaction_threshold() -> int:
    """Calculate compaction trigger point (window_size * threshold_pct).

    Returns:
        int: Token count at which to trigger compaction.
    """
    window_size = get_context_window_size()
    threshold_pct = get_compaction_threshold_pct()
    return int(window_size * threshold_pct / 100)


def should_trigger_compaction(current_tokens: int) -> bool:
    """Check if current token count exceeds threshold.

    Args:
        current_tokens: Current context token count.

    Returns:
        bool: True if compaction should be triggered.
    """
    threshold = get_compaction_threshold()
    should_compact = current_tokens >= threshold

    if should_compact:
        window_size = get_context_window_size()
        logger.info(
            f"Context compaction triggered: {current_tokens:,} tokens >= "
            f"{threshold:,} threshold ({get_compaction_threshold_pct()}% of {window_size:,})"
        )

    return should_compact


def needs_custom_compaction() -> bool:
    """Check if custom compaction is needed (non-Claude backends).

    Priority:
    1. CUSTOM_CONTEXT_COMPACTION environment variable
    2. Backend-specific default

    Returns:
        bool: True if custom compaction is needed.
    """
    # Check explicit environment setting
    env_custom = os.environ.get("CUSTOM_CONTEXT_COMPACTION", "").lower()
    if env_custom in ("true", "1", "yes"):
        return True
    if env_custom in ("false", "0", "no"):
        return False

    # Fall back to backend default
    config = get_backend_config()
    return config["needs_custom_compaction"]


def get_compaction_strategy() -> str:
    """Get configured compaction strategy.

    Returns:
        str: Strategy name (auto, summarize, truncate, clustering).
    """
    # Check environment variable
    env_strategy = os.environ.get("COMPACTION_STRATEGY", "").lower()
    valid_strategies = {"auto", "summarize", "truncate", "clustering"}

    if env_strategy in valid_strategies:
        return env_strategy

    if env_strategy:
        logger.warning(
            f"Unknown COMPACTION_STRATEGY='{env_strategy}', using 'auto'. "
            f"Valid strategies: {', '.join(valid_strategies)}"
        )

    # Fall back to backend default
    config = get_backend_config()
    return config["default_strategy"]


def get_checkpoint_before_compaction() -> bool:
    """Check if checkpoint should be created before compaction.

    Returns:
        bool: True if checkpoint should be created (default: True).
    """
    env_checkpoint = os.environ.get("CHECKPOINT_BEFORE_COMPACTION", "true").lower()
    return env_checkpoint in ("true", "1", "yes")


def get_context_status() -> Dict[str, any]:
    """Get comprehensive context configuration status.

    Returns:
        dict: Current configuration including backend, window size, threshold, etc.
    """
    backend = get_backend_name()
    config = get_backend_config()

    return {
        "backend": backend,
        "backend_description": config["description"],
        "context_window_size": get_context_window_size(),
        "compaction_threshold_pct": get_compaction_threshold_pct(),
        "compaction_threshold_tokens": get_compaction_threshold(),
        "needs_custom_compaction": needs_custom_compaction(),
        "compaction_strategy": get_compaction_strategy(),
        "checkpoint_before_compaction": get_checkpoint_before_compaction(),
    }


def log_context_status() -> None:
    """Log current context configuration status."""
    status = get_context_status()

    logger.info(
        f"Context configuration: "
        f"backend={status['backend']}, "
        f"window={status['context_window_size']:,} tokens, "
        f"threshold={status['compaction_threshold_pct']}% "
        f"({status['compaction_threshold_tokens']:,} tokens)"
    )

    if status["needs_custom_compaction"]:
        logger.info(
            f"Custom compaction enabled: strategy={status['compaction_strategy']}, "
            f"checkpoint={status['checkpoint_before_compaction']}"
        )
    else:
        logger.info("Using native backend compaction (Claude auto-compact)")
