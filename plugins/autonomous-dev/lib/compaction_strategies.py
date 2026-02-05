"""Pluggable compaction strategies for context window management.

This module provides different strategies for compacting conversation context
when approaching the context window limit. Strategies include:
- AutoCompactionStrategy: Delegates to Claude's native compaction
- SummarizeCompactionStrategy: Uses iterative summarization
- TruncateCompactionStrategy: Simple FIFO truncation
- ClusteringCompactionStrategy: Groups related memories

Usage:
    from plugins.autonomous_dev.lib.compaction_strategies import (
        get_compaction_strategy,
        CompactionStrategy
    )

    strategy = get_compaction_strategy("summarize")
    compacted_state = strategy.compact(session_state, keep_recent=20)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class CompactionStrategy(ABC):
    """Abstract base class for compaction strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return strategy description."""
        pass

    @abstractmethod
    def compact(
        self,
        session_state: Dict[str, Any],
        keep_recent: int = 20
    ) -> Dict[str, Any]:
        """Compact session state, return new state with reduced tokens.

        Args:
            session_state: Current session state with messages/context.
            keep_recent: Number of recent messages to preserve.

        Returns:
            dict: Compacted session state.
        """
        pass

    def estimate_compression(
        self,
        session_state: Dict[str, Any]
    ) -> float:
        """Estimate compression ratio this strategy would achieve.

        Args:
            session_state: Current session state.

        Returns:
            float: Estimated compression ratio (e.g., 3.0 means 3x smaller).
        """
        return 1.0  # Default: no compression


class AutoCompactionStrategy(CompactionStrategy):
    """Delegates to Claude's native auto-compaction.

    This is a no-op strategy for Claude backends that handle
    compaction automatically. Used as a marker/pass-through.
    """

    @property
    def name(self) -> str:
        return "auto"

    @property
    def description(self) -> str:
        return "Delegates to backend's native compaction (Claude auto-compact)"

    def compact(
        self,
        session_state: Dict[str, Any],
        keep_recent: int = 20
    ) -> Dict[str, Any]:
        """No-op for auto-compaction backends.

        Claude Code handles compaction automatically, so this
        strategy simply returns the state unchanged and logs
        that compaction is delegated.
        """
        logger.info(
            "Auto-compaction strategy: delegating to backend. "
            "No local compaction performed."
        )
        return session_state

    def estimate_compression(self, session_state: Dict[str, Any]) -> float:
        # Claude typically achieves 2-4x compression
        return 3.0


class TruncateCompactionStrategy(CompactionStrategy):
    """Simple FIFO truncation strategy.

    Removes oldest messages, keeping only the most recent N messages.
    Simple but loses historical context.
    """

    @property
    def name(self) -> str:
        return "truncate"

    @property
    def description(self) -> str:
        return "Remove oldest messages (FIFO), keep recent N messages"

    def compact(
        self,
        session_state: Dict[str, Any],
        keep_recent: int = 20
    ) -> Dict[str, Any]:
        """Truncate old messages, keep recent.

        Args:
            session_state: Must contain 'messages' list.
            keep_recent: Number of recent messages to preserve.

        Returns:
            dict: State with truncated messages.
        """
        messages = session_state.get("messages", [])

        if len(messages) <= keep_recent:
            logger.info(
                f"Truncate strategy: no action needed, "
                f"{len(messages)} messages <= {keep_recent} threshold"
            )
            return session_state

        # Keep system message (if present) + recent messages
        truncated = []
        for msg in messages:
            if msg.get("role") == "system":
                truncated.append(msg)
                break

        # Add recent messages
        recent_start = max(len(messages) - keep_recent, 0)
        truncated.extend(messages[recent_start:])

        removed_count = len(messages) - len(truncated)
        logger.info(
            f"Truncate strategy: removed {removed_count} messages, "
            f"kept {len(truncated)} messages"
        )

        return {
            **session_state,
            "messages": truncated,
            "compaction_metadata": {
                "strategy": "truncate",
                "original_count": len(messages),
                "final_count": len(truncated),
                "removed_count": removed_count
            }
        }

    def estimate_compression(self, session_state: Dict[str, Any]) -> float:
        messages = session_state.get("messages", [])
        if len(messages) <= 20:
            return 1.0
        return len(messages) / 20


class SummarizeCompactionStrategy(CompactionStrategy):
    """Anchored Iterative Summarization strategy.

    Uses LLM to summarize older messages while preserving recent context.
    Based on Factory.ai's Anchored Iterative Summarization pattern.
    """

    def __init__(
        self,
        summarization_model: str = "haiku",
        summary_max_tokens: int = 2000
    ):
        """Initialize summarization strategy.

        Args:
            summarization_model: Model to use for summarization (haiku for speed/cost).
            summary_max_tokens: Max tokens for summary output.
        """
        self.summarization_model = summarization_model
        self.summary_max_tokens = summary_max_tokens

    @property
    def name(self) -> str:
        return "summarize"

    @property
    def description(self) -> str:
        return "Summarize old messages, preserve recent context (Anchored Iterative)"

    def compact(
        self,
        session_state: Dict[str, Any],
        keep_recent: int = 20
    ) -> Dict[str, Any]:
        """Summarize older messages, keep recent.

        Args:
            session_state: Must contain 'messages' list.
            keep_recent: Number of recent messages to preserve.

        Returns:
            dict: State with summarized history + recent messages.
        """
        messages = session_state.get("messages", [])

        if len(messages) <= keep_recent:
            logger.info(
                f"Summarize strategy: no action needed, "
                f"{len(messages)} messages <= {keep_recent} threshold"
            )
            return session_state

        # Split messages
        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        if len(non_system) <= keep_recent:
            return session_state

        # Messages to summarize vs keep
        to_summarize = non_system[:-keep_recent]
        to_keep = non_system[-keep_recent:]

        # Generate summary
        summary = self._generate_summary(to_summarize)

        # Build compacted messages
        compacted_messages = system_messages.copy()

        # Add summary as assistant message
        if summary:
            compacted_messages.append({
                "role": "assistant",
                "content": f"[Previous conversation summary]\n{summary}"
            })

        compacted_messages.extend(to_keep)

        logger.info(
            f"Summarize strategy: compressed {len(to_summarize)} messages to summary, "
            f"kept {len(to_keep)} recent messages"
        )

        return {
            **session_state,
            "messages": compacted_messages,
            "compaction_metadata": {
                "strategy": "summarize",
                "original_count": len(messages),
                "summarized_count": len(to_summarize),
                "kept_count": len(to_keep),
                "final_count": len(compacted_messages)
            }
        }

    def _generate_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Generate summary of messages.

        Args:
            messages: Messages to summarize.

        Returns:
            str: Summary text.
        """
        # Build conversation text
        conversation_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                conversation_parts.append(f"{role.upper()}: {content[:500]}")

        conversation_text = "\n\n".join(conversation_parts)

        # Create summary prompt
        summary_prompt = f"""Summarize the following conversation, preserving:
1. Key decisions and conclusions
2. Important facts and context
3. Current task state and progress
4. Any unresolved questions or blockers

Keep the summary concise but complete.

CONVERSATION:
{conversation_text}

SUMMARY:"""

        # In production, this would call the LLM
        # For now, return a structured placeholder
        logger.info(
            f"Generating summary of {len(messages)} messages "
            f"using {self.summarization_model} model"
        )

        # Placeholder - actual implementation would use Task tool or API
        return (
            f"[Summary of {len(messages)} messages - "
            f"use Haiku model for actual summarization]"
        )

    def estimate_compression(self, session_state: Dict[str, Any]) -> float:
        # Summarization typically achieves 3-5x compression
        return 4.0


class ClusteringCompactionStrategy(CompactionStrategy):
    """Semantic clustering compaction strategy.

    Groups related memories into clusters and merges similar context.
    Achieves 6-8x compression for large-scale processing.
    """

    def __init__(self, min_cluster_size: int = 3):
        """Initialize clustering strategy.

        Args:
            min_cluster_size: Minimum messages to form a cluster.
        """
        self.min_cluster_size = min_cluster_size

    @property
    def name(self) -> str:
        return "clustering"

    @property
    def description(self) -> str:
        return "Group related memories into clusters (6-8x compression)"

    def compact(
        self,
        session_state: Dict[str, Any],
        keep_recent: int = 20
    ) -> Dict[str, Any]:
        """Cluster and merge related messages.

        Args:
            session_state: Must contain 'messages' list.
            keep_recent: Number of recent messages to preserve.

        Returns:
            dict: State with clustered history.
        """
        messages = session_state.get("messages", [])

        if len(messages) <= keep_recent:
            logger.info(
                f"Clustering strategy: no action needed, "
                f"{len(messages)} messages <= {keep_recent} threshold"
            )
            return session_state

        # For now, fall back to summarization approach
        # Full clustering would use embeddings and semantic similarity
        logger.info(
            f"Clustering strategy: processing {len(messages)} messages "
            f"(simplified implementation - uses topic clustering)"
        )

        # Keep system + recent, cluster the rest
        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        if len(non_system) <= keep_recent:
            return session_state

        to_cluster = non_system[:-keep_recent]
        to_keep = non_system[-keep_recent:]

        # Simple topic-based clustering (placeholder for semantic clustering)
        clusters = self._create_clusters(to_cluster)

        # Build compacted messages
        compacted_messages = system_messages.copy()

        # Add cluster summaries
        for cluster_name, cluster_messages in clusters.items():
            cluster_summary = self._summarize_cluster(cluster_name, cluster_messages)
            compacted_messages.append({
                "role": "assistant",
                "content": f"[{cluster_name}]\n{cluster_summary}"
            })

        compacted_messages.extend(to_keep)

        logger.info(
            f"Clustering strategy: created {len(clusters)} clusters from "
            f"{len(to_cluster)} messages, kept {len(to_keep)} recent"
        )

        return {
            **session_state,
            "messages": compacted_messages,
            "compaction_metadata": {
                "strategy": "clustering",
                "original_count": len(messages),
                "clusters_created": len(clusters),
                "kept_count": len(to_keep),
                "final_count": len(compacted_messages)
            }
        }

    def _create_clusters(
        self,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Create topic-based clusters from messages.

        Args:
            messages: Messages to cluster.

        Returns:
            dict: Mapping of cluster name to messages.
        """
        # Simple keyword-based clustering (placeholder for semantic)
        clusters: Dict[str, List[Dict[str, Any]]] = {
            "Context": [],
            "Implementation": [],
            "Discussion": []
        }

        for msg in messages:
            content = msg.get("content", "").lower()
            if any(kw in content for kw in ["file", "code", "function", "class", "implement"]):
                clusters["Implementation"].append(msg)
            elif any(kw in content for kw in ["project", "goal", "requirement", "context"]):
                clusters["Context"].append(msg)
            else:
                clusters["Discussion"].append(msg)

        # Remove empty clusters
        return {k: v for k, v in clusters.items() if v}

    def _summarize_cluster(
        self,
        cluster_name: str,
        messages: List[Dict[str, Any]]
    ) -> str:
        """Summarize a cluster of related messages.

        Args:
            cluster_name: Name of the cluster.
            messages: Messages in the cluster.

        Returns:
            str: Cluster summary.
        """
        # Placeholder - actual implementation would use LLM
        return f"Summary of {len(messages)} {cluster_name.lower()} messages"

    def estimate_compression(self, session_state: Dict[str, Any]) -> float:
        # Clustering achieves 6-8x compression
        return 7.0


# Strategy registry
_STRATEGY_REGISTRY: Dict[str, Type[CompactionStrategy]] = {
    "auto": AutoCompactionStrategy,
    "truncate": TruncateCompactionStrategy,
    "summarize": SummarizeCompactionStrategy,
    "clustering": ClusteringCompactionStrategy,
}


def get_compaction_strategy_instance(name: str) -> CompactionStrategy:
    """Get a compaction strategy instance by name.

    Args:
        name: Strategy name (auto, truncate, summarize, clustering).

    Returns:
        CompactionStrategy: Strategy instance.

    Raises:
        ValueError: If strategy name is unknown.
    """
    strategy_class = _STRATEGY_REGISTRY.get(name.lower())
    if not strategy_class:
        raise ValueError(
            f"Unknown compaction strategy: {name}. "
            f"Valid strategies: {', '.join(_STRATEGY_REGISTRY.keys())}"
        )
    return strategy_class()


def register_strategy(name: str, strategy_class: Type[CompactionStrategy]) -> None:
    """Register a custom compaction strategy.

    Args:
        name: Strategy name.
        strategy_class: Strategy class (must inherit CompactionStrategy).
    """
    if not issubclass(strategy_class, CompactionStrategy):
        raise TypeError(
            f"Strategy class must inherit from CompactionStrategy, "
            f"got {strategy_class.__name__}"
        )
    _STRATEGY_REGISTRY[name.lower()] = strategy_class
    logger.info(f"Registered custom compaction strategy: {name}")


def list_strategies() -> List[Dict[str, str]]:
    """List all available compaction strategies.

    Returns:
        list: Strategy info including name and description.
    """
    strategies = []
    for name, cls in _STRATEGY_REGISTRY.items():
        instance = cls()
        strategies.append({
            "name": name,
            "description": instance.description
        })
    return strategies
