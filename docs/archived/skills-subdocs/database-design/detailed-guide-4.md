# Database Design - Detailed Guide

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
