# Subprocess Safety (CWE-78 Prevention)

Execute external commands safely without command injection vulnerabilities.

## Critical Rules

- ✅ ALWAYS use argument arrays: `["gh", "issue", "create"]`
- ❌ NEVER use `shell=True` with user input
- ✅ ALWAYS whitelist allowed commands
- ✅ ALWAYS set timeouts

## Example

```python
import subprocess

# ✅ SAFE
result = subprocess.run(
    ["gh", "issue", "create", "--title", user_title],
    capture_output=True,
    text=True,
    timeout=30,
    check=True,
    shell=False  # CRITICAL
)

# ❌ DANGEROUS - Command injection!
command = f"gh issue create --title {user_title}"
result = subprocess.run(command, shell=True)  # VULNERABLE!
```

See: `templates/subprocess-executor-template.py`
