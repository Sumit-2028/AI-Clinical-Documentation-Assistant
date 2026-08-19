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


### Object storage for uploaded documents

Step 1 stores the original uploaded file before extraction runs. The default
`STEP1_STORAGE_MODE=mock` keeps objects in process memory, so the test suite and
a bare `uvicorn` need no storage service at all.

To exercise the real S3 code path locally, start MinIO and switch the mode:

```text
docker compose up -d minio minio-init
```

`minio-init` creates the bucket, which does not exist by default. The MinIO
console is at `http://localhost:9001`. Set `MINIO_ROOT_PASSWORD` in `.env`
first; compose refuses to start without it.

MinIO speaks the S3 API, so moving to AWS is configuration rather than code:
leave `S3_ENDPOINT_URL` empty, set `S3_FORCE_PATH_STYLE=false`, leave the access
key and secret blank so the instance role is used, and set `S3_SSE=aws:kms`.
The bucket itself should be created out of band with public access blocked,
default encryption, and versioning; the application is not granted
`CreateBucket`.

The gateway uses PostgreSQL-backed, request-scoped repositories by default
(`CLINICAL_PIPELINE_PERSISTENCE=true`). Deterministic AI adapters are forced
for tests, so CI does not need external API keys; production mode fails clearly
when its configured provider or model is unavailable. The gateway mounts the
Step 1–4 routes behind Bearer JWT authentication, RBAC, and patient assignment
checks. Standalone service apps are intended for isolated development tests
and must not be exposed directly to an untrusted network.

Typed PDF uploads are parsed with `pypdf` when available (with a constrained
valid-PDF text fallback for local smoke tests); uploaded PDF bytes are never
decoded as ordinary UTF-8 text. Gemini and other provider keys remain backend
only.

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

The current implementation and verification status are in
[docs/final-system-status.md](docs/final-system-status.md).
