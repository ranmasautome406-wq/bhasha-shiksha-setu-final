"""
/api/voice — server-side voice endpoints.

The frontend uses the BROWSER Web Speech APIs (free, no keys) as the primary
implementation. These endpoints are the optional server-side augmentation:
  * GET  /api/voice/voices       -> availability info (external TTS/STT configured? + text)
  * POST /api/voice/tts          -> optional external TTS (only if TTS_URL set)
  * POST /api/voice/transcribe   -> optional external STT (only if STT_URL set)

No provider keys are ever exposed to the browser; they live in .env only.
"""
from flask import Blueprint, current_app, request

from backend.services import voice_service
from backend.utils import fail, ok

bp = Blueprint("voice", __name__, url_prefix="/api/voice")


@bp.get("/voices")
def voices():
    """Availability info the frontend uses to decide browser vs server."""
    external = voice_service.tts_available() or voice_service.stt_available()
    return ok({
        "tts_available": voice_service.tts_available(),
        "stt_available": voice_service.stt_available(),
        "any_external": external,
        "primary": "browser",  # browser Web Speech is always primary
        "message": "Voice uses the browser Web Speech API. External TTS/STT is "
                   "used only when configured on the server (.env).",
    })


@bp.post("/tts")
def tts():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return fail("Text is required.", 400)
    if not voice_service.tts_available():
        return ok({"provider": "browser", "audio": None,
                   "message": "No external TTS configured — the browser speech "
                              "synthesis already reads this aloud."})
    audio, err = voice_service.speak(text, language=str(data.get("language", "English")))
    if err:
        return fail(err, 502)
    try:
        import base64
        voice_service.log_voice_usage("tts", meta=f"{len(text)} chars")
        return ok({"provider": "external", "audio_base64": base64.b64encode(audio).decode("ascii")})
    finally:
        pass


@bp.post("/transcribe")
def transcribe():
    data = request.get_json(silent=True) or {}
    audio = str(data.get("audio", ""))
    if not audio:
        return fail("Audio payload is required.", 400)
    if not voice_service.stt_available():
        return ok({"provider": "browser", "text": None,
                   "message": "No external STT configured — use the browser "
                              "microphone (Web Speech API)."})
    text, err = voice_service.transcribe(audio, language=str(data.get("language", "English")))
    if err:
        return fail(err, 502)
    voice_service.log_voice_usage("stt", meta=f"{len(text)} chars")
    return ok({"provider": "external", "text": text})
