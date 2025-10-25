"""
Orchestrator for autonomous-dev v2.0
Master coordinator for PROJECT.md-aligned autonomous development.

This module has been refactored into smaller, focused modules:
- project_md_parser.py: PROJECT.md parsing
- alignment_validator.py: Request validation
- agent_invoker.py: Agent invocation factory
- security_validator.py: Security validation
- workflow_coordinator.py: Main orchestration logic

For backward compatibility, we re-export the main classes here.
"""

# Import all classes from new modular structure
from project_md_parser import ProjectMdParser
from alignment_validator import AlignmentValidator
from agent_invoker import AgentInvoker
from security_validator import SecurityValidator
from workflow_coordinator import WorkflowCoordinator, Orchestrator

# Re-export for backward compatibility
__all__ = [
    'ProjectMdParser',
    'AlignmentValidator',
    'AgentInvoker',
    'SecurityValidator',
    'WorkflowCoordinator',
    'Orchestrator'  # Alias for WorkflowCoordinator
]
