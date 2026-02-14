# Idempotency Content Negotiation

## Idempotency

### Idempotency Keys (POST)

**Problem**: POST requests aren't idempotent (create duplicate resources if retried)

**Solution**: Idempotency keys

```bash
POST /payments
Idempotency-Key: abc123...

{
  "amount": 100,
  "currency": "USD"
}
```

**Implementation**:
```python
import redis

redis_client = redis.Redis()

@app.post("/payments")
def create_payment(
    payment: Payment,
    idempotency_key: str = Header(...)
):
    # Check if we've seen this key before
    cached = redis_client.get(f"idempotency:{idempotency_key}")
    if cached:
        return json.loads(cached)

    # Process payment
    result = process_payment(payment)

    # Cache result for 24 hours
    redis_client.setex(
        f"idempotency:{idempotency_key}",
        86400,
        json.dumps(result)
    )

    return result
```

---

## Content Negotiation

**Client specifies desired format**:

```bash
GET /users
Accept: application/json  # JSON response

GET /users
Accept: application/xml   # XML response
```

**Implementation**:
```python
from fastapi import Request

@app.get("/users")
def get_users(request: Request):
    users = db.get_users()

    if "application/xml" in request.headers.get("accept", ""):
        return Response(content=to_xml(users), media_type="application/xml")
    else:
        return users  # JSON by default
```

---
