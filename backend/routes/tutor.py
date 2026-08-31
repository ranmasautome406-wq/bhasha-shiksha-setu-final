"""
Tutor/AI Tutor routes — /api/tutor/*
  Tutors can chat with the AI, see student questions, manage tutor tips.
"""
from flask import Blueprint, g, request

from backend.database import db
from backend.models import ChatMessage, TeacherContent, User
from backend.services.ai_service import chat, demo_answer
from backend.utils import fail, log_activity, login_required, ok, roles_required, sanitize_text

bp = Blueprint("tutor", __name__, url_prefix="/api/tutor")


@bp.get("/dashboard")
@roles_required("tutor", "admin")
def dashboard():
    my_answers = TeacherContent.query.filter_by(teacher_id=g.user.id).count()
    student_questions = ChatMessage.query.filter(
        ChatMessage.user_id.in_(
            db.select(User.id).where(User.role == "student")
        )
    ).count()
    return ok({
        "profile": g.user.to_dict(),
        "stats": {
            "student_questions": student_questions,
            "my_notes": my_answers,
        },
    })


@bp.post("/chat")
@login_required
def tutor_chat():
    """Tutor mode chat — same AI engine, saved under 'tutor' context."""
    data = request.get_json(silent=True) or {}
    message = sanitize_text(data.get("message", ""), 2000)
    language = sanitize_text(data.get("language", "English"), 40)
    if not message:
        return fail("Please type a question.", 400)
    reply, err = chat(message, language=language, user=g.user,
                      guest_id=data.get("guest_id"), context="tutor")
    if err:
        return fail(err, 429 if "wait" in err else 400)
    return ok({"reply": reply})


@bp.get("/questions")
@roles_required("tutor", "admin")
def student_questions():
    """Recent questions students asked the AI — tutors can use these to help."""
    q = (ChatMessage.query
         .filter(ChatMessage.user_id.in_(db.select(User.id).where(User.role == "student")))
         .order_by(ChatMessage.created_at.desc()).limit(30).all())
    return ok([m.to_dict() for m in q])
