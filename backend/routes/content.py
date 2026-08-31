"""
Content routes — /api/content/*
Public website content + /api/translate + /api/explain + /api/chat
(the three endpoints the existing frontend already used).
"""
from flask import Blueprint, request

from backend import __version__
from backend.database import db
from backend.models import ChatMessage, Lesson, User
from backend.services.ai_service import chat, explain_lesson
from backend.services.content_service import get_all_text_content, get_active_announcements, get_faqs
from backend.services.translation_service import translate
from backend.utils import decode_token, fail, ok, sanitize_text
from flask import current_app

bp = Blueprint("content", __name__, url_prefix="/api")

GUEST_KEY = "guest_id"


def _guest_id():
    return sanitize_text(request.headers.get("X-Guest-Id", ""), 64) or None


def _user():
    """Optional auth: attach user if a valid token is present, else None."""
    from flask import g
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload, err = decode_token(auth[7:].strip())
        if not err:
            u = db.session.get(User, int(payload["sub"]))
            if u and u.active:
                g.user = u
                return u
    g.user = None
    return None


# ---------------------------------------------------------------------------
# Health / site config
# ---------------------------------------------------------------------------

@bp.get("/health")
def health():
    return ok({
        "status": "healthy",
        "project": "Bhasha Shiksha Setu",
        "problem_statement": "SIH26042",
        "version": __version__,
    })


@bp.get("/test")
def test():
    return ok({"status": "ok"}, "Bhasha Shiksha Setu API is running.")


@bp.get("/config")
def config():
    """Public config the frontend needs (safe values only — never secrets)."""
    from backend.config import Config
    from backend.models import Language
    langs = Language.query.filter_by(active=True).order_by(Language.sort_order).all()
    return ok({
        "project": "Bhasha Shiksha Setu",
        "tagline": "AI-Powered Vernacular Education for Every Learner",
        "problem_statement": "SIH26042",
        "languages": [l.to_dict() for l in langs],
        "ai_enabled": current_app.config["AI_PROVIDER"] != "off",
        "tts_browser_default": current_app.config["TTS_PROVIDER"] == "browser",
        "ai_provider": Config.public_settings(),
    })


# ---------------------------------------------------------------------------
# Text content, announcements, FAQ (Admin CMS drives these)
# ---------------------------------------------------------------------------

@bp.get("/content")
def get_content():
    return ok(get_all_text_content())


@bp.get("/content/announcements")
def announcements():
    items = get_active_announcements()
    return ok([a.to_dict() for a in items])


@bp.get("/settings")
def public_settings():
    """Sanitized public settings — never includes secrets or API keys."""
    from backend.utils import get_setting
    from backend.models import Language
    langs = Language.query.filter_by(active=True).order_by(Language.sort_order).all()
    return ok({
        "website_name": get_setting("website_name", "Bhasha Shiksha Setu"),
        "tagline": get_setting("tagline", "AI-Powered Vernacular Education for Every Learner"),
        "logo": get_setting("logo", ""),
        "favicon": get_setting("favicon", ""),
        "theme_mode": get_setting("theme_mode", "light"),
        "default_language": get_setting("default_language", "English"),
        "ai_enabled": get_setting("ai_enabled", "true") == "true",
        "voice_input_enabled": get_setting("voice_input_enabled", "true") == "true",
        "voice_output_enabled": get_setting("voice_output_enabled", "true") == "true",
        "contact_email": get_setting("contact_email", ""),
        "contact_phone": get_setting("contact_phone", ""),
        "social_twitter": get_setting("social_twitter", ""),
        "social_instagram": get_setting("social_instagram", ""),
        "social_youtube": get_setting("social_youtube", ""),
        "languages": [l.to_dict() for l in langs],
        "ai_model_display": get_setting("ai_model_display", current_app.config["AI_MODEL"]),
        "ai_provider": current_app.config["AI_PROVIDER"],
    })


@bp.get("/site-info")
def site_info():
    """Public site branding/contact info — driven by Admin → Settings."""
    from backend.utils import get_setting
    return ok({
        "website_name": get_setting("website_name", "Bhasha Shiksha Setu"),
        "tagline": get_setting("tagline", "AI-Powered Vernacular Education for Every Learner"),
        "logo": get_setting("logo", ""),
        "footer_text": get_setting("footer_text", ""),
        "contact_email": get_setting("contact_email", ""),
        "contact_phone": get_setting("contact_phone", ""),
        "social_twitter": get_setting("social_twitter", ""),
        "social_instagram": get_setting("social_instagram", ""),
        "social_youtube": get_setting("social_youtube", ""),
        "social_linkedin": get_setting("social_linkedin", ""),
    })


@bp.get("/content/faqs")
def faqs():
    return ok(get_faqs())


# ---------------------------------------------------------------------------
# Lessons (public, published only for students)
# ---------------------------------------------------------------------------

@bp.get("/lessons")
def list_lessons():
    include_drafts = False
    from backend.utils import decode_token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload, err = decode_token(auth[7:].strip())
        if not err:
            u = db.session.get(User, int(payload["sub"]))
            if u and u.role in ("admin", "teacher"):
                include_drafts = True

    query = Lesson.query
    if not include_drafts:
        query = query.filter_by(status="published")

    subject = request.args.get("subject")
    language = request.args.get("language")
    grade = request.args.get("grade")
    q = request.args.get("q")
    if subject:
        query = query.filter(Lesson.subject.ilike(f"%{subject}%"))
    if language:
        query = query.filter(Lesson.language.ilike(f"%{language}%"))
    if grade:
        query = query.filter(Lesson.grade.ilike(f"%{grade}%"))
    if q:
        query = query.filter(db.or_(Lesson.title.ilike(f"%{q}%"),
                                    Lesson.description.ilike(f"%{q}%")))

    lessons = query.order_by(Lesson.updated_at.desc()).limit(200).all()
    return ok([l.to_dict() for l in lessons])


@bp.get("/lessons/subjects")
def subjects():
    rows = db.session.query(Lesson.subject, db.func.count(Lesson.id)) \
        .filter_by(status="published").group_by(Lesson.subject).all()
    return ok([{"subject": s, "count": c} for s, c in rows])


@bp.get("/lessons/<int:lesson_id>")
def get_lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return fail("Lesson not found.", 404)
    if lesson.status != "published":
        user = _user()
        if not user or user.role not in ("admin", "teacher"):
            return fail("This lesson is not published yet.", 404)
    lesson.views = (lesson.views or 0) + 1
    db.session.commit()
    return ok(lesson.to_dict(full=True))


# ---------------------------------------------------------------------------
# AI Assistant chat, history, explain, translate
# ---------------------------------------------------------------------------

@bp.post("/chat")
def chat_endpoint():
    data = request.get_json(silent=True) or {}
    message = sanitize_text(data.get("message", ""), 2000)
    language = sanitize_text(data.get("language", "English"), 40)
    context = sanitize_text(data.get("context", "general"), 40)
    if not message:
        return fail("Please type a question first.", 400)
    if context not in ("general", "lesson", "tutor"):
        context = "general"

    # Enrich with lesson content when the question comes from inside a lesson
    if context == "lesson":
        try:
            lesson = db.session.get(Lesson, int(data.get("lesson_id") or 0))
            if lesson:
                body = "\n".join(c.content for c in lesson.content_items if c.type == "text")[:2500]
                message = (f"Lesson: {lesson.title} ({lesson.subject}, {lesson.language})\n"
                           f"Content: {body or lesson.description}\n\n"
                           f"Student question: {message}")
        except (TypeError, ValueError):
            pass

    user = _user()
    reply, err = chat(message, language=language, user=user,
                      guest_id=data.get("guest_id") or _guest_id(), context=context)
    if err:
        return fail(err, 429 if "wait" in err else 400)
    return ok({"reply": reply, "demo_mode": False}, "Answer ready.")


@bp.get("/chat/history")
def chat_history():
    user = _user()
    guest = _guest_id()
    limit = min(int(request.args.get("limit", 20)), 100)
    q = ChatMessage.query
    if user:
        q = q.filter(db.or_(ChatMessage.user_id == user.id,
                            (ChatMessage.guest_id == guest) & (ChatMessage.user_id.is_(None))))
    elif guest:
        q = q.filter(ChatMessage.guest_id == guest)
    else:
        q = q.filter(db.false())
    msgs = q.order_by(ChatMessage.created_at.desc()).limit(limit).all()
    return ok([m.to_dict() for m in reversed(msgs)])


@bp.delete("/chat/history")
def clear_chat_history():
    user = _user()
    guest = _guest_id()
    if user:
        ChatMessage.query.filter(db.or_(ChatMessage.user_id == user.id,
                                        ChatMessage.guest_id == guest)).delete()
    elif guest:
        ChatMessage.query.filter(ChatMessage.guest_id == guest).delete()
    else:
        return fail("Nothing to clear.", 400)
    db.session.commit()
    return ok(message="Chat history cleared.")


@bp.post("/explain")
def explain():
    data = request.get_json(silent=True) or {}
    lesson_id = data.get("lesson_id")
    question = sanitize_text(data.get("question", ""), 1000)
    language = sanitize_text(data.get("language", "English"), 40)

    try:
        lesson_id = int(lesson_id)
    except (TypeError, ValueError):
        return fail("Please provide a valid lesson_id.", 400)

    reply, err = explain_lesson(lesson_id, question, language, _user())
    if err:
        return fail(err, 404)
    return ok({"lesson_id": lesson_id, "explanation": reply})


@bp.post("/translate")
def translate_endpoint():
    data = request.get_json(silent=True) or {}
    text = sanitize_text(data.get("text", ""), 2500)
    source = sanitize_text(data.get("source_language", "English"), 40) or "English"
    target = sanitize_text(data.get("target_language", "Marathi"), 40) or "Marathi"
    if not text.strip():
        return fail("Please enter some text to translate.", 400)
    result, provider = translate(text, source, target, _user())
    return ok({"translated_text": result, "provider": provider}, "Translated.")
