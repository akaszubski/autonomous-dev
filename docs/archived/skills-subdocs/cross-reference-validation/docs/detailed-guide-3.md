# Cross Reference Validation - Detailed Guide

## Performance Optimization

For large projects (100+ documentation files):

**Batch file existence checks**:
```bash
# Instead of checking each file individually
# Create temp file with all references
cat references.txt | while read ref; do
  [ -f "$ref" ] || echo "BROKEN: $ref"
done > broken_refs.txt
```

**Cache git history**:
```bash
# Get all file moves once
git log --follow --name-status --diff-filter=R > /tmp/git_moves.txt

# Parse once, reference many times
```

**Parallel validation**:
```bash
# Split references into chunks
# Validate each chunk in parallel using & backgrounding
```

---

**This skill ensures documentation references stay accurate as code evolves, preventing link rot and reference decay.**
