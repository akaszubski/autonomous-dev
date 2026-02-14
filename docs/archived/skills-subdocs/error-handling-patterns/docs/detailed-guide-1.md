# Error Handling Patterns - Detailed Guide

## When This Skill Activates

- Raising custom exceptions
- Handling errors and validation failures
- Implementing security audit logging
- Designing graceful degradation
- Formatting error messages
- Creating exception hierarchies
- Keywords: "error", "exception", "validation", "raise", "try", "catch", "audit"

---

## Exception Hierarchy

All custom exceptions should follow a domain-specific hierarchy pattern.

### Pattern

```
BaseException (Python built-in)
└── Exception (Python built-in)
    └── AutonomousDevError (Project base error)
        ├── SecurityError (Domain: Security)
        │   ├── PathTraversalError (Specific: CWE-22)
        │   ├── InvalidPathError (Specific: CWE-59)
        │   └── LogInjectionError (Specific: CWE-117)
        ├── ValidationError (Domain: Validation)
        │   ├── InvalidFormatError (Specific: Format validation)
        │   ├── ParseError (Specific: Parsing failures)
        │   └── ProjectAlignmentError (Specific: PROJECT.md validation)
        ├── GitError (Domain: Git operations)
        │   ├── GitNotAvailableError (Specific: Git not installed)
        │   ├── MergeConflictError (Specific: Merge conflicts)
        │   └── GitCredentialsError (Specific: Authentication)
        └── AgentError (Domain: Agent operations)
            ├── AgentInvocationError (Specific: Agent failures)
            ├── AgentTimeoutError (Specific: Timeout)
            └── AgentOutputError (Specific: Invalid output)
```

### Base Error Class

All project errors should inherit from a common base:

```python
class AutonomousDevError(Exception):
    """Base exception for autonomous-dev plugin.

    All custom exceptions should inherit from this base class to enable
    consistent error handling and logging across the system.

    See error-handling-patterns skill for exception hierarchy and usage.
    """

    def __init__(self, message: str, context: dict = None):
        """Initialize error with message and optional context.

        Args:
            message: Human-readable error description
            context: Optional dict with error context (paths, values, etc.)
        """
        super().__init__(message)
        self.context = context or {}

    def __str__(self):
        """Format error with context if available."""
        if self.context:
            context_str = "\n".join(f"  {k}: {v}" for k, v in self.context.items())
            return f"{super().__str__()}\nContext:\n{context_str}"
        return super().__str__()
```

### Example: Domain-Specific Errors

See `examples/domain-error-example.py` for complete implementations.

---

## Error Message Format
