# Testing Layers

## Testing Layers: When to Use Which

### Layer 1: Unit Tests (pytest, fast)

**What**: Individual functions in isolation
**When**: Every function with logic
**Speed**: < 1 second total
**CI/CD**: YES, run on every commit

**Example**:
```python
# tests/unit/test_auth.py
def test_hash_password():
    """Test password is hashed."""
    hashed = hash_password("secret123")
    assert hashed != "secret123"  # Binary: not plaintext
    assert len(hashed) == 60  # bcrypt length
```

**Validation Type**: STRUCTURE
- ✅ Fast
- ✅ Deterministic
- ✅ Automated
- ❌ Doesn't check if hashing algorithm is secure

---

### Layer 2: Integration Tests (pytest, medium)

**What**: Components working together
**When**: Testing workflows, API endpoints, database interactions
**Speed**: < 10 seconds total
**CI/CD**: YES, run before merge

**Example**:
```python
# tests/integration/test_user_workflow.py
def test_user_registration_workflow(db):
    """Test complete user registration."""
    # Create user
    user = register_user("test@example.com", "password123")

    # Verify in database
    db_user = db.query(User).filter_by(email="test@example.com").first()
    assert db_user is not None

    # Verify password hashed
    assert db_user.password != "password123"
```

**Validation Type**: BEHAVIOR
- ✅ Tests real workflows
- ✅ Catches integration issues
- ✅ Automated
- ❌ Doesn't validate if workflow serves business goals

---

### Layer 3: UAT Tests (pytest, slow)

**What**: End-to-end user workflows
**When**: Before release, testing complete features
**Speed**: < 60 seconds total
**CI/CD**: Optional, can run nightly

**Example**:
```python
# tests/uat/test_user_journey.py
def test_complete_user_journey(tmp_path):
    """Test user journey: signup → login → create post → logout."""
    # Setup
    app = create_app(tmp_path)

    # Signup
    response = app.post("/signup", data={"email": "user@test.com"})
    assert response.status_code == 201

    # Login
    response = app.post("/login", data={"email": "user@test.com"})
    assert "session_token" in response.cookies

    # Create post
    response = app.post("/posts", json={"title": "Test"})
    assert response.status_code == 201

    # Logout
    response = app.post("/logout")
    assert "session_token" not in response.cookies
```

**Validation Type**: WORKS
- ✅ Tests complete user experience
- ✅ Catches workflow breaks
- ✅ Can be automated (but slow)
- ❌ Doesn't validate if feature aligns with strategic goals

---

### Layer 4: GenAI Validation (Claude, comprehensive)

**What**: Architectural intent, semantic alignment, quality assessment
**When**: Before release, after major changes, monthly maintenance
**Speed**: 2-5 minutes (manual review)
**CI/CD**: NO, requires human review

**Example**:
```markdown
# /validate-architecture

## Validate: Does orchestrator enforce PROJECT.md-first architecture?

Read agents/orchestrator.md and analyze:

1. **Intent (from ARCHITECTURE.md)**:
   "Prevent scope creep by validating alignment before work"

2. **Implementation Analysis**:
   - Does orchestrator check if PROJECT.md exists?
   - Does it read GOALS, SCOPE, CONSTRAINTS?
   - Does it validate feature aligns with goals?
   - Does it block work if misaligned?
   - Does it create PROJECT.md if missing?

3. **Behavioral Evidence**:
   - Line 20: `if [ ! -f PROJECT.md ]` ✓ Checks existence
   - Line 81-83: Reads GOALS/SCOPE/CONSTRAINTS ✓
   - Line 357-391: Displays rejection if misaligned ✓
   - Line 77: `exit 0` blocks work if PROJECT.md missing ✓

**Assessment**: ✅ ALIGNED
Implementation matches documented intent. Orchestrator actually
enforces PROJECT.md-first, not just mentions it.

**Why GenAI?**:
Static test could only check if "PROJECT.md" appears in file.
GenAI validates the BEHAVIOR matches the INTENT.
```

**Validation Type**: INTENT
- ✅ Validates semantic meaning
- ✅ Detects architectural drift
- ✅ Assesses quality and design
- ❌ Slow, requires human review
- ❌ Not deterministic (slight variations)

---
