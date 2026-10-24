// yWorkspace browser bridge: drives the chat page, relays replies to the local yWorkspace relay server.
(() => {
  if (window.__ywBridge) return;
  window.__ywBridge = true;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let running = false;
  let profile = null;
  let panel = null;

  async function loadProfile() {
    const res = await fetch(chrome.runtime.getURL("sites.json"));
    const all = await res.json();
    return all[location.hostname] || all["_default"];
  }

  function first(selectors) {
    for (const s of selectors || []) {
      try { const el = document.querySelector(s); if (el) return el; } catch (e) { /* bad selector */ }
    }
    return null;
  }

  function all(selectors) {
    for (const s of selectors || []) {
      try { const els = document.querySelectorAll(s); if (els.length) return Array.from(els); } catch (e) { }
    }
    return [];
  }

  function status(text) {
    if (!panel) {
      panel = document.createElement("div");
      panel.style.cssText = "position:fixed;bottom:16px;right:16px;z-index:2147483647;background:#1b2a3a;color:#fff;" +
        "font:13px system-ui;padding:10px 12px;border-radius:10px;box-shadow:0 4px 16px #0004;max-width:320px";
      const stop = document.createElement("button");
      stop.textContent = "■ Durdur / Stop";
      stop.style.cssText = "margin-left:8px;background:#c0392b;color:#fff;border:0;border-radius:6px;padding:3px 8px;cursor:pointer";
      stop.onclick = () => { running = false; status("Durduruldu / stopped"); };
      const span = document.createElement("span");
      panel.append("yWorkspace: ", span, stop);
      document.body.appendChild(panel);
    }
    panel.querySelector("span").textContent = text;
  }

  function setInput(el, text) {
    el.focus();
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value").set;
      setter.call(el, text);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    // contenteditable editors (ProseMirror, Quill ...): select all, then insert as a paste.
    document.getSelection().selectAllChildren(el);
    const dt = new DataTransfer();
    dt.setData("text/plain", text);
    const pasted = el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
    if (pasted && !el.innerText.includes(text.slice(0, 40))) {
      document.execCommand("insertText", false, text);
    }
  }

  async function sendMessage(text) {
    const input = first(profile.input);
    if (!input) throw new Error("Mesaj kutusu bulunamadı / chat input not found");
    setInput(input, text);
    await sleep(400);
    const btn = first(profile.send);
    if (btn && !btn.disabled) btn.click();
    else input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, bubbles: true }));
  }

  function replyText(el) {
    const blocks = Array.from(el.querySelectorAll("pre, code")).map((c) => c.innerText).filter((t) => t.includes("<<<yw:"));
    if (blocks.length) {
      const outside = el.innerText;
      return outside.includes("<<<yw:") && blocks.join("\n").length < outside.length * 0.3 ? outside : blocks.join("\n");
    }
    return el.innerText;
  }

  async function waitForReply(previousCount, timeoutMs = 15 * 60 * 1000) {
    const start = Date.now();
    let last = "", stableSince = Date.now();
    while (running && Date.now() - start < timeoutMs) {
      await sleep(1000);
      const replies = all(profile.reply);
      if (replies.length <= previousCount) continue;
      const busy = !!first(profile.busy);
      const text = replyText(replies[replies.length - 1]);
      if (text !== last) { last = text; stableSince = Date.now(); continue; }
      if (!busy && text.trim() && Date.now() - stableSince > 2500) return text;
    }
    if (!running) throw new Error("stopped");
    throw new Error("Cevap zaman aşımına uğradı / reply timed out");
  }

  async function relay(port, token, path, body) {
    const r = await chrome.runtime.sendMessage({ type: "yw-relay", port, token, path, body });
    if (!r || !r.ok) throw new Error(`yWorkspace: ${(r && r.error) || "no response"}`);
    return r.data;
  }

  async function deliver(parts) {
    let reply = "";
    for (const part of parts) {
      const before = all(profile.reply).length;
      await sendMessage(part);
      reply = await waitForReply(before);
    }
    return reply;
  }

  async function run({ token, port, goal }) {
    profile = await loadProfile();
    running = true;
    status("Başlıyor / starting");
    try {
      let { messages } = await relay(port, token, "/start", { goal });
      let turn = 0;
      while (running) {
        turn += 1;
        status(`Tur ${turn}: yapay zekâ çalışıyor / AI working`);
        const reply = await deliver(messages);
        status(`Tur ${turn}: araçlar çalışıyor / running tools`);
        const r = await relay(port, token, "/reply", { text: reply });
        if (r.done) { status("Bitti ✓ / done"); break; }
        messages = r.messages;
      }
    } catch (e) {
      status("Hata / error: " + e.message);
    } finally {
      running = false;
    }
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "yw-start") {
      if (running) { sendResponse({ ok: false, error: "zaten çalışıyor / already running" }); return; }
      run(msg);
      sendResponse({ ok: true });
    } else if (msg.type === "yw-stop") {
      running = false;
      sendResponse({ ok: true });
    }
  });
})();
