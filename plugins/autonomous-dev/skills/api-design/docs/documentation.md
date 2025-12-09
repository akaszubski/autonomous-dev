# Documentation

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
