# AI Clinical Documentation Assistant

This repository contains the authenticated clinical documentation pipeline:

```text
Gateway authentication/RBAC
  -> Step 1 input processing
  -> Step 2 clinical NLP
  -> Step 3 patient memory and retrieval
  -> Step 4 draft documentation and physician review
  -> Step 3 Memory Write Gate
```

## Local development

1. Copy `.env.example` to a local `.env` and replace all secret placeholders.
2. Start PostgreSQL with `docker compose up postgres` or use an existing PostgreSQL instance.
3. Run migrations with `alembic upgrade head`.
4. Run the test suite from `clinical-memory-system/`:

```text
pytest
```

Deterministic AI adapters are the default, so tests do not need external API keys. The gateway mounts the Step 1–4 routes behind Bearer JWT authentication and RBAC. Standalone service apps are intended for isolated development tests and must not be exposed directly to an untrusted network.

Security controls and deployment limitations are documented in [docs/security.md](docs/security.md).

## Frontend integration

The React/Vite frontend uses the FastAPI gateway through centralized HTTP
adapters. Configure `frontend/.env.local` from `frontend/.env.example`, set
`CORS_ALLOWED_ORIGINS=http://localhost:5173` in the backend environment, then
run:

```text
cd frontend
npm install
npm run dev
```

Integration mapping, request/response contracts, startup commands, verified
tests, and current backend limitations are documented in
[docs/frontend-backend-integration.md](docs/frontend-backend-integration.md).
The pre-change comparison is preserved in
[docs/frontend-backend-integration-audit.md](docs/frontend-backend-integration-audit.md).
