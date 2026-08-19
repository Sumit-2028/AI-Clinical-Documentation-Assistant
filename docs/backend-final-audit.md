# Final Backend Audit

Audit date: 2026-08-18

Scope: the backend under `clinical-memory-system/`, including the gateway,
Steps 1–4, shared contracts, database models and migrations, AI adapters,
Docker configuration, security controls, and automated tests.

> Historical note: this audit describes the pre-patient-identity and
> pre-durable-pipeline state. The authoritative current status is
> [docs/final-system-status.md](final-system-status.md); statements below about
> UUID public IDs, in-memory gateway defaults, missing assignments, and an
> empty aggregate OpenAPI file are retained as historical findings.

This audit records only behavior that was inspected or tested. It does not
add implementation features.

## Executive summary

The deterministic in-process pipeline is implemented and its available unit,
contract, integration, and end-to-end tests pass when the required test
environment variables are supplied. The generated gateway OpenAPI contains
all Step 1–4 routes and the authentication routes.

The backend is not yet production-ready as a durable multi-user clinical
system. The most important findings are:

1. The gateway composition uses in-memory repositories/stores by default.
   Durable SQLAlchemy adapters exist but are not wired into the gateway
   service graph, so pipeline state is lost on restart and is not shared
   across replicas.
2. The first Alembic migration cannot generate offline SQL because it calls
   SQLAlchemy inspection from `ensure_users_timestamps()` while using an
   offline mock connection.
3. `contracts/openapi/gateway.yaml` is empty. Authentication and health are
   implemented but have no checked-in gateway OpenAPI contract.
4. Patient-ID filtering exists, but the contracts contain no user-to-patient
   assignment model. Request-body `physician_id`/`reviewer_id` values are also
   not bound to the authenticated JWT subject.
5. A clean `pytest` invocation fails during collection when no environment
   file or shell variables are present. The full suite passes after supplying
   the required test database URL and JWT secret.

## Implementation status

| Area | Status | Audit result |
| --- | --- | --- |
| Project structure | Partial | Steps 1–4, shared contracts, database, adapters, tests, Docker, and docs exist. Hyphenated service directories have underscore import aliases; several scaffold directories and `database/init.sql` remain empty. |
| API contracts | Partial | Step 1–4 contracts are implemented. Authentication is implemented from the existing login contract but is absent from the checked-in gateway OpenAPI file. |
| OpenAPI | Partial | All 17 paths in the Step 1–4 YAML files are present in generated gateway OpenAPI. `gateway.yaml` is empty; several component schemas in the step YAML files are intentionally only `type: object` placeholders. |
| Pydantic schemas | Pass for tested flow | Shared models are strict (`extra="forbid"`) and API tests validate the Step 1–4 response contracts. |
| Database models | Partial | User, patient, encounter, document, processing, extraction, event, memory, conflict, generated-document, and audit-log models exist with PostgreSQL UUID/JSONB types. They are not the default runtime stores. |
| Alembic | Partial/Fail | One foundation revision and a valid migration head exist. Offline SQL generation fails in `ensure_users_timestamps()`; online migration status was not verified against a clean PostgreSQL instance. |
| Authentication | Pass in tested gateway flow | Login, refresh, `/auth/me`, inactive-user rejection, bcrypt hashing, and invalid-credential handling are covered. |
| JWT | Pass in tested flow | HMAC algorithm allowlist, expiration, `sub`, `type`, `iat`, `jti`, access/refresh separation, and refresh replay protection are implemented. Replay state is process-local. |
| RBAC | Partial | Gateway pipeline routes use role permissions. Direct service apps are intentionally unauthenticated and must not be exposed. Patient assignment and actor-subject binding are not implemented in the current contracts. |
| Step 1 | Pass in deterministic tests | Typed, handwritten, multilingual, confidence gating, human verification, audit abstraction, and upload validation are implemented. Default repository/audit logger are in-memory. |
| Step 2 | Pass in deterministic tests | Preprocessing, abbreviations, terminology, NER, assertion, temporal context, contextualization, validation, and API routes are implemented. Default repository is in-memory. |
| Step 3 | Pass in deterministic tests | Memory Write Gate, trust tiers, provenance, concept threads, conflicts, review, retrieval, and patient filtering are implemented. Default store is in-memory. |
| Step 4 | Pass in deterministic tests | SOAP/discharge draft generation, provenance, validation, review actions, and Step 3 handoff are implemented. Default repository is in-memory. |
| Memory Write Gate | Pass in tested gateway flow | Gateway Step 4 finalization uses the in-process Step 3 service and its single write gate. A separately configured HTTP handoff does not add service-to-service authentication. |
| Provenance | Pass for tested contracts | Step 1, ClinicalEvent, memory, and generated-document provenance fields are preserved in deterministic tests. Durable audit/review persistence is incomplete. |
| Conflict detection | Pass in deterministic tests | Contradictions are retained and unresolved conflicts remain unverified during retrieval. Durable conflict-resolution audit history is incomplete. |
| Retrieval | Pass in deterministic tests | Deterministic lexical/basic-vector abstraction, relevance scoring, patient filtering, trust filtering, conflict filtering, and provenance preservation are covered. Default retrieval is in-memory. |
| Documentation/review | Pass in deterministic tests | Documents remain drafts until physician action; accept/edit/reject-regenerate paths are covered. Physician identity is currently supplied by request data rather than derived from the JWT subject. |
| AI adapters | Partial | Provider-neutral OCR, VLM, translation, BioClinicalBERT, Gemini, and LLM boundaries exist with timeout/retry/error handling. Production providers were not called; deterministic mocks are the only tested runtime mode. |
| Tests | Partial | 90 tests pass with environment variables. Clean `pytest` collection is not self-contained. Ruff and Pyflakes were unavailable, so unused-code/dependency analysis is not conclusive. |
| Docker | Partial | `docker compose config` passes with required secrets. PostgreSQL and gateway definitions exist, but compose does not run migrations or seed a user automatically. No container runtime test was performed. |
| Security | Partial/pass for implemented controls | JWT/RBAC, redacted errors/logs, CORS defaults, rate limits, upload limits, prompt boundaries, and generated-claim validation are present. Process-local limits, missing patient assignment, MIME spoofing risk, and direct-service exposure remain deployment concerns. |

## Endpoint audit

The generated gateway OpenAPI was inspected using `create_app().openapi()`.
The 17 paths from the Step 1–4 OpenAPI files were all present. The generated
request and response models matched the Pydantic contracts. Multipart Step 1
requests are generated by FastAPI with an implementation-specific component
name and `application/octet-stream`; the checked-in contract uses a named
`TypedDocumentRequest` and `format: binary`. The field shape is equivalent,
but the generated and checked-in schema representations are not textually
identical.

| Method | Endpoint | Implementation | Checked-in OpenAPI | Tests |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | Implemented in gateway auth router | Missing because `gateway.yaml` is empty | Pass |
| POST | `/api/v1/auth/refresh` | Implemented in gateway auth router | Missing because `gateway.yaml` is empty | Pass |
| GET | `/api/v1/auth/me` | Implemented in gateway auth router | Missing because `gateway.yaml` is empty | Pass |
| POST | `/api/v1/step1/documents/typed` | Implemented | Present in `step1-input.yaml` | Pass |
| POST | `/api/v1/step1/documents/handwritten` | Implemented | Present in `step1-input.yaml` | Pass |
| POST | `/api/v1/step1/documents/multilingual` | Implemented | Present in `step1-input.yaml` | Pass |
| GET | `/api/v1/step1/documents/{document_id}` | Implemented | Present in `step1-input.yaml` | Pass |
| POST | `/api/v1/step1/documents/{document_id}/human-verify` | Implemented | Present in `step1-input.yaml` | Pass |
| POST | `/api/v1/step2/process` | Implemented | Present in `step2-nlp.yaml` | Pass |
| GET | `/api/v1/step2/process/{document_id}` | Implemented | Present in `step2-nlp.yaml` | Pass |
| POST | `/api/v1/step3/memory/events` | Implemented through Memory Write Gate | Present in `step3-memory.yaml` | Pass |
| GET | `/api/v1/step3/memory/{patient_id}/events` | Implemented | Present in `step3-memory.yaml` | Pass |
| GET | `/api/v1/step3/memory/{patient_id}/current-state` | Implemented | Present in `step3-memory.yaml` | Pass |
| POST | `/api/v1/step3/memory/retrieve` | Implemented | Present in `step3-memory.yaml` | Pass |
| GET | `/api/v1/step3/conflicts` | Implemented | Present in `step3-memory.yaml` | Pass |
| POST | `/api/v1/step3/conflicts/{conflict_id}/resolve` | Implemented | Present in `step3-memory.yaml` | Pass |
| POST | `/api/v1/step3/tier3/{event_id}/approve` | Implemented | Present in `step3-memory.yaml` | Pass |
| POST | `/api/v1/step3/tier3/{event_id}/reject` | Implemented | Present in `step3-memory.yaml` | Pass |
| POST | `/api/v1/step4/documents/generate` | Implemented | Present in `step4-docgen.yaml` | Pass |
| POST | `/api/v1/step4/documents/{document_id}/finalize` | Implemented | Present in `step4-docgen.yaml` | Pass |
| GET | `/health` | Implemented gateway health endpoint | Not present in step contracts | Pass |

FastAPI’s framework endpoints (`/docs`, `/redoc`, and `/openapi.json`) are
also exposed by default. No undocumented business endpoint beyond the
expected authentication and health endpoints was found. Standalone Step 1–4
apps expose their own health and documentation endpoints and are not an
authentication boundary.

## Database and migration audit

The metadata inspection found these tables:

`users`, `patients`, `encounters`, `documents`, `processing_jobs`,
`extraction_results`, `clinical_events`, `patient_memory`, `conflicts`,
`generated_documents`, and `audit_logs`.

Foreign keys and indexes are present for the principal patient, encounter,
document, event, memory, conflict, and actor-user relationships. The main
structural gaps are:

- `patient_memory.concept_thread_id` has no foreign key because there is no
  durable concept-thread table.
- There is no user-to-patient assignment or encounter-access table.
- Tier-review and conflict-resolution history are not represented by dedicated
  durable tables. Some information is retained in JSON payloads or in-memory
  records.
- The default integrated gateway graph uses `InMemoryDocumentRepository`,
  `InMemoryClinicalEventRepository`, `InMemoryMemoryStore`, and in-memory Step
  1 audit/document state. SQLAlchemy adapters are available but not selected
  by `build_integrated_services()`.
- The database schema uses individual indexes on common foreign keys, but no
  composite/status indexes were verified for the longitudinal retrieval and
  conflict-list query patterns.
- Patient deletion cascades to clinical records, memory, conflicts, and
  generated documents. This is explicit PostgreSQL behavior but requires
  operational deletion approval, backups, and retention policy.

Migration commands produced the following evidence:

- `alembic heads`: passed; head is `20260817_0001`.
- `alembic history`: passed; one foundation revision is present.
- `alembic upgrade head --sql`: failed. The migration calls
  `sa.inspect(op.get_bind())` in `ensure_users_timestamps()`, which is not
  available on Alembic’s offline `MockConnection`.
- `alembic check`: not verified because the configured local PostgreSQL
  connection rejected the supplied audit credentials. No clean database
  migration was claimed.

## AI integration audit

The following replaceable boundaries were found:

- Step 1: OCR, VLM, and translation adapters with deterministic mocks and
  provider-neutral HTTP implementations.
- Step 2: deterministic NER/contextualization plus injectable
  BioClinicalBERT and Gemini adapter boundaries.
- Step 4: deterministic document generator plus an OpenAI-compatible,
  provider-neutral production LLM boundary.
- Shared transport: bounded timeouts, retries, provider error normalization,
  and metadata-only logging.

No external provider was called during this audit. The normal test suite uses
deterministic mock behavior. Production NLP additionally requires the optional
model/runtime dependencies and model assets to be installed and configured;
that path was not executed.

## Security audit

Verified controls include:

- bcrypt password hashing and bounded password input.
- Signed, expiring JWTs with distinct access/refresh types and required claims.
- Inactive-user rejection and gateway RBAC.
- Refresh-token rotation with a process-local replay guard.
- Explicit-origin CORS with wildcard rejection.
- Process-local request limits with stricter authentication limits.
- Upload size, MIME allowlist, extension consistency, and path-traversal
  checks.
- Redacted request paths, validation errors, provider errors, and audit
  metadata.
- No passwords, tokens, API keys, request bodies, or full medical documents
  are intentionally logged by the hardened gateway paths.
- Prompt data delimiting, physician-instruction filtering, deterministic
  generated-claim validation, provenance, and draft-until-review behavior.
- SQLAlchemy expression queries and rollback handling in durable repository
  adapters.

Residual security concerns:

- Patient filtering is based on the requested patient ID. No current contract
  binds that ID to the authenticated user’s patient assignment.
- Review actor IDs are accepted from request bodies and are not checked
  against the JWT subject.
- Direct service applications have no authentication and must remain private.
- Refresh replay and rate-limit state are process-local, so multi-replica
  deployment requires shared state or a trusted edge control.
- Upload content is not magic-byte inspected; a caller can spoof a permitted
  MIME header unless an upstream scanner validates the content.
- Client-supplied `X-Request-ID` is logged as request metadata without a
  documented format/length policy.
- Prompt-injection rejection is heuristic and cannot replace physician review
  or provider isolation.

## Test status

Commands run from `clinical-memory-system/`:

| Command | Result |
| --- | --- |
| `pytest services/input-processing/tests/test_step1_service.py services/clinical-nlp/tests/test_nlp_pipeline.py services/memory-engine/tests/test_memory_engine.py services/memory-engine/tests/test_retrieval.py services/doc-generation/tests/test_doc_generation.py -q` | 47 passed |
| `pytest -k contract -q` | 5 passed |
| `pytest services/gateway/tests services/input-processing/tests/test_step1_api.py services/clinical-nlp/tests/test_nlp_api.py services/memory-engine/tests/test_memory_api.py services/doc-generation/tests/test_doc_api.py -q` | 26 passed |
| `pytest tests/test_phase9_end_to_end.py -q` | Collection failed without required environment variables |
| Test above with `DATABASE_URL`, `JWT_SECRET_KEY`, and `JWT_ALGORITHM` supplied | 4 passed |
| `pytest -q` | Collection failed without required environment variables |
| `pytest -q` with the required test environment supplied | 90 passed, 1 existing Starlette/httpx deprecation warning |
| `python -m compileall -q contracts database services tests` | Passed |
| `ruff check ...` | Not run: Ruff is not installed |
| `pyflakes ...` | Not run: Pyflakes is not installed |

The clean-test failure occurs because root-level E2E modules import gateway
settings during collection before the service-local test configuration can
set the required variables. This is a test-environment reproducibility issue,
not a passing clean-suite result.

## Docker status

`docker compose config` passed when `POSTGRES_PASSWORD` and `JWT_SECRET_KEY`
were supplied. `docker compose ps` without those variables fails secure
interpolation as expected. No containers were started during this audit, so
PostgreSQL connectivity, migration execution inside Docker, gateway startup,
and runtime health were not claimed.

The compose file starts PostgreSQL and builds the gateway, but it does not
automatically execute Alembic migrations or create the development physician.
Run those explicitly after the database is healthy.

## Required environment variables

Required for gateway startup:

- `DATABASE_URL` — PostgreSQL SQLAlchemy URL.
- `JWT_SECRET_KEY` — unique non-placeholder signing secret.

Required for the development seed command:

- `SEED_TEST_USER_PASSWORD`.

Required by Docker interpolation:

- `POSTGRES_PASSWORD`.

Optional gateway settings documented in `.env.example` include
`JWT_ALGORITHM`, token expirations, CORS origins/credentials, rate limits,
upload limits, and PostgreSQL connection components.

AI settings are optional in mock mode. Production configuration names include
`STEP1_AI_MODE`, `STEP1_AI_PROVIDER`, `STEP1_AI_API_KEY`,
`STEP1_AI_ENDPOINT`, `STEP2_NLP_MODE`, `GEMINI_API_KEY`, `GEMINI_MODEL`,
`GEMINI_API_URL`, `GEMINI_ENDPOINT`, `BIOCLINICALBERT_MODEL_NAME`,
`BIOCLINICALBERT_MODEL_PATH`, `STEP4_LLM_MODE`, `STEP4_LLM_API_KEY`,
`STEP4_LLM_ENDPOINT`, `STEP4_LLM_MODEL`, and the AI timeout/retry settings.

## Local commands

From `clinical-memory-system/`:

```powershell
Copy-Item .env.example .env
# Edit .env and replace every secret placeholder.
docker compose up -d postgres
alembic upgrade head
$env:SEED_TEST_USER_PASSWORD = "use-a-local-only-password"
python -m services.gateway.app.auth.seed
uvicorn services.gateway.app.main:app --host 0.0.0.0 --port 8000
```

For deterministic tests, set at least `DATABASE_URL`, `JWT_SECRET_KEY`, and
`JWT_ALGORITHM` in the shell before running `pytest`. Tests do not require
external AI keys. The migration command above requires a reachable PostgreSQL
instance with credentials matching `DATABASE_URL`; the offline migration
variant is currently known to fail as described above.

## Final recommended next steps

1. Fix the Alembic offline migration path and run `alembic upgrade head` and
   `alembic check` against a clean PostgreSQL database.
2. Wire durable repositories, audit logging, tier-review history, conflict
   resolution, and concept threads into the gateway service graph with
   transaction boundaries for batch writes.
3. Add the missing gateway authentication/health OpenAPI contract and replace
   placeholder component schemas with the exact shared Pydantic schemas.
4. Add authenticated user-to-patient/encounter authorization and derive review
   actor identity from the authenticated principal while preserving the
   public request shapes.
5. Make root test configuration self-contained and add an actual PostgreSQL
   integration job; add Ruff/Pyflakes or an equivalent static-analysis step.
6. Add content sniffing/antivirus policy for uploads and shared replay/rate
   limiting before multi-replica deployment.
7. Exercise each configured production AI adapter with provider-sandbox tests,
   without placing real medical data or credentials in CI.

## Audit conclusion

The backend is functionally covered for deterministic development and CI:
the requested pipeline tests pass with explicit environment configuration.
The evidence does not support claiming durable persistence, clean migration
execution, production AI operation, complete gateway OpenAPI documentation, or
full user-to-patient authorization yet.
