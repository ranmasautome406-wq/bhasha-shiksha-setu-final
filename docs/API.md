# Bhasha Shiksha Setu — API Reference

Base URL: `http://localhost:5000`  ·  all routes prefixed with `/api`

## Response envelope

```json
{ "success": true,  "message": "Operation successful", "data": {} }
{ "success": false, "message": "Unauthorized" }
```

## Authentication

- Login returns a JWT: `POST /api/auth/login` → `{ token, user }`
- Send it on protected calls: `Authorization: Bearer <token>`
- Tokens expire (default 24 h). 401 responses mean "re-login".
- Roles: `admin`, `teacher`, `student`, `tutor` (RBAC enforced on every protected route).

---

## 1. Public / system

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | `{ status: "healthy", project: "Bhasha Shiksha Setu", problem_statement: "SIH26042" }` |
| GET | `/api/test` | Ping test |
| GET | `/api/config` | Public config: languages, AI/voice availability (no secrets) |
| GET | `/api/content` | All website text content (CMS-driven) |
| GET | `/api/content/announcements` | Active announcements (public) |
| GET | `/api/content/faqs` | FAQ list (public) |
| GET | `/api/site-info` | Branding/contact from Admin → Settings |
| GET | `/api/lessons` | Published lessons (`?subject=&language=&grade=&q=`) |
| GET | `/api/lessons/subjects` | Subject counts |
| GET | `/api/lessons/<id>` | Lesson detail incl. content blocks (drafts → 404 for public) |

## 2. Auth

| Method | Endpoint | Body | Notes |
|---|---|---|---|
| POST | `/api/auth/login` | `{identifier, password}` | email or name; 429 after 5 fails / 15 min |
| POST | `/api/auth/register` | `{name, email, password, language_preference}` | students only |
| POST | `/api/auth/logout` | — | auth |
| GET | `/api/auth/me` | — | current user |
| POST | `/api/auth/change-password` | `{current_password, new_password}` | auth |

## 3. AI / translation / voice

| Method | Endpoint | Body | Description |
|---|---|---|---|
| POST | `/api/chat` | `{message, language, context?, lesson_id?, guest_id?}` | AI Tutor answer; saved to history; rate-limited |
| GET | `/api/chat/history?limit=20` | — | user/guest chat history |
| DELETE | `/api/chat/history` | — | clear history |
| POST | `/api/explain` | `{lesson_id, question?, language?}` | explain a lesson |
| POST | `/api/translate` | `{text, source_language, target_language}` | returns `{translated_text, provider}` |
| GET | `/api/voice/voices` | — | browser voice availability |
| POST | `/api/voice/tts` | `{text, language}` | external TTS (if configured) |
| POST | `/api/voice/transcribe` | `{audio, language}` | external STT (if configured) |

> Voice input/output primarily use the **browser** Web Speech APIs — free and key-less.

## 4. Student

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/student/dashboard` | profile, stats, recent/completed/saved/recommended, progress |
| GET | `/api/student/progress` | all progress rows |
| POST | `/api/student/progress` | `{lesson_id, progress?, status?, saved?}` |
| POST | `/api/student/lessons/<id>/save` | toggle saved |
| GET | `/api/student/stats` | this student's AI/translation counts |
| PUT | `/api/student/language` | update language preference |

## 5. Teacher (teacher or admin)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/teacher/dashboard` | own lessons + stats |
| POST | `/api/teacher/lessons` | create (title, subject, grade, language, status, content_items[]) |
| PUT | `/api/teacher/lessons/<id>` | update (own lessons only for non-admin) |
| DELETE | `/api/teacher/lessons/<id>` | delete |
| POST | `/api/teacher/lessons/<id>/publish` | toggle publish |
| GET | `/api/teacher/students` | student progress on own lessons |
| GET | `/api/teacher/activity` | recent activity feed |
| POST | `/api/teacher/content` | attach notes to a lesson |

## 6. Tutor (tutor or admin)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/tutor/dashboard` | tutor stats |
| POST | `/api/tutor/chat` | AI chat in tutor context |
| GET | `/api/tutor/questions` | recent student questions |

## 7. Admin (admin only)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/admin/dashboard` | stats + 14-day activity + top languages/topics + recent activity |
| GET | `/api/users` | `?q=&role=&status=` — also at `/api/admin/users` |
| POST | `/api/users` | create user (any role) |
| PUT / DELETE | `/api/users/<id>` | update / delete |
| POST | `/api/users/<id>/deactivate` | toggle active |
| POST | `/api/users/<id>/reset-password` | `{new_password}` |
| GET | `/api/users/<id>/activity` | user's activity log |
| GET | `/api/admin/lessons` | all lessons (`?q=&status=`) |
| GET / PUT | `/api/admin/content/text` | website text CMS (hero, about, FAQ, AI info…) |
| GET / POST | `/api/admin/media` | list / upload (`multipart/form-data`: file, title, description) |
| PUT / DELETE | `/api/admin/media/<id>` | edit meta / delete file |
| GET / POST / DELETE | `/api/admin/documents` | study documents |
| GET / POST / PUT / DELETE | `/api/admin/announcements` | announcements |
| GET / POST / PUT / DELETE | `/api/admin/languages` | language management |
| GET / PUT | `/api/admin/settings` | general/contact/AI/voice settings (no secrets ever) |
| GET | `/api/admin/ai-usage` | AI analytics: daily series, language pairs, topics, demo share |
| GET | `/api/admin/activity` | global activity log (`?action=` filter) |

## 8. Example payloads

```jsonc
// POST /api/translate
{ "text": "Explain photosynthesis", "source_language": "English", "target_language": "Marathi" }
// → { "success": true, "data": { "translated_text": "…", "provider": "demo" } }

// POST /api/chat
{ "message": "Explain photosynthesis in Marathi", "language": "Marathi", "user_id": 123 }
// → { "success": true, "data": { "reply": "प्रकाशसंश्लेषण म्हणजे…" } }

// Content block shape (lessons)
{ "type": "text" | "image" | "video" | "document", "title": "…", "content": "…", "url": "…", "sort_order": 0 }
```
