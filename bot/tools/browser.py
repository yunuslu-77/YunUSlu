"""Botun kendi tarayıcısı (Playwright, görünmez Chromium)."""
from __future__ import annotations

import asyncio

from .registry import P, ToolContext, tool
from .web import html_to_text


class BrowserManager:
    def __init__(self, executable: str = ""):
        self.executable = executable
        self._pw = None
        self._browser = None
        self.page = None
        self._lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        """Playwright kurulu mu? (Telefonda/Termux'ta kurulu değildir; o zaman tarayıcı araçları gizlenir.)"""
        import importlib.util
        return importlib.util.find_spec("playwright") is not None

    async def get_page(self):
        async with self._lock:
            if self.page and not self.page.is_closed():
                return self.page
            from playwright.async_api import async_playwright
            if not self._pw:
                self._pw = await async_playwright().start()
            if not self._browser:
                kw = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
                if self.executable:
                    kw["executable_path"] = self.executable
                self._browser = await self._pw.chromium.launch(**kw)
            ctx = await self._browser.new_context(locale="tr-TR", viewport={"width": 1280, "height": 900})
            self.page = await ctx.new_page()
            return self.page

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._pw = self._browser = self.page = None


async def _state(page, limit: int = 6000) -> dict:
    html = await page.content()
    info = html_to_text(html, limit)
    links = await page.eval_on_selector_all(
        "a,button,input,textarea,select",
        "els => els.slice(0,60).map(e => ({tag:e.tagName.toLowerCase(), text:(e.innerText||e.value||e.placeholder||e.name||'').trim().slice(0,60), "
        "name:e.name||'', id:e.id||''})).filter(x => x.text || x.name || x.id)")
    return {"url": page.url, **info, "elements": links}


@tool("browser_open", "Botun tarayıcısında bir adres açar ve sayfa metnini + tıklanabilir öğeleri döner.", "browser",
      {"url": P(str, "Adres")})
async def browser_open(ctx: ToolContext, url: str):
    page = await ctx.app.browser.get_page()
    if not url.startswith("http"):
        url = "https://" + url
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(800)
    return await _state(page)


@tool("browser_read", "Tarayıcıdaki mevcut sayfanın metnini okur.", "browser")
async def browser_read(ctx: ToolContext):
    page = await ctx.app.browser.get_page()
    return await _state(page, 12000)


@tool("browser_click", "Tarayıcıda görünen metne veya CSS seçiciye tıklar.", "browser",
      {"target": P(str, "Tıklanacak öğenin görünen metni veya CSS seçici (#id, .sınıf)")})
async def browser_click(ctx: ToolContext, target: str):
    page = await ctx.app.browser.get_page()
    loc = page.locator(target) if target[:1] in "#.[" else page.get_by_text(target, exact=False)
    await loc.first.click(timeout=10000)
    await page.wait_for_timeout(1200)
    return await _state(page)


@tool("browser_type", "Tarayıcıda bir alana yazı yazar. submit=True ise Enter'a basar (form gönderir).", "browser",
      {"target": P(str, "Alan: CSS seçici, name veya placeholder metni"), "text": P(str, "Yazılacak metin"),
       "submit": P(bool, "Enter'a basılsın mı", required=False)},
      approval=lambda a: bool(a.get("submit")) and not _is_search(a),
      summary=lambda a: f"🌐 Tarayıcıda formu gönder\nAlan: {a['target']}\nMetin: {a['text']}")
async def browser_type(ctx: ToolContext, target: str, text: str, submit: bool = False):
    page = await ctx.app.browser.get_page()
    if target[:1] in "#.[":
        loc = page.locator(target)
    else:
        loc = page.locator(f"[name='{target}']")
        if await loc.count() == 0:
            loc = page.get_by_placeholder(target)
    await loc.first.fill(text, timeout=10000)
    if submit:
        await loc.first.press("Enter")
        await page.wait_for_timeout(1500)
    return await _state(page)


def _is_search(a: dict) -> bool:
    """Arama kutusuna Enter basmak onay gerektirmez; diğer formlar gerektirir."""
    t = (a.get("target") or "").lower().strip("#.[]'\" ")
    return t in ("q", "s", "query", "search", "ara", "arama", "ara...", "search...") or t.startswith(("search", "arama"))


@tool("browser_look", "Tarayıcı ekranının görüntüsüne bakıp soruyu cevaplar (görsel düzen, grafik, captcha dışı).",
      "browser", {"question": P(str, "Ekranla ilgili soru")})
async def browser_look(ctx: ToolContext, question: str):
    page = await ctx.app.browser.get_page()
    img = await page.screenshot(type="png")
    return {"answer": await ctx.app.llm.vision(img, question)}


@tool("browser_screenshot", "Tarayıcı ekranının görüntüsünü kullanıcıya gönderir.", "browser")
async def browser_screenshot(ctx: ToolContext):
    page = await ctx.app.browser.get_page()
    img = await page.screenshot(type="png")
    await ctx.app.notifier.send_photo(img, page.url)
    return {"sent": True, "url": page.url}
