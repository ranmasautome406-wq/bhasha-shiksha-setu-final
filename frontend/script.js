/* =========================================================
   Bhasha Shiksha Setu — shared frontend logic
   API client, auth, dynamic content, AI Assistant widget,
   voice input (Web Speech API) and read-aloud (Speech Synthesis)
   ========================================================= */
"use strict";

/* ---------------- Tiny helpers ---------------- */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function escapeHtml(str = "") {
  return String(str).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function initials(name = "?") {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase();
}
function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }); }
  catch { return iso; }
}

function toast(message, type = "ok", ms = 3200) {
  let box = $("#toasts");
  if (!box) { box = document.createElement("div"); box.id = "toasts"; document.body.appendChild(box); }
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.textContent = message;
  box.appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; t.style.transition = ".4s"; setTimeout(() => t.remove(), 400); }, ms);
}

/* Modal helpers */
function openModal(id) { const m = $("#" + id); if (m) m.classList.add("open"); }
function closeModal(id) { const m = $("#" + id); if (m) m.classList.remove("open"); }
document.addEventListener("click", (e) => {
  if (e.target.classList && e.target.classList.contains("overlay")) e.target.classList.remove("open");
});

/* ---------------- API client ---------------- */
const API_BASE = (window.BSS_CONFIG && window.BSS_CONFIG.API_BASE) || "/api";
const GUEST_KEY = "bss_guest_id";

function guestId() {
  let id = localStorage.getItem(GUEST_KEY);
  if (!id) { id = "g" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36); localStorage.setItem(GUEST_KEY, id); }
  return id;
}
function authToken() { return localStorage.getItem("bss_token"); }
function currentUser() {
  try { return JSON.parse(localStorage.getItem("bss_user") || "null"); } catch { return null; }
}
function setAuth(token, user) {
  if (token) localStorage.setItem("bss_token", token);
  localStorage.setItem("bss_user", JSON.stringify(user));
}
function clearAuth() {
  localStorage.removeItem("bss_token");
  localStorage.removeItem("bss_user");
}

async function api(path, options = {}) {
  const opts = { ...options };
  opts.headers = { "Content-Type": "application/json", "X-Guest-Id": guestId(), ...(opts.headers || {}) };
  const token = authToken();
  if (token) opts.headers["Authorization"] = "Bearer " + token;
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  try {
    const res = await fetch(API_BASE + path, opts);
    let data = null;
    try { data = await res.json(); } catch { /* empty body */ }
    if (!res.ok || (data && data.success === false)) {
      const msg = (data && data.message) || "Something went wrong. Please try again.";
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return data ? data.data : null;
  } catch (e) {
    if (e.status === 401 && authToken()) {
      // session expired — clean up quietly
      clearAuth();
      updateNavAuth();
    }
    throw e;
  }
}

/* ---------------- Auth (login / register modals) ---------------- */
window.BSS_AUTH = {
  async login(identifier, password) {
    const data = await api("/auth/login", { method: "POST", body: { identifier, password } });
    setAuth(data.token, data.user);
    updateNavAuth();
    return data.user;
  },
  async register(payload) {
    const data = await api("/auth/register", { method: "POST", body: payload });
    setAuth(data.token, data.user);
    updateNavAuth();
    return data.user;
  },
  logout() {
    api("/auth/logout", { method: "POST" }).catch(() => {});
    clearAuth();
    updateNavAuth();
    toast("You have been logged out.");
  },
  logoutAll: clearAuth,
};

function updateNavAuth() {
  const user = currentUser();
  $$("[data-auth=in]").forEach(el => el.classList.toggle("hide", !user));
  $$("[data-auth=out]").forEach(el => el.classList.toggle("hide", !!user));
  const nameEl = $("#navUserName"), av = $("#navUserAvatar");
  if (nameEl) nameEl.textContent = user ? user.name : "";
  if (av) av.textContent = user ? initials(user.name) : "?";
  const logoutLinks = $$("[data-logout]");
  logoutLinks.forEach(el => {
    el.onclick = (e) => { e.preventDefault(); BSS_AUTH.logout(); };
  });
}

function bindLoginForm() {
  const form = $("#loginForm");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#loginSubmit");
    btn.disabled = true; btn.textContent = "Signing in…";
    try {
      const user = await BSS_AUTH.login($("#loginId").value.trim(), $("#loginPassword").value);
      closeModal("loginModal");
      toast(`Welcome back, ${user.name}! 🎉`);
      // Role-based redirect (if on a public page)
      const onPage = document.body.dataset.page;
      if (!onPage || onPage === "home") {
        const target = user.role === "admin" ? "/admin/dashboard.html"
          : user.role === "teacher" ? "teacher.html"
          : user.role === "tutor" ? "tutor.html" : "student.html";
        if (target.startsWith("/")) { window.location.href = target; }
        else if (window.location.pathname.endsWith("index.html") || window.location.pathname === "/") window.location.href = target;
        else location.reload();
      } else {
        // Portal page (student/teacher/tutor): reload so the logged-in UI renders
        window.location.reload();
      }
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false; btn.textContent = "Login";
    }
  });
}

function bindRegisterForm() {
  const form = $("#registerForm");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#registerSubmit");
    btn.disabled = true; btn.textContent = "Creating account…";
    try {
      const user = await BSS_AUTH.register({
        name: $("#regName").value.trim(),
        email: $("#regEmail").value.trim(),
        password: $("#regPassword").value,
        language_preference: $("#regLang") ? $("#regLang").value : "English",
      });
      closeModal("registerModal");
      toast(`Welcome, ${user.name}! Your account is ready. 🎉`);
      if (document.body.dataset.page === "student") location.reload();
      else window.location.href = "student.html";
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false; btn.textContent = "Create Account";
    }
  });
}

/* ---------------- Site config + CMS text ---------------- */
const BSS_STATE = {
  config: null,
  languages: ["English", "Marathi", "Hindi", "Gujarati", "Bengali", "Tamil", "Telugu",
              "Kannada", "Malayalam", "Punjabi", "Urdu"],
  aiEnabled: true,
  textContent: {},
};

async function loadSiteConfig() {
  try {
    const cfg = await api("/config");
    BSS_STATE.config = cfg;
    if (cfg.languages && cfg.languages.length) {
      BSS_STATE.languages = cfg.languages.filter(l => l.active).map(l => l.name);
    }
    BSS_STATE.aiEnabled = cfg.ai_enabled !== false;
    populateLanguageSelects();
    return cfg;
  } catch { /* offline / backend down — keep defaults */ }
}

function populateLanguageSelects() {
  $$("select[data-langs], .lang-select").forEach(sel => {
    if (sel.dataset.locked === "1") return;
    sel.dataset.locked = "1";
    const current = sel.value || localStorage.getItem("bss_lang") || "English";
    sel.innerHTML = BSS_STATE.languages.map(l =>
      `<option value="${escapeHtml(l)}" ${l === current ? "selected" : ""}>${escapeHtml(l)}</option>`).join("");
    sel.value = current;
  });
}

async function loadTextContent() {
  try {
    const data = await api("/content");
    BSS_STATE.textContent = data || {};
    applyTextContent();
  } catch { /* defaults remain in HTML */ }
}

function applyTextContent() {
  const t = BSS_STATE.textContent;
  if (!t) return;
  $$("[data-content]").forEach(el => {
    const key = el.dataset.content;
    if (t[key] !== undefined && t[key] !== "") el.textContent = t[key];
  });
}

async function loadAnnouncements() {
  const host = $("#announcements");
  if (!host) return;
  try {
    const items = await api("/content/announcements");
    if (!items || !items.length) { host.classList.add("hide"); return; }
    host.classList.remove("hide");
    host.innerHTML = '<div class="container">' + items.map(a => `
      <div class="announce-item" style="margin-bottom:6px">
        <b>📢 ${escapeHtml(a.title)}:</b> ${escapeHtml(a.message)}
        ${a.image ? `<a href="${escapeHtml(a.image)}" target="_blank" rel="noopener" style="margin-left:6px">🖼</a>` : ""}
      </div>`).join("") + "</div>";
  } catch { host.classList.add("hide"); }
}

async function loadFAQs() {
  const host = $("#faqList");
  if (!host) return;
  try {
    const faqs = await api("/content/faqs");
    if (!faqs || !faqs.length) { host.closest("section")?.classList.add("hide"); return; }
    host.innerHTML = faqs.map((f, i) => `
      <div class="faq-item ${i === 0 ? "open" : ""}">
        <div class="faq-q">${escapeHtml(f.q || f.question)}</div>
        <div class="faq-a">${escapeHtml(f.a || f.answer)}</div>
      </div>`).join("");
    $$(".faq-q", host).forEach(q => q.addEventListener("click", () => q.parentElement.classList.toggle("open")));
  } catch { host.closest("section")?.classList.add("hide"); }
}

/* ---------------- Lessons (public) ---------------- */
async function fetchLessons(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
  const qs = params.toString();
  return api("/lessons" + (qs ? "?" + qs : ""));
}

function lessonCard(l) {
  const thumb = l.thumbnail
    ? `<img src="${escapeHtml(l.thumbnail)}" alt="" loading="lazy">`
    : "📘";
  return `
  <div class="card lesson-card" data-lesson-id="${l.id}">
    <div class="lesson-thumb">${thumb}</div>
    <div class="lesson-meta">
      <span class="chip subj">${escapeHtml(l.subject)}</span>
      <span class="chip lang">🗣 ${escapeHtml(l.language)}</span>
      ${l.grade ? `<span class="chip grade">Class ${escapeHtml(l.grade)}</span>` : ""}
      <span class="chip ${l.status === "published" ? "pub" : "draft"}">${escapeHtml(l.status)}</span>
    </div>
    <h3>${escapeHtml(l.title)}</h3>
    <p>${escapeHtml((l.description || "").slice(0, 120))}${(l.description || "").length > 120 ? "…" : ""}</p>
    <button class="btn btn-primary btn-sm" onclick="BSS_LESSONS.open(${l.id})">Open Lesson →</button>
  </div>`;
}

window.BSS_LESSONS = {
  async render(hostSel = "#lessonGrid", filters = {}) {
    const host = $(hostSel);
    if (!host) return;
    host.innerHTML = '<div class="skeleton" style="height:190px"></div>'.repeat(3);
    try {
      const lessons = await fetchLessons(filters);
      if (!lessons.length) {
        host.innerHTML = `<div class="empty" style="grid-column:1/-1"><div class="big">📚</div>
          No lessons yet — check back soon!</div>`;
        return;
      }
      host.innerHTML = lessons.map(lessonCard).join("");
    } catch (e) {
      host.innerHTML = `<div class="empty" style="grid-column:1/-1"><div class="big">⚠️</div>${escapeHtml(e.message)}</div>`;
    }
  },
  async open(id) {
    const host = $("#lessonModalBody");
    if (host) {
      host.innerHTML = '<div class="skeleton" style="height:200px"></div>';
      openModal("lessonModal");
      try {
        const l = await api(`/lessons/${id}`);
        host.innerHTML = `
          <div class="reader">
            <div class="card lesson-thumb">${l.thumbnail ? `<img src="${escapeHtml(l.thumbnail)}">` : "📘"}</div>
            <div class="lesson-meta" style="margin:16px 0">
              <span class="chip subj">${escapeHtml(l.subject)}</span>
              <span class="chip lang">🗣 ${escapeHtml(l.language)}</span>
              ${l.grade ? `<span class="chip grade">Class ${escapeHtml(l.grade)}</span>` : ""}
              <span class="chip pub">${l.views} views</span>
            </div>
            <h2>${escapeHtml(l.title)}</h2>
            <p style="color:var(--muted);margin:10px 0 18px">${escapeHtml(l.description)}</p>
            ${(l.content_items || []).map(c => renderContentBlock(c)).join("")}
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:24px">
              <button class="btn btn-accent" onclick="BSS_VOICE.listen(this)" data-text="${escapeHtml(l.title + ". " + l.description)}">🔊 Hear Explanation</button>
              <button class="btn btn-primary" onclick="closeModal('lessonModal');BSS_AI.open('lesson', ${l.id})">🤖 Ask AI about this lesson</button>
            </div>
          </div>`;
      } catch (e) { host.innerHTML = `<div class="empty"><div class="big">⚠️</div>${escapeHtml(e.message)}</div>`; }
    }
  },
};

function renderContentBlock(c) {
  if (c.type === "text") return `<div class="reader-block"><h4>${escapeHtml(c.title || "")}</h4><p>${escapeHtml(c.content)}</p></div>`;
  if (c.type === "image") return `<div class="reader-block"><h4>${escapeHtml(c.title || "")}</h4><img src="${escapeHtml(c.url)}" alt="${escapeHtml(c.title)}"></div>`;
  if (c.type === "video") {
    const vid = c.url || "";
    const yt = vid.match(/(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([\w-]+)/);
    const src = yt ? `https://www.youtube.com/embed/${yt[1]}` : vid;
    return `<div class="reader-block"><h4>${escapeHtml(c.title || "Video")}</h4>
      <div class="video-frame"><iframe src="${escapeHtml(src)}" allowfullscreen loading="lazy"></iframe></div></div>`;
  }
  if (c.type === "document") return `<div class="reader-block"><h4>📄 ${escapeHtml(c.title || "Document")}</h4>
    <a class="btn btn-outline btn-sm" href="${escapeHtml(c.url)}" target="_blank" rel="noopener">Open document</a></div>`;
  return "";
}

/* ---------------- Voice: read aloud (browser Speech Synthesis) ---------------- */
window.BSS_VOICE = {
  supported: ("speechSynthesis" in window),
  _utter: null,
  _paused: false,
  voiceFor(langName) {
    const codes = { English: "en", Marathi: "mr-IN", Hindi: "hi-IN", Gujarati: "gu-IN",
      Bengali: "bn-IN", Tamil: "ta-IN", Telugu: "te-IN", Kannada: "kn-IN",
      Malayalam: "ml-IN", Punjabi: "pa-IN", Urdu: "ur-PK" };
    const code = codes[langName] || "en-IN";
    const voices = speechSynthesis.getVoices();
    return voices.find(v => v.lang === code) || voices.find(v => v.lang.startsWith(code.split("-")[0])) || null;
  },
  speak(text, opts = {}) {
    if (!this.supported) { toast("Read-aloud is not supported in this browser.", "warn"); return false; }
    this.stop();
    const u = new SpeechSynthesisUtterance(text);
    const v = this.voiceFor(opts.language || localStorage.getItem("bss_lang") || "English");
    if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = opts.rate || 0.95; u.pitch = 1;
    u.onend = () => { this._playing = false; this._syncBtn(); };
    u.onerror = () => { this._playing = false; this._syncBtn(); };
    this._utter = u; this._paused = false; this._playing = true;
    speechSynthesis.speak(u);
    this._syncBtn();
    return true;
  },
  pause() { if (speechSynthesis.speaking) { speechSynthesis.pause(); this._paused = true; this._syncBtn(); } },
  resume() { if (this._paused) { speechSynthesis.resume(); this._paused = false; this._syncBtn(); } },
  stop() { if ("speechSynthesis" in window) { speechSynthesis.cancel(); } this._paused = false; this._playing = false; this._syncBtn(); },
  toggle(text, opts = {}) {
    if (this._playing) {
      if (this._paused) this.resume();
      else this.pause();
    } else this.speak(text, opts);
  },
  /* Button behaviour: data-text = the text to read */
  listen(btn, opts = {}) {
    const text = (btn && btn.dataset.text) || "";
    if (!text) { toast("Nothing to read yet.", "warn"); return; }
    this.toggle(text, opts);
  },
  _syncBtn() {
    $$("[data-text]").forEach(b => {
      if (b.dataset.listening === "1") {
        b.textContent = this._playing ? (this._paused ? "▶ Resume" : "⏸ Pause") : "🔊 Read";
        b.dataset.listening = this._playing ? "1" : "0";
      }
    });
  },
};

/* ---------------- Voice input (browser Web Speech API) ---------------- */
window.BSS_STT = (() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  return {
    supported: !!SR,
    rec: null, active: false, onResult: null, onChange: null,
    langCode(name) {
      const codes = { English: "en-IN", Marathi: "mr-IN", Hindi: "hi-IN", Gujarati: "gu-IN",
        Bengali: "bn-IN", Tamil: "ta-IN", Telugu: "te-IN", Kannada: "kn-IN",
        Malayalam: "ml-IN", Punjabi: "pa-IN", Urdu: "ur-PK" };
      return codes[name] || "en-IN";
    },
    start(language, callbacks = {}) {
      if (!this.supported) { toast("Voice input is not supported in this browser. Try Chrome or Edge.", "warn"); return; }
      if (this.active) { this.stop(); return; }
      const rec = new SR();
      rec.lang = this.langCode(language);
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      rec.onstart = () => { this.active = true; callbacks.onChange && callbacks.onChange(true); };
      rec.onresult = (e) => {
        let text = "";
        for (let i = e.resultIndex; i < e.results.length; i++) text += e.results[i][0].transcript;
        callbacks.onResult && callbacks.onResult(text);
      };
      rec.onerror = (e) => {
        if (e.error !== "aborted") toast("Voice input error: " + e.error + ".", "warn");
        this.stop();
      };
      rec.onend = () => { this.active = false; callbacks.onChange && callbacks.onChange(false); };
      this.rec = rec;
      rec.start();
    },
    stop() { if (this.rec) { try { this.rec.stop(); } catch {} } this.active = false; },
  };
})();

/* ---------------- AI Assistant widget ---------------- */
window.BSS_AI = {
  inited: false,
  context: "general",
  lessonId: null,

  init() {
    if (this.inited) return;
    if (!BSS_STATE.aiEnabled) return;
    this.inited = true;
    if (!$("#aiFab")) {
      const fab = document.createElement("button");
      fab.id = "aiFab"; fab.className = "ai-fab";
      fab.innerHTML = "💬<small>AI Assistant</small>";
      fab.title = "Ask Bhasha AI Tutor";
      document.body.appendChild(fab);
      const panel = document.createElement("div");
      panel.id = "aiPanel"; panel.className = "ai-panel";
      panel.innerHTML = `
        <div class="ai-head">
          <div class="ai-avatar">🤖</div>
          <div><b>Bhasha AI Tutor</b><small id="aiStatus">Online • Demo mode available</small></div>
          <div class="ai-head-actions">
            <button id="aiClear" title="Clear chat">🗑</button>
            <button id="aiClose" title="Close">✕</button>
          </div>
        </div>
        <div class="ai-body" id="aiBody"></div>
        <div class="ai-chips" id="aiChips"></div>
        <div class="ai-input-row">
          <button class="ai-mic" id="aiMic" title="Ask by voice">🎤</button>
          <input id="aiInput" placeholder="Type your question…" autocomplete="off">
          <select id="aiLang" class="lang-select" title="Answer in language" style="max-width:110px;padding:8px"></select>
          <button class="ai-send" id="aiSend" title="Send">➤</button>
        </div>
        <div class="ai-foot-note">Answers are educational. In demo mode the tutor uses built-in knowledge.</div>`;
      document.body.appendChild(panel);

      $("#aiFab").addEventListener("click", () => this.open());
      $("#aiClose").addEventListener("click", () => this.close());
      $("#aiClear").addEventListener("click", () => this.clearHistory());
      $("#aiSend").addEventListener("click", () => this.send());
      $("#aiInput").addEventListener("keydown", (e) => { if (e.key === "Enter") this.send(); });
      $("#aiMic").addEventListener("click", () => this.toggleMic());

      const chips = ["Explain photosynthesis", "Explain in Marathi", "What is Bhasha Shiksha Setu?", "Give me study tips", "Explain fractions simply"];
      $("#aiChips").innerHTML = chips.map(c => `<button>${escapeHtml(c)}</button>`).join("");
      $$("#aiChips button").forEach(b => b.addEventListener("click", () => {
        this.setInput(b.textContent); this.send();
      }));

      const langSel = $("#aiLang");
      langSel.innerHTML = BSS_STATE.languages.map(l =>
        `<option value="${escapeHtml(l)}">${escapeHtml(l)}</option>`).join("");
      langSel.value = localStorage.getItem("bss_lang") || "English";

      this.loadHistory();
    }
  },

  setContext(ctx, lessonId = null) {
    this.context = ctx || "general";
    this.lessonId = lessonId;
  },
  open(context, lessonId) {
    this.init();
    this.setContext(context, lessonId);
    $("#aiPanel").classList.add("open");
    $("#aiInput").focus();
  },
  close() { const p = $("#aiPanel"); if (p) p.classList.remove("open"); },
  setInput(text) { const i = $("#aiInput"); if (i) { i.value = text; i.focus(); } },

  history: [],
  async loadHistory() {
    const body = $("#aiBody");
    try {
      const msgs = await api("/chat/history?limit=30");
      this.history = msgs || [];
      body.innerHTML = msgs.length ? "" : this.welcome();
      msgs.forEach(m => {
        this.renderMessage("user", m.message);
        this.renderMessage("bot", m.reply);
      });
      body.scrollTop = body.scrollHeight;
    } catch { body.innerHTML = this.welcome(); }
  },
  welcome() {
    const lang = localStorage.getItem("bss_lang") || "English";
    return `<div class="ai-msg bot"><div class="bubble">${escapeHtml(
      `Namaste! 🙏 I am Bhasha AI Tutor. Ask me anything about a lesson, science, maths — or type a question in ${lang}.`)}</div></div>`;
  },

  async send() {
    const input = $("#aiInput");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    this.renderMessage("user", text);
    this.typing(true);
    const lang = $("#aiLang").value;
    localStorage.setItem("bss_lang", lang);
    try {
      const data = await api("/chat", {
        method: "POST",
        body: { message: text, language: lang, user_id: (currentUser() || {}).id || null,
                guest_id: guestId(), context: this.context, lesson_id: this.lessonId },
      });
      this.typing(false);
      this.renderMessage("bot", data.reply);
      this.history.push({ message: text, reply: data.reply });
      const status = $("#aiStatus");
      if (status) status.textContent = "Online";
    } catch (e) {
      this.typing(false);
      this.renderMessage("bot", "⚠️ " + e.message);
    }
  },

  typing(on) {
    const body = $("#aiBody");
    if (!body) return;
    const t = $("#typingRow");
    if (on) {
      body.insertAdjacentHTML("beforeend",
        `<div class="ai-msg bot" id="typingRow"><div class="typing"><span></span><span></span><span></span></div></div>`);
    } else { const el = $("#typingRow"); if (el) el.remove(); }
    body.scrollTop = body.scrollHeight;
  },

  renderMessage(who, text) {
    const body = $("#aiBody");
    if (!body) return;
    const div = document.createElement("div");
    div.className = "ai-msg " + (who === "user" ? "user" : "bot");
    const btnText = escapeHtml(text);
    div.innerHTML = who === "bot"
      ? `<div class="bubble">${btnText}</div>
         <div style="display:flex;flex-direction:column;gap:4px">
           <div class="actions">
             <button onclick="BSS_VOICE.listen(this)" data-text="${btnText}" data-listening="0">🔊 Listen</button>
           </div>
         </div>`
      : `<div class="bubble">${btnText}</div>`;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
  },

  async clearHistory() {
    try {
      await api("/chat/history", { method: "DELETE" });
      this.history = [];
      const body = $("#aiBody");
      if (body) body.innerHTML = this.welcome();
      toast("Chat history cleared.");
    } catch (e) { toast(e.message, "err"); }
  },

  toggleMic() {
    const mic = $("#aiMic");
    if (!BSS_STT.supported) { toast("Voice input needs Chrome/Edge on desktop or Android.", "warn"); return; }
    const lang = ($("#aiLang") || {}).value || "English";
    BSS_STT.start(lang, {
      onChange: (on) => { mic.classList.toggle("rec", on); mic.textContent = on ? "⏹" : "🎤"; },
      onResult: (text) => { this.setInput(text); },
    });
  },
};

/* ---------------- Translation tool (home page) ---------------- */
async function doTranslate() {
  const src = $("#transSrc"), dst = $("#transDst");
  const text = (src ? src.value : "").trim();
  const target = (dst ? dst.value : "Marathi");
  const out = $("#transOut"), btn = $("#transBtn");
  if (!text) { toast("Type something to translate.", "warn"); return; }
  if (out) out.textContent = "Translating…";
  if (btn) btn.disabled = true;
  try {
    const data = await api("/translate", { method: "POST", body: { text, source_language: "English", target_language: target } });
    if (out) out.textContent = data.translated_text;
    const listenBtn = $("#transListen");
    if (listenBtn) { listenBtn.dataset.text = data.translated_text; listenBtn.classList.remove("hide"); }
  } catch (e) {
    if (out) out.textContent = "⚠️ " + e.message;
  } finally { if (btn) btn.disabled = false; }
}

function bindTranslateTool() {
  const btn = $("#transBtn");
  if (!btn) return;
  btn.addEventListener("click", doTranslate);
  const swap = $("#transSwap");
  if (swap) {
    swap.addEventListener("click", () => {
      const src = $("#transSrc"), dst = $("#transDst");
      if (!src || !dst) return;
      const t = src.value; src.value = dst.value || "";
      dst.value = t;
    });
  }
}

/* ---------------- Video translation + live dubbing ---------------- */
window.BSS_VIDEO = {
  init() {
    const file = $("#videoFile"), preview = $("#videoPreview"), name = $("#videoFileName");
    if (!file) return;
    file.addEventListener("change", () => {
      const f = file.files && file.files[0];
      if (!f) return;
      if (f.size > 200 * 1024 * 1024) { toast("Please choose a video smaller than 200 MB.", "warn"); file.value = ""; return; }
      if (name) name.textContent = `${f.name} · ${(f.size / 1024 / 1024).toFixed(1)} MB`;
      if (preview) { preview.src = URL.createObjectURL(f); preview.classList.remove("hide"); }
    });

    const source = $("#videoSourceLang"), target = $("#videoTargetLang");
    const liveSource = $("#liveSourceLang"), liveTarget = $("#liveTargetLang");
    const fill = (sel, value) => { if (sel && BSS_STATE.languages.length) { sel.innerHTML = BSS_STATE.languages.map(l => `<option>${escapeHtml(l)}</option>`).join(""); sel.value = value; } };
    fill(source, "English"); fill(target, "Marathi"); fill(liveSource, "English"); fill(liveTarget, "Marathi");

    const status = $("#videoStatus");
    api("/video/status").then(d => {
      if (status) status.textContent = d.stt_available && d.tts_available ? "✓ Server dubbing ready" : "Live browser dubbing ready · server video dubbing needs STT + TTS";
    }).catch(() => { if (status) status.textContent = "Live browser dubbing available"; });

    $("#dubVideoBtn")?.addEventListener("click", this.dub.bind(this));
    $("#liveDubBtn")?.addEventListener("click", this.live.bind(this));
  },
  async dub() {
    const file = $("#videoFile")?.files?.[0];
    if (!file) { toast("Choose a video first.", "warn"); return; }
    const btn = $("#dubVideoBtn"), result = $("#dubResult");
    const fd = new FormData();
    fd.append("video", file); fd.append("source_language", $("#videoSourceLang")?.value || "English"); fd.append("target_language", $("#videoTargetLang")?.value || "Marathi");
    btn.disabled = true; btn.textContent = "⏳ Processing video…"; result?.classList.add("hide");
    try {
      const res = await fetch(API_BASE + "/video/dub", { method:"POST", headers:{"X-Guest-Id":guestId(), ...(authToken()?{"Authorization":"Bearer "+authToken()}: {})}, body:fd });
      const data = await res.json();
      if (!res.ok || data.success === false) throw new Error(data.message || "Dubbing failed.");
      const d = data.data;
      result.innerHTML = `<b>✅ Dubbed video ready!</b><br><span>${escapeHtml(d.translated_text.slice(0,240))}${d.translated_text.length>240?"…":""}</span><br><a href="${escapeHtml(d.video_url)}" target="_blank" rel="noopener">▶ Open dubbed video</a>`;
      result.classList.remove("hide");
    } catch (e) { result.textContent = "⚠️ " + e.message; result.classList.remove("hide"); result.style.background="#fff7ed"; }
    finally { btn.disabled=false; btn.textContent="🎙️ Create Dubbed Video"; }
  },
  live() {
    const btn = $("#liveDubBtn"), out = $("#liveTranscript");
    if (!BSS_STT.supported) { toast("Live dubbing needs Chrome or Edge with microphone permission.", "warn"); return; }
    if (BSS_STT.active) { BSS_STT.stop(); btn.textContent="🎤 Start Live Dubbing"; return; }
    const src = $("#liveSourceLang")?.value || "English", dst = $("#liveTargetLang")?.value || "Marathi";
    btn.textContent = "⏹ Stop Live Dubbing";
    BSS_STT.start(src, {
      onChange: on => { if (!on) btn.textContent="🎤 Start Live Dubbing"; },
      onResult: async text => {
        if (!text || !text.trim()) return;
        out.textContent = "You: " + text;
        try {
          const d = await api("/translate", {method:"POST", body:{text, source_language:src, target_language:dst}});
          out.textContent = `${src}: ${text}\n${dst}: ${d.translated_text}`;
          BSS_VOICE.speak(d.translated_text, {language:dst, rate:1.0});
        } catch (e) { out.textContent = "⚠️ " + e.message; }
      }
    });
  }
};

/* ---------------- Boot ---------------- */
document.addEventListener("DOMContentLoaded", async () => {
  updateNavAuth();
  bindLoginForm();
  bindRegisterForm();
  bindTranslateTool();
  if (typeof BSS_VIDEO !== "undefined") BSS_VIDEO.init();
  $$(".burger").forEach(b => b.addEventListener("click", () => $(".nav-links")?.classList.toggle("open")));

  await loadSiteConfig();
  loadTextContent();
  loadAnnouncements();
  loadFAQs();

  const page = document.body.dataset.page;
  if (page !== "admin") BSS_AI.init();
  if (page === "home") {
    // Subject filter pills
    $$("#subjectPills .filter-pill").forEach(pill => pill.addEventListener("click", () => {
      $$("#subjectPills .filter-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      BSS_LESSONS.render("#lessonGrid", { subject: pill.dataset.subject });
    }));
    BSS_LESSONS.render("#lessonGrid");
    try {
      const lessons = await api("/lessons");
      const countEl = $("#heroLessonsCount");
      if (countEl) countEl.textContent = lessons.length;
      const bandEl = $("#bandLessons");
      if (bandEl) bandEl.textContent = lessons.length;
    } catch {}
    const langCountEl = $("#bandLangs");
    if (langCountEl) langCountEl.textContent = BSS_STATE.languages.length;
  }
  if (typeof window.PAGE_INIT === "function") window.PAGE_INIT();
});
