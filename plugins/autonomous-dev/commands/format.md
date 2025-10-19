

**Format code using language-specific formatters (black, isort, ruff for Python; prettier, eslint for JS/TS)**# Format Code

Run code formatters on the project to ensure consistent style.

## Usage

```bash
/format
```

## What This Does

Automatically formats code using configured formatters:

**Python**:
- `black .` - Code formatting (88 char line length)
- `isort .` - Import sorting
- `ruff check --fix .` - Fast linting with auto-fixes

**JavaScript/TypeScript**:
- `npx prettier --write .` - Code formatting
- `npx eslint --fix .` - Linting with auto-fixes

## Example Output

```
Running code formatters...

Python:
✅ black: reformatted 12 files
✅ isort: sorted imports in 8 files
✅ ruff: fixed 5 auto-fixable issues

All files formatted successfully!
```

## When to Use

- Before committing code
- After implementing features
- When code review requests formatting fixes
- To maintain consistent code style

## Auto-Run vs Manual

This command is **manual** (you control when it runs).

**Alternative**: The `auto_format.py` hook can run automatically:
- On file save (if configured)
- Before git commit (pre-commit hook)

**Recommended**: Use `/format` manually for full control.

## Troubleshooting

### Formatters not found
```bash
# Install Python formatters
pip install black isort ruff

# Install JS/TS formatters
npm install -D prettier eslint
```

### Format conflicts with existing code
- Formatters may make large changes on first run
- Review changes with `git diff` before committing
- Adjust formatter config in `pyproject.toml` or `.prettierrc` if needed

## Related Commands

- `/test` - Run tests after formatting
- `/full-check` - Format + test + security scan
- `/commit` - Format + commit changes


**This command gives you manual control over code formatting instead of automatic hooks.**
