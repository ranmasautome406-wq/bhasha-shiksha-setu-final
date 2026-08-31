"""
AI service — powers /api/chat and /api/explain.

Two modes (set via .env → AI_PROVIDER):
  * demo      : built-in educational engine, works offline, no API key needed
  * openai    : calls an LLM through the OpenAI-compatible API (key in .env)

The admin can change the system instructions + enable/disable the assistant
from Admin → AI Settings — those values are stored in the database and
injected into every prompt.
"""
import json
import re
import urllib.request
from urllib.error import HTTPError, URLError

from backend.database import db
from backend.models import ChatMessage, Lesson, User
from backend.utils import get_setting, log_activity, rate_limit, sanitize_text
from flask import current_app, request


# ---------------------------------------------------------------------------
# Knowledge base: what the assistant knows about the website + education
# ---------------------------------------------------------------------------

def website_facts():
    """Platform info shown by get_setting — editable in Admin → AI Settings."""
    return {
        "project": get_setting("website_name", "Bhasha Shiksha Setu"),
        "tagline": get_setting("tagline", "AI-Powered Vernacular Education for Every Learner"),
        "problem_statement": "SIH26042",
        "about": get_setting(
            "ai_about",
            "Bhasha Shiksha Setu is an AI-powered vernacular education platform that "
            "helps students learn in their own language — Marathi, Hindi, Gujarati, Bengali, "
            "Tamil, Telugu, Kannada, Malayalam, Punjabi, Urdu and English. "
            "It has three modes: Student Mode (learn lessons, translate, ask the AI tutor), "
            "Teacher Mode (create lessons, add material, monitor students) and Tutor/AI Tutor "
            "Mode (ask the AI Tutor questions in any language).",
        ),
    }


def demo_knowledge():
    """Small built-in glossary so demo mode answers real questions."""
    return {
        "photosynthesis": (
            "Photosynthesis is the process by which green plants make their own food. "
            "They use sunlight, water (from soil) and carbon dioxide (from air). "
            "Inside the leaves, chlorophyll (the green pigment) traps sunlight energy. "
            "The plant then makes glucose (sugar) — its food — and releases oxygen, "
            "which we breathe. Simple equation: Carbon dioxide + Water + Sunlight → "
            "Glucose + Oxygen."
        ),
        "gravity": (
            "Gravity is the invisible force that pulls objects towards each other. "
            "On Earth it pulls everything towards the centre of the planet, which is "
            "why dropped things fall down and why we stay on the ground. Earth's "
            "gravity is about 9.8 m/s² on the surface."
        ),
        "water_cycle": (
            "The water cycle is how water keeps moving between the Earth and the sky. "
            "Sunlight heats water in oceans/rivers → it evaporates into water vapour "
            "(rises up) → vapour cools and forms clouds (condensation) → water falls "
            "back as rain (precipitation) → water flows back to rivers and oceans, "
            "and the cycle repeats."
        ),
        "fractions": (
            "A fraction shows a part of a whole, written as numerator/denominator. "
            "Example: in 3/4, the 4 means the whole is divided into 4 equal parts, "
            "and 3 means we take 3 of them. 3/4 of a pizza is three slices when the "
            "pizza is cut into four equal slices."
        ),
        "pythagoras": (
            "Pythagoras theorem: In a right-angled triangle, the square of the longest "
            "side (hypotenuse) equals the sum of the squares of the other two sides: "
            "a² + b² = c². Example: sides 3 and 4 → hypotenuse = √(9+16) = √25 = 5."
        ),
        "noun": (
            "A noun is a naming word. It names a person (Maya), a place (Pune), a thing "
            "(book), an animal (tiger) or an idea (freedom). In the sentence 'Rita reads "
            "a story in the garden', the nouns are Rita, story and garden."
        ),
        "computer": (
            "A computer is an electronic machine that takes input, processes it with a "
            "program, and gives output. The main parts are: Input devices (keyboard, "
            "mouse), the CPU (brain), memory (RAM), storage (hard disk), and output "
            "devices (monitor, printer)."
        ),
        "study_tips": (
            "Here are 5 simple study tips: 1) Study the same subject at a fixed time daily. "
            "2) Learn 25 minutes, rest 5 minutes (Pomodoro). 3) Explain what you learned to "
            "someone — teaching is the best revision. 4) Revise within 24 hours and again "
            "after 7 days. 5) Use your own language first, then learn the English terms."
        ),
    }


def build_system_prompt():
    """Assemble prompt from editable DB settings + website facts."""
    facts = website_facts()
    instructions = get_setting(
        "ai_system_instructions",
        "You are Bhasha AI Tutor, a friendly, patient teacher inside the Bhasha Shiksha "
        "Setu platform. Always answer in the language the student asks in. Keep answers "
        "simple, short and use examples. Encourage the student. Never invent facts about "
        "the platform; if unsure, say so politely.",
    )
    return (
        f"You are {facts['project']}'s AI Tutor. Platform facts:\n"
        f"- Name: {facts['project']}\n- Tagline: {facts['tagline']}\n"
        f"- What it does: {facts['about']}\n"
        f"- Who can use it: Students (learn lessons, translate, ask AI), Teachers "
        f"(create lessons, upload material, monitor students), Tutors (AI Tutor + voice).\n"
        f"- Features: vernacular translation, AI Tutor chat, voice input (🎤), read-aloud "
        f"(🔊), lessons with images/PDF/videos, announcements.\n\n"
        f"Instructions:\n{instructions}\n\n"
        "If the user asks about the website (what is Bhasha Shiksha Setu, features, how "
        "to use), answer from the platform facts above."
    )


# ---------------------------------------------------------------------------
# Echo of the user question in their target language (for translation flow)
# ---------------------------------------------------------------------------

_LANGUAGE_ECHO = {
    "Marathi": "कृपया हे विचारा:", "Hindi": "कृपया पूछें:", "Gujarati": "કૃપા કરીને પૂછો:",
    "Bengali": "অনুগ্রহ করে জিজ্ঞাসা করুন:", "Tamil": "தயவுசெய்து கேளுங்கள்:",
    "Telugu": "దయచేసి అడగండి:", "Kannada": "ದಯವಿಟ್ಟು ಕೇಳಿ:", "Malayalam": "ദയവായി ചോദിക്കുക:",
    "Punjabi": "ਕਿਰਪਾ ਕਰਕੇ ਪੁੱਛੋ:", "Urdu": "براہ کرم پوچھیں:",
}


# ---------------------------------------------------------------------------
# Demo answer engine − works without any API key (offline fallback)
# ---------------------------------------------------------------------------

def demo_answer(message, language, context="general"):
    """Return (answer, demo_mode_flag, lesson_id_if_any)."""
    msg = message.lower().strip()

    # --- Website questions ------------------------------------------------
    if any(w in msg for w in ["what is bhasha", "what is this website", "about this website",
                              "about the platform", "what is the website", "who can use"]):
        facts = website_facts()
        return (
            f"{facts['project']} is an AI-powered vernacular education platform "
            f"(Smart India Hackathon problem statement {facts['problem_statement']}). "
            "Students can learn lessons in their own language, translate any text, and ask "
            "the AI Tutor questions in Marathi, Hindi, Gujarati, Bengali, Tamil, Telugu, "
            "Kannada, Malayalam, Punjabi, Urdu or English. Teachers can create lessons, "
            "upload study material and monitor students. The AI Tutor explains lessons, "
            "answers science & maths questions, and can read answers aloud — plus you can "
            "ask questions by voice with the 🎤 button. All of it is free of language "
            "barriers: learn in the language you think in!"), True, None

    if any(w in msg for w in ["how to use", "how do i use", "features", "what can you do",
                              "help me use", "student mode", "teacher mode", "tutor mode"]):
        return (
            "Here's how to use Bhasha Shiksha Setu:\n"
            "1) Student Mode — pick a language, open a lesson, and use the AI Tutor for "
            "doubts. Use Translate for any sentence, and 🔊 Hear Explanation to listen.\n"
            "2) Teacher Mode — log in as a teacher, create lessons, add images, PDFs and "
            "videos, and track how students are doing.\n"
            "3) Tutor/AI Tutor Mode — just type or speak a question (🎤) in any language; "
            "I'll explain it simply, step by step.\n"
            "Tip: click 💬 AI Assistant on any page to ask me anything!"), True, None

    # --- Topic lookups ----------------------------------------------------
    topic_map = {
        "photosynthesis": "photosynthesis", "phtosynthesis": "photosynthesis",
        "gravity": "gravity", "water cycle": "water_cycle", "evaporation": "water_cycle",
        "fraction": "fractions", "fractions": "fractions", "pythagoras": "pythagoras",
        "noun": "noun", "computer": "computer",
    }
    for key, val in topic_map.items():
        if key in msg:
            topic = val
            if topic == "photosynthesis":
                if "simple" in msg or "easy" in msg:
                    return ("Think of a plant as a tiny kitchen! The leaves are the solar "
                            "panels (chlorophyll catches sunlight). The roots drink water, "
                            "and the leaves breathe in carbon dioxide. Using sunlight, the "
                            "plant cooks glucose (its food) and gives out oxygen as a "
                            "'thank you'. That is photosynthesis!"), True, None
                if "marathi" in msg or language.lower() == "marathi":
                    return ("प्रकाशसंश्लेषण म्हणजे हिरव्या वनस्पतींनी स्वतःचे अन्न तयार करण्याची "
                            "प्रक्रिया. सूर्यप्रकाश, पाणी (मातीतून) आणि कार्बन डायऑक्साईड "
                            "(हवेतून) यांचा वापर करून पानांतील हरितद्रव्य (chlorophyll) "
                            "अन्न — ग्लुकोज — तयार करते आणि ऑक्सिजन बाहेर टाकते. "
                            "समीकरण: कार्बन डायऑक्साईड + पाणी + सूर्यप्रकाश → ग्लुकोज + ऑक्सिजन"), True, None
                return demo_knowledge()["photosynthesis"], True, None
            return demo_knowledge()[topic], True, None

    # --- Lesson explanations (after topic lookup so lesson Qs still match) --
    if context == "lesson":
        return ("I'm here to help with this lesson! Ask me things like 'explain photosynthesis "
                "step by step', 'give me an example', or 'explain this in Marathi'."), True, None

    # --- Study guidance ----------------------------------------------------
    if any(w in msg for w in ["how to study", "study tips", "study guidance", "how should i study",
                              "exam tips", "how to prepare"]):
        return demo_knowledge()["study_tips"], True, None

    # --- Translation request ----------------------------------------------
    if msg.startswith("translate") or "translate this" in msg:
        if language and language.lower() != "english":
            text = message.replace("translate", "", 1).strip(" :")
            if not text:
                text = "Work hard, and success will follow you."
            return f"{_LANGUAGE_ECHO.get(language, '')} {text}", True, None

    # --- Echo intent in the chosen language (demo translation) ------------
    if language and language.lower() != "english" and len(msg.split()) <= 12:
        return (f"{_LANGUAGE_ECHO.get(language, '')} {_simple_demo_translate(message, language)}", True, None)

    # --- Generic fallback (still helpful + honest about demo mode) --------
    return (
        "That's a great question! I'm running in Demo Mode (no AI API key set), so I can "
        "answer from my built-in knowledge: try asking about photosynthesis, gravity, the "
        "water cycle, fractions, Pythagoras theorem, nouns, computers, study tips, or "
        "anything about this website. Once the project admin adds an AI_API_KEY in .env, "
        "I'll answer every question with full AI power. 😊"
    ), True, None


def _simple_demo_translate(text, language):
    """Very small demo vocabulary so the demo translator feels alive."""
    words = {"hello": "नमस्कार", "teacher": "शिक्षक", "student": "विद्यार्थी",
             "lesson": "धडा", "school": "शाळा", "book": "पुस्तक", "water": "पाणी",
             "sun": "सूर्य", "earth": "पृथ्वी", "good": "चांगले"}
    translated = [words.get(w.lower(), w) for w in text.split()]
    return " ".join(translated)


# ---------------------------------------------------------------------------
# External LLM call (OpenAI-compatible), key only from .env
# ---------------------------------------------------------------------------

def call_llm(system_prompt, user_message, max_tokens=500):
    api_key = current_app.config["AI_API_KEY"]
    model = current_app.config["AI_MODEL"]
    base = current_app.config["AI_BASE_URL"].rstrip("/")
    if not api_key:
        raise RuntimeError("AI_API_KEY not configured")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.6,
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except HTTPError as e:
        raise RuntimeError(f"LLM error {e.code}") from e
    except URLError as e:
        raise RuntimeError("Could not reach the AI provider") from e


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------

def chat(message, language="English", user=None, guest_id=None, context="general"):
    """
    Handle a chat message end-to-end:
      rate limit -> build prompt -> demo or LLM -> save history -> log -> return reply
    """
    message = sanitize_text(message, 2000)
    if not message:
        return None, "Please type a question first."

    key = f"chat:{request.remote_addr}"
    allowed, retry = rate_limit("chat", key, limit=10, window_seconds=60)
    if not allowed:
        return None, f"Please wait {retry} seconds before sending another question."

    provider = current_app.config["AI_PROVIDER"]
    demo = True
    reply = None

    if provider in ("openai", "llm") and current_app.config["AI_API_KEY"]:
        try:
            reply = call_llm(build_system_prompt(), message)
            demo = False
        except Exception as e:
            current_app.logger.warning("LLM failed, falling back to demo: %s", e)
            reply = None

    if reply is None:
        reply, demo, _ = demo_answer(message, language, context)

    # Save to chat history
    try:
        db.session.add(ChatMessage(
            user_id=user.id if user else None,
            guest_id=guest_id,
            message=message,
            reply=reply,
            language=language,
            context=context,
            demo_mode=demo,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

    log_activity(user, "ai_question", f"Q: {message[:80]} | context: {context}")
    return reply, None


def get_lesson_for_explain(lesson_id):
    return db.session.get(Lesson, lesson_id)


def explain_lesson(lesson_id, question="", language="English", user=None):
    """Explain a lesson. Uses the lesson content + AI (demo or LLM)."""
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return None, "Lesson not found."

    context_text = "\n".join(
        c.content for c in lesson.content_items if c.type == "text"
    )[:3000] or lesson.description

    professor = current_app.config["AI_PROVIDER"]
    if professor in ("openai", "llm") and current_app.config["AI_API_KEY"]:
        try:
            prompt = (f"Lesson title: {lesson.title}\nSubject: {lesson.subject}, "
                      f"Grade: {lesson.grade}, Language: {lesson.language}\n"
                      f"Lesson content:\n{context_text}\n\n"
                      f"Student question (answer in {language}): {question or 'Explain this lesson simply'}")
            return call_llm(build_system_prompt(), prompt), None
        except Exception as e:
            current_app.logger.warning("LLM explain failed: %s", e)

    # Demo fallback
    summary = (
        f"📘 {lesson.title}\n\n"
        f"Subject: {lesson.subject}  |  Class: {lesson.grade or '-'}  |  "
        f"Language: {lesson.language}\n\n"
        f"{context_text or lesson.description or 'Detailed explanation will be added soon.'}"
    )
    return summary, None
