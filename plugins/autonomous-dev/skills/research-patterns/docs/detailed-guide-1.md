# Research Patterns - Detailed Guide

## Research Methodology

### 1. Define Clear Research Question

**Before starting research**:

```markdown
❓ **Research Question Template**:
- What: {What are we trying to build?}
- Why: {Why do we need it?}
- Scope: {What's in scope? What's out of scope?}
- Success: {What would a good solution look like?}
```

**Example**:
```markdown
What: Webhook handling system for receiving external events
Why: Need to integrate with 3rd-party services that push updates
Scope: IN - signature verification, retry logic, async processing
       OUT - webhook delivery (we're receiving, not sending)
Success: Secure, reliable, handles 1000+ webhooks/min
```

### 2. Search Existing Codebase First

**Always search internal patterns before external research.**

**Codebase Search Checklist**:

```markdown
□ Grep for relevant keywords (functionality, domain terms)
□ Glob for related files (naming patterns)
□ Read existing implementations (understand current patterns)
□ Check docs/ for existing architecture decisions
□ Review tests/ to understand current test patterns
```

**Common Search Patterns**:

| Goal | Grep Pattern | Glob Pattern |
|------|--------------|--------------|
| Find authentication | `"auth"`, `"login"`, `"token"` | `**/*auth*.py` |
| Find caching | `"cache"`, `"memoize"`, `"@lru_cache"` | `**/*cache*.py` |
| Find webhooks | `"webhook"`, `"callback"`, `"event"` | `**/*webhook*.py`, `**/*event*.py` |
| Find error handling | `"try:", "except", "raise"` | `**/*error*.py`, `**/*exception*.py` |

**Decision Tree**:
```
Found existing pattern?
├─ YES → Reuse/extend existing pattern
│         (Don't reinvent the wheel!)
│
└─ NO → Proceed with external research
        (Need to find industry best practices)
```

### 3. External Web Research

**When codebase search yields nothing, research externally.**

**WebSearch Query Strategy**:

#### Query Pattern Templates

**For Best Practices**:
```
"{topic} best practices {current_year}"
"{topic} design patterns {current_year}"
"{topic} common mistakes to avoid"
"{topic} anti-patterns"
```

**For Implementation Guidance**:
```
"{topic} {language} implementation"
"{topic} code examples GitHub"
"{topic} library comparison"
"{topic} step-by-step tutorial"
```

**For Security-Sensitive Topics**:
```
"{topic} security best practices"
"{topic} OWASP guidelines"
"{topic} secure implementation"
"{topic} vulnerability checklist"
```

**For Performance-Critical Topics**:
```
"{topic} performance optimization"
"{topic} scalability patterns"
"{topic} benchmarking"
"{topic} profiling and tuning"
```

**For Architecture Decisions**:
```
"{topic} architecture patterns"
"{topic} system design"
"{topic} microservices vs monolith"
"{topic} when to use"
```

#### Optimal Query Count

- **Minimum**: 3 queries (different angles on same topic)
- **Recommended**: 5 queries (comprehensive coverage)
- **Maximum**: 7 queries (diminishing returns after this)

**Example Research Plan**:
```markdown
Topic: "distributed caching for ML models"

Query 1: "distributed caching best practices 2025"
Query 2: "distributed caching Python Redis examples"
Query 3: "ML model caching strategies"
Query 4: "caching invalidation patterns"
Query 5: "Redis vs Memcached performance comparison"
```

### 4. Source Quality Evaluation

**Not all sources are created equal. Prioritize quality over quantity.**

#### Source Hierarchy (Highest to Lowest)

| Rank | Source Type | Trust Level | Example |
|------|-------------|-------------|---------|
| 1 | Official documentation | ⭐⭐⭐⭐⭐ | Python.org, FastAPI docs, [FRAMEWORK] docs |
| 2 | Official repositories | ⭐⭐⭐⭐⭐ | GitHub: pytorch/pytorch, ml-explore/[framework] |
| 3 | Well-known tech blogs | ⭐⭐⭐⭐ | Martin Fowler, Real Python, Uber Engineering |
| 4 | GitHub examples | ⭐⭐⭐⭐ | Popular repos with stars, active maintenance |
| 5 | Technical whitepapers | ⭐⭐⭐⭐ | Google, Meta, academic papers |
| 6 | Stack Overflow | ⭐⭐⭐ | Accepted answers, high votes |
| 7 | Blog posts | ⭐⭐⭐ | Individual developers (verify credibility) |
| 8 | Forum discussions | ⭐⭐ | Reddit, HN (good for trends, not authority) |
| 9 | Unverified tutorials | ⭐ | Medium posts, personal blogs (verify carefully) |

#### Recency Scoring

| Year | Score | When to Use |
|------|-------|-------------|
| 2025 | ⭐⭐⭐⭐⭐ | Cutting edge, latest practices |
| 2024 | ⭐⭐⭐⭐⭐ | Recent, highly relevant |
| 2023 | ⭐⭐⭐⭐ | Still current for most topics |
| 2022 | ⭐⭐⭐ | Acceptable for stable topics |
| 2021 | ⭐⭐ | Use only if nothing recent available |
| ≤2020 | ⭐ | Avoid unless foundational concepts |

**Exceptions** (where older sources are acceptable):
- Fundamental algorithms (sorting, graphs, etc.)
- Established design patterns (Gang of Four patterns)
- Mathematical foundations
- Core Python language features (pre-3.11)

#### Content Quality Scoring

**Award points for**:
- ✅ Multiple code examples (+2)
- ✅ Pros and cons comparison (+2)
- ✅ Performance benchmarks (+1)
- ✅ Security considerations (+1)
- ✅ Edge cases documented (+1)
- ✅ Testing examples (+1)
- ✅ Production experience shared (+1)

**Deduct points for**:
- ❌ Theory only, no code (-2)
- ❌ Incomplete examples (-1)
- ❌ No error handling shown (-1)
- ❌ Conflicting advice (-1)
- ❌ Obvious mistakes in code (-2)

**Overall Quality Formula**:
```
Quality = (Authority × 0.3) + (Recency × 0.25) + (Content × 0.2) + (Depth × 0.15) + (Confirmation × 0.1)
```

### 5. Distill Into Actionable Findings

**Transform research into implementation-ready guidance.**

#### Required Sections in Findings

**1. Executive Summary** (2-3 sentences)
- What's the recommended approach?
- Why is it best for our use case?
- What's the expected effort?

**2. Pattern Analysis**
- **Recommended Approach**: Detailed description + code example
- **Alternatives Considered**: At least 2 alternatives with pros/cons
- **Tradeoffs**: Comparison table

**3. Implementation Guide**
- **Step-by-Step**: Numbered steps with code examples
- **Integration Points**: Where in our codebase this fits
- **Dependencies**: Libraries, tools, infrastructure needed

**4. Pitfalls to Avoid**
- **Common Mistakes**: What developers often get wrong
- **Edge Cases**: Scenarios that need special handling
- **Security Considerations**: Vulnerabilities to prevent
- **Performance Issues**: Bottlenecks to avoid

**5. Source Evaluation**
- Table of all sources with quality ratings
- Notes on why each source was useful/not useful

**6. Next Steps**
- Recommended actions
- Files to create/modify
- Tests to write

---

## Pattern Recognition Framework

### Common Software Patterns

#### 1. Authentication/Authorization

**Research Focus**:
- OAuth 2.0 vs JWT vs API keys
- Session management
- Token refresh strategies
- RBAC vs ABAC

**Key Questions**:
- How are credentials stored securely?
- How is token expiration handled?
- What's the logout flow?
- How to handle concurrent sessions?

**Security Musts**:
- Password hashing (bcrypt, argon2)
- HTTPS only
- CSRF protection
- Rate limiting

#### 2. Caching

**Research Focus**:
- Cache invalidation strategies
- Cache eviction policies (LRU, LFU, TTL)
- Distributed vs local caching
- Cache coherence

**Key Questions**:
- What's the cache hit ratio target?
- How to handle cache misses?
- When to invalidate?
- How to prevent cache stampede?

**Common Patterns**:
- Write-through cache
- Write-behind cache
- Cache-aside
- Read-through cache

#### 3. Webhooks/Event Processing

**Research Focus**:
- Signature verification
- Retry logic and exponential backoff
- Idempotency
- Async vs sync processing

**Key Questions**:
- How to verify webhook authenticity?
- What happens if processing fails?
- How to prevent duplicate processing?
- How to handle order of events?

**Security Musts**:
- HMAC signature verification
- IP whitelisting (if applicable)
- Request validation
- Rate limiting

#### 4. API Design

**Research Focus**:
- REST vs GraphQL vs gRPC
- Versioning strategies
- Error response formats
- Pagination approaches

**Key Questions**:
- How to handle breaking changes?
- What's the rate limiting strategy?
- How to document the API?
- How to test the API?

**Best Practices**:
- Semantic versioning
- OpenAPI/Swagger docs
- Consistent error formats
- HATEOAS (if REST)

#### 5. Data Processing Pipelines

**Research Focus**:
- ETL vs ELT
- Batch vs stream processing
- Error handling and retries
- Monitoring and alerting

**Key Questions**:
- How to handle partial failures?
- How to ensure data quality?
- How to scale processing?
- How to monitor pipeline health?

**Common Tools**:
- Apache Airflow (batch)
- Apache Kafka (streaming)
- dbt (data transformation)
- Prefect (orchestration)

#### 6. Testing Strategies

**Research Focus**:
- Unit vs integration vs E2E tests
- Test data management
- Mocking strategies
- Coverage targets

**Key Questions**:
- What's the right test pyramid?
- How to test external dependencies?
- How to test async code?
- How to ensure tests are fast?

**Best Practices**:
- Arrange-Act-Assert pattern
- Given-When-Then (BDD)
- Test isolation
- Fast feedback loops

---

## Research Output Templates

### Template 1: Pattern Comparison

Use when comparing multiple approaches (e.g., "Redis vs Memcached"):

```markdown
# Comparison: {Option A} vs {Option B} vs {Option C}

## Quick Recommendation

**Use {Option A}** if: {scenario}
**Use {Option B}** if: {scenario}
**Use {Option C}** if: {scenario}

## Detailed Comparison

| Criterion | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| **Performance** | {rating + notes} | {rating + notes} | {rating + notes} |
| **Complexity** | {rating + notes} | {rating + notes} | {rating + notes} |
| **Scalability** | {rating + notes} | {rating + notes} | {rating + notes} |
| **Maintenance** | {rating + notes} | {rating + notes} | {rating + notes} |
| **Community** | {rating + notes} | {rating + notes} | {rating + notes} |
| **Cost** | {rating + notes} | {rating + notes} | {rating + notes} |

## Code Examples

### Option A
```python
# Example implementation
```

### Option B
```python
# Example implementation
```

### Option C
```python
# Example implementation
```

## Decision Matrix

**For our use case** (insert our specific requirements):

| Requirement | Option A | Option B | Option C |
|-------------|----------|----------|----------|
| Req 1 | ✅ | ❌ | ✅ |
| Req 2 | ✅ | ✅ | ❌ |
| Req 3 | ❌ | ✅ | ✅ |

**Winner**: {Option} because {reasoning}
```

### Template 2: Implementation Pattern

Use when researching how to implement a feature (e.g., "webhook handling"):

```markdown
# Implementation Pattern: {Feature Name}

## Pattern Overview
