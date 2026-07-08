"""Finding target classification for CI-analyst findings.

This module classifies findings as belonging to 'autonomous-dev', 'consumer', or 'both'
based on vocabulary analysis. Framework-specific terms indicate autonomous-dev issues,
while their absence suggests consumer application issues.
"""

import re
from typing import Optional


# Framework vocabulary - high-precision terms that indicate autonomous-dev issues
FRAMEWORK_TERMS = frozenset({
    # Agent names
    'planner', 'coordinator', 'implementer', 'reviewer', 'plan-critic',
    'doc-master', 'spec-validator', 'test-master', 'security-auditor',
    'continuous-improvement-analyst', 'alignment-validator',
    
    # Pipeline/hook terms
    'hook', 'pipeline', 'slashcommand', 'unified_pre_tool', 'pre-commit hook',
    'agent-completeness gate', 'pipeline_state', 'drain-queue',
    
    # Mode flags
    '--fix mode', '--light', '--issues',
    
    # Commands
    '/implement', '/plan', '/drain-queue', '/improve', '/triage',
    '/audit', '/align',
    
    # Framework-specific
    'autonomous-dev', 'plan-critic bypass', 'sentinel',
})

# Consumer hint terms - if these appear WITH framework terms, classify as "both"
CONSUMER_HINTS = frozenset({
    'gold', 'market', 'pricing', 'config drift', 'audit ordering',
})


def classify_finding_target(
    title: str,
    description: str = "",
    existing_target: Optional[str] = None,
) -> str:
    """Return 'autonomous-dev', 'consumer', or 'both'.
    
    If existing_target is provided and non-empty, returns it unchanged
    (respects CIA's classification). Otherwise applies keyword matching.
    
    Args:
        title: Finding title
        description: Finding description/evidence
        existing_target: Pre-classified target from CIA
        
    Returns:
        One of: 'autonomous-dev', 'consumer', 'both'
    """
    # Respect existing classification if present
    if existing_target and existing_target in {'autonomous-dev', 'consumer', 'both'}:
        return existing_target
    
    # Combine title and description for analysis
    combined_text = f"{title} {description}".lower()
    
    # Check for framework terms (word-boundary matching for multi-char tokens)
    framework_matches = 0
    for term in FRAMEWORK_TERMS:
        # For multi-word terms, replace spaces with regex pattern
        pattern = term.lower().replace(' ', r'\s+').replace('-', r'[\s\-]')
        # Add word boundaries for single words (but not for slash commands)
        if ' ' not in term and '-' not in term and '/' not in term:
            pattern = r'\b' + pattern + r'\b'
        elif '/' in term:
            # For slash commands, match the slash literally
            pattern = re.escape(term.lower())
        if re.search(pattern, combined_text):
            framework_matches += 1
    
    # Check for consumer hints
    consumer_matches = 0
    for hint in CONSUMER_HINTS:
        pattern = hint.lower().replace(' ', r'\s+')
        if ' ' not in hint:
            pattern = r'\b' + pattern + r'\b'
        if re.search(pattern, combined_text):
            consumer_matches += 1
    
    # Classification logic
    if framework_matches >= 1 and consumer_matches >= 1:
        return "both"
    elif framework_matches >= 1:
        return "autonomous-dev"
    else:
        return "consumer"