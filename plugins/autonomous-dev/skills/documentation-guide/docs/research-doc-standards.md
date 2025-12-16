# Research Documentation Standards

Standards for persisting research findings in docs/research/ for reuse across the project.

---

## Purpose

**Why persist research**:
- **Avoid duplicate research**: Future features can reference existing research instead of re-researching
- **Knowledge preservation**: Capture architectural decisions and rationale
- **Team collaboration**: Share research findings with team members
- **Historical context**: Understand why certain approaches were chosen

**Not all research needs persistence** - only substantial research that will be reused.

---

## When to Persist

Persist research to docs/research/ when it meets these criteria:

**Substantial Research** (at least one):
- 2+ best practices discovered
- 2+ security considerations identified
- 3+ authoritative sources consulted
- Architectural decision documented

**Reusability** (at least one):
- Research will be referenced by multiple features
- Research documents a pattern used project-wide
- Research captures security considerations for a technology
- Research provides implementation guidance for a common task

**Examples to Persist**:
- JWT authentication best practices (used by auth features)
- Error handling patterns (used project-wide)
- Rate limiting strategies (used by API features)
- Database migration patterns (used by schema updates)

**Examples NOT to Persist**:
- One-off bug investigation (use GitHub issue comments)
- Quick library comparison (use inline code comments)
- Trivial configuration research (use code comments)

---

## File Structure

All research documents use **SCREAMING_SNAKE_CASE** naming convention and are stored in `docs/research/` directory.

### Naming Convention

**SCREAMING_SNAKE_CASE**: All uppercase with underscores

**Format**: `{TOPIC}_{SUBTOPIC}_RESEARCH.md`

**Examples**:
- `JWT_AUTHENTICATION_RESEARCH.md`
- `ERROR_HANDLING_PATTERNS.md`
- `RATE_LIMITING_STRATEGIES.md`
- `DATABASE_MIGRATION_PATTERNS.md`
- `PYTHON_ASYNC_BEST_PRACTICES.md`

**Why SCREAMING_SNAKE_CASE**:
- Visually distinct from regular markdown files
- Indicates "authoritative reference document"
- Easy to identify in file listings
- Consistent with constant naming conventions

### Directory Location

All research documents go in: `docs/research/`

```
docs/
└── research/
    ├── README.md                              # Index of all research docs
    ├── JWT_AUTHENTICATION_RESEARCH.md
    ├── ERROR_HANDLING_PATTERNS.md
    └── RATE_LIMITING_STRATEGIES.md
```

### README.md Index

The `docs/research/README.md` file should list all research documents with brief descriptions:

```markdown
# Research Documentation

This directory contains research findings for reuse across the project.

## Available Research

- **[JWT_AUTHENTICATION_RESEARCH.md](JWT_AUTHENTICATION_RESEARCH.md)** - Best practices for JWT authentication and security
- **[ERROR_HANDLING_PATTERNS.md](ERROR_HANDLING_PATTERNS.md)** - Error handling patterns for Python applications
- **[RATE_LIMITING_STRATEGIES.md](RATE_LIMITING_STRATEGIES.md)** - Rate limiting strategies for API endpoints

## Contributing

See [research-doc-standards.md](../../plugins/autonomous-dev/skills/documentation-guide/docs/research-doc-standards.md) for research documentation standards.
```

---

## Document Template

Use this template for all research documents:

```markdown
# Topic Research

> **Issue Reference**: #{issue_number} (if applicable)
> **Research Date**: YYYY-MM-DD
> **Status**: Active | Complete | Archived

## Overview

Brief summary (2-3 sentences) of what was researched and why.

**Context**: Why this research was needed (feature requirement, architectural decision, etc.)

---

## Key Findings

Main discoveries, patterns, best practices discovered during research.

### Finding 1: {Title}

**Description**: Detailed explanation of the finding

**Rationale**: Why this matters for the project

**Example**:
```python
# Code example if applicable
```

### Finding 2: {Title}

...

---

## Source References

List of authoritative sources consulted during research.

- **{Source Name}**: {URL} - Brief description of what it provides
- **{Source Name}**: {URL} - Brief description

**Source Quality** (prioritize in this order):
1. Official documentation (e.g., Python docs, library docs)
2. Security standards (e.g., OWASP, CWE)
3. Authoritative blogs (e.g., library maintainer blogs)
4. GitHub issues/PRs (for implementation details)
5. Stack Overflow (for common pitfalls)

---

## Implementation Notes

Practical guidance on how to apply these findings in the codebase.

**Recommended Approach**:
- Step 1: ...
- Step 2: ...

**Code Patterns**:
```python
# Example implementation pattern
```

**Integration Points**:
- Where in the codebase this applies
- Which components should use this pattern
- Migration strategy (if updating existing code)

---

## Security Considerations

Security implications and mitigations (if applicable).

**Risks**:
- Risk 1: Description and severity (high/medium/low)
- Risk 2: Description and severity

**Mitigations**:
- How to mitigate each risk
- Security best practices specific to this topic

---

## Common Pitfalls

Known anti-patterns and mistakes to avoid.

**Pitfall 1: {Description}**
- **Consequence**: What goes wrong
- **Avoidance**: How to avoid this mistake

**Pitfall 2: {Description}**
...

---

## Alternatives Considered

Other approaches that were considered and why they were not chosen (if applicable).

**Alternative 1: {Name}**
- **Pros**: Benefits of this approach
- **Cons**: Drawbacks
- **Decision**: Why not chosen

**Alternative 2: {Name}**
...

---

## Related Issues

Links to GitHub issues that reference this research.

- #{issue_number} - Brief description
- #{issue_number} - Brief description

---

## Maintenance

**Last Updated**: YYYY-MM-DD
**Next Review**: YYYY-MM-DD (if applicable)

**Update Triggers** (when to review this research):
- When technology version changes (e.g., new Python version)
- When security standards are updated
- When project requirements change
- Annually (for ongoing patterns)
```

---

## Validation Checklist

Before saving a research document, validate:

**Format**:
- [ ] Filename uses SCREAMING_SNAKE_CASE
- [ ] File location is docs/research/
- [ ] Includes frontmatter (Issue Reference, Research Date, Status)
- [ ] Has all required sections (Overview, Key Findings, Source References, Implementation Notes)

**Content Quality**:
- [ ] Research is substantial (2+ findings/practices/considerations)
- [ ] Sources are authoritative and cited with URLs
- [ ] Implementation notes are actionable
- [ ] Security considerations included (if applicable)
- [ ] Related issues are linked

**Reusability**:
- [ ] Research will be referenced by future features
- [ ] Patterns are generalizable beyond single feature
- [ ] Guidance is clear enough for other developers

**Index**:
- [ ] docs/research/README.md updated with new entry
- [ ] Brief description added to README

---

## Examples

### Good Research Document

```markdown
# JWT Authentication Research

> **Issue Reference**: #123
> **Research Date**: 2025-12-17
> **Status**: Active

## Overview

Research on JWT authentication best practices for secure API access. Needed for implementing user authentication in the API layer.

**Context**: Feature #123 requires JWT authentication for API endpoints. Research focuses on security best practices and recommended libraries.

---

## Key Findings

### Finding 1: Use RS256 (Asymmetric) for Production

**Description**: RS256 uses public/private key pairs for signing JWTs, making it more secure than symmetric algorithms (HS256) for distributed systems.

**Rationale**: Private key stays on auth server only, public key distributed to API servers. Compromised API server cannot forge tokens.

**Example**:
```python
from jose import jwt

# Sign with private key (auth server)
token = jwt.encode(claims, private_key, algorithm='RS256')

# Verify with public key (API server)
claims = jwt.decode(token, public_key, algorithms=['RS256'])
```

### Finding 2: Short Expiry with Refresh Tokens

**Description**: Access tokens should have short expiry (15 minutes), use refresh tokens for long-lived sessions.

**Rationale**: Limits damage if access token is compromised. Refresh tokens stored securely and can be revoked.

---

## Source References

- **JWT.io**: https://jwt.io/introduction - Official JWT documentation and debugging tools
- **OWASP JWT Cheatsheet**: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html - Security best practices
- **PyJWT Docs**: https://pyjwt.readthedocs.io/ - Python JWT library documentation

---

## Implementation Notes

**Recommended Approach**:
1. Install PyJWT library: `pip install pyjwt[crypto]`
2. Generate RSA key pair for production
3. Implement token generation endpoint
4. Implement token validation middleware
5. Add refresh token endpoint

**Code Patterns**:
```python
# Token generation
def create_access_token(user_id: str) -> str:
    claims = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "iat": datetime.utcnow(),
        "iss": "api.example.com"
    }
    return jwt.encode(claims, private_key, algorithm='RS256')

# Token validation middleware
def validate_token(token: str) -> dict:
    try:
        return jwt.decode(token, public_key, algorithms=['RS256'])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired")
    except jwt.JWTError:
        raise AuthError("Invalid token")
```

---

## Security Considerations

**Risks**:
- **Token theft**: Access tokens can be stolen from client storage (high severity)
- **Algorithm confusion**: Attacker changes algorithm to 'none' (medium severity)

**Mitigations**:
- Store tokens in HttpOnly cookies (prevents XSS attacks)
- Always specify allowed algorithms in jwt.decode() (prevents algorithm confusion)
- Use short expiry times (limits damage from token theft)
- Implement token revocation for refresh tokens

---

## Common Pitfalls

**Pitfall 1: Storing sensitive data in JWT claims**
- **Consequence**: JWT is base64-encoded, not encrypted. Claims are readable by anyone with the token.
- **Avoidance**: Only store non-sensitive data (user_id, roles). Fetch sensitive data from database after validation.

**Pitfall 2: Using HS256 with shared secret across services**
- **Consequence**: Any service with the secret can forge tokens
- **Avoidance**: Use RS256 for distributed systems, only share public key

---

## Related Issues

- #123 - Implement JWT authentication for API endpoints
- #145 - Add refresh token endpoint

---

## Maintenance

**Last Updated**: 2025-12-17
**Next Review**: 2026-06-17

**Update Triggers**:
- When PyJWT library has major version update
- When OWASP updates JWT security recommendations
- When new JWT vulnerabilities are discovered
```

---

## Anti-Patterns

**What NOT to do**:

### Too Trivial
```markdown
# String Concatenation Research

## Key Findings
- Use f-strings instead of + operator

## Sources
- Python docs
```
**Problem**: This is common knowledge, doesn't need a research doc. Use inline comments instead.

### No Structure
```markdown
Found that JWT should use RS256. OWASP says short expiry is good.
Use PyJWT library. Tokens can be stolen.
```
**Problem**: No template structure, hard to read, missing sources and implementation guidance.

### Missing Context
```markdown
# JWT Research

## Findings
- RS256 is better than HS256
- Short expiry recommended
```
**Problem**: No issue reference, no date, no sources, no implementation notes. Can't determine relevance or apply findings.

---

## Integration with Agents

**researcher-web agent**:
- Decides whether to persist research based on criteria
- Creates research document following template
- Updates docs/research/README.md

**doc-master agent**:
- Validates research documentation format
- Ensures README.md is up-to-date
- Checks cross-references work

**implementer agent**:
- References research docs when implementing features
- Follows patterns documented in research

---

**This skill provides complete standards for research documentation persistence and reuse.**
