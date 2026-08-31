"""
Admin routes — /api/admin/*
  dashboard stats, users CRUD, media library, documents, settings,
  announcements, AI settings, AI usage analytics, activity logs.
Every route is protected by roles_required('admin').
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, request

from backend.config import Config
from backend.database import db
from backend.models import (
    ActivityLog, Announcement, ChatMessage, Document, Language, Lesson,
    Media, Setting, StudentProgress, Translation, User,
)
from backend.routes.teacher import create_lesson, delete_lesson, update_lesson
from backend.services.content_service import (
    DEFAULT_TEXT_CONTENT, TEXT_CONTENT_KEYS, update_text_content,
)
from backend.utils import (
    fail, get_setting, hash_password, log_activity, ok,
    roles_required, sanitize_text, set_settings, valid_email, valid_password,
)

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ===========================================================================
# Dashboard statistics (all values come from the DATABASE)
# ===========================================================================
@bp.get("/dashboard")
@roles_required("admin")
def dashboard():
    def count(model, **filters):
        q = model.query
        for k, v in filters.items():
            q = q.filter(getattr(model, k) == v)
        return q.count()

    total_users = count(User)
    active_users = count(User, active=True)
    now = datetime.now(timezone.utc)
    recent_users = User.query.filter(User.last_login >= now - timedelta(days=7)).count()

    # AI usage analytics
    ai_questions = count(ChatMessage)
    translations = count(Translation)
    voice_requests = Translation.query.filter(Translation.provider == "voice").count()

    # Chart data — last 14 days of activity
    days = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        days.append({
            "date": day.strftime("%Y-%m-%d"),
            "ai_questions": ChatMessage.query.filter(
                ChatMessage.created_at >= start, ChatMessage.created_at < end).count(),
            "translations": Translation.query.filter(
                Translation.created_at >= start, Translation.created_at < end,
                Translation.provider != "voice").count(),
            "new_users": User.query.filter(
                User.created_at >= start, User.created_at < end).count(),
        })

    # Most requested languages in chat (last 500 messages)
    lang_rows = (db.session.query(ChatMessage.language, db.func.count(ChatMessage.id))
                 .group_by(ChatMessage.language)
                 .order_by(db.func.count(ChatMessage.id).desc()).limit(10).all())

    # Most discussed topics: simple keyword extraction from chat messages
    from collections import Counter
    import re
    topics = Counter()
    for (msg,) in db.session.query(ChatMessage.message).order_by(
            ChatMessage.created_at.desc()).limit(300).all():
        for word in re.findall(r"\b[a-zA-Z]{5,}\b", (msg or "").lower()):
            if word not in {"which", "what", "please", "explain", "about", "this",
                            "that", "there", "their", "would", "could", "should",
                            "bhasha", "shiksha", "setu"}:
                topics[word] += 1
    topic_rows = [{"topic": k, "count": v} for k, v in topics.most_common(10)]

    # Role distribution + recent activity
    role_rows = []
    for role in User.VALID_ROLES:
        role_rows.append({"role": role, "count": count(User, role=role)})

    recent_activity = (ActivityLog.query.order_by(ActivityLog.created_at.desc())
                       .limit(12).all())

    # ---- Trend deltas: today vs yesterday ----
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    yest_start = today_start - timedelta(days=1)
    day_end = now + timedelta(days=1)

    def between(model, col, start, end, extra=None):
        q = model.query.filter(col >= start, col < end)
        if extra:
            for k, v in extra.items():
                q = q.filter(getattr(model, k) == v)
        return q.count()

    def delta(model, col, extra=None):
        return (between(model, col, today_start, day_end, extra)
                - between(model, col, yest_start, today_start, extra))

    trends = {
        "new_users": delta(User, User.created_at),
        "ai_questions": delta(ChatMessage, ChatMessage.created_at),
        "translations": delta(Translation, Translation.created_at),
        "voice_requests": (between(Translation, Translation.created_at, today_start, day_end, {"provider": "voice"})
                           - between(Translation, Translation.created_at, yest_start, today_start, {"provider": "voice"})),
        "lessons_views": 0,  # historical per-day views are not tracked retroactively
    }
    today = {
        "ai_questions": between(ChatMessage, ChatMessage.created_at, today_start, day_end),
        "translations": between(Translation, Translation.created_at, today_start, day_end),
        "new_users": between(User, User.created_at, today_start, day_end),
    }

    # ---- Lesson completion analytics ----
    total_progress = StudentProgress.query.count()
    completed_progress = StudentProgress.query.filter_by(status="completed").count()
    completion_rate = round(100 * completed_progress / total_progress) if total_progress else 0
    subj_rows = (db.session.query(Lesson.subject, db.func.count(StudentProgress.id))
                 .join(StudentProgress, StudentProgress.lesson_id == Lesson.id)
                 .filter(StudentProgress.status == "completed")
                 .group_by(Lesson.subject).all())

    return ok({
        "trends": trends,
        "today": today,
        "completion": {
            "total": total_progress, "completed": completed_progress,
            "rate": completion_rate,
            "by_subject": [{"subject": s or "Other", "count": c} for s, c in subj_rows],
        },
        "stats": {
            "total_students": count(User, role="student"),
            "total_teachers": count(User, role="teacher"),
            "total_tutors": count(User, role="tutor"),
            "total_admins": count(User, role="admin"),
            "total_users": total_users,
            "active_users": active_users,
            "recently_active_users": recent_users,
            "total_lessons": count(Lesson),
            "published_lessons": count(Lesson, status="published"),
            "total_translations": translations,
            "total_ai_questions": ai_questions,
            "total_voice_requests": voice_requests,
            "total_media": count(Media),
            "total_announcements": count(Announcement),
        },
        "activity_14days": days,
        "top_languages": [{"language": lang or "Unknown", "count": c} for lang, c in lang_rows],
        "top_topics": topic_rows,
        "roles": role_rows,
        "recent_activity": [a.to_dict() for a in recent_activity],
    })


# ===========================================================================
# User management
# ===========================================================================
@bp.get("/users")
@roles_required("admin")
def list_users():
    q = User.query
    role = request.args.get("role")
    search = request.args.get("q")
    status = request.args.get("status")
    if role in User.VALID_ROLES:
        q = q.filter(User.role == role)
    if status in ("active", "inactive"):
        q = q.filter(User.active == (status == "active"))
    if search:
        like = f"%{sanitize_text(search, 100)}%"
        q = q.filter(db.or_(User.name.ilike(like), User.email.ilike(like)))
    users = q.order_by(User.created_at.desc()).limit(500).all()
    return ok([u.to_dict() for u in users])


@bp.post("/users")
@roles_required("admin")
def create_user():
    data = request.get_json(silent=True) or {}
    name = sanitize_text(data.get("name", "")).strip()
    email = sanitize_text(data.get("email", "")).strip().lower()
    role = sanitize_text(data.get("role", "student")).strip().lower()
    password = str(data.get("password", ""))

    if not name:
        return fail("Name is required.", 400)
    if not valid_email(email):
        return fail("Valid email is required.", 400)
    if role not in User.VALID_ROLES:
        return fail("Role must be one of: student, teacher, tutor, admin.", 400)
    if not valid_password(password):
        return fail("Password must be at least 6 characters.", 400)
    if User.query.filter(db.func.lower(User.email) == email).first():
        return fail("An account with this email already exists.", 409)

    user = User(name=name, email=email, role=role, password_hash=hash_password(password),
                language_preference=sanitize_text(data.get("language_preference", "English"), 40))
    db.session.add(user)
    db.session.commit()
    log_activity(g.user, "user_created", f"{name} ({role})")
    return ok(user.to_dict(), "User created.", 201)


@bp.put("/users/<int:user_id>")
@roles_required("admin")
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return fail("User not found.", 404)
    data = request.get_json(silent=True) or {}

    if "name" in data and data["name"]:
        user.name = sanitize_text(data["name"]).strip()
    if "email" in data:
        email = sanitize_text(data["email"]).strip().lower()
        if not valid_email(email):
            return fail("Valid email is required.", 400)
        clash = User.query.filter(db.func.lower(User.email) == email,
                                  User.id != user.id).first()
        if clash:
            return fail("Another account already uses this email.", 409)
        user.email = email
    if data.get("role") in User.VALID_ROLES:
        user.role = data["role"]
    if "active" in data:
        user.active = bool(data["active"])
    if "language_preference" in data:
        user.language_preference = sanitize_text(data["language_preference"], 40)

    db.session.commit()
    log_activity(g.user, "user_updated", f"{user.name} ({user.role})")
    return ok(user.to_dict(), "User updated.")


@bp.delete("/users/<int:user_id>")
@roles_required("admin")
def delete_user(user_id):
    if user_id == g.user.id:
        return fail("You cannot delete your own account.", 400)
    user = db.session.get(User, user_id)
    if not user:
        return fail("User not found.", 404)
    name = user.name
    db.session.delete(user)
    db.session.commit()
    log_activity(g.user, "user_deleted", name)
    return ok(message="User deleted.")


@bp.post("/users/<int:user_id>/deactivate")
@roles_required("admin")
def deactivate_user(user_id):
    if user_id == g.user.id:
        return fail("You cannot deactivate your own account.", 400)
    user = db.session.get(User, user_id)
    if not user:
        return fail("User not found.", 404)
    user.active = not user.active
    db.session.commit()
    log_activity(g.user, "user_deactivate" if not user.active else "user_activate", user.name)
    return ok(user.to_dict(), "User deactivated." if not user.active else "User activated.")


@bp.post("/users/<int:user_id>/reset-password")
@roles_required("admin")
def reset_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return fail("User not found.", 404)
    data = request.get_json(silent=True) or {}
    new_password = str(data.get("new_password", ""))
    if not valid_password(new_password):
        return fail("New password must be at least 6 characters.", 400)
    user.password_hash = hash_password(new_password)
    db.session.commit()
    log_activity(g.user, "password_reset", f"Password reset for {user.name}")
    return ok(message="Password reset successfully.")


@bp.get("/users/<int:user_id>/activity")
@roles_required("admin")
def user_activity(user_id):
    logs = (ActivityLog.query.filter_by(user_id=user_id)
            .order_by(ActivityLog.created_at.desc()).limit(50).all())
    return ok([l.to_dict() for l in logs])


# ===========================================================================
# Lessons (admin can manage ALL lessons)
# ===========================================================================
@bp.get("/lessons")
@roles_required("admin")
def all_lessons():
    q = Lesson.query
    status = request.args.get("status")
    if status in ("draft", "published"):
        q = q.filter(Lesson.status == status)
    search = request.args.get("q")
    if search:
        like = f"%{sanitize_text(search, 100)}%"
        q = q.filter(db.or_(Lesson.title.ilike(like), Lesson.subject.ilike(like)))
    lessons = q.order_by(Lesson.updated_at.desc()).limit(500).all()
    return ok([l.to_dict() for l in lessons])


# ===========================================================================
# Text CMS content
# ===========================================================================
@bp.get("/content/text")
@roles_required("admin")
def admin_text_content():
    return ok({
        "keys": TEXT_CONTENT_KEYS,
        "content": get_setting_all(),
    })


def get_setting_all():
    return {k: get_setting(k, DEFAULT_TEXT_CONTENT.get(k, "")) for k in TEXT_CONTENT_KEYS}


@bp.put("/content/text")
@roles_required("admin")
def save_text_content():
    data = request.get_json(silent=True) or {}
    changed = update_text_content(data)
    log_activity(g.user, "content_updated", f"Text content: {', '.join(changed)}")
    return ok(get_setting_all(), "Content updated.")


# ===========================================================================
# Media library (upload / list / delete)
# ===========================================================================
@bp.get("/media")
@roles_required("admin", "teacher")
def list_media():
    rows = Media.query.order_by(Media.created_at.desc()).limit(500).all()
    return ok([m.to_dict() for m in rows])


@bp.post("/media")
@roles_required("admin", "teacher")
def upload_media():
    if "file" not in request.files:
        return fail("No file selected.", 400)
    file = request.files["file"]
    from backend.utils import validate_upload
    ok_type, err = validate_upload(file.filename, file.mimetype)
    if not ok_type:
        return fail(err, 400)

    ext = file.filename.rsplit(".", 1)[-1].lower()
    stored = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(current_app.config["UPLOAD_DIR"], exist_ok=True)
    file.save(os.path.join(current_app.config["UPLOAD_DIR"], stored))

    from backend.utils import detect_file_type
    _, ftype = detect_file_type(file.filename)
    media = Media(
        filename=stored,
        original_name=sanitize_text(file.filename, 200),
        file_type=ftype,
        mime_type=file.mimetype or "",
        size=os.path.getsize(os.path.join(current_app.config["UPLOAD_DIR"], stored)),
        title=sanitize_text(request.form.get("title", ""), 200),
        description=sanitize_text(request.form.get("description", ""), 2000),
        uploaded_by=g.user.id,
    )
    db.session.add(media)
    db.session.commit()
    log_activity(g.user, "media_upload", f"{media.original_name} ({media.size//1024} KB)")
    return ok(media.to_dict(), "File uploaded.", 201)


@bp.put("/media/<int:media_id>")
@roles_required("admin")
def update_media(media_id):
    media = db.session.get(Media, media_id)
    if not media:
        return fail("File not found.", 404)
    data = request.get_json(silent=True) or {}
    if "title" in data:
        media.title = sanitize_text(data["title"], 200)
    if "description" in data:
        media.description = sanitize_text(data["description"], 2000)
    db.session.commit()
    return ok(media.to_dict(), "Media updated.")


@bp.delete("/media/<int:media_id>")
@roles_required("admin", "teacher")
def delete_media(media_id):
    media = db.session.get(Media, media_id)
    if not media:
        return fail("File not found.", 404)
    if g.user.role != "admin" and media.uploaded_by != g.user.id:
        return fail("You can only delete your own uploads.", 403)
    path = os.path.join(current_app.config["UPLOAD_DIR"], media.filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    name = media.original_name
    db.session.delete(media)
    db.session.commit()
    log_activity(g.user, "media_deleted", name)
    return ok(message="File deleted.")


# ===========================================================================
# Documents (PDF / notes / study material)
# ===========================================================================
@bp.get("/documents")
@roles_required("admin", "teacher")
def list_documents():
    rows = Document.query.order_by(Document.created_at.desc()).limit(500).all()
    return ok([d.to_dict() for d in rows])


@bp.post("/documents")
@roles_required("admin", "teacher")
def create_document():
    data = request.get_json(silent=True) or {}
    title = sanitize_text(data.get("title", "")).strip()
    if not title:
        return fail("Document title is required.", 400)
    doc = Document(
        title=title,
        description=sanitize_text(data.get("description", ""), 2000),
        category=sanitize_text(data.get("category", "Study Material"), 100),
        media_id=None if not data.get("media_id") else int(data["media_id"]),
        uploaded_by=g.user.id,
    )
    db.session.add(doc)
    db.session.commit()
    log_activity(g.user, "document_added", title)
    return ok(doc.to_dict(), "Document added.", 201)


@bp.delete("/documents/<int:doc_id>")
@roles_required("admin")
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return fail("Document not found.", 404)
    db.session.delete(doc)
    db.session.commit()
    log_activity(g.user, "document_deleted", doc.title)
    return ok(message="Document deleted.")


# ===========================================================================
# Announcements
# ===========================================================================
@bp.get("/announcements")
@roles_required("admin")
def list_announcements():
    rows = Announcement.query.order_by(Announcement.created_at.desc()).limit(200).all()
    return ok([a.to_dict() for a in rows])


def _parse_priority(value):
    """Coerce priority to a non-negative int; tolerate strings/bad input."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _parse_dt(value):
    """Accept ISO datetime or plain date strings; tolerate empty values."""
    if not value:
        return None
    if isinstance(value, str):
        value = value.strip().replace("T", " ", 1).replace("Z", "+00:00")
        if value.endswith("+00:00"):
            value = value[:-6]
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                from datetime import date as _date
                return datetime.combine(_date.fromisoformat(value[:10]), datetime.min.time(),
                                        tzinfo=timezone.utc)
            except ValueError:
                return None
    return None


@bp.post("/announcements")
@roles_required("admin")
def create_announcement():
    data = request.get_json(silent=True) or {}
    title = sanitize_text(data.get("title", "")).strip()
    message = sanitize_text(data.get("message", "")).strip()
    if not title or not message:
        return fail("Title and message are required.", 400)
    ann = Announcement(
        title=title, message=message,
        image=sanitize_text(data.get("image", ""), 500),
        priority=_parse_priority(data.get("priority", 0)),
        active=bool(data.get("active", True)),
        start_date=_parse_dt(data.get("start_date")),
        end_date=_parse_dt(data.get("end_date")),
        created_by=g.user.id,
    )
    db.session.add(ann)
    db.session.commit()
    log_activity(g.user, "announcement_created", title)
    return ok(ann.to_dict(), "Announcement published.", 201)


@bp.put("/announcements/<int:ann_id>")
@roles_required("admin")
def update_announcement(ann_id):
    ann = db.session.get(Announcement, ann_id)
    if not ann:
        return fail("Announcement not found.", 404)
    data = request.get_json(silent=True) or {}
    if data.get("title"):
        ann.title = sanitize_text(data["title"]).strip()
    if data.get("message"):
        ann.message = sanitize_text(data["message"]).strip()
    if "image" in data:
        ann.image = sanitize_text(data["image"], 500)
    if "priority" in data:
        ann.priority = _parse_priority(data.get("priority", 0))
    if "active" in data:
        ann.active = bool(data["active"])
    if "start_date" in data:
        ann.start_date = _parse_dt(data["start_date"])
    if "end_date" in data:
        ann.end_date = _parse_dt(data["end_date"])
    db.session.commit()
    log_activity(g.user, "announcement_updated", ann.title)
    return ok(ann.to_dict(), "Announcement updated.")


@bp.delete("/announcements/<int:ann_id>")
@roles_required("admin")
def delete_announcement(ann_id):
    ann = db.session.get(Announcement, ann_id)
    if not ann:
        return fail("Announcement not found.", 404)
    db.session.delete(ann)
    db.session.commit()
    log_activity(g.user, "announcement_deleted", ann.title)
    return ok(message="Announcement deleted.")


# ===========================================================================
# Languages
# ===========================================================================
@bp.get("/languages")
@roles_required("admin")
def list_languages():
    rows = Language.query.order_by(Language.sort_order).all()
    return ok([l.to_dict() for l in rows])


@bp.post("/languages")
@roles_required("admin")
def add_language():
    data = request.get_json(silent=True) or {}
    name = sanitize_text(data.get("name", "")).strip()
    code = sanitize_text(data.get("code", "")).strip().lower()
    if not name or not code:
        return fail("Language name and code are required.", 400)
    if Language.query.filter(db.or_(Language.name.ilike(name),
                                    Language.code == code)).first():
        return fail("This language already exists.", 409)
    lang = Language(name=name, code=code,
                    native_name=sanitize_text(data.get("native_name", ""), 60),
                    active=bool(data.get("active", True)),
                    sort_order=int(data.get("sort_order", 999) or 999))
    db.session.add(lang)
    db.session.commit()
    log_activity(g.user, "language_added", name)
    return ok(lang.to_dict(), "Language added.", 201)


@bp.put("/languages/<int:lang_id>")
@roles_required("admin")
def update_language(lang_id):
    lang = db.session.get(Language, lang_id)
    if not lang:
        return fail("Language not found.", 404)
    data = request.get_json(silent=True) or {}
    if data.get("name"):
        lang.name = sanitize_text(data["name"]).strip()
    if data.get("code"):
        lang.code = sanitize_text(data["code"]).strip().lower()
    if "native_name" in data:
        lang.native_name = sanitize_text(data["native_name"], 60)
    if "active" in data:
        lang.active = bool(data["active"])
    if "sort_order" in data:
        lang.sort_order = int(data.get("sort_order", 999) or 999)
    if "is_default" in data and data["is_default"]:
        Language.query.update({Language.is_default: False})
        lang.is_default = True
    db.session.commit()
    log_activity(g.user, "language_updated", lang.name)
    return ok(lang.to_dict(), "Language updated.")


@bp.delete("/languages/<int:lang_id>")
@roles_required("admin")
def delete_language(lang_id):
    lang = db.session.get(Language, lang_id)
    if not lang:
        return fail("Language not found.", 404)
    db.session.delete(lang)
    db.session.commit()
    log_activity(g.user, "language_deleted", lang.name)
    return ok(message="Language deleted.")


# ===========================================================================
# Settings (general / contact / appearance / language / AI / voice)
# ===========================================================================
# keys editable from Admin → Settings (whitelist — safe, never secrets)
SETTING_KEYS = [
    # General
    "website_name", "tagline", "logo", "favicon",
    # Contact
    "contact_email", "contact_phone", "social_facebook", "social_twitter",
    "social_instagram", "social_youtube", "social_linkedin",
    # Appearance
    "theme_mode",   # light | dark
    # Language
    "default_language",
    # AI
    "ai_enabled", "ai_provider_ui", "ai_model_display", "ai_temperature",
    "ai_system_instructions", "ai_about",
    # Voice
    "voice_input_enabled", "voice_output_enabled",
    # Misc
    "footer_text", "announcements_note",
]


@bp.get("/settings")
@roles_required("admin")
def get_settings():
    data = {k: get_setting(k, "") for k in SETTING_KEYS}
    data["default_language"] = data["default_language"] or "English"
    data["ai_enabled"] = data["ai_enabled"] or "true"
    data["voice_input_enabled"] = data["voice_input_enabled"] or "true"
    data["voice_output_enabled"] = data["voice_output_enabled"] or "true"
    data["theme_mode"] = data["theme_mode"] or "light"
    # Public (safe) provider info, never the key itself
    data["config"] = {
        "ai_provider": current_app.config["AI_PROVIDER"],
        "ai_model": current_app.config["AI_MODEL"],
        "translation_provider": current_app.config["TRANSLATION_PROVIDER"],
        "tts_provider": current_app.config["TTS_PROVIDER"],
        "has_api_key": bool(current_app.config["AI_API_KEY"]),
        "database_url_scheme": current_app.config["SQLALCHEMY_DATABASE_URI"].split(":")[0],
    }
    return ok(data)


@bp.put("/settings")
@roles_required("admin")
def save_settings():
    data = request.get_json(silent=True) or {}
    updates = {}
    for key in SETTING_KEYS:
        if key in data:
            updates[key] = sanitize_text(data[key], 20000) if isinstance(data[key], str) \
                else str(data[key])
    if updates:
        set_settings(updates)
    log_activity(g.user, "settings_updated", ", ".join(updates.keys()))
    return ok(updates, "Settings saved.")


# ===========================================================================
# AI usage analytics
# ===========================================================================
@bp.get("/ai-usage")
@roles_required("admin")
def ai_usage():
    now = datetime.now(timezone.utc)
    labels, chat_series, voice_series, trans_series = [], [], [], []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        labels.append(day.strftime("%b %d"))
        chat_series.append(ChatMessage.query.filter(
            ChatMessage.created_at >= start, ChatMessage.created_at < end).count())
        voice_series.append(Translation.query.filter(
            Translation.provider == "voice",
            Translation.created_at >= start, Translation.created_at < end).count())
        trans_series.append(Translation.query.filter(
            Translation.provider != "voice",
            Translation.created_at >= start, Translation.created_at < end).count())

    lang_pairs = (db.session.query(Translation.source_language, Translation.target_language,
                                   db.func.count(Translation.id))
                  .group_by(Translation.source_language, Translation.target_language)
                  .order_by(db.func.count(Translation.id).desc()).limit(10).all())

    from collections import Counter
    import re
    topics = Counter()
    for (msg,) in db.session.query(ChatMessage.message).order_by(
            ChatMessage.created_at.desc()).limit(400).all():
        for word in re.findall(r"\b[a-zA-Z]{5,}\b", (msg or "").lower()):
            if word not in {"which", "what", "please", "explain", "about", "this",
                            "that", "there", "their", "would", "could", "should",
                            "bhasha", "shiksha", "setu", "some", "want", "know"}:
                topics[word] += 1

    return ok({
        "totals": {
            "ai_questions": ChatMessage.query.count(),
            "translations": Translation.query.filter(Translation.provider != "voice").count(),
            "voice_requests": Translation.query.filter(Translation.provider == "voice").count(),
        },
        "daily": {"labels": labels, "chat": chat_series,
                  "voice": voice_series, "translations": trans_series},
        "top_languages": [{"from": s, "to": t, "count": c} for s, t, c in lang_pairs],
        "top_topics": [{"topic": k, "count": v} for k, v in topics.most_common(12)],
        "demo_mode_share": {
            "ai": round(100 * ChatMessage.query.filter_by(demo_mode=True).count()
                        / max(ChatMessage.query.count(), 1)),
            "translations": round(100 * Translation.query.filter_by(provider="demo").count()
                                  / max(Translation.query.filter(Translation.provider != "voice").count(), 1)),
        },
    })


# ===========================================================================
# Analytics (AI usage + growth + completion) — /api/admin/analytics
# ===========================================================================
@bp.get("/analytics")
@roles_required("admin")
def analytics():
    now = datetime.now(timezone.utc)
    labels, chat_series, voice_series, trans_series, user_series = [], [], [], [], []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        labels.append(day.strftime("%b %d"))
        chat_series.append(ChatMessage.query.filter(
            ChatMessage.created_at >= start, ChatMessage.created_at < end).count())
        voice_series.append(Translation.query.filter(
            Translation.provider == "voice",
            Translation.created_at >= start, Translation.created_at < end).count())
        trans_series.append(Translation.query.filter(
            Translation.provider != "voice",
            Translation.created_at >= start, Translation.created_at < end).count())
        user_series.append(User.query.filter(
            User.created_at >= start, User.created_at < end).count())

    lang_pairs = (db.session.query(Translation.source_language, Translation.target_language,
                                   db.func.count(Translation.id))
                  .group_by(Translation.source_language, Translation.target_language)
                  .order_by(db.func.count(Translation.id).desc()).limit(12).all())

    chat_langs = (db.session.query(ChatMessage.language, db.func.count(ChatMessage.id))
                  .group_by(ChatMessage.language)
                  .order_by(db.func.count(ChatMessage.id).desc()).limit(8).all())

    from collections import Counter
    import re
    topics = Counter()
    for (msg,) in db.session.query(ChatMessage.message).order_by(
            ChatMessage.created_at.desc()).limit(400).all():
        for word in re.findall(r"\b[a-zA-Z]{5,}\b", (msg or "").lower()):
            if word not in {"which", "what", "please", "explain", "about", "this",
                            "that", "there", "their", "would", "could", "should",
                            "bhasha", "shiksha", "setu", "some", "want", "know"}:
                topics[word] += 1

    total_progress = StudentProgress.query.count()
    done = StudentProgress.query.filter_by(status="completed").count()

    return ok({
        "totals": {
            "ai_questions": ChatMessage.query.count(),
            "questions_today": ChatMessage.query.filter(
                ChatMessage.created_at >= datetime(now.year, now.month, now.day, tzinfo=timezone.utc)).count(),
            "translations": Translation.query.filter(Translation.provider != "voice").count(),
            "voice_requests": Translation.query.filter(Translation.provider == "voice").count(),
            "demo_share": round(100 * ChatMessage.query.filter_by(demo_mode=True).count()
                                / max(ChatMessage.query.count(), 1)),
        },
        "daily": {"labels": labels, "chat": chat_series, "voice": voice_series,
                  "translations": trans_series, "users": user_series},
        "language_pairs": [{"from": s or "?", "to": t or "?", "count": c} for s, t, c in lang_pairs],
        "chat_languages": [{"language": l or "Unknown", "count": c} for l, c in chat_langs],
        "top_topics": [{"topic": k, "count": v} for k, v in topics.most_common(12)],
        "completion": {"completed": done, "in_progress": max(total_progress - done, 0),
                       "rate": round(100 * done / total_progress) if total_progress else 0},
    })


# ===========================================================================
# Translation log + AI chat log (admin monitoring)
# ===========================================================================
@bp.get("/translations")
@roles_required("admin")
def translation_log():
    q = Translation.query
    lang = request.args.get("lang")
    search = request.args.get("q")
    if lang:
        q = q.filter(db.or_(Translation.source_language == lang,
                            Translation.target_language == lang))
    if search:
        like = f"%{sanitize_text(search, 100)}%"
        q = q.filter(db.or_(Translation.source_text.ilike(like),
                            Translation.translated_text.ilike(like)))
    rows = q.order_by(Translation.created_at.desc()).limit(200).all()
    out = []
    for r in rows:
        user = db.session.get(User, r.user_id) if r.user_id else None
        d = r.to_dict()
        d["user_name"] = user.name if user else "Guest"
        out.append(d)
    return ok(out)


@bp.get("/chat-log")
@roles_required("admin")
def chat_log():
    rows = ChatMessage.query.order_by(ChatMessage.created_at.desc()).limit(40).all()
    out = []
    for r in rows:
        user = db.session.get(User, r.user_id) if r.user_id else None
        d = r.to_dict()
        d["user_name"] = user.name if user else ("Guest" if r.guest_id else "Guest")
        out.append(d)
    return ok(out)


# ===========================================================================
# Activity logs
# ===========================================================================
@bp.get("/activity")
@roles_required("admin")
def activity_logs():
    q = ActivityLog.query
    action = request.args.get("action")
    if action:
        q = q.filter(ActivityLog.action.ilike(f"%{sanitize_text(action, 100)}%"))
    logs = q.order_by(ActivityLog.created_at.desc()).limit(200).all()
    return ok([l.to_dict() for l in logs])


# Uploads are served publicly (validated uploads only) at  /uploads/<filename>
# by the app-level catch-all route in backend/app.py.


# ===========================================================================
# Spec-compatible aliases: /api/users (same admin-protected handlers as
# /api/admin/users — the decorated functions handle auth + RBAC themselves).
# ===========================================================================
alias_bp = Blueprint("admin_api_root", __name__, url_prefix="/api")
alias_bp.add_url_rule("/users", view_func=list_users, endpoint="users_root_list", methods=["GET"])
alias_bp.add_url_rule("/users", view_func=create_user, endpoint="users_root_create", methods=["POST"])
alias_bp.add_url_rule("/users/<int:user_id>", view_func=update_user, endpoint="users_root_update", methods=["PUT"])
alias_bp.add_url_rule("/users/<int:user_id>", view_func=delete_user, endpoint="users_root_delete", methods=["DELETE"])
alias_bp.add_url_rule("/users/<int:user_id>/deactivate", view_func=deactivate_user,
                      endpoint="users_root_deactivate", methods=["POST"])
alias_bp.add_url_rule("/users/<int:user_id>/reset-password", view_func=reset_password,
                      endpoint="users_root_reset", methods=["POST"])
alias_bp.add_url_rule("/users/<int:user_id>/activity", view_func=user_activity,
                      endpoint="users_root_activity", methods=["GET"])
alias_bp.add_url_rule("/lessons", view_func=create_lesson, endpoint="lessons_root_create", methods=["POST"])
alias_bp.add_url_rule("/lessons/<int:lesson_id>", view_func=update_lesson, endpoint="lessons_root_update", methods=["PUT"])
alias_bp.add_url_rule("/lessons/<int:lesson_id>", view_func=delete_lesson, endpoint="lessons_root_delete", methods=["DELETE"])
alias_bp.add_url_rule("/admin/content", view_func=save_text_content,
                      endpoint="admin_content_root", methods=["POST", "PUT"])
