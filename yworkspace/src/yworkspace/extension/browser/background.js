// Talks to the local yWorkspace relay. Runs in the extension context, so page CORS and
// Private Network Access rules of the chat site do not apply.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "yw-relay") return false;
  fetch(`http://127.0.0.1:${msg.port}${msg.path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-YW-Token": msg.token },
    body: JSON.stringify(msg.body),
  })
    .then(async (r) => sendResponse(r.ok ? { ok: true, data: await r.json() } : { ok: false, error: `HTTP ${r.status}` }))
    .catch((e) => sendResponse({ ok: false, error: String(e) }));
  return true; // async response
});
