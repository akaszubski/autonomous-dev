# Git Workflow - Detailed Guide

## Pull Request Guidelines

### PR Title

Same as commit message format:

```
feat: add PDF extraction support
fix: resolve memory leak in data loader
docs: update installation instructions
```

### PR Description Template

```markdown
## Summary
Brief description of changes (1-3 sentences)

## Changes
- Add PDF extraction using PyPDF2
- Update DataCurator class with extract_from_pdf method
- Add tests for PDF extraction

## Testing
- [x] Unit tests added/updated
- [x] Integration tests pass
- [x] Manual testing completed

## Checklist
