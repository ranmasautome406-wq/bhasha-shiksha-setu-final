"""
Content service — reusable logic shared by the public content routes and
the admin CMS (headings, paragraphs, announcements, FAQs, AI Tutor info,
media + documents).
"""
from backend.database import db
from backend.models import Announcement, Setting
from backend.utils import get_setting, sanitize_text

# Keys of static-text settings the website reads. Admin edits these in the CMS.
TEXT_CONTENT_KEYS = [
    "hero_title", "hero_subtitle", "about_text", "features_text",
    "announcements_note", "faq", "ai_tutor_info", "footer_text",
]

DEFAULT_TEXT_CONTENT = {
    "hero_title": "Learn in the Language You Understand.",
    "hero_subtitle": ("Bhasha Shiksha Setu brings AI-powered lessons, translation and a "
                      "personal AI Tutor to every student — in Marathi, Hindi, Gujarati, "
                      "Bengali, Tamil, Telugu, Kannada, Malayalam, Punjabi, Urdu and English."),
    "about_text": ("Bhasha Shiksha Setu (SIH26042) is an AI-powered vernacular education "
                   "platform. It breaks the language barrier in classrooms so every learner "
                   "understands every concept — in their own language."),
    "features_text": "",
    "announcements_note": "",
    "faq": "[]",
    "ai_tutor_info": ("Meet Bhasha AI Tutor — your 24×7 study friend. Ask any question, "
                      "in any language, by typing or voice. Get simple explanations, "
                      "examples and study guidance instantly."),
    "footer_text": "Made with ❤️ for the Smart India Hackathon (SIH26042).",
}


def get_all_text_content():
    """Return all editable text content as a dict (with defaults)."""
    out = {}
    for key, default in DEFAULT_TEXT_CONTENT.items():
        out[key] = get_setting(key, default)
    return out


def update_text_content(payload):
    """Safely update text settings from an admin request (title->slug mapping)."""
    changed = []
    for key in TEXT_CONTENT_KEYS:
        if key in payload:
            value = payload[key]
            if key == "faq" and not isinstance(value, str):
                import json
                value = json.dumps(value, ensure_ascii=False)
            row = db.session.get(Setting, key)
            if row:
                row.value = sanitize_text(value, 20000)
            else:
                db.session.add(Setting(key=key, value=sanitize_text(value, 20000)))
            changed.append(key)
    db.session.commit()
    return changed


def get_active_announcements(limit=10):
    """Announcements shown on the public website (active + within schedule)."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return (Announcement.query
            .filter_by(active=True)
            .filter(db.or_(Announcement.start_date.is_(None), Announcement.start_date <= now))
            .filter(db.or_(Announcement.end_date.is_(None), Announcement.end_date >= now))
            .order_by(Announcement.priority.desc(), Announcement.created_at.desc())
            .limit(limit).all())


def get_faqs():
    """Parse stored FAQ JSON into a list — safe for the frontend."""
    import json
    raw = get_setting("faq", "[]")
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def display_safe(value):
    """Very small helper: keep plain text, avoid raw HTML injection."""
    return sanitize_text(value)
