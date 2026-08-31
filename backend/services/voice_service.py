"""
Voice service — /api/voice endpoints.

The frontend uses the BROWSER's native Speech Synthesis + Web Speech API as
the primary, free implementation (works offline, no key). This backend
module exposes:
  * GET  /api/voice/voices         -> browser voice availability info
  * POST /api/voice/tts            -> optional server-side TTS (if TTS_PROVIDER=external
                                      and an endpoint is configured via env)
  * POST /api/voice/transcribe     -> optional server-side STT (if configured)

If no external provider is configured, the frontend falls back to the
browser APIs automatically — the website still fully works.
"""
import json
import urllib.error
import urllib.request

from backend.database import db
from backend.models import ChatMessage, Translation
from backend.utils import log_activity
from flask import current_app, request

# Server-side TTS/STT providers accept an OpenAI-compatible vibe (or any
# HTTP endpoint) configured via env. No keys are ever exposed to the browser.
TTS_URL = ""
STT_URL = ""
TTS_KEY = ""
STT_KEY = ""


def _load_config():
    global TTS_URL, STT_URL, TTS_KEY, STT_KEY
    import os
    TTS_URL = os.getenv("TTS_URL", "")
    STT_URL = os.getenv("STT_URL", "")
    TTS_KEY = os.getenv("TTS_API_KEY", "")
    STT_KEY = os.getenv("STT_API_KEY", "")


def tts_available():
    _load_config()
    return bool(TTS_URL)


def stt_available():
    _load_config()
    return bool(STT_URL)


def speak(text, language="English", voice=""):
    """POST text to the configured external TTS endpoint (if any)."""
    _load_config()
    if not TTS_URL:
        return None, "No external TTS configured. The website uses the browser's built-in speech."
    payload = {"text": text, "language": language, "voice": voice}
    req = urllib.request.Request(
        TTS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {TTS_KEY}"} if TTS_KEY
        else {"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read(), None
    except urllib.error.HTTPError as e:
        return None, f"TTS provider error ({e.code})."
    except Exception as e:
        return None, "TTS provider unreachable."


def transcribe(audio_b64, language="English"):
    """Send audio (base64) to the configured STT endpoint (if any)."""
    _load_config()
    if not STT_URL:
        return None, "No external STT configured. Use the browser microphone (Web Speech API)."
    payload = {"audio": audio_b64, "language": language}
    req = urllib.request.Request(
        STT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {STT_KEY}"} if STT_KEY
        else {"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("text", ""), None
    except Exception as e:
        return None, "STT provider unreachable."


def log_voice_usage(kind, user=None, meta=""):
    """Keep AI-usage stats: voice requests are recorded in the DB."""
    try:
        db.session.add(Translation(
            user_id=user.id if user else None,
            source_text=f"[voice:{kind}]", translated_text=meta or "used",
            source_language="Voice", target_language=meta or "voice",
            provider="voice",
        ))
        db.session.commit()
        log_activity(user, "voice_request", f"{kind} {meta}")
    except Exception:
        db.session.rollback()
