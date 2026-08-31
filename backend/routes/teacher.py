"""
Teacher routes — /api/teacher/*
  dashboard, lessons (create/edit/publish own lessons), students,
  lesson activity, extra teacher content.
Teachers can manage their OWN lessons/drafts — admins manage everything.
"""
from flask import Blueprint, g, request

from backend.database import db
from backend.models import (
    Lesson, LessonContent, Media, StudentProgress, TeacherContent, User,
)
from backend.utils import fail, log_activity, ok, roles_required, sanitize_text

bp = Blueprint("teacher", __name__, url_prefix="/api/teacher")


@bp.get("/dashboard")
@roles_required("teacher", "admin")
def dashboard():
    lessons = (Lesson.query.filter_by(author_id=g.user.id)
               .order_by(Lesson.updated_at.desc()).all())
    students = User.query.filter_by(role="student", active=True).count()
    total_views = sum(l.views or 0 for l in lessons)
    published = sum(1 for l in lessons if l.status == "published")

    return ok({
        "profile": g.user.to_dict(),
        "stats": {
            "my_lessons": len(lessons),
            "published": published,
            "drafts": len(lessons) - published,
            "total_views": total_views,
            "students": students,
        },
        "lessons": [l.to_dict() for l in lessons],
    })


@bp.post("/lessons")
@roles_required("teacher", "admin")
def create_lesson():
    data = request.get_json(silent=True) or {}
    title = sanitize_text(data.get("title", "")).strip()
    if not title:
        return fail("Lesson title is required.", 400)
    if not data.get("subject"):
        return fail("Subject is required.", 400)

    lesson = Lesson(
        title=title,
        description=sanitize_text(data.get("description", ""), 5000),
        subject=sanitize_text(data.get("subject", "")).strip(),
        grade=sanitize_text(data.get("grade", "")).strip(),
        language=sanitize_text(data.get("language", "English")).strip() or "English",
        status=data.get("status", "draft") if data.get("status") in ("draft", "published") else "draft",
        thumbnail=sanitize_text(data.get("thumbnail", ""), 500),
        author_id=g.user.id,
    )
    db.session.add(lesson)
    db.session.flush()

    for i, item in enumerate(data.get("content_items") or []):
        if not isinstance(item, dict):
            continue
        ctype = item.get("type")
        if ctype not in ("text", "image", "video", "document"):
            continue
        db.session.add(LessonContent(
            lesson_id=lesson.id, type=ctype,
            title=sanitize_text(item.get("title", ""), 200),
            url=sanitize_text(item.get("url", ""), 500),
            content=sanitize_text(item.get("content", ""), 20000),
            sort_order=int(item.get("sort_order", i)),
        ))

    db.session.commit()
    log_activity(g.user, "lesson_created", f"'{lesson.title}'")
    return ok(lesson.to_dict(full=True), "Lesson created.", 201)


@bp.put("/lessons/<int:lesson_id>")
@roles_required("teacher", "admin")
def update_lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return fail("Lesson not found.", 404)
    if g.user.role != "admin" and lesson.author_id != g.user.id:
        return fail("You can only edit your own lessons.", 403)

    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"]:
        lesson.title = sanitize_text(data["title"]).strip()
    if "description" in data:
        lesson.description = sanitize_text(data["description"], 5000)
    if "subject" in data and data["subject"]:
        lesson.subject = sanitize_text(data["subject"]).strip()
    if "grade" in data:
        lesson.grade = sanitize_text(data["grade"]).strip()
    if "language" in data and data["language"]:
        lesson.language = sanitize_text(data["language"]).strip()
    if "thumbnail" in data:
        lesson.thumbnail = sanitize_text(data["thumbnail"], 500)
    if data.get("status") in ("draft", "published"):
        lesson.status = data["status"]

    if "content_items" in data:  # replace-all strategy (simple + predictable)
        LessonContent.query.filter_by(lesson_id=lesson.id).delete()
        db.session.flush()
        for i, item in enumerate(data["content_items"] or []):
            if not isinstance(item, dict) or item.get("type") not in ("text", "image", "video", "document"):
                continue
            db.session.add(LessonContent(
                lesson_id=lesson.id, type=item["type"],
                title=sanitize_text(item.get("title", ""), 200),
                url=sanitize_text(item.get("url", ""), 500),
                content=sanitize_text(item.get("content", ""), 20000),
                sort_order=int(item.get("sort_order", i)),
            ))

    db.session.commit()
    log_activity(g.user, "lesson_updated", f"'{lesson.title}'")
    return ok(lesson.to_dict(full=True), "Lesson updated.")


@bp.delete("/lessons/<int:lesson_id>")
@roles_required("teacher", "admin")
def delete_lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return fail("Lesson not found.", 404)
    if g.user.role != "admin" and lesson.author_id != g.user.id:
        return fail("You can only delete your own lessons.", 403)
    title = lesson.title
    db.session.delete(lesson)
    db.session.commit()
    log_activity(g.user, "lesson_deleted", f"'{title}'")
    return ok(message="Lesson deleted.")


@bp.post("/lessons/<int:lesson_id>/publish")
@roles_required("teacher", "admin")
def publish_lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return fail("Lesson not found.", 404)
    if g.user.role != "admin" and lesson.author_id != g.user.id:
        return fail("You can only publish your own lessons.", 403)
    lesson.status = "published" if lesson.status != "published" else "draft"
    db.session.commit()
    log_activity(g.user, "lesson_publish", f"'{lesson.title}' -> {lesson.status}")
    return ok(lesson.to_dict(), f"Lesson {lesson.status}.")


@bp.get("/students")
@roles_required("teacher", "admin")
def students():
    """Students who have progress on this teacher's lessons."""
    lesson_ids = [l.id for l in Lesson.query.filter_by(author_id=g.user.id).all()]
    rows = []
    if lesson_ids:
        rows = (StudentProgress.query
                .filter(StudentProgress.lesson_id.in_(lesson_ids))
                .order_by(StudentProgress.updated_at.desc()).limit(100).all())
    out = []
    for r in rows:
        student = db.session.get(User, r.user_id)
        lesson = db.session.get(Lesson, r.lesson_id)
        out.append({
            "student": student.to_dict() if student else None,
            "lesson_title": lesson.title if lesson else "?",
            "progress": r.progress, "status": r.status,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })
    return ok(out)


@bp.get("/activity")
@roles_required("teacher", "admin")
def activity():
    """Last activity across the teacher's lessons."""
    from backend.models import ActivityLog
    logs = (ActivityLog.query.order_by(ActivityLog.created_at.desc())
            .filter(ActivityLog.action.in_(["student_progress", "lesson_created",
                                            "lesson_updated", "lesson_publish"]))
            .limit(30).all())
    return ok([l.to_dict() for l in logs])


@bp.post("/content")
@roles_required("teacher", "admin")
def add_teacher_content():
    """Teacher's own explanation/notes attached to a lesson."""
    data = request.get_json(silent=True) or {}
    try:
        lesson_id = int(data.get("lesson_id"))
    except (TypeError, ValueError):
        return fail("lesson_id is required.", 400)
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return fail("Lesson not found.", 404)

    tc = TeacherContent(
        teacher_id=g.user.id, lesson_id=lesson_id,
        title=sanitize_text(data.get("title", ""), 200),
        content=sanitize_text(data.get("content", ""), 20000),
    )
    db.session.add(tc)
    db.session.commit()
    log_activity(g.user, "teacher_content", f"Added note to '{lesson.title}'")
    return ok(tc.to_dict(), "Content added.", 201)
