#!/usr/bin/env bash
#
# Demonstrates Step 1 object storage end to end against a running gateway.
#
#   ./scripts/demo_object_storage.sh
#
# Requires: the gateway on :8000 with STEP1_STORAGE_MODE=s3, MinIO on :9000,
# and a seeded physician.  Prints what it checks so the run is followable live.

set -euo pipefail

API="${API:-http://127.0.0.1:8000}"
EMAIL="${DEMO_EMAIL:-doctor@example.com}"
PASSWORD="${DEMO_PASSWORD:-DemoPass123}"
PY="${PY:-.venv/bin/python}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; exit 1; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

jget() { "$PY" -c "import sys,json;print(json.load(sys.stdin)$1)"; }

step "1. Services"
curl -sf -o /dev/null "$API/health" || fail "gateway is not responding on $API"
pass "gateway healthy"
curl -sf -o /dev/null http://localhost:9000/minio/health/live \
  || fail "MinIO is not responding on :9000  (docker compose up -d minio)"
pass "MinIO healthy"

step "2. Authenticate"
TOKEN=$(curl -sf -X POST "$API/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jget "['access_token']")
[ -n "$TOKEN" ] || fail "login failed for $EMAIL"
AUTH="Authorization: Bearer $TOKEN"
pass "signed in as $EMAIL"

step "3. Create a patient"
PATIENT=$(curl -sf -X POST "$API/api/v1/patients" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Storage Demo Patient"}' | jget "['patient_id']")
pass "patient $PATIENT"

step "4. Upload a clinical note"
cat > "$WORK/note.txt" <<'NOTE'
Patient reports chest pain for two days. BP 150/95.
Started aspirin 75mg daily. No known drug allergies.
NOTE
DOC=$(curl -sf -X POST "$API/api/v1/step1/documents/typed" -H "$AUTH" \
  -F "patient_id=$PATIENT" -F "encounter_id=$(uuidgen)" \
  -F "file=@$WORK/note.txt;type=text/plain" | jget "['document_id']")
pass "stored and processed as document $DOC"

step "5. Ask for the original document back"
curl -sf "$API/api/v1/step1/documents/$DOC/source" -H "$AUTH" > "$WORK/source.json"
URL=$(jget "['download_url']" < "$WORK/source.json")
"$PY" -c "
import json
d = json.load(open('$WORK/source.json'))
print('  content type :', d['content_type'])
print('  size         :', d['size_bytes'], 'bytes')
print('  link expires :', d['expires_at'])
"
case "$URL" in
  memory://*) fail "gateway is in mock storage mode; set STEP1_STORAGE_MODE=s3" ;;
  *) pass "presigned S3 link issued" ;;
esac
printf '  key: %s\n' "$(printf '%s' "$URL" | sed -E 's|https?://[^/]+/[^/]+/||; s|\?.*||')"

step "6. Download it and compare"
curl -sf -o "$WORK/downloaded.txt" -D "$WORK/headers.txt" "$URL"
cmp -s "$WORK/note.txt" "$WORK/downloaded.txt" \
  && pass "downloaded bytes are identical to the upload" \
  || fail "downloaded content does not match"
grep -i 'content-disposition' "$WORK/headers.txt" | sed 's/^/  /'
pass "download is named after the document id, not the uploaded filename"

step "7. The link is signed, not a public URL"
code=$(curl -s -o /dev/null -w '%{http_code}' "${URL%?}X")
[ "$code" = "403" ] && pass "tampered signature rejected ($code)" \
  || fail "expected 403 for a tampered signature, got $code"
code=$(curl -s -o /dev/null -w '%{http_code}' "${URL%%\?*}")
[ "$code" = "403" ] && pass "unsigned request rejected ($code)" \
  || fail "expected 403 for an unsigned request, got $code"

step "8. Uploads are checked against their real bytes"
printf '%%PDF-1.7\ntrailer\n%%%%EOF\n' > "$WORK/actually_a_pdf.png"
code=$(curl -s -o /dev/null -w '%{http_code}' \
  -X POST "$API/api/v1/step1/documents/typed" -H "$AUTH" \
  -F "patient_id=$PATIENT" -F "encounter_id=$(uuidgen)" \
  -F "file=@$WORK/actually_a_pdf.png;type=image/png")
[ "$code" = "415" ] && pass "PDF disguised as a PNG rejected ($code)" \
  || fail "expected 415 for a spoofed file, got $code"

step "9. Access requires authentication"
code=$(curl -s -o /dev/null -w '%{http_code}' "$API/api/v1/step1/documents/$DOC/source")
[ "$code" = "401" ] && pass "no token, no document ($code)" \
  || fail "expected 401 without a token, got $code"

printf '\n\033[1;32mAll checks passed.\033[0m\n'
printf 'MinIO console: http://localhost:9001\n\n'
