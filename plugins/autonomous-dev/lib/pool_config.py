#!/usr/bin/env python3
"""
Pool Configuration - Agent pool configuration with validation and loading

Manages configuration for the scalable parallel agent pool system, supporting:
- Default configuration values (max_agents=6, token_budget=150000)
- Environment variable override (AGENT_POOL_* variables)
- PROJECT.md configuration loading
- Validation (max_agents: 3-12, token_budget: positive)

Configuration Sources (priority order):
    1. Constructor arguments (highest priority)
    2. Environment variables (AGENT_POOL_*)
    3. PROJECT.md (## Agent Pool Configuration section)
    4. Defaults (fallback)

Usage:
    from pool_config import PoolConfig

    # Use defaults
    config = PoolConfig()

    # Load from environment
    config = PoolConfig.load_from_env()

    # Load from PROJECT.md
    config = PoolConfig.load_from_project(project_root)

    # Custom values
    config = PoolConfig(max_agents=8, token_budget=200000)

Security:
- Input validation for all configuration values
- Graceful degradation for invalid PROJECT.md
- No network dependencies

Date: 2026-01-02
Issue: GitHub #188 (Scalable parallel agent pool)
Agent: implementer
Phase: TDD Green (making tests pass)

See library-design-patterns skill for standardized library structure.
See error-handling-patterns skill for validation patterns.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Pool Configuration
# ============================================================================

@dataclass
class PoolConfig:
    """Agent pool configuration with validation.

    Attributes:
        max_agents: Maximum concurrent agents (3-12)
        token_budget: Token budget for sliding window (positive integer)
        priority_enabled: Enable priority queue (default: True)
        token_window_seconds: Sliding window duration in seconds (default: 60)

    Raises:
        ValueError: If validation fails (max_agents out of range, negative budget)
    """
    max_agents: int = 6
    token_budget: int = 150000
    priority_enabled: bool = True
    token_window_seconds: int = 60

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """Validate configuration values.

        Raises:
            ValueError: If validation fails
        """
        # Validate max_agents (3-12 range)
        if not (3 <= self.max_agents <= 12):
            raise ValueError(
                f"max_agents must be between 3 and 12, got {self.max_agents}"
            )

        # Validate token_budget (must be positive)
        if self.token_budget <= 0:
            raise ValueError(
                f"token_budget must be positive, got {self.token_budget}"
            )

        # Validate token_window_seconds (must be positive)
        if self.token_window_seconds <= 0:
            raise ValueError(
                f"token_window_seconds must be positive, got {self.token_window_seconds}"
            )

    @classmethod
    def load_from_env(cls) -> "PoolConfig":
        """Load configuration from environment variables.

        Environment Variables:
            AGENT_POOL_MAX_AGENTS: Maximum concurrent agents (3-12)
            AGENT_POOL_TOKEN_BUDGET: Token budget for sliding window
            AGENT_POOL_PRIORITY_ENABLED: Enable priority queue (true/false)
            AGENT_POOL_TOKEN_WINDOW_SECONDS: Sliding window duration

        Returns:
            PoolConfig instance with environment overrides

        Raises:
            ValueError: If environment values fail validation
        """
        # Load with defaults
        max_agents = int(os.getenv("AGENT_POOL_MAX_AGENTS", "6"))
        token_budget = int(os.getenv("AGENT_POOL_TOKEN_BUDGET", "150000"))
        priority_enabled = os.getenv("AGENT_POOL_PRIORITY_ENABLED", "true").lower() == "true"
        token_window_seconds = int(os.getenv("AGENT_POOL_TOKEN_WINDOW_SECONDS", "60"))

        return cls(
            max_agents=max_agents,
            token_budget=token_budget,
            priority_enabled=priority_enabled,
            token_window_seconds=token_window_seconds,
        )

    @classmethod
    def load_from_project(cls, project_root: Path) -> "PoolConfig":
        """Load configuration from PROJECT.md.

        Searches for:
            ## Agent Pool Configuration

            ```json
            {
              "max_agents": 8,
              "token_budget": 100000,
              "priority_enabled": true
            }
            ```

        Args:
            project_root: Project root directory (contains .claude/PROJECT.md)

        Returns:
            PoolConfig instance with PROJECT.md overrides (or defaults if not found)
        """
        project_md = project_root / ".claude" / "PROJECT.md"

        # If PROJECT.md doesn't exist, return defaults
        if not project_md.exists():
            logger.debug(f"PROJECT.md not found at {project_md}, using defaults")
            return cls()

        try:
            # Read PROJECT.md
            content = project_md.read_text()

            # Search for Agent Pool Configuration section
            pattern = r"## Agent Pool Configuration\s*```json\s*(\{[^`]+\})\s*```"
            match = re.search(pattern, content, re.DOTALL)

            if not match:
                logger.debug("No Agent Pool Configuration section found, using defaults")
                return cls()

            # Parse JSON configuration
            config_json = match.group(1)
            config_data = json.loads(config_json)

            # Extract values with defaults
            max_agents = config_data.get("max_agents", 6)
            token_budget = config_data.get("token_budget", 150000)
            priority_enabled = config_data.get("priority_enabled", True)
            token_window_seconds = config_data.get("token_window_seconds", 60)

            return cls(
                max_agents=max_agents,
                token_budget=token_budget,
                priority_enabled=priority_enabled,
                token_window_seconds=token_window_seconds,
            )

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse PROJECT.md configuration: {e}, using defaults")
            return cls()
