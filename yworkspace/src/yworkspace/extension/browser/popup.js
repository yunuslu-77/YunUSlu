const $ = (id) => document.getElementById(id);
chrome.storage.local.get(["token", "port"], (v) => { if (v.token) $("token").value = v.token; if (v.port) $("port").value = v.port; });

async function send(msg) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  try { return await chrome.tabs.sendMessage(tab.id, msg); }
  catch (e) { return { ok: false, error: "Bu sekme desteklenen bir sohbet sitesi değil / unsupported tab" }; }
}

$("start").onclick = async () => {
  const token = $("token").value.trim(), port = $("port").value.trim() || "8766", goal = $("goal").value.trim();
  if (!token || !goal) { $("status").textContent = "Kod ve görev gerekli / token and task required"; return; }
  chrome.storage.local.set({ token, port });
  const r = await send({ type: "yw-start", token, port, goal });
  $("status").textContent = r && r.ok ? "Çalışıyor… / running…" : (r && r.error) || "hata / error";
};
$("stop").onclick = async () => { await send({ type: "yw-stop" }); $("status").textContent = "Durduruldu / stopped"; };
