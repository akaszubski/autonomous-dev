# Test Project 1: Simple API - Validation Guide

**Purpose**: Test Enhancement 3 - PROJECT.md Bootstrapping

## What This Tests

✅ `/create-project-md --generate` command
✅ `project-bootstrapper` agent codebase analysis
✅ Architecture pattern detection (MVC pattern)
✅ Tech stack extraction from package.json
✅ File organization documentation generation

## Expected Behavior

### 1. Run Bootstrap Command

```bash
cd plugins/autonomous-dev/tests/synthetic-projects/test1-simple-api
/create-project-md --generate
```

### 2. Expected Output

```
🔍 Analyzing codebase...

✅ Found README.md (extracting project vision)
✅ Found package.json (extracting tech stack)
✅ Analyzing src/ structure (3 files)
✅ Analyzing tests/ structure (unit tests detected)

🧠 Architecture pattern detected: MVC (Models, Routes)

✅ Generated PROJECT.md (350-450 lines)

📋 Sections Created:
✅ Project Vision (from README.md)
✅ Architecture Overview (MVC pattern)
✅ Technology Stack (Node.js, Express, PostgreSQL)
✅ File Organization Standards
✅ Development Workflow (from package.json scripts)
✅ Testing Strategy (unit tests, Jest)
```

### 3. Validation Checklist

**PROJECT.md should contain:**

- [ ] **Project Vision**: "REST API for managing blog posts"
- [ ] **Architecture Pattern**: MVC or simple REST API
- [ ] **Tech Stack**:
  - [ ] Node.js 20.x
  - [ ] Express 4.18
  - [ ] PostgreSQL
  - [ ] TypeScript 5.3
- [ ] **Dependencies**: Listed with purposes
  - [ ] express - Web framework
  - [ ] pg - PostgreSQL client
  - [ ] jsonwebtoken - JWT authentication
- [ ] **File Organization**:
  - [ ] src/ - Source code
  - [ ] tests/unit/ - Unit tests
  - [ ] Root directory policy (max 8 .md files)
- [ ] **Development Workflow**:
  - [ ] npm run dev - Start dev server
  - [ ] npm test - Run tests
  - [ ] npm run build - Build for production
- [ ] **Testing Strategy**:
  - [ ] Unit tests in tests/unit/
  - [ ] Framework: Jest
  - [ ] Coverage target: 80%
- [ ] **Key Components**:
  - [ ] routes/ - API endpoints
  - [ ] models/ - Data models

**Line count**: 300-500 lines

**TODO markers**: 5-10 sections needing customization

### 4. Quality Checks

**Run alignment after generation:**
```bash
/align-project
```

Expected: 90%+ alignment score (newly generated, should be accurate)

### 5. Manual Review

**Check these sections for accuracy:**

1. **Architecture description** - Does it match the MVC/REST pattern?
2. **Data flow** - Is there an ASCII diagram or clear description?
3. **Component list** - Are routes/, models/ mentioned?
4. **Testing strategy** - Does it mention Jest and unit tests?

## Success Criteria

✅ PROJECT.md generated in < 60 seconds
✅ 300-500 lines
✅ 80-90% complete (10-20% TODO markers)
✅ All required sections present
✅ Architecture pattern correctly detected (MVC)
✅ Tech stack accurately extracted
✅ File organization standards included
✅ Passes `/align-project` with 90%+ score

## Common Issues

**Issue**: Architecture pattern detected as "Monolithic" instead of "MVC"
**Fix**: This is acceptable - small API can be considered simple/monolithic

**Issue**: Some TODO markers in unexpected places
**Fix**: Expected - bootstrapper marks sections needing domain knowledge

**Issue**: Tech stack missing some dependencies
**Fix**: Should list core dependencies (express, pg, jwt) - dev dependencies optional
