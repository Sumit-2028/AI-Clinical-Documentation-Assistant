# Backend Security and Production Hardening

## Secure defaults

- Authentication uses signed, expiring JWT access and refresh tokens. Access and refresh token types are distinct, the signing algorithm is restricted to HMAC algorithms configured by `JWT_ALGORITHM`, and required claims include `sub`, `type`, `iat`, `exp`, and `jti`.
- Refresh tokens are rotated and a previously consumed refresh `jti` is rejected by the local replay guard.
- Passwords are stored only as bcrypt hashes. Oversized passwords are rejected before bcrypt processing.
- All gateway-mounted Step 1–4 routes require a Bearer access token. RBAC maps read, write, review, and memory operations to the existing role permissions.
- CORS has no allowed origins by default. Configure exact origins with `CORS_ALLOWED_ORIGINS`; wildcard origins are rejected.
- The gateway applies local in-memory rate limits, with a stricter limit for login and refresh endpoints.
- Uploads are bounded by `MAX_UPLOAD_SIZE_BYTES`, checked against an allowlist of MIME types, and rejected when filenames contain path traversal or unsafe characters. Uploaded content is never used as a filesystem path.
- Upload content is validated against its actual leading bytes, not the caller's declared MIME type, so a renamed file cannot be stored as a permitted type (`UPLOAD_MAGIC_BYTE_CHECK`, on by default). Two limits are deliberate: the PDF header is accepted anywhere in the first 1024 bytes because the specification permits leading bytes, so a polyglot file could satisfy it; and `text/plain` has no signature, so it is validated negatively (no NUL bytes, no other format's signature, no unexpected control characters, and it must decode as UTF-8). There is no antivirus or malware scanning.
- Original uploaded documents are persisted to object storage before extraction runs. Object keys contain only opaque identifiers (`{prefix}/patients/{patient_id}/documents/{document_id}/source`) and deliberately exclude the original filename, which routinely carries patient identifiers. Keys are never written to logs. The bucket is private; nothing is publicly readable.
- Original documents are retrieved through short-lived presigned URLs, never proxied through the gateway. **A presigned URL is a bearer credential for its lifetime: anyone holding it can fetch the document without presenting a token, bypassing gateway RBAC.** Expiry is therefore short (`S3_PRESIGN_EXPIRY_SECONDS`, default 300 seconds, clamped to 60–3600), and the download filename is derived from the document ID rather than the uploaded filename.
- Request logs contain method, redacted route, status, duration, and request ID only. Passwords, JWTs, API keys, request bodies, medical text, and raw patient/document UUIDs are not logged.
- Gateway responses include no-store caching for API responses plus defensive browser headers (`nosniff`, frame denial, restrictive referrer/permissions policy, and a default-deny content security policy).
- Validation and unexpected-error responses do not echo request bodies, provider responses, SQL details, or exception messages.
- Clinical text in generation prompts is explicitly delimited as untrusted data. Prompt-control patterns in physician instructions are rejected. Generated clinical claims must pass deterministic support, provenance, required-section, and conflict validation; documents remain drafts until physician action.
- Clinical memory writes enter through the single Step 3 Memory Write Gate. Memory retrieval filters by patient ID, trust tier, and unresolved conflict state.
- Patient isolation is enforced at the gateway and memory/retrieval boundaries. Physicians require an active PostgreSQL `patient_assignments` row; patient accounts are limited to their linked profile; admins have the existing administrative access. Public numeric patient IDs are resolved to internal UUIDs server-side, so changing a frontend ID cannot grant access.
- SQL access uses SQLAlchemy query expressions; no user-controlled SQL strings are composed. Durable repositories roll back failed write transactions.
- Audit records retain action metadata, actor information where supplied, and timestamps; sensitive values are redacted.

## Configuration hygiene

Never commit `.env` files. Use `.env.example` only as a variable-name template. Set a unique production `JWT_SECRET_KEY`, database password, seed password, and AI provider keys through the deployment secret manager. The gateway runtime `.env` must remain outside version control. Docker Compose now requires `POSTGRES_PASSWORD` and `JWT_SECRET_KEY` instead of supplying source-controlled defaults.

## Deployment limitations and required production controls

The local replay guard and rate limiter are process-local. A multi-replica deployment must put refresh-token replay state and rate limiting behind shared durable infrastructure or a trusted edge gateway. TLS termination, secure network boundaries, database encryption/backups, secret rotation, dependency scanning, and centralized append-only audit retention remain deployment responsibilities.

Object storage now holds protected health information at rest, and the following are deployment responsibilities rather than application behaviour:

- **Bucket-level encryption.** Set default server-side encryption (SSE-KMS in production, via `S3_SSE=aws:kms` and `S3_SSE_KMS_KEY_ID`). The local MinIO development stack does not exercise this, so it must be verified against the real bucket.
- **Block Public Access** on the bucket, plus a bucket policy denying `aws:SecureTransport=false` so objects are unreachable over plaintext HTTP.
- **Versioning and retention**, including object lock or legal hold where record-retention obligations apply, and a documented deletion path for patient erasure requests. The application deliberately has no delete operation.
- **Lifecycle rules** to abort incomplete multipart uploads and to reap orphaned objects. An upload is stored before extraction runs, so a process failure between storing and saving can leave an object with no document row referencing it.
- **Scoped IAM.** Grant only `GetObject` and `PutObject` on the key prefix. The application must not hold `CreateBucket` or `DeleteObject`; `S3_CREATE_BUCKET_IF_MISSING` exists for local development and must stay `false` in production, where the bucket is created out of band with the controls above.
- **Access logging.** Enable CloudTrail data events for the bucket; object reads through presigned URLs do not pass through the gateway and so do not appear in application logs or audit records.

Direct service applications are useful for isolated development tests but are not an alternative trust boundary to the gateway. Production traffic should enter through the gateway or an equivalent authenticated service mesh. Keep `GEMINI_API_KEY`, `STEP1_AI_API_KEY`, and `STEP4_LLM_API_KEY` backend-only; `GEMINI_ENDPOINT` must be a URL or empty, never an API key.
