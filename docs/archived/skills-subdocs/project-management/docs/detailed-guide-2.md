# Project Management - Detailed Guide

## GOALS

1. **Reduce page load time from 5s to < 2s** (Performance)
   - Specific: Page load time
   - Measurable: 5s → 2s
   - Achievable: Yes (optimization techniques exist)
   - Relevant: User experience critical for retention
   - Time-bound: By end of Q2

2. **Increase test coverage from 60% to 85%** (Quality)
   - Specific: Test coverage metric
   - Measurable: 60% → 85%
   - Achievable: Yes (identify untested code)
   - Relevant: Reduces bugs in production
   - Time-bound: By v2.0 release

3. **Launch mobile app for iOS and Android** (Expansion)
   - Specific: Mobile apps (both platforms)
   - Measurable: App store submissions approved
   - Achievable: Yes (team has mobile expertise)
   - Relevant: 70% of traffic is mobile web
   - Time-bound: Beta by Q3, GA by Q4
```

---

### OKRs (Objectives & Key Results)

**Objective**: Inspirational, qualitative goal

**Key Results**: Measurable outcomes (3-5 per objective)

#### Example OKR

```markdown
## GOALS

**Objective**: Become the fastest AI training platform

**Key Results**:
- KR1: Training time for LoRA < 10 minutes (currently 45 min)
- KR2: 95% of users rate training speed as "fast" or "very fast"
- KR3: Support 10K concurrent training jobs (currently 1K)

**Success Metrics**:
- Training time: < 10 min ✅
- User satisfaction: 95% positive ✅
- Concurrent jobs: 10K ✅
```

---

## Scope Definition Best Practices

### The "In vs Out" Template

**Purpose**: Prevent scope creep by being explicit

```markdown
## SCOPE

**What's IN Scope** ✅:

**MVP Features** (v1.0 launch):
- ✅ **User authentication** (email/password, OAuth)
- ✅ **Basic CRUD operations** (create, read, update, delete)
- ✅ **Search functionality** (full-text search)
- ✅ **Mobile responsive design** (works on phones/tablets)

**What's OUT of Scope** ❌:

- ❌ **Advanced analytics** - Deferred to v2.0 (needs dedicated team)
- ❌ **Real-time collaboration** - Too complex for MVP
- ❌ **AI-powered recommendations** - Requires ML expertise we don't have yet
- ❌ **White-labeling** - Enterprise feature for later
```

### The "Must Have, Should Have, Could Have, Won't Have" (MoSCoW) Method

```markdown
## SCOPE (MoSCoW)

**Must Have** (Non-negotiable for launch):
- User login
- Data persistence
- Error handling

**Should Have** (Important but not critical):
- Email notifications
- Export to CSV
- Dark mode

**Could Have** (Nice to have if time permits):
- Keyboard shortcuts
- Bulk operations
- Advanced filters

**Won't Have** (Explicitly not in this release):
- Mobile app
- Offline mode
- Multi-language support
```

---

## Constraint Documentation

### Types of Constraints

#### 1. Technical Constraints

```markdown
## CONSTRAINTS

**Technical Constraints**:
- **Python 3.11+**: Required for new type hints and performance improvements
- **PostgreSQL only**: No NoSQL - need ACID transactions for financial data
- **< 500MB Docker image**: Deploy to edge locations with limited bandwidth
- **RESTful API**: No GraphQL - team lacks expertise, adds complexity
```

#### 2. Resource Constraints

```markdown
**Resource Constraints**:
- **Budget**: $50K total (includes infrastructure, tools, contractors)
- **Timeline**: 3-month deadline (hard constraint - board presentation)
- **Team**: 2 full-time devs (cannot hire more until Q3)
- **Infrastructure**: AWS only (existing credits, no multi-cloud)
```

#### 3. Legal/Compliance Constraints

```markdown
**Compliance Constraints**:
- **GDPR**: Must support data export and deletion (EU users)
- **HIPAA**: Healthcare data requires encryption at rest and in transit
- **SOC 2**: Annual audit required - need logging and access controls
- **Age restriction**: COPPA compliance - no users under 13
```

#### 4. External Dependencies

```markdown
**External Dependencies**:
- **OpenAI API**: Training features depend on GPT-4 availability
- **Stripe**: Payment processing (single point of failure)
- **AWS S3**: File storage (if S3 goes down, uploads fail)
- **Partner API**: Data sync requires their API stability
```

---

## Sprint Planning

### Sprint Template

```markdown
## CURRENT SPRINT

**Sprint 5**: "Search & Filter"
**Dates**: 2025-11-01 to 2025-11-14 (2 weeks)
**Goal**: Users can search and filter results efficiently

**Capacity**: 80 story points (2 devs × 2 weeks × 20 pts/week)

**In Progress** (40 pts):
- [ ] Implement full-text search (13 pts) - @alice - 50% done
- [ ] Add filter UI component (8 pts) - @bob - 25% done
- [ ] Optimize query performance (13 pts) - @alice - blocked (waiting on DB migration)
- [ ] Update search documentation (3 pts) - @bob - 10% done
- [ ] Write integration tests (3 pts) - unassigned

**Planned Next** (20 pts):
- [ ] Add autocomplete to search (8 pts)
- [ ] Implement saved searches (5 pts)
- [ ] Add pagination (5 pts)
- [ ] Fix search bug #127 (2 pts)

**Done This Sprint** (18 pts):
- [x] Design search UX mockups (5 pts)
- [x] Set up Elasticsearch (8 pts)
- [x] Spike: Evaluate search libraries (5 pts)

**Blocked**:
- Query optimization blocked on DB migration (see issue #145)

**Risks**:
- Elasticsearch setup more complex than expected (3 days vs 1 day estimate)
- Bob out sick 2 days - may not finish filter UI

**Sprint Retrospective Topics**:
- Estimation accuracy (search tasks underestimated)
- Dependency management (DB migration caused blocker)
```

---

### Sprint Planning Checklist

**Before Sprint Planning**:
- [ ] **Backlog groomed** - Stories estimated and prioritized
- [ ] **Dependencies identified** - External blockers noted
- [ ] **Team capacity known** - Account for holidays, PTO
- [ ] **Previous sprint reviewed** - Retro insights captured

**During Sprint Planning**:
- [ ] **Sprint goal defined** - One sentence, clear outcome
- [ ] **Stories committed** - Team agrees on workload
- [ ] **Tasks broken down** - Stories decomposed into tasks
- [ ] **Assignments made** - Owners identified (optional)
- [ ] **Definition of done agreed** - What "done" means

**During Sprint**:
- [ ] **Daily standup** - 15 min sync (blockers, progress)
- [ ] **Update sprint board** - Move tasks, update progress
- [ ] **Flag blockers early** - Don't wait until sprint end
- [ ] **Adjust scope if needed** - Remove low-priority items

**End of Sprint**:
- [ ] **Demo/Review** - Show completed work to stakeholders
- [ ] **Retrospective** - What went well, what to improve
- [ ] **Update metrics** - Velocity, burndown, etc.
- [ ] **Close sprint** - Move incomplete items to backlog

---

## Milestone Planning

### Milestone Template

```markdown
## ROADMAP

### Milestone 1: MVP Launch (Months 1-2)

**Goal**: Production-ready app with core features

**Features**:
- [x] User authentication
- [x] CRUD operations
- [ ] Search functionality (Sprint 5)
- [ ] Mobile responsive design
- [ ] Error handling

**Success Criteria**:
- ✅ 50 beta users signed up
- ✅ < 5 critical bugs
- ✅ 80%+ test coverage
- ⏳ Sub-2s page load time

**Dependencies**:
- AWS account approved (done)
- Design mockups complete (done)
- Database schema finalized (in progress)

**Risks**:
- Third-party API integration delayed (mitigation: build fallback)
```

---

### Roadmap Granularity

**Month 1-3** (Detailed):
```markdown
### Phase 1: Foundation (Months 1-3)

**Month 1**:
- Week 1-2: User auth + database setup
- Week 3-4: CRUD operations + basic UI

**Month 2**:
- Week 1-2: Search + filters
- Week 3-4: Mobile responsive + testing

**Month 3**:
- Week 1-2: Performance optimization
- Week 3-4: Beta launch + bug fixes
```

**Month 4-6** (Less Detailed):
```markdown
### Phase 2: Growth (Months 4-6)
- Analytics dashboard
- Advanced features (saved searches, exports)
- Scaling infrastructure
```

**Month 7-12** (High-Level):
```markdown
### Phase 3: Scale (Months 7-12)
- Enterprise features
- API for third-party integrations
- International expansion
```

---

## Alignment Validation

### Checking Alignment

When evaluating a feature request, ask:

**1. Does it serve a GOAL?**
```markdown
Feature: Add social media sharing
Goal alignment: ✅ YES - Goal 2 is "Increase user growth"
Rationale: Sharing drives viral growth
```

**2. Is it IN SCOPE?**
```markdown
Feature: Add video calling
Scope check: ❌ NO - Out of scope (requires real-time infrastructure)
Recommendation: Defer to Phase 3 or reject
```

**3. Does it violate CONSTRAINTS?**
```markdown
Feature: Use MongoDB instead of PostgreSQL
Constraint check: ❌ YES - Violates "PostgreSQL only" constraint
Rationale: Team lacks NoSQL expertise, ACID transactions required
```

**4. Does it contribute to current SPRINT goal?**
```markdown
Feature: Add dark mode
Sprint goal: "Search & Filter" ❌ NO
Recommendation: Add to backlog for later sprint
```

---

### Alignment Decision Tree

```
Is feature request aligned?
│
├─ Does it serve a GOAL?
│  ├─ NO → Reject (explain why)
│  └─ YES → Continue
│
├─ Is it IN SCOPE?
│  ├─ NO → Defer or reject
│  └─ YES → Continue
│
├─ Does it violate CONSTRAINTS?
│  ├─ YES → Modify or reject
│  └─ NO → Continue
│
└─ Is it the right time (sprint/phase)?
   ├─ NO → Add to backlog for later
   └─ YES → Approve and prioritize
```

---

## PROJECT.md Best Practices
