/* =========================================================
   Bhasha Shiksha Setu — Admin Dashboard logic (v2)
   One file powers every admin page (dispatch by data-page).
   Every API call requires the JWT stored by login.html.
   ========================================================= */
"use strict";

/* ---------------- helpers ---------------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s = "") => String(s).replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(msg, type = "ok", ms = 3000) {
  const box = $("#toasts");
  const t = document.createElement("div");
  t.className = "toast " + type;
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), ms);
}
function openModal(id) { const m = $("[data-modal='" + id + "']"); if (m) m.classList.add("open"); }
function closeModal(id) { const m = $("[data-modal='" + id + "']"); if (m) m.classList.remove("open"); }
document.addEventListener("click", e => {
  if (e.target.classList?.contains("overlay")) e.target.classList.remove("open");
});
function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }); }
  catch { return iso; }
}
function fmtTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch { return ""; }
}
function initials(name = "?") {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase();
}
const AVATAR_COLORS = ["linear-gradient(135deg,#4f46e5,#7c3aed)", "linear-gradient(135deg,#0d9488,#14b8a6)",
  "linear-gradient(135deg,#f59e0b,#f97316)", "linear-gradient(135deg,#db2777,#ec4899)",
  "linear-gradient(135deg,#0284c7,#38bdf8)", "linear-gradient(135deg,#7c3aed,#a78bfa)"];

/* ---------------- API client ---------------- */
function token() { return localStorage.getItem("bss_token"); }
function adminUser() { try { return JSON.parse(localStorage.getItem("bss_user") || "null"); } catch { return null; } }

async function api(path, options = {}) {
  const opts = { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } };
  const t = token();
  if (t) opts.headers["Authorization"] = "Bearer " + t;
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  const res = await fetch("/api" + path, opts);
  let data = null;
  try { data = await res.json(); } catch {}
  if (res.status === 401) { localStorage.removeItem("bss_token"); localStorage.removeItem("bss_user"); window.location.href = "login.html"; throw new Error("Session expired."); }
  if (!res.ok || (data && data.success === false)) throw new Error((data && data.message) || "Something went wrong. Please try again.");
  return data ? data.data : null;
}

/* ---------------- shared chrome ---------------- */
let __activityCache = null;

document.addEventListener("click", e => {
  if (e.target.closest("[data-logout]")) {
    api("/auth/logout", { method: "POST" }).catch(() => {});
    localStorage.removeItem("bss_token");
    localStorage.removeItem("bss_user");
    window.location.href = "login.html";
  }
  if (e.target.closest("[data-open-change-pw]")) openModal("changePwModal");
});

function initChrome() {
  if (!token()) { window.location.href = "login.html"; return false; }
  const user = adminUser();
  if (!user || user.role !== "admin") { window.location.href = "login.html"; return false; }

  const setText = (sel, txt) => { const el = $(sel); if (el) el.textContent = txt; };
  setText("#profileName", user.name);
  setText("#profileEmail", user.email);
  setText("#sideName", user.name);
  setText("#sideEmail", user.email);
  const av1 = $("#profileAvatar"), av2 = $("#sideAvatar");
  const ini = initials(user.name);
  if (av1) { av1.textContent = ini; }
  if (av2) { av2.textContent = ini; }

  const page = document.body.dataset.page;
  $$(".side-nav a").forEach(a => a.classList.toggle("active", a.dataset.page === page));

  $(".burger")?.addEventListener("click", () => $(".sidebar")?.classList.toggle("open"));
  $$(".side-nav a").forEach(a => a.addEventListener("click", () => $(".sidebar")?.classList.remove("open")));

  // tabs
  $$(".tabs[data-tabs]").forEach(group => {
    $$(".tab", group).forEach(tab => tab.addEventListener("click", () => {
      $$(".tab", group).forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      const name = tab.dataset.tab;
      group.parentElement.querySelectorAll("[data-tabpage]").forEach(p =>
        p.classList.toggle("hide", p.dataset.tabpage !== name));
    }));
  });

  // global search → filter visible tables
  $("#globalSearch")?.addEventListener("keyup", e => {
    const q = e.target.value.trim().toLowerCase();
    $$("main table tbody tr").forEach(tr => {
      tr.style.display = !q || tr.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  });

  // profile dropdown
  const chip = $("#profileChip"), drop = $("#profileDrop");
  if (chip && drop) {
    chip.addEventListener("click", (e) => { e.stopPropagation(); drop.classList.toggle("open"); });
    document.addEventListener("click", () => drop.classList.remove("open"));
  }

  // notifications
  const bellWrap = $("#bellWrap"), bellDrop = $("#bellDrop"), bellBtn = $("#bellBtn");
  if (bellWrap && bellDrop && bellBtn) {
    bellBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const opening = !bellDrop.classList.contains("open");
      bellDrop.classList.toggle("open");
      if (opening) {
        bellBtn.querySelector(".dot")?.remove();
        if (!__activityCache) {
          try { __activityCache = await api("/admin/activity"); } catch { __activityCache = []; }
        }
        const items = (__activityCache || []).slice(0, 8);
        bellDrop.innerHTML = `<div class="dd-head"><b>🔔 Notifications</b><small>Latest activity</small></div>` +
          (items.map(a => `<div class="notif-item"><span class="n-ico">${actionIcon(a.action)}</span>
            <div><b>${esc(a.user_name || "Guest")} · ${esc(a.action)}</b>
            <small>${esc((a.detail || "").slice(0, 52))} — ${fmtTime(a.created_at)}</small></div></div>`).join("") ||
            '<div class="empty" style="padding:16px">No activity yet.</div>');
      }
    });
    document.addEventListener("click", () => bellDrop.classList.remove("open"));
  }

  // change password
  $("#changePwForm")?.addEventListener("submit", async e => {
    e.preventDefault();
    try {
      await api("/auth/change-password", { method: "POST", body: {
        current_password: $("#pwCurrent").value, new_password: $("#pwNew").value } });
      toast("Password changed successfully 🔒");
      closeModal("changePwModal");
      e.target.reset();
    } catch (err) { toast(err.message, "err"); }
  });
  return true;
}
function actionIcon(a) {
  const map = { login: "🔑", logout: "🚪", register: "🎒", failed_login: "⚠️", lesson: "📚",
    user: "👤", content: "✏️", media: "📤", announcement: "📢", settings: "⚙️",
    password: "🔒", ai: "🤖", translation: "🌐", voice: "🎤", language: "🌍", document: "📄" };
  for (const k of Object.keys(map)) if ((a || "").includes(k)) return map[k];
  return "•";
}

/* Chart helpers */
let charts = [];
function destroyCharts() { charts.forEach(c => { try { c.destroy(); } catch {} }); charts = []; }
function makeChart(id, cfg) {
  const el = $("#" + id);
  if (!el || typeof Chart === "undefined") return null;
  const c = new Chart(el.getContext("2d"), cfg);
  charts.push(c);
  return c;
}
const PALETTE = ["#4f46e5", "#0d9488", "#f59e0b", "#dc2626", "#14b8a6", "#8b5cf6", "#ec4899", "#64748b"];

/* ================= PAGE: dashboard ================= */
async function initDashboard() {
  try {
    const d = await api("/admin/dashboard");
    const s = d.stats, t = d.trends || {}, today = d.today || {};

    $("#welcomeName").textContent = adminUser().name.split(" ")[0] || "Admin";
    const dt = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    $("#welcomeDate").textContent = dt;

    const trendPill = (v, label = "vs yesterday") => {
      if (v === undefined || v === null || v === 0) return `<span class="trend-pill flat">— ${label}</span>`;
      const cls = v > 0 ? "up" : "down";
      const sign = v > 0 ? "+" : "";
      return `<span class="trend-pill ${cls}">${sign}${v} ${label}</span>`;
    };

    const stat = (id, icon, bg, value, label, trend) => `
      <div class="stat">
        <div class="s-top"><span class="ico" style="background:${bg}">${icon}</span>${trend}</div>
        <b id="${id}">${esc(String(value))}</b><span class="lbl">${label}</span>
      </div>`;
    $("#statGrid").innerHTML =
      stat("stStudents", "🧑‍🎓", "var(--psoft)", s.total_students, "Total Students", trendPill(t.new_users)) +
      stat("stTeachers", "👩‍🏫", "var(--accent-soft)", s.total_teachers, "Total Teachers", `<span class="trend-pill flat">${s.total_tutors} tutors</span>`) +
      stat("stLessons", "📚", "var(--teal-soft)", s.total_lessons, "Total Lessons", `<span class="trend-pill up">${s.published_lessons} live</span>`) +
      stat("stAI", "🤖", "var(--danger-soft)", s.total_ai_questions, "AI Questions", trendPill(t.ai_questions)) +
      stat("stTrans", "🌐", "var(--psoft)", s.total_translations, "Translations", trendPill(t.translations)) +
      stat("stActive", "🟢", "var(--success-soft)", s.active_users, "Active Users", `<span class="trend-pill flat">${s.recently_active_users} this week</span>`);

    $("#todayChips").innerHTML = `
      <span class="badge">🤖 ${today.ai_questions || 0} questions today</span>
      <span class="badge">🌐 ${today.translations || 0} translations today</span>
      <span class="badge">👥 ${today.new_users || 0} new users today</span>
      <span class="badge">📚 ${s.total_lessons - s.published_lessons} drafts</span>
      <span class="badge">🖼 ${s.total_media} media files</span>
      <span class="badge">📢 ${s.total_announcements} announcements</span>`;

    const days = d.activity_14days || [];
    makeChart("chartGrowth", {
      type: "line",
      data: { labels: days.map(x => x.date.slice(5)), datasets: [
        { label: "New users", data: days.map(x => x.new_users), borderColor: "#4f46e5",
          backgroundColor: "rgba(79,70,229,.12)", fill: true, tension: .4, pointRadius: 2 },
        { label: "AI questions", data: days.map(x => x.ai_questions), borderColor: "#f59e0b",
          tension: .4, pointRadius: 2 },
        { label: "Translations", data: days.map(x => x.translations), borderColor: "#0d9488",
          tension: .4, pointRadius: 2 },
      ]},
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 12, usePointStyle: true } } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
    });

    makeChart("chartAI", {
      type: "bar",
      data: { labels: days.map(x => x.date.slice(5)), datasets: [
        { label: "AI questions", data: days.map(x => x.ai_questions), backgroundColor: "#4f46e5", borderRadius: 6 },
        { label: "Translations", data: days.map(x => x.translations), backgroundColor: "#0d9488", borderRadius: 6 },
      ]},
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 12, usePointStyle: true } } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
    });

    makeChart("chartLangs", {
      type: "doughnut",
      data: { labels: (d.top_languages || []).map(x => x.language),
        datasets: [{ data: (d.top_languages || []).map(x => x.count), backgroundColor: PALETTE, borderWidth: 3, borderColor: "#fff" }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "64%", plugins: { legend: { position: "bottom", labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } } } } },
    });

    // completion
    const comp = d.completion || { rate: 0, completed: 0, total: 0, by_subject: [] };
    const cData = [comp.completed, Math.max((comp.total || 0) - comp.completed, 0)];
    makeChart("chartCompletion", {
      type: "doughnut",
      data: { labels: ["Completed", "In progress"],
        datasets: [{ data: cData, backgroundColor: ["#16a34a", "#c7d2fe"], borderWidth: 3, borderColor: "#fff" }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "64%",
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } } } } },
    });
    $("#completionRate").innerHTML = `<b style="font-size:30px;letter-spacing:-.02em">${comp.rate}%</b><br><span style="color:var(--muted);font-size:12px">completion rate</span>`;
    $("#subjectBars").innerHTML = (comp.by_subject || []).length
      ? comp.by_subject.map(x => `<div class="list-row"><b>${esc(x.subject)}</b>
          <div style="display:flex;align-items:center;gap:10px;width:60%">
            <div class="mini-bar" style="flex:1"><i style="width:${Math.min(100, Math.round(x.count / Math.max(comp.completed, 1) * 100))}%"></i></div>
            <span style="font-size:12px;color:var(--muted);min-width:20px;text-align:right">${x.count}</span>
          </div></div>`).join("")
      : '<div class="empty" style="padding:14px">No completions yet.</div>';

    const act = $("#recentActivity");
    act.innerHTML = (d.recent_activity || []).map(a => `
      <div class="notif-item"><span class="n-ico">${actionIcon(a.action)}</span>
        <div style="flex:1;min-width:0"><b style="font-size:12.8px">${esc(a.user_name || "Guest")} · ${esc(a.action)}</b>
        <small style="color:var(--muted)">${esc((a.detail || "").slice(0, 60))}</small></div>
        <small style="color:var(--muted);white-space:nowrap">${fmtTime(a.created_at)}</small>
      </div>`).join("") || '<div class="empty" style="padding:16px">No activity yet.</div>';
  } catch (e) { toast(e.message, "err"); }
}

/* ================= PAGE: users ================= */
async function initUsers() {
  let users = [];
  const table = $("#usersBody");
  async function load() {
    const params = new URLSearchParams();
    const q = $("#userSearch").value.trim(); if (q) params.set("q", q);
    const role = $("#userRole").value; if (role) params.set("role", role);
    const status = $("#userStatus").value; if (status) params.set("status", status);
    users = await api("/users?" + params.toString());
    table.innerHTML = users.length ? users.map(u => `
      <tr>
        <td>
          <div class="avatar-cell">
            <span class="av" style="background:${AVATAR_COLORS[u.id % AVATAR_COLORS.length]}">${initials(u.name)}</span>
            <div><b style="font-size:13.5px">${esc(u.name)}</b><br><small style="color:var(--muted)">${esc(u.email)}</small></div>
          </div>
        </td>
        <td><span class="role-badge ${u.role}">${u.role === "admin" ? "🛡" : u.role === "teacher" ? "👩‍🏫" : u.role === "tutor" ? "🤖" : "🎒"} ${esc(u.role)}</span></td>
        <td>${esc(u.language_preference || "—")}</td>
        <td><span class="status-pill ${u.active ? "active" : "inactive"}">${u.active ? "Active" : "Inactive"}</span></td>
        <td style="white-space:nowrap">${fmtDate(u.created_at)}</td>
        <td><div class="row-actions">
          <button class="btn btn-sm btn-g" title="Edit" onclick="editUser(${u.id})">✏️</button>
          <button class="btn btn-sm btn-g" title="Activity" onclick="openUserActivity(${u.id})">🧾</button>
          <button class="btn btn-sm btn-a" title="Reset password" onclick="resetPw(${u.id})">🔑</button>
          <button class="btn btn-sm ${u.active ? "btn-g" : "btn-soft"}" title="${u.active ? "Deactivate" : "Activate"}" onclick="toggleActive(${u.id})">${u.active ? "🚫" : "✅"}</button>
          <button class="btn btn-sm btn-d" title="Delete" onclick="delUser(${u.id})">🗑</button>
        </div></td>
      </tr>`).join("") : '<tr><td colspan="6" class="empty"><div class="big">🔍</div>No users match your filters.</td></tr>';
  }
  $("#userSearch").addEventListener("keyup", load);
  $("#userRole").addEventListener("change", load);
  $("#userStatus").addEventListener("change", load);

  $("#addUserBtn").addEventListener("click", () => {
    $("#userFormTitle").textContent = "Add User";
    $("#ufId").value = ""; $("#ufName").value = ""; $("#ufEmail").value = "";
    $("#ufPw").value = ""; $("#ufRole").value = "student"; $("#ufActive").checked = true;
    $("#ufPwWrap").classList.remove("hide");
    $("#userFormSubmit").textContent = "＋ Add user";
    openModal("userModal");
  });
  window.editUser = (id) => {
    const u = users.find(x => x.id === id);
    if (!u) return;
    $("#userFormTitle").textContent = "Edit User";
    $("#ufId").value = u.id; $("#ufName").value = u.name; $("#ufEmail").value = u.email;
    $("#ufPw").value = ""; $("#ufRole").value = u.role; $("#ufActive").checked = u.active;
    $("#ufPwWrap").classList.add("hide");
    $("#userFormSubmit").textContent = "💾 Save changes";
    openModal("userModal");
  };
  $("#userForm").addEventListener("submit", async e => {
    e.preventDefault();
    const id = $("#ufId").value;
    const body = { name: $("#ufName").value.trim(), email: $("#ufEmail").value.trim(),
      role: $("#ufRole").value, active: $("#ufActive").checked };
    if (!id) body.password = $("#ufPw").value;
    try {
      if (id) { await api("/users/" + id, { method: "PUT", body }); toast("User updated ✨"); }
      else { await api("/users", { method: "POST", body }); toast("User created 🎉"); }
      closeModal("userModal"); load();
    } catch (err) { toast(err.message, "err"); }
  });
  window.toggleActive = async (id) => {
    if (!confirm("Toggle this user's active status?")) return;
    try { await api(`/users/${id}/deactivate`, { method: "POST" }); toast("Status changed."); load(); }
    catch (err) { toast(err.message, "err"); }
  };
  window.resetPw = async (id) => {
    const u = users.find(x => x.id === id);
    const pw = prompt("New password for " + (u ? u.name : "this user") + " (min 6 chars):");
    if (!pw) return;
    try { await api(`/users/${id}/reset-password`, { method: "POST", body: { new_password: pw } }); toast("Password reset 🔑"); }
    catch (err) { toast(err.message, "err"); }
  };
  window.delUser = async (id) => {
    const u = users.find(x => x.id === id);
    if (!confirm(`Delete ${u ? u.name : "this user"} permanently? This cannot be undone.`)) return;
    try { await api("/users/" + id, { method: "DELETE" }); toast("User deleted."); load(); }
    catch (err) { toast(err.message, "err"); }
  };
  window.openUserActivity = async (id) => {
    try {
      const logs = await api(`/users/${id}/activity`);
      $("#uaList").innerHTML = logs.length ? logs.map(l => `
        <div class="list-row"><div><b>${actionIcon(l.action)} ${esc(l.action)}</b>
          ${l.detail ? `<small style="color:var(--muted)"> — ${esc(l.detail.slice(0, 70))}</small>` : ""}</div>
          <small style="color:var(--muted)">${fmtTime(l.created_at)}</small></div>`).join("")
        : '<div class="empty">No activity recorded.</div>';
      openModal("userActivityModal");
    } catch (err) { toast(err.message, "err"); }
  };
  load();
}

/* ================= PAGE: lessons ================= */
let __blkSeq = 0;
function lessonBlock(type, existing = {}) {
  const host = $("#blocks");
  const row = document.createElement("div");
  row.className = "card"; row.style.cssText = "margin-bottom:10px;padding:14px;box-shadow:none";
  row.dataset.type = type;
  row.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <b style="font-size:12px">${type.toUpperCase()}</b>
      <button type="button" class="btn btn-sm btn-d" onclick="this.closest('.card').remove()">Remove</button>
    </div>
    <div class="field"><label>Title</label><input class="bTitle" maxlength="200" value="${esc(existing.title || "")}"></div>
    ${type === "text"
      ? `<div class="field"><label>Content</label><textarea class="bContent">${esc(existing.content || "")}</textarea></div>`
      : `<div class="field"><label>URL / path</label><input class="bUrl" maxlength="500" value="${esc(existing.url || "")}" placeholder="${type === "image" ? "/uploads/… or https://…" : type === "video" ? "YouTube link" : "/uploads/file.pdf"}"></div>`}`;
  host.appendChild(row);
}

async function initLessons() {
  let lessons = [];
  const body = $("#lessonsBody");
  async function load() {
    const params = new URLSearchParams();
    const q = $("#lessonSearch").value.trim(); if (q) params.set("q", q);
    const status = $("#lessonStatus").value; if (status) params.set("status", status);
    lessons = await api("/admin/lessons?" + params.toString());
    body.innerHTML = lessons.length ? lessons.map(l => `
      <tr>
        <td><b style="font-size:13.5px">${esc(l.title)}</b><br><small style="color:var(--muted)">${esc((l.description || "").slice(0, 56))}</small></td>
        <td>${esc(l.subject)}</td><td>${esc(l.language)}</td><td>${esc(l.grade || "—")}</td>
        <td>${l.views}</td>
        <td><span class="chip ${l.status === "published" ? "ok" : "a"}">${l.status === "published" ? "● Published" : "○ Draft"}</span></td>
        <td><div class="row-actions">
          <button class="btn btn-sm btn-g" title="Edit" onclick="adminEditLesson(${l.id})">✏️</button>
          <button class="btn btn-sm ${l.status === "published" ? "btn-g" : "btn-a"}" title="Toggle publish" onclick="adminPublish(${l.id})">${l.status === "published" ? "📥" : "🚀"}</button>
          <button class="btn btn-sm btn-d" title="Delete" onclick="adminDelLesson(${l.id})">🗑</button>
        </div></td>
      </tr>`).join("") : '<tr><td colspan="7" class="empty"><div class="big">📚</div>No lessons found.</td></tr>';
  }
  $("#lessonSearch").addEventListener("keyup", load);
  $("#lessonStatus").addEventListener("change", load);

  $("#newLessonBtn").addEventListener("click", () => {
    $("#lessonEditorTitle").textContent = "Create Lesson";
    ["#lTitle", "#lSubject", "#lGrade", "#lDesc", "#lThumb"].forEach(s => $(s).value = "");
    $("#lStatus").value = "draft"; $("#lLang").value = "English";
    $("#blocks").innerHTML = "";
    window.__editId = null;
    openModal("lessonEditorModal");
  });
  window.adminEditLesson = async (id) => {
    try {
      const l = await api("/lessons/" + id);
      window.__editId = id;
      $("#lessonEditorTitle").textContent = "Edit Lesson";
      $("#lTitle").value = l.title; $("#lSubject").value = l.subject;
      $("#lGrade").value = l.grade || ""; $("#lDesc").value = l.description || "";
      $("#lThumb").value = l.thumbnail || ""; $("#lStatus").value = l.status;
      $("#lLang").value = l.language || "English";
      $("#blocks").innerHTML = "";
      (l.content_items || []).forEach(c => lessonBlock(c.type, c));
      openModal("lessonEditorModal");
    } catch (err) { toast(err.message, "err"); }
  };
  $("#lessonForm").addEventListener("submit", async e => {
    e.preventDefault();
    const blocks = $$("#blocks .card").map((row, i) => {
      const type = row.dataset.type;
      return { type, title: $(".bTitle", row).value,
        content: type === "text" ? $(".bContent", row).value : "",
        url: type !== "text" ? $(".bUrl", row).value : "", sort_order: i };
    });
    const payload = { title: $("#lTitle").value.trim(), subject: $("#lSubject").value.trim(),
      grade: $("#lGrade").value.trim(), description: $("#lDesc").value,
      thumbnail: $("#lThumb").value.trim(), language: $("#lLang").value,
      status: $("#lStatus").value, content_items: blocks };
    try {
      if (window.__editId) { await api("/teacher/lessons/" + window.__editId, { method: "PUT", body: payload }); toast("Lesson updated ✨"); }
      else { await api("/teacher/lessons", { method: "POST", body: payload }); toast("Lesson created 🎉"); }
      closeModal("lessonEditorModal"); load();
    } catch (err) { toast(err.message, "err"); }
  });
  window.adminPublish = async (id) => {
    try { await api(`/teacher/lessons/${id}/publish`, { method: "POST" }); toast("Status toggled ✔"); load(); }
    catch (err) { toast(err.message, "err"); }
  };
  window.adminDelLesson = async (id) => {
    if (!confirm("Delete this lesson permanently?")) return;
    try { await api("/teacher/lessons/" + id, { method: "DELETE" }); toast("Lesson deleted."); load(); }
    catch (err) { toast(err.message, "err"); }
  };
  load();
}

/* ================= PAGE: content (text CMS + FAQ) ================= */
async function initContent() {
  const TEXT_KEYS = ["hero_title", "hero_subtitle", "about_text", "features_text",
    "ai_tutor_info", "announcements_note", "footer_text"];
  async function loadText() {
    const data = await api("/admin/content/text");
    TEXT_KEYS.forEach(k => { const el = $("#c_" + k); if (el) el.value = data.content[k] || ""; });
    let faqs = [];
    try { faqs = JSON.parse(data.content.faq || "[]"); } catch {}
    const host = $("#faqRows");
    host.innerHTML = "";
    (faqs.length ? faqs : [{ q: "", a: "" }]).forEach(f => addFaqRow(f));
  }
  function addFaqRow(f = {}) {
    const host = $("#faqRows");
    const row = document.createElement("div");
    row.className = "field-row";
    row.style.cssText = "margin-bottom:10px;grid-template-columns:1fr 1fr auto";
    row.innerHTML = `<input class="fq" placeholder="Question" value="${esc(f.q || "")}">
      <input class="fa" placeholder="Answer" value="${esc(f.a || "")}">
      <button type="button" class="btn btn-sm btn-d" onclick="this.closest('.field-row').remove()">✕</button>`;
    host.appendChild(row);
  }
  window.addFaqRow = addFaqRow;
  $("#saveTextBtn").addEventListener("click", async () => {
    const payload = {};
    TEXT_KEYS.forEach(k => payload[k] = $("#c_" + k).value);
    payload.faq = $$("#faqRows .field-row").map(r => ({ q: $(".fq", r).value.trim(), a: $(".fa", r).value.trim() }))
      .filter(x => x.q && x.a);
    try { await api("/admin/content/text", { method: "PUT", body: payload }); toast("Website content updated — live now! 🎉"); }
    catch (err) { toast(err.message, "err"); }
  });
  loadText();
}

/* ================= PAGE: media ================= */
async function initMedia() {
  let media = [], docs = [];
  const grid = $("#mediaGrid");
  async function loadMedia() {
    media = await api("/admin/media");
    grid.innerHTML = media.length ? media.map(m => `
      <div class="media-item">
        <div class="media-prev">${m.file_type === "image" ? `<img src="${esc(m.url)}" loading="lazy" alt="">`
          : m.file_type === "video" ? "🎬" : "📄"}
          <span class="type-tag">${esc(m.file_type)}</span></div>
        <div class="info"><b title="${esc(m.original_name)}">${esc(m.title || m.original_name)}</b>
          <small>${(m.size / 1024).toFixed(0)} KB · ${fmtDate(m.created_at)}</small></div>
        <div class="acts">
          <button class="btn btn-sm btn-g" onclick="editMedia(${m.id})">✏️</button>
          <button class="btn btn-sm btn-g" onclick="copyMedia('${esc(m.url)}')">📋 URL</button>
          <button class="btn btn-sm btn-d" onclick="delMedia(${m.id})">🗑</button>
        </div>
      </div>`).join("") : '<div class="empty" style="grid-column:1/-1"><div class="big">🖼</div>No files yet — drag &amp; drop to upload!</div>';
  }
  window.copyMedia = async (url) => { try { await navigator.clipboard.writeText(url); toast("URL copied: " + url); } catch { toast(url, "warn", 6000); } };
  window.editMedia = (id) => {
    const m = media.find(x => x.id === id); if (!m) return;
    $("#medTitle").value = m.title || ""; $("#medDesc").value = m.description || ""; window.__medId = id;
    openModal("mediaEditModal");
  };
  $("#mediaEditForm").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      await api("/admin/media/" + window.__medId, { method: "PUT",
        body: { title: $("#medTitle").value, description: $("#medDesc").value } });
      toast("Media updated ✨"); closeModal("mediaEditModal"); loadMedia();
    } catch (err) { toast(err.message, "err"); }
  });
  window.delMedia = async (id) => {
    if (!confirm("Delete this file permanently?")) return;
    try { await api("/admin/media/" + id, { method: "DELETE" }); toast("File deleted."); loadMedia(); }
    catch (err) { toast(err.message, "err"); }
  };

  const zone = $("#uploadZone"), fileInput = $("#uploadFile");
  zone.addEventListener("click", () => fileInput.click());
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", e => { e.preventDefault(); zone.classList.remove("drag"); uploadFiles(e.dataTransfer.files); });
  fileInput.addEventListener("change", () => uploadFiles(fileInput.files));
  async function uploadFiles(files) {
    for (const file of files) {
      const fd = new FormData();
      fd.append("file", file);
      try {
        const res = await fetch("/api/admin/media", { method: "POST",
          headers: { "Authorization": "Bearer " + token() }, body: fd });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.message || "Upload failed");
        toast("Uploaded: " + data.data.original_name);
      } catch (err) { toast(err.message, "err"); }
    }
    loadMedia(); loadDocs();
  }

  const docBody = $("#docBody");
  async function loadDocs() {
    try {
      docs = await api("/admin/documents");
      media = media.length ? media : await api("/admin/media");
      docBody.innerHTML = docs.length ? docs.map(d => `
        <tr><td><b>${esc(d.title)}</b><br><small style="color:var(--muted)">${esc(d.category)}</small></td>
        <td>${d.media_id ? '<span class="chip ok">● has file</span>' : '<span class="chip gray">link only</span>'}</td>
        <td>${fmtDate(d.created_at)}</td>
        <td><div class="row-actions"><button class="btn btn-sm btn-d" onclick="delDoc(${d.id})">🗑</button></div></td></tr>`).join("")
        : '<tr><td colspan="4" class="empty">No documents yet.</td></tr>';
      $("#docMediaSelect").innerHTML = '<option value="">— no file —</option>' + media
        .filter(m => m.file_type === "document" || m.file_type === "image")
        .map(m => `<option value="${m.id}">${esc(m.title || m.original_name)}</option>`).join("");
    } catch (err) { toast(err.message, "err"); }
  }
  window.delDoc = async (id) => {
    if (!confirm("Delete this document entry?")) return;
    try { await api("/admin/documents/" + id, { method: "DELETE" }); toast("Deleted."); loadDocs(); }
    catch (err) { toast(err.message, "err"); }
  };
  $("#docForm").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      await api("/admin/documents", { method: "POST", body: {
        title: $("#docTitle").value.trim(), category: $("#docCat").value.trim() || "Study Material",
        description: $("#docDesc").value.trim(), media_id: $("#docMediaSelect").value || null } });
      toast("Document added 📄"); e.target.reset(); loadDocs();
    } catch (err) { toast(err.message, "err"); }
  });
  loadMedia(); loadDocs();
}

/* ================= PAGE: announcements ================= */
async function initAnnouncements() {
  let anns = [];
  const ab = $("#annBody");
  async function load() {
    anns = await api("/admin/announcements");
    ab.innerHTML = anns.length ? anns.map(a => `
      <tr>
        <td><b>${esc(a.title)}</b><br><small style="color:var(--muted)">${esc((a.message || "").slice(0, 64))}</small></td>
        <td>★ ${a.priority}</td>
        <td>${scheduleText(a)}</td>
        <td>${a.active ? '<span class="chip ok">● active</span>' : '<span class="chip gray">○ inactive</span>'}</td>
        <td style="white-space:nowrap">${fmtDate(a.created_at)}</td>
        <td><div class="row-actions">
          <button class="btn btn-sm btn-g" onclick="editAnn(${a.id})">✏️</button>
          <button class="btn btn-sm btn-g" onclick="toggleAnn(${a.id})">${a.active ? "⏸" : "▶"}</button>
          <button class="btn btn-sm btn-d" onclick="delAnn(${a.id})">🗑</button>
        </div></td>
      </tr>`).join("") : '<tr><td colspan="6" class="empty"><div class="big">📢</div>No announcements yet.</td></tr>';
  }
  function scheduleText(a) {
    if (!a.start_date && !a.end_date) return '<span class="chip gray">always</span>';
    return `<small style="color:var(--muted)">${a.start_date ? fmtDate(a.start_date) : "…"} → ${a.end_date ? fmtDate(a.end_date) : "…"}</small>`;
  }
  $("#addAnnBtn").addEventListener("click", () => {
    $("#annTitle").value = ""; $("#annMsg").value = ""; $("#annImg").value = "";
    $("#annPri").value = 1; $("#annActive").checked = true;
    $("#annStart").value = ""; $("#annEnd").value = "";
    window.__annId = null;
    openModal("annModal");
  });
  window.editAnn = (id) => {
    const a = anns.find(x => x.id === id); if (!a) return;
    window.__annId = id;
    $("#annTitle").value = a.title; $("#annMsg").value = a.message;
    $("#annImg").value = a.image || ""; $("#annPri").value = a.priority; $("#annActive").checked = a.active;
    $("#annStart").value = a.start_date ? a.start_date.slice(0, 16) : "";
    $("#annEnd").value = a.end_date ? a.end_date.slice(0, 16) : "";
    openModal("annModal");
  };
  $("#annForm").addEventListener("submit", async e => {
    e.preventDefault();
    const body = { title: $("#annTitle").value.trim(), message: $("#annMsg").value.trim(),
      image: $("#annImg").value.trim(), priority: parseInt($("#annPri").value) || 0,
      active: $("#annActive").checked,
      start_date: $("#annStart").value || null, end_date: $("#annEnd").value || null };
    try {
      if (window.__annId) { await api("/admin/announcements/" + window.__annId, { method: "PUT", body }); toast("Announcement updated."); }
      else { await api("/admin/announcements", { method: "POST", body }); toast("Announcement live on the website! 📢"); }
      closeModal("annModal"); load();
    } catch (err) { toast(err.message, "err"); }
  });
  window.toggleAnn = async (id) => {
    const a = anns.find(x => x.id === id); if (!a) return;
    try { await api("/admin/announcements/" + id, { method: "PUT", body: { active: !a.active } }); load(); }
    catch (err) { toast(err.message, "err"); }
  };
  window.delAnn = async (id) => {
    if (!confirm("Delete this announcement?")) return;
    try { await api("/admin/announcements/" + id, { method: "DELETE" }); toast("Deleted."); load(); }
    catch (err) { toast(err.message, "err"); }
  };
  load();
}

/* ================= PAGE: ai (AI Assistant settings + chat log) ================= */
async function initAi() {
  let data = {};
  try { data = await api("/admin/settings"); } catch (e) { toast(e.message, "err"); }
  ["ai_enabled", "ai_system_instructions", "ai_about", "voice_input_enabled",
   "voice_output_enabled", "default_language", "ai_model_display"].forEach(k => {
    const el = $("#s_" + k);
    if (el && data[k] !== undefined) el.value = data[k];
  });
  if (data.config) {
    $("#cfgProvider").textContent = data.config.ai_provider;
    $("#cfgModel").textContent = data.config.ai_model;
    $("#cfgKey").textContent = data.config.has_api_key ? "✅ Configured (hidden)" : "❌ Not set — demo mode active";
    $("#cfgDb").textContent = data.config.database_url_scheme;
    $("#cfgTrans").textContent = data.config.translation_provider;
    $("#cfgTts").textContent = data.config.tts_provider;
  }
  $("#saveAiBtn").addEventListener("click", async () => {
    const payload = {};
    ["ai_enabled", "ai_system_instructions", "ai_about", "voice_input_enabled",
     "voice_output_enabled", "default_language", "ai_model_display"].forEach(k => {
      const el = $("#s_" + k); if (el) payload[k] = el.value;
    });
    try { await api("/admin/settings", { method: "PUT", body: payload }); toast("AI settings saved — the assistant uses them instantly 🤖"); }
    catch (err) { toast(err.message, "err"); }
  });

  // conversation log
  const tbl = $("#chatLogBody");
  try {
    const logs = await api("/admin/chat-log");
    tbl.innerHTML = logs.length ? logs.map(r => `
      <tr>
        <td><b>${esc(r.user_name || "Guest")}</b><br><small style="color:var(--muted)">${fmtTime(r.created_at)}</small></td>
        <td style="max-width:240px"><span style="font-size:13px">${esc((r.message || "").slice(0, 80))}</span></td>
        <td style="max-width:300px"><span style="font-size:12.5px;color:var(--ink2)">${esc((r.reply || "").slice(0, 110))}…</span></td>
        <td>${esc(r.language)}</td>
        <td>${r.demo_mode ? '<span class="chip a">demo</span>' : '<span class="chip ok">AI</span>'}</td>
      </tr>`).join("") : '<tr><td colspan="5" class="empty"><div class="big">💬</div>No conversations yet.</td></tr>';
  } catch (e) { toast(e.message, "err"); }
}

/* ================= PAGE: translations ================= */
async function initTranslations() {
  const body = $("#transBody");
  async function load() {
    const params = new URLSearchParams();
    const lang = $("#transLang").value; if (lang) params.set("lang", lang);
    const q = $("#transSearch").value.trim(); if (q) params.set("q", q);
    const rows = await api("/admin/translations?" + params.toString());
    const total = rows.length;
    const today = rows.filter(r => r.created_at && new Date(r.created_at).toDateString() === new Date().toDateString()).length;
    $("#transChips").innerHTML = `
      <span class="badge">🌐 ${total} translation records</span>
      <span class="badge">⚡ ${today} today</span>
      <span class="badge">🎤 ${rows.filter(r => r.provider === "voice").length} voice</span>`;
    body.innerHTML = rows.length ? rows.map(r => `
      <tr>
        <td><b>${esc(r.user_name || "Guest")}</b><br><small style="color:var(--muted)">${fmtTime(r.created_at)}</small></td>
        <td><span class="chip p">${esc(r.source_language || "?")}</span> → <span class="chip t">${esc(r.target_language || "?")}</span></td>
        <td style="max-width:260px"><span style="font-size:13px">${esc((r.source_text || "").slice(0, 70))}</span></td>
        <td style="max-width:260px"><span style="font-size:13px;color:var(--ink2)">${esc((r.translated_text || "").slice(0, 70))}</span></td>
        <td><span class="chip ${r.provider === "demo" ? "a" : r.provider === "voice" ? "gray" : "ok"}">${esc(r.provider)}</span></td>
      </tr>`).join("") : '<tr><td colspan="5" class="empty"><div class="big">🌐</div>No translations yet — try the translator on the website!</td></tr>';
  }
  $("#transLang").addEventListener("change", load);
  $("#transSearch").addEventListener("keyup", load);
  load();
}

/* ================= PAGE: analytics ================= */
async function initAnalytics() {
  try {
    const d = await api("/admin/analytics");
    const set = (id, v) => { const el = $("#" + id); if (el) el.textContent = v; };
    set("auQuestions", d.totals.ai_questions);
    set("auToday", d.totals.questions_today);
    set("auVoice", d.totals.voice_requests);
    set("auTrans", d.totals.translations);
    set("auDemo", d.totals.demo_share + "%");

    makeChart("chartDaily", {
      type: "line",
      data: { labels: d.daily.labels, datasets: [
        { label: "AI questions", data: d.daily.chat, borderColor: "#4f46e5", backgroundColor: "rgba(79,70,229,.12)", fill: true, tension: .4, pointRadius: 2 },
        { label: "Voice requests", data: d.daily.voice, borderColor: "#f59e0b", tension: .4, pointRadius: 2 },
        { label: "Translations", data: d.daily.translations, borderColor: "#0d9488", tension: .4, pointRadius: 2 },
        { label: "New users", data: d.daily.users, borderColor: "#14b8a6", tension: .4, pointRadius: 2 },
      ]},
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
    });
    makeChart("chartPairs", {
      type: "bar", indexAxis: "y",
      data: { labels: (d.language_pairs || []).map(x => `${x.from || "?"} → ${x.to}`),
        datasets: [{ data: (d.language_pairs || []).map(x => x.count), backgroundColor: "#0d9488", borderRadius: 6 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } },
    });
    makeChart("chartChatLangs", {
      type: "doughnut",
      data: { labels: (d.chat_languages || []).map(x => x.language),
        datasets: [{ data: (d.chat_languages || []).map(x => x.count), backgroundColor: PALETTE, borderWidth: 3, borderColor: "#fff" }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "62%",
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } } } } },
    });
    $("#auTopicList").innerHTML = (d.top_topics || []).map(t =>
      `<div class="list-row"><b>${esc(t.topic)}</b><span class="badge">${t.count}</span></div>`).join("") ||
      '<div class="empty">No data yet</div>';
    const comp = d.completion || {};
    $("#auCompletion").innerHTML = `
      <div style="display:flex;gap:26px;align-items:center;flex-wrap:wrap">
        <div style="text-align:center"><b style="font-size:34px;letter-spacing:-.02em">${comp.rate || 0}%</b>
          <div style="color:var(--muted);font-size:12px">completion</div></div>
        <div><div class="mini-bar" style="width:min(260px,50vw)"><i style="width:${comp.rate || 0}%"></i></div>
          <small style="color:var(--muted)">${comp.completed || 0} completed · ${comp.in_progress || 0} in progress</small></div>
      </div>`;
  } catch (e) { toast(e.message, "err"); }
}

/* ================= PAGE: activity ================= */
async function initActivity() {
  const body = $("#logBody");
  async function load() {
    const action = $("#logFilter").value.trim();
    const logs = await api("/admin/activity" + (action ? "?action=" + encodeURIComponent(action) : ""));
    body.innerHTML = logs.length ? logs.map(l => `
      <tr>
        <td><b>${actionIcon(l.action)} ${esc(l.action)}</b></td>
        <td><div class="avatar-cell" style="gap:9px">
          <span class="av" style="background:${AVATAR_COLORS[(l.user_id || 0) % AVATAR_COLORS.length]};width:32px;height:32px;font-size:11px">${initials(l.user_name || "G")}</span>
          <div><b style="font-size:13px">${esc(l.user_name || "Guest")}</b><br><small style="color:var(--muted)">${esc(l.role || "")}</small></div>
        </div></td>
        <td>${esc((l.detail || "").slice(0, 90))}</td>
        <td><small style="color:var(--muted)">${esc(l.ip || "")}</small></td>
        <td style="white-space:nowrap">${fmtTime(l.created_at)}</td>
      </tr>`).join("") : '<tr><td colspan="5" class="empty"><div class="big">🧾</div>No log entries.</td></tr>';
  }
  $("#logFilter").addEventListener("keyup", load);
  load();
}

/* ================= PAGE: settings ================= */
async function initSettings() {
  let data = {};
  try { data = await api("/admin/settings"); } catch (e) { toast(e.message, "err"); }
  const FIELDS = ["website_name", "tagline", "logo", "favicon", "contact_email", "contact_phone",
    "social_facebook", "social_twitter", "social_instagram", "social_youtube", "social_linkedin",
    "theme_mode", "default_language", "footer_text", "announcements_note"];
  FIELDS.forEach(k => { const el = $("#s_" + k); if (el && data[k] !== undefined) el.value = data[k]; });

  async function save() {
    const payload = {};
    FIELDS.forEach(k => { const el = $("#s_" + k); if (el) payload[k] = el.value; });
    try { await api("/admin/settings", { method: "PUT", body: payload }); toast("Settings saved — website picks them up instantly ✨"); }
    catch (err) { toast(err.message, "err"); }
  }
  $("#saveGeneralBtn").addEventListener("click", save);
  $("#saveContactBtn").addEventListener("click", save);
  $("#saveAppearanceBtn").addEventListener("click", save);
  $("#saveLangBtn").addEventListener("click", save);

  let langs = [];
  const lb = $("#langBody");
  async function loadLangs() {
    langs = await api("/admin/languages");
    lb.innerHTML = langs.map(l => `
      <tr>
        <td><b>${esc(l.name)}</b>${l.is_default ? ' <span class="badge">default</span>' : ""}
          <br><small style="color:var(--muted)">${esc(l.native_name)} · ${esc(l.code)}</small></td>
        <td><span class="chip ${l.active ? "ok" : "gray"}">${l.active ? "● active" : "○ inactive"}</span></td>
        <td>${l.sort_order}</td>
        <td><div class="row-actions">
          <button class="btn btn-sm btn-g" onclick="setDefaultLang(${l.id})">⭐ Default</button>
          <button class="btn btn-sm btn-g" onclick="toggleLang(${l.id})">${l.active ? "⏸" : "▶"}</button>
          <button class="btn btn-sm btn-d" onclick="delLang(${l.id})">🗑</button>
        </div></td>
      </tr>`).join("");
  }
  window.setDefaultLang = async (id) => {
    try { await api("/admin/languages/" + id, { method: "PUT", body: { is_default: true } }); toast("Default language set ⭐"); loadLangs(); }
    catch (err) { toast(err.message, "err"); }
  };
  window.toggleLang = async (id) => {
    const l = langs.find(x => x.id === id);
    try { await api("/admin/languages/" + id, { method: "PUT", body: { active: !(l && l.active) } }); loadLangs(); }
    catch (err) { toast(err.message, "err"); }
  };
  window.delLang = async (id) => {
    if (!confirm("Remove this language?")) return;
    try { await api("/admin/languages/" + id, { method: "DELETE" }); toast("Removed."); loadLangs(); }
    catch (err) { toast(err.message, "err"); }
  };
  $("#addLangBtn").addEventListener("click", () => {
    const name = prompt("Language name (e.g. Odia):");
    if (!name) return;
    const code = prompt("ISO code (e.g. or):");
    if (!code) return;
    const native = prompt("Native name (optional):") || "";
    (async () => {
      try { await api("/admin/languages", { method: "POST", body: { name, code: code.toLowerCase(), native_name: native } }); toast("Language added 🌍"); loadLangs(); }
      catch (err) { toast(err.message, "err"); }
    })();
  });
  loadLangs();
}

/* ================= boot ================= */
document.addEventListener("DOMContentLoaded", () => {
  if (!initChrome()) return;
  const page = document.body.dataset.page;
  const map = { dashboard: initDashboard, users: initUsers, lessons: initLessons,
    content: initContent, media: initMedia, announcements: initAnnouncements,
    ai: initAi, translations: initTranslations, analytics: initAnalytics,
    activity: initActivity, settings: initSettings };
  (map[page] || (() => {}))();
});
