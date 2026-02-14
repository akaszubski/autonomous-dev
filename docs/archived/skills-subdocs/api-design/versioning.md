# Versioning

## API Versioning

### URL Path Versioning (Recommended)

```bash
# ✅ GOOD: Version in URL
GET /v1/users
GET /v2/users
```

**Pros**:
- Simple, clear
- Easy to route
- Cached separately

**Cons**:
- URL changes

**Implementation**:
```python
# FastAPI
app = FastAPI()

v1_router = APIRouter(prefix="/v1")
v2_router = APIRouter(prefix="/v2")

@v1_router.get("/users")
def list_users_v1():
    return {"version": 1, "users": [...]}

@v2_router.get("/users")
def list_users_v2():
    return {"version": 2, "users": [...]}

app.include_router(v1_router)
app.include_router(v2_router)
```

---

### Header Versioning

```bash
GET /users
Accept: application/vnd.myapi.v1+json
```

**Pros**:
- Same URL
- Semantic

**Cons**:
- Harder to test (need headers)
- Not cached separately

---

### Breaking Changes

**What requires a new version**:
- ❌ Remove field
- ❌ Rename field
- ❌ Change field type
- ❌ Add required field
- ✅ Add optional field (backward compatible)

**Example**:
```json
// v1
{"id": 1, "name": "John"}

// v2 - Breaking change (renamed field)
{"id": 1, "full_name": "John"}  // Need /v2/users

// v2 - Non-breaking (added optional field)
{"id": 1, "name": "John", "email": "john@example.com"}  // Can keep /v1/users
```

---
