// yWorkspace phone remote: talks to the user's own computer, never to a cloud.
const $ = (s) => document.querySelector(s);
const S = { lang: localStorage.getItem("yw_lang") || ((navigator.language || "tr").slice(0, 2) === "tr" ? "tr" : "en"), project: localStorage.getItem("yw_project") || "" };
const T = {
  tr: { welcome: "Telefonunu bağla", howto: "Bilgisayarında yWorkspace'i aç → Ayarlar → Telefon eşleştir. Çıkan QR kodu telefonunun kamerasıyla okut ya da kodu buraya yaz.",
    connect: "Bağlan", project: "Proje", goal_ph: "Ne yapalım? Örn: Giriş sayfasına şifremi unuttum ekle", start: "Başlat", stop: "Durdur",
    q_economy: "Ekonomik", q_balanced: "Dengeli", q_max: "Maksimum kalite", activity: "Neler oluyor", open: "Aç",
    approve: "Onayla", reject: "Reddet", feedback: "Ne değişsin? (isteğe bağlı)", started: "Başladı", finished: "Bitti ✓",
    not_finished: "Bitmedi", paired: "Bağlandı", bad_code: "Kod yanlış ya da süresi dolmuş. Bilgisayarda yeni kod göster.",
    no_project: "Önce bilgisayarda bir proje oluştur.", offline: "Bilgisayara ulaşılamıyor. Aynı Wi-Fi'da mısın, yWorkspace açık mı?",
    a_spec: "Proje tanımını onaylıyor musun?", a_plan: "Planı onaylıyor musun?", a_tool: "Bu işleme izin var mı?", a_question: "Yapay zekâ bir şey soruyor" },
  en: { welcome: "Connect your phone", howto: "On your computer open yWorkspace → Settings → Pair a phone, then scan the QR code with the phone camera or type the code here.",
    connect: "Connect", project: "Project", goal_ph: "What shall we do? e.g. Add 'forgot password' to the login page", start: "Start", stop: "Stop",
    q_economy: "Economy", q_balanced: "Balanced", q_max: "Maximum quality", activity: "What's happening", open: "Open",
    approve: "Approve", reject: "Reject", feedback: "What should change? (optional)", started: "Started", finished: "Done ✓",
    not_finished: "Not finished", paired: "Connected", bad_code: "Wrong or expired code. Show a new code on the computer.",
    no_project: "Create a project on the computer first.", offline: "Cannot reach the computer. Same Wi-Fi? Is yWorkspace running?",
    a_spec: "Approve the specification?", a_plan: "Approve the plan?", a_tool: "Allow this action?", a_question: "The AI has a question" },
};
const t = (k) => T[S.lang][k] || k;
const PHASE = { tr: { new: "yeni", spec: "tanım", plan: "plan", build: "yapılıyor", verify: "doğrulanıyor", done: "bitti" },
  en: { new: "new", spec: "spec", plan: "plan", build: "building", verify: "verifying", done: "done" } };
const TOOL = { tr: { read: "Dosya okunuyor", create: "Dosya oluşturuldu", edit: "Dosya düzenlendi", multi_edit: "Dosya düzenlendi",
    run: "Komut çalıştırılıyor", search: "Kodda arama", list: "Dosyalara bakılıyor", plan_update: "Görev güncellendi",
    plan_add_tasks: "Plan yapıldı", plan_set_spec: "Proje tanımı yazıldı", check: "Kontroller çalışıyor", review_verdict: "İnceleme sonucu" },
  en: { read: "Reading a file", create: "Created a file", edit: "Edited a file", multi_edit: "Edited a file", run: "Running a command",
    search: "Searching the code", list: "Looking at files", plan_update: "Task updated", plan_add_tasks: "Planned",
    plan_set_spec: "Wrote the specification", check: "Running checks", review_verdict: "Review result" } };

async function api(path, opts = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
  if (!res.ok) { const e = new Error((await res.json().catch(() => ({}))).detail || res.statusText); e.status = res.status; throw e; }
  return res.json();
}

function i18n() {
  document.documentElement.lang = S.lang;
  $("#lang").textContent = S.lang === "tr" ? "EN" : "TR";
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  document.querySelectorAll("[data-tph]").forEach((el) => { el.placeholder = t(el.dataset.tph); });
}

function feed(kind, text) {
  const li = document.createElement("li");
  li.className = kind; li.textContent = text;
  $("#feed").prepend(li);
  while ($("#feed").children.length > 120) $("#feed").lastChild.remove();
}

async function claim(code) {
  try {
    const name = /Android/i.test(navigator.userAgent) ? "Android" : /iPhone|iPad/i.test(navigator.userAgent) ? "iPhone" : "Telefon";
    await api("/api/pair/claim", { method: "POST", body: JSON.stringify({ code, name }) });
    history.replaceState(null, "", "/m/");
    return true;
  } catch (e) { $("#pairErr").textContent = t("bad_code"); $("#pairErr").hidden = false; return false; }
}

async function boot() {
  i18n();
  const m = location.hash.match(/pair=([A-Z0-9-]+)/i);
  if (m) await claim(m[1]);
  try {
    const me = await api("/api/me");
    $("#who").textContent = me.owner ? "🖥" : "📱 " + me.device.name;
    $("#app").hidden = false; $("#unpaired").hidden = true;
    await loadProjects(); connect(); refresh();
  } catch (e) {
    $("#unpaired").hidden = false; $("#app").hidden = true;
    if (e.status !== 401) { $("#pairErr").textContent = t("offline"); $("#pairErr").hidden = false; }
  }
}

async function loadProjects() {
  const list = await api("/api/projects");
  const sel = $("#project"); sel.innerHTML = "";
  for (const p of list) { const o = document.createElement("option"); o.value = o.textContent = p.name || p; sel.appendChild(o); }
  if (!list.length) feed("error", t("no_project"));
  if (S.project && [...sel.options].some((o) => o.value === S.project)) sel.value = S.project;
  S.project = sel.value;
}

async function refresh() {
  if (!S.project) return;
  try {
    const st = await api(`/api/projects/${encodeURIComponent(S.project)}/state`);
    $("#phase").textContent = PHASE[S.lang][st.phase] || st.phase || "—";
    const tasks = st.tasks || [];
    const done = tasks.filter((x) => x.status === "done").length;
    $("#summary").textContent = tasks.length ? `${done}/${tasks.length}` : "";
    $("#fill").style.width = tasks.length ? `${(done / tasks.length) * 100}%` : "0";
  } catch (e) { /* project without state yet */ }
}

function busy(on) { $("#stop").hidden = !on; $("#start").hidden = on; }

function approval(e) {
  if (document.getElementById("ap-" + e.id)) return;
  const box = document.createElement("div");
  box.className = "approval"; box.id = "ap-" + e.id;
  const h = document.createElement("b"); h.textContent = t("a_" + e.type) || e.type;
  const pre = document.createElement("pre"); pre.textContent = e.text;
  const fb = document.createElement("input"); fb.placeholder = t("feedback");
  const row = document.createElement("div"); row.className = "row";
  const send = async (ok) => { await api("/api/approve", { method: "POST", body: JSON.stringify({ id: e.id, ok, feedback: fb.value }) }); box.remove(); };
  const yes = document.createElement("button"); yes.className = "primary"; yes.textContent = t("approve"); yes.onclick = () => send(true);
  const no = document.createElement("button"); no.className = "danger"; no.textContent = t("reject"); no.onclick = () => send(false);
  row.append(no, yes); box.append(h, pre, fb, row);
  $("#approvals").prepend(box);
  if (navigator.vibrate) navigator.vibrate([120, 60, 120]);
}

function onEvent(e) {
  if (e.project && S.project && e.project !== S.project && e.kind !== "approval") return;
  switch (e.kind) {
    case "approval": approval(e); break;
    case "approval_done": document.getElementById("ap-" + e.id)?.remove(); break;
    case "run_started": busy(true); feed("info", t("started") + ": " + e.text); break;
    case "run_finished": busy(false); feed("done", e.data && e.data.finished ? t("finished") : t("not_finished")); refresh(); break;
    case "error": feed("error", e.text.slice(0, 300)); break;
    case "info": if (e.text.startsWith("role:")) feed("info", "▶ " + e.text.slice(5)); refresh(); break;
    case "tool_call": feed("info", TOOL[S.lang][e.text] || e.text); break;
    case "assistant": feed("info", e.text.slice(0, 200)); break;
  }
}

function connect() {
  const es = new EventSource("/api/events");
  es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch (err) { console.error(err); } };
  es.onerror = () => { es.close(); setTimeout(connect, 4000); };
}

$("#lang").onclick = () => { S.lang = S.lang === "tr" ? "en" : "tr"; localStorage.setItem("yw_lang", S.lang); i18n(); };
$("#codeForm").onsubmit = async (ev) => { ev.preventDefault(); if (await claim($("#code").value)) boot(); };
$("#project").onchange = () => { S.project = $("#project").value; localStorage.setItem("yw_project", S.project); refresh(); };
$("#start").onclick = async () => {
  const goal = $("#goal").value.trim();
  if (!goal || !S.project) return;
  try { await api("/api/run", { method: "POST", body: JSON.stringify({ project: S.project, goal, quality: $("#quality").value }) }); busy(true); $("#goal").value = ""; }
  catch (e) { feed("error", e.message); }
};
$("#stop").onclick = () => api("/api/stop", { method: "POST" });
$("#openPreview").onclick = () => { const u = $("#preview").value.trim(); if (/^https?:\/\//.test(u)) window.open(u, "_blank", "noopener"); };
window.addEventListener("hashchange", () => { if (/pair=/.test(location.hash)) boot(); });
if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("/m/sw.js", { scope: "/m/" }).catch(() => {});
boot();
