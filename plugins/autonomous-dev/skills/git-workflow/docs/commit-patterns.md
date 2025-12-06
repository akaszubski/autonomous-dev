# Commit Message Patterns

Conventional commit patterns for consistent git history and automated tooling.

## Overview

Conventional Commits is a specification for adding human and machine-readable meaning to commit messages. The pattern enables automated changelog generation, semantic versioning, and clear communication of intent.

## Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Type

The type communicates the intent of the change:

- **feat:** A new feature for the user (not a new feature for build scripts)
- **fix:** A bug fix for the user (not a fix to a build script)
- **docs:** Documentation only changes (README, guides, API docs)
- **style:** Formatting changes that don't affect code meaning (white-space, formatting, missing semi-colons, etc)
- **refactor:** A code change that neither fixes a bug nor adds a feature (restructuring existing code)
- **test:** Adding missing tests or correcting existing tests
- **chore:** Changes to the build process, auxiliary tools, libraries, or other maintenance tasks

### Scope (Optional)

The scope provides additional contextual information about what part of the codebase is affected:

```bash
feat(api): add endpoint for user profile updates
fix(auth): resolve token refresh timing issue
docs(readme): update installation instructions
refactor(database): extract query builder to separate class
```

Common scopes:
- Component names: `api`, `cli`, `ui`, `database`
- Functional areas: `auth`, `validation`, `logging`
- File/module names: `user-service`, `config-parser`

### Description

The description is a short summary of the code changes:

- Use imperative, present tense: "change" not "changed" nor "changes"
- Don't capitalize the first letter
- No period (.) at the end
- Limit to 50-72 characters for readability

### Body (Optional)

The body provides additional context about the change:

- Use imperative, present tense
- Explain the motivation for the change (the "why")
- Contrast with previous behavior when useful
- Wrap at 72 characters for readability

### Footer (Optional)

The footer contains information about breaking changes and issue references:

```bash
# Issue references
Closes #123
Fixes #456
Resolves #789

# Breaking changes
BREAKING CHANGE: API endpoint /v1/users now requires authentication
```

## Breaking Changes

Breaking changes MUST be indicated in two ways:

### Method 1: Exclamation Mark

Add `!` after the type/scope:

```bash
feat!: remove deprecated API endpoints
feat(api)!: change response format for /users endpoint
```

### Method 2: Footer

Add `BREAKING CHANGE:` footer:

```bash
feat: update authentication flow

BREAKING CHANGE: OAuth tokens now expire after 1 hour instead of 24 hours.
Users will need to refresh tokens more frequently.
```

### Both Methods (Recommended)

For maximum clarity, use both:

```bash
feat(auth)!: implement JWT-based authentication

Replace session-based authentication with JWT tokens for better scalability
and stateless API design.

BREAKING CHANGE: Session cookies are no longer supported. All API clients
must migrate to JWT token authentication using the /auth/login endpoint.

Closes #42
```

## Commit Message Examples

### Simple Commits

```bash
feat: add user profile image upload
fix: resolve memory leak in data processing
docs: update API documentation for v2.0
style: format code with black formatter
refactor: extract validation logic to utils module
test: add integration tests for payment flow
chore: update dependencies to latest versions
```

### Commits with Scope

```bash
feat(cli): add --verbose flag for detailed output
fix(database): prevent duplicate entries in user table
docs(api): document rate limiting behavior
refactor(parser): simplify JSON parsing logic
test(integration): add end-to-end tests for checkout flow
```

### Commits with Body

```bash
feat: implement caching for API responses

Add Redis-based caching layer to reduce database load for frequently
accessed API endpoints. Cache TTL is configurable via environment variable.

Closes #156
```

```bash
fix: resolve race condition in concurrent uploads

Use file locking to prevent simultaneous writes to the same file during
parallel upload operations. This resolves intermittent data corruption
issues reported by users.

Fixes #234, #235
```

### Breaking Change Commits

```bash
feat!: change API response format to JSON:API spec

BREAKING CHANGE: API responses now follow JSON:API specification.
Clients must update their response parsing logic to handle the new format.

Before:
{
  "id": 1,
  "name": "John"
}

After:
{
  "data": {
    "type": "users",
    "id": "1",
    "attributes": {
      "name": "John"
    }
  }
}

Closes #78
```

## Best Practices

### Do's

✅ **Use imperative mood**: "add feature" not "added feature"
✅ **Keep first line under 72 characters**: Enables readable git log
✅ **Separate subject from body**: Use blank line between them
✅ **Explain why, not what**: The diff shows what changed
✅ **Reference issues**: Use `Closes #123`, `Fixes #456`
✅ **Use consistent types**: Stick to conventional commit types
✅ **Group related changes**: Multiple files for one logical change = one commit

### Don'ts

❌ **Don't use vague descriptions**: "updates", "fixes", "changes"
❌ **Don't commit unrelated changes together**: Keep commits focused
❌ **Don't use past tense**: "added" should be "add"
❌ **Don't exceed 50 chars without body**: Use body for longer descriptions
❌ **Don't commit work-in-progress**: Commits should be complete units of work
❌ **Don't skip the type prefix**: Always use conventional commit format

## Automated Tooling Benefits

Conventional commits enable:

1. **Automated changelog generation**: Generate CHANGELOG.md from commit history
2. **Semantic versioning**: Automatically determine next version (MAJOR.MINOR.PATCH)
3. **Release notes**: Create release notes from commit messages
4. **Issue tracking**: Link commits to issues automatically
5. **Code review**: Understand changes quickly from commit messages
6. **Git history navigation**: Filter commits by type (`git log --grep "^feat:"`)

## Further Reading

- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Angular Commit Guidelines](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)
- [Semantic Versioning](https://semver.org/)
