---
name: database-design
type: knowledge
description: Database schema design, migrations, query optimization, and ORM patterns. Use when designing database schemas, writing migrations, optimizing queries, or working with ORMs like SQLAlchemy or Django ORM.
keywords: database, schema, migration, query, sql, orm, sqlalchemy, django orm, postgres, mysql, index, transaction
auto_activate: true
---

# Database Design Skill

Database schema design, migration strategies, query optimization, and ORM best practices.

## When This Skill Activates

- Designing database schemas
- Writing database migrations
- Optimizing slow queries
- Working with ORMs (SQLAlchemy, Django ORM)
- Setting up database indexes
- Handling transactions
- Keywords: "database", "schema", "migration", "query", "sql", "orm"

---

## Schema Design Best Practices

### Normalization vs Denormalization

**Normalization** (Eliminate redundancy):
- ✅ Use for: Transactional systems (OLTP)
- ✅ Benefits: Data integrity, no update anomalies
- ❌ Drawback: More JOINs, slower reads

**Denormalization** (Add redundancy):
- ✅ Use for: Analytical systems (OLAP), read-heavy apps
- ✅ Benefits: Faster reads, fewer JOINs
- ❌ Drawback: Harder to maintain consistency

**Normal Forms Quick Reference**:

| Normal Form | Rule | Example |
|-------------|------|---------|
| 1NF | Atomic values, no repeating groups | No CSV in columns |
| 2NF | 1NF + no partial dependencies | All non-key columns depend on full primary key |
| 3NF | 2NF + no transitive dependencies | No non-key depends on another non-key |

**Practical Approach**:
```sql
-- ✅ GOOD: 3NF design (normalized)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ❌ BAD: Denormalized without reason
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    user_email VARCHAR(255),  -- Redundant! Violates 3NF
    total_amount DECIMAL(10, 2)
);
```

**When to Denormalize**:
```sql
-- ✅ GOOD: Denormalize for performance (read-heavy)
CREATE TABLE order_summary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    user_email VARCHAR(255),      -- Denormalized for fast reads
    total_amount DECIMAL(10, 2),
    order_count INTEGER,          -- Denormalized aggregate
    last_order_date TIMESTAMP
);
-- Use for dashboards, reporting, analytics
```

---

### Data Types

**Choose Appropriate Types**:

```sql
-- ✅ GOOD: Specific types
email VARCHAR(255)           -- Fixed max length
price DECIMAL(10, 2)         -- Exact precision for money
created_at TIMESTAMP         -- Date + time
is_active BOOLEAN            -- True/false
metadata JSONB               -- Structured data (PostgreSQL)

-- ❌ BAD: Vague types
email TEXT                   -- Unbounded
price FLOAT                  -- Precision errors with money!
created_at VARCHAR(50)       -- String instead of timestamp
is_active VARCHAR(5)         -- "true" vs true
```

**Money Handling**:
```sql
-- ✅ CORRECT: DECIMAL for money
price DECIMAL(10, 2)  -- Up to 99,999,999.99

-- ❌ WRONG: FLOAT for money
price FLOAT           -- Precision errors: 0.1 + 0.2 ≠ 0.3
```

---

### Primary Keys

**Auto-Incrementing Integer (Most Common)**:
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,  -- PostgreSQL
    -- id INT AUTO_INCREMENT PRIMARY KEY  -- MySQL
    email VARCHAR(255)
);
```

**UUID (Distributed Systems)**:
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255)
);
```

**Comparison**:

| Approach | Pros | Cons | Use When |
|----------|------|------|----------|
| **SERIAL/INT** | Simple, small, ordered | Not globally unique | Single database |
| **UUID** | Globally unique, no conflicts | Larger, unordered | Distributed systems, merging DBs |

---

### Foreign Keys & Relationships

**One-to-Many**:
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255)
);

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    content TEXT
);
```

**Many-to-Many** (Junction Table):
```sql
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
);

CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
);

CREATE TABLE enrollments (
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (student_id, course_id)
);
```

**ON DELETE Options**:
- `CASCADE` - Delete related records (use carefully!)
- `SET NULL` - Set foreign key to NULL
- `RESTRICT` - Prevent deletion (default)

**Best Practice**:
```sql
-- ✅ GOOD: Explicit CASCADE when you want it
user_id INTEGER REFERENCES users(id) ON DELETE CASCADE

-- ✅ GOOD: RESTRICT when you want protection
user_id INTEGER REFERENCES users(id) ON DELETE RESTRICT

-- ❌ BAD: No constraint (orphaned records)
user_id INTEGER  -- No REFERENCES!
```

---

## Indexing

### When to Add Indexes

**Always Index**:
- Primary keys (automatic)
- Foreign keys (manual in most DBs)
- Frequently queried columns (`WHERE`, `ORDER BY`, `GROUP BY`)
- Unique constraints (`UNIQUE`)

**Example**:
```sql
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,                    -- Indexed automatically
    user_id INTEGER REFERENCES users(id),     -- Should index!
    title VARCHAR(255),
    created_at TIMESTAMP,
    status VARCHAR(20)
);

-- Add indexes for common queries
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_created_at ON posts(created_at);
```

### Index Types

**B-Tree (Default)**:
```sql
-- For: =, <, >, <=, >=, BETWEEN, ORDER BY
CREATE INDEX idx_created_at ON posts(created_at);
```

**Hash** (PostgreSQL):
```sql
-- For: = only (faster than B-tree for equality)
CREATE INDEX idx_email ON users USING HASH (email);
```

**GIN** (Generalized Inverted Index - PostgreSQL):
```sql
-- For: Full-text search, JSONB, arrays
CREATE INDEX idx_tags ON posts USING GIN (tags);  -- Array column
CREATE INDEX idx_metadata ON posts USING GIN (metadata);  -- JSONB
```

**Partial Index**:
```sql
-- Index only active users (saves space)
CREATE INDEX idx_active_users ON users(email) WHERE is_active = true;
```

**Composite Index**:
```sql
-- For queries filtering by BOTH columns
CREATE INDEX idx_user_status ON posts(user_id, status);

-- ✅ Uses index
SELECT * FROM posts WHERE user_id = 1 AND status = 'published';

-- ✅ Uses index (leftmost prefix)
SELECT * FROM posts WHERE user_id = 1;

-- ❌ Does NOT use index (missing leftmost column)
SELECT * FROM posts WHERE status = 'published';
```

### Index Tradeoffs

**Pros**:
- ⚡ Faster reads (queries)
- ⚡ Faster JOINs

**Cons**:
- 🐢 Slower writes (INSERT, UPDATE, DELETE)
- 💾 More disk space
- 🔧 More maintenance

**Rule of Thumb**: Index columns in `WHERE`, `JOIN`, `ORDER BY` - but don't over-index.

---

## Query Optimization

### EXPLAIN ANALYZE

**Always profile slow queries**:

```sql
EXPLAIN ANALYZE
SELECT posts.*, users.email
FROM posts
JOIN users ON posts.user_id = users.id
WHERE posts.status = 'published'
ORDER BY posts.created_at DESC
LIMIT 10;
```

**What to Look For**:
- ❌ **Seq Scan** (table scan) - Add index!
- ✅ **Index Scan** - Using index
- ❌ **High cost** - Optimize query
- ❌ **Nested Loop** on large tables - Check JOIN

### N+1 Query Problem

**❌ BAD: N+1 queries (slow)**:
```python
# SQLAlchemy
users = session.query(User).all()
for user in users:
    print(user.posts)  # Triggers N queries!
# Total: 1 (users) + N (posts per user) queries
```

**✅ GOOD: Eager loading (fast)**:
```python
# SQLAlchemy
users = session.query(User).options(joinedload(User.posts)).all()
for user in users:
    print(user.posts)  # No extra query!
# Total: 1 query with JOIN
```

**Django ORM**:
```python
# ❌ BAD: N+1
users = User.objects.all()
for user in users:
    print(user.posts.all())  # N queries

# ✅ GOOD: prefetch_related
users = User.objects.prefetch_related('posts').all()
for user in users:
    print(user.posts.all())  # 2 queries total
```

### Common Optimizations

**Use LIMIT**:
```sql
-- ❌ BAD: Load everything
SELECT * FROM posts ORDER BY created_at DESC;

-- ✅ GOOD: Load only what you need
SELECT * FROM posts ORDER BY created_at DESC LIMIT 10;
```

**Avoid SELECT ***:
```sql
-- ❌ BAD: Load all columns
SELECT * FROM users WHERE id = 1;

-- ✅ GOOD: Load only needed columns
SELECT id, email FROM users WHERE id = 1;
```

**Use EXISTS instead of COUNT**:
```sql
-- ❌ SLOW: Counts all matching rows
SELECT COUNT(*) FROM posts WHERE user_id = 1;
IF count > 0 THEN ...

-- ✅ FAST: Stops at first match
SELECT EXISTS(SELECT 1 FROM posts WHERE user_id = 1 LIMIT 1);
```

---

## Migrations

### Migration Best Practices

**1. Make Migrations Reversible**:
```python
# ✅ GOOD: Can rollback
def upgrade():
    op.add_column('users', sa.Column('phone', sa.String(20)))

def downgrade():
    op.drop_column('users', 'phone')
```

**2. Avoid Locking (Large Tables)**:
```sql
-- ❌ BAD: Locks table (blocks reads/writes)
ALTER TABLE users ADD COLUMN phone VARCHAR(20) NOT NULL DEFAULT '';

-- ✅ GOOD: Add nullable first, backfill, then add constraint
ALTER TABLE users ADD COLUMN phone VARCHAR(20);  -- Step 1: No lock
-- Step 2: Backfill in batches (application code)
UPDATE users SET phone = '' WHERE phone IS NULL;
-- Step 3: Add constraint
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;
```

**3. Test Migrations**:
```bash
# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1

# Re-apply
alembic upgrade head
```

**4. Never Edit Merged Migrations**:
- Always create a new migration to fix issues
- Old migrations are historical record

### Migration Tools

**Python**:
- **Alembic** (SQLAlchemy)
- **Django Migrations** (Django ORM)

**Node.js**:
- **Knex.js**
- **TypeORM**

**Ruby**:
- **ActiveRecord Migrations** (Rails)

---

## ORM Patterns

### SQLAlchemy (Python)

**Define Models**:
```python
from sqlalchemy import Column, Integer, String, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    posts = relationship('Post', back_populates='user')

class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(255))
    user = relationship('User', back_populates='posts')
```

**Query**:
```python
# Create
user = User(email="test@example.com")
session.add(user)
session.commit()

# Read
user = session.query(User).filter_by(email="test@example.com").first()
users = session.query(User).filter(User.email.like('%@example.com')).all()

# Update
user.email = "new@example.com"
session.commit()

# Delete
session.delete(user)
session.commit()
```

**Eager Loading (Avoid N+1)**:
```python
from sqlalchemy.orm import joinedload

# ✅ GOOD: Load posts in one query
users = session.query(User).options(joinedload(User.posts)).all()
```

### Django ORM

**Define Models**:
```python
from django.db import models

class User(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=255)
    content = models.TextField()
```

**Query**:
```python
# Create
user = User.objects.create(email="test@example.com")

# Read
user = User.objects.get(email="test@example.com")
users = User.objects.filter(email__endswith="@example.com")

# Update
user.email = "new@example.com"
user.save()

# Delete
user.delete()
```

**Eager Loading**:
```python
# ✅ GOOD: Avoid N+1
users = User.objects.prefetch_related('posts').all()
```

---

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

### Soft Deletes

**Instead of deleting, mark as deleted**:

```sql
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    deleted_at TIMESTAMP NULL  -- NULL = not deleted
);

-- ❌ Hard delete
DELETE FROM posts WHERE id = 1;

-- ✅ Soft delete
UPDATE posts SET deleted_at = NOW() WHERE id = 1;

-- Query non-deleted
SELECT * FROM posts WHERE deleted_at IS NULL;
```

**ORM (SQLAlchemy)**:
```python
class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    deleted_at = Column(DateTime, nullable=True)

# Soft delete
post.deleted_at = datetime.now()
session.commit()

# Query non-deleted
active_posts = session.query(Post).filter(Post.deleted_at == None).all()
```

---

### Timestamps (created_at, updated_at)

**Always track when records are created/modified**:

```sql
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Trigger to auto-update updated_at (PostgreSQL)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_posts_updated_at BEFORE UPDATE ON posts
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**ORM (SQLAlchemy)**:
```python
from datetime import datetime

class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

### Unique Constraints

**Enforce uniqueness at database level**:

```sql
-- Single column
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL
);

-- Multiple columns (composite unique)
CREATE TABLE enrollments (
    student_id INTEGER,
    course_id INTEGER,
    UNIQUE (student_id, course_id)  -- Can't enroll twice in same course
);
```

---

## Database Choice

### PostgreSQL vs MySQL

| Feature | PostgreSQL | MySQL |
|---------|-----------|-------|
| **ACID** | ✅ Full | ✅ Full (InnoDB) |
| **JSON** | ✅ JSONB (binary) | ⚠️ JSON (text) |
| **Full-text** | ✅ Built-in | ✅ Built-in |
| **Window Functions** | ✅ Yes | ✅ Yes (8.0+) |
| **CTEs** | ✅ Yes | ✅ Yes (8.0+) |
| **Performance** | ⚡ Complex queries | ⚡ Simple queries |
| **Use Case** | Data-heavy, analytics | Web apps, simple queries |

**Recommendation**: PostgreSQL for most projects (richer features, better JSON support)

---

## Key Takeaways

1. **Normalize by default** - Denormalize only for performance
2. **Index strategically** - WHERE, JOIN, ORDER BY columns
3. **Avoid N+1 queries** - Use eager loading
4. **Use transactions** - For related operations
5. **Profile queries** - EXPLAIN ANALYZE for slow queries
6. **Test migrations** - Apply + rollback before merging
7. **Use foreign keys** - Enforce referential integrity
8. **Add timestamps** - created_at, updated_at on all tables
9. **Connection pooling** - Reuse connections
10. **Choose types carefully** - DECIMAL for money, TIMESTAMP for dates

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: python-standards (ORMs), testing-guide (database tests), security-patterns (SQL injection)
