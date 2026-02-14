# Research Patterns - Detailed Guide

## Example Research Workflows

### Workflow 1: Architecture Decision

**Trigger**: "Should we use microservices or monolith for this feature?"

**Research Process**:
1. Define question: "What architecture pattern for feature X with Y requirements?"
2. Codebase search: Check existing architecture (`docs/architecture/`)
3. WebSearch:
   - "microservices vs monolith decision criteria 2025"
   - "when to use microservices"
   - "monolith to microservices migration patterns"
4. WebFetch: Martin Fowler, microservices.io, AWS architecture blog
5. Distill findings:
   - Comparison table (complexity, ops, scaling, etc.)
   - Decision tree based on our requirements
   - Recommendation with clear reasoning

**Output**: `docs/research/20251018_architecture_decision/findings.md`

### Workflow 2: Library Comparison

**Trigger**: "Which Python caching library should we use?"

**Research Process**:
1. Define question: "Best caching library for ML model inference with TTL support?"
2. Codebase search: Check if we already use a caching library
3. WebSearch:
   - "Python caching libraries comparison 2025"
   - "Redis vs Memcached Python"
   - "cachetools vs dogpile.cache"
4. WebFetch: Official docs for top 3 libraries, performance benchmarks
5. Distill findings:
   - Feature comparison table
   - Performance benchmarks
   - Ease of use comparison
   - Recommendation based on our needs

**Output**: `docs/research/20251018_caching_library/findings.md`

### Workflow 3: Security Pattern

**Trigger**: "How should we handle API key authentication?"

**Research Process**:
1. Define question: "Secure API key authentication for external API?"
2. Codebase search: Check current auth patterns
3. WebSearch:
   - "API key authentication best practices 2025"
   - "API key security OWASP"
   - "API key vs OAuth comparison"
4. WebFetch: OWASP API Security, Auth0 docs, security blogs
5. Distill findings:
   - Security threat model
   - Recommended implementation (key rotation, rate limiting, etc.)
   - OWASP compliance checklist
   - Secure code examples

**Output**: `docs/research/20251018_api_key_auth/findings.md`

---

## Key Takeaways

1. **Research is an investment**: 20 minutes of research saves hours of refactoring.

2. **Codebase first**: Don't reinvent patterns we already have.

3. **Quality over quantity**: 3 great sources > 10 mediocre sources.

4. **Code examples are mandatory**: Theory alone is not actionable.

5. **Security is non-negotiable**: Always consider security implications.

6. **Tradeoffs must be explicit**: Help decision-makers understand choices.

7. **Recent sources preferred**: 2024-2025 for current best practices.

8. **Research feeds the whole workflow**: Findings guide all downstream subagents.

---

**This skill enables confident, informed implementation by ensuring we learn from the industry before we build.**
