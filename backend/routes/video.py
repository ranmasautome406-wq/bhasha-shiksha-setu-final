"""Video translation and dubbing endpoints.

Pipeline for uploaded videos:
video -> FFmpeg audio extraction -> configured STT -> existing translator -> configured TTS -> FFmpeg mux.
Provider credentials stay on the server. If STT/TTS are not configured, the API returns a clear setup message.
"""
import base64
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from flask import Blueprint, current_app, request, send_from_directory
from werkzeug.utils import secure_filename

from backend.services.translation_service import translate
from backend.services.voice_service import speak, transcribe, stt_available, tts_available
from backend.utils import fail, ok

bp = Blueprint("video", __name__, url_prefix="/api/video")

ALLOWED = {"mp4", "webm", "mov", "m4v"}


def _ext(name):
    return Path(name or "").suffix.lower().lstrip(".")


def _run(cmd):
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        return None
    except subprocess.TimeoutExpired:
        return "Video processing timed out. Try a shorter video."
    except subprocess.CalledProcessError as exc:
        current_app.logger.warning("FFmpeg failed: %s", exc.stderr.decode("utf-8", "ignore")[-1000:])
        return "The video could not be processed. Please use MP4/WebM and try again."


@bp.get("/status")
def status():
    return ok({
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "stt_available": stt_available(),
        "tts_available": tts_available(),
        "translation_available": True,
        "supported_formats": sorted(ALLOWED),
        "max_mb": int(current_app.config["MAX_CONTENT_LENGTH"] / 1024 / 1024),
    })


@bp.post("/dub")
def dub():
    if "video" not in request.files:
        return fail("Please choose a video file.", 400)
    video = request.files["video"]
    if not video.filename:
        return fail("Please choose a video file.", 400)
    ext = _ext(video.filename)
    if ext not in ALLOWED:
        return fail("Supported video formats: MP4, WebM, MOV and M4V.", 400)
    if not shutil.which("ffmpeg"):
        return fail("FFmpeg is not installed on the server.", 500)
    if not stt_available() or not tts_available():
        return fail("Video dubbing needs both STT_URL and TTS_URL in the server .env. Live browser dubbing can still be used without them.", 503)

    source = str(request.form.get("source_language", "English"))
    target = str(request.form.get("target_language", "Marathi"))
    upload_dir = Path(current_app.config["UPLOAD_DIR"]) / "dubbed"
    upload_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="bss_dub_", dir=str(upload_dir)))

    try:
        safe = secure_filename(video.filename) or f"video.{ext}"
        input_path = work / f"input_{uuid.uuid4().hex}.{ext}"
        audio_path = work / "source.wav"
        dubbed_audio = work / "dubbed_audio"
        output_name = f"dubbed_{uuid.uuid4().hex}.mp4"
        output_path = upload_dir / output_name
        video.save(input_path)

        err = _run(["ffmpeg", "-y", "-i", str(input_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)])
        if err:
            return fail(err, 422)

        audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
        text, err = transcribe(audio_b64, source)
        if err or not text:
            return fail(err or "No speech was detected in the video.", 422)

        translated, provider = translate(text, source, target)
        audio_bytes, err = speak(translated, target)
        if err or not audio_bytes:
            return fail(err or "TTS did not return audio.", 502)
        dubbed_audio.write_bytes(audio_bytes)

        err = _run([
            "ffmpeg", "-y", "-i", str(input_path), "-i", str(dubbed_audio),
            "-filter_complex", "[1:a]apad[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(output_path)
        ])
        if err:
            return fail(err, 422)

        # Copy the final file into the normal public upload folder so the existing
        # /uploads/<filename> static route can serve it.
        public_dir = Path(current_app.config["UPLOAD_DIR"])
        public_dir.mkdir(parents=True, exist_ok=True)
        public_path = public_dir / output_name
        shutil.copy2(output_path, public_path)
        return ok({
            "video_url": f"/uploads/{output_name}",
            "source_text": text,
            "translated_text": translated,
            "translation_provider": provider,
            "target_language": target,
        }, "Dubbed video is ready.")
    except Exception as exc:
        current_app.logger.exception("Video dubbing failed: %s", exc)
        return fail("Video dubbing failed. Please try a shorter video.", 500)
    finally:
        shutil.rmtree(work, ignore_errors=True)
