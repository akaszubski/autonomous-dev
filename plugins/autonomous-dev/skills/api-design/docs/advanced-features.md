# Advanced Features

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
