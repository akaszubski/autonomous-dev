# GitHub Issue Description Guide

Best practices for writing effective issue descriptions that facilitate understanding, prioritization, and implementation.

## Overview

A well-written issue description helps contributors understand:
- **What** the problem or feature request is
- **Why** it matters (impact and motivation)
- **How** it should be solved (proposed solution)
- **When** it should be addressed (priority and context)

## Standard Issue Structure

### Minimum Required Sections

Every issue should include:

```markdown
## Problem
Clear description of the problem or feature gap

## Solution
Proposed solution or desired outcome

## Acceptance Criteria
Specific, testable conditions that must be met

## Context
Additional background, related issues, or constraints
```

### Expanded Template (Recommended)

For more complex issues:

```markdown
## Problem
What problem does this solve? What is the current pain point?

## Solution
High-level description of proposed solution

## Motivation
Why is this important? What is the business/user impact?

## Acceptance Criteria
- [ ] Specific condition 1
- [ ] Specific condition 2
- [ ] Specific condition 3

## Technical Approach (Optional)
Suggested implementation approach or architecture

## Alternatives Considered (Optional)
Other solutions that were considered and why they were rejected

## Open Questions (Optional)
Unresolved questions that need discussion

## Related
Links to related issues, PRs, or documentation

## Context
Environment, user stories, or additional background
```

## Writing an Effective Problem Statement

### Purpose
The problem statement establishes **what** needs to be addressed and **why** it matters.

### Best Practices

✅ **Do's:**
- Start with user impact or pain point
- Be specific about current behavior
- Include concrete examples
- Quantify impact when possible

❌ **Don'ts:**
- Jump straight to solution
- Use vague terms like "bad UX" without specifics
- Assume everyone knows the background
- Omit why it matters

### Examples

**Bad Problem Statement:**
```markdown
## Problem
The app is slow.
```

**Good Problem Statement:**
```markdown
## Problem
Report generation takes 30+ seconds for datasets >10,000 rows, causing users
to abandon the operation. Analytics show 45% of report generation attempts
time out, leading to 20+ support tickets per week.

Current behavior:
- Load all data into memory before processing
- No progress indication for user
- No ability to cancel operation

Impact:
- Lost productivity (30s × 500 reports/day = 4.2 hours wasted daily)
- Support burden (20 tickets/week × 15 min = 5 hours/week)
- User frustration (45% abandon rate)
```

**Bad Problem Statement:**
```markdown
## Problem
Need better authentication.
```

**Good Problem Statement:**
```markdown
## Problem
Current session-based authentication doesn't support horizontal scaling,
limiting our ability to handle traffic spikes during peak hours (9am-11am PST).

Current limitations:
- Sticky sessions required in load balancer
- Can't add new servers dynamically
- Session state lost when server restarts
- Unable to support mobile app (requires stateless auth)

Recent impact:
- 2 outages during traffic spikes (>10,000 concurrent users)
- Mobile app launch blocked for Q4
- Infrastructure costs 30% higher than stateless architecture
```

## Defining Clear Solutions

### Purpose
The solution describes the **desired outcome** or proposed approach to solve the problem.

### Best Practices

✅ **Do's:**
- Describe desired outcome, not just implementation
- Be specific enough to guide implementation
- Leave room for implementer's expertise
- Consider edge cases

❌ **Don'ts:**
- Over-specify implementation details
- Propose multiple conflicting solutions
- Ignore non-functional requirements (performance, security)
- Forget about backwards compatibility

### Examples

**Bad Solution:**
```markdown
## Solution
Make it faster.
```

**Good Solution:**
```markdown
## Solution
Implement streaming report generation with progressive rendering:

1. Process data in chunks (1,000 rows at a time)
2. Stream results to client as they're generated
3. Show progress indicator (% complete)
4. Allow user to cancel operation

Expected outcome:
- First results visible within 2 seconds
- Complete report in <10 seconds (vs current 30+ seconds)
- No memory issues with large datasets
- Graceful cancellation without orphaned processes
```

**Bad Solution:**
```markdown
## Solution
Use JWT tokens.
```

**Good Solution:**
```markdown
## Solution
Migrate authentication from session-based to JWT token-based:

Components:
1. JWT token issuance on login (15-minute expiry)
2. Refresh token mechanism (7-day expiry)
3. Token validation middleware for API endpoints
4. Graceful migration path for existing sessions

Benefits:
- Stateless authentication enables horizontal scaling
- Works with mobile apps (no cookie requirement)
- Reduced server memory usage (no session storage)
- Supports multiple load balancer configurations

Non-functional requirements:
- No downtime during migration
- Backwards compatible during transition period (1 month)
- Secure token storage (HttpOnly, Secure flags)
```

## Writing Testable Acceptance Criteria

### Purpose
Acceptance criteria define the **specific, testable conditions** that must be met for the issue to be considered complete.

### Format

Use checkbox lists for clarity:

```markdown
## Acceptance Criteria

### Functional Requirements
- [ ] User can generate report for any dataset size
- [ ] Progress indicator shows % complete during generation
- [ ] User can cancel report generation at any time
- [ ] First results appear within 2 seconds
- [ ] Complete report available in <10 seconds (10K rows)

### Non-Functional Requirements
- [ ] Memory usage <500MB regardless of dataset size
- [ ] No memory leaks (tested with 100 consecutive reports)
- [ ] Works on Chrome, Firefox, Safari (latest versions)
- [ ] Responsive on mobile devices

### Edge Cases
- [ ] Handles empty datasets gracefully
- [ ] Handles datasets with 100K+ rows
- [ ] Handles special characters in data (unicode, emojis)
- [ ] Recovers from network interruption during generation
```

### Best Practices

✅ **Do's:**
- Make each criterion testable (yes/no)
- Be specific about numbers (not "fast", but "<2 seconds")
- Include edge cases and error scenarios
- Group criteria by category

❌ **Don'ts:**
- Use vague terms ("good UX", "performant")
- Omit error handling requirements
- Forget about non-functional requirements
- Make criteria too broad or too granular

## Providing Context

### Purpose
Context helps contributors understand the **broader picture**, constraints, and dependencies.

### What to Include

1. **Environment details** (if relevant)
```markdown
## Context

### Environment
- OS: macOS 14.0, Windows 11, Ubuntu 22.04
- Browser: Chrome 119, Firefox 120
- Python version: 3.11+
- Database: PostgreSQL 15
```

2. **User stories**
```markdown
## Context

### User Story
As a data analyst, I need to generate large reports quickly so that I can
meet daily deadlines without waiting for slow exports.

Currently:
- Generate 10-15 reports per day
- Each report takes 30+ seconds
- Total time wasted: 5-7.5 minutes/day
- Causes missed deadlines 2-3 times/week
```

3. **Business context**
```markdown
## Context

### Business Impact
- Q4 goal: Support 50,000 concurrent users
- Current bottleneck: Session-based auth limits to 10,000 users
- Mobile app launch depends on this (scheduled for Dec 1)
- Estimated cost savings: $5,000/month (reduced server capacity)
```

4. **Technical constraints**
```markdown
## Context

### Technical Constraints
- Must maintain backwards compatibility (30-day transition period)
- Cannot require database schema changes (compliance review required)
- Must work with existing load balancer configuration
- Security audit required before production deployment
```

## Issue Types and Templates

### Bug Report

```markdown
## Problem
Describe the bug and its impact

## Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Screenshots
If applicable, add screenshots

## Environment
- OS: [e.g., macOS 14.0]
- Browser: [e.g., Chrome 119]
- Version: [e.g., v2.3.0]

## Additional Context
Any other relevant information

## Acceptance Criteria
- [ ] Bug no longer occurs
- [ ] Regression test added
- [ ] Works across all supported environments
```

### Feature Request

```markdown
## Problem
What user need or pain point does this address?

## Solution
Proposed feature or enhancement

## User Story
As a [type of user], I want [goal] so that [benefit].

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Mockups / Examples
Visual examples or mockups of proposed feature

## Alternatives Considered
Other approaches and why this is preferred

## Impact
Expected user/business impact

## Priority
High / Medium / Low - with justification
```

### Performance Issue

```markdown
## Problem
Describe the performance bottleneck and its impact

## Current Performance
- Metric 1: [e.g., response time = 5 seconds]
- Metric 2: [e.g., memory usage = 2GB]
- Metric 3: [e.g., throughput = 100 req/sec]

## Target Performance
- Metric 1: [e.g., response time < 500ms]
- Metric 2: [e.g., memory usage < 500MB]
- Metric 3: [e.g., throughput > 1000 req/sec]

## Profiling Data
Attach profiling data, flame graphs, or performance traces

## Proposed Solution
High-level optimization approach

## Acceptance Criteria
- [ ] Performance targets met
- [ ] No functionality regression
- [ ] Load testing confirms improvements
```

### Refactoring

```markdown
## Problem
Why does this code need refactoring? What's the current pain point?

## Current State
Describe current code organization and issues

## Proposed Changes
High-level refactoring approach

## Benefits
- Improved maintainability
- Reduced duplication
- Better test coverage
- [Other benefits]

## Risks
- Potential regression areas
- Migration complexity
- [Other risks]

## Acceptance Criteria
- [ ] All existing tests pass
- [ ] No behavior changes (pure refactoring)
- [ ] Code coverage maintained or improved
- [ ] Documentation updated
```

## Best Practices

### Use Labels Effectively

Apply appropriate labels to help with:
- **Type**: `bug`, `feature`, `enhancement`, `documentation`
- **Priority**: `P0-critical`, `P1-high`, `P2-medium`, `P3-low`
- **Status**: `needs-triage`, `ready-to-work`, `in-progress`, `blocked`
- **Area**: `api`, `ui`, `database`, `performance`, `security`

### Link Related Issues and PRs

```markdown
## Related
- Depends on #123 (auth refactoring)
- Blocks #125 (mobile app launch)
- Related to #124 (performance improvements)
- Duplicate of #100 (if applicable)
- Follow-up to #90
- See also: [Design Doc](link)
```

### Include Visuals

For UI/UX issues:
- Screenshots of current state
- Mockups of proposed changes
- User flow diagrams
- Before/after comparisons

```markdown
## Mockups

### Current State
![Current UI](./screenshots/current.png)

### Proposed Design
![Proposed UI](./screenshots/proposed.png)

**Key improvements:**
- Moved action buttons to more prominent location
- Added progress indicator
- Improved error message visibility
```

### Estimate Complexity

Help with prioritization:

```markdown
## Complexity Estimate
- **Effort**: 3-5 days
- **Risk**: Low (well-understood problem)
- **Dependencies**: None
- **Skills needed**: Backend Python, Redis caching
```

### Provide Examples

Concrete examples clarify requirements:

```markdown
## Examples

### Example 1: Small Dataset (100 rows)
- Current time: 2 seconds
- Target time: <1 second
- Expected: Instant results, no progress indicator needed

### Example 2: Medium Dataset (10,000 rows)
- Current time: 30 seconds
- Target time: <5 seconds
- Expected: Progress indicator, streaming results

### Example 3: Large Dataset (100,000 rows)
- Current time: Times out (>60 seconds)
- Target time: <20 seconds
- Expected: Chunked processing, downloadable result
```

## Common Mistakes to Avoid

### 1. Solution-First Thinking
❌ **Bad:** "Add caching" (jumps to solution)
✅ **Good:** "API response time is 5s, users expect <500ms" (states problem)

### 2. Vague Problem Description
❌ **Bad:** "App is buggy"
✅ **Good:** "Form submission fails when email field contains '+' character"

### 3. Missing Acceptance Criteria
❌ **Bad:** No clear definition of done
✅ **Good:** Specific, testable checklist

### 4. Omitting Context
❌ **Bad:** Just the problem statement
✅ **Good:** Problem + impact + constraints + related issues

### 5. Unclear Priority
❌ **Bad:** "This is urgent!" (without justification)
✅ **Good:** "P0-critical: Blocks Q4 mobile app launch (revenue impact: $50K/month)"

## Examples

### Example 1: Performance Bug

```markdown
# Report generation times out for large datasets

## Problem
Report generation fails with timeout error for datasets containing more than
10,000 rows. Users see "Request timeout" error after waiting 60+ seconds.

Impact:
- 45% of report generation attempts fail (analytics data)
- 20+ support tickets per week
- Users forced to manually export data in smaller batches

## Current Behavior
1. User clicks "Generate Report" button
2. No progress indication
3. After 60 seconds, timeout error appears
4. No way to resume or save partial results

## Root Cause (Hypothesis)
All data loaded into memory before processing, causing:
- High memory usage (>2GB for 10K rows)
- Slow processing (not optimized for large datasets)
- No streaming or progressive rendering

## Solution
Implement streaming report generation with chunked processing:

1. Process data in 1,000-row chunks
2. Stream results to client progressively
3. Show progress indicator (% complete)
4. Allow cancellation without orphaning processes

## Acceptance Criteria

### Functional
- [ ] Reports with 10K+ rows complete successfully
- [ ] First results visible within 2 seconds
- [ ] Complete report available in <10 seconds (10K rows)
- [ ] Progress indicator shows % complete
- [ ] User can cancel operation at any time
- [ ] Partial results saved if cancelled

### Performance
- [ ] Memory usage <500MB regardless of dataset size
- [ ] No memory leaks (tested with 100 consecutive reports)
- [ ] Handles datasets up to 100K rows

### Edge Cases
- [ ] Empty datasets handled gracefully
- [ ] Special characters rendered correctly (unicode, emojis)
- [ ] Network interruption recovers gracefully

## Technical Approach
1. Refactor report generator to use streaming SQL queries
2. Implement server-sent events for progress updates
3. Add Redis-based job queue for large reports
4. Implement progressive rendering in frontend

## Testing Strategy
- Load testing with 100K row dataset
- Memory profiling during generation
- Concurrent report generation (10 simultaneous users)

## Related
- Related to #234 (API performance improvements)
- Blocks #235 (enterprise tier launch)

## Priority
**P1-High**: Affects 45% of report generation attempts, causing significant user frustration and support burden.

## Labels
`bug`, `performance`, `P1-high`, `backend`, `frontend`
```

### Example 2: Feature Request

```markdown
# Add JWT-based authentication for stateless API

## Problem
Current session-based authentication doesn't support horizontal scaling,
limiting our ability to handle traffic spikes and blocking mobile app launch.

Current limitations:
- Requires sticky sessions in load balancer
- Session state lost when server restarts
- Cannot dynamically add servers during traffic spikes
- Incompatible with mobile app (no cookie support)

Business impact:
- 2 production outages during traffic spikes (>10K concurrent users)
- Mobile app launch blocked (scheduled for Dec 1, revenue: $50K/month)
- Infrastructure costs 30% higher than necessary

## Solution
Migrate to JWT token-based authentication with refresh token mechanism.

Components:
1. **Access tokens**: Short-lived JWT (15 minutes)
2. **Refresh tokens**: Long-lived (7 days), stored securely
3. **Token validation**: Middleware for all API endpoints
4. **Migration path**: Support both session and JWT during transition

## User Story
As an API developer, I want stateless authentication so that I can scale
the API horizontally without sticky sessions and support mobile clients.

## Acceptance Criteria

### Functional Requirements
- [ ] Users can authenticate with username/password
- [ ] Access token issued on successful login (15 min expiry)
- [ ] Refresh token issued on successful login (7 day expiry)
- [ ] Refresh endpoint exchanges valid refresh token for new access token
- [ ] All API endpoints validate JWT before processing request
- [ ] Invalid/expired tokens return 401 Unauthorized
- [ ] Token revocation supported (logout)

### Security Requirements
- [ ] Tokens signed with RS256 algorithm (asymmetric)
- [ ] Refresh tokens stored securely (HttpOnly, Secure flags)
- [ ] No sensitive data in JWT payload
- [ ] Rate limiting on auth endpoints (10 req/min per IP)
- [ ] Security audit completed before production deployment

### Migration Requirements
- [ ] Backwards compatible during transition (support sessions + JWT)
- [ ] Existing sessions remain valid (no forced logout)
- [ ] Automated migration script for user accounts
- [ ] 30-day transition period before disabling sessions
- [ ] Migration guide for API clients

### Performance Requirements
- [ ] Token validation <10ms (no database lookup)
- [ ] Supports 50,000 concurrent users
- [ ] Load testing confirms no bottlenecks

### Documentation
- [ ] API documentation updated with JWT examples
- [ ] Migration guide for API clients published
- [ ] Admin guide for token management
- [ ] Security best practices documented

## Technical Approach

### Architecture
```
┌─────────┐     1. Login      ┌─────────────┐
│ Client  │ ────────────────> │  Auth API   │
└─────────┘                   └─────────────┘
     │                               │
     │ 2. JWT + Refresh Token        │
     │ <─────────────────────────────┘
     │
     │ 3. API Request + JWT
     │ ───────────────────────────>
     │                         ┌─────────────┐
     │                         │  API Server │
     │ 4. Response             └─────────────┘
     │ <──────────────────────
```

### Implementation Steps
1. Add PyJWT dependency
2. Create JWT service module (sign, verify, refresh)
3. Implement auth endpoints (/login, /refresh, /logout)
4. Add JWT validation middleware
5. Update API documentation
6. Deploy with feature flag (gradual rollout)

### Token Structure
```json
{
  "sub": "user_id",
  "name": "John Doe",
  "role": "admin",
  "iat": 1609459200,
  "exp": 1609460100
}
```

## Alternatives Considered

### 1. OAuth 2.0
**Pros:** Industry standard, well-supported
**Cons:** Overkill for our use case, added complexity
**Decision:** Too complex for internal API

### 2. Keep session-based auth
**Pros:** No migration needed
**Cons:** Doesn't solve scaling problem
**Decision:** Doesn't meet requirements

### 3. API keys
**Pros:** Simple
**Cons:** No expiration, harder to revoke
**Decision:** Less secure than JWT

## Open Questions
- [ ] Should we support multiple simultaneous sessions?
- [ ] What should refresh token rotation policy be?
- [ ] Should we integrate with SSO (future)?

## Testing Strategy
- Unit tests for JWT service (sign, verify, expire)
- Integration tests for auth endpoints
- Load testing with 50K concurrent users
- Security testing (token tampering, replay attacks)
- Penetration testing before production

## Rollout Plan
1. **Week 1**: Development and testing
2. **Week 2**: Internal beta (dev team)
3. **Week 3**: Staged rollout (10% of users)
4. **Week 4**: Full rollout (100% of users)
5. **Week 5-8**: Monitor, support transition
6. **Week 9**: Disable session-based auth

## Related
- Depends on #123 (security hardening)
- Blocks #125 (mobile app launch)
- Related to #124 (horizontal scaling infrastructure)
- Design doc: [JWT Architecture](link)

## Priority
**P0-Critical**: Blocks Q4 mobile app launch (Dec 1 deadline, $50K/month revenue at stake)

## Complexity Estimate
- **Effort**: 2-3 weeks (including testing and migration)
- **Risk**: Medium (requires careful security review)
- **Skills needed**: Backend (Python), security, DevOps

## Labels
`feature`, `P0-critical`, `backend`, `security`, `authentication`
```

## Summary

Great issue descriptions:
- **State the problem clearly** - Impact and pain points
- **Propose a solution** - Desired outcome and approach
- **Define success** - Specific, testable acceptance criteria
- **Provide context** - Environment, constraints, related work
- **Include examples** - Concrete scenarios and edge cases
- **Link related issues** - Dependencies, blockers, related work
- **Estimate complexity** - Help with prioritization

**Remember:** A well-written issue saves hours of back-and-forth clarification and helps contributors implement the right solution the first time.
