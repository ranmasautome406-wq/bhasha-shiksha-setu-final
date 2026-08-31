"""
Translation service — powers /api/translate.

Providers (set via .env → TRANSLATION_PROVIDER):
  * demo   : built-in dictionary + phrase engine (offline)
  * openai : LLM translation using the configured AI key (OpenAI-compatible)
  * google : free Google Translate endpoint (no key, unofficial — best effort)
"""
import json
import re
import urllib.parse
import urllib.request

from backend.database import db
from backend.models import Translation
from backend.utils import log_activity, sanitize_text
from flask import current_app, request

# language name -> (ISO code, sample greeting in that script)
LANGUAGES = {
    "English": ("en", "Hello! How are you?"),
    "Hindi": ("hi", "नमस्ते! आप कैसे हैं?"),
    "Marathi": ("mr", "नमस्कार! तू कसा आहेस?"),
    "Gujarati": ("gu", "નમસ્તે! તમે કેમ છો?"),
    "Bengali": ("bn", "নমস্কার! আপনি কেমন আছেন?"),
    "Tamil": ("ta", "வணக்கம்! நீங்கள் எப்படி இருக்கிறீர்கள்?"),
    "Telugu": ("te", "నమస్కారం! మీరు ఎలా ఉన్నారు?"),
    "Kannada": ("kn", "ನಮಸ್ಕಾರ! ನೀವು ಹೇಗಿದ್ದೀರಿ?"),
    "Malayalam": ("ml", "നമസ്കാരം! സുഖമാണോ?"),
    "Punjabi": ("pa", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?"),
    "Urdu": ("ur", "السلام علیکم! آپ کیسے ہیں؟"),
}

# Small multilingual teaching glossary for demo mode
_DEMO_PHRASES = {
    ("hello", "Marathi"): "नमस्कार", ("hello", "Hindi"): "नमस्ते",
    ("hello", "Gujarati"): "નમસ્તે", ("hello", "Bengali"): "নমস্কার",
    ("hello", "Tamil"): "வணக்கம்", ("hello", "Telugu"): "నమస్కారం",
    ("hello", "Kannada"): "ನಮಸ್ಕಾರ", ("hello", "Malayalam"): "നമസ്കാരം",
    ("hello", "Punjabi"): "ਸਤ ਸ੍ਰੀ ਅਕਾਲ", ("hello", "Urdu"): "السلام علیکم",
    ("teacher", "Marathi"): "शिक्षक", ("teacher", "Hindi"): "शिक्षक",
    ("teacher", "Gujarati"): "શિક્ષક", ("teacher", "Bengali"): "শিক্ষক",
    ("teacher", "Tamil"): "ஆசிரியர்", ("teacher", "Telugu"): "ఉపాధ్యాయుడు",
    ("teacher", "Kannada"): "ಶಿಕ್ಷಕ", ("teacher", "Malayalam"): "അധ്യാപകൻ",
    ("teacher", "Punjabi"): "ਅਧਿਆਪਕ", ("teacher", "Urdu"): "استاد",
    ("student", "Marathi"): "विद्यार्थी", ("student", "Hindi"): "छात्र",
    ("student", "Gujarati"): "વિદ્યાર્થી", ("student", "Bengali"): "শিক্ষার্থী",
    ("student", "Tamil"): "மாணவர்", ("student", "Telugu"): "విద్యార్థి",
    ("student", "Kannada"): "ವಿದ್ಯಾರ್ಥಿ", ("student", "Malayalam"): "വിദ്യാർത്ഥി",
    ("student", "Punjabi"): "ਵਿਦਿਆਰਥੀ", ("student", "Urdu"): "طالب علم",
    ("lesson", "Marathi"): "धडा", ("lesson", "Hindi"): "पाठ",
    ("lesson", "Gujarati"): "પાઠ", ("lesson", "Bengali"): "পাঠ",
    ("lesson", "Tamil"): "பாடம்", ("lesson", "Telugu"): "పాఠం",
    ("lesson", "Kannada"): "ಪಾಠ", ("lesson", "Malayalam"): "പാഠം",
    ("lesson", "Punjabi"): "ਪਾਠ", ("lesson", "Urdu"): "سبق",
    ("school", "Marathi"): "शाळा", ("school", "Hindi"): "विद्यालय",
    ("school", "Gujarati"): "શાળા", ("school", "Bengali"): "বিদ্যালয়",
    ("school", "Tamil"): "பள்ளி", ("school", "Telugu"): "పాఠశాల",
    ("school", "Kannada"): "ಶಾಲೆ", ("school", "Malayalam"): "വിദ്യാലയം",
    ("school", "Punjabi"): "ਸਕੂਲ", ("school", "Urdu"): "اسکول",
    ("book", "Marathi"): "पुस्तक", ("book", "Hindi"): "पुस्तक",
    ("book", "Gujarati"): "પુસ્તક", ("book", "Bengali"): "বই",
    ("book", "Tamil"): "புத்தகம்", ("book", "Telugu"): "పుస్తకం",
    ("book", "Kannada"): "ಪುಸ್ತಕ", ("book", "Malayalam"): "പുസ്തകം",
    ("book", "Punjabi"): "ਕਿਤਾਬ", ("book", "Urdu"): "کتاب",
    ("water", "Marathi"): "पाणी", ("water", "Hindi"): "पानी",
    ("water", "Gujarati"): "પાણી", ("water", "Bengali"): "জল",
    ("water", "Tamil"): "தண்ணீர்", ("water", "Telugu"): "నీరు",
    ("water", "Kannada"): "ನೀರು", ("water", "Malayalam"): "വെള്ളം",
    ("water", "Punjabi"): "ਪਾਣੀ", ("water", "Urdu"): "پانی",
}


def _demo_translate(text, target):
    words = re.findall(r"\w+|[.,!?;]", text)
    out = []
    for w in words:
        if re.fullmatch(r"\w+", w):
            out.append(_DEMO_PHRASES.get((w.lower(), target), w))
        else:
            out.append(w)
    return " ".join(out)


def _google_translate(text, target):
    """Unofficial free Google Translate endpoint — best effort, no key."""
    code = LANGUAGES.get(target, ("en", ""))[0]
    url = ("https://translate.googleapis.com/translate_a/single"
           f"?client=gtx&sl=auto&tl={urllib.parse.quote(code)}"
           f"&dt=t&q={urllib.parse.quote(text[:2000])}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return "".join(seg[0] for seg in data[0] if seg and seg[0])
    except Exception:
        return None


def translate(text, source_language="English", target_language="Marathi", user=None):
    """
    Translate text. Returns (translated_text, provider).
    Falls back gracefully: LLM -> google -> demo.
    """
    text = sanitize_text(text, 2500)
    if not text.strip():
        return "Please enter some text to translate.", "demo"
    if (target_language or "").strip().lower() not in [x.lower() for x in LANGUAGES]:
        return "Unsupported target language. Try one of: " + ", ".join(LANGUAGES), "demo"

    target = LANGUAGES.get(target_language, (target_language,))[0]
    provider = current_app.config["TRANSLATION_PROVIDER"]

    # 1) LLM (if configured)
    if provider in ("openai", "llm") and current_app.config["AI_API_KEY"]:
        from backend.services.ai_service import call_llm
        try:
            prompt = (f"Translate the following text to {target_language}. "
                      f"Return ONLY the translation, no explanations.\n\nText: {text}")
            result = call_llm(prompt, "Translate", max_tokens=800)
            if result:
                _save(user, text, result, source_language, target_language, "openai")
                return result, "openai"
        except Exception as e:
            current_app.logger.warning("LLM translate failed: %s", e)

    # 2) Free Google endpoint
    if provider in ("google", "llm", "openai", "auto"):
        result = _google_translate(text, target_language)
        if result:
            _save(user, text, result, source_language, target_language, "google")
            return result, "google"

    # 3) Demo (always available)
    result = _demo_translate(text, target_language)
    _save(user, text, result, source_language, target_language, "demo")
    return result, "demo"


def _save(user, source, translated, src_lang, tgt_lang, provider):
    try:
        db.session.add(Translation(
            user_id=user.id if user else None,
            source_text=source, translated_text=translated,
            source_language=src_lang, target_language=tgt_lang, provider=provider,
        ))
        db.session.commit()
        log_activity(user, "translation", f"{src_lang} -> {tgt_lang}")
    except Exception:
        db.session.rollback()
