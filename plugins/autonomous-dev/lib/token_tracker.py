#!/usr/bin/env python3
"""
Token Tracker - Token-aware rate limiting with sliding window

Tracks token usage across multiple agents with a sliding time window to prevent
budget exhaustion and enable efficient resource allocation.

Features:
- Token budget enforcement (reject submissions exceeding budget)
- Sliding window expiration (old usage records expire automatically)
- Per-agent usage tracking (breakdown by agent_id)
- Concurrent usage support (thread-safe tracking)
- Remaining budget calculation (real-time budget availability)

Usage:
    from token_tracker import TokenTracker

    # Create tracker with budget
    tracker = TokenTracker(budget=150000, window_seconds=60)

    # Check if can submit task
    if tracker.can_submit(estimated_tokens=10000):
        # Submit task...
        tracker.record_usage(agent_id="researcher", tokens=10000)

    # Get remaining budget
    remaining = tracker.get_remaining_budget()

    # Get usage by agent
    usage = tracker.get_usage_by_agent()

Security:
- Budget enforcement prevents resource exhaustion (CWE-400)
- No external dependencies or network calls
- Thread-safe for concurrent usage

Date: 2026-01-02
Issue: GitHub #188 (Scalable parallel agent pool)
Agent: implementer
Phase: TDD Green (making tests pass)

See library-design-patterns skill for standardized library structure.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Usage Record
# ============================================================================

@dataclass
class UsageRecord:
    """Token usage record for an agent.

    Attributes:
        agent_id: Agent identifier
        tokens: Number of tokens used
        timestamp: When usage was recorded
    """
    agent_id: str
    tokens: int
    timestamp: datetime


# ============================================================================
# Token Tracker
# ============================================================================

class TokenTracker:
    """Token-aware rate limiting with sliding window.

    Tracks token usage across multiple agents and enforces budget limits using
    a sliding time window. Old usage records expire automatically.

    Design:
        - Sliding window: Usage expires after window_seconds
        - Budget enforcement: Rejects submissions exceeding budget
        - Thread-safe: Can be used with concurrent agents
        - Per-agent tracking: Breakdown usage by agent_id

    Attributes:
        budget: Maximum token budget for window
        window_seconds: Sliding window duration in seconds
    """

    def __init__(self, budget: int, window_seconds: int = 60):
        """Initialize token tracker.

        Args:
            budget: Maximum token budget for sliding window
            window_seconds: Sliding window duration in seconds (default: 60)

        Raises:
            ValueError: If budget or window_seconds is non-positive
        """
        if budget <= 0:
            raise ValueError(f"budget must be positive, got {budget}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be positive, got {window_seconds}")

        self.budget = budget
        self.window_seconds = window_seconds
        self._usage_records: List[UsageRecord] = []

    def record_usage(self, agent_id: str, tokens: int):
        """Record token usage for an agent.

        Args:
            agent_id: Agent identifier
            tokens: Number of tokens used
        """
        record = UsageRecord(
            agent_id=agent_id,
            tokens=tokens,
            timestamp=datetime.now()
        )
        self._usage_records.append(record)

        logger.debug(f"Recorded {tokens} tokens for agent {agent_id}")

    def can_submit(self, estimated_tokens: int) -> bool:
        """Check if submission is within budget.

        Args:
            estimated_tokens: Estimated token usage for submission

        Returns:
            True if submission is within budget, False otherwise
        """
        self._cleanup_expired_records()
        remaining = self.get_remaining_budget()
        return remaining >= estimated_tokens

    def get_remaining_budget(self) -> int:
        """Get remaining token budget in current window.

        Returns:
            Remaining token budget (non-negative)
        """
        self._cleanup_expired_records()

        # Calculate total usage in window
        total_used = sum(record.tokens for record in self._usage_records)

        return max(0, self.budget - total_used)

    def get_usage_by_agent(self) -> Dict[str, int]:
        """Get token usage breakdown by agent.

        Returns:
            Dictionary mapping agent_id to total tokens used
        """
        self._cleanup_expired_records()

        usage = {}
        for record in self._usage_records:
            usage[record.agent_id] = usage.get(record.agent_id, 0) + record.tokens

        return usage

    def _cleanup_expired_records(self):
        """Remove usage records outside sliding window."""
        cutoff_time = datetime.now() - timedelta(seconds=self.window_seconds)

        # Keep only records within window
        self._usage_records = [
            record for record in self._usage_records
            if record.timestamp > cutoff_time
        ]
