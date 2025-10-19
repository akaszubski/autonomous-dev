

**Run security vulnerability scan (secrets detection, dependency check, code analysis)**# Security Scan

Scan code for security vulnerabilities, exposed secrets, and dependency issues.

## Usage

```bash
/security-scan
```

## What This Does

Runs multiple security checks:

### 1. Secrets Detection
Scans for hardcoded:
- API keys
- Passwords
- Tokens
- Connection strings

```bash
grep -rn "api_key\|password\|secret\|token" --include="*.py" --include="*.js" --include="*.ts" .
```

### 2. Code Security Analysis
**Python**:
```bash
bandit -r src/ -ll  # Medium/High severity only
```

**JavaScript/TypeScript**:
```bash
npm audit
```

### 3. Dependency Vulnerabilities
```bash
# Python
pip install safety
safety check

# JavaScript
npm audit
```

## Example Output

```
Running security scan...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Secrets Detection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scanning for: API keys, passwords, tokens, secrets...
✅ No hardcoded secrets found

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 Code Security Analysis (Bandit)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scanning 45 Python files...

Medium Severity Issues:
- src/utils.py:67 - subprocess with shell=True (B602)
  Fix: Use shell=False and pass args as list

✅ No critical or high severity issues

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 Dependency Vulnerabilities
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Checking Python dependencies...
✅ All dependencies up to date

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 Critical: 0
🟡 Medium: 1 (fix recommended)
🟢 Low/Info: 0

⚠️  Fix medium severity issue before deployment
```

## Severity Levels

| Severity | Priority | Action |
|----------|----------|--------|
| 🔴 Critical | Block deployment | MUST fix immediately |
| 🟡 High | Fix soon | Should fix before release |
| 🟠 Medium | Improvement | Fix when possible |
| 🟢 Low/Info | FYI | Optional fix |

## Common Issues Detected

### 1. Hardcoded Secrets
```python
# ❌ WRONG
api_key = "sk-ant-1234567890"

# ✅ CORRECT
import os
api_key = os.getenv("ANTHROPIC_API_KEY")
```

### 2. Command Injection
```python
# ❌ WRONG
subprocess.run(f"ls {user_input}", shell=True)

# ✅ CORRECT
subprocess.run(["ls", user_input], shell=False)
```

### 3. SQL Injection
```python
# ❌ WRONG
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# ✅ CORRECT
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### 4. Path Traversal
```python
# ❌ WRONG
file_path = f"/data/{user_filename}"

# ✅ CORRECT
from pathlib import Path
base = Path("/data").resolve()
file_path = (base / user_filename).resolve()
if not file_path.is_relative_to(base):
    raise ValueError("Invalid path")
```

## When to Use

- Before committing code
- After implementing features
- Before deployment
- When handling user input
- When using external libraries

## Auto-Run vs Manual

This command is **manual** (you control when it runs).

**Alternative**: The `security_scan.py` hook can run automatically:
- Before git commit (pre-commit hook)
- Before deployment (CI/CD)

**Recommended**: Use `/security-scan` manually for full control.

## Troubleshooting

### Scanners not found
```bash
# Install Python security tools
pip install bandit safety

# Install JS security tools
npm install
```

### False positives
- Review each finding carefully
- Some patterns may be safe in context (e.g., example code in comments)
- Add exclusions to config if needed (`bandit.yaml`)

### Too many issues
- Prioritize by severity (critical → high → medium → low)
- Fix one category at a time
- Re-run `/security-scan` after fixes

## Related Commands

- `/test` - Run tests before security scan
- `/full-check` - Run all checks (format + test + security)
- `/commit` - Commit after security scan passes


**Run this before committing to ensure no security vulnerabilities are introduced.**
