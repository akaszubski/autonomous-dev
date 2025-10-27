# GenAI Integration Quick Reference

**For**: Developers planning GenAI enhancements to autonomous-dev hooks
**Updated**: 2025-10-27

---

## At a Glance

| Hook | Why GenAI? | What to Ask Claude | Impact |
|------|-----------|------------------|--------|
| **security_scan.py** | Reduce false positives | "Is this real secret or test data?" | HIGH |
| **auto_generate_tests.py** | Semantic intent detection | "Is this implementing a feature or refactoring?" | HIGH |
| **auto_update_docs.py** | Smart complexity assessment | "Are these changes simple or complex?" | MEDIUM-HIGH |
| **validate_docs_consistency.py** | Semantic description validation | "Does description match implementation?" | MEDIUM |
| **auto_fix_docs.py** | Smart auto-fixing | "Generate description for this command" | HIGH |

---

## Implementation Priority

### Phase 1 (Week 1) - Start Here
```
security_scan.py + auto_generate_tests.py
- Highest impact
- Proven pattern exists (validate_readme_with_genai.py)
- 1-2 days each
- ~4 days total
```

### Phase 2 (Week 2-3)
```
auto_update_docs.py + validate_docs_consistency.py
- Medium complexity
- 2-3 days each
- ~5 days total
```

### Phase 3 (Week 3-4)
```
auto_fix_docs.py
- Most complex
- 3-5 days
```

---

## Code Template (Refactored - v2.0)

**Updated**: All hooks now use shared utility pattern for maintainability.

```python
from genai_utils import GenAIAnalyzer, parse_binary_response
from genai_prompts import SECRET_ANALYSIS_PROMPT

# Initialize analyzer (with feature flag support)
analyzer = GenAIAnalyzer(
    use_genai=os.environ.get("GENAI_SECURITY_SCAN", "true").lower() == "true"
)

def analyze_secret_context(line: str, secret_type: str) -> bool:
    """Use GenAI to determine if secret is real or test data."""
    response = analyzer.analyze(
        SECRET_ANALYSIS_PROMPT,
        line=line,
        secret_type=secret_type,
        variable_name="N/A"
    )

    if response:
        is_real = parse_binary_response(
            response,
            true_keywords=["REAL", "LIKELY_REAL"],
            false_keywords=["FAKE"]
        )
        if is_real is not None:
            return is_real

    return _heuristic_fallback(line, secret_type)
```

**Key Features**:
- ✅ Centralized prompts in `genai_prompts.py`
- ✅ Shared analyzer in `genai_utils.py`
- ✅ 70% code reduction per hook
- ✅ Single source of truth for prompts
- ✅ Consistent error handling

---

## Hook-by-Hook Integration Guide

### 1. security_scan.py

**Current Flow**:
```
Regex match → Flag as violation
```

**Enhanced Flow**:
```
Regex match → Analyze context with Claude → 
  If real: Flag violation
  If test: Allow (or warn)
```

**Claude Question**:
```
Is this a real API key or test/example data?

Variable name: {var_name}
Comment: {comment}
Context: {surrounding_code}

Answer: REAL / TEST / UNCLEAR
Confidence: HIGH / MEDIUM / LOW
```

**Example Implementation**:
```python
def analyze_secret_context(line: str, var_name: str, comment: str) -> bool:
    """Determine if matched secret is real or fake."""
    question = f"""Is this a real API key or test/example data?

Variable: {var_name}
Comment: {comment}
Code: {line}

Answer only: REAL or FAKE"""
    
    analysis = analyze_with_genai(line, question)
    return "REAL" in analysis.upper() if analysis else True
```

---

### 2. auto_generate_tests.py

**Current Flow**:
```
Keyword matching → detect feature/refactor
```

**Enhanced Flow**:
```
Keyword matching → Claude semantic analysis → 
  Classify: IMPLEMENT / REFACTOR / UNCLEAR →
  Route to test-master or skip
```

**Claude Question**:
```
Classify this development task:

User statement: "{user_prompt}"

Is the user:
1. Implementing a NEW FEATURE (requires TDD)?
2. REFACTORING existing code (skip TDD)?
3. Updating DOCUMENTATION (skip TDD)?
4. Fixing a BUG (requires minimal TDD)?

Classification: IMPLEMENT | REFACTOR | DOCS | BUG | UNCLEAR
Confidence: HIGH / MEDIUM / LOW
Reasoning: [2-3 sentences]
```

**Example Implementation**:
```python
def classify_feature_intent(user_prompt: str) -> str:
    """Classify if user is implementing feature or refactoring."""
    question = f"""Classify this task:

"{user_prompt}"

Answer: IMPLEMENT or REFACTOR or DOCS"""
    
    analysis = analyze_with_genai(user_prompt, question)
    if analysis and "IMPLEMENT" in analysis.upper():
        return "IMPLEMENT"
    return "REFACTOR"  # Default to skip
```

---

### 3. auto_update_docs.py

**Current Flow**:
```
Count API changes → Simple heuristic → auto-fix or suggest
```

**Enhanced Flow**:
```
Detect API changes → Claude semantic analysis →
  Assess complexity → Decide auto-fix or suggest
```

**Claude Question**:
```
Analyze these API changes for documentation impact:

New functions ({count}):
{list_functions}

New classes ({count}):
{list_classes}

Breaking changes ({count}):
{list_breaking}

Assess complexity:
1. Can this be auto-documented? (SIMPLE / COMPLEX)
2. Are there breaking changes? (YES / NO)
3. Documentation priority? (HIGH / MEDIUM / LOW)

Classification: SIMPLE | COMPLEX
Explanation: [2-3 sentences]
```

**Example Implementation**:
```python
def assess_change_complexity(changes: dict) -> str:
    """Assess if API changes are simple or complex."""
    question = f"""These API changes are:
    
{len(changes['new_functions'])} new functions
{len(changes['new_classes'])} new classes
{len(changes['breaking'])} breaking changes

Simple (auto-fixable) or Complex (needs review)?
Answer: SIMPLE or COMPLEX"""
    
    analysis = analyze_with_genai(str(changes), question)
    return "SIMPLE" if "SIMPLE" in analysis.upper() else "COMPLEX"
```

---

### 4. validate_docs_consistency.py

**Current Flow**:
```
Count matches → exact match or fail
```

**Enhanced Flow**:
```
Count matches → Semantic description validation →
  Check if descriptions are accurate
```

**Claude Question**:
```
Does this description match the actual implementation?

Description: "{description}"

Implementation code:
{code_snippet}

Does the description accurately represent what this {type} does?
Answer: ACCURATE | MISLEADING | UNCLEAR
Issues: [list any accuracy problems]
```

**Example Implementation**:
```python
def validate_description_accuracy(description: str, code: str, type_: str) -> bool:
    """Validate if description matches implementation."""
    question = f"""Does this {type_} description match the code?

Description: {description}
Code: {code}

Answer: ACCURATE or MISLEADING"""
    
    analysis = analyze_with_genai(code, question)
    return "ACCURATE" in analysis.upper() if analysis else True
```

---

### 5. auto_fix_docs.py

**Current Flow**:
```
Detect doc changes → check if auto-fixable pattern → auto-fix or block
```

**Enhanced Flow**:
```
Detect doc changes → Claude determines fixability →
  Generate/update docs or suggest manual review
```

**Claude Question**:
```
Generate documentation for this new command:

Command: {command_name}
Code:
{command_code}

Docstring/comments:
{docstring}

Generate:
1. One-line description (10-15 words)
2. Usage example
3. Prerequisites (if any)

Format as markdown section."""

**Example Implementation**:
```python
def generate_command_doc(name: str, code: str, docstring: str) -> str:
    """Generate documentation for new command."""
    question = f"""Generate docs for: {name}

Code: {code}

Generate a one-line description and brief usage."""
    
    analysis = analyze_with_genai(code, question)
    return analysis or f"### /{name}\n[Description needed]"
```

---

## Testing GenAI Integration

### Unit Test Template

```python
import pytest
from unittest.mock import patch, MagicMock

def test_genai_analysis_with_real_secret():
    """Test that GenAI correctly identifies real secrets."""
    result = analyze_secret_context(
        'api_key = "sk-proj-realkey123456"',
        'api_key',
        'Real API key'
    )
    assert result is True  # Should identify as real

def test_genai_analysis_with_fake_secret():
    """Test that GenAI correctly identifies fake secrets."""
    result = analyze_secret_context(
        'test_key = "sk-proj-fake123456"  # FAKE FOR TESTING',
        'test_key',
        'FAKE FOR TESTING'
    )
    assert result is False  # Should identify as fake

def test_genai_fallback_when_sdk_missing():
    """Test graceful degradation if SDK not installed."""
    with patch('anthropic.Anthropic', side_effect=ImportError):
        result = analyze_with_genai("content", "question")
        assert result is None  # Should return None, not crash
```

---

## Performance Considerations

### Latency Budget

- **Per hook call**: 100-500ms (typical API response)
- **Max acceptable**: 1-2 seconds per hook
- **Recommendation**: Only call for ambiguous cases, not every file

### Optimization Strategies

1. **Caching**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def analyze_with_cache(content: str, question: str) -> Optional[str]:
    """Cached version of GenAI analysis."""
    return analyze_with_genai(content, question)
```

2. **Batching**
```python
# Instead of analyzing each file separately
# Collect ambiguous cases and ask Claude in bulk
ambiguous_cases = [f1, f2, f3]
question = f"Classify these {len(ambiguous_cases)} cases: ..."
```

3. **Conditional Calling**
```python
# Only call GenAI if pattern matching was ambiguous
if result == UNCERTAIN:
    analysis = analyze_with_genai(...)
```

---

## Debugging GenAI Decisions

### Enable Logging

```python
import logging

logger = logging.getLogger(__name__)

def analyze_with_logging(content: str, question: str) -> Optional[str]:
    """Analyze with detailed logging."""
    logger.debug(f"GenAI Question: {question[:100]}...")
    logger.debug(f"Content: {content[:200]}...")
    
    result = analyze_with_genai(content, question)
    
    logger.info(f"GenAI Result: {result[:100]}...")
    return result
```

### Common Issues

**Issue**: GenAI returns unexpected classification
```python
# Solution: Add explicit categories + ask for confidence
question = "Classify as: REAL, FAKE, or UNCLEAR. "
         + "Confidence: HIGH, MEDIUM, LOW"
```

**Issue**: GenAI too slow
```python
# Solution: Timeout + fallback
try:
    result = analyze_with_genai(content, question, timeout=2)
except TimeoutError:
    logger.warning("GenAI timeout, using fallback")
    result = fallback_heuristic(content)
```

**Issue**: GenAI inconsistent
```python
# Solution: Cache results + use temperature=0 for deterministic
# Note: Haiku defaults are good, but temperature=0 makes deterministic
```

---

## Success Metrics

### Before/After Comparison

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| False positive rate (security) | ~15% | < 5% | < 3% |
| Manual doc-syncer invocations | 60% of API changes | 30% | 20% |
| Test generation accuracy | 85% | 95%+ | 98% |
| Documentation validation time | 30s | 10s | < 5s |
| Hook execution time | < 1s | 1-2s | < 3s |

---

## Migration Path

### Stage 1: Add GenAI Layer (Non-blocking)
```python
# Make GenAI optional, don't block on failures
enhanced_result = analyze_with_genai(...) or fallback_result
```

### Stage 2: Use GenAI for Decisions
```python
# Use GenAI analysis to inform decisions
if genai_suggests_simple:
    auto_fix()
else:
    suggest_manual_review()
```

### Stage 3: Deprecate Old Heuristics
```python
# Replace old pattern matching with GenAI
# Old: if len(functions) > 5 → complex
# New: if genai_assessment == COMPLEX → complex
```

---

## Resources

- **Existing Example**: `/plugins/autonomous-dev/hooks/validate_readme_with_genai.py`
- **SDK Docs**: https://docs.anthropic.com/
- **Model**: claude-haiku-4-5-20251001 (fast, cheap, sufficient)
- **Max Tokens**: 500 (for hook responses)
- **Full Analysis**: `/docs/HOOKS-GENAI-OPPORTUNITIES.md`

---

## Questions?

Refer to full analysis: `/docs/HOOKS-GENAI-OPPORTUNITIES.md`
