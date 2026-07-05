# KPanel2 — AI Agent Instructions

This document is the source of truth for how AI agents should work in this repository. Follow it on every task unless the user explicitly overrides a specific point.

## What this repo is

KPanel2 is a monorepo for Raspberry Pi touchscreen panels:

| Package | Stack | Purpose |
|---------|-------|---------|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy, MariaDB | OIDC auth, accounts, device claiming, config API |
| `frontend/` | Angular 19, Karma/Jasmine | User portal for sign-in and panel management |
| `client-system/` | Python, systemd | Pi runtime: connectivity, registration, kiosk launch |
| `docs/` | Markdown | Architecture and distribution decisions |
| `infra/` | Caddy | External TLS reverse-proxy examples |

See `README.md` and `docs/architecture.md` for domain details and API contracts.

---

## Non-negotiable engineering principles

### 1. Test-Driven Development (TDD)

**Write tests first, then implementation.** Do not ship production code without tests.

Workflow for every feature or bug fix:

1. **Red** — Write a failing test that describes the desired behavior.
2. **Green** — Write the smallest implementation that passes.
3. **Refactor** — Clean up while keeping tests green.

Rules:

- Never merge logic-only changes without corresponding tests.
- Prefer unit tests for pure logic; use integration/route tests for HTTP and DB boundaries.
- Use `@pytest.mark.parametrize` for input normalization and edge-case matrices.
- Inject dependencies (DB sessions, API clients, subprocess runners) so behavior is testable without real I/O.
- Reuse `backend/tests/factories.py` and `backend/tests/conftest.py` fixtures instead of duplicating setup.

### 2. DRY (Don't Repeat Yourself)

- Extract shared setup into factories, fixtures, and small helpers — not copy-pasted blocks.
- One canonical place for constants (e.g. `SUPPORTED_DEVICE_ACTIONS`, env var names).
- If you write the same assertion or seed pattern twice, refactor it.
- Do **not** over-abstract: a one-off helper used once is worse than inline code.

### 3. SOLID

Apply these consistently:

| Principle | In this repo |
|-----------|--------------|
| **S** — Single Responsibility | Routes handle HTTP; services hold business logic; models hold persistence shape. |
| **O** — Open/Closed | Extend via new functions/modules, not by editing unrelated code paths. |
| **L** — Liskov Substitution | Test doubles (e.g. `FakeApi`) must honor the same contract as real implementations. |
| **I** — Interface Segregation | Pass only what a function needs (`runner` callback, not the whole client object). |
| **D** — Dependency Inversion | High-level orchestration depends on abstractions injected at call sites or via FastAPI `Depends`. |

**Backend layering pattern** (follow existing code):

```
routes (account_routes.py, main.py)  →  service modules (device_actions.py, user_service.py)  →  models (models.py)
```

Keep normalization, validation, and domain rules in service modules — not in route handlers.

---

## Test coverage requirements

| Target | Requirement |
|--------|-------------|
| **Minimum** | **90%** line coverage on all **new or changed** code |
| **Preferred** | **100%** coverage on new modules, pure functions, and service logic |
| **PR diff** | Changed lines must meet the 90% floor; aim for 100% |

### How to verify coverage

**Backend** (from `backend/`):

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
# Review term-missing output; JSON report at coverage/coverage.json
```

**Frontend** (from `frontend/`):

```bash
npm ci
npm test -- --no-watch --browsers=ChromeHeadless --code-coverage
# Report under coverage/kpanel-frontend/
```

**Client system** (from `client-system/`):

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

CI currently reports at an 80% threshold for visibility; **agent work must hold itself to 90% minimum / 100% preferred** regardless of CI warnings.

Before finishing any task, run the relevant test suite and confirm coverage on touched files. If coverage is below 90%, add tests — do not lower the bar.

---

## Package-specific conventions

### Backend (`backend/`)

- App code lives in `backend/app/`; tests in `backend/tests/`.
- Use in-memory SQLite via `conftest.py` for tests — never hit a real MariaDB in unit tests.
- Seed data with `tests/factories.py` (`seed_user`, `seed_device`).
- Use `TestClient` + `client` / `db_session` fixtures for route tests.
- Raise `HTTPException` from service layer for domain errors; let routes stay thin.
- Environment variables are prefixed `KPANEL_`; set test values in `conftest.py`.

### Frontend (`frontend/`)

- Angular feature modules under `src/app/features/`; shared services under `src/app/core/services/`.
- Every new service, component with logic, and utility needs a `.spec.ts` beside it.
- Mock HTTP and auth dependencies; do not call real APIs in unit tests.
- Match existing Jasmine patterns in `auth-flow.service.spec.ts` and `login.component.spec.ts`.

### Client system (`client-system/`)

- Package code in `kpanel_client/`; tests in `client-system/tests/`.
- Inject side effects (`runner`, API client) for testability — see `pending_actions.py` + `test_pending_actions.py`.
- Hardware-specific paths (nmcli, systemd, Tkinter) stay behind injectable boundaries.

---

## Scope and change discipline

- **Minimize diff scope** — only change what the task requires.
- **Match existing style** — naming, imports, typing, error handling.
- **No drive-by refactors** unless required for the task or SOLID violations block testing.
- **No new markdown/docs** unless the user asks.
- **No commits or PRs** unless the user explicitly requests them.
- **Security** — never commit secrets; keep `KPANEL_DEV_AUTH_ENABLED=false` outside local dev; do not weaken device-token or OIDC checks.

---

## Local development quick reference

```bash
# Full stack
docker compose up --build

# URLs
# Frontend: http://localhost:8080
# Backend:  http://localhost:8000/docs
```

---

## Checklist before marking work complete

- [ ] Tests written **before** or alongside implementation (TDD)
- [ ] All tests pass locally
- [ ] New/changed code ≥ 90% covered (100% preferred)
- [ ] No duplicated logic that belongs in a shared helper/factory
- [ ] Business logic in service layer, not routes or components
- [ ] Dependencies injected for testability
- [ ] No unrelated files changed
