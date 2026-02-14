# Issue Automation Patterns

**Automate issue management for faster triage and better organization**

This guide covers automation patterns for GitHub issue management, including auto-triage, auto-assignment, auto-labeling, and stale issue detection.

---

## Auto-Triage

Automatically categorize and prioritize issues based on content, labels, or source.

### Pattern 1: Priority-Based Triage

```yaml
# .github/workflows/issue-triage.yml
name: Issue Auto-Triage
on:
  issues:
    types: [opened]

jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - name: Analyze issue content
        id: analyze
        uses: actions/github-script@v6
        with:
          script: |
            const issue = context.payload.issue;
            const title = issue.title.toLowerCase();
            const body = issue.body.toLowerCase();

            // Priority detection
            let priority = 'medium';
            if (title.includes('critical') || body.includes('production down')) {
              priority = 'high';
            } else if (title.includes('enhancement') || title.includes('feature')) {
              priority = 'low';
            }

            // Category detection
            let category = 'bug';
            if (title.includes('feature') || title.includes('enhancement')) {
              category = 'enhancement';
            } else if (title.includes('docs') || title.includes('documentation')) {
              category = 'documentation';
            }

            core.setOutput('priority', priority);
            core.setOutput('category', category);

      - name: Apply labels
        run: |
          gh issue edit ${{ github.event.issue.number }} \
            --add-label "priority:${{ steps.analyze.outputs.priority }}" \
            --add-label "${{ steps.analyze.outputs.category }}"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Pattern 2: Template-Based Triage

```yaml
# Triage based on issue template used
jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - name: Check template type
        id: template
        uses: actions/github-script@v6
        with:
          script: |
            const issue = context.payload.issue;
            const body = issue.body || '';

            let labels = [];

            if (body.includes('Bug Report')) {
              labels = ['bug', 'needs-triage', 'priority:medium'];
            } else if (body.includes('Feature Request')) {
              labels = ['enhancement', 'needs-review', 'priority:low'];
            } else if (body.includes('Security Vulnerability')) {
              labels = ['security', 'urgent', 'priority:high'];
            }

            for (const label of labels) {
              await github.rest.issues.addLabels({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                labels: [label]
              });
            }
```

### Pattern 3: Source-Based Triage

```yaml
# Triage based on issue source (bot, team member, external)
- name: Triage by source
  uses: actions/github-script@v6
  with:
    script: |
      const issue = context.payload.issue;
      const author = issue.user.login;

      // Check if author is team member
      const { data: membership } = await github.rest.teams.getMembershipForUserInOrg({
        org: 'your-org',
        team_slug: 'core-team',
        username: author
      }).catch(() => ({ data: null }));

      let labels = [];
      if (membership) {
        labels.push('internal');
      } else {
        labels.push('external', 'needs-review');
      }

      // Bot-created issues
      if (author.endsWith('[bot]')) {
        labels.push('automated');
      }

      await github.rest.issues.addLabels({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
        labels: labels
      });
```

---

## Auto-Assignment

Automatically assign issues to team members based on workload, expertise, or rotation.

### Pattern 1: Round-Robin Assignment

```yaml
# .github/workflows/issue-assignment.yml
name: Issue Auto-Assignment
on:
  issues:
    types: [opened, labeled]

jobs:
  assign:
    runs-on: ubuntu-latest
    steps:
      - name: Round-robin assignment
        uses: pozil/auto-assign-issue@v1
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          assignees: alice,bob,charlie,diana
          numOfAssignee: 1
```

### Pattern 2: Expertise-Based Assignment

```yaml
# Assign based on issue labels
jobs:
  assign-by-expertise:
    runs-on: ubuntu-latest
    steps:
      - name: Assign by label
        uses: actions/github-script@v6
        with:
          script: |
            const issue = context.payload.issue;
            const labels = issue.labels.map(l => l.name);

            let assignee = null;

            if (labels.includes('backend') || labels.includes('python')) {
              assignee = 'alice';  // Backend expert
            } else if (labels.includes('frontend') || labels.includes('javascript')) {
              assignee = 'bob';  // Frontend expert
            } else if (labels.includes('devops') || labels.includes('infrastructure')) {
              assignee = 'charlie';  // DevOps expert
            } else if (labels.includes('documentation')) {
              assignee = 'diana';  // Tech writer
            }

            if (assignee) {
              await github.rest.issues.addAssignees({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                assignees: [assignee]
              });
            }
```

### Pattern 3: Workload-Balanced Assignment

```yaml
# Assign to team member with fewest open issues
- name: Balanced assignment
  uses: actions/github-script@v6
  with:
    script: |
      const team = ['alice', 'bob', 'charlie'];
      const workloads = {};

      // Count open issues for each team member
      for (const member of team) {
        const { data: issues } = await github.rest.issues.listForRepo({
          owner: context.repo.owner,
          repo: context.repo.repo,
          assignee: member,
          state: 'open'
        });
        workloads[member] = issues.length;
      }

      // Find team member with least workload
      const assignee = Object.entries(workloads)
        .sort(([,a], [,b]) => a - b)[0][0];

      await github.rest.issues.addAssignees({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
        assignees: [assignee]
      });
```

---

## Auto-Labeling

Automatically label issues based on content, files, or patterns.

### Pattern 1: Content-Based Labeling

```yaml
# .github/workflows/issue-labeler.yml
name: Issue Auto-Labeling
on:
  issues:
    types: [opened]

jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - name: Label by keywords
        uses: github/issue-labeler@v3.0
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          configuration-path: .github/issue-labeler.yml
```

**Configuration** (`.github/issue-labeler.yml`):
```yaml
bug:
  - '/bug/i'
  - '/error/i'
  - '/crash/i'
  - '/broken/i'

enhancement:
  - '/feature/i'
  - '/enhancement/i'
  - '/improve/i'

documentation:
  - '/docs/i'
  - '/documentation/i'
  - '/readme/i'

performance:
  - '/slow/i'
  - '/performance/i'
  - '/optimization/i'

security:
  - '/security/i'
  - '/vulnerability/i'
  - '/cve/i'
```

### Pattern 2: Technology Stack Labeling

```yaml
# Label by technology mentioned
- name: Tech stack labeling
  uses: actions/github-script@v6
  with:
    script: |
      const issue = context.payload.issue;
      const text = `${issue.title} ${issue.body}`.toLowerCase();

      const techLabels = {
        'lang:python': ['python', 'pytest', 'django', 'flask'],
        'lang:javascript': ['javascript', 'node', 'react', 'vue'],
        'lang:go': ['golang', 'go'],
        'db:postgres': ['postgres', 'postgresql'],
        'db:redis': ['redis'],
        'cloud:aws': ['aws', 'amazon web services', 'ec2', 's3'],
        'cloud:gcp': ['gcp', 'google cloud'],
      };

      const labels = [];
      for (const [label, keywords] of Object.entries(techLabels)) {
        if (keywords.some(kw => text.includes(kw))) {
          labels.push(label);
        }
      }

      if (labels.length > 0) {
        await github.rest.issues.addLabels({
          owner: context.repo.owner,
          repo: context.repo.repo,
          issue_number: context.issue.number,
          labels: labels
        });
      }
```

---

## Stale Issue Detection

Automatically detect and close stale issues.

### Pattern 1: Stale Issue Bot

```yaml
# .github/workflows/stale-issues.yml
name: Stale Issue Detection
on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight

jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/stale@v8
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          stale-issue-message: >
            This issue has been automatically marked as stale because it has not had
            recent activity. It will be closed if no further activity occurs. Thank you
            for your contributions.
          close-issue-message: >
            This issue has been automatically closed due to inactivity. If you believe
            this is still relevant, please reopen or create a new issue.
          days-before-stale: 60
          days-before-close: 7
          exempt-issue-labels: 'pinned,security,roadmap'
          stale-issue-label: 'stale'
```

### Pattern 2: Conditional Stale Detection

```yaml
# Different stale timeouts by label
jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/stale@v8
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          days-before-stale: 30
          days-before-close: 7

          # Bugs: 30 days stale, 7 days to close
          stale-issue-label: 'stale'

          # Enhancements: 90 days stale, 14 days to close
          exempt-issue-labels: 'bug,security'
          exempt-all-issue-milestones: true

      - uses: actions/stale@v8
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          days-before-stale: 90
          days-before-close: 14
          only-issue-labels: 'enhancement'
```

### Pattern 3: Require Response from Reporter

```yaml
# Close if no response from reporter
- uses: actions/stale@v8
  with:
    repo-token: ${{ secrets.GITHUB_TOKEN }}
    stale-issue-message: >
      @${{ github.event.issue.user.login }} - We need more information to proceed.
      Please provide additional details within 7 days or this issue will be closed.
    days-before-stale: 14
    days-before-close: 7
    only-issue-labels: 'needs-info'
    remove-stale-when-updated: true
```

---

## Issue Labeling

Systematic labeling strategy for better organization.

### Label Categories

**Priority**:
```yaml
priority:high      # Critical, production down
priority:medium    # Important, not urgent
priority:low       # Nice to have
```

**Type**:
```yaml
bug                # Something is broken
enhancement        # New feature or improvement
documentation      # Documentation only
technical-debt     # Code quality improvement
```

**Status**:
```yaml
needs-triage       # Needs initial review
needs-info         # Waiting for more information
in-progress        # Actively being worked on
blocked            # Cannot proceed
```

**Technology**:
```yaml
lang:python
lang:javascript
db:postgres
cloud:aws
```

### Auto-Label Workflow

```yaml
# .github/workflows/comprehensive-labeling.yml
name: Comprehensive Issue Labeling
on:
  issues:
    types: [opened, edited]

jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - name: Apply comprehensive labels
        uses: actions/github-script@v6
        with:
          script: |
            const issue = context.payload.issue;
            const text = `${issue.title} ${issue.body}`.toLowerCase();

            const labels = new Set();

            // Priority
            if (text.includes('critical') || text.includes('production')) {
              labels.add('priority:high');
            } else if (text.includes('enhancement') || text.includes('nice to have')) {
              labels.add('priority:low');
            } else {
              labels.add('priority:medium');
            }

            // Type
            if (text.includes('bug') || text.includes('error')) {
              labels.add('bug');
            } else if (text.includes('feature') || text.includes('enhancement')) {
              labels.add('enhancement');
            } else if (text.includes('docs') || text.includes('documentation')) {
              labels.add('documentation');
            }

            // Status
            labels.add('needs-triage');

            await github.rest.issues.addLabels({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              labels: Array.from(labels)
            });
```

---

## Issue Linking

Automatically link related issues and PRs.

### Pattern 1: Link to Parent Issue

```yaml
# Detect "Part of #123" and link issues
- name: Link to parent
  uses: actions/github-script@v6
  with:
    script: |
      const issue = context.payload.issue;
      const body = issue.body || '';

      // Match "Part of #123" or "Related to #123"
      const matches = body.match(/#(\d+)/g);

      if (matches) {
        const comment = `This issue is linked to: ${matches.join(', ')}`;

        await github.rest.issues.createComment({
          owner: context.repo.owner,
          repo: context.repo.repo,
          issue_number: context.issue.number,
          body: comment
        });
      }
```

### Pattern 2: Auto-Link Duplicate Issues

```yaml
# Detect duplicate issues by similarity
- name: Detect duplicates
  uses: actions/github-script@v6
  with:
    script: |
      const issue = context.payload.issue;

      // Get all open issues
      const { data: openIssues } = await github.rest.issues.listForRepo({
        owner: context.repo.owner,
        repo: context.repo.repo,
        state: 'open'
      });

      // Simple similarity check (improve with ML in production)
      const similar = openIssues.filter(i =>
        i.number !== issue.number &&
        i.title.toLowerCase().includes(issue.title.toLowerCase().split(' ')[0])
      );

      if (similar.length > 0) {
        const links = similar.map(i => `#${i.number}`).join(', ');
        await github.rest.issues.createComment({
          owner: context.repo.owner,
          repo: context.repo.repo,
          issue_number: context.issue.number,
          body: `Potentially duplicate of: ${links}`
        });
      }
```

---

## Best Practices

### ✅ DO

1. **Use issue templates** - Ensure consistent information
2. **Auto-label on creation** - Faster triage
3. **Assign based on expertise** - Faster resolution
4. **Close stale issues** - Keep backlog clean
5. **Link related issues** - Maintain context

### ❌ DON'T

1. **Over-automate closure** - Some issues need time
2. **Skip triage** - Leads to issue backlog chaos
3. **Ignore reporter feedback** - Always ask for clarification
4. **Create too many labels** - Keep it simple
5. **Auto-close security issues** - Always requires manual review

---

## See Also

- [pr-automation.md](pr-automation.md) - PR automation patterns
- [github-actions-integration.md](github-actions-integration.md) - GitHub Actions workflows
- [api-security-patterns.md](api-security-patterns.md) - API security best practices
