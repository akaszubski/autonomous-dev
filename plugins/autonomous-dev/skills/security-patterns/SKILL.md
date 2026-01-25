---
name: security-patterns
version: 1.1.0
type: knowledge
description: Security best practices, API key management, input validation. Use when handling secrets, user input, or security-sensitive code.
keywords: security, api key, secret, validation, injection, owasp
auto_activate: true
allowed-tools: [Read]
---

# Security Patterns Skill

Security best practices and patterns for secure development.

**See:** [code-examples.md](code-examples.md) for Python implementations
**See:** [templates.md](templates.md) for checklists and config templates

## When This Activates

- API key handling
- User input validation
- File operations
- Security-sensitive code
- Keywords: "security", "api key", "secret", "validate", "input"

---

## API Keys & Secrets

### Environment Variables (REQUIRED)

**Rule:** Never hardcode secrets. Always use environment variables via `.env` files.

```python
# ✅ CORRECT
api_key = os.getenv("ANTHROPIC_API_KEY")

# ❌ WRONG
api_key = "sk-ant-1234567890abcdef"  # NEVER!
```

**See:** [code-examples.md#api-keys--secrets](code-examples.md#api-keys--secrets) for full validation code

---

## Input Validation

### Path Traversal Prevention

**Rule:** Always validate paths are within allowed directories.

```python
# Use is_relative_to() to prevent ../ attacks
if not file_path.is_relative_to(base_dir):
    raise ValueError("Path traversal detected")
```

### Command Injection Prevention

**Rule:** Never use `shell=True`. Pass arguments as lists.

```python
# ✅ CORRECT
subprocess.run([command] + args, shell=False)

# ❌ WRONG
subprocess.run(f"ls {user_input}", shell=True)  # Injection risk!
```

### SQL Injection Prevention

**Rule:** Always use parameterized queries.

```python
# ✅ CORRECT
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))

# ❌ WRONG
cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
```

**See:** [code-examples.md#input-validation](code-examples.md#input-validation) for complete examples

---

## File Operations Security

### Secure Permissions

| Use Case | Permission | Octal |
|----------|------------|-------|
| Sensitive files | `rw-------` | 0o600 |
| Sensitive dirs | `rwx------` | 0o700 |
| Public files | `rw-r--r--` | 0o644 |

### File Upload Validation

- Validate extensions (whitelist only)
- Check file size limits
- Reject executable files

**See:** [code-examples.md#file-operations-security](code-examples.md#file-operations-security)

---

## Cryptographic Operations

### Secure Random

**Rule:** Use `secrets` module for security-sensitive random values.

```python
# ✅ CORRECT
token = secrets.token_hex(32)

# ❌ WRONG
token = str(random.randint(0, 999999))  # Not cryptographically secure!
```

**See:** [code-examples.md#cryptographic-operations](code-examples.md#cryptographic-operations) for password hashing

---

## Logging Security

**Rule:** Never log full secrets. Mask sensitive values.

```python
# ✅ CORRECT
masked_key = api_key[:7] + "***" + api_key[-4:]
logging.info(f"Using key {masked_key}")

# ❌ WRONG
logging.info(f"Using key {api_key}")  # Exposes full key!
```

---

## Dependencies Security

```bash
# Check for vulnerabilities
pip install safety && safety check
# OR
pip install pip-audit && pip-audit
```

---

## Key Takeaways

1. **Never hardcode secrets** - Use environment variables
2. **Validate all inputs** - User data, file paths, commands
3. **Prevent path traversal** - Use `is_relative_to()`
4. **No shell=True** - Use list arguments with subprocess
5. **Parameterized queries** - Never string interpolation
6. **Secure random** - Use `secrets` module
7. **Restrict permissions** - Files 0o600, dirs 0o700
8. **Mask secrets in logs** - Show only first/last few chars
9. **Scan dependencies** - Use safety/pip-audit
10. **.gitignore secrets** - .env, *.key, *.pem

---

## Related Files

- [code-examples.md](code-examples.md) - Complete Python code examples
- [templates.md](templates.md) - .env, .gitignore, and security checklists

## OWASP Top 10 Quick Reference

**See:** [templates.md#owasp-top-10-quick-reference](templates.md#owasp-top-10-quick-reference)
