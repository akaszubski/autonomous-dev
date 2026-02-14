# Authentication Patterns

Secure handling of API credentials and tokens.

## Principles

- Use environment variables for credentials
- Never hardcode API keys
- Never log credentials
- Validate credentials before use

## Example

```python
import os

def get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN not found\n"
            "Set with: export GITHUB_TOKEN=your_token"
        )
    return token

# Use in API calls
token = get_github_token()
headers = {"Authorization": f"Bearer {token}"}
```

## Security

- ✅ Environment variables
- ❌ Hardcoded strings
- ❌ Logging credentials
- ✅ Validation before use

See: `templates/github-api-template.py`
