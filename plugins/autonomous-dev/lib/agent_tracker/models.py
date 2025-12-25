#!/usr/bin/env python3
"""
Agent Tracker Models - Constants and data structures

This module defines metadata and constants used across the agent_tracker package.

Date: 2025-12-25
Issue: GitHub #165 - Refactor agent_tracker.py into package
"""

# Agent metadata with descriptions and emojis
AGENT_METADATA = {
    "researcher": {
        "description": "Research patterns and best practices (DEPRECATED - use researcher-local + researcher-web)",
        "emoji": "🔍"
    },
    "researcher-local": {
        "description": "Search codebase for existing patterns",
        "emoji": "🔍"
    },
    "researcher-web": {
        "description": "Research industry best practices and standards",
        "emoji": "🌐"
    },
    "planner": {
        "description": "Create architecture plan and design",
        "emoji": "📋"
    },
    "test-master": {
        "description": "Write tests first (TDD)",
        "emoji": "🧪"
    },
    "implementer": {
        "description": "Implement code to make tests pass",
        "emoji": "⚙️"
    },
    "reviewer": {
        "description": "Code review and quality check",
        "emoji": "👀"
    },
    "security-auditor": {
        "description": "Security scan and vulnerability detection",
        "emoji": "🔒"
    },
    "doc-master": {
        "description": "Update documentation",
        "emoji": "📝"
    }
}

# Expected agents in execution order (standard workflow)
# This list defines the standard /auto-implement pipeline
EXPECTED_AGENTS = [
    "researcher",
    "planner",
    "test-master",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master"
]

# Export all public symbols
__all__ = ["AGENT_METADATA", "EXPECTED_AGENTS"]
