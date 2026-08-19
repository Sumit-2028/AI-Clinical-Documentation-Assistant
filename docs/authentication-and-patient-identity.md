# Authentication and patient identity

## Status

The gateway uses PostgreSQL-backed users and JWT access/refresh tokens. Public registration is available at `POST /api/v1/auth/register`; it does not use the frontend fixtures.

## Registration

Registration accepts:

```json
{
  "full_name": "Asha Physician",
  "email": "asha@example.com",
  "password": "a-password-of-at-least-8-characters",
  "role": "physician"
}
```

Public roles are limited to `physician` and `patient`. Admin, reviewer, and nurse accounts cannot be self-created. Emails are trimmed, lower-cased, checked case-insensitively, and protected by a PostgreSQL unique expression index. Passwords are stored only as secure bcrypt hashes.

Patient registration creates one durable `patients` row and returns a backend-generated, numeric 6–8 digit `patient_id`. The internal patient primary key remains UUID-based, while `public_patient_id` is unique and indexed in PostgreSQL. The `patients.user_id` relationship is unique and survives login, profile changes, and backend restarts. Physician registration does not create a patient profile.

Registration and the patient-profile creation run in one transaction. A duplicate email returns `409`; invalid input or a privileged self-registration attempt is rejected by schema validation.

## Login and current user

`POST /api/v1/auth/login` verifies the normalized email, password hash, active status, and returns the existing contract:

```json
{
  "access_token": "JWT",
  "refresh_token": "JWT",
  "token_type": "bearer"
}
```

Access tokens and refresh tokens have distinct token types and expirations. `POST /api/v1/auth/refresh` validates type, expiration, active user status, and refresh-token replay state. `GET /api/v1/auth/me` reads the user and any linked patient profile from PostgreSQL; the frontend does not decide identity or authorization from local storage.

The React client keeps the access token in memory and the refresh token in session storage. Production Vite builds do not have an authentication bypass. Test-mode fixture identity is retained only for deterministic frontend tests.

## Roles and patient access

Existing roles are preserved: `admin`, `physician`, `reviewer`, `nurse`, and `patient`. RBAC permissions remain defined in `services/gateway/app/auth/rbac.py`.

Physicians create a patient with `POST /api/v1/patients`. The backend creates the numeric public ID and a persistent active `patient_assignments` row linking the physician to that patient. An admin may assign an existing patient to an active physician with `POST /api/v1/patients/{patient_id}/assignments`.

`GET /api/v1/patients/{patient_id}` requires authentication and checks the server-side relationship. Patient accounts can access only their own linked profile; physicians and staff require an active assignment; admins can access all patients. The same access policy is applied by the gateway before pipeline resources are accessed, including documents, memory, conflicts, and generated documentation. A client-supplied `patient_id` cannot grant access.

## Database and migrations

The relevant schema is:

```text
users
  └── patients.user_id (unique, nullable for physician/staff users)

users ──< patient_assignments >── patients
```

Migrations:

- `20260817_0001_backend_foundation`
- `20260818_0002_auth_patient_identity`
- `20260818_0003_case_insensitive_user_email`
- `20260818_0004_public_patient_identifier`

Apply them with:

```powershell
alembic upgrade head
```

## Local configuration and commands

Backend `.env` must provide at least:

```text
DATABASE_URL=postgresql+psycopg2://...
JWT_SECRET_KEY=<strong-secret-at-least-16-characters>
JWT_ALGORITHM=HS256
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

Keep `GEMINI_API_KEY` backend-only. It is not needed by registration or authentication and must never be placed in a `VITE_*` variable.

Run the backend from `clinical-memory-system`:

```powershell
alembic upgrade head
uvicorn services.gateway.app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

The frontend uses `VITE_API_BASE_URL=http://127.0.0.1:8000` from `frontend/.env.example`.

## Verification

Run the deterministic auth and patient tests:

```powershell
pytest -q tests/test_auth_registration_patient_identity.py
pytest -q tests/test_phase9_end_to_end.py
pytest -q tests/test_auth_postgres_integration.py
```

The PostgreSQL integration test creates unique temporary accounts, verifies registration, login, `/auth/me`, patient persistence, and authorized/unauthorized physician lookup, then removes its rows. It is skipped when the configured database is unavailable.

## Known limitations

- Physician-to-patient assignment is currently created by the physician who creates a patient or by an admin assignment request; there is no separate invitation workflow.
- Access tokens are held in browser memory and refresh tokens in session storage. A production deployment may choose an HttpOnly cookie strategy without changing the backend identity model.
- The gateway selects request-scoped SQLAlchemy repositories/stores by default when `CLINICAL_PIPELINE_PERSISTENCE=true` (the default). In-memory repositories are retained for isolated service tests and can be explicitly selected for local test-only runs with `CLINICAL_PIPELINE_PERSISTENCE=false`.
