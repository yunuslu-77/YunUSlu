// yWorkspace web interface (no build step).
const $ = (s) => document.querySelector(s);
const state = { project: null, lang: localStorage.getItem("yw_lang") || "tr", models: [], busy: false };

const T = {
  tr: { simple: "Basit", detailed: "Detaylı", settings: "Ayarlar", projects: "Projeler", new: "+ Yeni",
    goal_ph: "Ne yapalım? Örn: Kuaförler için randevu sistemi yap", aut_steps: "Her adımda onay",
    aut_milestones: "Önemli aşamalarda onay", aut_auto: "Tamamen otomatik", q_economy: "Ekonomik",
    q_balanced: "Dengeli", q_max: "Maksimum kalite", stop: "Durdur", start: "Başlat", activity: "Neler oluyor",
    tasks: "Görevler", journeys: "Kullanıcı yolculukları", files: "Dosyalar", changes: "Değişiklikler", log: "Günlük",
    preview: "Önizleme", model: "Model", budget: "Bütçe (USD)", sandbox: "Komutların çalıştığı yer",
    local: "Bu bilgisayar (Docker'sız)", projects_dir: "Proje klasörü", api_key: "API anahtarı ekle", save: "Kaydet",
    close: "Kapat", approve: "Onayla", reject: "Reddet", change: "Değiştir", feedback_ph: "Ne değişsin? (isteğe bağlı)",
    project_name: "Proje adı:", pick_project: "Önce bir proje seç ya da oluştur.", no_tasks: "Henüz görev yok",
    a_spec: "Proje tanımını onaylıyor musun?", a_plan: "Planı onaylıyor musun?", a_tool: "Bu işleme izin var mı?",
    a_question: "Yapay zekâ bir şey soruyor", a_deploy: "Yayına alayım mı?", saved: "Kaydedildi",
    started: "Başladı", finished: "Bitti ✓", setup: "Kurulum", apply: "Uygula", not_finished: "Bitmedi", key_saved: "Anahtar kaydedildi",
    phone: "Telefon", pair: "Telefon eşleştir", pair_help: "Telefonun kamerasıyla QR kodu okut (5 dakika geçerli). Kod:",
    pair_lan: "Telefon bu bilgisayara ulaşamaz: yWorkspace'i `yw web --lan` ile başlat.", revoke: "Kaldır", last_seen: "son görülme" },
  en: { simple: "Simple", detailed: "Detailed", settings: "Settings", projects: "Projects", new: "+ New",
    goal_ph: "What shall we build? e.g. An appointment system for hair salons", aut_steps: "Approve every step",
    aut_milestones: "Approve milestones", aut_auto: "Fully automatic", q_economy: "Economy", q_balanced: "Balanced",
    q_max: "Maximum quality", stop: "Stop", start: "Start", activity: "What's happening", tasks: "Tasks",
    journeys: "User journeys", files: "Files", changes: "Changes", log: "Log", preview: "Preview", model: "Model",
    budget: "Budget (USD)", sandbox: "Where commands run", local: "This computer (no Docker)",
    projects_dir: "Projects folder", api_key: "Add an API key", save: "Save", close: "Close", approve: "Approve",
    reject: "Reject", change: "Change", feedback_ph: "What should change? (optional)", project_name: "Project name:",
    pick_project: "Pick or create a project first.", no_tasks: "No tasks yet", a_spec: "Approve the specification?",
    a_plan: "Approve the plan?", a_tool: "Allow this action?", a_question: "The AI has a question",
    a_deploy: "Deploy now?", saved: "Saved", started: "Started", finished: "Done ✓", setup: "Setup", apply: "Apply", not_finished: "Not finished",
    key_saved: "Key saved", phone: "Phone", pair: "Pair a phone",
    pair_help: "Scan the QR code with the phone's camera (valid for 5 minutes). Code:",
    pair_lan: "The phone cannot reach this computer: start yWorkspace with `yw web --lan`.", revoke: "Remove", last_seen: "last seen" },
};
const t = (k) => (T[state.lang] && T[state.lang][k]) || T.en[k] || k;

const FRIENDLY = {
  tr: { read: "Dosya okunuyor", outline: "Dosya yapısına bakılıyor", create: "Dosya oluşturuldu", edit: "Dosya düzenlendi",
    multi_edit: "Dosya düzenlendi", delete: "Dosya silindi", list: "Proje inceleniyor", search: "Kodda arama yapılıyor",
    run: "Komut çalıştırıldı", start_process: "Uygulama başlatıldı", install: "Paket kuruluyor", check: "Testler çalıştırıldı",
    plan_set_spec: "Proje tanımı yazıldı", plan_add_tasks: "Plan çıkarıldı", plan_update: "Görev güncellendi",
    screen_open: "Uygulama açılıp deneniyor", tap: "Uygulamada tıklandı", type: "Uygulamaya yazıldı",
    journey_result: "Kullanıcı yolculuğu sonuçlandı", git_commit: "Değişiklikler kaydedildi", memory_note: "Not alındı",
    review_verdict: "İnceleme tamamlandı" },
  en: { read: "Reading a file", outline: "Looking at file structure", create: "Created a file", edit: "Edited a file",
    multi_edit: "Edited a file", delete: "Deleted a file", list: "Exploring the project", search: "Searching the code",
    run: "Ran a command", start_process: "Started the app", install: "Installing packages", check: "Ran the tests",
    plan_set_spec: "Wrote the specification", plan_add_tasks: "Made the plan", plan_update: "Updated a task",
    screen_open: "Opening and trying the app", tap: "Clicked in the app", type: "Typed in the app",
    journey_result: "Finished a user journey", git_commit: "Saved the changes", memory_note: "Took a note",
    review_verdict: "Review finished" },
};
const ROLES = { analyst: ["Analist", "Analyst"], architect: ["Mimar", "Architect"], developer: ["Geliştirici", "Developer"],
  tester: ["Test uzmanı", "Tester"], reviewer: ["İnceleyici", "Reviewer"], debugger: ["Hata ayıklayıcı", "Debugger"],
  test_user: ["Test kullanıcısı", "Test user"], merger: ["Birleştirici", "Merger"], director: ["Yönetmen", "Director"] };

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

function applyI18n() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  $("#langBtn").textContent = state.lang === "tr" ? "EN" : "TR";
}

function addFeed(kind, text, tech) {
  const li = document.createElement("li");
  li.className = kind;
  li.textContent = text;
  if (tech) { const d = document.createElement("div"); d.className = "tech"; d.textContent = tech; li.appendChild(d); }
  const feed = $("#feed");
  feed.appendChild(li);
  while (feed.children.length > 400) feed.firstChild.remove();
  feed.scrollTop = feed.scrollHeight;
}

function onEvent(e) {
  if (e.project && state.project && e.project !== state.project) return;
  const L = state.lang === "tr" ? 0 : 1;
  switch (e.kind) {
    case "assistant": addFeed("assistant", e.text.slice(0, 600)); break;
    case "tool_call": addFeed("tool", (FRIENDLY[state.lang][e.text] || e.text), `${e.text} ${JSON.stringify(e.data.args || {}).slice(0, 300)}`); break;
    case "tool_result": if (e.data && e.data.is_error) addFeed("error", "⚠ " + e.text.split("\n")[0].slice(0, 200), e.text.slice(0, 1500));
      else { const last = $("#feed").lastElementChild; if (last && last.querySelector(".tech")) last.querySelector(".tech").textContent += "\n" + e.text.slice(0, 800); }
      break;
    case "info":
      if (e.text.startsWith("role:")) { const r = ROLES[e.text.slice(5)]; addFeed("info", "▶ " + (r ? r[L] : e.text.slice(5))); }
      else addFeed("info", e.text);
      refreshState(); break;
    case "error": addFeed("error", e.text); break;
    case "run_started": state.busy = true; syncBusy(); addFeed("info", t("started") + ": " + e.text); break;
    case "run_finished": state.busy = false; syncBusy(); addFeed("done", e.data.finished ? t("finished") : t("not_finished") + " — " + e.data.reason, e.text); refreshState(); break;
    case "approval": showApproval(e); break;
    case "approval_done": document.getElementById("ap-" + e.id)?.remove(); break;
  }
}

function showApproval(e) {
  if (document.getElementById("ap-" + e.id)) return;
  const box = document.createElement("div");
  box.className = "approval"; box.id = "ap-" + e.id;
  const h = document.createElement("h4"); h.textContent = t("a_" + e.type);
  const pre = document.createElement("pre"); pre.textContent = e.text;
  const row = document.createElement("div"); row.className = "row";
  const fb = document.createElement("input"); fb.placeholder = t("feedback_ph");
  const yes = document.createElement("button"); yes.className = "primary"; yes.textContent = e.type === "question" ? t("save") : t("approve");
  const no = document.createElement("button"); no.textContent = t("reject");
  const send = async (ok) => { await api("/api/approve", { method: "POST", body: JSON.stringify({ id: e.id, ok, feedback: fb.value }) }); box.remove(); };
  yes.onclick = () => send(true); no.onclick = () => send(false);
  row.append(fb, yes); if (e.type !== "question") row.append(no);
  box.append(h, pre, row);
  $("#approvals").appendChild(box);
}

function syncBusy() { $("#runBtn").disabled = state.busy; $("#stopBtn").hidden = !state.busy; }

async function loadProjects() {
  const list = await api("/api/projects");
  const ul = $("#projectList"); ul.innerHTML = "";
  for (const p of list) {
    const li = document.createElement("li");
    li.textContent = p.name;
    const s = document.createElement("small"); s.textContent = p.goal ? p.goal.slice(0, 60) : (state.lang === "tr" ? "henüz görev yok" : "no goal yet"); li.appendChild(s);
    if (p.name === state.project) li.className = "on";
    li.onclick = () => { state.project = p.name; localStorage.setItem("yw_project", p.name); loadProjects(); refreshState(); };
    ul.appendChild(li);
  }
  if (!state.project && list.length) { state.project = localStorage.getItem("yw_project") || list[0].name; refreshState(); }
}

async function refreshState() {
  if (!state.project) return;
  const s = await api(`/api/projects/${encodeURIComponent(state.project)}/state`);
  const PH = { tr: { new: "yeni", spec: "tanım", plan: "plan", build: "yapılıyor", verify: "doğrulanıyor", done: "bitti" } };
  $("#phase").textContent = (PH[state.lang] && PH[state.lang][s.phase]) || s.phase;
  const nDone = s.tasks.filter((x) => x.status === "done").length;
  $("#summary").textContent = state.lang === "tr" ? `${nDone}/${s.tasks.length} görev tamam` : `${nDone}/${s.tasks.length} tasks done`;
  const models = Object.keys(s.cost_by_model || {}).join(", ");
  $("#cost").textContent = `${(s.tokens_in + s.tokens_out).toLocaleString()} token · $${s.cost_usd.toFixed(3)}` +
    (s.saved_usd > 0 ? ` · ${state.lang === "tr" ? "tasarruf" : "saved"} $${s.saved_usd.toFixed(2)}` : "");
  $("#cost").title = models;
  const done = s.tasks.filter((x) => x.status === "done").length;
  $("#barFill").style.width = s.tasks.length ? `${(100 * done) / s.tasks.length}%` : "0";
  const ul = $("#tasks"); ul.innerHTML = "";
  if (!s.tasks.length) { const li = document.createElement("li"); li.textContent = t("no_tasks"); ul.appendChild(li); }
  for (const task of s.tasks) { const li = document.createElement("li"); li.className = task.status; li.textContent = `${task.id} ${task.title}`; li.title = (task.acceptance || []).join("\n"); ul.appendChild(li); }
  const jl = $("#journeys"); jl.innerHTML = "";
  for (const j of s.journeys) { const li = document.createElement("li"); li.className = j.passed ? "done" : "blocked"; li.textContent = `${j.name} (${j.persona})`; li.title = j.notes; jl.appendChild(li); }
  $("#specView").textContent = s.spec || "—"; $("#logView").textContent = s.progress || "—";
  if (s.goal && !$("#goal").value) $("#goal").value = s.goal;
}

async function loadFile() {
  if (!state.project) return;
  try { const r = await api(`/api/projects/${encodeURIComponent(state.project)}/files?path=${encodeURIComponent($("#filePath").value)}`);
    $("#fileView").textContent = r.listing || r.content; } catch (e) { $("#fileView").textContent = e.message; }
}

async function loadDiff() {
  if (!state.project) return;
  const r = await api(`/api/projects/${encodeURIComponent(state.project)}/history`);
  $("#diffView").textContent = r.history + "\n\n" + (r.diff || "");
}

async function loadStatus() {
  const s = await api("/api/status");
  state.busy = s.busy; syncBusy();
  $("#autonomy").value = s.config.autonomy; $("#quality").value = s.config.quality;
  const h = $("#health"); h.innerHTML = "";
  for (const item of s.health) { const d = document.createElement("div"); d.className = item.ok ? "ok" : "bad"; d.textContent = item.name + (item.detail && !item.ok ? ` — ${item.detail}` : ""); h.appendChild(d); }
  state.config = s.config;
}

async function openSettings() {
  state.models = await api("/api/models");
  const sel = $("#setModel"); sel.innerHTML = "";
  for (const m of state.models) { const o = document.createElement("option"); o.value = m.id; o.textContent = `${m.id} ${m.has_key ? "✓" : ""}`; sel.appendChild(o); }
  sel.value = state.config.model; $("#setBudget").value = state.config.budget_usd;
  $("#setSandbox").value = state.config.sandbox; $("#setDir").value = state.config.projects_dir;
  $("#settings").showModal();
  loadSetup();
}

async function loadSetup() {
  const s = await api("/api/setup");
  $("#sysInfo").textContent = s.system;
  const ul = $("#setupSteps"); ul.innerHTML = "";
  for (const st of s.steps) {
    const li = document.createElement("li");
    li.className = st.ok ? "done" : (st.skipped ? "todo" : "blocked");
    li.textContent = `${state.lang === "tr" ? st.title_tr : st.title_en} ${st.detail ? "— " + st.detail : ""} `;
    if (!st.ok) {
      const b = document.createElement("button"); b.type = "button"; b.className = "small"; b.textContent = t("apply");
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

function wire() {
  $("#viewSimple").onclick = () => { document.body.classList.remove("detailed"); $("#viewSimple").classList.add("on"); $("#viewDetailed").classList.remove("on"); localStorage.setItem("yw_view", "simple"); };
  $("#viewDetailed").onclick = () => { document.body.classList.add("detailed"); $("#viewDetailed").classList.add("on"); $("#viewSimple").classList.remove("on"); localStorage.setItem("yw_view", "detailed"); loadFile(); };
  if (localStorage.getItem("yw_view") === "detailed") $("#viewDetailed").onclick();
  $("#langBtn").onclick = () => { state.lang = state.lang === "tr" ? "en" : "tr"; localStorage.setItem("yw_lang", state.lang); applyI18n(); };
  $("#themeBtn").onclick = () => { const cur = document.documentElement.dataset.theme; const next = cur === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next; localStorage.setItem("yw_theme", next); };
  const savedTheme = localStorage.getItem("yw_theme"); if (savedTheme) document.documentElement.dataset.theme = savedTheme;
  $("#newProject").onclick = async () => { const name = prompt(t("project_name")); if (!name) return; const r = await api("/api/projects", { method: "POST", body: JSON.stringify({ name }) }); state.project = r.name; await loadProjects(); refreshState(); };
  $("#runBtn").onclick = async () => {
    if (!state.project) { alert(t("pick_project")); return; }
    const goal = $("#goal").value.trim(); if (!goal) return;
    try { await api("/api/run", { method: "POST", body: JSON.stringify({ project: state.project, goal, autonomy: $("#autonomy").value, quality: $("#quality").value }) }); state.busy = true; syncBusy(); }
    catch (e) { addFeed("error", e.message); }
  };
  $("#stopBtn").onclick = () => api("/api/stop", { method: "POST" });
  $("#settingsBtn").onclick = () => { openSettings(); loadDevices(); };
  $("#pairBtn").onclick = startPairing;
  $("#saveSettings").onclick = async () => { await api("/api/config", { method: "PUT", body: JSON.stringify({ model: $("#setModel").value, budget_usd: parseFloat($("#setBudget").value), sandbox: $("#setSandbox").value, projects_dir: $("#setDir").value }) }); loadStatus(); loadProjects(); };
  $("#saveKey").onclick = async () => { try { await api("/api/keys", { method: "POST", body: JSON.stringify({ name: $("#keyName").value.trim(), value: $("#keyValue").value.trim() }) }); $("#keyValue").value = ""; alert(t("key_saved")); loadStatus(); } catch (e) { alert(e.message); } };
  document.querySelectorAll(".tab").forEach((b) => b.onclick = () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x === b));
    document.querySelectorAll(".tabbody").forEach((x) => x.hidden = x.id !== "tab-" + b.dataset.tab);
    if (b.dataset.tab === "files") loadFile(); if (b.dataset.tab === "diff") loadDiff(); if (b.dataset.tab === "spec" || b.dataset.tab === "log") refreshState();
  });
  $("#filePath").onchange = loadFile;
  $("#previewUrl").onchange = () => { $("#previewFrame").src = $("#previewUrl").value; };
}

async function startPairing() {
  try {
    const p = await api("/api/pair/start", { method: "POST" });
    $("#pairBox").hidden = false;
    $("#pairQr").innerHTML = p.svg;  // generated by the server's own QR encoder
    const info = $("#pairInfo");
    info.textContent = `${t("pair_help")} ${p.code} — ${p.link}` + (p.lan ? "" : "\n" + t("pair_lan"));
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
      const li = document.createElement("li");
      li.textContent = `📱 ${d.name} — ${t("last_seen")} ${new Date(d.last_seen * 1000).toLocaleString(state.lang)}`;
      const b = document.createElement("button");
      b.type = "button"; b.className = "small ghost"; b.textContent = t("revoke");
      b.onclick = async () => { await api("/api/devices/" + d.id, { method: "DELETE" }); loadDevices(); };
      li.appendChild(b); ul.appendChild(li);
    }
  } catch (e) { ul.innerHTML = ""; }
}

function connect() {
  const es = new EventSource("/api/events");
  es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch (e) { console.error(e); } };
  es.onerror = () => { es.close(); setTimeout(connect, 3000); };
}

wire(); applyI18n();
loadStatus().then(loadProjects).then(connect).catch((e) => addFeed("error", e.message));
