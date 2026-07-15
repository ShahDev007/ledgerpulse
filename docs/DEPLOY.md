# Deploying LedgerPulse to Vercel (always-on shareable link)

The stack deploys as **two Vercel projects from this one repo**: a Python API function + a
Next.js web app, backed by **Vercel Postgres**. Files are stored in Postgres and the mock-ERP is
in-process, so no object store or extra services are needed.

## 1. API project (Python / FastAPI)
- **New Project → import this repo → Root Directory: `/` (repo root)**, Framework Preset: **Other**.
- `vercel.json` (repo root) already routes all paths to `api/index.py` with `maxDuration: 60`,
  and `requirements.txt` (repo root) has the slim serverless deps.
- **Storage → Add Vercel Postgres** to this project (injects `POSTGRES_URL` automatically; the app
  derives an async URL from it).
- **Environment variables** (Project → Settings → Environment Variables):
  | Key | Value |
  |---|---|
  | `ANTHROPIC_API_KEY` | your key |
  | `LLM_PROVIDER` | `anthropic` |
  | `STORAGE_BACKEND` | `postgres` |
  | `ERP_MODE` | `inprocess` |
  | `AUTH_SECRET` | a long random string |
  | `ADMIN_TOKEN` | a long random string (used once for bootstrap) |
- Deploy → note the URL, e.g. `https://ledgerpulse-api.vercel.app`.

## 2. Bootstrap the data (one time, after the API is live)
```bash
API=https://ledgerpulse-api.vercel.app
TOK=<your ADMIN_TOKEN>
curl -X POST $API/v1/admin/bootstrap -H "X-Admin-Token: $TOK"
for k in INV-001 INV-002 INV-003 INV-004 INV-005 INV-006 INV-007 INV-008; do
  curl -X POST $API/v1/admin/process/$k -H "X-Admin-Token: $TOK"; echo
done
curl $API/v1/admin/status -H "X-Admin-Token: $TOK"
```
This creates the schema, seeds master data + policies, intakes the 8 invoices, then live-extracts
and matches each (kept per-invoice so every call stays under the 60s function limit).

## 3. Web project (Next.js)
- **New Project → same repo → Root Directory: `apps/web`** (Framework auto-detects Next.js).
- **Environment variable**: `NEXT_PUBLIC_API_URL = https://ledgerpulse-api.vercel.app`.
- Deploy → this URL (e.g. `https://ledgerpulse.vercel.app`) is the **shareable link**.

## Notes
- `VERCEL=1` is set automatically → the app uses `NullPool` + TLS for Neon/Vercel Postgres.
- Demo data only; anyone with the link can switch personas (dev auth). Payment execution and
  vendor-master changes remain out of scope.
- To reset the hosted demo: re-run the bootstrap + process calls (idempotent on invoice keys).
