"""Shared heredoc-stripping utility used by hook + classifier code paths.

Extracted from ``unified_pre_tool.py:_strip_heredoc_content`` (Phase 2, Issue
#1153) so the same single source of truth is used everywhere a Bash command is
inspected for risky patterns. Mirrors the extraction precedent set by
``hook_bypass.py`` (lifted from ``unified_pre_tool.py`` and now imported by
many hooks).

This module is intentionally tiny — one pure function, one compiled regex —
and has zero runtime dependencies beyond ``re``. It must remain importable
from both the hook subprocess (where ``plugins/autonomous-dev/hooks/`` is on
``sys.path``) and from ``edit_tier_classifier.py`` (which is loaded by
``importlib.util`` from the hook).

Issue: #1153
"""

from __future__ import annotations

import re

# Extension of the legacy ``unified_pre_tool.py:_strip_heredoc_content``
# regex (line 2054 in master prior to Phase 2). The pattern matches:
#   - ``<<EOF`` / ``<<-EOF`` (indented form — tabs allowed before closer)
#   - ``<<'EOF'`` / ``<<"EOF"``
# captures the delimiter word, then strips everything up to the matching
# delimiter on its own line (or EOF). The ``[ \t]*`` before ``\1`` lets us
# correctly strip POSIX-style ``<<-`` indented heredocs where the closing
# delimiter is preceded by leading tabs (Bash strips those for ``<<-``).
# This goes slightly beyond the original strip but fixes the Phase 2 risk
# #4 in the plan: indented-heredoc forms were a documented residual.
_HEREDOC_PATTERN = re.compile(
    r"<<-?\s*['\"]?(\w+)['\"]?.*?\n(.*?\n)*?[ \t]*\1\b",
    re.DOTALL,
)


def strip_heredoc_content(command: str) -> str:
    """Remove heredoc bodies from a Bash command string.

    Used to prevent false positives when keyword-like content (commit
    messages, issue bodies, code examples in documentation) appears inside
    a heredoc body that itself sits inside a parent command we are scanning
    for risky patterns (``gh issue create``, ``cat > X.py``, etc.).

    The function is intentionally conservative: it accepts the broadest set
    of well-formed heredoc forms (``<<``, ``<<-``, single-quoted, double-
    quoted, unquoted) and returns the input unchanged on any regex error.

    Args:
        command: The raw Bash command string.

    Returns:
        The command with heredoc body content (between the opening
        delimiter and its closing line) replaced by the empty string.
        Returns the input unchanged when the regex engine raises.
    """
    if not command:
        return command
    try:
        return _HEREDOC_PATTERN.sub("", command)
    except re.error:
        return command


__all__ = ["strip_heredoc_content"]
