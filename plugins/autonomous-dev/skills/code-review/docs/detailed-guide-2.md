# Code Review - Detailed Guide

## Review Comment Templates

### Suggesting Improvements

```markdown
**suggestion**: Consider extracting this logic to a separate function for reusability.

Current:
```python
# Repeated logic in multiple places
if user.is_active and user.email_verified and not user.is_banned:
    ...
```

Suggested:
```python
def can_user_access_feature(user):
    return user.is_active and user.email_verified and not user.is_banned

if can_user_access_feature(user):
    ...
```
```

### Identifying Bugs

```markdown
**issue**: This will raise a `KeyError` if the key doesn't exist.

Suggested fix:
```python
# Instead of:
value = config['api_key']

# Use:
value = config.get('api_key')
if value is None:
    raise ValueError("Missing required config: api_key")
```
```

### Performance Concerns

```markdown
**issue**: This query runs inside a loop, causing N+1 queries.

Current approach makes `len(users)` database queries:
```python
for user in users:
    orders = db.query("SELECT * FROM orders WHERE user_id = ?", user.id)
```

Suggested batch query:
```python
user_ids = [u.id for u in users]
all_orders = db.query("SELECT * FROM orders WHERE user_id IN (?)", user_ids)
orders_by_user = group_by(all_orders, 'user_id')
```
```

### Test Coverage

```markdown
**suggestion**: Add test for the error case.

Suggested test:
```python
def test_process_data_raises_error_on_empty_input():
    with pytest.raises(ValueError, match="Input cannot be empty"):
        process_data([])
```
```

---

## Responding to Review Feedback

### As the Author (Receiving Feedback)

**1. Read all comments before responding**
- Get full picture before reacting
- Understand reviewer's perspective
- Identify patterns in feedback

**2. Ask clarifying questions**

```markdown
# Good clarifying question
> "This should handle empty lists as well"

Thanks for catching this! Should it return an empty result or raise an error?
I'm leaning toward raising an error since empty input is likely a bug.
```

**3. Acknowledge and implement**

```markdown
# ✅ Agree and done
> "Use a set for O(1) lookup"

Done! Changed to use a set. Performance improved 10x in my local tests.
```

**4. Explain alternative approaches**

```markdown
# 💭 Alternative proposal
> "This could use a dictionary"

I considered that, but went with a dataclass instead because:
- Provides type hints
- Better IDE support
- Validates types at runtime

Thoughts?
```

**5. Defer to separate PR when appropriate**

```markdown
# ✅ Agree but separate PR
> "We should also add retry logic"

Great idea! I'd prefer to address that in a separate PR since:
- This PR is already large
- Retry logic needs its own tests
- Unrelated to the current bug fix

Created #127 to track it.
```

### As the Reviewer (Getting Responses)

**1. Be patient and collaborative**
- Remember: You're on the same team
- Goal is better code, not winning arguments
- Be willing to learn from the author

**2. Approve when issues are addressed**

```markdown
# ✅ Approval comment
Thanks for addressing the feedback! The refactoring looks much cleaner.
Approving.
```

**3. Escalate blockers clearly**

```markdown
# ⛔ Clear blocker
I can't approve this yet due to the backwards compatibility break.

We need to either:
1. Add a migration path for existing users
2. Defer this change to v2.0.0

Happy to discuss the best approach.
```

---

## Review Checklists
