"""
Student routes — /api/student/*
  dashboard, progress, lessons, save, recommend, history, stats
"""
from datetime import datetime, timezone

from flask import Blueprint, request

from backend.database import db
from backend.models import Lesson, StudentProgress, User
from backend.utils import fail, log_activity, login_required, ok
from flask import g

bp = Blueprint("student", __name__, url_prefix="/api/student")


def _student():
    return g.user


@bp.get("/dashboard")
@login_required
def dashboard():
    user = g.user
    progress_rows = (StudentProgress.query
                     .filter_by(user_id=user.id).all())

    recent = (Lesson.query.filter_by(status="published")
              .order_by(Lesson.created_at.desc()).limit(5).all())
    completed = [p for p in progress_rows if p.status == "completed"]
    saved = [p for p in progress_rows if p.saved]
    in_progress = [p for p in progress_rows if p.status == "in_progress"]

    # Recommended: same language/subject as what the student already has, not yet done
    done_ids = {p.lesson_id for p in progress_rows}
    lang = user.language_preference or "English"
    recommended = (Lesson.query.filter_by(status="published", language=lang)
                   .filter(~Lesson.id.in_(done_ids)).order_by(Lesson.views.desc())
                   .limit(4).all())
    if len(recommended) < 4:
        extras = (Lesson.query.filter_by(status="published")
                  .filter(~Lesson.id.in_(done_ids)).order_by(Lesson.views.desc())
                  .limit(4 - len(recommended)).all())
        recommended = recommended + extras

    progress_sum = sum(p.progress or 0 for p in progress_rows)
    avg_progress = round(progress_sum / len(progress_rows)) if progress_rows else 0

    return ok({
        "profile": user.to_dict(),
        "stats": {
            "total_lessons": Lesson.query.filter_by(status="published").count(),
            "completed": len(completed),
            "in_progress": len(in_progress),
            "saved": len(saved),
            "avg_progress": avg_progress,
        },
        "recent_lessons": [l.to_dict() for l in recent],
        "completed_lessons": [l.to_dict() for l in [
            db.session.get(Lesson, p.lesson_id) for p in completed[:10] if db.session.get(Lesson, p.lesson_id)]],
        "saved_lessons": [l.to_dict() for l in [
            db.session.get(Lesson, p.lesson_id) for p in saved[:10] if db.session.get(Lesson, p.lesson_id)]],
        "recommended_lessons": [l.to_dict() for l in recommended],
        "progress": {
            "completed_ids": [p.lesson_id for p in completed],
            "rows": [p.to_dict() for p in progress_rows],
        },
        "language_preference": lang,
    })


@bp.get("/progress")
@login_required
def progress():
    rows = (StudentProgress.query.filter_by(user_id=g.user.id)
            .order_by(StudentProgress.updated_at.desc()).all())
    return ok([r.to_dict() for r in rows])


@bp.post("/progress")
@login_required
def save_progress():
    """Update progress for a lesson (called as the student reads/view completes)."""
    data = request.get_json(silent=True) or {}
    try:
        lesson_id = int(data.get("lesson_id"))
    except (TypeError, ValueError):
        return fail("lesson_id is required.", 400)

    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return fail("Lesson not found.", 404)

    row = (StudentProgress.query
           .filter_by(user_id=g.user.id, lesson_id=lesson_id).first())
    if not row:
        row = StudentProgress(user_id=g.user.id, lesson_id=lesson_id)
        db.session.add(row)

    if "progress" in data:
        row.progress = max(0, min(100, int(data.get("progress", 0))))
    if "saved" in data:
        row.saved = bool(data.get("saved"))
    if data.get("status") == "completed" or row.progress >= 100:
        row.status = "completed"
        if not row.completed_at:
            row.completed_at = datetime.now(timezone.utc)
    elif data.get("status") == "in_progress":
        row.status = "in_progress"

    db.session.commit()
    log_activity(g.user, "student_progress",
                 f"Lesson {lesson.title} -> {row.status} ({row.progress}%)")
    return ok(row.to_dict(), "Progress saved.")


@bp.post("/lessons/<int:lesson_id>/save")
@login_required
def toggle_save(lesson_id):
    row = (StudentProgress.query
           .filter_by(user_id=g.user.id, lesson_id=lesson_id).first())
    if not row:
        row = StudentProgress(user_id=g.user.id, lesson_id=lesson_id)
        db.session.add(row)
    row.saved = not row.saved
    db.session.commit()
    return ok({"saved": row.saved}, "Lesson saved." if row.saved else "Lesson removed from saved.")


@bp.get("/stats")
@login_required
def stats():
    """AI usage for this student (shown in the dashboard)."""
    from backend.models import ChatMessage, Translation
    chats = ChatMessage.query.filter_by(user_id=g.user.id).count()
    trans = Translation.query.filter_by(user_id=g.user.id).count()
    return ok({"ai_questions": chats, "translations": trans})


@bp.put("/language")
@login_required
def set_language():
    data = request.get_json(silent=True) or {}
    lang = (data.get("language_preference") or "").strip()
    if not lang:
        return fail("Language is required.", 400)
    g.user.language_preference = lang[:40]
    db.session.commit()
    return ok(g.user.to_dict(), "Language preference updated.")
