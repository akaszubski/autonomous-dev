# Structured Logging

## Structured Logging

### Why Structured Logging?

**Traditional (unstructured)**:
```python
print(f"User {user_id} logged in from {ip_address}")
# Hard to parse, search, filter
```

**Structured (JSON)**:
```python
logger.info("user_login", extra={
    "user_id": user_id,
    "ip_address": ip_address,
    "timestamp": datetime.utcnow().isoformat()
})
# Easy to parse, search, filter, aggregate
```

**Benefits**:
- ✅ Easy to search/filter
- ✅ Machine-readable
- ✅ Aggregate metrics
- ✅ Correlate events
- ✅ Feed to log aggregators (ELK, Splunk, Datadog)

---

### Python Logging Setup

**Basic configuration**:

```python
import logging
import sys

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Console
        logging.FileHandler('app.log')      # File
    ]
)

logger = logging.getLogger(__name__)

# Use it
logger.info("Application started")
logger.warning("Database connection slow")
logger.error("Failed to process request", exc_info=True)
```

---

### Log Levels

| Level | Value | Use When | Example |
|-------|-------|----------|---------|
| **DEBUG** | 10 | Development, detailed tracing | Variable values, function calls |
| **INFO** | 20 | Normal operations | User logged in, request processed |
| **WARNING** | 30 | Unexpected but handled | Deprecated API used, slow query |
| **ERROR** | 40 | Error occurred | Failed to save file, API error |
| **CRITICAL** | 50 | System failure | Database down, disk full |

**Usage**:
```python
logger.debug(f"Processing item: {item}")           # Development only
logger.info(f"User {user_id} logged in")           # Normal event
logger.warning(f"Query took {duration}s (slow!)")  # Unexpected
logger.error(f"Failed to save: {error}")           # Error
logger.critical(f"Database unreachable!")          # System failure
```

---

### Structured JSON Logging

**Using python-json-logger**:

```python
from pythonjsonlogger import jsonlogger
import logging

# Setup JSON formatter
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(name)s %(levelname)s %(message)s'
)
logHandler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Log with extra fields
logger.info("user_login", extra={
    "user_id": 123,
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
})
```

**Output**:
```json
{
  "asctime": "2025-10-24 12:00:00,000",
  "name": "root",
  "levelname": "INFO",
  "message": "user_login",
  "user_id": 123,
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0..."
}
```

---

### Context Logging

**Add context to all logs in a function**:

```python
import logging
from contextvars import ContextVar

# Context variable
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)

class ContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True

# Add filter
logger.addFilter(ContextFilter())

# Use in request handler
def handle_request(request):
    request_id = generate_request_id()
    request_id_var.set(request_id)

    logger.info("Processing request")  # Includes request_id automatically
    process_data()
    logger.info("Request complete")    # Includes request_id automatically
```

---

### Best Practices for Logging

**✅ DO**:

```python
# 1. Use appropriate log levels
logger.debug("Variable value: {value}")      # Debug details
logger.info("User action completed")         # Normal operations
logger.error("Failed to process", exc_info=True)  # Errors

# 2. Include context
logger.info("Processing payment", extra={
    "user_id": user_id,
    "amount": amount,
    "currency": currency
})

# 3. Log exceptions with stack traces
try:
    process_data()
except Exception as e:
    logger.error("Processing failed", exc_info=True)  # Includes stack trace

# 4. Use lazy formatting
logger.debug("Processing %s items", len(items))  # Only formats if DEBUG enabled
```

**❌ DON'T**:

```python
# 1. Don't log sensitive data
logger.info(f"User password: {password}")  # NEVER!
logger.info(f"Credit card: {card_number}")  # NEVER!

# 2. Don't log in loops (too verbose)
for item in items:
    logger.info(f"Processing {item}")  # 1M items = 1M log lines!

# 3. Don't use print() in production
print("Debug info")  # Use logger.debug() instead

# 4. Don't catch and ignore
try:
    process()
except:
    pass  # Silent failure! At least log it!
```

---
