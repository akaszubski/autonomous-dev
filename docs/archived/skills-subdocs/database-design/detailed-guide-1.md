# Database Design - Detailed Guide

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
