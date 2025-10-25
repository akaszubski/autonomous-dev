#!/usr/bin/env python3
"""
GenAI Quality Gates - Consolidated Implementation

All GenAI-powered quality validation in one file for maximum accuracy:
1. Code Review Quality Gate
2. Test Quality Assessment
3. Security Vulnerability Detection
4. GitHub Issue Classification
5. Commit Message Generation

Usage:
    # Code review
    python genai_quality_gates.py review --diff <file>

    # Test quality
    python genai_quality_gates.py test-quality --file tests/test_foo.py

    # Security scan
    python genai_quality_gates.py security --file src/foo.py

    # Classify issue
    python genai_quality_gates.py classify-issue --description "Test fails"

    # Generate commit message
    python genai_quality_gates.py commit-msg --diff <changes>
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# ============================================================================
# GenAI Client
# ============================================================================

def get_llm_client():
    """Get LLM client (maximum accuracy model - Sonnet 4.5)."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if anthropic_key:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        return client, "claude-sonnet-4-5-20250929", "anthropic"  # Latest Sonnet 4.5
    elif openrouter_key:
        import openai
        client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key)
        return client, "anthropic/claude-sonnet-4.5", "openrouter"  # Sonnet 4.5 via OpenRouter
    else:
        print("❌ No API key! Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY")
        sys.exit(1)

def call_llm(prompt: str) -> str:
    """Call LLM with prompt, return response."""
    client, model, provider = get_llm_client()

    if provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    else:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

# ============================================================================
# 1. Code Review Quality Gate
# ============================================================================

@dataclass
class CodeReviewResult:
    approved: bool
    score: int  # 0-10
    issues: List[Dict]
    strengths: List[str]
    suggestions: List[str]
    reasoning: str

def code_review_genai(diff_content: str, context: Dict = None) -> CodeReviewResult:
    """Deep code review with architectural awareness."""

    prompt = f"""You are performing a deep code review with architectural awareness.

**CODE CHANGES**:
```
{diff_content[:6000]}
```

**PROJECT CONTEXT** (if available):
{json.dumps(context or {}, indent=2)[:1000]}

**REVIEW CHECKLIST**:

1. **Logic & Correctness**:
   - Edge cases handled? (null, empty, negative, boundary values)
   - Off-by-one errors?
   - Race conditions?
   - Resource leaks?

2. **Code Quality**:
   - Variable names semantic and clear?
   - Functions single-responsibility?
   - Complexity reasonable (not over-engineered)?
   - DRY principle followed?

3. **Architecture**:
   - Follows existing patterns?
   - Introduces new patterns? (justify if so)
   - Breaks modularity?
   - Creates tight coupling?

4. **Security**:
   - Input validation?
   - SQL injection risks?
   - XSS vulnerabilities?
   - Sensitive data exposure?

5. **Testing**:
   - Tests included?
   - Edge cases tested?
   - Test quality adequate?

6. **Performance**:
   - O(n²) or worse algorithms?
   - Memory leaks?
   - Unnecessary database queries?

Respond JSON:
```json
{{
  "approved": true/false,
  "score": 0-10,
  "reasoning": "Overall assessment",
  "issues": [
    {{"severity": "critical/high/medium/low", "description": "...", "suggestion": "..."}}
  ],
  "strengths": ["What's good about this code"],
  "suggestions": ["How to improve"]
}}
```

Approve (score 7+) if no critical issues. Be thorough but fair.
"""

    response = call_llm(prompt)
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    data = json.loads(json_match.group(1) if json_match else response)

    return CodeReviewResult(
        approved=data.get("approved", False),
        score=data.get("score", 0),
        issues=data.get("issues", []),
        strengths=data.get("strengths", []),
        suggestions=data.get("suggestions", []),
        reasoning=data.get("reasoning", "")
    )

# ============================================================================
# 2. Test Quality Assessment
# ============================================================================

@dataclass
class TestQualityResult:
    score: int  # 0-10
    coverage_meaningful: bool
    gaps: List[str]
    strengths: List[str]
    recommendations: List[str]

def assess_test_quality_genai(test_code: str, source_code: str) -> TestQualityResult:
    """Assess test quality beyond coverage %."""

    prompt = f"""Assess test quality (not just coverage %).

**SOURCE CODE**:
```
{source_code[:3000]}
```

**TEST CODE**:
```
{test_code[:3000]}
```

**ASSESSMENT CRITERIA**:

1. **Edge Cases**: null, empty, negative, boundary, max values
2. **Error Conditions**: exceptions, invalid input, timeouts
3. **Independence**: no shared state, order-independent
4. **Assertions**: meaningful (not just "assert True")
5. **Test Names**: descriptive of what's being tested
6. **Setup/Teardown**: proper resource cleanup
7. **Mocking**: appropriate use of mocks/stubs

Respond JSON:
```json
{{
  "score": 0-10,
  "coverage_meaningful": true/false,
  "gaps": ["Missing edge case: null input", "No error condition tests"],
  "strengths": ["Good test independence", "Clear test names"],
  "recommendations": ["Add boundary value tests", "Test concurrent access"]
}}
```

Score 7+ = good tests. Be strict - high coverage with weak tests = low score.
"""

    response = call_llm(prompt)
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    data = json.loads(json_match.group(1) if json_match else response)

    return TestQualityResult(
        score=data.get("score", 0),
        coverage_meaningful=data.get("coverage_meaningful", False),
        gaps=data.get("gaps", []),
        strengths=data.get("strengths", []),
        recommendations=data.get("recommendations", [])
    )

# ============================================================================
# 3. Security Vulnerability Detection
# ============================================================================

@dataclass
class SecurityScanResult:
    vulnerabilities: List[Dict]
    risk_score: int  # 0-10 (10 = critical risk)
    safe: bool

def security_scan_genai(code: str, context: str = "") -> SecurityScanResult:
    """Context-aware security vulnerability detection."""

    prompt = f"""Perform context-aware security analysis.

**CODE**:
```
{code[:4000]}
```

**CONTEXT**:
{context[:500]}

**SECURITY CHECKS**:

1. **Injection Attacks**:
   - SQL injection (even in ORMs - parameterization correct?)
   - Command injection (shell, os.system, subprocess with user input?)
   - LDAP injection
   - XML injection

2. **XSS Vulnerabilities**:
   - Output escaping (HTML, JS, URL contexts)?
   - Content-Type headers correct?

3. **Authentication/Authorization**:
   - Auth bypasses (logic flaws)?
   - Privilege escalation possible?
   - Session management secure?

4. **Data Exposure**:
   - Sensitive data in logs/errors?
   - PII handling compliant?
   - Secrets hardcoded?

5. **Crypto Issues**:
   - Weak algorithms (MD5, SHA1, DES)?
   - Hardcoded keys/IVs?
   - Insecure random (Math.random)?

6. **Race Conditions**:
   - TOCTOU (time-of-check-time-of-use)?
   - Concurrent access issues?

7. **Resource Exhaustion**:
   - Unbounded loops/recursion?
   - Memory/file descriptor leaks?

Respond JSON:
```json
{{
  "vulnerabilities": [
    {{"severity": "critical/high/medium/low", "type": "SQL Injection", "description": "...", "line": 42, "fix": "Use parameterized queries"}}
  ],
  "risk_score": 0-10,
  "safe": true/false
}}
```

Mark safe=false if any critical/high vulnerabilities found.
"""

    response = call_llm(prompt)
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    data = json.loads(json_match.group(1) if json_match else response)

    return SecurityScanResult(
        vulnerabilities=data.get("vulnerabilities", []),
        risk_score=data.get("risk_score", 0),
        safe=data.get("safe", True)
    )

# ============================================================================
# 4. GitHub Issue Classification
# ============================================================================

@dataclass
class IssueClassification:
    type: str  # bug/feature/enhancement/refactoring/documentation
    priority: str  # critical/high/medium/low
    component: str
    labels: List[str]
    goal_alignment: str

def classify_issue_genai(description: str, context: Dict = None) -> IssueClassification:
    """Intelligent issue classification."""

    prompt = f"""Classify this GitHub issue.

**ISSUE DESCRIPTION**:
{description}

**PROJECT CONTEXT**:
{json.dumps(context or {}, indent=2)[:500]}

**CLASSIFICATION TASK**:

Determine:
1. **Type**: bug/feature/enhancement/refactoring/documentation/question
2. **Priority**: critical (blocks release) / high (important) / medium (nice to have) / low (backlog)
3. **Component**: Which part of codebase affected
4. **Labels**: Suggested GitHub labels
5. **Goal Alignment**: Which PROJECT.md goal does this relate to?

Respond JSON:
```json
{{
  "type": "bug",
  "priority": "high",
  "component": "authentication",
  "labels": ["bug", "security", "P1"],
  "goal_alignment": "Security and quality"
}}
```
"""

    response = call_llm(prompt)
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    data = json.loads(json_match.group(1) if json_match else response)

    return IssueClassification(
        type=data.get("type", "question"),
        priority=data.get("priority", "low"),
        component=data.get("component", "general"),
        labels=data.get("labels", []),
        goal_alignment=data.get("goal_alignment", "")
    )

# ============================================================================
# 5. Commit Message Generation
# ============================================================================

def generate_commit_message_genai(diff: str, context: Dict = None) -> str:
    """Generate semantic commit message following conventions."""

    prompt = f"""Generate a semantic commit message following conventional commits.

**GIT DIFF**:
```
{diff[:3000]}
```

**PROJECT CONTEXT**:
{json.dumps(context or {}, indent=2)[:500]}

**COMMIT MESSAGE FORMAT**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: feat, fix, docs, refactor, test, chore, perf, ci, build, revert

**Rules**:
- Subject: imperative mood ("add" not "added"), <72 chars, no period
- Body: what changed and why (not how)
- Footer: breaking changes, issue references

**Example**:
```
feat(version-sync): add GenAI validation for accuracy

Replace regex-based version detection with LLM-powered contextual
understanding. This eliminates false positives from external package
versions (anthropic 3.3.0, pytest 23.11.0) while maintaining 99%+
accuracy for actual plugin version references.

Closes #42
```

Generate the commit message for this diff.
"""

    response = call_llm(prompt)
    # Extract commit message (remove markdown formatting if present)
    message = response.strip()
    if message.startswith("```"):
        lines = message.split("\n")
        message = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return message.strip()

# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="GenAI Quality Gates")
    subparsers = parser.add_subparsers(dest="command")

    # Code review
    review_parser = subparsers.add_parser("review", help="Code review")
    review_parser.add_argument("--diff", help="Diff file or use git diff")

    # Test quality
    test_parser = subparsers.add_parser("test-quality", help="Assess test quality")
    test_parser.add_argument("--test-file", required=True)
    test_parser.add_argument("--source-file", required=True)

    # Security scan
    security_parser = subparsers.add_parser("security", help="Security scan")
    security_parser.add_argument("--file", required=True)

    # Classify issue
    issue_parser = subparsers.add_parser("classify-issue", help="Classify GitHub issue")
    issue_parser.add_argument("--description", required=True)

    # Commit message
    commit_parser = subparsers.add_parser("commit-msg", help="Generate commit message")
    commit_parser.add_argument("--use-git-diff", action="store_true")

    args = parser.parse_args()

    if args.command == "review":
        if args.diff:
            diff = Path(args.diff).read_text()
        else:
            diff = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True).stdout

        result = code_review_genai(diff)
        print(f"\n{'✅ APPROVED' if result.approved else '❌ REJECTED'} - Score: {result.score}/10\n")
        print(f"Reasoning: {result.reasoning}\n")
        if result.issues:
            print("Issues:")
            for issue in result.issues:
                print(f"  [{issue['severity']}] {issue['description']}")
        return 0 if result.approved else 1

    elif args.command == "test-quality":
        test_code = Path(args.test_file).read_text()
        source_code = Path(args.source_file).read_text()
        result = assess_test_quality_genai(test_code, source_code)
        print(f"\nTest Quality Score: {result.score}/10")
        print(f"Coverage Meaningful: {'✅' if result.coverage_meaningful else '❌'}\n")
        if result.gaps:
            print("Gaps:", "\n".join(f"  - {g}" for g in result.gaps))
        return 0 if result.score >= 7 else 1

    elif args.command == "security":
        code = Path(args.file).read_text()
        result = security_scan_genai(code)
        print(f"\n{'✅ SAFE' if result.safe else '❌ VULNERABILITIES FOUND'}")
        print(f"Risk Score: {result.risk_score}/10\n")
        for vuln in result.vulnerabilities:
            print(f"[{vuln['severity']}] {vuln['type']}: {vuln['description']}")
        return 0 if result.safe else 1

    elif args.command == "classify-issue":
        result = classify_issue_genai(args.description)
        print(f"\nType: {result.type}")
        print(f"Priority: {result.priority}")
        print(f"Component: {result.component}")
        print(f"Labels: {', '.join(result.labels)}")

    elif args.command == "commit-msg":
        if args.use_git_diff:
            diff = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True).stdout
        else:
            diff = sys.stdin.read()
        message = generate_commit_message_genai(diff)
        print(message)

    return 0

if __name__ == "__main__":
    sys.exit(main())
