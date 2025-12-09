# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.x.x   | :white_check_mark: |
| < 3.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in autonomous-dev, please report it responsibly.

### How to Report

1. **Do NOT open a public GitHub issue** for security vulnerabilities
2. **Email**: Send details to the repository owner via GitHub (click "Report a vulnerability" on the Security tab)
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Fix Timeline**: Critical issues within 14 days, others within 30 days
- **Credit**: Security researchers will be credited in the release notes (unless anonymity is preferred)

### Scope

The following are in scope for security reports:

- Path traversal vulnerabilities (CWE-22)
- Command injection (CWE-78)
- Symlink attacks (CWE-59)
- Code injection in generated files
- Privilege escalation
- Secrets exposure
- TOCTOU race conditions (CWE-367)

### Out of Scope

- Issues in dependencies (report to the dependency maintainer)
- Issues requiring physical access to the machine
- Social engineering attacks
- Denial of service via resource exhaustion (unless trivially exploitable)

## Security Features

autonomous-dev includes comprehensive security hardening:

- **Centralized security module**: `lib/security_utils.py`
- **Path validation**: Whitelist-based, blocks traversal and symlinks
- **Input validation**: Length limits, format validation
- **Audit logging**: All security events logged to `logs/security_audit.log`
- **MCP security**: Permission-based access control for MCP operations

See [docs/SECURITY.md](../docs/SECURITY.md) for the complete security architecture.

## Security Updates

Security fixes are released as patch versions (e.g., 3.39.1) and announced in:

- [CHANGELOG.md](../CHANGELOG.md)
- GitHub Releases
- GitHub Security Advisories (for critical issues)
