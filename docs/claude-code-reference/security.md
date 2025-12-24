# Claude Code Security Documentation

> **Source**: https://code.claude.com/docs/en/security
> **Downloaded**: 2025-12-16

## Overview
Claude Code is Anthropic's official CLI for Claude with security built at its core. This document provides comprehensive security information, safeguards, and best practices.

## How We Approach Security

### Security Foundation
- Built according to Anthropic's comprehensive security program
- Resources available at [Anthropic Trust Center](https://trust.anthropic.com) (SOC 2 Type 2 report, ISO 27001 certificate)

### Permission-Based Architecture
- **Default behavior**: Strict read-only permissions
- **Explicit approval required** for: file editing, test running, command execution
- **User control**: Approve actions once or allow automatically
- **Transparency**: Bash commands require approval before execution
- **Flexibility**: Users and organizations can configure permissions directly

### Built-in Protections

1. **Sandboxed Bash Tool**
   - Filesystem and network isolation
   - Reduces permission prompts while maintaining security
   - Enable with `/sandbox` to define autonomous work boundaries

2. **Write Access Restriction**
   - Can only write to the started folder and subfolders
   - Cannot modify parent directory files without explicit permission
   - Can read files outside working directory (for system libraries/dependencies)
   - Clear security boundary for project scope

3. **Prompt Fatigue Mitigation**
   - Allowlist frequently used safe commands
   - Per-user, per-codebase, or per-organization configuration

4. **Accept Edits Mode**
   - Batch accept multiple edits
   - Maintains permission prompts for side-effect commands

### User Responsibility
- Claude Code only has granted permissions
- Users must review proposed code and commands for safety before approval

## Protecting Against Prompt Injection

Prompt injection: attackers override AI instructions by inserting malicious text.

### Core Protections
- **Permission system**: Sensitive operations require explicit approval
- **Context-aware analysis**: Detects harmful instructions by analyzing full requests
- **Input sanitization**: Prevents command injection through user input processing
- **Command blocklist**: Blocks `curl`, `wget` by default (arbitrary web content fetching)

### Privacy Safeguards
- Limited retention periods for sensitive information ([Privacy Center](https://privacy.anthropic.com/en/articles/10023548-how-long-do-you-store-my-data))
- Restricted access to user session data
- User control over data training preferences
- Consumer users can modify [privacy settings](https://claude.ai/settings/privacy)

**Legal references**:
- [Commercial Terms of Service](https://www.anthropic.com/legal/commercial-terms) (Team, Enterprise, API)
- [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) (Free, Pro, Max)
- [Privacy Policy](https://www.anthropic.com/legal/privacy)

### Additional Safeguards
- **Network request approval**: Tools making network requests require user approval by default
- **Isolated context windows**: Web fetch uses separate context to avoid malicious prompt injection
- **Trust verification**: First-time codebase runs and new MCP servers require verification
  - *Note*: Disabled when running non-interactively with `-p` flag
- **Command injection detection**: Suspicious bash commands require manual approval (even if allowlisted)
- **Fail-closed matching**: Unmatched commands default to manual approval
- **Natural language descriptions**: Complex bash commands include explanations
- **Secure credential storage**: API keys and tokens are encrypted ([Credential Management](/docs/en/iam#credential-management))

### ⚠️ Windows WebDAV Security Risk
When running Claude Code on Windows:
- **Avoid** enabling WebDAV or allowing access to paths like `\\*`
- [WebDAV deprecated by Microsoft](https://learn.microsoft.com/en-us/windows/whats-new/deprecated-features) due to security risks
- WebDAV may allow Claude Code to trigger network requests to remote hosts, bypassing permissions

### Best Practices for Untrusted Content
1. Review suggested commands before approval
2. Avoid piping untrusted content directly to Claude
3. Verify proposed changes to critical files
4. Use virtual machines (VMs) to run scripts and make tool calls (especially with external web services)
5. Report suspicious behavior with `/bug`

**⚠️ Important**: While protections significantly reduce risk, no system is completely immune. Always maintain good security practices with any AI tool.

## MCP Security

- Claude Code allows Model Context Protocol (MCP) server configuration
- Allowed servers configured in source code (part of Claude Code settings)
- **Recommendation**: Write your own MCP servers or use from trusted providers
- Users can configure Claude Code permissions for MCP servers
- **Important**: Anthropic does not manage or audit MCP servers

## IDE Security
See [VS Code Security](/docs/en/vs-code#security) for IDE-specific information.

## Cloud Execution Security

When using [Claude Code on the web](/docs/en/claude-code-on-the-web):

- **Isolated virtual machines**: Each cloud session in isolated Anthropic-managed VM
- **Network access controls**: Limited by default, configurable to disable or allow specific domains
- **Credential protection**: Secure proxy uses scoped credential in sandbox, translated to actual GitHub token
- **Branch restrictions**: Git push restricted to current working branch
- **Audit logging**: All cloud environment operations logged for compliance/audit
- **Automatic cleanup**: Cloud environments auto-terminated after session completion

## Security Best Practices

### Working with Sensitive Code
- Review all suggested changes before approval
- Use project-specific permission settings for sensitive repositories
- Consider [devcontainers](/docs/en/devcontainer) for additional isolation
- Regularly audit permission settings with `/permissions`

### Team Security
- Use [enterprise managed policies](/docs/en/iam#enterprise-managed-policy-settings) for organizational standards
- Share approved permission configurations through version control
- Train team members on security best practices
- Monitor Claude Code usage via [OpenTelemetry metrics](/docs/en/monitoring-usage)

### Reporting Security Issues

If you discover a security vulnerability:
1. **Do not disclose publicly**
2. Report through [HackerOne vulnerability program](https://hackerone.com/anthropic-vdp/reports/new?type=team&report_type=vulnerability)
3. Include detailed reproduction steps
4. Allow time for resolution before public disclosure

## Related Resources

- [Sandboxing](/docs/en/sandboxing) - Filesystem and network isolation for bash
- [Identity and Access Management](/docs/en/iam) - Permission and access control configuration
- [Monitoring Usage](/docs/en/monitoring-usage) - Track and audit Claude Code activity
- [Development Containers](/docs/en/devcontainer) - Secure, isolated environments
- [Anthropic Trust Center](https://trust.anthropic.com) - Security certifications and compliance
