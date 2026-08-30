---
name: api-design
description: "REST API design best practices covering versioning, error handling, pagination, and OpenAPI documentation. Use when designing or implementing REST APIs or HTTP endpoints. TRIGGER when: API design, REST endpoint, HTTP route, OpenAPI, swagger, pagination. DO NOT TRIGGER when: internal library code, CLI tools, non-HTTP interfaces."
allowed-tools: "Read"
---

# API Design Skill

Project conventions for REST API design, error handling, versioning, and documentation.

## Core Concepts

### 1. REST Principles

RESTful resource design using nouns (not verbs), proper HTTP methods, and hierarchical URL structure.

**Key Principles**:
- Resources are nouns: `/users`, `/posts` (not `/getUsers`, `/createPost`)
- Use HTTP methods correctly: GET (read), POST (create), PUT (replace), PATCH (update), DELETE (remove)
- Hierarchical relationships: `/users/123/posts` for related resources
- Keep URLs shallow (max 3 levels)

**See**: `docs/rest-principles.md` for detailed examples and patterns

---

### 2. Error Handling

RFC 7807 Problem Details format for consistent, structured error responses.

**Standard Format**:
```json
{
  "type": "https://example.com/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "Email address is invalid",
  "instance": "/users",
  "errors": {
    "email": ["Must be a valid email address"]
  }
}
```

**See**: `docs/error-handling.md` for implementation patterns and best practices

---

### 4. Request/Response Format

JSON structure conventions for request bodies and response payloads.

**Best Practices**:
- Use `snake_case` for JSON keys
- Include metadata in responses (timestamps, IDs)
- Consistent field naming across endpoints
- Clear data types and structures

**See**: `docs/request-response-format.md` for detailed examples

---

### 5. Pagination

Offset-based and cursor-based pagination strategies for large datasets.

**Offset-Based** (simple, good for small datasets):
```bash
GET /users?page=2&limit=20
```

**Cursor-Based** (scalable, handles real-time updates):
```bash
GET /users?cursor=abc123&limit=20
```

**See**: `docs/pagination.md` for implementation details and trade-offs

---

### 6. API Versioning

URL path versioning (recommended) and header-based versioning strategies.

**URL Path Versioning**:
```bash
/v1/users
/v2/users
```

**When to Version**:
- Breaking changes (removing fields, changing behavior)
- New required fields
- Changed data types

**See**: `docs/versioning.md` for migration strategies and deprecation policies

---

### 7. Authentication & Authorization

API key and JWT authentication patterns for securing endpoints.

**API Key** (simple, good for service-to-service):
```http
Authorization: Bearer sk_live_abc123...
```

**JWT** (stateless, good for user authentication):
```http
Authorization: Bearer eyJhbGc...
```

**See**: `docs/authentication.md` for implementation patterns

---

### 8. Rate Limiting

Rate limit headers and strategies to prevent abuse.

**Standard Headers**:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

**See**: `docs/rate-limiting.md` for implementation strategies

---

### 9. Advanced Features

CORS configuration, filtering, sorting, and search patterns.

**Topics**:
- CORS headers for browser-based clients
- Query parameter filtering
- Multi-field sorting
- Full-text search

**See**: `docs/advanced-features.md` for detailed patterns

---

### 10. Documentation

OpenAPI/Swagger documentation for API discoverability.

**Auto-Generated** (FastAPI):
```python
@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int):
    """Get user by ID"""
    return db.get_user(user_id)
```

**See**: `docs/documentation.md` for OpenAPI specifications

---

### 11. Design Patterns

Idempotency, content negotiation, HATEOAS, bulk operations, and webhooks.

**Topics**:
- Idempotency keys for safe retries
- Content negotiation (JSON, XML, etc.)
- HATEOAS for discoverable APIs
- Bulk operations for batch processing
- Webhooks for event notifications

**See**: `docs/idempotency-content-negotiation.md` and `docs/patterns-checklist.md`

---

## API Design Workflow

1. **Define resources** — identify nouns and relationships (`/users`, `/users/{id}/posts`)
2. **Design endpoints** — map CRUD to HTTP methods, keep URLs max 3 levels deep
3. **Implement error handling** — RFC 7807 format on all endpoints
4. **Add pagination** — offset or cursor-based on all collection endpoints
5. **Version the API** — URL path versioning (`/v1/`)
6. **Secure endpoints** — authentication (API key or JWT) + rate limiting
7. **Generate documentation** — OpenAPI spec, verify all endpoints documented
8. **Validate** — test idempotency for POST/PUT/DELETE, verify CORS if browser clients

**See**: `docs/patterns-checklist.md` for complete checklist

---

## Reference Documentation

| Topic | File |
|-------|------|
| REST principles | `docs/rest-principles.md` |
| Status codes | `docs/http-status-codes.md` |
| Error handling | `docs/error-handling.md` |
| Request/response format | `docs/request-response-format.md` |
| Pagination | `docs/pagination.md` |
| Versioning | `docs/versioning.md` |
| Authentication | `docs/authentication.md` |
| Rate limiting | `docs/rate-limiting.md` |
| CORS, filtering, sorting | `docs/advanced-features.md` |
| OpenAPI/Swagger | `docs/documentation.md` |
| Idempotency, HATEOAS, webhooks | `docs/idempotency-content-negotiation.md` |
| Full checklist | `docs/patterns-checklist.md` |

## Cross-References

- [error-handling](../error-handling/SKILL.md) — Error handling best practices
- [security-patterns](../security-patterns/SKILL.md) — API security hardening
- [python-standards](../python-standards/SKILL.md) — Python API implementation standards

## Hard Rules

**FORBIDDEN**:
- Exposing internal IDs or database schema in API responses
- Returning 200 for error conditions (use proper HTTP status codes)
- APIs without versioning (MUST use URL path versioning like `/v1/`)
- Endpoints that accept unbounded input without pagination or limits

**REQUIRED**:
- All endpoints MUST use RFC 7807 Problem Details error format
- All collection endpoints MUST support pagination
- All mutations MUST be idempotent or explicitly documented as non-idempotent
- Rate limiting MUST be documented in API specification
