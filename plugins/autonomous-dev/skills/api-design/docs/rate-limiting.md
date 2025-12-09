# Rate Limiting

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
