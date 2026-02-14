# Request Response Format

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
