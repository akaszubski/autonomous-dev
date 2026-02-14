# GitHub CLI (gh) Integration Patterns

Standardized patterns for GitHub operations via gh CLI.

## Prerequisites

- gh CLI installed (`gh --version`)
- Authenticated (`gh auth login`)

## Common Patterns

### Create Issue
```python
subprocess.run(
    ["gh", "issue", "create", "--title", title, "--body", body],
    check=True, timeout=30, shell=False
)
```

### Create PR
```python
subprocess.run(
    ["gh", "pr", "create", "--title", title, "--body", body],
    check=True, timeout=30, shell=False
)
```

### List Issues
```python
result = subprocess.run(
    ["gh", "issue", "list", "--json", "number,title"],
    capture_output=True, text=True, check=True
)
issues = json.loads(result.stdout)
```

See: `examples/github-issue-example.py`
