# CLAUDE.md

## Project Overview

This is a Python project designed to demonstrate good software engineering
practice, including clean architecture, automated testing, documentation,
observability, and controlled use of AI/agentic functionality.

The project should remain simple, maintainable, testable, and easy for
another engineer to understand.

---

## Core Engineering Principles

Follow these principles for all changes:

1. Prefer simple solutions over clever solutions.
2. Keep functions and classes small and focused.
3. Follow the Single Responsibility Principle.
4. Avoid unnecessary abstractions.
5. Do not duplicate logic.
6. Prefer explicit behaviour over implicit behaviour.
7. Keep business logic separate from UI, infrastructure, and external services.
8. Make dependencies explicit.
9. Fail safely and provide useful error messages.
10. Never hide errors or silently ignore failures.

Before introducing a new dependency, consider whether the requirement can be
met using the Python standard library or existing project dependencies.

---

## Python Standards

Use:

- Python 3.12+
- Type hints for functions and methods
- `dataclasses` or appropriate models for structured data
- `pathlib` rather than string manipulation for filesystem paths
- `logging` rather than `print()` for application logging
- f-strings for string formatting
- `pytest` for testing

Follow PEP 8 and standard Python naming conventions.

Example:

```python
def load_agent_definition(path: Path) -> AgentDefinition:
    ...
```

---

## Security Requirements (mandatory)

The following security rules from the project security policy are always in force:

- No hardcoded secrets, passwords, API keys, or tokens in source code.
- Secrets must come from environment variables or a secure vault.
- Use TLS 1.2+ (prefer 1.3) for all network communication; never disable
  certificate validation. Never bind services to 0.0.0.0.
- Use minimal, trusted base images (Red Hat registry) for any containers.
- Run containers as a non-root user.
- Validate all user inputs; use parameterized queries; encode outputs.
- Never log sensitive data (passwords, tokens, PII). Use structured logging.
- Return generic error messages to clients; log details server-side only.
- Hash passwords with a strong KDF (e.g., PBKDF2/scrypt/argon2); never store
  reversed or plaintext.
- Scan dependencies for vulnerabilities before use; use lock files.

---

## Testing Requirements

- All new logic must have unit tests (`pytest`).
- Adversarial/red-team test cases are required for security-sensitive code.
- Tests must run cleanly before any change is considered complete:
  `pytest` exits 0.
- Coverage of edge cases: empty input, None, non-string types, malformed data.
