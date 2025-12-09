# Error Handling

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
