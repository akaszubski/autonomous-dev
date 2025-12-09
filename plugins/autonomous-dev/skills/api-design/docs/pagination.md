# Pagination

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
