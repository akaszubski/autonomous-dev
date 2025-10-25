"""
Alignment validation for PROJECT.md.

Validates user requests against PROJECT.md GOALS, SCOPE, and CONSTRAINTS.
Uses Claude Sonnet 4 for semantic understanding (GenAI-only, no fallbacks).
"""

import json
from typing import Dict, Any, Tuple
from anthropic import Anthropic


class AlignmentValidator:
    """Validate request alignment with PROJECT.md using GenAI"""

    @staticmethod
    def validate_with_genai(
        request: str,
        project_md: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Use Claude Sonnet for semantic alignment validation.

        Args:
            request: User's feature request
            project_md: Parsed PROJECT.md content

        Returns:
            Tuple of (is_aligned, reasoning, alignment_data)

        Raises:
            ImportError: If anthropic package not installed
            anthropic.APIError: If API call fails
        """
        client = Anthropic()  # Uses ANTHROPIC_API_KEY env var

        prompt = f"""Analyze if this request aligns with PROJECT.md.

Request: "{request}"

PROJECT.md GOALS:
{json.dumps(project_md.get('goals', []), indent=2)}

PROJECT.md SCOPE (IN):
{json.dumps(project_md.get('scope', {}).get('included', []), indent=2)}

PROJECT.md SCOPE (OUT):
{json.dumps(project_md.get('scope', {}).get('excluded', []), indent=2)}

PROJECT.md CONSTRAINTS:
{json.dumps(project_md.get('constraints', []), indent=2)}

Evaluate alignment:
1. Does request serve any GOALS? (semantic match, not just keywords)
2. Is request within defined SCOPE?
3. Does request violate any CONSTRAINTS?

Return JSON (valid JSON only, no markdown):
{{
  "is_aligned": true or false,
  "confidence": 0.0 to 1.0,
  "matching_goals": ["goal1", "goal2"],
  "reasoning": "detailed explanation of alignment assessment",
  "scope_assessment": "in scope" or "out of scope" or "unclear",
  "constraint_violations": []
}}"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        result = json.loads(response.content[0].text)

        # Build alignment_data in expected format
        alignment_data = {
            'validated': True,
            'matches_goals': result.get('matching_goals', []),
            'within_scope': result.get('scope_assessment') == 'in scope',
            'scope_items': result.get('matching_goals', []),
            'respects_constraints': len(result.get('constraint_violations', [])) == 0,
            'constraints_checked': len(project_md.get('constraints', [])),
            'confidence': result.get('confidence', 0.0),
            'genai_enhanced': True
        }

        return (
            result['is_aligned'],
            result['reasoning'],
            alignment_data
        )

    @staticmethod
    def validate(
        request: str,
        project_md: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate if request aligns with PROJECT.md (GenAI-only).

        Args:
            request: User's request
            project_md: Parsed PROJECT.md content

        Returns:
            (is_aligned, reason, alignment_data)

        Raises:
            ImportError: If anthropic package not installed
            anthropic.APIError: If API call fails
        """
        return AlignmentValidator.validate_with_genai(request, project_md)
