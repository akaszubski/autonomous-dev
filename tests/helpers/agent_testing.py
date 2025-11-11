"""
Helper utilities for agent testing in Issue #72 integration tests.

Provides functions to invoke agents and validate their outputs
against expected formats from agent-output-formats skill.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import re
import json


def invoke_test_agent(agent_name: str, task: str) -> str:
    """
    Mock agent invocation for testing.

    In real implementation, this would invoke the agent via Claude Code.
    For testing, we return mock outputs that follow expected formats.

    Args:
        agent_name: Name of agent to invoke
        task: Task description for agent

    Returns:
        Simulated agent output
    """
    # Mock outputs that follow expected formats
    mock_outputs = {
        "researcher": """## Patterns Found

- **Pattern 1**: Async/await for concurrent operations
- **Pattern 2**: Context managers for resource cleanup
- **Pattern 3**: Type hints for better IDE support

## Best Practices

- Use asyncio.gather() for parallel tasks
- Always use try/finally for cleanup
- Add type hints to public APIs

## Security Considerations

- Validate all async inputs
- Timeout long-running operations
- Handle cancellation gracefully

## Recommendations

1. Start with simple async functions
2. Use asyncio.run() for top-level entry
3. Test with pytest-asyncio

## References

- PEP 492: Coroutines with async/await
- asyncio documentation
- Real Python async guide
""",
        "planner": """## Architecture Plan

### Overview
Implementation plan for async API endpoints.

### Components
1. AsyncAPIHandler - Main handler for async requests
2. TaskQueue - Queue for background tasks
3. ResponseCache - Cache for async results

### Implementation Steps

**Step 1**: Create AsyncAPIHandler (2 hours)
- Define async request/response types
- Implement handler registration
- Add error handling

**Step 2**: Implement TaskQueue (3 hours)
- Queue data structure
- Worker pool management
- Task status tracking

**Step 3**: Add ResponseCache (1 hour)
- Cache key generation
- TTL-based expiration
- Cache invalidation

### Dependencies
- Step 2 depends on Step 1
- Step 3 can run in parallel

### Testing Strategy
- Unit tests for each component
- Integration tests for full workflow
- Load tests for performance

### Success Criteria
- All tests pass
- <100ms latency for cached responses
- Handles 1000 concurrent requests
""",
        "test-master": """## Test Suite

### Unit Tests

```python
def test_async_handler_processes_request():
    '''Test that async handler processes valid request.'''
    handler = AsyncAPIHandler()
    request = {"task": "process_data", "data": [1, 2, 3]}

    result = await handler.handle(request)

    assert result["status"] == "success"
    assert "task_id" in result
```

```python
def test_async_handler_validates_input():
    '''Test that async handler validates input.'''
    handler = AsyncAPIHandler()
    invalid_request = {"invalid": "data"}

    with pytest.raises(ValueError):
        await handler.handle(invalid_request)
```

### Integration Tests

```python
def test_full_async_workflow():
    '''Test complete async request workflow.'''
    handler = AsyncAPIHandler()
    queue = TaskQueue()
    cache = ResponseCache()

    # Submit task
    task_id = await handler.submit({"task": "process"})

    # Wait for completion
    result = await queue.wait_for_completion(task_id)

    # Verify cached
    cached = cache.get(task_id)
    assert cached == result
```

## Test Coverage

Target: 80%+ on new code
Focus: Error handling, edge cases, concurrent access
""",
        "quality-validator": """Quality Validation Report

Overall Score: 8/10 (PASS)

✅ Strengths:
- Code follows Python standards (type hints, docstrings)
- Good test coverage (85% on new code)
- Clean separation of concerns

⚠️ Issues:
- async_handler.py:42 Missing error handling for network timeout
- task_queue.py:156 TODO comment should be resolved

🔧 Recommended Actions:
1. Add timeout handling in async_handler.py (line 42)
2. Resolve or remove TODO in task_queue.py (line 156)
3. Consider adding more integration tests for error scenarios
""",
        "advisor": """RECOMMENDATION: PROCEED WITH CAUTION

Alignment Score: 7/10
Why: Feature aligns with performance goals but adds complexity

Complexity Assessment:
- Estimated LOC: 450
- Files affected: 5 (3 new, 2 modified)
- Time estimate: 8-10 hours

Pros:
- Improves API responsiveness significantly
- Follows industry best practices
- Good test coverage planned

Cons:
- Adds async complexity to codebase
- Requires team training on async patterns
- More difficult to debug

Alternatives:
1. Simple caching: Add response cache only (2 hours, less complexity)
2. Queue-only: Use task queue without full async (4 hours, moderate complexity)

Recommendation: Proceed but invest in team training on async/await patterns. Consider starting with Alternative 1 (caching) to validate benefit before full async implementation.
""",
        "alignment-validator": json.dumps({
            "aligned": True,
            "confidence": 0.85,
            "reasoning": {
                "serves_goals": [
                    "Performance: Async API improves response times",
                    "Scalability: Handles more concurrent requests"
                ],
                "within_scope": "API performance optimization is explicitly in scope",
                "respects_constraints": "Implementation stays within 500 LOC constraint"
            },
            "concerns": [
                "Team async expertise needed"
            ],
            "suggestion": ""
        }, indent=2),
        "project-progress-tracker": json.dumps({
            "feature_completed": "Add async API support",
            "maps_to_goal": "Performance & scalability",
            "scope_area": "API",
            "goal_progress": {
                "goal_name": "Performance & scalability",
                "previous_progress": "40%",
                "new_progress": "60%",
                "features_completed": 3,
                "features_total": 5,
                "status": "in_progress"
            },
            "project_md_updates": {
                "section": "GOALS - Performance & scalability",
                "changes": [
                    "Updated 'Performance' goal: 40% → 60% (3/5 features)",
                    "Added 'Add async API support' to completed features"
                ]
            },
            "next_priorities": [
                {
                    "feature": "Add response caching",
                    "goal": "Performance & scalability",
                    "rationale": "Completes performance goal (would be 80% done)",
                    "estimated_effort": "medium"
                },
                {
                    "feature": "Add rate limiting",
                    "goal": "Security & reliability",
                    "rationale": "Addresses underserved goal (currently 20%)",
                    "estimated_effort": "high"
                }
            ],
            "summary": "Feature 'Add async API support' advances 'Performance' goal to 60% (3/5). Recommend focusing on completing performance goal or addressing security goal next."
        }, indent=2)
    }

    return mock_outputs.get(agent_name, f"Mock output for {agent_name}: {task}")


def validate_output_format(output: str, format_type: str, strict: bool = True) -> bool:
    """
    Validate agent output against expected format.

    Args:
        output: Agent output string
        format_type: Expected format type (research, plan, validation, etc.)
        strict: If True, only allow defined sections; if False, allow extra sections

    Returns:
        True if output matches expected format
    """
    # Define required sections for each format type
    required_sections = {
        "research": [
            "## Patterns Found",
            "## Best Practices",
            "## Security Considerations",
            "## Recommendations"
        ],
        "plan": [
            "## Architecture Plan",
            "## Components",
            "## Implementation Steps",
            "## Testing Strategy"
        ],
        "test": [
            "## Test Suite",
            "## Test Coverage"
        ],
        "validation": [
            "Overall Score:",
            "✅ Strengths:",
            "🔧 Recommended Actions:"
        ],
        "advisory": [
            "RECOMMENDATION:",
            "Alignment Score:",
            "Complexity Assessment:",
            "Pros:",
            "Cons:",
            "Alternatives:"
        ]
    }

    sections = required_sections.get(format_type, [])

    # Check all required sections are present
    for section in sections:
        if section not in output:
            return False

    return True


def validate_research_output(output: str) -> bool:
    """
    Validate research agent output.

    Args:
        output: Research agent output

    Returns:
        True if output is valid research format
    """
    return validate_output_format(output, "research")


def validate_plan_output(output: str) -> bool:
    """
    Validate planner agent output.

    Args:
        output: Planner agent output

    Returns:
        True if output is valid plan format
    """
    return validate_output_format(output, "plan")


def validate_test_output(output: str) -> bool:
    """
    Validate test-master agent output.

    Args:
        output: Test-master agent output

    Returns:
        True if output is valid test format
    """
    return validate_output_format(output, "test")


def validate_quality_report(output: str) -> bool:
    """
    Validate quality-validator agent output.

    Args:
        output: Quality-validator agent output

    Returns:
        True if output is valid validation report format
    """
    return validate_output_format(output, "validation")


def validate_advisory_output(output: str) -> bool:
    """
    Validate advisor agent output.

    Args:
        output: Advisor agent output

    Returns:
        True if output is valid advisory format
    """
    return validate_output_format(output, "advisory")


def validate_json_output(output: str, required_keys: List[str]) -> bool:
    """
    Validate JSON output has required keys.

    Args:
        output: JSON output string
        required_keys: List of required top-level keys

    Returns:
        True if JSON is valid and has required keys
    """
    try:
        data = json.loads(output)
        return all(key in data for key in required_keys)
    except (json.JSONDecodeError, TypeError):
        return False


def extract_sections(output: str) -> Dict[str, str]:
    """
    Extract sections from agent output.

    Args:
        output: Agent output with markdown sections

    Returns:
        Dictionary mapping section name to content
    """
    sections = {}

    # Split by ## headers
    parts = re.split(r'\n## ', output)

    # First part is preamble
    if parts:
        sections["_preamble"] = parts[0]

    # Parse remaining sections
    for part in parts[1:]:
        lines = part.split('\n', 1)
        if len(lines) >= 1:
            section_name = lines[0].strip()
            section_content = lines[1] if len(lines) > 1 else ""
            sections[section_name] = section_content

    return sections


def count_sections(output: str) -> int:
    """
    Count number of ## sections in output.

    Args:
        output: Agent output

    Returns:
        Number of ## sections
    """
    return len(re.findall(r'^## ', output, re.MULTILINE))
