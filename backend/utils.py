"""
Shared helpers: JSON responses, JWT auth decorators, role-based access control,
activity logging, rate limiting, file validation, settings access.
"""
import functools
import hashlib
import re
import time
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app, g, jsonify, request

from backend.database import db
from backend.models import ActivityLog, Setting, User

# ---------------------------------------------------------------------------
# JSON responses (consistent across the whole API)
# ---------------------------------------------------------------------------

def ok(data=None, message="Operation successful", status=200):
    return jsonify({"success": True, "message": message, "data": data}), status


def fail(message="Something went wrong. Please try again.", status=400):
    """Friendly, safe error — never leak raw tracebacks to users."""
    return jsonify({"success": False, "message": message}), status


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

def create_token(user):
    """Create a signed JWT access token for a user."""
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"]),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None, "Session expired. Please log in again."
    except Exception:
        return None, "Invalid authentication token."
    return payload, None


def current_user():
    return getattr(g, "user", None)


def login_required(f):
    """Require a valid Bearer token."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return fail("Authentication required. Please log in.", 401)
        payload, err = decode_token(auth[7:].strip())
        if err:
            return fail(err, 401)
        user = db.session.get(User, int(payload["sub"]))
        if not user or not user.active:
            return fail("Account not found or deactivated.", 401)
        g.user = user
        return f(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    """Require login AND one of the given roles. Example: roles_required('admin')"""
    def decorator(f):
        @functools.wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if g.user.role not in roles:
                return fail("You do not have permission to perform this action.", 403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def hash_password(password):
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password, method="pbkdf2:sha256")


def check_password(user, password):
    from werkzeug.security import check_password_hash
    return check_password_hash(user.password_hash, password)


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------

def log_activity(user, action, detail="", ip=None):
    """Record an activity entry. Never fails the main request."""
    try:
        log = ActivityLog(
            user_id=user.id if user else None,
            user_name=user.name if user else "Guest",
            role=user.role if user else "guest",
            action=action,
            detail=detail,
            ip=ip or client_ip(),
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


def client_ip():
    """Best-effort client IP (respects common proxy headers)."""
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or ""


# ---------------------------------------------------------------------------
# Brute-force protection (in-memory, simple)
# ---------------------------------------------------------------------------

_attempts = {}  # key -> [timestamps]


def check_login_lockout(key):
    now = time.time()
    cutoff = now - current_app.config["LOGIN_LOCKOUT_MINUTES"] * 60
    times = [t for t in _attempts.get(key, []) if t > cutoff]
    _attempts[key] = times
    if len(times) >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
        wait = int(current_app.config["LOGIN_LOCKOUT_MINUTES"] - (now - times[0]) / 60) + 1
        return True, wait
    return False, 0


def record_failed_login(key):
    _attempts.setdefault(key, []).append(time.time())
    # keep memory tidy
    if len(_attempts) > 5000:
        _attempts.clear()


def clear_login_attempts(key):
    _attempts.pop(key, None)


def rate_limit(bucket, key, limit, window_seconds):
    """Simple in-memory rate limiter. Returns (allowed, retry_after)."""
    now = time.time()
    records = _attempts.setdefault(f"rl:{bucket}:{key}", [])
    records[:] = [t for t in records if t > now - window_seconds]
    if len(records) >= limit:
        retry = int(records[0] + window_seconds - now) + 1
        return False, retry
    records.append(now)
    return True, 0


# ---------------------------------------------------------------------------
# Site settings (key-value from DB)
# ---------------------------------------------------------------------------

def get_setting(key, default=""):
    row = db.session.get(Setting, key)
    return row.value if row else default


def set_setting(key, value):
    row = db.session.get(Setting, key)
    if row:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))
    db.session.commit()


def set_settings(mapping):
    """Safely update many settings at once."""
    for key, value in mapping.items():
        set_setting(key, value)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email):
    return bool(EMAIL_RE.match(email or ""))


def valid_password(password):
    return isinstance(password, str) and len(password) >= 6


def sanitize_text(value, max_len=5000):
    """Strip control chars; keeps HTML-friendly plain text safe-ish for display."""
    if value is None:
        return ""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value))[:max_len]


ALLOWED_EXTENSIONS = {
    "image": {"jpg", "jpeg", "png", "webp", "gif", "svg"},
    "video": {"mp4", "webm", "ogg"},
    "document": {"pdf", "doc", "docx", "ppt", "pptx", "txt", "md", "xls", "xlsx"},
}
ALLOWED_MIME = {
    "image": {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"},
    "video": {"video/mp4", "video/webm", "video/ogg"},
    "document": {"application/pdf", "application/msword",
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 "text/plain", "text/markdown", "application/octet-stream"},
}


def detect_file_type(filename, mime=""):
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    for ftype, exts in ALLOWED_EXTENSIONS.items():
        if ext in exts:
            return ftype, ext
    return None, ext


def validate_upload(filename, mime=""):
    """Return (file_type_ok, error_message)."""
    if not filename:
        return False, "No file selected."
    ftype, ext = detect_file_type(filename, mime)
    if ftype is None:
        return False, f"File type .{ext or '?'} is not allowed. Allowed: images (jpg/png/webp/svg), videos (mp4), documents (pdf/doc/txt)."
    if ftype == "image" and ext == "svg":
        # SVG can contain scripts — only accept it as pure XML markup
        if mime and mime not in ("image/svg+xml", "application/octet-stream"):
            return False, "SVG files must be served as image/svg+xml."
    return True, ""
