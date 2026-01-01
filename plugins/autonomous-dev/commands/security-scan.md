---
name: security-scan
description: Security vulnerability scan and OWASP compliance check
argument-hint: Optional - specific file or component to scan
allowed-tools: [Task, Read, Grep, Glob, Bash]
---

# Security Vulnerability Scan

Invoke the **security-auditor agent** to scan for vulnerabilities and check OWASP compliance.

## Implementation

Invoke the security-auditor agent with optional focus area from user.

ARGUMENTS: {{ARGUMENTS}}

Use the Task tool to invoke the security-auditor agent with subagent_type="security-auditor" and provide any specific focus from ARGUMENTS (or scan recent changes if no argument provided).

## What This Does

The security-auditor agent will:

1. Scan for hardcoded secrets and credentials
2. Check for common vulnerabilities (SQL injection, XSS, etc.)
3. Verify OWASP compliance
4. Identify security best practice violations

**Time**: 1-2 minutes (vs 20-30 min full pipeline)

## Usage

```bash
/security-scan

/security-scan src/auth/

/security-scan recent authentication changes
```

## Output

The security-auditor provides:

- **Secrets Detection**: Hardcoded API keys, passwords, tokens
- **Vulnerability Report**: Common security issues found
- **OWASP Compliance**: Checklist against OWASP Top 10
- **Recommendations**: How to fix security issues

## When to Use

Use `/security-scan` when you need:

- Quick security audit before commit
- Verification after implementing security-sensitive code
- Check for accidentally committed secrets
- OWASP compliance verification

## What Gets Scanned

The auditor checks for:
- **Secrets**: API keys, passwords, tokens in code
- **Injection**: SQL, command, LDAP injection vulnerabilities
- **Authentication**: Weak auth, session management issues
- **XSS**: Cross-site scripting vulnerabilities
- **Input Validation**: Missing or weak input validation
- **Error Handling**: Information disclosure in errors

## Next Steps

After security scan, you can:

1. **Fix vulnerabilities** - Address issues found
2. **Update docs** - Use `/update-docs` if security changes made
3. **Commit** - If scan passes, commit changes
4. **Re-scan** - Run `/security-scan` again after fixes

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/implement` | 5-10 min | Code implementation |
| `/review` | 2-3 min | Code quality review |
| `/security-scan` | 1-2 min | Security vulnerability scan (this command) |
| `/update-docs` | 1-2 min | Documentation sync |
| `/auto-implement` | 20-30 min | Full pipeline (research → plan → test → implement → review → security → docs) |

## Technical Details

This command invokes the `security-auditor` agent with:
- **Model**: Haiku (fast scanning)
- **Tools**: Read, Bash, Grep, Glob
- **Permissions**: Read-only + bash for security tools

---

**Part of**: Individual agent commands (GitHub #44)
**Related**: `/review`, `/update-docs`, `/auto-implement`
