"""
Database models for Bhasha Shiksha Setu.

Tables:
  users, languages, lessons, lesson_content, translations, chat_history,
  media, documents, student_progress, teacher_content, settings,
  announcements, activity_logs

Every model has a to_dict() helper so the API returns clean JSON.
"""
from datetime import datetime, timezone

from backend.database import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    ROLE_ADMIN = "admin"
    ROLE_TEACHER = "teacher"
    ROLE_STUDENT = "student"
    ROLE_TUTOR = "tutor"
    VALID_ROLES = (ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT, ROLE_TUTOR)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)  # never plain text
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    language_preference = db.Column(db.String(40), nullable=False, default="English")
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self, private=False):
        data = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "active": self.active,
            "language_preference": self.language_preference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        return data


class Language(db.Model):
    __tablename__ = "languages"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)   # e.g. 'mr'
    name = db.Column(db.String(60), unique=True, nullable=False)   # e.g. 'Marathi'
    native_name = db.Column(db.String(60), default="")             # e.g. 'मराठी'
    is_default = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id, "code": self.code, "name": self.name,
            "native_name": self.native_name, "is_default": self.is_default,
            "active": self.active, "sort_order": self.sort_order,
        }


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    subject = db.Column(db.String(100), nullable=False, index=True)
    grade = db.Column(db.String(20), default="")                    # class/grade
    language = db.Column(db.String(40), default="English", index=True)
    status = db.Column(db.String(20), default="draft", index=True)  # draft | published
    thumbnail = db.Column(db.String(500), default="")               # url or /uploads/...
    views = db.Column(db.Integer, default=0)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    content_items = db.relationship(
        "LessonContent", backref="lesson", cascade="all, delete-orphan",
        order_by="LessonContent.sort_order", lazy="selectin",
    )

    def to_dict(self, full=False):
        data = {
            "id": self.id, "title": self.title, "description": self.description,
            "subject": self.subject, "grade": self.grade, "language": self.language,
            "status": self.status, "thumbnail": self.thumbnail, "views": self.views,
            "author_id": self.author_id, "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if full:
            data["content_items"] = [c.to_dict() for c in self.content_items]
        return data


class LessonContent(db.Model):
    """A single block inside a lesson: text / image / video / document."""
    __tablename__ = "lesson_content"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False)     # text | image | video | document
    title = db.Column(db.String(200), default="")
    url = db.Column(db.String(500), default="")         # image/video/document url
    content = db.Column(db.Text, default="")            # text body (for type=text)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "lesson_id": self.lesson_id, "type": self.type,
                "title": self.title, "url": self.url, "content": self.content,
                "sort_order": self.sort_order}


class Translation(db.Model):
    __tablename__ = "translations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    source_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    source_language = db.Column(db.String(40), index=True)
    target_language = db.Column(db.String(40), index=True)
    provider = db.Column(db.String(30), default="demo")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "source_text": self.source_text,
                "translated_text": self.translated_text,
                "source_language": self.source_language,
                "target_language": self.target_language,
                "provider": self.provider,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class ChatMessage(db.Model):
    __tablename__ = "chat_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    guest_id = db.Column(db.String(64), nullable=True, index=True)  # anonymous visitors
    message = db.Column(db.Text, nullable=False)
    reply = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(40), default="English")
    context = db.Column(db.String(40), default="general")   # general | lesson | tutor
    demo_mode = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    def to_dict(self):
        return {"id": self.id, "message": self.message, "reply": self.reply,
                "language": self.language, "context": self.context,
                "demo_mode": self.demo_mode,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), unique=True, nullable=False)  # stored name
    original_name = db.Column(db.String(200), nullable=False)
    file_type = db.Column(db.String(20), default="image")   # image | video | document
    mime_type = db.Column(db.String(80), default="")
    size = db.Column(db.Integer, default=0)                 # bytes
    title = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "filename": self.filename, "original_name": self.original_name,
                "file_type": self.file_type, "mime_type": self.mime_type, "size": self.size,
                "title": self.title, "description": self.description,
                "uploaded_by": self.uploaded_by,
                "url": "/uploads/" + self.filename,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Document(db.Model):
    """Study documents (PDF / notes) managed by admins & teachers."""
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(100), default="Study Material")
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "title": self.title, "description": self.description,
                "category": self.category, "media_id": self.media_id,
                "uploaded_by": self.uploaded_by,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class StudentProgress(db.Model):
    __tablename__ = "student_progress"
    __table_args__ = (db.UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False, index=True)
    progress = db.Column(db.Integer, default=0)                 # 0-100
    status = db.Column(db.String(20), default="in_progress")    # in_progress | completed
    saved = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "lesson_id": self.lesson_id,
                "progress": self.progress, "status": self.status, "saved": self.saved,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None}


class TeacherContent(db.Model):
    """Extra explanations / material a teacher adds to a lesson."""
    __tablename__ = "teacher_content"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False, index=True)
    title = db.Column(db.String(200), default="")
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "teacher_id": self.teacher_id, "lesson_id": self.lesson_id,
                "title": self.title, "content": self.content,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Setting(db.Model):
    """Key-value website settings (editable from Admin → Settings)."""
    __tablename__ = "settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, default="")


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(500), default="")
    priority = db.Column(db.Integer, default=0)             # higher = more important
    active = db.Column(db.Boolean, default=True)
    start_date = db.Column(db.DateTime, nullable=True)      # optional scheduling
    end_date = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "title": self.title, "message": self.message,
                "image": self.image, "priority": self.priority, "active": self.active,
                "start_date": self.start_date.isoformat() if self.start_date else None,
                "end_date": self.end_date.isoformat() if self.end_date else None,
                "created_by": self.created_by,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    user_name = db.Column(db.String(120), default="")
    role = db.Column(db.String(20), default="")
    action = db.Column(db.String(120), nullable=False, index=True)
    detail = db.Column(db.Text, default="")
    ip = db.Column(db.String(64), default="")   # kept minimal, for basic admin visibility
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "user_name": self.user_name,
                "role": self.role, "action": self.action, "detail": self.detail,
                "ip": self.ip,
                "created_at": self.created_at.isoformat() if self.created_at else None}
