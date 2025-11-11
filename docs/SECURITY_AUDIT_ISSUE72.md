# Security Audit: Issue #72 - Agent Output Format Cleanup

## Summary
Security audit of Issue #72 implementation (agent output format cleanup):
- `scripts/measure_agent_tokens.py` (531 lines)
- `scripts/measure_output_format_sections.py` (127 lines)  
- `tests/helpers/agent_testing.py` (430 lines)
- 5 agent prompts modified
- Documentation updates

## Audit Date
2025-11-12

## Configuration Status
- ✅ `.env` is in `.gitignore` - Credentials are properly isolated
- ✅ No API keys/tokens in git history verified
- ✅ No subprocess calls with shell=True detected
- ✅ No hardcoded secrets in source code

## Vulnerabilities Found

### [HIGH] Path Traversal in analyze_agent_tokens()
**Issue**: User input (`agent_name` parameter) is directly interpolated into file path without validation. An attacker could use path traversal sequences like `../../../sensitive_file` to read arbitrary files on the system.

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/measure_agent_tokens.py:227`

**Vulnerable Code**:
```python
def analyze_agent_tokens(agent_name: str) -> Dict:
    agents_dir = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "agents"
    agent_file = agents_dir / f"{agent_name}.md"  # <-- VULNERABLE: agent_name not validated
    
    if not agent_file.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_file}")
    
    return analyze_agent_file(agent_file)
```

**Attack Vector**: 
```bash
# Attacker could call:
analyze_agent_tokens("../../etc/passwd")
# This would attempt to read /etc/passwd and process it
```

**Impact**: 
- Information disclosure of arbitrary files
- Denial of service by reading large files
- Processing of non-markdown files could cause crashes

**OWASP**: CWE-22 (Path Traversal), CWE-36 (Absolute Path Traversal)

**Recommendation**:
1. Validate `agent_name` to only allow alphanumeric, hyphens, underscores
2. Verify resolved path is within agents directory
3. Use `Path.resolve()` and verify it's under expected directory

```python
import re
from pathlib import Path

def analyze_agent_tokens(agent_name: str) -> Dict:
    # Validate agent_name format
    if not re.match(r'^[a-zA-Z0-9_-]+$', agent_name):
        raise ValueError(f"Invalid agent name format: {agent_name}")
    
    agents_dir = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "agents"
    agent_file = agents_dir / f"{agent_name}.md"
    
    # Verify resolved path is within agents directory
    try:
        agent_file.resolve().relative_to(agents_dir.resolve())
    except ValueError:
        raise ValueError(f"Agent file path outside allowed directory: {agent_name}")
    
    if not agent_file.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_name}")
    
    return analyze_agent_file(agent_file)
```

---

### [MEDIUM] Unvalidated File Output Path
**Issue**: The `--output` CLI argument accepts arbitrary paths without validation. User can write to any location they have permissions for.

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/measure_agent_tokens.py:482-490`

**Vulnerable Code**:
```python
if args.output:
    save_baseline(baseline, args.output)  # <-- VULNERABLE: no path validation
    print(f"Baseline saved to {args.output}")

def save_baseline(baseline: Dict[str, int], output_path: Path) -> None:
    with open(output_path, 'w') as f:  # <-- Can write anywhere user has permission
        json.dump(baseline, f, indent=2)
```

**Attack Vector**:
```bash
# Attacker could write to sensitive locations:
python scripts/measure_agent_tokens.py --baseline --output /etc/cron.d/malicious
python scripts/measure_agent_tokens.py --baseline --output ~/.ssh/authorized_keys
```

**Impact**: 
- Privilege escalation via cron job injection
- SSH key overwriting
- Overwriting application config files
- Denial of service

**OWASP**: CWE-73 (External Control of File Name/Path)

**Recommendation**:
1. Restrict output to a safe directory (e.g., project root, `./outputs/`)
2. Validate path is within allowed directory
3. Use `pathlib.Path.resolve()` and verify location
4. Consider using temporary file APIs

```python
def save_baseline(baseline: Dict[str, int], output_path: Path) -> None:
    # Validate output path
    safe_dir = Path(__file__).parent.parent / "outputs"
    safe_dir.mkdir(exist_ok=True)
    
    # Convert to absolute path and verify it's in safe directory
    abs_path = output_path.resolve()
    try:
        abs_path.relative_to(safe_dir.resolve())
    except ValueError:
        raise ValueError(f"Output path must be in {safe_dir}, got {output_path}")
    
    # Ensure directory exists
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(abs_path, 'w') as f:
        json.dump(baseline, f, indent=2)
```

---

### [LOW] Information Disclosure via Error Messages
**Issue**: Error messages expose full file system paths, which could aid reconnaissance attacks.

**Location**: 
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/measure_agent_tokens.py:230` (FileNotFoundError)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/measure_agent_tokens.py:252-255` (ValueError)

**Code**:
```python
raise FileNotFoundError(f"Agent file not found: {agent_file}")
raise ValueError(f"Malformed agent file (empty): {agent_file}")
raise ValueError(f"Malformed agent file (missing frontmatter): {agent_file}")
```

**Attack Vector**: 
- Information leakage about directory structure
- Could reveal system usernames or paths
- Assists attackers in scanning for files

**Impact**: 
- Reconnaissance assistance for attackers
- Potential to leak absolute paths

**OWASP**: CWE-209 (Information Exposure Through an Error Message)

**Recommendation**:
Use relative paths or descriptive names in error messages instead of absolute paths.

```python
raise FileNotFoundError(f"Agent '{agent_name}' not found")
raise ValueError(f"Agent '{agent_name}' file is empty or malformed")
```

---

## Security Checks Completed

- ✅ No hardcoded API keys, passwords, or tokens in source code
- ✅ No secrets in git history (verified with `git log -S`)
- ✅ `.env` properly gitignored - Configuration separated from code
- ✅ No subprocess calls with `shell=True` (no command injection risk)
- ✅ No SQL injection risk (no database operations)
- ✅ No XSS risk (CLI tools, no web output)
- ✅ Input validation present for JSON deserialization (safe error handling)
- ✅ File permissions appropriate (tools create files with default umask)
- ✅ No arbitrary code execution in JSON parsing

## Vulnerabilities Summary

| Severity | Type | Count | Status |
|----------|------|-------|--------|
| CRITICAL | None | 0 | - |
| HIGH | Path Traversal | 1 | UNFIXED |
| MEDIUM | Unvalidated Output Path | 1 | UNFIXED |
| LOW | Information Disclosure | 1 | UNFIXED |

## OWASP Top 10 Assessment

- **A01:2021 - Broken Access Control**: ✅ PASS (no access control needed for CLI tools)
- **A02:2021 - Cryptographic Failures**: ✅ PASS (no sensitive data encrypted)
- **A03:2021 - Injection**: ⚠️ HIGH RISK - Path traversal vulnerability (CWE-22)
- **A04:2021 - Insecure Design**: ✅ PASS (design is appropriate for CLI)
- **A05:2021 - Security Misconfiguration**: ✅ PASS (no configuration files)
- **A06:2021 - Vulnerable Components**: ✅ PASS (uses standard library only)
- **A07:2021 - Authentication/Session**: ✅ PASS (no authentication needed)
- **A08:2021 - Software/Data Integrity**: ✅ PASS (no external dependencies)
- **A09:2021 - Logging & Monitoring**: ✅ PASS (appropriate error handling)
- **A10:2021 - SSRF**: ✅ PASS (no external requests)

## Overall Security Status

**FAIL** - Path traversal vulnerability (HIGH severity) must be fixed before merging.

## Remediation Priority

1. **IMMEDIATE**: Fix path traversal in `analyze_agent_tokens()` (HIGH severity)
2. **IMMEDIATE**: Fix output path validation in `save_baseline()` (MEDIUM severity)
3. **OPTIONAL**: Improve error messages to not expose file paths (LOW severity)

## Testing Recommendations

After fixes, test with:
```python
# Test path traversal protection
with pytest.raises(ValueError):
    analyze_agent_tokens("../../../etc/passwd")

with pytest.raises(ValueError):
    analyze_agent_tokens("../../sensitive_data")

# Test output path validation
with pytest.raises(ValueError):
    measure_agent_tokens.save_baseline({}, Path("/etc/passwd"))

with pytest.raises(ValueError):
    measure_agent_tokens.save_baseline({}, Path("/tmp/malicious"))
```

---

**Audit Completed**: 2025-11-12
**Auditor**: security-auditor agent
**Status**: REQUIRES REMEDIATION

---

## Additional Vulnerabilities

### [HIGH] Path Traversal in measure_output_format_lines()
**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/measure_agent_tokens.py:316`

**Vulnerable Code**:
```python
def measure_output_format_lines(agent_name: str) -> int:
    agents_dir = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "agents"
    agent_file = agents_dir / f"{agent_name}.md"  # <-- VULNERABLE: agent_name not validated
    ...
```

Same vulnerability as `analyze_agent_tokens()`. Same fix required.

---

### [HIGH] Path Traversal in count_output_format_tokens()
**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/measure_agent_tokens.py:292`

**Vulnerable Code**:
```python
def count_output_format_tokens(agent_name: str) -> int:
    analysis = analyze_agent_tokens(agent_name)  # <-- VULNERABLE: calls vulnerable function
    ...
```

Inherits vulnerability from `analyze_agent_tokens()`. Will be fixed by addressing root cause.

---

### [HIGH] Path Traversal in compare_output_format_sections()
**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/measure_agent_tokens.py:371-372`

**Vulnerable Code**:
```python
def compare_output_format_sections(agent_name: str) -> Dict:
    after_tokens = count_output_format_tokens(agent_name)        # <-- VULNERABLE
    after_lines = measure_output_format_lines(agent_name)        # <-- VULNERABLE
    ...
```

Inherits vulnerability from both called functions. Will be fixed by addressing root causes.

---

## Vulnerability Summary Update

| Severity | Type | Count | Functions Affected |
|----------|------|-------|-------------------|
| CRITICAL | None | 0 | - |
| HIGH | Path Traversal | 3 | `analyze_agent_tokens()`, `measure_output_format_lines()`, `count_output_format_tokens()` |
| MEDIUM | Unvalidated Output Path | 1 | `save_baseline()` |
| LOW | Information Disclosure | 1 | Error messages in multiple functions |

**Note**: The three HIGH vulnerabilities are actually root-cause variations of the same issue:
- Root cause: `analyze_agent_tokens()` and `measure_output_format_lines()` don't validate `agent_name`
- Secondary: `count_output_format_tokens()` and `compare_output_format_sections()` call the vulnerable functions

**Fix Strategy**: Fix the two root-cause functions, and all callers will be protected.

---

## Overall Security Status (Updated)

**FAIL** - Multiple path traversal vulnerabilities (HIGH severity) must be fixed before merging.

## Remediation Priority (Updated)

1. **IMMEDIATE**: Fix path traversal in `analyze_agent_tokens()` AND `measure_output_format_lines()` (HIGH severity, root causes)
2. **IMMEDIATE**: Fix output path validation in `save_baseline()` (MEDIUM severity)
3. **OPTIONAL**: Improve error messages to not expose file paths (LOW severity)

