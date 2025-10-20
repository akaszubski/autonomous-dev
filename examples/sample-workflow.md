# Sample Workflow - Complete Feature Development

This example shows the complete autonomous workflow from feature request to production.

---

## Scenario: Add User Authentication

**Project**: Python web application
**Goal**: Add JWT-based authentication
**Time**: ~2 hours (manual would take 6+ hours)

---

## Step 1: Feature Request

**User**:
> "Add JWT authentication to the API"

**Claude** (automatic alignment check):
> I'll help add JWT authentication. First, let me check alignment with PROJECT.md...
>
> ✓ Aligns with GOALS: "Secure API access"
> ✓ Within SCOPE: "Authentication & authorization"
> ✓ Respects CONSTRAINTS: "Use industry-standard security"
>
> Proceeding with implementation...

---

## Step 2: Orchestrator Coordinates

**Orchestrator agent** (automatic):
> Coordinating 8-agent pipeline for JWT authentication feature...
>
> **Plan**:
> 1. researcher: Find JWT best practices
> 2. planner: Design authentication architecture (using Opus)
> 3. test-master: Write tests first (TDD)
> 4. implementer: Implement to pass tests
> 5. reviewer: Quality check
> 6. security-auditor: Security audit (using Haiku)
> 7. doc-master: Update documentation (using Haiku)
>
> Starting pipeline...

---

## Step 3: Research Phase

**Researcher agent** (automatic):
> Researching JWT authentication best practices...
>
> **Findings**:
> - Industry standard: PyJWT library
> - Best practice: Access tokens (15min) + Refresh tokens (7 days)
> - Security: HMAC-SHA256 signing
> - Storage: httpOnly cookies
>
> **Existing patterns in codebase**:
> - Found: Existing user model in models/user.py
> - Found: Password hashing in auth/utils.py
> - Found: Session management in auth/session.py
>
> **Recommendation**: Extend existing auth system with JWT

---

## Step 4: Architecture Planning

**Planner agent** (automatic, using Opus for complex planning):
> Designing JWT authentication architecture...
>
> **Design**:
> ```
> auth/
> ├── jwt_manager.py     # JWT creation/validation
> ├── middleware.py      # Request authentication
> └── decorators.py      # @require_auth decorator
>
> endpoints/
> └── auth_endpoints.py  # /login, /refresh, /logout
>
> tests/
> ├── test_jwt_manager.py
> ├── test_middleware.py
> └── test_auth_endpoints.py
> ```
>
> **Implementation tasks**:
> 1. Create JWTManager class
> 2. Add authentication middleware
> 3. Create login/refresh endpoints
> 4. Add @require_auth decorator
> 5. Update existing endpoints to use decorator
>
> Ready to implement...

---

## Step 5: Test-Driven Development

**Test-master agent** (automatic):
> Writing tests first (TDD approach)...
>
> **Created tests/**:
> - test_jwt_manager.py (12 tests)
> - test_middleware.py (8 tests)
> - test_auth_endpoints.py (15 tests)
>
> **Test coverage planned**: 95%+
>
> **Running tests** (should fail - no implementation yet):
> ```
> ❌ test_jwt_manager.py::test_create_access_token FAILED
> ❌ test_middleware.py::test_auth_required FAILED
> ❌ test_auth_endpoints.py::test_login_success FAILED
> ... (35 failures - expected!)
> ```
>
> Tests written. Ready for implementation...

---

## Step 6: Implementation

**Implementer agent** (automatic):
> Implementing JWT authentication to pass tests...
>
> **Created auth/jwt_manager.py**:
> ```python
> from datetime import datetime, timedelta
> import jwt
> from typing import Dict, Optional
>
> class JWTManager:
>     """JWT token management."""
>
>     def __init__(self, secret_key: str, algorithm: str = "HS256"):
>         self.secret_key = secret_key
>         self.algorithm = algorithm
>
>     def create_access_token(
>         self,
>         user_id: int,
>         expires_delta: timedelta = timedelta(minutes=15)
>     ) -> str:
>         """Create JWT access token."""
>         payload = {
>             "user_id": user_id,
>             "exp": datetime.utcnow() + expires_delta,
>             "type": "access"
>         }
>         return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
>
>     # ... (10 more methods)
> ```
>
> **Auto-formatted** (black + isort):
> ✓ Code formatted
> ✓ Imports organized
>
> **Running tests**:
> ```
> ✓ test_jwt_manager.py::test_create_access_token PASSED
> ✓ test_middleware.py::test_auth_required PASSED
> ✓ test_auth_endpoints.py::test_login_success PASSED
> ... (35/35 tests passed!)
> ```
>
> Implementation complete. Coverage: 96%

---

## Step 7: Quality Review

**Reviewer agent** (automatic):
> Reviewing JWT authentication implementation...
>
> **Code quality**: ✓
> - Follows python-standards skill
> - Type hints present
> - Docstrings complete
> - Error handling robust
>
> **Test coverage**: ✓
> - 96% coverage (exceeds 80% requirement)
> - Edge cases covered
> - Error paths tested
>
> **Documentation**: ✓
> - API docs updated
> - README updated
> - Examples provided
>
> **Patterns**: ✓
> - Consistent with existing auth code
> - Follows project conventions
> - No code duplication
>
> Quality check passed!

---

## Step 8: Security Audit

**Security-auditor agent** (automatic, using Haiku for cost efficiency):
> Running security audit on JWT implementation...
>
> **Checks**:
> ✓ No hardcoded secrets
> ✓ Secret key from environment variable
> ✓ HMAC-SHA256 signing (industry standard)
> ✓ Token expiration enforced
> ✓ Refresh token rotation implemented
> ✓ httpOnly cookies (prevents XSS)
> ✓ CSRF protection enabled
> ✓ No SQL injection vulnerabilities
> ✓ Input validation present
> ✓ Rate limiting added
>
> **Recommendations**:
> ✓ Added: Rate limiting (10 attempts/min)
> ✓ Added: Token blacklist for logout
> ✓ Added: Password requirements validation
>
> Security audit passed!

---

## Step 9: Documentation Update

**Doc-master agent** (automatic, using Haiku):
> Updating documentation for JWT authentication...
>
> **Updated**:
> - README.md: Added authentication section
> - API.md: Documented /login, /refresh, /logout endpoints
> - SETUP.md: Added JWT_SECRET_KEY configuration
> - SECURITY.md: Documented token lifecycle
>
> **Created**:
> - docs/authentication.md: Complete authentication guide
> - examples/auth_example.py: Usage example
>
> **Cross-references validated**: ✓
> - All links working
> - Code examples current
> - Version numbers correct
>
> Documentation complete!

---

## Step 10: Automatic Commit

**Auto-commit hook** (automatic):
> Creating conventional commit...
>
> ```bash
> git add .
> git commit -m "$(cat <<'EOF'
> feat(auth): add JWT authentication
>
> - Implement JWTManager for token creation/validation
> - Add authentication middleware
> - Create /login, /refresh, /logout endpoints
> - Add @require_auth decorator
> - 96% test coverage (35 tests)
> - Security audit passed
> - Documentation updated
>
> 🤖 Generated with Claude Code
>
> Co-Authored-By: Claude <noreply@anthropic.com>
> EOF
> )"
> ```
>
> Commit created: abc1234

---

## Step 11: Complete Quality Check

**User** (optional):
> /full-check

**Full-check command**:
> Running complete quality check...
>
> **Formatting**: ✓
> - black: All files formatted
> - isort: Imports organized
> - ruff: No linting errors
>
> **Testing**: ✓
> - Unit tests: 35/35 passed
> - Integration tests: 8/8 passed
> - Coverage: 96% (exceeds 80%)
>
> **Security**: ✓
> - No secrets detected
> - No vulnerabilities
> - OWASP compliance: ✓
>
> **Documentation**: ✓
> - README updated
> - API docs current
> - Examples provided
>
> **Architecture alignment**: ✓
> - Aligns with PROJECT.md goals
> - Follows existing patterns
> - No drift detected
>
> All checks passed! Ready to push. ✓

---

## Summary

**What you did**:
1. Requested: "Add JWT authentication"

**What the system did automatically**:
1. ✓ Validated alignment with PROJECT.md
2. ✓ Researched best practices
3. ✓ Designed architecture (Opus)
4. ✓ Wrote 35 tests first (TDD)
5. ✓ Implemented code to pass tests
6. ✓ Auto-formatted code (black, isort)
7. ✓ Reviewed quality
8. ✓ Audited security (Haiku)
9. ✓ Updated documentation (Haiku)
10. ✓ Created conventional commit

**Time**:
- Manual: 6-8 hours
- Autonomous: 2 hours (4x faster!)

**Quality**:
- ✓ 96% test coverage
- ✓ Security audit passed
- ✓ Documentation complete
- ✓ Production-ready

**Cost optimization**:
- Opus: Complex planning only
- Haiku: Security audit, documentation
- Result: High quality, low cost

---

## What You Learned

1. **PROJECT.md-first**: Every feature validated against strategic goals
2. **8-agent pipeline**: Each agent has a specific role
3. **Model optimization**: Opus for planning, Haiku for routine tasks
4. **Automatic quality**: Formatting, testing, security, docs all automatic
5. **Focus on features**: You specify what, system handles how

---

**Next feature?** Just describe what you want. The system handles the rest! 🚀
