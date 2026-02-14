# GitHub API Security Patterns

**Secure GitHub API integration and webhook handling**

This guide covers essential security patterns for GitHub API usage, including webhook signature verification, token security, rate limiting, and HTTPS requirements.

---

## Webhook Signature Verification

Always verify webhook signatures to prevent unauthorized requests.

### HMAC SHA-256 Verification

GitHub signs webhook payloads with HMAC SHA-256 using your webhook secret.

**Python implementation**:
```python
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature.

    Args:
        payload: Raw request body (bytes)
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret from GitHub settings

    Returns:
        True if signature is valid, False otherwise

    Security:
        - Uses constant-time comparison to prevent timing attacks
        - Validates signature format before comparison
        - Never logs secret or signature values
    """
    if not signature.startswith('sha256='):
        return False

    # Extract signature hash
    expected_signature = signature[7:]  # Remove 'sha256=' prefix

    # Compute HMAC
    mac = hmac.new(
        secret.encode('utf-8'),
        msg=payload,
        digestmod=hashlib.sha256
    )
    computed_signature = mac.hexdigest()

    # Constant-time comparison (prevents timing attacks)
    return hmac.compare_digest(computed_signature, expected_signature)
```

**Flask example**:
```python
from flask import Flask, request, abort

app = Flask(__name__)
WEBHOOK_SECRET = os.environ['GITHUB_WEBHOOK_SECRET']

@app.route('/webhook', methods=['POST'])
def webhook():
    # Get signature from header
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        abort(401, 'Missing signature header')

    # Verify signature
    payload = request.get_data()
    if not verify_webhook_signature(payload, signature, WEBHOOK_SECRET):
        abort(401, 'Invalid signature')

    # Process webhook
    event = request.headers.get('X-GitHub-Event')
    data = request.get_json()

    # Handle event
    if event == 'push':
        handle_push(data)
    elif event == 'pull_request':
        handle_pull_request(data)

    return {'status': 'success'}, 200
```

### Express.js Example

```javascript
const express = require('express');
const crypto = require('crypto');

const app = express();
const WEBHOOK_SECRET = process.env.GITHUB_WEBHOOK_SECRET;

// Use raw body parser for signature verification
app.use(express.json({
  verify: (req, res, buf) => {
    req.rawBody = buf.toString('utf8');
  }
}));

function verifySignature(payload, signature, secret) {
  if (!signature || !signature.startsWith('sha256=')) {
    return false;
  }

  const expectedSignature = signature.slice(7);
  const computedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');

  return crypto.timingSafeEqual(
    Buffer.from(computedSignature),
    Buffer.from(expectedSignature)
  );
}

app.post('/webhook', (req, res) => {
  const signature = req.headers['x-hub-signature-256'];

  if (!verifySignature(req.rawBody, signature, WEBHOOK_SECRET)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  const event = req.headers['x-github-event'];

  // Handle webhook
  console.log(`Received ${event} event`);

  res.json({ status: 'success' });
});
```

---

## Token Security

Protect GitHub API tokens and credentials.

### Token Storage

**Environment variables** (recommended):
```bash
# .env file (gitignored!)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY_PATH=/path/to/private-key.pem
```

**Never commit**:
```python
# ❌ WRONG - Hardcoded token
token = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# ✅ CORRECT - Environment variable
import os
token = os.environ['GITHUB_TOKEN']
```

### Token Scopes

Use minimum required scopes:

```bash
# Read-only access (recommended for CI/CD)
gh auth login --scopes repo:status,public_repo

# Full repository access (required for PRs, issues)
gh auth login --scopes repo

# Admin access (only when necessary)
gh auth login --scopes repo,admin:org
```

**Scope reference**:
- `repo`: Full control of private repositories
- `repo:status`: Access commit status
- `public_repo`: Access public repositories
- `admin:org`: Full organization access
- `write:discussion`: Discussions access
- `workflow`: GitHub Actions workflows

### Token Rotation

Rotate tokens regularly:

```python
from datetime import datetime, timedelta

class TokenManager:
    def __init__(self):
        self.token = os.environ['GITHUB_TOKEN']
        self.created_at = datetime.now()
        self.max_age_days = 90

    def is_expired(self) -> bool:
        """Check if token should be rotated."""
        age = datetime.now() - self.created_at
        return age > timedelta(days=self.max_age_days)

    def rotate_if_needed(self):
        """Rotate token if expired."""
        if self.is_expired():
            # Log rotation needed (don't log token!)
            logger.warning(
                f"GitHub token is {(datetime.now() - self.created_at).days} days old. "
                "Rotation recommended."
            )
            # In production: automate token rotation via GitHub Apps
```

### GitHub Apps vs Personal Access Tokens

**GitHub Apps** (recommended for automation):
```python
import jwt
import time
import requests

def generate_jwt(app_id: int, private_key: str) -> str:
    """Generate GitHub App JWT for authentication."""
    now = int(time.time())
    payload = {
        'iat': now,
        'exp': now + (10 * 60),  # 10 minutes
        'iss': app_id
    }
    return jwt.encode(payload, private_key, algorithm='RS256')

def get_installation_token(app_id: int, private_key: str, installation_id: int) -> str:
    """Get installation access token."""
    jwt_token = generate_jwt(app_id, private_key)

    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github+json'
    }

    response = requests.post(
        f'https://api.github.com/app/installations/{installation_id}/access_tokens',
        headers=headers
    )

    return response.json()['token']
```

**Benefits of GitHub Apps**:
- Fine-grained permissions
- Automatic token rotation (1-hour expiry)
- Better audit trail
- Can act on behalf of app (not user)

---

## Rate Limiting

Respect GitHub API rate limits.

### Check Rate Limit Status

```python
import requests

def check_rate_limit(token: str) -> dict:
    """Check current rate limit status."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json'
    }

    response = requests.get(
        'https://api.github.com/rate_limit',
        headers=headers
    )

    data = response.json()

    return {
        'limit': data['rate']['limit'],
        'remaining': data['rate']['remaining'],
        'reset': data['rate']['reset']  # Unix timestamp
    }
```

### Rate Limit Handling

```python
import time
from datetime import datetime

class GitHubAPIClient:
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json'
        })

    def make_request(self, url: str, method: str = 'GET', **kwargs):
        """Make API request with rate limit handling."""
        response = self.session.request(method, url, **kwargs)

        # Check rate limit
        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

        if remaining < 10:
            # Low on requests - wait for reset
            wait_seconds = reset_time - int(time.time())
            if wait_seconds > 0:
                print(f"Rate limit low ({remaining} remaining). Waiting {wait_seconds}s...")
                time.sleep(wait_seconds)

        if response.status_code == 403 and 'rate limit' in response.text.lower():
            # Hit rate limit - wait for reset
            wait_seconds = reset_time - int(time.time()) + 5
            print(f"Rate limit exceeded. Waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
            return self.make_request(url, method, **kwargs)  # Retry

        response.raise_for_status()
        return response.json()
```

### Rate Limit Best Practices

**Conditional requests**:
```python
# Use ETag for caching
etag = None

def get_user(username: str):
    global etag

    headers = {}
    if etag:
        headers['If-None-Match'] = etag

    response = requests.get(
        f'https://api.github.com/users/{username}',
        headers=headers
    )

    if response.status_code == 304:
        # Not modified - use cached data
        return cached_user

    # Update cache
    etag = response.headers.get('ETag')
    cached_user = response.json()
    return cached_user
```

**Pagination**:
```python
def get_all_issues(repo: str):
    """Fetch all issues with pagination."""
    issues = []
    url = f'https://api.github.com/repos/{repo}/issues'
    params = {'per_page': 100}  # Max per page

    while url:
        response = requests.get(url, params=params)
        issues.extend(response.json())

        # Get next page URL from Link header
        url = response.links.get('next', {}).get('url')

    return issues
```

---

## HTTPS Requirements

Always use HTTPS for secure communication.

### Webhook Configuration

**GitHub webhook settings**:
```
Payload URL: https://example.com/webhook  ✅ Secure
Payload URL: http://example.com/webhook   ❌ Insecure
```

**Server configuration** (nginx):
```nginx
server {
    listen 80;
    server_name example.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location /webhook {
        proxy_pass http://localhost:5000;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### TLS/SSL Certificate Verification

**Python**:
```python
# ✅ Verify SSL certificates (default)
response = requests.get('https://api.github.com/users/octocat')

# ❌ Disable verification (NEVER in production!)
response = requests.get('https://api.github.com/users/octocat', verify=False)
```

**Node.js**:
```javascript
const https = require('https');

// ✅ Verify SSL certificates (default)
https.get('https://api.github.com/users/octocat', (res) => {
  // Handle response
});

// ❌ Disable verification (NEVER in production!)
const agent = new https.Agent({ rejectUnauthorized: false });
https.get('https://api.github.com/users/octocat', { agent }, (res) => {
  // Handle response
});
```

---

## Additional Security Patterns

### IP Allowlisting

Restrict webhook sources to GitHub's IP ranges:

```python
import ipaddress

GITHUB_META_URL = 'https://api.github.com/meta'

def get_github_ip_ranges():
    """Fetch GitHub webhook IP ranges."""
    response = requests.get(GITHUB_META_URL)
    data = response.json()
    return data['hooks']  # List of CIDR ranges

def is_github_ip(ip: str) -> bool:
    """Check if IP is from GitHub."""
    github_ranges = get_github_ip_ranges()

    ip_addr = ipaddress.ip_address(ip)
    for cidr in github_ranges:
        if ip_addr in ipaddress.ip_network(cidr):
            return True

    return False

# In webhook handler
@app.route('/webhook', methods=['POST'])
def webhook():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not is_github_ip(client_ip):
        abort(403, 'Request not from GitHub')

    # Process webhook
```

### Webhook Replay Protection

Prevent replay attacks:

```python
from datetime import datetime, timedelta

processed_webhooks = set()  # In production: use Redis

def is_duplicate_delivery(delivery_id: str) -> bool:
    """Check if webhook was already processed."""
    if delivery_id in processed_webhooks:
        return True

    processed_webhooks.add(delivery_id)
    return False

@app.route('/webhook', methods=['POST'])
def webhook():
    delivery_id = request.headers.get('X-GitHub-Delivery')

    if is_duplicate_delivery(delivery_id):
        return {'status': 'duplicate'}, 200

    # Process webhook
```

---

## Best Practices

### ✅ DO

1. **Always verify webhook signatures** - Prevent unauthorized requests
2. **Use environment variables for tokens** - Never commit secrets
3. **Implement rate limit handling** - Avoid API throttling
4. **Use HTTPS exclusively** - Encrypt all communication
5. **Rotate tokens regularly** - Minimize exposure risk

### ❌ DON'T

1. **Skip signature verification** - Allows webhook forgery
2. **Hardcode tokens** - Security vulnerability
3. **Ignore rate limits** - API abuse and throttling
4. **Use HTTP for webhooks** - Exposes payload data
5. **Disable SSL verification** - Man-in-the-middle attacks

---

## See Also

- [pr-automation.md](pr-automation.md) - PR automation patterns
- [issue-automation.md](issue-automation.md) - Issue automation patterns
- [github-actions-integration.md](github-actions-integration.md) - GitHub Actions workflows
- [GitHub Webhook Documentation](https://docs.github.com/en/webhooks)
- [GitHub API Documentation](https://docs.github.com/en/rest)
