# Security Policy

## Supported Versions

Currently supported versions for security updates:

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | ✅ Yes             |
| 1.x.x   | ❌ No              |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

### How to Report

1. **DO NOT** open a public issue
2. **Email** the maintainers directly or use GitHub's private security advisory feature
3. **Include** in your report:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

### What to Expect

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Resolution Timeline**: Depends on severity
  - Critical: 1-7 days
  - High: 7-30 days
  - Medium: 30-90 days
  - Low: Best effort

### Security Update Process

1. Vulnerability is validated
2. Fix is developed and tested
3. Security advisory is published
4. Patch is released
5. Users are notified via GitHub releases

## Security Best Practices

### For Plugin Users

- **Keep updated**: Always use the latest version
- **Review hooks**: Understand what automation hooks do before enabling
- **Protect secrets**: Never commit API keys or credentials
- **Audit agents**: Review agent permissions and tools
- **Use .env files**: Store sensitive configuration in gitignored `.env` files

### For Contributors

- **No secrets in code**: Never hardcode credentials
- **Validate inputs**: Sanitize all user inputs in hooks/scripts
- **Minimize permissions**: Agents should only have necessary tools
- **Review dependencies**: Check third-party packages for vulnerabilities
- **Test security**: Run `/security-scan` before commits

## Known Security Considerations

### Hooks Execute Code

- Hooks run automatically on events (Write, Edit, etc.)
- **Mitigation**: Review hook code before installation
- **User control**: Users can disable hooks in settings

### Agents Have File Access

- Agents can read/write files based on their tools
- **Mitigation**: Agents have minimal required permissions
- **User control**: Users can customize agent tool access

### Bash Commands

- Some hooks/agents execute bash commands
- **Mitigation**: Commands are logged and visible
- **User control**: Review hook output before accepting

## Security Features

### Built-in Security Checks

- ✅ **security_scan.py hook**: Scans for secrets, vulnerabilities
- ✅ **/security-scan command**: Manual security audit
- ✅ **security-auditor agent**: Reviews code for security issues
- ✅ **Pre-commit validation**: Blocks commits with secrets

### What We Scan For

- API keys and tokens
- AWS credentials
- Private keys
- Database passwords
- Known vulnerability patterns

## Disclosure Policy

- Security vulnerabilities will be disclosed after a fix is available
- Users will be notified via GitHub Security Advisories
- CVE will be requested for critical vulnerabilities

## Contact

For security concerns:
- **GitHub Security Advisory**: Use GitHub's private reporting feature
- **Issues**: For non-sensitive security suggestions, open an issue with `security` label

---

**Last Updated**: 2025-10-20
