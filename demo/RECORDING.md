# Object storage demo — recording runbook

Everything needed to reproduce the upload-to-S3 walkthrough on camera.

Sample files live in [`demo/samples/`](samples). Drag them into the upload page
rather than typing content live.

| File | Use |
|---|---|
| `clinical-note.txt` | The main upload |
| `followup-note.txt` | A second upload, to show two documents for one patient |
| `spoofed-image.png` | A PDF renamed to `.png` — rejected with 415 |

---

## Before recording

**1. Docker must be running.** Start it and wait for the whale icon to settle.

```bash
open -a Docker
```

**2. Start Postgres and MinIO.**

```bash
cd ~/Desktop/AI-Clinical-Documentation-Assistant && docker compose up -d postgres minio
```

**3. Start the gateway in S3 mode.** The default is `mock`, which stores to
process memory — the demo would look identical while proving nothing, so this
step is not optional. Leave it running in its own terminal.

```bash
cd ~/Desktop/AI-Clinical-Documentation-Assistant && set -a && . ./.env && set +a && STEP1_STORAGE_MODE=s3 S3_ENDPOINT_URL=http://localhost:9000 S3_BUCKET=clinical-documents S3_FORCE_PATH_STYLE=true S3_ACCESS_KEY_ID="$MINIO_ROOT_USER" S3_SECRET_ACCESS_KEY="$MINIO_ROOT_PASSWORD" STEP1_AI_MODE=mock STEP2_NLP_MODE=mock STEP4_LLM_MODE=mock .venv/bin/uvicorn services.gateway.app.main:app --port 8000
```

**4. Start the frontend** in a second terminal.

```bash
cd ~/Desktop/AI-Clinical-Documentation-Assistant/frontend && npm run dev -- --port 5173
```

**5. Create a patient** and note the number it returns — the upload form needs
it. Run this in a third terminal.

```bash
cd ~/Desktop/AI-Clinical-Documentation-Assistant && TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"email":"doctor@example.com","password":"DemoPass123"}' | .venv/bin/python -c "import sys,json;print(json.load(sys.stdin)['access_token'])") && curl -s -X POST http://127.0.0.1:8000/api/v1/patients -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"display_name":"Demo Patient"}'
```

**6. Open two browser tabs**, so you can cut between them without fumbling:

- `http://localhost:5173` — the app
- `http://localhost:9001` — the MinIO console (log in with the
  `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env`), open the
  `clinical-documents` bucket

---

## The walkthrough

**Show the empty state first.** In the MinIO tab, note the current object count.
The demo lands much better when the audience sees the number change.

**Sign in** at `http://localhost:5173/login`.

| | |
|---|---|
| Email | `doctor@example.com` |
| Password | `DemoPass123` |

**Go to Upload & Process** in the left sidebar.

1. Choose **Typed** under *Document type* — it defaults to Multilingual, which
   expects pasted text and no file.
2. Enter the patient number from step 5 in **Patient ID**. Encounter ID is
   pre-filled.
3. Drag `demo/samples/clinical-note.txt` onto the drop zone.
4. Click **Start processing**. The app moves to the clinical analysis page.

**Switch to the MinIO tab and refresh.** One new object, under a key shaped
like:

```
step1/patients/{patient-uuid}/documents/{document-uuid}/source
```

Click into it to show the size and content type, and that the contents are the
uploaded note.

### Two points worth saying out loud

**The key contains no patient information** — only opaque identifiers. Not the
patient number you typed, not the original filename, not a name or a date.
Keys reach logs, audit records, and signed URLs, and uploaded filenames very
often carry patient names.

**The path uses the internal patient UUID, not the number you entered.** The
public number is an external identifier; the backend resolves it before
building the key. Expect the question, since the number you typed is visibly
absent from the path.

---

## Optional: the security properties

These are the parts that show why storage was done this way rather than by
writing files to disk. The script prints each check as it passes.

```bash
cd ~/Desktop/AI-Clinical-Documentation-Assistant && ./scripts/demo_object_storage.sh
```

It proves the same upload path plus: a tampered signature is refused (403), an
unsigned request is refused (403), a PDF renamed to `.png` is rejected (415),
and the document is unreachable without a token (401).

To show the rejection in the UI instead, upload `demo/samples/spoofed-image.png`
as a typed document — the file is a PDF wearing a `.png` extension, and the
backend rejects it on its actual bytes rather than its declared type.

---

## If something fails on camera

| Symptom | Cause |
|---|---|
| Upload error, or link shows `memory://` | Gateway is in mock mode — step 3 was skipped or its terminal died |
| `Patient not found` | The patient number is wrong, or the database was recreated after step 5 |
| Browser says the backend is unreachable | Vite is on a port that is not in `CORS_ALLOWED_ORIGINS`; check the address bar, `5174` means another Vite already had `5173` |
| MinIO console will not load | `docker compose up -d minio` was skipped, or Docker Desktop is not running |

---

## What is deliberately not shown

Extraction runs with deterministic mock adapters (`STEP1_AI_MODE=mock`), so the
extracted fields are stubs rather than real OCR output. Storage and retrieval
are genuine; what is pulled out of the document is not. Worth stating plainly
if anyone asks whether the pipeline is "real".
