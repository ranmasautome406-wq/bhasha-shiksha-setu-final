# 🎓 Bhasha Shiksha Setu — AI-Powered Vernacular Education for Every Learner

**Smart India Hackathon · Problem Statement SIH26042**

A complete full-stack prototype: public website (Student / Teacher / AI Tutor modes),
a secure **Flask backend** with REST APIs, a database-driven **Admin Dashboard**
(users, lessons, content CMS, media library, announcements, AI settings, analytics,
activity log) and AI features (chat tutor, translation, voice input, read-aloud).

```
Frontend → Backend API → Database / AI services → Backend → Frontend
```

---

## 1. Installation

### 1.1 Install Python (3.10+)

- **Windows:** download from [python.org](https://www.python.org/downloads/) — tick **"Add Python to PATH"** during install.
- **macOS:** `brew install python`
- **Ubuntu/Debian:** `sudo apt update && sudo apt install -y python3 python3-pip python3-venv`

Check: `python3 --version`

### 1.2 Create a virtual environment

```bash
cd bhasha-shiksha-setu
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 1.3 Install dependencies

```bash
pip install -r requirements.txt
```

### 1.4 Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` and at minimum change **`SECRET_KEY`** and **`ADMIN_PASSWORD`**.
See [Environment variables](#9-environment-variables).

### 1.5 Initialize the database

The database (SQLite by default) and all tables are created **automatically on first
run**, together with default languages (11 Indian languages), default settings,
one admin account and optional demo data (users + sample lessons).

```bash
python run.py        # first run creates bhasha_shiksha_setu.db
```

### 1.6 Create / reset the admin account

Option A — via `.env` (used automatically at first start):

```
ADMIN_EMAIL=admin@bhasha.setu
ADMIN_PASSWORD=Admin@123
```

Option B — dedicated script (works any time):

```bash
python create_admin.py                    # uses .env values
python create_admin.py me@site.com MySecurePass456   # custom values
```

> ⚠ No password is hardcoded in the code. The admin should change the password
> after the first login (admin → 🔒 button → change password), or via
> `python create_admin.py`.

### 1.7 Run the backend locally

```bash
python run.py
```

Server: **http://localhost:5000**

| URL | What it is |
|---|---|
| `http://localhost:5000/` | Public website (home) |
| `http://localhost:5000/student.html` | Student dashboard |
| `http://localhost:5000/teacher.html` | Teacher dashboard |
| `http://localhost:5000/tutor.html` | AI Tutor chat page |
| `http://localhost:5000/admin` | **Admin login** |

### 1.8 Connect the frontend

Already connected — Flask serves `frontend/` and `admin/` and the pages call
`/api/...` with `fetch()`. To run the frontend on a different host, set this
before loading `script.js`:

```html
<script>window.BSS_CONFIG = { API_BASE: "https://your-backend.com/api" };</script>
```

(and set `CORS_ORIGINS` in the backend `.env` to that site's origin).

### 1.9 Deploy (e.g. Render)

1. Push the project to GitHub (do **not** commit `.env` or `*.db`).
2. On Render → **New Web Service** → pick the repo, `Root Directory: bhasha-shiksha-setu` (or repo root).
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn --bind 0.0.0.0:$PORT run:app`
5. Add environment variables (see below); for production set `SEED_DEMO=false`
   and use a PostgreSQL `DATABASE_URL`.
6. `python create_admin.py` equivalent: set `ADMIN_EMAIL` / `ADMIN_PASSWORD`
   in the Render dashboard before first start.

A `Procfile` (`web: gunicorn --bind 0.0.0.0:$PORT run:app`) is included for
Heroku-style hosts.

### 1.10 Configure the AI API (optional but recommended)

Without any key the whole site still works in **demo mode** (built-in educational
engine). To enable real LLM answers:

```env
AI_PROVIDER=openai
AI_API_KEY=sk-...            # never expose this to the browser
AI_MODEL=gpt-4o-mini
AI_BASE_URL=https://api.openai.com/v1
```

Translation providers: `TRANSLATION_PROVIDER=demo | google | openai`
(Google uses the free, no-key endpoint; OpenAI uses your key).

Voice: `TTS_PROVIDER=browser` uses the free browser Speech Synthesis.
An optional external TTS/STT can be configured with `TTS_URL` / `TTS_API_KEY` /
`STT_URL` / `STT_API_KEY`.

### 1.11 Configure the production database

```env
DATABASE_URL=postgresql://user:password@host:5432/bhasha_shiksha_setu
```

That's the only change needed — SQLAlchemy does the rest. (MySQL works similarly.)

---

## 2. Default Accounts (demo/seed)

| Role | Email | Password |
|---|---|---|
| Admin | `admin@bhasha.setu` | `Admin@123` (change it!) |
| Student | `student@demo.setu` | `Demo@123` |
| Teacher | `teacher@demo.setu` | `Demo@123` |
| Tutor | `tutor@demo.setu` | `Demo@123` |

Set `SEED_DEMO=false` in `.env` to skip demo users/lessons.

---

## 3. Project structure

```
bhasha-shiksha-setu/
├── frontend/                  # public website (served by Flask)
│   ├── index.html             # landing page (announcements, lessons, translate, FAQ)
│   ├── student.html           # student dashboard (progress, saved, recommended)
│   ├── teacher.html           # teacher dashboard (create/edit/publish lessons, uploads)
│   ├── tutor.html             # full AI Tutor chat + voice + student questions
│   ├── script.js              # shared: API client, auth, AI widget, voice, TTS
│   ├── CSS/style.css
│   └── images/
├── admin/                     # Admin dashboard (served at /admin)
│   ├── login.html  dashboard.html  users.html  lessons.html  content.html
│   ├── media.html  announcements.html  ai.html  translations.html  analytics.html
│   ├── activity.html  settings.html  admin.js  assets/ (css + chart.js vendor)
├── backend/
│   ├── app.py                 # Flask factory, CORS, headers, error handlers, static serving
│   ├── config.py              # env-driven configuration
│   ├── database.py            # SQLAlchemy setup (SQLite → PostgreSQL switch)
│   ├── models.py              # users, languages, lessons, lesson_content, translations,
│   │                          # chat_history, media, documents, student_progress,
│   │                          # teacher_content, settings, announcements, activity_logs
│   ├── seed.py                # default languages/settings/admin/demo data
│   ├── utils.py               # JWT auth, RBAC, JSON responses, rate limit, upload validation
│   ├── routes/                # auth · content · student · teacher · tutor · voice · admin
│   ├── services/              # ai_service · translation_service · voice_service · content_service
│   └── uploads/               # uploaded media (served at /uploads/…)
├── tests/test_api.py          # 14 end-to-end API tests (pytest)
├── run.py  create_admin.py  Procfile  requirements.txt  .env.example  .gitignore
└── docs/API.md                # full API reference
```

---

## 4. API documentation

Complete reference in [`docs/API.md`](docs/API.md). Quick tour:

```
GET  /api/health                      → {status, project, problem_statement}
GET  /api/test                        → API is running
GET  /api/config                      → public config + languages + AI status
POST /api/auth/login                  → {token, user}   (JWT, hashed pw, lockout)
POST /api/auth/register               → student self-registration
POST /api/auth/logout · GET /api/auth/me · POST /api/auth/change-password
GET  /api/content                     → website text (CMS-driven, public)
GET  /api/content/announcements       → active announcements (public)
GET  /api/content/faqs                → FAQ list (public)
GET  /api/lessons  /api/lessons/<id>  → published lessons (drafts hidden)
POST /api/translate                   → {text, source_language, target_language}
POST /api/chat · GET /api/chat/history · DELETE /api/chat/history
POST /api/explain                     → explain a lesson by id
GET  /api/student/dashboard · POST /api/student/progress
GET  /api/teacher/dashboard · POST/PUT/DELETE /api/teacher/lessons
GET  /api/tutor/dashboard · POST /api/tutor/chat · GET /api/tutor/questions
GET  /api/admin/dashboard             → stats + charts data (admin only)
GET/POST/PUT/DELETE /api/users        → admin user management (+ /deactivate, /reset-password, /activity)
GET/POST/PUT/DELETE /api/admin/lessons · /media · /documents · /announcements
GET/PUT /api/admin/content/text · /api/admin/settings · /api/admin/languages
GET  /api/admin/analytics · /api/admin/translations · /api/admin/chat-log · /api/admin/activity
GET  /api/voice/voices · POST /api/voice/tts · POST /api/voice/transcribe
```

Every response uses the same envelope:

```json
{ "success": true, "message": "Operation successful", "data": {} }
{ "success": false, "message": "Unauthorized" }
```

Errors are always friendly — raw tracebacks never reach the client.

---

## 5. How the frontend and backend communicate

1. Pages are static HTML **served by Flask** (`frontend/`, `admin/`).
2. `script.js` / `admin.js` talk to the API with `fetch()`:

```js
await fetch("/api/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
  body: JSON.stringify({ message: "Explain photosynthesis", language: "Marathi" }),
});
```

3. Login stores a **JWT** in `localStorage` (`bss_token`) — sent as
   `Authorization: Bearer …` on every protected call.
4. Anonymous visitors get a `guest_id` cookie-less id (`X-Guest-Id` header) so
   the AI widget can keep chat history without an account.
5. Admin changes (announcement, text, settings, lesson) are stored in the
   **database** and the public endpoints read from the database — so what the
   admin saves appears on the website instantly, no frontend edits needed.

---

## 6. Security features

- ✅ Passwords hashed with PBKDF2-SHA256 (never plain text)
- ✅ JWT auth with expiry (24h default) + protected routes + role-based access control (`admin / teacher / student / tutor`)
- ✅ Brute-force lockout (5 failed logins → 15 min), in-memory rate limits on `/api/chat`
- ✅ CORS restricted via `CORS_ORIGINS`
- ✅ Upload validation: allow-list of extensions + MIME checks, size cap, UUID filenames, no dangerous types
- ✅ Input sanitization on all text fields; SQL via SQLAlchemy ORM (no injection)
- ✅ Auth check on **every** admin endpoint; logout; friendly error handler (500 → "Something went wrong")
- ✅ API keys only in `.env` on the server — never in frontend JS, never in the DB
- ✅ Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)

---

## 7. Testing

```bash
python -m pytest tests/ -v
```

The suite (14 tests) covers: health/config, login success + wrong password,
token-protected routes, role access control (student → admin = 403), brute-force
lockout, password change, user CRUD, admin dashboard stats, lesson lifecycle
(draft hidden → publish → visible → delete), student progress, chat + history +
clear, translation, media upload (allowed + rejected), CMS round-trip.

Manual test checklist: log in at `/admin` → dashboard numbers change when you
add users/lessons → Upload in Media → paste `/uploads/…` URL into a lesson →
publish → open the website → create an announcement → it appears on the
homepage → ask the AI assistant → change AI instructions in Settings → ask again.

---

## 8. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev value | JWT signing — **change in production** |
| `DEBUG` | false | Flask debug mode |
| `DATABASE_URL` | `sqlite:///…` | SQLite dev / PostgreSQL prod |
| `AI_PROVIDER` | `demo` | `demo` or `openai` |
| `AI_API_KEY` | *(empty)* | LLM key — server-side only |
| `AI_MODEL` | `gpt-4o-mini` | Model name |
| `AI_BASE_URL` | OpenAI | Any OpenAI-compatible endpoint |
| `TRANSLATION_PROVIDER` | `demo` | `demo` / `google` / `openai` |
| `TTS_PROVIDER` | `browser` | `browser` (free) or external via `TTS_URL` |
| `TTS_URL` / `TTS_API_KEY` / `STT_URL` / `STT_API_KEY` | *(empty)* | optional external speech services |
| `CORS_ORIGINS` | `*` | comma-separated allowed origins |
| `TOKEN_EXPIRY_HOURS` | `24` | JWT lifetime |
| `MAX_UPLOAD_MB` | `50` | upload size cap |
| `ADMIN_NAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` | local dev | first admin account |
| `SEED_DEMO` | `true` | seed demo users/lessons |
| `PORT` | `5000` | server port (Render sets this) |

---

## 9. Notes for the SIH judges / evaluators

- **No fake data**: every dashboard number, lesson, announcement, media item and
  AI setting comes from the database via APIs.
- **Works offline**: demo AI + browser voice + Google translation fallback mean
  the prototype runs with zero external keys; add `AI_API_KEY` to unlock full LLM answers.
- **Admin → everywhere**: change announcement/hero text/AI instructions in the
  admin and refresh the public site to see the change.

## Video Translation & Live Dubbing

The home page now includes a **Video Language Bridge**. It supports:

- Video preview and language selection.
- Uploaded-video dubbing: FFmpeg extracts speech audio, the configured STT service transcribes it, the existing translation service translates it, the configured TTS service generates the target voice, and FFmpeg muxes the new audio back into an MP4.
- Live dubbing in the browser using Web Speech Recognition + the existing `/api/translate` endpoint + browser Speech Synthesis. This mode does not require server STT/TTS keys.

### Uploaded-video dubbing setup

The server needs FFmpeg plus two server-side HTTP services:

- `STT_URL`: accepts JSON with base64 WAV audio and returns `{ "text": "..." }`.
- `TTS_URL`: accepts JSON with `text` and `language`, and returns audio bytes.

Set `STT_URL`, `STT_API_KEY`, `TTS_URL`, and `TTS_API_KEY` in `.env`. Keys are never sent to the browser.

For a Render deployment, make sure FFmpeg is available in the runtime and that the service has enough temporary disk/RAM for video processing.
