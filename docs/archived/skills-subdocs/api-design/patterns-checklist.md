# Patterns Checklist

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
