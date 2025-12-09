# Authentication

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
