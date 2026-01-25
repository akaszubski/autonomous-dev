# Security Patterns - Templates

Configuration templates and security checklists.

---

## Environment Configuration

### .env File Template

```bash
# .env (must be in .gitignore!)
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
HUGGINGFACE_TOKEN=hf_your-token-here
```

### .gitignore Security Entries

```gitignore
# .gitignore - MUST include these
.env
.env.local
.env.*.local
*.key
*.pem
secrets/
```

---

## Security Checklists

### Code Review Checklist

- [ ] No hardcoded API keys/secrets
- [ ] All secrets in .env (gitignored)
- [ ] .env file in .gitignore
- [ ] Input validation on user data
- [ ] Path traversal prevention
- [ ] No shell=True in subprocess
- [ ] Parameterized database queries
- [ ] Secure file permissions
- [ ] Cryptographically secure random
- [ ] No secrets in logs
- [ ] Dependencies scanned for vulnerabilities

### File Operations Checklist

- [ ] Validate file extensions
- [ ] Check file size limits
- [ ] Prevent path traversal
- [ ] Restrict file permissions
- [ ] Validate before deserialize

### API Operations Checklist

- [ ] API keys from environment
- [ ] Keys validated before use
- [ ] Keys masked in logs
- [ ] Rate limiting considered
- [ ] Error messages don't expose secrets

---

## OWASP Top 10 Quick Reference

| # | Vulnerability | Prevention |
|---|---------------|------------|
| 1 | **Injection** | Use parameterized queries |
| 2 | **Authentication** | Use secure tokens (secrets module) |
| 3 | **Sensitive Data** | Never hardcode, use .env |
| 4 | **XXE** | Disable external entities in XML |
| 5 | **Access Control** | Validate file paths |
| 6 | **Security Config** | Secure defaults |
| 7 | **XSS** | Sanitize output (if web) |
| 8 | **Deserialization** | Don't unpickle untrusted data |
| 9 | **Components** | Keep dependencies updated |
| 10 | **Logging** | Don't log secrets |

---

## File Permission Reference

| Permission | Octal | Use Case |
|------------|-------|----------|
| `rw-------` | 0o600 | Sensitive files (API keys, configs) |
| `rwx------` | 0o700 | Sensitive directories |
| `rw-r--r--` | 0o644 | Public files |
| `rwxr-xr-x` | 0o755 | Public directories |
