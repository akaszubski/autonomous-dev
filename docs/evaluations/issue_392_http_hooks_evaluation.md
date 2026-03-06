# Issue #392: HTTP Hooks Evaluation

## Overview

Claude Code 2.1.69+ introduced HTTP hooks, enabling POST JSON requests to external URLs as an alternative to command-based hooks. HTTP hooks fire on the same lifecycle events (PreToolUse, PostToolUse, Notification, etc.) but deliver payloads over the network rather than executing local scripts.

This evaluation assesses whether HTTP hooks should replace or supplement the current command hook approach used by autonomous-dev.

## Configuration Mechanics

HTTP hooks are configured in `.claude/settings.json` alongside command hooks. The configuration format uses a `type` field to distinguish HTTP hooks from command hooks:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "http",
        "url": "https://example.com/hook",
        "headers": {
          "Authorization": "Bearer $TOKEN"
        },
        "allowedEnvVars": ["TOKEN"],
        "timeout": 30
      }
    ]
  }
}
```

**Key fields:**

- **type**: Must be `"http"` to indicate an HTTP hook (command hooks use `"command"` or omit the type field)
- **url**: The endpoint URL that receives POST requests with JSON payloads
- **headers**: Optional HTTP headers; supports environment variable interpolation via `$VAR` syntax
- **allowedEnvVars**: Whitelist of environment variables that may be interpolated into headers. Variables not listed are silently ignored, preventing accidental secret exposure
- **timeout**: Maximum seconds to wait for a response (default: 30). If the timeout is exceeded, the hook is treated as non-blocking and execution continues

## Decision Tree: When to Use HTTP vs Command Hooks

Use this decision tree to choose the right hook type:

- **If you need blocking enforcement** (e.g., reject a tool call) --> Use a **command hook**. Command hooks block deterministically via exit code 2. HTTP hooks fail-open on timeout, so they cannot guarantee enforcement.
- **If you need filesystem access** (e.g., read/write local files, run scripts) --> Use a **command hook**. HTTP hooks receive only the JSON body; they have no access to the local filesystem.
- **If you need team-wide notifications** (e.g., Slack alerts when a tool runs) --> Use an **HTTP hook**. A centralized endpoint serves all team members without per-machine setup.
- **If you need CI/CD integration** (e.g., trigger GitHub Actions, update dashboards) --> Use an **HTTP hook**. Native POST is suitable for webhook-driven CI/CD systems.
- **If you need fast, low-latency hooks** --> Use a **command hook**. Local execution completes in milliseconds; HTTP hooks incur network latency.
- **If you need audit logging to a remote service** --> Use an **HTTP hook**. Centralized logging endpoints aggregate data from multiple machines.

## Comparison Matrix

| Dimension | Command Hooks | HTTP Hooks | Winner |
|-----------|---------------|------------|--------|
| Blocking reliability | Exit code 2 blocks deterministically | 2xx + JSON blocks, but timeout = non-blocking | Command |
| Latency | Milliseconds (local execution) | Network latency (up to 30s timeout) | Command |
| Filesystem access | Full local filesystem access | None (JSON body only) | Command |
| Team-wide deployment | Per-machine installation required | Centralized endpoint, no per-machine setup | HTTP |
| CI/CD integration | Via shell scripts calling APIs | Native POST to webhook endpoints | HTTP |
| Failure mode | Deterministic (exit codes) | Fail-open on timeout or network error | Command |
| Secret management | Environment variables, local config | allowedEnvVars whitelist with silent failure | Command |
| Setup complexity | Script files + permissions | URL + optional auth headers | HTTP |
| Debugging | Local logs, stderr output | Requires endpoint logging infrastructure | Command |
| Offline operation | Works without network | Requires network connectivity | Command |

**Summary**: Command hooks win 7 of 10 dimensions. HTTP hooks are better suited for team-wide deployment and CI/CD integration use cases.

## Security Analysis

### No Built-in HMAC Verification

HTTP hooks do not include HMAC signature verification or request signing. The receiving endpoint cannot cryptographically verify that a request originated from Claude Code rather than an attacker. This means:

- Any party that knows the endpoint URL can send forged hook payloads
- There is no integrity guarantee on the request body
- Endpoints must rely on bearer token authentication as the sole verification mechanism

### Bearer Token Authentication

Authentication is handled via the `Authorization` header with bearer tokens:

```json
{
  "headers": {
    "Authorization": "Bearer $HOOK_TOKEN"
  },
  "allowedEnvVars": ["HOOK_TOKEN"]
}
```

The token value is interpolated from environment variables at runtime. If the environment variable is not set, the header is sent with the literal `$HOOK_TOKEN` string (silent failure), which will likely cause authentication failures at the endpoint but provides no user-visible warning.

### Timeout Equals Non-Blocking

The timeout setting (default 30 seconds) determines how long Claude Code waits for a response. When a timeout occurs:

- The hook is treated as non-blocking -- execution continues as if the hook approved the action
- This means HTTP hooks cannot guarantee enforcement for security-critical policies
- A slow or unavailable endpoint effectively disables the hook

### No Retry Logic

Failed HTTP requests (network errors, 5xx responses) are not retried. Notifications sent via HTTP hooks can be silently lost if the endpoint is temporarily unavailable.

### allowedEnvVars Whitelist

The `allowedEnvVars` field controls which environment variables can be interpolated into headers. This is a security allowlist -- only variables explicitly listed are expanded. However:

- There is no validation that listed variables are actually set
- Missing variables result in literal string interpolation (e.g., `$TOKEN` sent as-is)
- No warning is surfaced to the user when a variable is missing

## Security Best Practices

When using HTTP hooks, follow these practices:

1. **Always use HTTPS** -- Never send hook payloads over unencrypted HTTP
2. **Use bearer tokens via allowedEnvVars** -- Store tokens in environment variables, reference them in headers
3. **Rotate tokens regularly** -- Treat hook endpoint tokens like any other API credential
4. **Never hardcode secrets in settings.json** -- This file is typically committed to version control
5. **Implement endpoint-side validation** -- Since there is no HMAC, validate payloads server-side (check expected fields, rate-limit requests)
6. **Monitor endpoint availability** -- HTTP hooks fail silently; set up alerting on your endpoint
7. **Use short timeouts for non-critical hooks** -- Reduce latency impact for notification-only hooks

## Recommendation

**Command hooks remain the primary hook mechanism for autonomous-dev.** All current hooks in the plugin require:

- Local filesystem access (reading settings, config files, project state)
- Fast execution (hooks fire on every tool call; network latency is unacceptable)
- Reliable blocking (security enforcement must be deterministic, not fail-open)

HTTP hooks are unsuitable as a replacement for any existing hook because the current approach depends on local execution, deterministic blocking, and filesystem access -- none of which HTTP hooks provide.

**HTTP hooks are recommended as supplementary for specific use cases:**

- **Slack/Teams notifications** -- Alert channels when significant tool actions occur
- **GitHub Actions triggers** -- Kick off CI/CD workflows via webhook on code changes
- **Remote audit logging** -- Stream hook events to a centralized logging service (e.g., Datadog, Splunk)
- **Dashboard updates** -- Push real-time metrics to monitoring dashboards

These use cases are notification-oriented and do not require blocking or filesystem access, making HTTP hooks a good fit.

## Conclusion

HTTP hooks are a welcome addition to Claude Code's extensibility model but do not change the architecture of autonomous-dev's hook system. The plugin's hooks are enforcement-oriented (blocking disallowed actions, validating policies) and execution-oriented (running local scripts, reading config). HTTP hooks serve a fundamentally different purpose: external integration and notification.

The recommendation is to document HTTP hooks as an available option for users who want to add external integrations on top of autonomous-dev, but to continue using command hooks for all plugin-provided hook functionality.

## Sources

- Claude Code HTTP Hooks Documentation: https://docs.anthropic.com/en/docs/claude-code/hooks
- Claude Code Changelog (v2.1.69 HTTP hooks release): https://docs.anthropic.com/en/docs/claude-code/changelog
- Claude Code Settings Reference: https://docs.anthropic.com/en/docs/claude-code/settings
- Anthropic Claude Code GitHub Repository: https://github.com/anthropics/claude-code
