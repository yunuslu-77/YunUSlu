"""Launch kit pages: landing page with SEO built in, SEO audit, e-mails, a tiny Markdown renderer."""

from __future__ import annotations

import html
import json
import re
from datetime import date
from html.parser import HTMLParser

E = html.escape


def md(text: str) -> str:
    """Small, safe Markdown → HTML (headings, paragraphs, lists, bold, italic, code, links)."""
    def inline(s: str) -> str:
        s = E(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|mailto:[^)\s]+|/[^)\s]*)\)", r'<a href="\2">\1</a>', s)
    out, para, lst = [], [], None

    def flush():
        nonlocal para, lst
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para = []
        if lst:
            tag, items = lst
            out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>")
            lst = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if not s:
            flush()
        elif m:
            flush()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif re.match(r"[-*]\s+", s) or re.match(r"\d+[.)]\s+", s):
            tag = "ul" if re.match(r"[-*]\s+", s) else "ol"
            if para:
                out.append(f"<p>{inline(' '.join(para))}</p>")
                para = []
            if lst and lst[0] != tag:
                flush()
            lst = lst or (tag, [])
            lst[1].append(re.sub(r"^([-*]|\d+[.)])\s+", "", s))
        else:
            if lst:
                flush()
            para.append(s)
    flush()
    return "\n".join(out)


TEXT = {
    "tr": {"features": "Özellikler", "pricing": "Fiyatlar", "faq": "Sıkça sorulan sorular", "join": "Bekleme listesine katıl",
           "email": "E-posta adresin", "privacy": "Gizlilik", "terms": "Kullanım koşulları", "month": "/ay",
           "thanks": "Teşekkürler! Haber vereceğiz.", "start": "Hemen başla"},
    "en": {"features": "Features", "pricing": "Pricing", "faq": "Frequently asked questions", "join": "Join the waitlist",
           "email": "Your email", "privacy": "Privacy", "terms": "Terms", "month": "/mo",
           "thanks": "Thanks! We'll let you know.", "start": "Get started"},
}

LANDING_CSS = """*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
color:#14202e;background:#fff;line-height:1.6}a{color:var(--c)}.wrap{max-width:1080px;margin:auto;padding:0 20px}
header{padding:18px 0}header .wrap{display:flex;justify-content:space-between;align-items:center}.logo{font-weight:800;
font-size:20px}.hero{padding:72px 0 56px;text-align:center}.hero h1{font-size:clamp(32px,5vw,56px);line-height:1.1;
margin:0 0 16px}.hero p{font-size:20px;color:#4a5a6e;max-width:680px;margin:0 auto 28px}.btn{display:inline-block;
background:var(--c);color:#fff;padding:14px 26px;border-radius:10px;text-decoration:none;font-weight:700;border:0;
font-size:16px;cursor:pointer}section{padding:56px 0}h2{font-size:32px;text-align:center;margin:0 0 32px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}.card{border:1px solid #e3e9f2;
border-radius:14px;padding:22px}.card h3{margin:0 0 8px}.price{font-size:36px;font-weight:800}.plan.best{border:2px solid
var(--c)}details{border-bottom:1px solid #e3e9f2;padding:14px 0}summary{font-weight:700;cursor:pointer}
form.wait{display:flex;gap:8px;justify-content:center;flex-wrap:wrap}form.wait input{padding:14px;border:1px solid
#c9d3e0;border-radius:10px;min-width:260px;font-size:16px}footer{padding:32px 0;color:#6a7a8e;font-size:14px;
border-top:1px solid #e3e9f2}footer .wrap{display:flex;gap:18px;flex-wrap:wrap}
@media (prefers-color-scheme:dark){body{background:#0f1720;color:#e6edf5}.hero p{color:#a9b7c8}.card,details,footer{
border-color:#26323f}form.wait input{background:#16212c;color:#e6edf5;border-color:#33414f}}"""


def landing(p: dict) -> dict[str, str]:
    """p: name, tagline, description, features[{title,text}], plans[{name,price,currency,features[],best}],
    faq[{q,a}], lang, color, url, waitlist_url, cta_url, image. Returns files to write."""
    lang = p.get("lang", "tr")
    t = TEXT.get(lang, TEXT["en"])
    name, tagline = p["name"], p.get("tagline", "")
    desc = p.get("description") or tagline
    url = p.get("url", "").rstrip("/")
    color = p.get("color", "#2f6fe4")
    feats = "".join(f'<div class="card"><h3>{E(f["title"])}</h3><p>{E(f.get("text", ""))}</p></div>'
                    for f in p.get("features", []))
    plans = ""
    for pl in p.get("plans", []):
        items = "".join(f"<li>{E(x)}</li>" for x in pl.get("features", []))
        price = pl.get("price", 0)
        shown = ("0" if price == 0 else f"{price:g}") if isinstance(price, (int, float)) else E(str(price))
        plans += (f'<div class="card plan{" best" if pl.get("best") else ""}"><h3>{E(pl["name"])}</h3>'
                  f'<div class="price">{E(pl.get("currency", "₺"))}{shown}<small>{t["month"]}</small></div>'
                  f"<ul>{items}</ul></div>")
    faq = "".join(f"<details><summary>{E(f['q'])}</summary><p>{E(f['a'])}</p></details>" for f in p.get("faq", []))
    cta = p.get("cta_url") or "#waitlist"
    wait = ""
    if p.get("waitlist_url", "") != "none":
        action = E(p.get("waitlist_url") or "/api/waitlist")
        wait = (f'<section id="waitlist"><div class="wrap"><h2>{t["join"]}</h2><form class="wait" method="post" '
                f'action="{action}"><input type="email" name="email" required placeholder="{t["email"]}" '
                f'aria-label="{t["email"]}"><button class="btn" type="submit">{t["join"]}</button></form>'
                "</div></section>")
    ld = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": name, "description": desc,
          "applicationCategory": p.get("category", "BusinessApplication"), "operatingSystem": p.get("os", "Web")}
    if p.get("plans"):
        prices = [pl.get("price") for pl in p["plans"] if isinstance(pl.get("price"), (int, float))]
        if prices:
            ld["offers"] = {"@type": "AggregateOffer", "lowPrice": min(prices), "highPrice": max(prices),
                            "priceCurrency": p.get("currency_code", "TRY")}
    faq_ld = ({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
        for f in p["faq"]]} if p.get("faq") else None)
    image = p.get("image", "og.png")
    head = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{E(name)} — {E(tagline)}</title><meta name=\"description\" content=\"{E(desc[:160])}\">"
            + (f'<link rel="canonical" href="{E(url)}/">' if url else "")
            + f'<meta property="og:title" content="{E(name)}"><meta property="og:description" content="{E(desc[:200])}">'
            f'<meta property="og:type" content="website"><meta property="og:image" content="{E((url + "/" if url else "") + image)}">'
            + (f'<meta property="og:url" content="{E(url)}/">' if url else "")
            + '<meta name="twitter:card" content="summary_large_image"><link rel="icon" href="favicon.ico">'
            f"<style>:root{{--c:{E(color)}}}{LANDING_CSS}</style>"
            f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
            + (f'<script type="application/ld+json">{json.dumps(faq_ld, ensure_ascii=False)}</script>' if faq_ld else "")
            + "</head>")
    body = (f'<body><header><div class="wrap"><div class="logo">{E(name)}</div><a class="btn" href="{E(cta)}">'
            f'{t["start"]}</a></div></header><main><section class="hero"><div class="wrap"><h1>{E(tagline or name)}</h1>'
            f'<p>{E(desc)}</p><a class="btn" href="{E(cta)}">{t["start"]}</a></div></section>'
            + (f'<section id="features"><div class="wrap"><h2>{t["features"]}</h2><div class="grid">{feats}</div></div></section>'
               if feats else "")
            + (f'<section id="pricing"><div class="wrap"><h2>{t["pricing"]}</h2><div class="grid">{plans}</div></div></section>'
               if plans else "")
            + (f'<section id="faq"><div class="wrap"><h2>{t["faq"]}</h2>{faq}</div></section>' if faq else "")
            + wait + f'</main><footer><div class="wrap"><span>© {date.today().year} {E(p.get("company", name))}</span>'
            f'<a href="privacy.html">{t["privacy"]}</a><a href="terms.html">{t["terms"]}</a></div></footer></body></html>')
    files = {"landing/index.html": head + body,
             "landing/robots.txt": "User-agent: *\nAllow: /\n" + (f"Sitemap: {url}/sitemap.xml\n" if url else "")}
    if url:
        pages = ["", "privacy.html", "terms.html"]
        files["landing/sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/'
                                        'schemas/sitemap/0.9">\n' + "".join(
                                            f"  <url><loc>{E(url)}/{pg}</loc><lastmod>{date.today()}</lastmod></url>\n"
                                            for pg in pages) + "</urlset>\n")
    return files


class _Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.meta: dict[str, str] = {}
        self.h1 = 0
        self.imgs_no_alt = 0
        self.imgs = 0
        self.lang = ""
        self.canonical = False
        self.jsonld = 0
        self.viewport = False
        self._in_ld = False
        self.ld_errors = 0
        self._ld = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            key = a.get("name") or a.get("property") or ""
            if key:
                self.meta[key.lower()] = a.get("content", "")
            if key == "viewport":
                self.viewport = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "img":
            self.imgs += 1
            if not (a.get("alt") or "").strip() and a.get("role") != "presentation":
                self.imgs_no_alt += 1
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = True
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld, self._ld = True, ""

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self._in_ld:
            self._in_ld = False
            try:
                json.loads(self._ld)
                self.jsonld += 1
            except json.JSONDecodeError:
                self.ld_errors += 1

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self._in_ld:
            self._ld += data


def seo_audit(page: str) -> tuple[int, list[str], list[str]]:
    """Returns (score, problems, good)."""
    a = _Audit()
    a.feed(page)
    bad, good = [], []

    def check(cond, ok_text, bad_text):
        (good if cond else bad).append(ok_text if cond else bad_text)
    tl = len(a.title.strip())
    check(10 <= tl <= 60, f"title length {tl}", f"title is {tl} characters (aim for 10-60)")
    d = a.meta.get("description", "")
    check(50 <= len(d) <= 160, f"meta description {len(d)} chars", f"meta description is {len(d)} characters (50-160)")
    check(a.h1 == 1, "exactly one h1", f"{a.h1} h1 headings (use exactly one)")
    check(bool(a.lang), f"lang={a.lang}", "the html tag has no lang attribute")
    check(a.viewport, "mobile viewport", "no viewport meta tag (bad on phones)")
    check(a.canonical, "canonical link", "no canonical link")
    check(all(a.meta.get(k) for k in ("og:title", "og:description", "og:image")), "Open Graph tags",
          "missing Open Graph tags (og:title, og:description, og:image) - links look bare when shared")
    check(a.jsonld > 0 and not a.ld_errors, f"{a.jsonld} JSON-LD blocks",
          "no valid JSON-LD structured data" if not a.ld_errors else f"{a.ld_errors} invalid JSON-LD blocks")
    check(a.imgs_no_alt == 0, f"all {a.imgs} images have alt text", f"{a.imgs_no_alt} images without alt text")
    score = round(100 * len(good) / (len(good) + len(bad)))
    return score, bad, good


def email(subject: str, preheader: str, body_md: str, cta_text: str = "", cta_url: str = "", color: str = "#2f6fe4",
          footer: str = "", lang: str = "tr") -> tuple[str, str]:
    """Inline-styled e-mail that renders in common mail clients, plus its plain-text version."""
    unsub = {"tr": "Abonelikten çık", "en": "Unsubscribe"}.get(lang, "Unsubscribe")
    button = (f'<p style="text-align:center;margin:28px 0"><a href="{E(cta_url)}" style="background:{E(color)};'
              f'color:#ffffff;padding:14px 26px;border-radius:8px;text-decoration:none;font-weight:bold;'
              f'display:inline-block">{E(cta_text)}</a></p>' if cta_text and cta_url else "")
    body_html = md(body_md).replace("<p>", '<p style="margin:0 0 14px">')
    page = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width"><title>{E(subject)}</title></head>'
            f'<body style="margin:0;background:#f3f5f9;font-family:Arial,Helvetica,sans-serif;color:#14202e">'
            f'<span style="display:none;max-height:0;overflow:hidden">{E(preheader)}</span>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" '
            f'style="padding:24px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" '
            f'style="max-width:600px;width:100%;background:#ffffff;border-radius:12px"><tr><td style="padding:32px;'
            f'font-size:16px;line-height:1.6">{body_html}{button}</td></tr></table>'
            f'<p style="font-size:12px;color:#6a7a8e">{E(footer)} · <a href="{{{{unsubscribe_url}}}}" '
            f'style="color:#6a7a8e">{unsub}</a></p></td></tr></table></body></html>')
    plain = re.sub(r"[*`#]", "", body_md).strip() + (f"\n\n{cta_text}: {cta_url}" if cta_text else "") + \
        f"\n\n--\n{footer}\n{unsub}: {{{{unsubscribe_url}}}}\n"
    return page, plain
