# Frontend–Backend Integration Audit

Audit date: 2026-08-18

Scope: existing React/Vite frontend, the FastAPI gateway, shared backend
contracts, Pydantic schemas, and current service routers. This audit was
completed before integration changes.

## Executive findings

The frontend is a fixture-driven workflow shell. Its pages and hooks are
useful presentation surfaces, but its API layer does not currently make HTTP
requests. The most important integration gaps are:

- There is no centralized HTTP client, API base URL, authentication state, or
  login route.
- `frontend/src/api/step1.ts` sends only identifiers and modality metadata;
  it does not send the selected file bytes required by the backend multipart
  contract.
- `frontend/src/api/pipeline.ts` resolves all Step 2–4, memory, conflict, and
  trust operations from JSON fixtures.
- The frontend uses fixture IDs such as `pat_00123`, `enc_2026_0817_01`,
  `job_ocr_771`, `job_nlp_412`, and `phy_04` in production code paths.
- Frontend contract types have drifted from the current backend contracts.
  Examples include frontend `job_id`, `source_document`, `updated_at`, and
  `written_to_memory` fields that are absent from the backend `Step1Output`,
  and nested conflict/event shapes that do not match the backend schemas.
- No authoritative backend audit endpoint exists in the current OpenAPI or
  router set, so the audit page cannot be connected to a backend audit list
  without inventing an endpoint.
- The backend gateway mounts the requested routes, but its default integrated
  graph uses in-memory stores. Frontend HTTP integration can be completed for
  the current API behavior, but durable PostgreSQL-backed end-to-end behavior
  is a backend deployment limitation.

## Frontend operation mapping

| Frontend operation | Frontend file | Current mock/API | Backend endpoint | Request schema | Response schema | Status | Required change |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Login | No login page or auth hook | Not implemented | `POST /api/v1/auth/login` | `LoginRequest` | `TokenResponse` | Missing | Add centralized auth adapter/state and login route without exposing tokens in UI. |
| Restore current physician | No auth state | Not implemented | `GET /api/v1/auth/me` | Bearer access token | `UserResponse` | Missing | Restore session through HTTP transport and protect workflow routes. |
| Refresh access token | No refresh logic | Not implemented | `POST /api/v1/auth/refresh` | `RefreshTokenRequest` | `TokenResponse` | Missing | Add single-flight refresh/retry behavior and logout on refresh failure. |
| Upload typed document | `src/pages/UploadPage.tsx`, `src/api/step1.ts` | Mock; metadata only, no bytes | `POST /api/v1/step1/documents/typed` | Multipart `patient_id`, `encounter_id`, `file` | `Step1Output` | Contract mismatch | Preserve `File` in request and send multipart bytes. |
| Upload handwritten document | `src/pages/UploadPage.tsx`, `src/api/step1.ts` | Mock; metadata only, no bytes | `POST /api/v1/step1/documents/handwritten` | Multipart `patient_id`, `encounter_id`, `file` | `Step1Output` | Contract mismatch | Send the selected file and use backend processing status. |
| Upload multilingual input | `src/pages/UploadPage.tsx`, `src/api/step1.ts` | Mock; no text input | `POST /api/v1/step1/documents/multilingual` | `MultilingualDocumentRequest` with `text_input` | `Step1Output` | Contract mismatch | Add a text-input path or use an approved text/file UX; do not send only a filename. |
| Load Step 1 document | `src/hooks/useStep1.ts`, `src/api/step1.ts` | Mock keyed by `job_ocr_771` | `GET /api/v1/step1/documents/{document_id}` | Path `document_id` | `Step1Output` | Wrong identifier | Replace job fixture lookup with real `document_id`; map UI display fields from the real response. |
| Step 1 processing lifecycle | `src/pages/UploadPage.tsx`, `src/context/WorkflowContext.tsx` | Assumes immediate response; no polling | Current backend returns `Step1Output` directly | No separate job-status contract exists | `Step1Output` | Partial | Handle `complete`, `pending_human_verification`, and `failed`; do not invent a polling endpoint or `job_id`. |
| Human verification | `src/pages/VerificationPage.tsx`, `src/api/step1.ts` | Mock mutation; hardcoded `phy_04` | `POST /api/v1/step1/documents/{document_id}/human-verify` | `HumanVerificationRequest` | `Step1Output` | Contract mismatch | Send real document/field IDs and authenticated reviewer context; use returned Step1Output. |
| Step 1 review queue | `src/hooks/useStep1.ts`, `src/pages/ReviewQueuePage.tsx` | Mock derived from one fixture | No review-queue endpoint | None | None | No backend endpoint | Derive from a loaded Step1 document or leave as local navigation; do not invent a list API. |
| Step 1 audit view | `src/hooks/useStep1.ts`, `src/pages/AuditLogPage.tsx` | Mock synthetic audit record | No authoritative audit endpoint | None | None | No backend endpoint | Display available `audit_log_id`/Step1 metadata only, or defer until a documented endpoint exists. |
| Step 2 source/load | `src/hooks/useStep2.ts`, `src/pages/ClinicalNlpPage.tsx` | Mock keyed by `job_nlp_412` | `GET /api/v1/step2/process/{document_id}` | Path `document_id` | `ClinicalEventBatch` | Wrong identifier | Use workflow `document_id`; gate UI on actual response. |
| Step 2 process | `src/hooks/useStep2.ts`, `src/pages/ClinicalNlpPage.tsx` | Disabled query resolves fixture | `POST /api/v1/step2/process` | `Step2ProcessRequest` containing `Step1Output` | `ClinicalEventBatch` | Contract mismatch | Send real Step1Output/document/patient/encounter values and handle 422/503 states. |
| Clinical findings | `src/pages/ClinicalNlpPage.tsx`, `src/components/ClinicalEventCard.tsx` | Fixture events with extra fields | Step 2 response | `ClinicalEvent[]` inside `ClinicalEventBatch` | `ClinicalEventBatch` | Contract drift | Preserve backend fields and make frontend-only presentation fields optional/derived. |
| Memory events | `src/hooks/useMemory.ts`, `src/pages/MemoryExplorerPage.tsx` | Mock fixture | `GET /api/v1/step3/memory/{patient_id}/events` | Path `patient_id` | `MemoryEventHistory` | Contract mismatch | Map backend `MemoryEvent` to the existing display model without fabricating fields. |
| Patient current state | `src/hooks/useMemory.ts`, `src/pages/MemoryExplorerPage.tsx` | Mock derived array | `GET /api/v1/step3/memory/{patient_id}/current-state` | Path `patient_id` | `CurrentPatientState` | Contract mismatch | Render concept threads/current state separately from event history. |
| Memory retrieval | `src/hooks/useMemory.ts`, `src/pages/MemoryExplorerPage.tsx` | Mock `RetrievedContext` | `POST /api/v1/step3/memory/retrieve` | `MemoryRetrieveRequest` | `RetrievedContext` | Partial | Connect HTTP and preserve verified, unverified, and conflicts as separate collections. |
| Conflict list | `src/hooks/useMemory.ts`, `src/pages/MemoryExplorerPage.tsx` | Mock conflicts nested with event objects | `GET /api/v1/step3/conflicts` | Query `patient_id`, optional status/risk | `ConflictRecord[]` | Contract mismatch | Use flat backend conflict IDs/status/risk and load event details separately if needed. |
| Conflict resolution | `src/hooks/useMemory.ts`, `src/pages/MemoryExplorerPage.tsx` | Mock optimistic response; `dismissed` status | `POST /api/v1/step3/conflicts/{conflict_id}/resolve` | `ResolveConflictRequest` | `ResolveConflictResponse` | Contract mismatch | Use backend `resolved`/`unresolved`, reconcile only after mutation success, and preserve unresolved conflicts. |
| Tier-3 approval | `src/hooks/useMemory.ts`, `src/pages/MemoryExplorerPage.tsx`, `ClinicalNlpPage.tsx` | Mock; hardcoded physician ID | `POST /api/v1/step3/tier3/{event_id}/approve` | `TierReviewRequest` | `TierReviewResponse` | Contract mismatch | Send event ID and authenticated reviewer identity through the backend contract. |
| Tier-3 rejection | Same as approval | Mock; hardcoded physician ID | `POST /api/v1/step3/tier3/{event_id}/reject` | `TierReviewRequest` | `TierReviewResponse` | Contract mismatch | Keep rejected information visible as unverified and reconcile server state. |
| Documentation generation | `src/hooks/useDocuments.ts`, `src/pages/DocumentationPage.tsx` | Mock SOAP/discharge fixtures | `POST /api/v1/step4/documents/generate` | `GenerateDocumentRequest` | `GeneratedDocument` | Contract mismatch | Send real current events and RetrievedContext; align document/provenance/flag schemas. |
| Document draft load | `src/hooks/useDocuments.ts`, `DocumentationPage.tsx` | Mock document history | No GET document-draft endpoint | None | None | No backend endpoint | Use the generated response in query state; do not invent a GET route. |
| Physician document review | `src/pages/DocumentationPage.tsx`, `DocumentEditor.tsx` | Local edit state | Part of finalize endpoint | `FinalizeDocumentRequest` | `DocumentReviewResponse` | Partial | Keep draft status authoritative and submit edits only on finalization. |
| Accept/edit finalization | `src/hooks/useDocuments.ts`, `DocumentationPage.tsx` | Mock finalization | `POST /api/v1/step4/documents/{document_id}/finalize` | `FinalizeDocumentRequest` | `DocumentReviewResponse` | Contract mismatch | Handle `draft`/`finalized`, validation errors, and returned memory payload. |
| Reject/regenerate | `src/hooks/useDocuments.ts`, `DocumentationPage.tsx` | Mock discarded response | Same finalize endpoint, action `reject_regenerate` | `FinalizeDocumentRequest` | `DocumentReviewResponse` | Contract mismatch | Use backend draft/regeneration response; frontend `discarded` status is not in backend `DocumentStatus`. |
| Memory Write Gate | `ClinicalNlpPage.tsx`, `useDocuments.ts` | Frontend directly calls mocked `writeMemoryEvents` | `POST /api/v1/step3/memory/events` | `MemoryWriteRequest` | `MemoryWriteResponse` | Safety-critical mock | Only submit returned `memory_write_payload` after physician finalization; never write locally or to PostgreSQL. |
| Audit/provenance display | Provenance drawers and audit page | Fixture-specific fields | Provenance is embedded in Step 1/2/3/4 responses; no audit list endpoint | Existing response schemas | Embedded provenance | Partial | Render backend provenance fields; do not fabricate missing audit records. |
| Loading/error states | Pages and TanStack Query hooks | Some loading states; generic/mock success | All endpoints | HTTP status/error body | `ApiError` needs normalization | Partial | Centralize status handling for 401/403/404/409/422/429/5xx, retry, empty, and mutation states. |

## Contract drift requiring adapter work

### Step 1

Backend `Step1Output` contains `document_id`, `patient_id`, `encounter_id`,
`input_modality`, `source_language`, `extracted_fields`,
`translation_confidence`, `original_language_text`, `ocr_engine_used`,
`vlm_model_used`, `processing_status`, `audit_log_id`, `created_at`, and
`verification_state`.

The frontend currently expects additional or different fields including
`job_id`, `source_document`, `updated_at`, `written_to_memory`,
`field_type`, `review_status`, and `verified_text`. These must become
frontend-derived view values or be removed from backend-facing types. The
backend verification endpoint returns the updated `Step1Output`, not the
frontend `VerificationResponse` fixture shape.

### Step 2

The backend `ClinicalEvent` requires `translation_confidence` as a number,
`validation_status` as `valid | invalid`, and does not expose the frontend’s
`ambiguous_abbreviation_resolved`, medication attributes, lab attributes, or
the narrower frontend enum values. Those fields may be optional presentation
extensions only when absent from backend responses; they cannot be required
for HTTP serialization.

### Step 3

The backend `MemoryContextItem` is smaller and provenance-centered. The
frontend `MemoryFact` currently expects extraction/contextualization
confidence, timestamps, medication/lab attributes, and thread-match fields
that are not in the backend response contract. Backend `ConflictRecord` uses
`event_a_id`/`event_b_id` and has no nested `event_a`/`event_b` objects.

### Step 4

The backend `GeneratedDocument` includes `patient_id`, `encounter_id`,
`status: draft | finalized`, `DocumentReviewFlag`,
`DocumentProvenanceEntry`, and structured `ValidationFailure` objects. The
frontend currently models `validation_failed`/`discarded` statuses and a
different provenance/flag shape. The adapter must preserve the backend model
and use a separate view model only where the UI needs presentation labels.

## Authentication and transport findings

- The frontend has no login route, auth context, token storage policy, or
  `Authorization` header handling.
- No `VITE_API_BASE_URL` exists. The frontend needs a non-secret
  `frontend/.env.example` value such as `http://127.0.0.1:8000`.
- The backend CORS default is closed. Local development needs the backend
  environment configured with the frontend origin, for example
  `CORS_ALLOWED_ORIGINS=http://localhost:5173`; wildcard CORS must remain
  disabled.
- Bearer tokens should be kept out of UI state and logs. The frontend must not
  define a `VITE_GEMINI_API_KEY` or call Gemini directly.
- Gateway pipeline routes require JWT/RBAC. Standalone service apps are not a
  frontend trust boundary and must not be exposed directly.

## Source-of-truth conclusion

The backend Pydantic schemas and mounted FastAPI routes are authoritative for
the integration. Existing frontend fixture types are not authoritative where
they disagree. The incremental implementation should therefore proceed in
this order:

1. Add audit-approved HTTP transport, normalized errors, and auth state.
2. Align API adapter request/response types with backend contracts while
   retaining presentation-only view helpers.
3. Connect Step 1 multipart upload and real document IDs.
4. Connect Step 2, memory/retrieval/conflict/trust, and Step 4 review.
5. Route the returned memory payload through the Step 3 endpoint only.
6. Add frontend contract/integration tests and run the backend suite.

## Post-audit implementation update

The findings above describe the pre-integration state as requested. The
incremental implementation now adds `frontend/src/api/client.ts`, authenticated
HTTP adapters, real multipart upload handling, workflow ID propagation, Step
2–4/memory adapters, normalized API errors, and frontend contract tests. The
production path uses HTTP; fixture adapters remain test-only.

The backend limitations remain material: the default gateway graph uses
in-memory stores, no patient-assignment authorization model is wired, several
history/audit/job endpoints do not exist, and Step 4 finalization currently
commits through the Step 3 Memory Write Gate internally. Final status and
verified test results are recorded in
`docs/frontend-backend-integration.md`.
