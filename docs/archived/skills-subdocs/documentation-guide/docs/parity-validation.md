# Documentation Parity Validation Checklist

Before completing documentation sync, validate documentation parity:

## 1. Run Parity Validator

```bash
python plugins/autonomous-dev/lib/validate_documentation_parity.py --project-root .
```

## 2. Check Version Consistency

- CLAUDE.md **Last Updated** date matches PROJECT.md
- No version drift between documentation files

## 3. Verify Count Accuracy

- Agent count matches actual .md files in agents/
- Command count matches actual .md files in commands/
- Skill count matches actual .md files in skills/
- Hook count matches actual .py files in hooks/

## 4. Validate Cross-References

- Documented agents exist as files
- Documented commands exist as files
- Documented libraries exist in lib/
- No undocumented features

## 5. Ensure CHANGELOG is Up-to-Date

- Current version from plugin.json is documented in CHANGELOG.md
- Release notes are complete

## 6. Confirm Security Documentation

- Security practices mentioned in CLAUDE.md
- SECURITY.md exists with CWE coverage
- Security utilities are documented

## Exit Criteria

**Exit with error** if parity validation fails (has_errors == True). Documentation must be accurate.
