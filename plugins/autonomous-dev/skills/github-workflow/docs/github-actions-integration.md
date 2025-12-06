# GitHub Actions Integration

**Complete guide to GitHub Actions workflow automation**

This guide covers GitHub Actions fundamentals, workflow syntax, event triggers, actions marketplace, and custom action development.

---

## Workflow Syntax

GitHub Actions workflows are defined in YAML files under `.github/workflows/`.

### Basic Workflow Structure

```yaml
name: CI Pipeline
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run build
        run: make build
```

**Components**:
- `name`: Workflow name (displayed in GitHub UI)
- `on`: Event triggers
- `jobs`: One or more jobs to execute
- `runs-on`: Runner environment (ubuntu-latest, windows-latest, macos-latest)
- `steps`: Sequential steps within a job
- `uses`: Use a pre-built action
- `run`: Execute shell commands

### Multi-Job Workflow

```yaml
name: Full CI/CD Pipeline
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest

  build:
    needs: test  # Wait for test job to complete
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build application
        run: make build
      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: build-artifact
          path: dist/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'  # Only on main branch
    steps:
      - uses: actions/download-artifact@v3
        with:
          name: build-artifact
      - name: Deploy
        run: ./deploy.sh
        env:
          DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
```

**Key concepts**:
- `needs`: Job dependencies (sequential execution)
- `if`: Conditional execution
- `env`: Environment variables
- `secrets`: Encrypted secrets from repository settings

### Matrix Builds

Test across multiple environments:

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: [3.8, 3.9, '3.10', 3.11]

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Run tests
        run: pytest
```

**Result**: Tests run on 12 combinations (3 OS × 4 Python versions)

---

## Event Triggers

Control when workflows execute.

### Common Events

```yaml
# Single event
on: push

# Multiple events
on: [push, pull_request]

# Event with filters
on:
  push:
    branches:
      - main
      - 'release/**'
    paths:
      - 'src/**'
      - '!docs/**'

# Scheduled execution
on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight UTC
```

### Event Activity Types

```yaml
on:
  pull_request:
    types:
      - opened
      - synchronize
      - reopened
      - ready_for_review

  issues:
    types:
      - opened
      - labeled

  release:
    types:
      - published
```

### Manual Triggers

```yaml
on:
  workflow_dispatch:  # Manual trigger from GitHub UI
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        type: choice
        options:
          - development
          - staging
          - production
      version:
        description: 'Version to deploy'
        required: false
        default: 'latest'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to ${{ github.event.inputs.environment }}
        run: |
          echo "Deploying version ${{ github.event.inputs.version }}"
          echo "Environment: ${{ github.event.inputs.environment }}"
```

### Workflow Triggers

Trigger workflows from other workflows:

```yaml
on:
  workflow_run:
    workflows: ["CI Pipeline"]
    types:
      - completed
    branches:
      - main

jobs:
  after-ci:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    steps:
      - name: Run after CI
        run: echo "CI completed successfully"
```

---

## Actions Marketplace

Reuse community-built actions from https://github.com/marketplace?type=actions

### Essential Actions

**Checkout code**:
```yaml
- uses: actions/checkout@v3
  with:
    fetch-depth: 0  # Full git history
```

**Setup languages**:
```yaml
# Python
- uses: actions/setup-python@v4
  with:
    python-version: '3.11'
    cache: 'pip'

# Node.js
- uses: actions/setup-node@v3
  with:
    node-version: '18'
    cache: 'npm'

# Go
- uses: actions/setup-go@v4
  with:
    go-version: '1.21'
```

**Caching**:
```yaml
# Cache dependencies
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

**Artifacts**:
```yaml
# Upload
- uses: actions/upload-artifact@v3
  with:
    name: test-results
    path: test-results/

# Download (in different job)
- uses: actions/download-artifact@v3
  with:
    name: test-results
```

### Popular Community Actions

**Code quality**:
```yaml
# Linting
- uses: github/super-linter@v5
  env:
    VALIDATE_ALL_CODEBASE: false
    DEFAULT_BRANCH: main

# Security scanning
- uses: aquasecurity/trivy-action@master
  with:
    scan-type: 'fs'
    scan-ref: '.'
```

**Testing**:
```yaml
# Coverage reporting
- uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
    fail_ci_if_error: true
```

**Deployment**:
```yaml
# AWS
- uses: aws-actions/configure-aws-credentials@v2
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: us-east-1

# Docker
- uses: docker/build-push-action@v4
  with:
    push: true
    tags: user/app:latest
```

---

## Custom Actions

Create reusable actions for your workflows.

### Composite Action

**File**: `.github/actions/setup-project/action.yml`
```yaml
name: 'Setup Project'
description: 'Install dependencies and setup environment'
inputs:
  python-version:
    description: 'Python version'
    required: false
    default: '3.11'

runs:
  using: 'composite'
  steps:
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ inputs.python-version }}
        cache: 'pip'

    - name: Install dependencies
      shell: bash
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Setup pre-commit
      shell: bash
      run: pre-commit install
```

**Usage**:
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: ./.github/actions/setup-project
        with:
          python-version: '3.11'
```

### JavaScript Action

**File**: `.github/actions/notify-slack/action.yml`
```yaml
name: 'Notify Slack'
description: 'Send notification to Slack'
inputs:
  webhook-url:
    description: 'Slack webhook URL'
    required: true
  message:
    description: 'Message to send'
    required: true

runs:
  using: 'node16'
  main: 'index.js'
```

**File**: `.github/actions/notify-slack/index.js`
```javascript
const core = require('@actions/core');
const https = require('https');

async function run() {
  try {
    const webhookUrl = core.getInput('webhook-url');
    const message = core.getInput('message');

    const data = JSON.stringify({ text: message });

    const url = new URL(webhookUrl);
    const options = {
      hostname: url.hostname,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': data.length
      }
    };

    const req = https.request(options, (res) => {
      console.log(`Status: ${res.statusCode}`);
    });

    req.on('error', (error) => {
      core.setFailed(error.message);
    });

    req.write(data);
    req.end();

    core.setOutput('success', 'true');
  } catch (error) {
    core.setFailed(error.message);
  }
}

run();
```

**Usage**:
```yaml
- uses: ./.github/actions/notify-slack
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    message: 'Deployment completed successfully!'
```

### Docker Action

**File**: `.github/actions/security-scan/action.yml`
```yaml
name: 'Security Scan'
description: 'Run security vulnerability scan'
inputs:
  path:
    description: 'Path to scan'
    required: true
    default: '.'

runs:
  using: 'docker'
  image: 'Dockerfile'
  args:
    - ${{ inputs.path }}
```

**File**: `.github/actions/security-scan/Dockerfile`
```dockerfile
FROM python:3.11-slim

RUN pip install bandit safety

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

**File**: `.github/actions/security-scan/entrypoint.sh`
```bash
#!/bin/bash
set -e

path=$1

echo "Running security scan on $path"

# Run bandit
bandit -r "$path" -f json -o bandit-report.json

# Run safety check
safety check --json > safety-report.json

echo "Security scan complete"
```

---

## Advanced Patterns

### Reusable Workflows

**File**: `.github/workflows/reusable-test.yml`
```yaml
name: Reusable Test Workflow
on:
  workflow_call:
    inputs:
      python-version:
        required: false
        type: string
        default: '3.11'
    secrets:
      api-key:
        required: false

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ inputs.python-version }}
      - run: pytest
```

**Usage**:
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    uses: ./.github/workflows/reusable-test.yml
    with:
      python-version: '3.11'
    secrets:
      api-key: ${{ secrets.API_KEY }}
```

### Conditional Steps

```yaml
steps:
  - name: Run only on main
    if: github.ref == 'refs/heads/main'
    run: echo "Main branch"

  - name: Run only on PRs
    if: github.event_name == 'pull_request'
    run: echo "Pull request"

  - name: Run only on success
    if: success()
    run: echo "Previous steps succeeded"

  - name: Run only on failure
    if: failure()
    run: echo "Previous steps failed"

  - name: Always run
    if: always()
    run: echo "Runs regardless of previous step status"
```

---

## Best Practices

### ✅ DO

1. **Use specific action versions** - `uses: actions/checkout@v3` (not `@main`)
2. **Cache dependencies** - Faster builds
3. **Use matrix builds** - Test multiple environments
4. **Set timeout limits** - Prevent runaway workflows
5. **Use secrets** - Never hardcode credentials

### ❌ DON'T

1. **Hardcode secrets** - Always use `${{ secrets.NAME }}`
2. **Run on every commit** - Use path filters
3. **Create monolithic workflows** - Split into reusable components
4. **Ignore failure modes** - Handle errors explicitly
5. **Skip version pinning** - Actions can break with updates

---

## See Also

- [pr-automation.md](pr-automation.md) - PR automation patterns
- [issue-automation.md](issue-automation.md) - Issue automation patterns
- [api-security-patterns.md](api-security-patterns.md) - API security best practices
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
