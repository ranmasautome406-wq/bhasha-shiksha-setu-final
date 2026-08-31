"""Seed: default languages, settings, admin account, demo users & lessons."""
from datetime import datetime, timezone

from backend.config import Config
from backend.database import db
from backend.models import (
    Announcement, Language, Lesson, LessonContent, Setting, User,
)
from backend.services.content_service import DEFAULT_TEXT_CONTENT
from backend.utils import hash_password

DEFAULT_LANGUAGES = [
    ("en", "English", "English", True, 1),
    ("mr", "Marathi", "मराठी", False, 2),
    ("hi", "Hindi", "हिन्दी", False, 3),
    ("gu", "Gujarati", "ગુજરાતી", False, 4),
    ("bn", "Bengali", "বাংলা", False, 5),
    ("ta", "Tamil", "தமிழ்", False, 6),
    ("te", "Telugu", "తెలుగు", False, 7),
    ("kn", "Kannada", "ಕನ್ನಡ", False, 8),
    ("ml", "Malayalam", "മലയാളം", False, 9),
    ("pa", "Punjabi", "ਪੰਜਾਬੀ", False, 10),
    ("ur", "Urdu", "اردو", False, 11),
]

DEFAULT_SETTINGS = {
    "website_name": "Bhasha Shiksha Setu",
    "tagline": "AI-Powered Vernacular Education for Every Learner",
    "contact_email": "admin@bhasha.setu",
    "contact_phone": "+91 98765 43210",
    "social_twitter": "https://twitter.com",
    "social_instagram": "https://instagram.com",
    "social_youtube": "https://youtube.com",
    "theme_mode": "light",
    "default_language": "English",
    "ai_enabled": "true",
    "ai_provider_ui": Config.AI_PROVIDER,
    "ai_model_display": Config.AI_MODEL,
    "voice_input_enabled": "true",
    "voice_output_enabled": "true",
    "ai_about": (
        "Bhasha Shiksha Setu is an AI-powered vernacular education platform that helps "
        "students learn in their own language — Marathi, Hindi, Gujarati, Bengali, Tamil, "
        "Telugu, Kannada, Malayalam, Punjabi, Urdu and English. It has three modes: "
        "Student Mode (learn lessons, translate, ask the AI tutor), Teacher Mode (create "
        "lessons, add material, monitor students) and Tutor/AI Tutor Mode (ask the AI "
        "Tutor questions in any language)."
    ),
    "ai_system_instructions": (
        "You are Bhasha AI Tutor, a friendly, patient teacher inside the Bhasha Shiksha "
        "Setu platform. Always answer in the language the student asks in. Keep answers "
        "simple, short and use examples. Encourage the student. Never invent facts about "
        "the platform; if unsure, say so politely."
    ),
    "footer_text": "Made with ❤️ for the Smart India Hackathon (SIH26042).",
    "announcements_note": "Announcements appear on the homepage and inside the Student dashboard.",
}

SAMPLE_LESSONS = [
    {
        "title": "Introduction to Photosynthesis",
        "description": "Understand how green plants make their own food using sunlight, water and carbon dioxide — explained simply.",
        "subject": "Science", "grade": "8", "language": "Marathi",
        "status": "published",
        "content": [
            ("text", "What is Photosynthesis?",
             "Photosynthesis is the process by which green plants prepare their own food. They use sunlight, water (from the soil) and carbon dioxide (from the air). Chlorophyll — the green pigment in leaves — traps sunlight energy. The plant makes glucose (sugar) and releases oxygen which we breathe."),
            ("text", "The Equation",
             "Carbon dioxide + Water + Sunlight → Glucose + Oxygen"),
            ("video", "Watch: Photosynthesis (YouTube)", "https://www.youtube.com/watch?v=eo5XndJaz-Y"),
            ("text", "Let's Think!",
             "Question: Why do plants need sunlight for photosynthesis? Hint: what would happen to a plant kept in a dark cupboard for a week?"),
        ],
    },
    {
        "title": "The Water Cycle",
        "description": "A simple journey of a water drop: evaporation, condensation, precipitation and collection.",
        "subject": "Science", "grade": "6", "language": "English",
        "status": "published",
        "content": [
            ("text", "The Journey of a Water Drop",
             "Sunlight heats the ocean. Water turns into vapour and rises — that is evaporation. High in the sky the vapour cools and forms clouds — condensation. When clouds get heavy, water falls as rain — precipitation. The rain flows into rivers and back to the ocean, and the cycle repeats. This is how nature keeps fresh water moving."),
            ("text", "Think About It",
             "Where does the water in our well come from? Trace it back step by step."),
        ],
    },
    {
        "title": "Fractions Made Easy",
        "description": "Numerator, denominator, and why 3/4 of a pizza is bigger than 1/2.",
        "subject": "Mathematics", "grade": "5", "language": "Hindi",
        "status": "published",
        "content": [
            ("text", "What is a Fraction?",
             "A fraction is a part of a whole. In 3/4, the bottom number (denominator = 4) tells us the whole is cut into 4 equal parts. The top number (numerator = 3) tells us how many parts we take. So 3/4 means three out of four equal parts."),
            ("text", "Which is bigger?",
             "Compare 1/2 and 3/4: 1/2 = 2/4, and 2/4 < 3/4, so 3/4 is bigger. When denominators are the same, the bigger numerator is the bigger fraction."),
            ("image", "Fraction pizza diagram", "pizza"),
        ],
    },
    {
        "title": "Parts of a Computer",
        "description": "Input devices, CPU, memory, storage and output devices — the basic anatomy of a computer.",
        "subject": "Computer Science", "grade": "4", "language": "English",
        "status": "published",
        "content": [
            ("text", "A Computer's Brain and Body",
             "A computer takes INPUT (keyboard, mouse), processes it in the CPU (the brain), stores it in memory (RAM) and storage (hard disk), and gives OUTPUT (monitor, printer). Software tells the hardware what to do."),
            ("text", "Activity",
             "List three input and three output devices you see at home or school."),
        ],
    },
    {
        "title": "Newton's Law of Gravitation",
        "description": "Why do things fall down? An introduction to gravity for class 9.",
        "subject": "Science", "grade": "9", "language": "English",
        "status": "draft",
        "content": [
            ("text", "Gravity — the invisible pull",
             "Every object attracts every other object with a force called gravity. Earth's gravity keeps us on the ground and pulls the Moon around us. Its strength on Earth's surface is about 9.8 m/s²."),
        ],
    },
    {
        "title": "Nouns — Naming Words",
        "description": "A friendly introduction to nouns with lots of examples (Marathi + English).",
        "subject": "English", "grade": "3", "language": "Marathi",
        "status": "published",
        "content": [
            ("text", "What is a Noun? (नाम म्हणजे काय?)",
             "A noun is a naming word — it names a person (Maya/माया), a place (Pune/पुणे), a thing (book/पुस्तक), an animal (tiger/वाघ) or an idea (freedom/स्वातंत्र्य). In 'Rita reads a story in the garden', the nouns are: Rita, story, garden."),
            ("text", "Find the nouns!",
             "The teacher opened the door. → teacher, door. Now try: 'The boy played with a ball in the park'."),
        ],
    },
]


def migrate_columns():
    """Tiny schema migration for databases created by earlier versions.
    (SQLite ALTER TABLE ADD COLUMN — also works on Postgres/MySQL.)"""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    if "announcements" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("announcements")}
        with db.engine.connect() as conn:
            for name, ddl in (("start_date", "ALTER TABLE announcements ADD COLUMN start_date DATETIME"),
                              ("end_date", "ALTER TABLE announcements ADD COLUMN end_date DATETIME")):
                if name not in cols:
                    try:
                        conn.execute(text(ddl))
                        conn.commit()
                    except Exception:
                        conn.rollback()


def seed_defaults():
    """Idempotent: runs at startup, only inserts what's missing."""
    # --- Languages ---------------------------------------------------------
    if Language.query.count() == 0:
        for code, name, native, is_default, order in DEFAULT_LANGUAGES:
            db.session.add(Language(code=code, name=name, native_name=native,
                                    is_default=is_default, sort_order=order))
        db.session.commit()

    # --- Settings ----------------------------------------------------------
    for key, value in DEFAULT_SETTINGS.items():
        if db.session.get(Setting, key) is None:
            db.session.add(Setting(key=key, value=value))
    for key, value in DEFAULT_TEXT_CONTENT.items():
        if db.session.get(Setting, key) is None:
            db.session.add(Setting(key=key, value=value))
    db.session.commit()

    # --- Admin account (reads .env at runtime — overridable in tests/deploy) --
    import os as _os
    admin_email = _os.getenv("ADMIN_EMAIL", "admin@bhasha.setu").lower()
    if not User.query.filter_by(role="admin", email=admin_email).first():
        admin = User(
            name=_os.getenv("ADMIN_NAME", "Administrator"),
            email=admin_email,
            role="admin",
            password_hash=hash_password(_os.getenv("ADMIN_PASSWORD", "Admin@123")),
            language_preference="English",
        )
        db.session.add(admin)
        db.session.commit()

    # --- Demo users + lessons (only when SEED_DEMO=true) --------------------
    import os as _os2
    if not str(_os2.getenv("SEED_DEMO", "true")).strip().lower() in ("1", "true", "yes", "on"):
        return

    demo_users = [
        ("Priya Sharma", "student@demo.setu", "student", "Marathi"),
        ("Amit Deshmukh", "teacher@demo.setu", "teacher", "Marathi"),
        ("Sneha Kulkarni", "tutor@demo.setu", "tutor", "English"),
    ]
    existing = {u.email: u for u in User.query.all()}
    for name, email, role, lang in demo_users:
        if email not in existing:
            u = User(name=name, email=email, role=role,
                     password_hash=hash_password("Demo@123"), language_preference=lang)
            db.session.add(u)
            existing[email] = u
    db.session.commit()

    teacher = existing.get("teacher@demo.setu")
    admin_user = User.query.filter_by(role="admin").first()
    if Lesson.query.count() == 0:
        author = teacher.id if teacher else (admin_user.id if admin_user else None)
        for sample in SAMPLE_LESSONS:
            lesson = Lesson(
                title=sample["title"], description=sample["description"],
                subject=sample["subject"], grade=sample["grade"],
                language=sample["language"], status=sample["status"],
                author_id=author, views=(len(sample["title"]) * 17) % 300,
            )
            db.session.add(lesson)
            db.session.flush()
            for i, (ctype, title, body) in enumerate(sample["content"]):
                if ctype == "image" and body == "pizza":
                    # placeholder illustration URL (kept generic)
                    body = "images/lesson-pizza.jpg"
                db.session.add(LessonContent(
                    lesson_id=lesson.id, type=ctype, title=title,
                    content=body if ctype == "text" else "",
                    url=body if ctype != "text" else "",
                    sort_order=i,
                ))
        db.session.commit()

    # --- First welcome announcement ----------------------------------------
    if Announcement.query.count() == 0:
        db.session.add(Announcement(
            title="Welcome to Bhasha Shiksha Setu! 🎉",
            message="Learn every subject in YOUR language — with the AI Tutor, translation and voice support. New lessons are added every week!",
            priority=5, active=True,
            created_by=admin_user.id if admin_user else None,
        ))
        db.session.commit()
