#!/usr/bin/env python3
"""
Implementation modes for consolidated /implement command.

Defines ImplementMode enum with three modes:
    - FULL_PIPELINE: Complete SDLC workflow (research → plan → test → implement → review → security → docs)
    - QUICK: Direct implementation (implementer agent only, skip pipeline)
    - BATCH: Batch processing (multiple features from file, GitHub issues, or resume)

Date: 2026-01-09
Issue: Consolidate /implement, /auto-implement, /batch-implement
Agent: implementer
Status: GREEN (implementation complete)
"""

from enum import Enum
from typing import Dict, Any


class ImplementMode(Enum):
    """
    Implementation mode for /implement command.

    Attributes:
        FULL_PIPELINE: Full autonomous workflow (auto-implement)
        QUICK: Quick implementation (implementer agent only)
        BATCH: Batch processing (file/issues/resume)
    """

    FULL_PIPELINE = "full_pipeline"
    QUICK = "quick"
    BATCH = "batch"

    def __str__(self) -> str:
        """String representation of mode."""
        return self.value

    @property
    def description(self) -> str:
        """Human-readable description of mode."""
        descriptions = {
            ImplementMode.FULL_PIPELINE: "Full autonomous workflow with research, planning, testing, implementation, review, security audit, and documentation",
            ImplementMode.QUICK: "Quick implementation with implementer agent only (skip research/planning/review)",
            ImplementMode.BATCH: "Batch processing of multiple features from file, GitHub issues, or resume previous batch",
        }
        return descriptions[self]

    @property
    def estimated_time(self) -> str:
        """Estimated time for mode execution."""
        times = {
            ImplementMode.FULL_PIPELINE: "15-25 minutes",
            ImplementMode.QUICK: "2-5 minutes",
            ImplementMode.BATCH: "20-30 minutes per feature",
        }
        return times[self]

    @property
    def use_cases(self) -> list[str]:
        """Typical use cases for this mode."""
        use_cases = {
            ImplementMode.FULL_PIPELINE: [
                "New features requiring tests and documentation",
                "Bug fixes requiring comprehensive validation",
                "API changes requiring security review",
                "Any code requiring TDD workflow",
            ],
            ImplementMode.QUICK: [
                "Documentation updates",
                "Configuration changes",
                "Simple typo fixes",
                "Quick prototypes (no tests required)",
            ],
            ImplementMode.BATCH: [
                "Processing multiple GitHub issues",
                "Implementing features from backlog file",
                "Resuming interrupted batch processing",
                "Automated feature development pipeline",
            ],
        }
        return use_cases[self]

    def to_dict(self) -> Dict[str, Any]:
        """Convert mode to dictionary representation."""
        return {
            "mode": self.value,
            "description": self.description,
            "estimated_time": self.estimated_time,
            "use_cases": self.use_cases,
        }


# Mode descriptions for help text
MODE_DESCRIPTIONS = {
    ImplementMode.FULL_PIPELINE: {
        "name": "Full Pipeline",
        "description": "Complete SDLC workflow (research → plan → test → implement → review → security → docs)",
        "flags": ["(default)", "--full"],
        "example": '/implement "Add JWT authentication with bcrypt hashing"',
        "time": "15-25 minutes",
    },
    ImplementMode.QUICK: {
        "name": "Quick Mode",
        "description": "Direct implementation with implementer agent only (skip pipeline)",
        "flags": ["--quick", "-q"],
        "example": '/implement --quick "Fix typo in README"',
        "time": "2-5 minutes",
    },
    ImplementMode.BATCH: {
        "name": "Batch Mode",
        "description": "Process multiple features from file, GitHub issues, or resume",
        "flags": ["--batch FILE", "--issues N...", "--resume BATCH_ID"],
        "example": '/implement --batch features.txt',
        "time": "20-30 minutes per feature",
    },
}


def get_mode_help_text() -> str:
    """
    Generate help text for all implementation modes.

    Returns:
        str: Formatted help text with mode descriptions and examples
    """
    help_lines = [
        "Implementation Modes:",
        "",
    ]

    for mode, info in MODE_DESCRIPTIONS.items():
        help_lines.append(f"  {info['name']} ({info['time']})")
        help_lines.append(f"    {info['description']}")
        help_lines.append(f"    Flags: {', '.join(info['flags'])}")
        help_lines.append(f"    Example: {info['example']}")
        help_lines.append("")

    return "\n".join(help_lines)
