---
name: Test Failure (Automated)
about: Automatically created from pytest failure
labels: bug, automated, layer-1
assignees: ''
---

## Test Failure

**Test**: `{{ test_file }}::{{ test_name }}:{{ line_number }}`
**Status**: ❌ FAILED
**Date**: {{ date }}
**Layer**: Layer 1 (pytest)

---

## Error

```
{{ error_message }}
```

## Stack Trace

```
{{ stack_trace }}
```

---

## Reproduction

```bash
# Reproduce the failure
pytest {{ test_file }}::{{ test_name }} -v

# Run with more context
pytest {{ test_file }}::{{ test_name }} -vv -s
```

---

## Context

- **Python**: {{ python_version }}
- **pytest**: {{ pytest_version }}
- **Coverage**: {{ coverage }}%
- **Platform**: {{ platform }}
- **OS**: {{ os_version }}

---

## Suggested Fix

{{ genai_suggestion }}

---

## Related Files

{{ related_files }}

---

## Priority

{{ priority }} - {{ priority_reasoning }}

---

*Auto-created by `/test --track-issues`*
*See: [GITHUB-ISSUES-INTEGRATION.md](docs/GITHUB-ISSUES-INTEGRATION.md)*
