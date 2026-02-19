---
name: research-patterns
version: 1.0.0
type: knowledge
description: Enforcement skill for consistent research methodology
keywords: [research, sources, evidence, methodology, codebase-recon]
auto_activate: true
allowed-tools: [WebSearch, WebFetch, Read, Grep, Glob]
---

# Research Patterns Enforcement Skill

Ensures every research task follows a consistent, evidence-based methodology. Used by the researcher and researcher-local agents.

## 4-Phase Research Methodology

Every research task MUST follow these phases in order.

### Phase 1: Codebase Recon
- Grep/Glob for existing patterns that relate to the task
- Identify what the codebase already does (avoid reinventing)
- Note file locations, naming conventions, architectural patterns
- Document existing test patterns for the area

### Phase 2: Targeted Web Search
- Formulate 2-3 specific search queries
- Include the current year in queries for freshness (e.g., "JWT best practices 2026")
- Search for official documentation first
- Search for known issues or CVEs if security-related

### Phase 3: Deep Fetch Top Sources
- Fetch the top 2-3 most relevant results
- Extract specific code examples, configuration snippets, or API references
- Note version numbers and compatibility requirements
- Record URLs for citation

### Phase 4: Synthesis with Gap Analysis
- Compare findings against existing codebase patterns
- Identify gaps between current implementation and best practices
- Produce structured recommendations with tradeoffs
- Flag risks and unknowns explicitly

---

## Source Hierarchy

When sources conflict, prefer in this order:

1. **Official documentation** — language docs, framework docs, RFCs
2. **Authoritative GitHub repos** — reference implementations, official examples
3. **Stack Overflow** — accepted answers with high votes, verify currency
4. **Blog posts / tutorials** — cross-reference with official docs

Every recommendation MUST include at least one URL source.

---

## HARD GATE: Research Output

**FORBIDDEN**:
- Recommending an approach without citing sources
- Using "I think" or "I believe" without supporting evidence
- Skipping codebase search (Phase 1) and jumping straight to web
- Single-source recommendations — minimum 2 sources for any recommendation
- Presenting opinions as facts
- Ignoring existing codebase patterns in favor of greenfield approaches

**REQUIRED**:
- Minimum 3 sources cited across the research output
- Existing codebase patterns identified first (Phase 1 before Phase 2)
- Tradeoffs stated for every recommendation (pros AND cons)
- Structured output in the format below
- Version/date noted for all external sources
- Risks section with at least one identified risk

---

## Required Output Format

```json
{
  "findings": "Summary of what was discovered",
  "sources": [
    {"url": "https://...", "title": "...", "relevance": "..."},
    {"url": "https://...", "title": "...", "relevance": "..."},
    {"url": "https://...", "title": "...", "relevance": "..."}
  ],
  "existing_patterns": [
    {"file": "path/to/file.py", "pattern": "description", "reusable": true}
  ],
  "recommendations": [
    {
      "approach": "description",
      "pros": ["..."],
      "cons": ["..."],
      "effort": "low/medium/high"
    }
  ],
  "risks": [
    {"risk": "description", "mitigation": "how to handle", "severity": "low/medium/high"}
  ]
}
```

---

## Anti-Patterns

### BAD: Vague "best practice" without citation
```
"The best practice is to use dependency injection."
```
No source, no context, no tradeoffs. Useless as research output.

### GOOD: Cited recommendation with tradeoffs
```
"Dependency injection is recommended by the Python Packaging Guide
(https://packaging.python.org/...) for testability. Tradeoff: adds
indirection that can make debugging harder for small projects."
```

### BAD: Ignoring existing codebase patterns
Recommending a completely new auth library when the codebase already uses a working pattern. Always check what exists first.

### BAD: Single-source echo chamber
Reading one blog post and presenting its opinion as the definitive answer. Cross-reference with at least one other source.

### GOOD: Multiple sources with synthesis
```
"Three sources agree on token rotation (RFC 6749 Section 10.4,
OWASP Cheat Sheet, and the existing auth.py pattern at line 42).
The codebase already implements refresh tokens; recommend extending
rather than replacing."
```

---

## Cross-References

- **security-patterns**: Security-specific research requirements
- **architecture-patterns**: How research feeds into architecture planning
- **project-alignment**: Ensuring research aligns with PROJECT.md scope
