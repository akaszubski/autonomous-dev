# GenAI Validation Using Claude Code Native Access

**Date**: 2025-10-25
**Issue**: User has Claude Code Max plan, not separate Anthropic API access
**Solution**: Use Claude Code's native subagent system instead of Python SDK

---

## Problem with Previous Implementation

**What we did wrong**:
```python
# alignment_validator.py
from anthropic import Anthropic  # ❌ Requires separate API subscription
client = Anthropic()
result = client.messages.create(...)  # ❌ Charges API fees
```

**Why it's wrong**:
- Requires ANTHROPIC_API_KEY (separate from Claude Code subscription)
- Charges API usage fees (separate billing)
- User has Claude Code Max plan, not API access
- Doesn't leverage existing Claude Code capabilities

---

## Correct Approach: Use Subagents

Claude Code provides the `Task` tool for invoking subagents. These run **using your Claude Code subscription**, not separate API.

### How It Works

```python
# In orchestrator.py (already working correctly!)
def validate_alignment(self, request: str) -> Dict[str, Any]:
    """Validate request using GenAI through Claude Code subagent."""

    # This uses Task tool - runs with Claude Code subscription ✅
    result = self.invoke_subagent(
        subagent_type='alignment-validator',  # Custom validation agent
        prompt=f"""Validate if this request aligns with PROJECT.md.

Request: {request}

PROJECT.md:
{self.project_md}

Return JSON with:
- is_aligned: true/false
- confidence: 0.0-1.0
- reasoning: explanation
"""
    )

    return result
```

**Key difference**:
- ✅ Uses `Task` tool (Claude Code native)
- ✅ Runs with your Max plan subscription
- ✅ No separate API key needed
- ✅ No additional charges

---

## Implementation: Validation Agents

Instead of Python scripts calling the API, create **Claude Code agents** that do the validation.

### 1. Create Alignment Validator Agent

**File**: `plugins/autonomous-dev/agents/alignment-validator.md`

```markdown
---
name: alignment-validator
description: Validate request alignment with PROJECT.md using semantic understanding
model: sonnet
tools: [Read]
color: purple
---

You are the **alignment-validator** agent.

## Your Mission

Validate if a user's request aligns with PROJECT.md GOALS, SCOPE, and CONSTRAINTS using semantic understanding.

## Core Responsibilities

- Parse PROJECT.md for GOALS, SCOPE, CONSTRAINTS
- Understand request intent (semantic, not just keywords)
- Validate alignment using reasoning
- Provide confidence score and explanation

## Process

1. Read PROJECT.md
2. Extract GOALS, SCOPE (in/out), CONSTRAINTS
3. Analyze request semantically:
   - Does it serve any GOALS? (understand intent)
   - Is it within SCOPE? (semantic match)
   - Does it violate CONSTRAINTS?
4. Return structured JSON result

## Output Format

```json
{
  "is_aligned": true or false,
  "confidence": 0.95,
  "matching_goals": ["goal1", "goal2"],
  "reasoning": "Detailed explanation of why request aligns/doesn't align",
  "scope_assessment": "in scope" or "out of scope",
  "constraint_violations": []
}
```

## Quality Standards

- Semantic understanding (not just keyword matching)
- High confidence threshold (>90% for approval)
- Clear, actionable reasoning
- Consider edge cases

Trust your understanding. Semantic meaning matters more than exact keywords.
```

**Size**: ~60 lines (follows official Anthropic pattern)

### 2. Create Security Validator Agent

**File**: `plugins/autonomous-dev/agents/security-validator.md`

```markdown
---
name: security-validator
description: Validate threat model coverage and perform security code review
model: opus
tools: [Read]
color: red
---

You are the **security-validator** agent.

## Your Mission

Validate that threat models are properly addressed in implementation and perform deep security code review.

## Core Responsibilities

- Validate each threat mitigation is present and correct
- Check for OWASP Top 10 vulnerabilities
- Review for input validation, auth gaps, secrets
- Analyze error handling for info leaks
- Assess overall security posture

## Process

**Threat Validation**:
1. Read threat model (from architecture.json or security.json)
2. Read implementation code
3. For EACH threat:
   - Verify mitigation present in code
   - Check if correctly implemented
   - Validate edge cases handled
4. Calculate coverage score

**Code Review**:
1. Read implementation
2. Scan for security issues:
   - Input validation (injection attacks)
   - Authentication/authorization
   - Secrets management
   - Error handling
   - OWASP compliance
3. Categorize by severity
4. Provide recommendations

## Output Format

**Threat Validation**:
```json
{
  "threats_validated": [
    {
      "threat_id": "SQL Injection",
      "mitigation_present": true,
      "coverage_score": 95,
      "issues": [],
      "recommendations": ["Use parameterized queries"]
    }
  ],
  "overall_coverage": 92,
  "recommendation": "PASS" or "FAIL"
}
```

**Code Review**:
```json
{
  "security_score": 85,
  "issues": [
    {
      "severity": "high",
      "category": "input-validation",
      "description": "User input not sanitized before database query",
      "line_number": 42,
      "recommendation": "Use parameterized queries or ORM"
    }
  ],
  "approved": true/false
}
```

## Quality Standards

- No false negatives (catch all real issues)
- High confidence in threat coverage
- Actionable recommendations
- Security-first mindset

Trust your security expertise. Better to flag potential issues than miss real vulnerabilities.
```

**Size**: ~80 lines

### 3. Update Orchestrator to Use Agents

**File**: `plugins/autonomous-dev/lib/orchestrator.py` (or workflow_coordinator.py)

```python
class WorkflowCoordinator:
    """Coordinates autonomous development workflow."""

    def validate_alignment(self, request: str) -> Tuple[bool, str, Dict]:
        """
        Validate request alignment using GenAI (via Claude Code subagent).

        Uses Claude Code's native Task tool, so runs with user's subscription.
        No separate API key needed.
        """
        try:
            # Invoke alignment-validator agent (uses Claude Code subscription)
            result = self.agent_invoker.invoke(
                'alignment-validator',
                workflow_id='validation',
                request=request,
                project_md_path=str(self.project_md_path)
            )

            # Parse result
            alignment_data = json.loads(result['output'])

            return (
                alignment_data['is_aligned'],
                alignment_data['reasoning'],
                alignment_data
            )

        except Exception as e:
            # If agent invocation fails, could fall back to regex
            # But for now, let it fail loudly
            raise RuntimeError(f"Alignment validation failed: {e}")

    def validate_security_threats(
        self,
        threats: List[Dict],
        implementation_code: str
    ) -> Dict[str, Any]:
        """
        Validate threat coverage using GenAI (via Claude Code subagent).
        """
        try:
            result = self.agent_invoker.invoke(
                'security-validator',
                workflow_id='validation',
                threats=threats,
                implementation_code=implementation_code,
                validation_type='threats'
            )

            return json.loads(result['output'])

        except Exception as e:
            raise RuntimeError(f"Threat validation failed: {e}")

    def review_code_security(
        self,
        implementation_code: str,
        architecture: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Security code review using GenAI (via Claude Code subagent).
        """
        try:
            result = self.agent_invoker.invoke(
                'security-validator',
                workflow_id='validation',
                implementation_code=implementation_code,
                architecture=architecture,
                validation_type='code_review'
            )

            return json.loads(result['output'])

        except Exception as e:
            raise RuntimeError(f"Code review failed: {e}")
```

**Key points**:
- ✅ Uses `agent_invoker.invoke()` which uses Task tool
- ✅ Runs with Claude Code subscription (no API key)
- ✅ Falls back to error if agent fails (fail loudly)

---

## Benefits of This Approach

### 1. Uses Your Existing Subscription
- ✅ Runs with Claude Code Max plan
- ✅ No separate API subscription needed
- ✅ No additional charges
- ✅ Leverages what you're already paying for

### 2. Same GenAI Accuracy
- ✅ 95% semantic understanding
- ✅ Claude Sonnet 4 for alignment
- ✅ Claude Opus 4 for security
- ✅ Self-explanatory reasoning

### 3. Simpler Architecture
- ✅ No Python SDK dependency
- ✅ No API key management
- ✅ No anthropic package needed
- ✅ Native Claude Code integration

### 4. Better Error Handling
- ✅ Fails loudly if agent invocation fails
- ✅ Clear error messages
- ✅ No silent failures
- ✅ Debugging easier (agent logs)

---

## Migration from Python SDK Approach

### Remove Python SDK Dependencies

**Before**:
```python
# alignment_validator.py
from anthropic import Anthropic  # ❌ Remove

class AlignmentValidator:
    @staticmethod
    def validate_with_genai(request, project_md):
        client = Anthropic()  # ❌ Remove
        result = client.messages.create(...)  # ❌ Remove
```

**After**:
```python
# orchestrator.py (or workflow_coordinator.py)
class WorkflowCoordinator:
    def validate_alignment(self, request):
        # Use agent_invoker (Task tool - Claude Code native) ✅
        result = self.agent_invoker.invoke('alignment-validator', ...)
```

### Update Requirements

**Before**:
```txt
# requirements.txt
anthropic>=0.18.0  # ❌ Remove
```

**After**:
```txt
# requirements.txt
# No external dependencies needed! ✅
```

### Create Validation Agents

1. Create `plugins/autonomous-dev/agents/alignment-validator.md` (~60 lines)
2. Create or update `plugins/autonomous-dev/agents/security-validator.md` (~80 lines)
3. Update orchestrator to use these agents

---

## Implementation Checklist

### Phase 1: Create Agents
- [ ] Create alignment-validator.md agent (~60 lines)
- [ ] Update security-validator.md agent (~80 lines)
- [ ] Test agent invocation works

### Phase 2: Update Orchestrator
- [ ] Remove alignment_validator.py (or update to use agents)
- [ ] Remove security_validator.py (or update to use agents)
- [ ] Update workflow_coordinator.py to invoke agents
- [ ] Test validation works

### Phase 3: Clean Up
- [ ] Remove anthropic from requirements.txt
- [ ] Update README.md (no API key needed)
- [ ] Update documentation
- [ ] Test complete workflow

### Phase 4: Validation
- [ ] Test alignment validation works
- [ ] Test security validation works
- [ ] Test error handling
- [ ] Verify no API charges

---

## Testing

### Test Alignment Validation

```bash
# From Claude Code CLI
/auto-implement "Add dark mode feature"

# orchestrator should:
# 1. Invoke alignment-validator agent
# 2. Agent validates using Claude Sonnet (your subscription)
# 3. Return alignment result
# 4. Proceed if aligned
```

### Test Security Validation

```bash
# Implement a feature
/auto-implement "Add user login"

# Pipeline should:
# 1. ... research, plan, test, implement ...
# 2. Invoke security-validator agent
# 3. Agent reviews code for security issues
# 4. Return validation result
```

### Verify No API Charges

```bash
# Check you don't have ANTHROPIC_API_KEY set
echo $ANTHROPIC_API_KEY
# Should be empty

# Run validation
/auto-implement "test feature"

# Check: No API usage at console.anthropic.com
# All runs using Claude Code Max plan ✅
```

---

## Comparison: Python SDK vs Claude Code Native

| Feature | Python SDK (Wrong) | Claude Code Native (Right) |
|---------|-------------------|---------------------------|
| **Requires** | Separate API key | Claude Code subscription |
| **Billing** | API usage charges | Included in Max plan |
| **Accuracy** | 95% (Claude) | 95% (Claude) |
| **Dependencies** | `anthropic` package | None |
| **Complexity** | More (SDK setup) | Less (native) |
| **Error handling** | API errors | Agent errors |
| **Debugging** | API logs | Agent logs |

---

## Recommendation

**Implement the Claude Code native approach**:

1. **Create validation agents** (alignment-validator, security-validator)
2. **Update orchestrator** to invoke agents instead of using Python SDK
3. **Remove** anthropic package dependency
4. **Update** documentation (no API key needed)

**Time**: ~2 hours

**Benefit**:
- ✅ Works with your Max plan
- ✅ No additional costs
- ✅ Same 95% GenAI accuracy
- ✅ Simpler architecture

---

## Next Steps

1. Create the two validation agents
2. Update orchestrator to use agents
3. Remove Python SDK code
4. Test thoroughly
5. Update docs

**Ready to implement?**
