// yWorkspace web interface (no build step): sidebar of projects, the run as a conversation, a side panel.
const $ = (s) => document.querySelector(s);
const state = { project: null, lang: localStorage.getItem("yw_lang") || "tr", models: [], busy: false,
  busyProject: null, events: [], config: {}, tab: "tasks" };

const T = {
  tr: { settings: "Ayarlar", projects: "Projeler", new_project: "Yeni proje", system: "Sistem durumu",
    greet: "Bugün ne yapalım?", working: "Çalışıyor…", goal_ph: "Ne yapalım? Örn: Kuaförler için randevu sistemi yap",
    foot: "Model bu bilgisayarda çalışıyor; kodun dışarı gönderilmez.", foot_cloud: "Yapay zekâ hata yapabilir; önemli işleri kontrol edin.",
    aut_steps: "Her adımda sor", aut_milestones: "Önemli aşamalarda sor", aut_auto: "Otomatik", q_economy: "Hızlı",
    q_balanced: "Dengeli", q_max: "En iyi kalite", tasks: "Görevler", journeys: "Kullanıcı yolculukları", files: "Dosyalar",
    changes: "Değişiklikler", log: "Günlük", preview: "Önizleme", model: "Model", budget: "Bütçe (USD)",
    sandbox: "Komutların çalıştığı yer", local: "Bu bilgisayar (Docker'sız)", projects_dir: "Proje klasörü",
    api_key: "API anahtarı ekle", save: "Kaydet", close: "Kapat", approve: "Onayla", reject: "Reddet", send: "Gönder",
    feedback_ph: "Ne değişsin? (isteğe bağlı)", answer_ph: "Cevabın…", project_name: "Proje adı:", no_tasks: "Henüz görev yok",
    no_projects: "Henüz proje yok. Aşağıya ne yapmak istediğini yaz, proje kendiliğinden açılır.",
    a_spec: "Proje tanımını onaylıyor musun?", a_plan: "Planı onaylıyor musun?", a_tool: "Bu işleme izin veriyor musun?",
    a_question: "Bir sorum var", a_deploy: "Yayına alayım mı?", finished: "Bitti", not_finished: "Bitmedi",
    setup: "Kurulum", apply: "Uygula", key_saved: "Anahtar kaydedildi", phone: "Telefon", pair: "Telefon eşleştir",
    pair_help: "Telefonun kamerasıyla QR kodu okut (5 dakika geçerli). Kod:",
    pair_lan: "Telefon bu bilgisayara ulaşamaz: yWorkspace'i `yw web --lan` ile başlat.", revoke: "Kaldır",
    last_seen: "son görülme", report: "Rapor", local_model: "yerel", tasks_done: "görev tamam",
    phases: { new: "yeni", spec: "tanım", plan: "plan", build: "yapılıyor", verify: "doğrulanıyor", done: "bitti" },
    chips: ["Kuaförler için randevu sitesi yap", "Bu projedeki hataları bul ve düzelt", "Basit bir yapılacaklar uygulaması yap",
      "CSV dosyasını özetleyen bir Python betiği yaz"] },
  en: { settings: "Settings", projects: "Projects", new_project: "New project", system: "System status",
    greet: "What shall we build today?", working: "Working…", goal_ph: "What shall we build? e.g. An appointment system for hair salons",
    foot: "The model runs on this computer; your code never leaves it.", foot_cloud: "AI can make mistakes; check important work.",
    aut_steps: "Ask at every step", aut_milestones: "Ask at milestones", aut_auto: "Automatic", q_economy: "Fast",
    q_balanced: "Balanced", q_max: "Best quality", tasks: "Tasks", journeys: "User journeys", files: "Files",
    changes: "Changes", log: "Log", preview: "Preview", model: "Model", budget: "Budget (USD)",
    sandbox: "Where commands run", local: "This computer (no Docker)", projects_dir: "Projects folder",
    api_key: "Add an API key", save: "Save", close: "Close", approve: "Approve", reject: "Reject", send: "Send",
    feedback_ph: "What should change? (optional)", answer_ph: "Your answer…", project_name: "Project name:", no_tasks: "No tasks yet",
    no_projects: "No projects yet. Type what you want below and one opens by itself.",
    a_spec: "Approve the specification?", a_plan: "Approve the plan?", a_tool: "Allow this action?",
    a_question: "I have a question", a_deploy: "Deploy now?", finished: "Done", not_finished: "Not finished",
    setup: "Setup", apply: "Apply", key_saved: "Key saved", phone: "Phone", pair: "Pair a phone",
    pair_help: "Scan the QR code with the phone's camera (valid for 5 minutes). Code:",
    pair_lan: "The phone cannot reach this computer: start yWorkspace with `yw web --lan`.", revoke: "Remove",
    last_seen: "last seen", report: "Report", local_model: "local", tasks_done: "tasks done",
    phases: { new: "new", spec: "spec", plan: "plan", build: "building", verify: "verifying", done: "done" },
    chips: ["Build an appointment site for hair salons", "Find and fix the bugs in this project", "Make a simple to-do app",
      "Write a Python script that summarizes a CSV file"] },
};
const t = (k) => (T[state.lang] && T[state.lang][k]) || T.en[k] || k;

const FRIENDLY = {
  tr: { read: "Dosya okundu", outline: "Dosya yapısına bakıldı", create: "Dosya oluşturuldu", edit: "Dosya düzenlendi",
    multi_edit: "Dosya düzenlendi", delete: "Dosya silindi", list: "Proje incelendi", search: "Kodda arandı",
    run: "Komut çalıştırıldı", start_process: "Uygulama başlatıldı", install: "Paket kuruldu", check: "Testler çalıştırıldı",
    plan_set_spec: "Proje tanımı yazıldı", plan_add_tasks: "Plan çıkarıldı", plan_update: "Görev güncellendi",
    screen_open: "Uygulama açılıp denendi", tap: "Uygulamada tıklandı", type: "Uygulamaya yazıldı",
    journey_result: "Kullanıcı yolculuğu sonuçlandı", git_commit: "Değişiklikler kaydedildi", memory_note: "Not alındı",
    review_verdict: "İnceleme tamamlandı", plan_show: "Plana bakıldı" },
  en: { read: "Read a file", outline: "Looked at file structure", create: "Created a file", edit: "Edited a file",
    multi_edit: "Edited a file", delete: "Deleted a file", list: "Explored the project", search: "Searched the code",
    run: "Ran a command", start_process: "Started the app", install: "Installed packages", check: "Ran the tests",
    plan_set_spec: "Wrote the specification", plan_add_tasks: "Made the plan", plan_update: "Updated a task",
    screen_open: "Opened and tried the app", tap: "Clicked in the app", type: "Typed in the app",
    journey_result: "Finished a user journey", git_commit: "Saved the changes", memory_note: "Took a note",
    review_verdict: "Review finished", plan_show: "Looked at the plan" },
};
const ROLES = { analyst: ["Analist", "Analyst"], architect: ["Mimar", "Architect"], developer: ["Geliştirici", "Developer"],
  tester: ["Test uzmanı", "Tester"], reviewer: ["İnceleyici", "Reviewer"], debugger: ["Hata ayıklayıcı", "Debugger"],
  test_user: ["Test kullanıcısı", "Test user"], merger: ["Birleştirici", "Merger"], director: ["Yönetmen", "Director"] };

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

// ------------------------------------------------------------------ markdown (escaped first, then a small subset)
function esc(s) { return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function inline(s) {
  return s.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}
function md(text) {
  const out = [];
  const parts = (text || "").split(/```[^\n]*\n?/);
  parts.forEach((part, i) => {
    if (i % 2) { out.push(`<pre><code>${esc(part.replace(/\n$/, ""))}</code></pre>`); return; }
    let list = null;
    const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
    let para = [];
    const flush = () => { if (para.length) { out.push(`<p>${para.join("<br>")}</p>`); para = []; } };
    for (const raw of part.split("\n")) {
      const line = esc(raw);
      let m;
      if (!line.trim()) { flush(); close(); continue; }
      if ((m = line.match(/^(#{1,3})\s+(.*)/))) { flush(); close(); out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`); continue; }
      if ((m = line.match(/^\s*[-*•]\s+(.*)/))) { flush(); if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inline(m[1])}</li>`); continue; }
      if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { flush(); if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inline(m[1])}</li>`); continue; }
      close(); para.push(inline(line));
    }
    flush(); close();
  });
  return out.join("");
}

// ------------------------------------------------------------------ i18n
function applyI18n() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((e) => { e.textContent = t(e.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach((e) => { e.placeholder = t(e.dataset.i18nPh); });
  $("#langBtn").textContent = state.lang === "tr" ? "EN" : "TR";
  const chips = $("#chips"); chips.innerHTML = "";
  for (const c of t("chips")) { const b = el("button", "", c); b.onclick = () => { $("#goal").value = c; autosize(); $("#goal").focus(); }; chips.appendChild(b); }
  syncModelChip();
  render();
}

// ------------------------------------------------------------------ conversation
function argSummary(args) {
  if (!args || typeof args !== "object") return "";
  const v = args.path || args.command || args.cmd || args.query || args.pattern || args.target || args.name || args.title || "";
  return typeof v === "string" ? v : JSON.stringify(v);
}

let lastTool = null;

function render() {
  $("#thread").innerHTML = ""; lastTool = null;
  const evs = state.events.filter((e) => !e.project || e.project === state.project);
  for (const e of evs) append(e);
  afterAppend(true);
}

function afterAppend(force) {
  const s = $("#scroller");
  const nearBottom = s.scrollHeight - s.scrollTop - s.clientHeight < 160;
  const evs = state.events.filter((e) => !e.project || e.project === state.project);
  $("#empty").hidden = evs.length > 0;
  $("#working").hidden = !(state.busy && state.busyProject === state.project);
  if (force || nearBottom) requestAnimationFrame(() => { s.scrollTop = s.scrollHeight; });
}

function append(e) {
  const thread = $("#thread");
  const L = state.lang === "tr" ? 0 : 1;
  {
    switch (e.kind) {
      case "run_started": thread.appendChild(el("div", "msg-user", e.text)); lastTool = null; break;
      case "assistant": { const d = el("div", "msg-ai md"); d.innerHTML = md(e.text); thread.appendChild(d); lastTool = null; break; }
      case "tool_call": {
        const d = el("details", "tool run");
        const s = el("summary");
        s.append(el("span", "st", "●"), el("span", "lbl", FRIENDLY[state.lang][e.text] || e.text),
          el("span", "arg", argSummary(e.data && e.data.args)), el("span", "chev", "›"));
        const pre = el("pre", "", `${e.text} ${JSON.stringify((e.data && e.data.args) || {}, null, 1).slice(0, 1500)}`);
        d.append(s, pre); thread.appendChild(d); lastTool = d; break;
      }
      case "tool_result": {
        const err = e.data && e.data.is_error;
        if (lastTool) {
          lastTool.classList.remove("run"); lastTool.classList.add(err ? "err" : "ok");
          lastTool.querySelector(".st").textContent = err ? "✕" : "✓";
          lastTool.querySelector("pre").textContent += "\n\n" + e.text.slice(0, 3000);
          if (err) lastTool.open = true;
        } else if (err) thread.appendChild(el("div", "err-box", e.text.slice(0, 1500)));
        lastTool = null; break;
      }
      case "info":
        if (e.text.startsWith("model:")) break;  // which model a role uses: shown in the detailed log only
        if (e.text.startsWith("role:")) { const r = ROLES[e.text.slice(5)]; thread.appendChild(el("div", "role", r ? r[L] : e.text.slice(5))); }
        else thread.appendChild(el("div", "note", e.text));
        break;
      case "error": thread.appendChild(el("div", "err-box", e.text)); break;
      case "run_finished": {
        const ok = e.data && e.data.finished;
        const box = el("div", "done-box" + (ok ? "" : " no"));
        box.appendChild(el("h4", "", ok ? "✓ " + t("finished") : "! " + t("not_finished") + (e.data && e.data.reason ? " — " + e.data.reason : "")));
        const body = el("div", "md"); body.innerHTML = md(e.text); box.appendChild(body);
        thread.appendChild(box); break;
      }
    }
  }
}

function onEvent(e) {
  if (e.kind === "approval") { showApproval(e); return; }
  if (e.kind === "approval_done") { document.getElementById("ap-" + e.id)?.remove(); return; }
  if (e.project && history[e.project] !== undefined && (e.time || 0) <= history[e.project]) return;  // already loaded from disk
  state.events.push(e);
  if (state.events.length > 1500) state.events.splice(0, state.events.length - 1500);
  if (e.kind === "run_started") { state.busy = true; state.busyProject = e.project; syncBusy(); loadProjects(); }
  if (e.kind === "run_finished" || (e.kind === "error" && !e.data)) { state.busy = false; syncBusy(); refreshState(); loadProjects(); }
  if (e.kind === "info") refreshState();
  if (!e.project || e.project === state.project) {
    const s = $("#scroller");
    const nearBottom = s.scrollHeight - s.scrollTop - s.clientHeight < 160;
    append(e); afterAppend(nearBottom);
  }
}

function showApproval(e) {
  if (document.getElementById("ap-" + e.id)) return;
  const box = el("div", "approval"); box.id = "ap-" + e.id;
  const body = el("div", "body md"); body.innerHTML = md(e.text);
  const row = el("div", "row");
  const fb = el("input"); fb.placeholder = e.type === "question" ? t("answer_ph") : t("feedback_ph");
  const yes = el("button", "primary", e.type === "question" ? t("send") : t("approve"));
  const no = el("button", "", t("reject"));
  const send = async (ok) => {
    box.remove();  // at once, so a second card that follows is never mistaken for this one
    try { await api("/api/approve", { method: "POST", body: JSON.stringify({ id: e.id, ok, feedback: fb.value }) }); }
    catch (err) { $("#approvals").appendChild(box); alert(err.message); }
  };
  yes.onclick = () => send(true); no.onclick = () => send(false);
  fb.onkeydown = (k) => { if (k.key === "Enter") send(true); };
  row.append(fb); if (e.type !== "question") row.append(no); row.append(yes);
  box.append(el("h4", "", t("a_" + e.type)), body, row);
  $("#approvals").appendChild(box);
  fb.focus();
}

function syncBusy() {
  const mine = state.busy && state.busyProject === state.project;
  $("#runBtn").hidden = mine; $("#stopBtn").hidden = !mine;
  $("#runBtn").disabled = state.busy;
  $("#working").hidden = !mine;
}

// ------------------------------------------------------------------ projects and state
async function loadProjects() {
  const list = await api("/api/projects");
  const ul = $("#projectList"); ul.innerHTML = "";
  if (!list.length) ul.appendChild(el("li", "empty-note", t("no_projects")));
  for (const p of list) {
    const li = el("li");
    if (state.busy && state.busyProject === p.name) li.appendChild(el("span", "live"));
    li.appendChild(document.createTextNode(p.name));
    li.title = p.goal || p.name;
    if (p.name === state.project) li.className = "on";
    li.onclick = () => selectProject(p.name);
    ul.appendChild(li);
  }
  if (!state.project && list.length) {
    const saved = localStorage.getItem("yw_project");
    selectProject(list.some((p) => p.name === saved) ? saved : list[0].name);
  }
}

function selectProject(name) {
  state.project = name;
  if (name) localStorage.setItem("yw_project", name);
  document.body.classList.remove("sb-open");
  $("#projTitle").textContent = name || "yWorkspace";
  document.querySelectorAll("#projectList li").forEach((li) => li.classList.toggle("on", li.textContent === name));
  syncBusy(); render(); refreshState(); loadConversation(name);
  if (state.tab !== "tasks") openTab(state.tab);
}

// The project's earlier conversation, kept on disk by the server; live events newer than it are kept too.
const history = {};
async function loadConversation(name) {
  if (!name || history[name] !== undefined) return;
  let saved;
  try { saved = await api(`/api/projects/${encodeURIComponent(name)}/conversation`); } catch { return; }
  const last = saved.length ? saved[saved.length - 1].time || 0 : 0;
  history[name] = last;
  const live = state.events.filter((e) => e.project !== name || (e.time || 0) > last);
  state.events = [...saved, ...live];
  if (state.project === name) render();
}

async function refreshState() {
  if (!state.project) { $("#phase").hidden = true; $("#progressMini").hidden = true; $("#cost").textContent = ""; return; }
  let s;
  try { s = await api(`/api/projects/${encodeURIComponent(state.project)}/state`); } catch { return; }
  const ph = t("phases");
  $("#phase").hidden = !s.phase; $("#phase").textContent = ph[s.phase] || s.phase;
  const done = s.tasks.filter((x) => x.status === "done").length;
  $("#progressMini").hidden = !s.tasks.length;
  $("#summary").textContent = `${done}/${s.tasks.length} ${t("tasks_done")}`;
  $("#barFill").style.width = s.tasks.length ? `${(100 * done) / s.tasks.length}%` : "0";
  const tokens = s.tokens_in + s.tokens_out;
  $("#cost").textContent = tokens ? `${tokens.toLocaleString(state.lang)} token` + (s.cost_usd > 0 ? ` · $${s.cost_usd.toFixed(3)}` : "") : "";
  $("#cost").title = Object.keys(s.cost_by_model || {}).join(", ");
  const ul = $("#tasks"); ul.innerHTML = "";
  if (!s.tasks.length) ul.appendChild(el("li", "none", t("no_tasks")));
  for (const task of s.tasks) { const li = el("li", task.status, `${task.title}`); li.title = (task.acceptance || []).join("\n"); ul.appendChild(li); }
  const jl = $("#journeys"); jl.innerHTML = "";
  for (const j of s.journeys) { const li = el("li", j.passed ? "done" : "blocked", `${j.name} (${j.persona})`); li.title = j.notes; jl.appendChild(li); }
  $("#specView").innerHTML = s.spec ? md(s.spec) : "—";
  $("#logView").textContent = s.progress || "—";
}

function slug(text) {
  const map = { ç: "c", ğ: "g", ı: "i", ö: "o", ş: "s", ü: "u", Ç: "c", Ğ: "g", İ: "i", Ö: "o", Ş: "s", Ü: "u" };
  const s = text.replace(/[çğıöşüÇĞİÖŞÜ]/g, (c) => map[c]).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()
    .split(/\s+/).slice(0, 4).join("-");
  return s || "proje";
}

async function send() {
  const goal = $("#goal").value.trim();
  if (!goal || state.busy) return;
  try {
    if (!state.project) {
      const r = await api("/api/projects", { method: "POST", body: JSON.stringify({ name: slug(goal) }) });
      await loadProjects(); selectProject(r.name);
    }
    await api("/api/run", { method: "POST", body: JSON.stringify({ project: state.project, goal,
      autonomy: $("#autonomy").value, quality: $("#quality").value }) });
    $("#goal").value = ""; autosize();
    state.busy = true; state.busyProject = state.project; syncBusy();
  } catch (e) { state.events.push({ kind: "error", project: state.project, text: e.message }); render(); }
}

// ------------------------------------------------------------------ side panel
function openTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x.dataset.tab === tab));
  document.querySelectorAll(".tabbody").forEach((x) => { x.hidden = x.id !== "tab-" + tab; });
  if (tab === "files") loadFile(); if (tab === "diff") loadDiff(); if (["tasks", "spec", "log"].includes(tab)) refreshState();
}
function togglePanel(show) {
  const p = $("#panel"); const on = show === undefined ? p.hidden : show;
  p.hidden = !on; localStorage.setItem("yw_panel", on ? "1" : "0");
  if (on) openTab(state.tab);
}

async function loadFile() {
  if (!state.project) return;
  try {
    const r = await api(`/api/projects/${encodeURIComponent(state.project)}/files?path=${encodeURIComponent($("#filePath").value)}`);
    $("#fileView").textContent = r.listing || r.content;
  } catch (e) { $("#fileView").textContent = e.message; }
}

async function loadDiff() {
  if (!state.project) return;
  const r = await api(`/api/projects/${encodeURIComponent(state.project)}/history`);
  $("#diffView").textContent = (r.history || "—") + "\n\n" + (r.diff || "");
}

// ------------------------------------------------------------------ status, settings, setup
async function loadStatus() {
  const s = await api("/api/status");
  state.busy = s.busy; state.busyProject = s.project; state.config = s.config; syncBusy();
  $("#autonomy").value = s.config.autonomy; $("#quality").value = s.config.quality;
  const h = $("#health"); h.innerHTML = "";
  let allOk = true;
  for (const item of s.health) {
    allOk = allOk && item.ok;
    h.appendChild(el("div", item.ok ? "ok" : "bad", item.name + (item.detail && !item.ok ? ` — ${item.detail}` : "")));
  }
  $("#healthDot").className = "dot " + (allOk ? "ok" : "bad");
  state.models = await api("/api/models");
  syncModelChip();
}

function syncModelChip() {
  const m = state.models.find((x) => x.id === state.config.model);
  $("#modelChip").textContent = m ? `${m.model}${m.local ? " · " + t("local_model") : ""}` : (state.config.model || "");
  const local = m ? m.local : false;
  document.querySelector(".foot").textContent = local ? t("foot") : t("foot_cloud");
  $("#keyBox").hidden = state.models.length > 0 && state.models.every((x) => x.local);
}

async function openSettings() {
  state.models = await api("/api/models");
  const sel = $("#setModel"); sel.innerHTML = "";
  for (const m of state.models) { const o = el("option", "", `${m.id}${m.has_key ? " ✓" : ""}`); o.value = m.id; sel.appendChild(o); }
  sel.value = state.config.model; $("#setBudget").value = state.config.budget_usd;
  $("#setSandbox").value = state.config.sandbox; $("#setDir").value = state.config.projects_dir;
  $("#settings").showModal();
  loadSetup(); loadDevices();
}

async function loadSetup() {
  const s = await api("/api/setup");
  $("#sysInfo").textContent = s.system;
  const ul = $("#setupSteps"); ul.innerHTML = "";
  for (const st of s.steps) {
    const li = el("li", st.ok ? "done" : (st.skipped ? "todo" : "blocked"), `${state.lang === "tr" ? st.title_tr : st.title_en} ${st.detail ? "— " + st.detail : ""} `);
    if (!st.ok) {
      const b = el("button", "small", t("apply")); b.type = "button";
      b.onclick = async () => {
        const out = $("#setupOut"); out.hidden = false;
        const plan = await api(`/api/setup/${st.id}`, { method: "POST", body: JSON.stringify({ run: false }) });
        out.textContent = plan.plan.map((a) => `• ${a.describe}${a.command ? "\n  $ " + a.command : ""}${a.manual ? "\n  " + a.manual : ""}`).join("\n");
        const res = await api(`/api/setup/${st.id}`, { method: "POST", body: JSON.stringify({ run: true }) });
        out.textContent += "\n\n" + (res.results || []).join("\n");
        loadSetup(); loadStatus();
      };
      li.appendChild(b);
    }
    ul.appendChild(li);
  }
}

async function startPairing() {
  try {
    const p = await api("/api/pair/start", { method: "POST" });
    $("#pairBox").hidden = false;
    $("#pairQr").innerHTML = p.svg;  // generated by the server's own QR encoder
    $("#pairInfo").textContent = `${t("pair_help")} ${p.code} — ${p.link}` + (p.lan ? "" : "\n" + t("pair_lan"));
    const until = Date.now() + p.expires_in * 1000;
    const poll = setInterval(async () => { if (Date.now() > until) { clearInterval(poll); $("#pairBox").hidden = true; } loadDevices(); }, 3000);
  } catch (e) { alert(e.message); }
}

async function loadDevices() {
  const ul = $("#deviceList");
  try {
    const list = await api("/api/devices");
    ul.innerHTML = "";
    for (const d of list) {
      const li = el("li", "", `📱 ${d.name} — ${t("last_seen")} ${new Date(d.last_seen * 1000).toLocaleString(state.lang)}`);
      const b = el("button", "small ghost", t("revoke")); b.type = "button";
      b.onclick = async () => { await api("/api/devices/" + d.id, { method: "DELETE" }); loadDevices(); };
      li.appendChild(b); ul.appendChild(li);
    }
  } catch { ul.innerHTML = ""; }
}

// ------------------------------------------------------------------ wiring
function autosize() { const g = $("#goal"); g.style.height = "auto"; g.style.height = Math.min(g.scrollHeight, 260) + "px"; }

function wire() {
  const savedTheme = localStorage.getItem("yw_theme"); if (savedTheme) document.documentElement.dataset.theme = savedTheme;
  $("#themeBtn").onclick = () => {
    const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    const next = dark ? "light" : "dark"; document.documentElement.dataset.theme = next; localStorage.setItem("yw_theme", next);
  };
  $("#langBtn").onclick = () => { state.lang = state.lang === "tr" ? "en" : "tr"; localStorage.setItem("yw_lang", state.lang); applyI18n(); refreshState(); };
  $("#newProject").onclick = async () => {
    const name = prompt(t("project_name")); if (!name) return;
    const r = await api("/api/projects", { method: "POST", body: JSON.stringify({ name }) });
    await loadProjects(); selectProject(r.name); $("#goal").focus();
  };
  $("#goal").addEventListener("input", autosize);
  $("#goal").addEventListener("keydown", (k) => { if (k.key === "Enter" && !k.shiftKey && !k.isComposing) { k.preventDefault(); send(); } });
  $("#runBtn").onclick = send;
  $("#stopBtn").onclick = () => api("/api/stop", { method: "POST" });
  $("#settingsBtn").onclick = openSettings;
  $("#pairBtn").onclick = startPairing;
  $("#saveSettings").onclick = async () => {
    await api("/api/config", { method: "PUT", body: JSON.stringify({ model: $("#setModel").value, budget_usd: parseFloat($("#setBudget").value),
      sandbox: $("#setSandbox").value, projects_dir: $("#setDir").value }) });
    loadStatus(); loadProjects();
  };
  $("#saveKey").onclick = async () => {
    try { await api("/api/keys", { method: "POST", body: JSON.stringify({ name: $("#keyName").value.trim(), value: $("#keyValue").value.trim() }) });
      $("#keyValue").value = ""; alert(t("key_saved")); loadStatus(); } catch (e) { alert(e.message); }
  };
  $("#autonomy").onchange = () => api("/api/config", { method: "PUT", body: JSON.stringify({ autonomy: $("#autonomy").value }) }).catch(() => {});
  $("#quality").onchange = () => api("/api/config", { method: "PUT", body: JSON.stringify({ quality: $("#quality").value }) }).catch(() => {});
  document.querySelectorAll(".tab").forEach((b) => { b.onclick = () => openTab(b.dataset.tab); });
  $("#panelBtn").onclick = () => togglePanel();
  $("#closePanel").onclick = () => togglePanel(false);
  $("#openSidebar").onclick = () => document.body.classList.add("sb-open");
  $("#closeSidebar").onclick = () => document.body.classList.remove("sb-open");
  $("#scrim").onclick = () => document.body.classList.remove("sb-open");
  $("#filePath").onchange = loadFile;
  $("#previewUrl").onchange = () => { $("#previewFrame").src = $("#previewUrl").value; };
  if (localStorage.getItem("yw_panel") === "1" && innerWidth > 1100) togglePanel(true);
}

function connect() {
  const es = new EventSource("/api/events");
  es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch (err) { console.error(err); } };
  es.onerror = () => {
    es.close(); state.events = [];
    for (const k of Object.keys(history)) delete history[k];  // reload from disk after reconnecting
    setTimeout(() => { connect(); loadConversation(state.project); }, 3000);
  };
}

wire(); applyI18n();
loadStatus().then(loadProjects).then(connect).then(() => $("#goal").focus())
  .catch((e) => { state.events.push({ kind: "error", text: e.message }); render(); });
