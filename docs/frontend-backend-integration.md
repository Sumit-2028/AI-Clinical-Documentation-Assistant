# Frontend–Backend Integration

Audit and implementation date: 2026-08-18.

This document describes the current contract-first integration between the
React/Vite frontend and the FastAPI gateway. Production frontend adapters use
HTTP; deterministic fixtures are used only when `MODE === "test"`. Backend
schemas in `contracts/schemas/` and mounted gateway routers are authoritative.

## 1. Final architecture

```text
React + Vite
  -> frontend/src/api/client.ts (JSON/multipart, bearer auth, refresh, errors)
  -> FastAPI gateway /api/v1
  -> authentication/RBAC dependency
  -> Step 1 -> Step 2 -> Step 3 retrieval -> Step 4 review
  -> Step 3 Memory Write Gate
  -> configured persistence/provider adapters
```

The frontend does not call Gemini or another AI provider. Provider keys and
provider calls remain backend-only. Pages call hooks, hooks call API adapters,
and adapters call the shared HTTP client.

## 2. Frontend API mapping

| Frontend operation | Adapter | Backend route | Status |
| --- | --- | --- | --- |
| Login | `src/api/auth.ts` | `POST /api/v1/auth/login` | Connected |
| Restore physician | `src/api/auth.ts` | `GET /api/v1/auth/me` | Connected |
| Refresh session | `src/api/auth.ts` | `POST /api/v1/auth/refresh` | Connected |
| Typed upload | `src/api/step1.ts` | `POST /api/v1/step1/documents/typed` | Connected; multipart bytes |
| Handwritten upload | `src/api/step1.ts` | `POST /api/v1/step1/documents/handwritten` | Connected; multipart bytes |
| Multilingual input | `src/api/step1.ts` | `POST /api/v1/step1/documents/multilingual` | Connected; JSON text |
| Step 1 read | `src/api/step1.ts` | `GET /api/v1/step1/documents/{document_id}` | Connected |
| Human verification | `src/api/step1.ts` | `POST /api/v1/step1/documents/{document_id}/human-verify` | Connected |
| Step 2 process/read | `src/api/pipeline.ts` | `POST/GET /api/v1/step2/process...` | Connected |
| Memory write | `src/api/pipeline.ts` | `POST /api/v1/step3/memory/events` | Connected; contract-shaped |
| Memory events/state | `src/api/pipeline.ts` | `GET /api/v1/step3/memory/{patient_id}/...` | Connected |
| Retrieval | `src/api/pipeline.ts` | `POST /api/v1/step3/memory/retrieve` | Connected |
| Conflicts | `src/api/pipeline.ts` | `GET/POST /api/v1/step3/conflicts...` | Connected |
| Tier 3 review | `src/api/pipeline.ts` | `POST /api/v1/step3/tier3/{event_id}/...` | Connected |
| Document generation | `src/api/pipeline.ts` | `POST /api/v1/step4/documents/generate` | Connected |
| Document finalization | `src/api/pipeline.ts` | `POST /api/v1/step4/documents/{document_id}/finalize` | Connected |

The frontend deliberately does not invent a review-queue list, audit-history
list, document-draft GET, document-history list, or separate job-status route;
none is in the current gateway contract. Those screens use loaded responses or
show an empty/availability state.

## 3. Backend endpoint and schema mapping

All routes below are mounted by `services/gateway/app/main.py`. Pipeline routes
require a Bearer token and the gateway pipeline-access dependency.

| Method and path | Request | Response |
| --- | --- | --- |
| `POST /api/v1/auth/login` | `LoginRequest` | `TokenResponse` |
| `POST /api/v1/auth/refresh` | `RefreshTokenRequest` | `TokenResponse` |
| `GET /api/v1/auth/me` | Bearer token | `UserResponse` |
| `POST /api/v1/step1/documents/typed` | multipart `patient_id`, `encounter_id`, `file` | `Step1Output` |
| `POST /api/v1/step1/documents/handwritten` | multipart `patient_id`, `encounter_id`, `file` | `Step1Output` |
| `POST /api/v1/step1/documents/multilingual` | `MultilingualDocumentRequest` | `Step1Output` |
| `GET /api/v1/step1/documents/{document_id}` | UUID path | `Step1Output` |
| `POST /api/v1/step1/documents/{document_id}/human-verify` | `HumanVerificationRequest` | `Step1Output` |
| `POST /api/v1/step2/process` | `Step2ProcessRequest` | `ClinicalEventBatch` |
| `GET /api/v1/step2/process/{document_id}` | UUID path | `ClinicalEventBatch` |
| `POST /api/v1/step3/memory/events` | `MemoryWriteRequest` | `MemoryWriteResponse` |
| `GET /api/v1/step3/memory/{patient_id}/events` | UUID path | `MemoryEventHistory` |
| `GET /api/v1/step3/memory/{patient_id}/current-state` | UUID path | `CurrentPatientState` |
| `POST /api/v1/step3/memory/retrieve` | `MemoryRetrieveRequest` | `RetrievedContext` |
| `GET /api/v1/step3/conflicts` | optional `patient_id`, `status`, `risk_level` | `ConflictRecord[]` |
| `POST /api/v1/step3/conflicts/{conflict_id}/resolve` | `ResolveConflictRequest` | `ResolveConflictResponse` |
| `POST /api/v1/step3/tier3/{event_id}/approve` | `TierReviewRequest` | `TierReviewResponse` |
| `POST /api/v1/step3/tier3/{event_id}/reject` | `TierReviewRequest` | `TierReviewResponse` |
| `POST /api/v1/step4/documents/generate` | `GenerateDocumentRequest` | `GeneratedDocument` |
| `POST /api/v1/step4/documents/{document_id}/finalize` | `FinalizeDocumentRequest` | `DocumentReviewResponse` |

The frontend preserves `patient_id`, `encounter_id`, `document_id`, `event_id`,
and `conflict_id`. Presentation normalization supplies safe defaults for
fields absent from the smaller backend retrieval item; it does not create
clinical facts.

## 4. Authentication flow

1. The login page posts credentials to `/auth/login`.
2. The access token is held in HTTP-client memory. The refresh token is kept in
   `sessionStorage` for the browser session; neither is rendered or logged.
3. Protected requests receive `Authorization: Bearer <access_token>`.
4. A single-flight refresh runs after a 401 and retries the original request
   once.
5. Failed refresh clears session state and routes to `/login`.
6. `/auth/me` restores the current physician after reload.

The backend remains authoritative for expiration, token type, inactive users,
roles, and permissions. Production requests do not use a fixture physician ID.

## 5. File upload and job lifecycle

Typed and handwritten uploads use `FormData` with the actual selected `File`,
`patient_id`, and `encounter_id`. Multilingual input uses JSON with
`patient_id`, `encounter_id`, `text_input`, and `source_language`.

The gateway currently returns `Step1Output` directly and reports statuses such
as `complete`, `failed`, or `pending_human_verification`. There is no separate
`job_id` or polling route in the authoritative gateway contract, so the
frontend does not fabricate job identifiers or poll an undocumented endpoint.

## 6. Step 1 → Step 2 → Step 3

After Step 1, the real `document_id`, `patient_id`, and `encounter_id` are kept
in workflow state. Step 2 receives the complete `Step1Output` and returns a
`ClinicalEventBatch`. Human verification posts the exact `field_id`,
`verified_text`, `reviewer_id`, and `approved` fields.

Clinical events are submitted to memory only through `MemoryWriteRequest` and
the Step 3 write gate. The adapter strips presentation-only fields before
serialization while preserving event provenance, text spans, modality,
language, confidence, assertion, status, and validation fields.

Retrieval requests contain the real patient and encounter IDs. The response
remains split into `verified_context`, `unverified_information`, and
`conflicts`.

## 7. Step 3 → Step 4

Documentation generation receives the real consultation events and serialized
`RetrievedContext`. The UI keeps verified, unverified, and conflicting
information separate and displays provenance and review flags. Supported types
are `soap_note` and `discharge_summary`.

Generated documents remain drafts until explicit physician action. Accept and
edit actions call finalization; reject/regenerate records the action and starts
a new draft generation request.

## 8. Step 4 → Memory Write Gate

In the current integrated gateway, Step 4 finalization invokes its injected
`MemoryWriteClient`, which routes the approved payload through the Step 3
Memory Write Gate before returning `memory_write_payload`. The production
adapter marks the response as `memory_write_committed`, and the UI does not
submit it a second time. This prevents duplicate append-only events.

Fixture-mode tests retain an explicit Step 3 write call to exercise the public
adapter contract. If the backend changes to return an uncommitted payload, it
must still be sent only to `POST /api/v1/step3/memory/events`; the frontend
never writes directly to PostgreSQL.

## 9. Environment variables

Frontend (`frontend/.env.example`):

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

This is a public endpoint value, not a secret. Do not define
`VITE_GEMINI_API_KEY`.

Backend values are documented in the root `.env.example`. Minimum local values:

```text
APP_ENV=development
DATABASE_URL=postgresql+psycopg2://...
JWT_SECRET_KEY=<local-secret>
JWT_ALGORITHM=HS256
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

`GEMINI_API_KEY`, `STEP1_AI_API_KEY`, and `STEP4_LLM_API_KEY` belong only in
the backend environment and are optional for deterministic mock tests.

## 10. Local startup commands

From `clinical-memory-system/` in PowerShell:

```powershell
Copy-Item .env.example .env
# Edit .env with a local JWT secret and PostgreSQL password.
docker compose up postgres
alembic upgrade head
python -m uvicorn services.gateway.app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second shell:

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Set `CORS_ALLOWED_ORIGINS=http://localhost:5173` for Vite development. Use
HTTPS and an explicit origin list outside local development.

## 11. Testing commands and verified results

Frontend:

```powershell
Set-Location frontend
npm run lint
npm test -- --run
npm run build
```

Backend:

```powershell
Set-Location ..
$env:DATABASE_URL='postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_memory_test'
$env:JWT_SECRET_KEY='test-secret-key-change-me'
$env:JWT_ALGORITHM='HS256'
$env:APP_ENV='test'
$env:LOG_LEVEL='INFO'
pytest -q
```

Verified on 2026-08-18: 90 backend tests passed, 41 frontend tests passed,
the frontend type check passed, and the Vite production build passed. `npm
install` passed; npm reported two moderate audit vulnerabilities and no
automatic audit fix was applied.

## 12. Known limitations

- The default `build_integrated_services()` path uses in-memory repositories.
  PostgreSQL/SQLAlchemy adapters exist, but durable gateway persistence was not
  proven by this integration run.
- There is no user-to-patient assignment/access table. Patient IDs are filtered
  by service operations, but complete physician-to-patient authorization and a
  cross-patient isolation proof are not established.
- The gateway OpenAPI contract file is empty even though generated FastAPI
  routes exist; this is a contract publication gap.
- There is no audit list/history, document draft GET, document history, review
  queue, or separate job-status endpoint. The frontend does not invent routes
  for them.
- External OCR, VLM, NLP, and LLM provider calls were not exercised.
- Offline Alembic SQL generation encounters the existing timestamp inspection
  behavior; migrations should be run and verified against real PostgreSQL.
- Docker configuration was reviewed in the backend audit, but full container
  startup and a real PostgreSQL workflow were not executed in this frontend
  integration run.

## 13. Production deployment requirements

- Wire the gateway to durable PostgreSQL repositories and run migrations in a
  controlled deployment step.
- Add explicit physician/patient/encounter authorization and bind reviewer IDs
  to the authenticated principal instead of trusting arbitrary body IDs.
- Publish and test a non-empty gateway OpenAPI contract matching Pydantic
  schemas.
- Configure backend-only provider secrets, timeouts, retries, and monitoring;
  keep deterministic mocks out of production mode.
- Serve the Vite bundle with BrowserRouter fallback for `/memory`,
  `/clinical-nlp`, and `/documentation/review`.
- Use HTTPS, explicit CORS origins, secure token policy, rate limits, secret
  rotation, audit retention, and logs that exclude medical content, tokens,
  passwords, and provider keys.
- Run a real PostgreSQL-backed workflow test covering login, upload, Step 1,
  Step 2, retrieval, document review, finalization, conflict handling, and the
  single Memory Write Gate commit.
