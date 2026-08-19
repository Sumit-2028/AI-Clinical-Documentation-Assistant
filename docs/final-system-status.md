# Final System Status

Audit date: 2026-08-18

Scope: current repository state after the patient-identity, PostgreSQL
persistence, PDF extraction, NLP, AI-adapter, gateway-authorization, and
multi-clinician acceptance changes. Statuses below distinguish automated
verification from provider or deployment paths that were not exercised.

## 1. Frontend status

The existing React + Vite frontend was preserved. Functional integration
changes are limited to numeric patient-ID input validation, upload identifier
validation/new-consultation UUID handling, and upload error presentation. The
centralized HTTP/API adapter architecture remains in use; Gemini is not
exposed through Vite variables.

Verified:

- `npm run lint` passed.
- `npm test -- --run` passed: 10 files, 46 tests.
- `npm run build` passed.

The browser UI was not driven manually in this environment; backend workflow
acceptance was executed through FastAPI integration clients.

## 2. Authentication status

PostgreSQL-backed registration, bcrypt password hashing, login, `/auth/me`,
JWT access/refresh separation, expiration, inactive-user rejection, refresh
rotation/replay rejection, and logout-side frontend state handling are
implemented. Public registration is limited to the existing `physician` and
`patient` roles; privileged roles cannot be self-registered.

The real PostgreSQL registration/login/current-user path passed in the
integration suite.

## 3. Patient ID status

The internal patient primary key remains UUID-based. The clinician-facing
`patient_id` is now a backend-generated numeric 6–8 digit identifier stored in
`patients.public_patient_id`, with a PostgreSQL unique index. Allocation
checks for collisions and the database constraint is the final guard.

Migration `20260818_0004_public_patient_identifier` is applied and is the
current Alembic head. Existing rows were backfilled deterministically; new
rows use backend allocation. The identifier is not derived from a name/email
and is not regenerated on login or restart.

## 4. Patient search status

`GET /api/v1/patients/{patient_id}` accepts the numeric public ID and retains
legacy UUID compatibility. The existing frontend patient lookup now expects a
6–8 digit numeric value and does not generate IDs.

Patient lookup is server-authorized and was verified in PostgreSQL tests.

## 5. Authorization status

`patient_assignments` is a persistent many-clinician relationship. A
physician who creates a patient receives an active assignment; an admin can
assign any active physician. Gateway pipeline requests resolve public IDs to
internal UUIDs and check the authenticated user’s assignment before accessing
patient resources.

Cross-patient denial, actor binding from the JWT subject, and authorized
multi-clinician access are covered by tests. Direct standalone service apps
remain test/development entry points and must not be exposed as production
trust boundaries.

## 6. PDF extraction status

Typed PDF uploads are sent as multipart file bytes and no longer decoded as
ordinary UTF-8. `pypdf` is the production parser dependency; a constrained
valid-PDF text fallback supports simple local smoke documents. A real
synthetic PDF was uploaded through the gateway and its extracted text passed
into Step 2.

Original file bytes are currently processed in memory. `documents.storage_uri`
exists but no durable object-storage implementation is configured; retaining
original documents requires a deployment storage decision.

## 7. OCR/VLM status

Provider-neutral OCR, VLM, and translation interfaces exist with deterministic
mock adapters and production HTTP adapters, bounded timeout/retry behavior,
and failure signaling. Handwritten/multilingual unit coverage passes.

External OCR/VLM calls and a scanned-image production workflow were not run
because the current acceptance environment uses deterministic mock modes.

## 8. NLP status

The existing Step 2 pipeline is used: preprocessing, abbreviation expansion,
terminology normalization, NER, contextualization, assertion/temporal
handling, event construction, and validation. The undefined terminology
fallback and missing BioClinicalBERT adapter import were fixed.

The real Step 1 output was passed to Step 2 in the PostgreSQL acceptance
workflow. BioClinicalBERT is behind a replaceable adapter and fails clearly if
its optional runtime/model is unavailable; the production model path was not
executed locally.

## 9. ClinicalEvent status

The existing ClinicalEvent contract remains authoritative. Validation preserves
source document, text span, modality, language, confidence, assertion,
temporal, validation, and provenance fields. Durable Step 2 repository writes
are append-oriented and validated before persistence.

## 10. PostgreSQL status

PostgreSQL is the production runtime store. The gateway defaults to
request-scoped SQLAlchemy repositories for Step 1 documents/audits, Step 2
events, Step 3 memory/conflicts, and Step 4 generated documents when
`CLINICAL_PIPELINE_PERSISTENCE=true`.

Verified:

- `alembic upgrade head` passed.
- `alembic current` reported `20260818_0004 (head)`.
- `alembic check` reported no new upgrade operations.
- Registration, assignment, documents, events, memory, and multi-clinician
  retrieval were exercised against the configured local PostgreSQL instance.

## 11. Memory status

Step 3 memory is append-oriented, provenance-aware, trust-aware, and
conflict-aware. The gateway uses the durable memory store by default.
Historical events are not silently overwritten, and repeated concepts are
connected through concept threads.

## 12. Multi-clinician status

The model supports any number of physicians through the assignment table; it
does not encode a Doctor 1/Doctor 2 limit. The automated PostgreSQL acceptance
test registered Clinician A and Clinician B, assigned both to one patient,
processed reports from both, and verified that the second clinician retrieved
both longitudinal concepts by the same numeric patient ID.

A separate three-clinician acceptance run was not performed.

## 13. Provenance status

Provenance is preserved across Step 1, ClinicalEvent, memory, documentation,
and audit paths. Gateway routes bind actor identity to the authenticated JWT
subject rather than trusting a caller-supplied reviewer/physician identity.
Source document/event IDs, encounter, text span, modality, language,
confidence, and approval information remain available where supported by the
contract.

## 14. Trust status

The Memory Write Gate applies trust tiers and keeps low-confidence/high-risk
or unreviewed information out of verified context. Tier-3 approval/rejection
and physician approval provenance are covered by deterministic tests.

## 15. Conflict status

Contradictory events are retained as historical records and produce conflict
records. Unresolved conflicts are not silently treated as verified facts;
explicit conflict resolution is required. Conflict detection and resolution
tests pass, including patient isolation.

## 16. Retrieval status

The retrieval layer uses the existing vector-store abstraction with a
deterministic lexical/basic implementation for local MVP operation. Relevance
scoring, patient isolation, trust filtering, unresolved-conflict filtering,
and provenance preservation are covered. The multi-clinician PostgreSQL test
verified relevant history from both clinicians rather than dumping an
unrelated patient’s records.

## 17. Gemini status

Gemini remains backend-only. The contextualization and documentation adapters
use the API key through backend configuration and send it in the provider
header; frontend `VITE_*` variables contain no Gemini secret. The adapter
supports timeout/retry and rejects malformed provider responses.

The current local `.env` uses mock modes for the tested workflow, so no live
Gemini request was made. Production Gemini configuration must set a valid
backend `GEMINI_API_KEY`; `GEMINI_ENDPOINT` must be a URL or empty. The
integration layer defensively ignores an endpoint value that is identical to
the key rather than treating the secret as a URL. Rotate any provider secret
if a rendered Compose configuration has been saved or shared.

## 18. Documentation status

SOAP-note and discharge-summary generation remain behind the existing
generator interface. Deterministic generation, required-section validation,
unsupported-claim checks, provenance mapping, and conflict safeguards pass in
tests. The persistent manual workflow reached a draft document before review;
the test workflow uses the deterministic generator.

## 19. Physician review status

Documents remain drafts until an explicit physician action. Accept, edit, and
reject/regenerate paths are implemented and tested. Finalization binds the
actor to the authenticated user at the gateway boundary and can return a
memory-write payload.

## 20. Memory Write Gate status

Step 4 finalization hands approved facts to the in-process Step 3 client, which
enters the single Memory Write Gate. Step 4 does not directly insert trusted
memory. The end-to-end pipeline test verified that physician-approved facts
were appended through this gate and retained original provenance.

## 21. Frontend/backend integration status

The FastAPI gateway currently exposes 25 OpenAPI paths, including health, auth,
patient identity/assignment, Step 1, Step 2, Step 3, and Step 4 routes. The
checked-in `contracts/openapi/gateway.yaml` now aggregates the detailed
service-specific contracts through external references. All contract YAML
files parse successfully.

The frontend adapters preserve contract field names such as `patient_id`,
`encounter_id`, `document_id`, `event_id`, and `conflict_id`; no Gemini
call is made from the browser.

## 22. Test results

Verified commands and results:

```text
pytest -q -rs                         125 passed
pytest -q tests/test_postgres_multi_clinician_e2e.py  1 passed
npm run lint                          passed
npm test -- --run                     46 passed
npm run build                         passed
alembic upgrade head                  passed
alembic check                         no new upgrade operations
OpenAPI YAML parse                    passed
docker compose config                 passed
```

The backend suite emitted two dependency deprecation warnings from the test
client stack. No test was weakened to hide a failure. Docker container runtime
startup was not tested because the Docker engine was unavailable in this
environment.

## 23. Remaining blockers

- Live Gemini, external OCR/VLM, and production BioClinicalBERT calls still
  need environment/model credentials and a separate controlled verification.
- Original upload bytes do not yet have durable object storage; only extracted
  Step 1 data is persisted by the current repository adapter.
- Refresh replay protection and the rate limiter are process-local; a
  multi-replica deployment needs shared state or an edge gateway.
- The browser-based full workflow and Docker container startup were not run in
  this environment.
- A dedicated invitation/assignment administration UX and a three-clinician
  acceptance run remain future operational work.
- Audit records are persisted, but a complete audit-history browsing endpoint
  is not part of the current public contract.

## Local commands

From `clinical-memory-system/`:

```powershell
alembic upgrade head
pytest -q
uvicorn services.gateway.app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

For Docker, provide secret values through an uncommitted `.env`, then run:

```powershell
docker compose up --build
docker compose exec gateway alembic upgrade head
```

The Docker commands require a running Docker engine. Do not paste the output
of `docker compose config` into logs or tickets because it can render secret
environment values.

## Required environment variables

At minimum configure `DATABASE_URL`, `JWT_SECRET_KEY`,
`CORS_ALLOWED_ORIGINS`, `POSTGRES_*` values for Compose, and
token-expiration settings. Configure
`CLINICAL_PIPELINE_PERSISTENCE=true` for durable runtime state. For
production AI modes configure the applicable `STEP1_AI_*`,
`STEP2_NLP_MODE`, `GEMINI_*`, `BIOCLINICALBERT_*`, and `STEP4_LLM_*`
variables. Keep all API keys backend-only. The frontend only requires
`VITE_API_BASE_URL`.
