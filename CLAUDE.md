# Sponda — Project Instructions

## Engineering Standards

- Always prefer the robust, production-grade approach. Never take shortcuts that reduce test coverage, skip CI checks, or weaken the safety net.
- If something is broken in CI (e.g. a missing dependency, a misconfigured environment), fix the root cause. Do not work around it by ignoring or skipping tests.
- When faced with a "quick fix vs proper fix" tradeoff, default to the proper fix unless explicitly told otherwise.

## Test-Driven Development (TDD)

This project follows strict TDD:

1. **Tests first.** Every new feature and every bug fix starts with a failing test.
2. **Run tests, confirm they fail.** Never skip this step.
3. **Implement the feature or fix.**
4. **Run tests, confirm they pass.**
5. **Maintain extremely good coverage.** Every API endpoint, every model method, every frontend component interaction should have tests.

Backend tests use pytest + pytest-django + factory-boy. Frontend tests use vitest. E2E tests use playwright.

## Clean Code

Follow clean code principles (Martin Fowler, Uncle Bob / Robert C. Martin):

- Functions should do one thing and do it well.
- Keep functions small and focused.
- Prefer composition over inheritance.
- Follow the Single Responsibility Principle at every level.
- No magic numbers — use named constants.
- Code should read like well-written prose.

## Naming Conventions

- Use **descriptive, human-readable** variable, function, and class names. Never abbreviate.
- When touching existing code, convert abbreviated names to full descriptive names (e.g., `d` → `quoteResult`, `t` → `ticker`, `c` → `company`).
- When touching code, evaluate whether a name is **legacy and too narrow** or **no longer reflects what it does**. If so, rename it — and make sure the application still works perfectly after the rename.
