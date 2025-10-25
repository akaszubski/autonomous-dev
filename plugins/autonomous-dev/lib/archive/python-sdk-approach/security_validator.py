"""
Security validation using GenAI.

Validates threat model coverage and performs code security review.
Uses Claude Opus 4 for security-critical analysis (GenAI-only, no fallbacks).
"""

import json
from typing import Dict, Any, List
from anthropic import Anthropic


class SecurityValidator:
    """Security validation using Claude Opus (GenAI-only)"""

    @staticmethod
    def validate_threats_with_genai(
        threats: List[Dict],
        implementation_code: str
    ) -> Dict[str, Any]:
        """
        Validate threat model coverage using Claude Opus.

        Args:
            threats: List of threat dictionaries from security audit
            implementation_code: Implementation code to validate

        Returns:
            Dict with validation results:
                - threats_validated: List of per-threat assessments
                - overall_coverage: Coverage score 0-100
                - recommendation: "PASS" or "FAIL"
                - summary: Overall assessment

        Raises:
            ImportError: If anthropic package not installed
            anthropic.APIError: If API call fails
        """
        client = Anthropic()

        prompt = f"""Validate threat mitigation coverage:

THREAT MODEL:
{json.dumps(threats, indent=2)}

IMPLEMENTATION:
```python
{implementation_code}
```

For EACH threat in the threat model, validate:
1. Is the mitigation present in the implementation?
2. Is it correctly implemented?
3. Are edge cases handled?
4. Any security gaps?

Return JSON (valid JSON only, no markdown):
{{
  "threats_validated": [
    {{
      "threat_id": "threat name or category",
      "mitigation_present": true/false,
      "coverage_score": 0-100,
      "issues": ["issue1", "issue2"],
      "recommendations": ["rec1", "rec2"]
    }}
  ],
  "overall_coverage": 0-100,
  "recommendation": "PASS" or "FAIL",
  "summary": "overall assessment"
}}"""

        response = client.messages.create(
            model="claude-opus-4-20250514",  # Use Opus for security-critical analysis
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

        result = json.loads(response.content[0].text)
        return result

    @staticmethod
    def review_code_with_genai(
        implementation_code: str,
        architecture: Dict[str, Any],
        workflow_id: str
    ) -> Dict[str, Any]:
        """
        Review code for security issues using Claude Opus.

        Args:
            implementation_code: Code to review
            architecture: Architecture specifications
            workflow_id: Workflow identifier

        Returns:
            Dict with review results:
                - security_score: 0-100
                - issues: List of security issues found
                - recommendations: List of recommendations
                - approved: Boolean approval status

        Raises:
            ImportError: If anthropic package not installed
            anthropic.APIError: If API call fails
        """
        client = Anthropic()

        # Extract API contracts for context
        api_contracts = architecture.get('api_contracts', [])

        prompt = f"""Security code review:

IMPLEMENTATION:
```python
{implementation_code}
```

API CONTRACTS:
{json.dumps(api_contracts, indent=2)}

Review for:
1. Input validation (injection attacks, type safety)
2. Authentication/authorization gaps
3. Secrets management (no hardcoded secrets)
4. Error handling (no info leaks)
5. OWASP Top 10 vulnerabilities
6. Unsafe operations (eval, exec, shell injection)

Return JSON (valid JSON only, no markdown):
{{
  "security_score": 0-100,
  "issues": [
    {{
      "severity": "critical|high|medium|low",
      "category": "category",
      "description": "issue description",
      "line_number": 123,
      "recommendation": "how to fix"
    }}
  ],
  "recommendations": ["general rec1", "general rec2"],
  "approved": true/false,
  "summary": "overall security assessment"
}}"""

        response = client.messages.create(
            model="claude-opus-4-20250514",  # Use Opus for security
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

        result = json.loads(response.content[0].text)
        return result
