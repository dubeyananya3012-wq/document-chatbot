# Document Intelligence Chatbot

Multi-tenant RAG chatbot. Each user logs in, uploads their own documents,
and gets answers grounded only in their own files. $0 budget - free tiers only.

## Directory structure

```
document-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app entrypoint
│   │   ├── config.py            env-based settings
│   │   ├── auth.py               Firebase token verification
│   │   ├── models.py             Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── upload.py         POST /upload, GET /upload/history
│   │   │   └── query.py          POST /query
│   │   └── services/
│   │       ├── docling_loader.py Unified PDF/DOCX/MD parsing + OCR
│   │       ├── chunker.py        6 chunking strategies
│   │       ├── token_check.py    Token-ceiling safeguard
│   │       ├── vectorstore.py    Chroma Cloud client, per-user isolation
│   │       ├── llm.py            Groq (Llama 3.3 70B) client
│   │       ├── grounding.py      Confidence scoring
│   │       └── upload_log.py     Upload audit log
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── firebase.js
    │   ├── context/AuthContext.jsx
    │   ├── api/client.js         Attaches Firebase ID token to every call
    │   └── components/
    │       ├── Login.jsx
    │       ├── UploadPanel.jsx
    │       └── ChatPanel.jsx
    ├── package.json
    └── .env.example
```

---

## 1. Set up Firebase Authentication + Firestore

1. Go to https://console.firebase.google.com, create a new project (free Spark plan).
2. In the project: **Build > Authentication > Get started**. Enable **Email/Password** and **Google** sign-in providers.
3. In the same project: **Build > Firestore Database > Create database**. Start in production mode (the backend writes via the admin SDK, which bypasses client security rules, so default rules are fine). This backs both the upload log and the OKF metadata layer - no separate setup needed for each.
4. Get the **frontend config**: Project Settings (gear icon) > General > "Your apps" > add a Web app. Copy the `firebaseConfig` values into `frontend/.env` (copy from `.env.example` first).
5. Get the **backend service account**: Project Settings > Service Accounts > "Generate new private key". This downloads a JSON file.
   - Save it as `backend/firebase-service-account.json` (this path is already in `.gitignore` - never commit it).

## 2. Set up Chroma Cloud

1. Sign up at https://www.trychroma.com/ (free tier).
2. Create a database. Note your **API key**, **tenant ID**, and **database name**.
3. Put these into `backend/.env` as `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`.

## 3. Get a Groq API key

1. Sign up at https://console.groq.com (free, no card required).
2. Create an API key under **API Keys**.
3. Put it in `backend/.env` as `GROQ_API_KEY`.
4. Free tier limits: ~30 requests/minute, ~1,000 requests/day on Llama 3.3 70B - fine solo, revisit if this gets multiple concurrent users.

## 4. Backend setup (local)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in the values from steps 1-3
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for the interactive API docs.

## 5. Frontend setup (local)

```bash
cd frontend
npm install
cp .env.example .env            # fill in Firebase web config + API base URL
npm run dev
```

Visit `http://localhost:5173`.

## 6. Deploy

**Frontend (Vercel or Netlify, free):**
- Connect the GitHub repo, set the root directory to `frontend/`.
- Add the same environment variables from `frontend/.env` in the host's dashboard.
- Set `VITE_API_BASE_URL` to your deployed backend URL (step below).

**Backend (Render, free tier):**
- New Web Service, connect the repo, root directory `backend/`.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Add all variables from `backend/.env` in Render's environment settings.
- For `FIREBASE_SERVICE_ACCOUNT_PATH`: don't commit the JSON file. Instead, either:
  - paste its full contents into a `FIREBASE_SERVICE_ACCOUNT_JSON` env var and adjust `app/auth.py` to load `credentials.Certificate(json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]))`, or
  - use Render's "Secret Files" feature to upload the JSON directly.
- Free tier has a 30-50s cold start after inactivity - expected for a personal-scale project.
- Update `CORS_ORIGINS` in Render's env vars to your deployed frontend URL.

## Security

This started with almost none - see the PRD's non-goals. Hardened since:

- **Auth & isolation** — every document route depends on a verified Firebase ID token (signature, expiry, revocation all checked server-side); `user_id` is never accepted from the client, only from the decoded token; Chroma queries and deletes are filtered by that `user_id` server-side so one user's documents are structurally unreachable from another's requests.
- **Path traversal** — `sanitize_filename()` strips directory components, null bytes, and non-safe characters from every client-supplied filename before it touches the filesystem (`app/services/file_security.py`).
- **Upload size cap** — uploads are streamed to disk in 1 MB chunks and aborted (HTTP 413) the instant they exceed `MAX_UPLOAD_SIZE_MB` (default 20), so nothing is ever fully buffered in memory or written past the cap.
- **Content-type spoofing** — file content is checked against magic bytes (PDF/DOCX) or UTF-8 decodability (md/txt), not just the extension, so a renamed arbitrary file is rejected before it reaches Docling.
- **Rate limiting** — `slowapi`, keyed by client IP, caps `/upload` (`RATE_LIMIT_UPLOAD`, default 10/min) and `/query`+`/query/stream` (`RATE_LIMIT_QUERY`, default 20/min). In-memory, so it resets per process - fine for a single free-tier instance; would need a shared store (e.g. Redis) behind a load balancer.
- **Prompt-injection resistance** — retrieved document text is wrapped in explicit `<context>` tags with a system-prompt instruction to treat that content strictly as data, never as commands. Reduces but does not eliminate the risk of a malicious document trying to steer the model.
- **PII redaction at ingest** — email addresses, US SSNs, credit-card-like numbers, and phone numbers are regex-redacted from extracted text before chunking/embedding (`app/services/pii.py`, toggle via `ENABLE_PII_REDACTION`). This is pattern matching, not a trained PII model - it will miss anything less structured (names, addresses) and is a floor, not a guarantee.
- **No internal error leakage** — exceptions are logged server-side in full; clients get a generic message. Applies to both `/upload` and `/query` (including the SSE error event).
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store`, and HSTS are set on every response.
- **CORS** — restricted to `CORS_ORIGINS` from env and to the three methods actually used (`GET`, `POST`, `DELETE`), not wildcard.

**Still open, by deliberate scope decision, not oversight:**
- No malware/antivirus scanning of uploaded files.
- No per-user/account-level quota beyond IP-based rate limiting (a user with many IPs, or several users behind one IP, aren't distinguished).
- No automated dependency/vulnerability scanning wired into CI (there is no CI at this stage - see PRD non-goals).
- PII redaction is regex-based and English/US-format-biased; it will under-redact other formats.

## Known open problems (see PRD)

- Chroma Cloud free-tier storage/query limits not yet confirmed against expected usage.

## Features added beyond the original PRD

- **Delete / re-upload from the UI** — `DELETE /upload/{filename}` clears a user's chunks and OKF record; re-uploading the same filename replaces rather than duplicates its chunks (see `app/routers/upload.py`).
- **Firestore-backed upload log** — replaces the local-JSON version, which did not persist across Render restarts/deploys (see `app/services/upload_log.py`). Requires Firestore enabled in the same Firebase project (free tier) - no new account needed.
- **MMR + score-threshold retrieval** — addresses the "top-k scores cluster too closely" ambiguity problem: a wider candidate pool is pulled, weak matches (`SCORE_DISTANCE_THRESHOLD`) are dropped, and the rest are reranked for a relevance/diversity balance (`MMR_LAMBDA`) instead of raw similarity order (see `app/services/vectorstore.py`, tunable in `app/config.py`).
- **Streaming answers** — `POST /query/stream` (Server-Sent Events) streams the answer token-by-token instead of waiting for the full completion; the frontend chat now renders incrementally (see `app/routers/query.py`, `app/services/llm.py`, `frontend/src/api/client.js`).
- **OKF metadata layer** — a companion markdown+YAML record per document, stored in Firestore (collection `okf_metadata`, one doc per user+filename, overwritten on re-upload) with provenance + a trust tier derived from ingestion signals (chunk count, OCR fallback). Sequenced to write only after a confirmed successful embed, fixing the earlier bug where a failed ingestion could still leave behind a metadata record claiming success (see `app/services/okf.py`).

## UI

The frontend uses a retro-terminal-meets-Notion look: a dark moss sidebar with a pixel/monospace type (VT323) for navigation and chrome, a light paper-toned reading pane in Inter for actual chat content, and JetBrains Mono for data (filenames, chunk counts, citations). Confidence is shown as a 3-segment pixel meter rather than a colored badge. Icons are `lucide-react` throughout - no emoji anywhere. Favicon is a small pixel document mark at `frontend/public/favicon.svg`.
