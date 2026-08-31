"""
Auth routes — /api/auth/*
  login, register, logout, me, change-password, refresh
Uses JWT bearer tokens + password hashing + brute-force lockout.
"""
from datetime import datetime, timezone

from flask import Blueprint, request

from backend.database import db
from backend.models import User
from backend.utils import (
    check_login_lockout, check_password, clear_login_attempts, client_ip,
    create_token, fail, hash_password, log_activity, login_required,
    ok, record_failed_login, sanitize_text, valid_email, valid_password,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    identifier = sanitize_text(data.get("identifier", "")).strip()  # email OR username
    password = str(data.get("password", ""))

    if not identifier or not password:
        return fail("Please enter your email and password.", 400)

    ip = client_ip()
    locked, wait = check_login_lockout(f"login:{identifier.lower()}")
    if locked:
        return fail(f"Too many failed attempts. Try again in {wait} minute(s).", 429)

    user = User.query.filter(
        db.or_(User.email.ilike(identifier), User.name.ilike(identifier))
    ).first()

    if not user or not check_password(user, password):
        record_failed_login(f"login:{identifier.lower()}")
        log_activity(None, "failed_login", f"Attempt for {identifier}", ip)
        return fail("Invalid email or password.", 401)

    if not user.active:
        return fail("Your account has been deactivated. Contact the administrator.", 403)

    clear_login_attempts(f"login:{identifier.lower()}")
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()
    log_activity(user, "login", "User logged in", ip)

    return ok({
        "token": create_token(user),
        "user": user.to_dict(),
    }, "Login successful.")


@bp.post("/register")
def register():
    """Public student self-registration (admin creates other roles)."""
    data = request.get_json(silent=True) or {}
    name = sanitize_text(data.get("name", "")).strip()
    email = sanitize_text(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    language = sanitize_text(data.get("language_preference", "English")).strip() or "English"

    if not name:
        return fail("Please enter your full name.", 400)
    if not valid_email(email):
        return fail("Please enter a valid email address.", 400)
    if not valid_password(password):
        return fail("Password must be at least 6 characters.", 400)
    if User.query.filter(db.func.lower(User.email) == email).first():
        return fail("An account with this email already exists.", 409)

    user = User(name=name, email=email, role="student",
                password_hash=hash_password(password),
                language_preference=language)
    db.session.add(user)
    db.session.commit()
    log_activity(user, "register", "New student registered", client_ip())

    return ok({"token": create_token(user), "user": user.to_dict()},
              "Account created successfully!", 201)


@bp.post("/logout")
@login_required
def logout():
    log_activity(current_user(), "logout", "User logged out", client_ip())
    return ok(message="Logged out successfully.")


@bp.get("/me")
@login_required
def me():
    return ok(current_user().to_dict())


@bp.post("/change-password")
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_password = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))

    if not check_password(current_user(), current_password):
        return fail("Current password is incorrect.", 400)
    if not valid_password(new_password):
        return fail("New password must be at least 6 characters.", 400)

    user = current_user()
    user.password_hash = hash_password(new_password)
    db.session.commit()
    log_activity(user, "change_password", "Password changed")
    return ok(message="Password updated successfully.")


from backend.utils import current_user  # noqa: E402  (flask.g accessor)
