"""
Alignment validation for PROJECT.md.

Validates user requests against PROJECT.md GOALS, SCOPE, and CONSTRAINTS.
Uses GenAI (Claude) for semantic validation with regex fallback.
"""

import json
import re
from typing import Dict, Any, Tuple


class AlignmentValidator:
    """Validate request alignment with PROJECT.md"""

    @staticmethod
    def validate_with_genai(
        request: str,
        project_md: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Use Claude Sonnet for semantic alignment validation."""
        try:
            from anthropic import Anthropic
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

        except ImportError:
            # Fallback to regex if anthropic not installed
            print("⚠️  anthropic package not installed, falling back to regex validation")
            return None  # Signal to use fallback
        except Exception as e:
            # Fallback on any error
            print(f"⚠️  GenAI validation failed: {e}, falling back to regex")
            return None  # Signal to use fallback

    @staticmethod
    def validate(
        request: str,
        project_md: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate if request aligns with PROJECT.md (try GenAI, fallback to regex)

        Args:
            request: User's request
            project_md: Parsed PROJECT.md content

        Returns:
            (is_aligned, reason, alignment_data)
        """
        # Try GenAI first
        try:
            genai_result = AlignmentValidator.validate_with_genai(request, project_md)
            if genai_result is not None:
                return genai_result
        except Exception:
            # Fall back to regex if GenAI fails
            pass

        # Original regex implementation
        goals = project_md.get('goals', [])
        scope_included = project_md.get('scope', {}).get('included', [])
        scope_excluded = project_md.get('scope', {}).get('excluded', [])
        constraints = project_md.get('constraints', [])

        # Check 1: Does request support any goal?
        matching_goals = []
        request_lower = request.lower()

        # Domain knowledge: semantic relationships
        semantic_mappings = {
            'authentication': ['security', 'auth', 'login', 'user management'],
            'testing': ['automation', 'quality', 'test', 'coverage'],
            'documentation': ['docs', 'guide', 'readme'],
            'security': ['authentication', 'encryption', 'validation', 'safe'],
            'performance': ['optimize', 'speed', 'fast', 'cache'],
            'automation': ['automatic', 'auto', 'workflow', 'pipeline']
        }

        for goal in goals:
            goal_lower = goal.lower()
            goal_keywords = set(re.findall(r'\b\w+\b', goal_lower))
            request_keywords = set(re.findall(r'\b\w+\b', request_lower))

            # Direct keyword match
            if len(goal_keywords & request_keywords) >= 1:
                matching_goals.append(goal)
                continue

            # Semantic match
            for req_keyword in request_keywords:
                for goal_keyword in goal_keywords:
                    # Check semantic relationships
                    if req_keyword in semantic_mappings.get(goal_keyword, []):
                        matching_goals.append(goal)
                        break
                    if goal_keyword in semantic_mappings.get(req_keyword, []):
                        matching_goals.append(goal)
                        break
                if goal in matching_goals:
                    break

        if not matching_goals:
            return False, f"Request doesn't support any PROJECT.md goal. Goals: {goals}", {}

        # Check 2: Is request within scope?
        # Check if explicitly excluded
        for excluded_item in scope_excluded:
            excluded_lower = excluded_item.lower()
            excluded_keywords = set(re.findall(r'\b\w+\b', excluded_lower))

            if len(excluded_keywords & set(re.findall(r'\b\w+\b', request_lower))) >= 2:
                return False, f"Request '{request}' is explicitly out of scope: {excluded_item}", {}

        # Check if within included scope
        in_scope_items = []
        for included_item in scope_included:
            included_lower = included_item.lower()
            included_keywords = set(re.findall(r'\b\w+\b', included_lower))

            if len(included_keywords & set(re.findall(r'\b\w+\b', request_lower))) >= 1:
                in_scope_items.append(included_item)

        if not in_scope_items and scope_included:  # Only check if scope is defined
            return False, f"Request not clearly within PROJECT.md scope. Scope: {scope_included}", {}

        # Check 3: Does request violate any constraint?
        violations = []
        for constraint in constraints:
            constraint_lower = constraint.lower()

            # Check for explicit "no" or "must not" patterns
            if re.search(r'\b(no|must not|cannot|don\'t)\b', constraint_lower):
                # Extract what's forbidden
                forbidden_patterns = re.findall(r'(?:no|must not|cannot|don\'t)\s+(\w+(?:\s+\w+)*)', constraint_lower)

                for pattern in forbidden_patterns:
                    if pattern in request_lower:
                        violations.append(f"{constraint} (detected: '{pattern}')")

        if violations:
            return False, f"Request violates constraints: {violations}", {}

        # All checks passed
        alignment_data = {
            'validated': True,
            'matches_goals': matching_goals,
            'within_scope': True,
            'scope_items': in_scope_items,
            'respects_constraints': True,
            'constraints_checked': len(constraints)
        }

        rationale = f"""
Alignment validated:
- Supports goals: {', '.join(matching_goals)}
- Within scope: {', '.join(in_scope_items) if in_scope_items else 'General scope'}
- Respects all {len(constraints)} constraints
"""

        return True, rationale.strip(), alignment_data
