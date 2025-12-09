# Database Design - Detailed Guide

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
