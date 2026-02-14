# Rest Principles

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
