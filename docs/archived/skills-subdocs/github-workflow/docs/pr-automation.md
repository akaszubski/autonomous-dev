# Pull Request Automation Patterns

**Automate PR workflows for consistent quality and faster delivery**

This guide covers automation patterns for pull request management, including auto-labeling, reviewer assignment, status checks, and auto-merge workflows.

---

## Auto-Labeling

Automatically label PRs based on changed files, PR size, or content.

### Pattern 1: Label by Changed Files

```yaml
# .github/workflows/pr-labeler.yml
name: PR Auto-Labeling
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/labeler@v4
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
```

**Configuration** (`.github/labeler.yml`):
```yaml
documentation:
  - docs/**/*
  - '**/*.md'

backend:
  - 'src/**/*.py'
  - 'lib/**/*.py'

frontend:
  - 'static/**/*.js'
  - 'templates/**/*.html'

tests:
  - 'tests/**/*'
```

### Pattern 2: Label by PR Size

```yaml
# .github/workflows/pr-size.yml
name: PR Size Labeling
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  size:
    runs-on: ubuntu-latest
    steps:
      - uses: codelytv/pr-size-labeler@v1
        with:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          xs_label: 'size/xs'
          xs_max_size: 10
          s_label: 'size/s'
          s_max_size: 50
          m_label: 'size/m'
          m_max_size: 200
          l_label: 'size/l'
          l_max_size: 500
          xl_label: 'size/xl'
```

**Why it matters**: Large PRs are harder to review. Size labels help prioritize and encourage smaller, focused changes.

---

## Auto-Reviewers

Automatically assign reviewers based on code ownership, expertise, or round-robin distribution.

### Pattern 1: CODEOWNERS-Based Assignment

**Setup** (`.github/CODEOWNERS`):
```
# Global owners
* @team-lead

# Backend code
/src/**/*.py @backend-team
/lib/**/*.py @backend-team

# Frontend code
/static/**/*.js @frontend-team
/templates/**/*.html @frontend-team

# DevOps
/.github/workflows/* @devops-team
/docker/* @devops-team

# Documentation
/docs/* @tech-writers
*.md @tech-writers
```

**Enable auto-assignment**:
```yaml
# .github/workflows/auto-reviewers.yml
name: Auto-Assign Reviewers
on:
  pull_request:
    types: [opened, ready_for_review]

jobs:
  assign:
    runs-on: ubuntu-latest
    steps:
      - uses: kentaro-m/auto-assign-action@v1.2.1
        with:
          configuration-path: '.github/auto-assign.yml'
```

**Configuration** (`.github/auto-assign.yml`):
```yaml
# Auto-assign reviewers from CODEOWNERS
addReviewers: true
addAssignees: false

reviewers:
  - backend-team
  - frontend-team

numberOfReviewers: 2
```

### Pattern 2: Round-Robin Assignment

```yaml
# .github/auto-assign.yml
reviewers:
  - alice
  - bob
  - charlie

numberOfReviewers: 2
useReviewGroups: false
useAssigneeGroups: false

# Skip draft PRs
skipDraftPR: true
```

**Result**: Each PR gets 2 reviewers assigned in rotating order, skipping drafts.

### Pattern 3: Expertise-Based Assignment

```yaml
# Assign based on file patterns
reviewGroups:
  python:
    - alice
    - bob
  javascript:
    - charlie
    - diana
  devops:
    - eve

# Rules
fileRules:
  - pattern: '\.py$'
    reviewGroup: python
  - pattern: '\.js$'
    reviewGroup: javascript
  - pattern: '\.yml$|Dockerfile'
    reviewGroup: devops
```

---

## Auto-Merge

Automatically merge PRs when all checks pass and approvals are received.

### Pattern 1: Auto-Merge with Approvals

```yaml
# .github/workflows/auto-merge.yml
name: Auto-Merge
on:
  pull_request_review:
    types: [submitted]
  check_suite:
    types: [completed]

jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.event.pull_request.draft == false
    steps:
      - uses: pascalgn/automerge-action@v0.15.6
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          MERGE_LABELS: "automerge,!hold"
          MERGE_METHOD: "squash"
          MERGE_COMMIT_MESSAGE: "pull-request-title-and-description"
          MERGE_FORKS: "false"
          MERGE_RETRIES: "6"
          MERGE_RETRY_SLEEP: "10000"
          UPDATE_LABELS: ""
```

**Enable auto-merge on PR**:
```bash
# Add label to PR
gh pr edit 123 --add-label automerge

# PR will auto-merge when:
# ✅ All status checks pass
# ✅ Minimum approvals received
# ✅ No "hold" label present
# ✅ Not in draft mode
```

### Pattern 2: Dependabot Auto-Merge

```yaml
# .github/workflows/dependabot-auto-merge.yml
name: Dependabot Auto-Merge
on: pull_request

jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.actor == 'dependabot[bot]'
    steps:
      - uses: actions/checkout@v3

      - name: Check if tests pass
        run: |
          # Wait for status checks
          sleep 30
          gh pr checks ${{ github.event.pull_request.number }} --watch
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Enable auto-merge
        run: gh pr merge --auto --squash ${{ github.event.pull_request.number }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Why it matters**: Security updates merge automatically after passing tests, keeping dependencies current without manual intervention.

---

## Status Checks

Enforce quality gates before PR merge.

### Pattern 1: Required Status Checks

**GitHub Settings** → **Branches** → **Branch protection rules**:
```
Branch name pattern: main

✅ Require status checks to pass before merging
  ✅ Require branches to be up to date before merging

  Required checks:
  - build
  - test
  - lint
  - security-scan
  - coverage-check
```

### Pattern 2: Custom Status Check Workflow

```yaml
# .github/workflows/status-checks.yml
name: PR Status Checks
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  build:
    name: Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: make build

  test:
    name: Test Suite
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: make test

  lint:
    name: Code Quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: make lint

  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: make security-scan

  coverage:
    name: Coverage Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: make coverage
      - run: |
          coverage_pct=$(coverage report | tail -1 | awk '{print $4}' | sed 's/%//')
          if [ "$coverage_pct" -lt 80 ]; then
            echo "Coverage $coverage_pct% is below 80% threshold"
            exit 1
          fi
```

### Pattern 3: Conditional Checks

```yaml
# Only run expensive checks on certain files
jobs:
  frontend-tests:
    if: contains(github.event.pull_request.changed_files, 'static/')
    runs-on: ubuntu-latest
    steps:
      - run: npm test

  backend-tests:
    if: contains(github.event.pull_request.changed_files, 'src/')
    runs-on: ubuntu-latest
    steps:
      - run: pytest
```

---

## Milestone Tracking

Automatically track PR progress toward milestones.

### Pattern 1: Auto-Add to Milestone

```yaml
# .github/workflows/milestone-tracking.yml
name: Milestone Tracking
on:
  pull_request:
    types: [opened]

jobs:
  assign-milestone:
    runs-on: ubuntu-latest
    steps:
      - name: Extract milestone from branch
        id: milestone
        run: |
          # Branch pattern: sprint-6/feature-name
          branch="${{ github.head_ref }}"
          milestone=$(echo $branch | cut -d/ -f1 | sed 's/sprint-/Sprint /')
          echo "milestone=$milestone" >> $GITHUB_OUTPUT

      - name: Assign to milestone
        run: |
          gh pr edit ${{ github.event.pull_request.number }} \
            --milestone "${{ steps.milestone.outputs.milestone }}"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Branch naming**: `sprint-6/add-user-auth` → Auto-assigned to "Sprint 6" milestone

---

## Draft PR Workflows

Automate draft PR lifecycle.

### Pattern 1: Auto-Draft for WIP

```yaml
# .github/workflows/draft-detection.yml
name: Draft Detection
on:
  pull_request:
    types: [opened]

jobs:
  auto-draft:
    runs-on: ubuntu-latest
    steps:
      - name: Mark as draft if WIP
        if: contains(github.event.pull_request.title, 'WIP') || contains(github.event.pull_request.title, '[WIP]')
        run: gh pr ready --undo ${{ github.event.pull_request.number }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Pattern 2: Auto-Ready When Checks Pass

```yaml
# .github/workflows/auto-ready.yml
name: Auto-Ready for Review
on:
  check_suite:
    types: [completed]

jobs:
  auto-ready:
    runs-on: ubuntu-latest
    if: github.event.check_suite.conclusion == 'success'
    steps:
      - name: Get PR
        id: pr
        run: |
          pr=$(gh pr view ${{ github.event.check_suite.pull_requests[0].number }} --json isDraft,number -q '.number')
          echo "pr_number=$pr" >> $GITHUB_OUTPUT
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Mark ready if draft
        run: gh pr ready ${{ steps.pr.outputs.pr_number }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## PR Comment Automation

Automatically post comments with useful information.

### Pattern 1: Coverage Report Comment

```yaml
# .github/workflows/coverage-comment.yml
name: Coverage Comment
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run coverage
        run: |
          coverage run -m pytest
          coverage report > coverage.txt

      - name: Post coverage comment
        uses: py-cov-action/python-coverage-comment-action@v3
        with:
          GITHUB_TOKEN: ${{ github.token }}
```

### Pattern 2: Build Size Comment

```yaml
# Post build size changes
- name: Comment build size
  uses: andresz1/size-limit-action@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
```

### Pattern 3: Security Findings Comment

```yaml
# Post security scan results
- name: Run security scan
  run: bandit -r src/ -f json -o bandit-report.json
  continue-on-error: true

- name: Comment security findings
  uses: actions/github-script@v6
  with:
    script: |
      const fs = require('fs');
      const report = JSON.parse(fs.readFileSync('bandit-report.json'));
      const findings = report.results.length;

      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: `## Security Scan Results\n\n${findings} findings detected. See workflow for details.`
      });
```

---

## Best Practices

### ✅ DO

1. **Use draft PRs by default** - Prevents accidental merges
2. **Require status checks** - Enforce quality gates
3. **Auto-label for organization** - Easier filtering and prioritization
4. **Assign reviewers automatically** - Faster review cycle
5. **Track milestones** - Maintain sprint alignment

### ❌ DON'T

1. **Auto-merge without approvals** - Bypasses code review
2. **Skip status checks** - Quality degrades quickly
3. **Over-automate** - Some decisions need human judgment
4. **Ignore draft status** - Respect work-in-progress
5. **Forget security** - Always verify webhook signatures

---

## See Also

- [issue-automation.md](issue-automation.md) - Issue automation patterns
- [github-actions-integration.md](github-actions-integration.md) - GitHub Actions workflows
- [api-security-patterns.md](api-security-patterns.md) - API security best practices
