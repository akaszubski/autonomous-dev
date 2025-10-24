---
name: api-design
type: knowledge
description: REST API design best practices, versioning strategies, error handling, pagination, and OpenAPI documentation. Use when designing or implementing REST APIs, HTTP endpoints, or API documentation.
keywords: api, rest, endpoint, http, json, openapi, swagger, versioning, pagination, api design
auto_activate: true
---

# API Design Skill

REST API design best practices, HTTP conventions, versioning, error handling, and documentation standards.

## When This Skill Activates

- Designing REST APIs
- Creating HTTP endpoints
- Writing API documentation
- Handling API errors
- Implementing pagination
- API versioning strategies
- Keywords: "api", "rest", "endpoint", "http", "json", "openapi"

---

## REST Principles

### RESTful Resource Design

**Resources are nouns, not verbs**:

```bash
# ✅ GOOD: Resource-based
GET    /users              # List users
GET    /users/123          # Get user 123
POST   /users              # Create user
PUT    /users/123          # Update user 123
DELETE /users/123          # Delete user 123

# ❌ BAD: Action-based
GET    /getUsers
POST   /createUser
POST   /updateUser
POST   /deleteUser
```

### HTTP Methods (Verbs)

| Method | Purpose | Idempotent? | Safe? |
|--------|---------|-------------|-------|
| **GET** | Read resource | ✅ Yes | ✅ Yes |
| **POST** | Create resource | ❌ No | ❌ No |
| **PUT** | Replace resource | ✅ Yes | ❌ No |
| **PATCH** | Update partial resource | ❌ No | ❌ No |
| **DELETE** | Delete resource | ✅ Yes | ❌ No |

**Idempotent**: Same request → same result (can retry safely)
**Safe**: No side effects (doesn't modify data)

---

## URL Structure

### Resource Naming

**Use plural nouns**:
```bash
# ✅ GOOD: Plural
/users
/posts
/comments

# ❌ BAD: Singular
/user
/post
/comment
```

**Use hierarchical structure for relationships**:
```bash
# ✅ GOOD: Nested resources
GET /users/123/posts              # Posts by user 123
GET /posts/456/comments           # Comments on post 456
POST /users/123/posts             # Create post for user 123

# ❌ BAD: Flat structure
GET /posts?user_id=123            # Less clear
```

**Keep URLs shallow (max 3 levels)**:
```bash
# ✅ GOOD: 2-3 levels
/users/123/posts
/posts/456/comments

# ❌ BAD: Too deep
/users/123/posts/456/comments/789/replies
# Use: /comments/789/replies instead
```

### Query Parameters

**Use for filtering, sorting, pagination**:

```bash
# Filtering
GET /users?role=admin
GET /users?created_after=2024-01-01

# Sorting
GET /posts?sort=created_at&order=desc
GET /posts?sort=-created_at  # - prefix for descending

# Pagination
GET /users?page=2&limit=20
GET /users?offset=40&limit=20

# Search
GET /users?q=john
GET /posts?search=python
```

---

## HTTP Status Codes

### Success Codes (2xx)

```
200 OK                  - Request succeeded (GET, PUT, PATCH)
201 Created             - Resource created (POST)
204 No Content          - Success, no response body (DELETE)
```

**Examples**:
```python
# 200 OK - Return resource
@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = db.get_user(user_id)
    return JSONResponse(content=user, status_code=200)

# 201 Created - Return created resource + Location header
@app.post("/users")
def create_user(user: User):
    created = db.create_user(user)
    return JSONResponse(
        content=created,
        status_code=201,
        headers={"Location": f"/users/{created['id']}"}
    )

# 204 No Content - No body needed
@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    db.delete_user(user_id)
    return Response(status_code=204)
```

### Client Error Codes (4xx)

```
400 Bad Request         - Invalid request body/parameters
401 Unauthorized        - Authentication required
403 Forbidden           - Authenticated but not allowed
404 Not Found           - Resource doesn't exist
409 Conflict            - Conflict (e.g., duplicate email)
422 Unprocessable       - Validation error
429 Too Many Requests   - Rate limit exceeded
```

### Server Error Codes (5xx)

```
500 Internal Server Error - Unexpected server error
503 Service Unavailable   - Server temporarily down
```

---

## Error Response Format

### RFC 7807 (Problem Details)

**Standard error format**:

```json
{
  "type": "https://example.com/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "Email address is invalid",
  "instance": "/users",
  "errors": {
    "email": ["Must be a valid email address"],
    "password": ["Must be at least 8 characters"]
  }
}
```

**Implementation**:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: dict = {}

@app.post("/users")
def create_user(user: User):
    if not validate_email(user.email):
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://example.com/errors/validation-error",
                "title": "Validation Error",
                "status": 422,
                "detail": "Invalid email address",
                "instance": "/users",
                "errors": {
                    "email": ["Must be a valid email address"]
                }
            }
        )
```

### Consistent Error Structure

**Minimal error (for simple cases)**:
```json
{
  "error": "Invalid email address",
  "code": "VALIDATION_ERROR"
}
```

**Detailed error (for complex cases)**:
```json
{
  "error": "Validation failed",
  "code": "VALIDATION_ERROR",
  "message": "One or more fields failed validation",
  "fields": {
    "email": "Must be a valid email address",
    "password": "Must be at least 8 characters"
  },
  "timestamp": "2025-10-24T12:00:00Z",
  "path": "/users"
}
```

---

## Request/Response Format

### Request Body (POST/PUT/PATCH)

**JSON format**:
```json
POST /users
Content-Type: application/json

{
  "email": "user@example.com",
  "name": "John Doe",
  "role": "admin"
}
```

**Python (FastAPI)**:
```python
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    role: str

@app.post("/users")
def create_user(user: UserCreate):
    # user.email, user.name, user.role automatically validated
    return db.create_user(user.dict())
```

### Response Body

**Single resource**:
```json
GET /users/123

{
  "id": 123,
  "email": "user@example.com",
  "name": "John Doe",
  "created_at": "2025-10-24T12:00:00Z"
}
```

**Collection**:
```json
GET /users

{
  "data": [
    {"id": 1, "email": "user1@example.com"},
    {"id": 2, "email": "user2@example.com"}
  ],
  "meta": {
    "total": 100,
    "page": 1,
    "limit": 20,
    "pages": 5
  }
}
```

---

## Pagination

### Offset-Based Pagination

**Query parameters**:
```bash
GET /users?page=2&limit=20
GET /users?offset=40&limit=20
```

**Response**:
```json
{
  "data": [...],
  "meta": {
    "total": 100,
    "offset": 40,
    "limit": 20,
    "next": "/users?offset=60&limit=20",
    "prev": "/users?offset=20&limit=20"
  }
}
```

**Implementation**:
```python
@app.get("/users")
def list_users(page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    users = db.get_users(offset=offset, limit=limit)
    total = db.count_users()

    return {
        "data": users,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    }
```

**Pros**: Simple, can jump to any page
**Cons**: Inconsistent if data changes between requests

---

### Cursor-Based Pagination

**Better for real-time data**:

```bash
GET /users?cursor=abc123&limit=20
```

**Response**:
```json
{
  "data": [...],
  "meta": {
    "next_cursor": "def456",
    "prev_cursor": "xyz789",
    "has_more": true
  }
}
```

**Implementation**:
```python
@app.get("/users")
def list_users(cursor: str = None, limit: int = 20):
    users = db.get_users_after_cursor(cursor, limit)
    next_cursor = users[-1].id if users else None

    return {
        "data": users,
        "meta": {
            "next_cursor": next_cursor,
            "has_more": len(users) == limit
        }
    }
```

**Pros**: Consistent results, works with real-time data
**Cons**: Can't jump to arbitrary page

---

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

## Authentication & Authorization

### API Key (Simple)

```bash
GET /users
Authorization: Bearer sk-abc123...
```

**Implementation**:
```python
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/users")
def list_users(credentials: HTTPAuthorizationCredentials = Security(security)):
    api_key = credentials.credentials
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return get_users()
```

---

### JWT (Stateless)

```bash
GET /users
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Implementation**:
```python
import jwt
from datetime import datetime, timedelta

SECRET = "your-secret-key"

def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/users")
def list_users(token: str = Security(security)):
    payload = verify_token(token)
    user_id = payload["user_id"]
    return get_users_for(user_id)
```

---

## Rate Limiting

### Headers

```bash
X-RateLimit-Limit: 1000       # Max requests per hour
X-RateLimit-Remaining: 999    # Requests remaining
X-RateLimit-Reset: 1698768000 # Unix timestamp when limit resets
```

**Implementation**:
```python
from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import redis

redis_client = redis.Redis()

RATE_LIMIT = 1000  # per hour

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"

    # Increment counter
    current = redis_client.incr(key)

    # Set expiration on first request
    if current == 1:
        redis_client.expire(key, 3600)  # 1 hour

    # Get TTL
    ttl = redis_client.ttl(key)
    reset_time = datetime.now() + timedelta(seconds=ttl)

    # Check limit
    if current > RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(RATE_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_time.timestamp()))
            }
        )

    # Add headers
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT)
    response.headers["X-RateLimit-Remaining"] = str(RATE_LIMIT - current)
    response.headers["X-RateLimit-Reset"] = str(int(reset_time.timestamp()))

    return response
```

---

## CORS (Cross-Origin Resource Sharing)

**Allow browser requests from different domains**:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://example.com"],  # Specific origins
    # allow_origins=["*"],  # All origins (development only!)
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## Filtering & Sorting

### Filtering

```bash
# Single filter
GET /users?role=admin

# Multiple filters
GET /users?role=admin&status=active

# Range filters
GET /posts?created_after=2024-01-01&created_before=2024-12-31

# Search
GET /users?q=john
```

**Implementation**:
```python
@app.get("/users")
def list_users(
    role: str = None,
    status: str = None,
    q: str = None
):
    query = db.query(User)

    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    if q:
        query = query.filter(User.name.contains(q))

    return query.all()
```

### Sorting

```bash
# Ascending
GET /posts?sort=created_at

# Descending (- prefix)
GET /posts?sort=-created_at

# Multiple sorts
GET /posts?sort=-created_at,title
```

**Implementation**:
```python
@app.get("/posts")
def list_posts(sort: str = None):
    query = db.query(Post)

    if sort:
        for field in sort.split(','):
            if field.startswith('-'):
                # Descending
                query = query.order_by(desc(getattr(Post, field[1:])))
            else:
                # Ascending
                query = query.order_by(asc(getattr(Post, field)))

    return query.all()
```

---

## OpenAPI (Swagger) Documentation

### Auto-Generated Docs (FastAPI)

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="My API",
    description="API for managing users and posts",
    version="1.0.0",
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc"     # ReDoc UI
)

class User(BaseModel):
    """User model"""
    id: int = Field(..., description="Unique user ID")
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User full name")

@app.get(
    "/users/{user_id}",
    response_model=User,
    summary="Get user by ID",
    description="Retrieve a single user by their unique ID",
    responses={
        200: {"description": "User found"},
        404: {"description": "User not found"}
    }
)
def get_user(user_id: int):
    """
    Get user by ID.

    Returns user object if found, 404 if not found.
    """
    return db.get_user(user_id)
```

**Auto-generated docs at**:
- `/docs` - Swagger UI (interactive)
- `/redoc` - ReDoc (pretty)
- `/openapi.json` - OpenAPI spec

---

## Idempotency

### Idempotency Keys (POST)

**Problem**: POST requests aren't idempotent (create duplicate resources if retried)

**Solution**: Idempotency keys

```bash
POST /payments
Idempotency-Key: abc123...

{
  "amount": 100,
  "currency": "USD"
}
```

**Implementation**:
```python
import redis

redis_client = redis.Redis()

@app.post("/payments")
def create_payment(
    payment: Payment,
    idempotency_key: str = Header(...)
):
    # Check if we've seen this key before
    cached = redis_client.get(f"idempotency:{idempotency_key}")
    if cached:
        return json.loads(cached)

    # Process payment
    result = process_payment(payment)

    # Cache result for 24 hours
    redis_client.setex(
        f"idempotency:{idempotency_key}",
        86400,
        json.dumps(result)
    )

    return result
```

---

## Content Negotiation

**Client specifies desired format**:

```bash
GET /users
Accept: application/json  # JSON response

GET /users
Accept: application/xml   # XML response
```

**Implementation**:
```python
from fastapi import Request

@app.get("/users")
def get_users(request: Request):
    users = db.get_users()

    if "application/xml" in request.headers.get("accept", ""):
        return Response(content=to_xml(users), media_type="application/xml")
    else:
        return users  # JSON by default
```

---

## API Design Checklist

**Before shipping an API**:

- [ ] **Nouns for resources** (/users, not /getUsers)
- [ ] **Plural resource names** (/users, not /user)
- [ ] **Proper HTTP methods** (GET/POST/PUT/DELETE)
- [ ] **Proper status codes** (200/201/204/400/404/500)
- [ ] **Consistent error format** (RFC 7807 or custom)
- [ ] **Pagination** (for collections)
- [ ] **Filtering & sorting** (query params)
- [ ] **Versioning** (/v1/users)
- [ ] **Authentication** (API key or JWT)
- [ ] **Rate limiting** (protect from abuse)
- [ ] **CORS** (if browser access needed)
- [ ] **Documentation** (OpenAPI/Swagger)
- [ ] **Idempotency** (for payment/critical endpoints)
- [ ] **Validation** (request body validation)
- [ ] **Security** (no secrets in responses)

---

## Common Patterns

### HATEOAS (Hypermedia)

**Include links to related resources**:

```json
GET /users/123

{
  "id": 123,
  "email": "user@example.com",
  "links": {
    "self": "/users/123",
    "posts": "/users/123/posts",
    "followers": "/users/123/followers"
  }
}
```

---

### Bulk Operations

**Batch create**:
```bash
POST /users/batch

{
  "users": [
    {"email": "user1@example.com"},
    {"email": "user2@example.com"}
  ]
}
```

**Batch update**:
```bash
PATCH /users/batch

{
  "updates": [
    {"id": 1, "status": "active"},
    {"id": 2, "status": "inactive"}
  ]
}
```

---

### Webhooks

**Allow clients to subscribe to events**:

```bash
POST /webhooks

{
  "url": "https://example.com/webhook",
  "events": ["user.created", "user.updated"]
}
```

**Send events**:
```python
import requests

def notify_webhook(event_type: str, data: dict):
    webhooks = db.get_webhooks(event_type)
    for webhook in webhooks:
        requests.post(webhook.url, json={
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })

# Usage
user = create_user(...)
notify_webhook("user.created", user)
```

---

## Key Takeaways

1. **Resources as nouns** (/users, not /getUsers)
2. **Use proper HTTP methods** (GET/POST/PUT/DELETE)
3. **Use proper status codes** (200/201/204/400/404)
4. **Version your API** (/v1, /v2)
5. **Paginate collections** (offset or cursor)
6. **Consistent errors** (RFC 7807)
7. **Authenticate requests** (API key or JWT)
8. **Rate limit** (protect from abuse)
9. **Document with OpenAPI** (auto-generate)
10. **Test idempotency** (especially payments)

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: security-patterns (API security), python-standards (FastAPI), testing-guide (API tests)
