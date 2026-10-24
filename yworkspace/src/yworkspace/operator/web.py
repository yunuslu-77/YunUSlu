"""Use a web app like a real person: real browser, numbered elements, human-speed input, personas."""

from __future__ import annotations

import base64
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import ToolError

ELEMENTS_JS = r"""() => {
  const sel = 'a,button,input,select,textarea,[role=button],[role=link],[role=checkbox],[role=tab],[role=menuitem],' +
              '[role=switch],[role=option],[onclick],[contenteditable=true],summary,label[for]';
  document.querySelectorAll('[data-yw-id]').forEach(e => e.removeAttribute('data-yw-id'));
  let n = 0; const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none' || st.opacity === '0') continue;
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    n++; el.setAttribute('data-yw-id', n);
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || (tag === 'input' ? 'input:' + (el.type || 'text') : tag);
    let name = (el.getAttribute('aria-label') || (tag === 'input' || tag === 'textarea' ? '' : el.innerText) ||
                el.title || el.alt || '').trim().replace(/\s+/g, ' ');
    if (!name && el.id) { const l = document.querySelector('label[for="' + el.id + '"]'); if (l) name = l.innerText.trim(); }
    const extra = [];
    if (el.disabled) extra.push('disabled');
    if (el.checked) extra.push('checked');
    if ('value' in el && el.value && tag !== 'button' && el.type !== 'password') extra.push('value="' + String(el.value).slice(0, 40) + '"');
    if (el.placeholder) extra.push('placeholder="' + el.placeholder + '"');
    if (tag === 'a' && el.getAttribute('href')) extra.push('href=' + el.getAttribute('href').slice(0, 60));
    out.push({n, role, name: name.slice(0, 80), extra: extra.join(' '), x: r.left + r.width / 2, y: r.top + r.height / 2,
              l: r.left, t: r.top, w: r.width, h: r.height, placeholder: el.placeholder || '', tag});
  }
  return out;
}"""

LABELS_ON_JS = r"""(els) => {
  const box = document.createElement('div'); box.id = '__yw_labels';
  box.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647';
  for (const e of els) {
    const b = document.createElement('div');
    b.style.cssText = `position:fixed;left:${e.l}px;top:${e.t}px;width:${e.w}px;height:${e.h}px;outline:2px solid #e8420a;`;
    const tag = document.createElement('span'); tag.textContent = e.n;
    tag.style.cssText = 'position:absolute;left:-2px;top:-14px;background:#e8420a;color:#fff;font:bold 11px sans-serif;padding:0 3px;border-radius:3px';
    b.appendChild(tag); box.appendChild(b);
  }
  document.body.appendChild(box);
}"""

A11Y_JS = r"""() => {
  const issues = [];
  document.querySelectorAll('img').forEach(i => { if (!i.hasAttribute('alt')) issues.push('Image without alt text: ' + (i.src || '').slice(-60)); });
  document.querySelectorAll('input,select,textarea').forEach(i => {
    if (i.type === 'hidden') return;
    const labelled = i.getAttribute('aria-label') || i.getAttribute('aria-labelledby') || (i.id && document.querySelector('label[for="' + i.id + '"]')) || i.closest('label');
    if (!labelled) issues.push('Form field without a label: ' + (i.name || i.placeholder || i.type));
  });
  document.querySelectorAll('button,a,[role=button]').forEach(b => {
    const r = b.getBoundingClientRect();
    if (r.width === 0) return;
    if (!(b.innerText || '').trim() && !b.getAttribute('aria-label') && !b.title) issues.push('Button/link without a name: ' + b.outerHTML.slice(0, 80));
    if (innerWidth < 600 && (r.width < 40 || r.height < 40)) issues.push(`Small tap target (${Math.round(r.width)}x${Math.round(r.height)}): ` + (b.innerText || b.getAttribute('aria-label') || '').slice(0, 40));
  });
  const lum = (c) => { const m = c.match(/\d+(\.\d+)?/g); if (!m) return 1; const [r, g, b] = m.slice(0, 3).map(v => { v = v / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const bgOf = (el) => { while (el) { const c = getComputedStyle(el).backgroundColor; if (c && !c.includes('rgba(0, 0, 0, 0)') && c !== 'transparent') return c; el = el.parentElement; } return 'rgb(255,255,255)'; };
  let checked = 0;
  for (const el of document.querySelectorAll('p,span,a,button,label,li,h1,h2,h3,h4,td')) {
    if (checked++ > 400) break;
    if (!(el.innerText || '').trim() || el.children.length > 3) continue;
    const st = getComputedStyle(el); const L1 = lum(st.color), L2 = lum(bgOf(el));
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const big = parseFloat(st.fontSize) >= 24 || (parseFloat(st.fontSize) >= 18.66 && parseInt(st.fontWeight) >= 700);
    if (ratio < (big ? 3 : 4.5)) issues.push(`Low contrast ${ratio.toFixed(1)}:1 — "${el.innerText.trim().slice(0, 40)}"`);
  }
  if (!document.documentElement.lang) issues.push('Page has no lang attribute');
  return [...new Set(issues)].slice(0, 60);
}"""


@dataclass
class Persona:
    key: str
    title_tr: str
    description: str
    typing_delay: tuple[int, int] = (40, 110)  # ms per key
    think_time: tuple[float, float] = (0.3, 1.2)  # seconds between actions
    device: str | None = None  # Playwright device name
    viewport: tuple[int, int] = (1280, 800)
    network: str | None = None  # slow3g | offline
    locale: str = "tr-TR"
    color_scheme: str = "light"
    double_clicks: bool = False
    zoom: float = 1.0
    screen_reader: bool = False


PERSONAS: dict[str, Persona] = {p.key: p for p in [
    Persona("first_time", "İlk kez kullanan", "Knows nothing about the app; reads labels, tries the obvious path."),
    Persona("non_technical", "Teknolojiye uzak", "Reads slowly, struggles with small text and jargon, clicks carefully.",
            typing_delay=(150, 350), think_time=(1.5, 4.0), zoom=1.25),
    Persona("impatient", "Sabırsız", "Double-clicks, does not wait for loading, goes back and refreshes.",
            typing_delay=(20, 50), think_time=(0.05, 0.3), double_clicks=True),
    Persona("screen_reader", "Ekran okuyucu", "Navigates only by keyboard and accessible names.", screen_reader=True),
    Persona("attacker", "Kötü niyetli test", "Enters very long text, special characters and injection attempts "
            "into every field. ONLY for the user's own app."),
    Persona("mobile_slow", "Mobil + yavaş internet", "Small phone screen on a slow network.", device="iPhone 13",
            network="slow3g"),
    Persona("arabic_rtl", "Sağdan sola dil", "Uses Arabic locale; checks right-to-left layout.", locale="ar-SA"),
    Persona("dark_mode", "Karanlık mod", "Uses dark mode.", color_scheme="dark"),
]}


@dataclass
class Action:
    kind: str
    target: dict | None = None
    value: str | None = None
    url: str | None = None


@dataclass
class WebScreen:
    evidence_dir: Path
    persona: Persona = field(default_factory=lambda: PERSONAS["first_time"])
    headless: bool = True
    actions: list[Action] = field(default_factory=list)
    console: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._pw = self._browser = self._ctx = self._page = None
        self._els: list[dict] = []
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- lifecycle
    def open(self, url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ToolError("no_browser", "Playwright is not installed.",
                            "pip install playwright && python -m playwright install chromium") from e
        if self._page is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self.headless)
            p = self.persona
            opts: dict = {"locale": p.locale, "color_scheme": p.color_scheme,
                          "record_video_dir": str(self.evidence_dir / "video")}
            if p.device:
                opts.update(self._pw.devices[p.device])
            else:
                opts["viewport"] = {"width": p.viewport[0], "height": p.viewport[1]}
            self._ctx = self._browser.new_context(**opts)
            self._page = self._ctx.new_page()
            self._page.on("console", lambda m: self.console.append(f"{m.type}: {m.text}") if m.type in
                          ("error", "warning") else None)
            self._page.on("pageerror", lambda e: self.console.append(f"pageerror: {e}"))
            if p.network:
                cdp = self._ctx.new_cdp_session(self._page)
                cdp.send("Network.enable")
                if p.network == "offline":
                    cdp.send("Network.emulateNetworkConditions", {"offline": True, "latency": 0,
                                                                  "downloadThroughput": 0, "uploadThroughput": 0})
                else:
                    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 400,
                                                                  "downloadThroughput": 50_000,
                                                                  "uploadThroughput": 20_000})
        try:
            self._page.goto(url, wait_until="load", timeout=45000)
        except Exception as e:
            raise ToolError("open_failed", f"Could not open {url}: {e}",
                            "Is the app running? Check processes/logs and the port map.") from e
        if self.persona.zoom != 1.0:
            self._page.evaluate(f"document.body.style.zoom = '{self.persona.zoom}'")
        self.actions.append(Action("goto", url=url))
        return self.view()

    def close(self) -> str:
        video = None
        if self._page is not None:
            try:
                video = self._page.video.path() if self._page.video else None
            except Exception:
                video = None
            self._ctx.close()
            self._browser.close()
            self._pw.stop()
            self._page = None
        return f"Browser closed.{' Video: ' + str(video) if video else ''}"

    def _need(self):
        if self._page is None:
            raise ToolError("no_screen", "No screen is open.", "Call screen_open with the app's URL first.")
        return self._page

    def _think(self) -> None:
        lo, hi = self.persona.think_time
        time.sleep(random.uniform(lo, hi) * 0.25)  # scaled: realistic rhythm without wasting minutes

    # ---------------------------------------------------------------- seeing
    def view(self, screenshot: bool = True) -> tuple[str, list[str]] | str:
        page = self._need()
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        self._els = page.evaluate(ELEMENTS_JS)
        lines = [f"URL: {page.url}", f"Title: {page.title()}", f"Persona: {self.persona.title_tr}", "", "Elements:"]
        for e in self._els:
            lines.append(f"[{e['n']}] {e['role']} \"{e['name']}\" {e['extra']}".rstrip())
        if self.persona.screen_reader:
            try:
                lines += ["", "Accessibility tree (what a screen reader hears):", page.locator("body").aria_snapshot()[:6000]]
            except Exception:
                pass
        text = page.evaluate("() => document.body.innerText")[:3000]
        lines += ["", "Visible text:", text]
        if self.console:
            lines += ["", "Console errors/warnings:"] + self.console[-10:]
        images: list[str] = []
        if screenshot:
            page.evaluate(LABELS_ON_JS, self._els)
            png = page.screenshot(type="png")
            page.evaluate("() => document.getElementById('__yw_labels')?.remove()")
            shot = self.evidence_dir / f"step-{len(self.actions):03d}.png"
            shot.write_bytes(png)
            lines.append(f"\nScreenshot saved: {shot.name}")
            images.append(base64.b64encode(png).decode())
        return "\n".join(lines), images

    def _el(self, n: int) -> dict:
        for e in self._els:
            if e["n"] == int(n):
                return e
        raise ToolError("no_element", f"No element [{n}] on the current screen.", "Call screen_view to refresh numbers.")

    @staticmethod
    def _locator_desc(e: dict) -> dict:
        role_map = {"button": "button", "a": "link", "input:checkbox": "checkbox", "select": "combobox",
                    "input:radio": "radio"}
        return {"role": role_map.get(e["role"], e["role"]), "name": e["name"], "placeholder": e.get("placeholder", ""),
                "tag": e.get("tag", "")}

    def _move_to(self, e: dict) -> tuple[float, float]:
        page = self._need()
        x = e["x"] + random.uniform(-e["w"] / 6, e["w"] / 6)
        y = e["y"] + random.uniform(-e["h"] / 6, e["h"] / 6)
        page.mouse.move(x, y, steps=random.randint(8, 20))
        return x, y

    # ---------------------------------------------------------------- acting
    def click(self, n: int, double: bool = False) -> None:
        e = self._el(n)
        self._think()
        x, y = self._move_to(e)
        page = self._need()
        if double or self.persona.double_clicks:
            page.mouse.dblclick(x, y)
        else:
            page.mouse.down()
            time.sleep(random.uniform(0.04, 0.12))
            page.mouse.up()
        self.actions.append(Action("click", self._locator_desc(e)))

    def type(self, n: int, text: str, clear: bool = True, submit: bool = False) -> None:
        e = self._el(n)
        self.click(n)
        page = self._need()
        if clear:
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
        lo, hi = self.persona.typing_delay
        for ch in text:
            page.keyboard.type(ch, delay=0)
            time.sleep(random.uniform(lo, hi) / 1000 * 0.3)
        if submit:
            page.keyboard.press("Enter")
        self.actions.append(Action("fill", self._locator_desc(e), text))

    def key(self, keys: str) -> None:
        self._need().keyboard.press(keys)
        self.actions.append(Action("key", value=keys))

    def scroll(self, direction: str = "down", amount: int = 600) -> None:
        page = self._need()
        dy = amount if direction == "down" else -amount
        for _ in range(4):
            page.mouse.wheel(0, dy / 4)
            time.sleep(0.05)

    def drag(self, n_from: int, n_to: int) -> None:
        a, b = self._el(n_from), self._el(n_to)
        page = self._need()
        page.mouse.move(a["x"], a["y"], steps=10)
        page.mouse.down()
        page.mouse.move(b["x"], b["y"], steps=25)
        page.mouse.up()

    def upload(self, n: int, path: str) -> None:
        self._need().locator(f"[data-yw-id='{int(n)}']").set_input_files(path)

    def select(self, n: int, option: str) -> None:
        e = self._el(n)
        self._need().locator(f"[data-yw-id='{int(n)}']").select_option(label=option)
        self.actions.append(Action("select", self._locator_desc(e), option))

    def wait_for(self, text: str, timeout: int = 15) -> bool:
        try:
            self._need().get_by_text(text).first.wait_for(timeout=timeout * 1000)
            self.actions.append(Action("expect_text", value=text))
            return True
        except Exception:
            return False

    def back(self) -> None:
        self._need().go_back()

    def reload(self) -> None:
        self._need().reload()

    def a11y(self) -> list[str]:
        return self._need().evaluate(A11Y_JS)

    # ---------------------------------------------------------------- export
    def export_test(self, name: str) -> str:
        """Turn the recorded actions into a pytest + Playwright regression test."""
        lines = ["# Generated by yWorkspace from a human-like journey. Run: pytest -q", "import re", "",
                 "from playwright.sync_api import Page, expect", "", "",
                 f"def test_{''.join(c if c.isalnum() else '_' for c in name.lower()).strip('_')}(page: Page):"]

        def loc(t: dict) -> str:
            if t.get("placeholder"):
                return f"page.get_by_placeholder({t['placeholder']!r})"
            if t.get("name") and t.get("role") in ("button", "link", "checkbox", "combobox", "radio"):
                return f"page.get_by_role({t['role']!r}, name={t['name']!r})"
            if t.get("name"):
                return f"page.get_by_text({t['name']!r}).first"
            return "page.locator('body')"

        for a in self.actions:
            if a.kind == "goto":
                lines.append(f"    page.goto({a.url!r})")
            elif a.kind == "click":
                lines.append(f"    {loc(a.target)}.click()")
            elif a.kind == "fill":
                lines.append(f"    {loc(a.target)}.fill({a.value!r})")
            elif a.kind == "select":
                lines.append(f"    {loc(a.target)}.select_option(label={a.value!r})")
            elif a.kind == "key":
                lines.append(f"    page.keyboard.press({a.value!r})")
            elif a.kind == "expect_text":
                lines.append(f"    expect(page.get_by_text({a.value!r}).first).to_be_visible()")
        if len(lines) == 7:
            lines.append("    pass  # no actions were recorded")
        return "\n".join(lines) + "\n"
