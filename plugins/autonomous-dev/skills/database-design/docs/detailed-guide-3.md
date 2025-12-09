# Database Design - Detailed Guide

## Transactions

### ACID Properties

- **A**tomicity: All or nothing
- **C**onsistency: Valid state always
- **I**solation: Concurrent transactions don't interfere
- **D**urability: Committed data persists

### Using Transactions

**SQLAlchemy**:
```python
from sqlalchemy.orm import Session

with Session(engine) as session:
    try:
        user = User(email="test@example.com")
        session.add(user)

        post = Post(user_id=user.id, title="Test")
        session.add(post)

        session.commit()  # ✅ Both saved
    except Exception as e:
        session.rollback()  # ❌ Neither saved
        raise
```

**Django**:
```python
from django.db import transaction

with transaction.atomic():
    user = User.objects.create(email="test@example.com")
    Post.objects.create(user=user, title="Test")
    # ✅ Both saved or ❌ neither saved
```

**Raw SQL**:
```sql
BEGIN;
    INSERT INTO users (email) VALUES ('test@example.com');
    INSERT INTO posts (user_id, title) VALUES (1, 'Test');
COMMIT;
-- Or ROLLBACK; to cancel
```

---

## Connection Pooling

### Why Pool?

- Creating connections is expensive
- Reuse existing connections
- Limit concurrent connections

### SQLAlchemy Pooling

```python
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://user:pass@localhost/db',
    pool_size=10,          # Max 10 connections
    max_overflow=20,       # Allow 20 temporary connections
    pool_timeout=30,       # Wait 30s for connection
    pool_recycle=3600      # Recycle after 1 hour
)
```

### Django Pooling

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
        'CONN_MAX_AGE': 600,  # Persist connections for 10 min
    }
}
```

---

## Common Patterns
