"""Launch Kit tools: everything needed to introduce a finished product to the world."""

from __future__ import annotations

import re

from ..core.errors import ToolError
from ..extensions import register
from ..tools.registry import SAFE, WRITE, Tool, obj
from . import market, pages

S = {"type": "string"}
ARR = {"type": "array", "items": {"type": "object"}}


@register
def install(session) -> None:
    reg, ws = session.registry, session.workspace

    def write(path: str, content: str) -> None:
        full = ws.root / path
        if full.exists():
            if full.read_text("utf-8", "replace") == content:
                return
            ws.read(path)
        ws.create(path, content, overwrite=full.exists())

    def launch_landing(product: dict) -> str:
        if not product.get("name"):
            raise ToolError("no_name", "product.name is required.")
        files = pages.landing(product)
        for path, content in files.items():
            write(path, content)
        score, bad, _good = pages.seo_audit(files["landing/index.html"])
        notes = [] if product.get("url") else ["Set product.url to get canonical links and sitemap.xml."]
        if not (ws.root / "landing/og.png").exists():
            notes.append("Make landing/og.png (1200x630) with render_html - it is the image shown when the link is "
                         "shared.")
        return (f"Wrote {', '.join(files)}. SEO score {score}/100." + ("\nSEO problems:\n- " + "\n- ".join(bad)
                                                                         if bad else "")
                + ("\n" + "\n".join(notes) if notes else "") + "\nCheck how it looks: screen_open the file, mobile "
                "and desktop, light and dark.")

    def launch_seo_audit(path: str) -> str:
        score, bad, good = pages.seo_audit(ws.root.joinpath(ws.rel(ws.resolve(path))).read_text("utf-8", "replace"))
        return f"SEO score {score}/100\nGood: {', '.join(good)}" + ("\nFix:\n- " + "\n- ".join(bad) if bad else "")

    def launch_store_listing(platform: str, fields: dict, lang: str = "tr") -> str:
        try:
            files, problems = market.store_listing(platform, lang, fields)
        except ValueError as e:
            raise ToolError("bad_platform", str(e)) from e
        for path, content in files.items():
            write(path, content)
        head = f"Wrote {len(files)} {platform} listing files ({lang}) in the fastlane layout"
        tail = " (upload with `fastlane supply` / `fastlane deliver`)."
        if problems:
            return head + tail + "\nFIX BEFORE SUBMITTING:\n- " + "\n- ".join(problems)
        return head + tail + " All limits respected. Add screenshots (screen_shot on real screens) and a preview " \
            "video (video_compose, format 9:16)."

    def launch_social(posts: list[dict], start: str = "") -> str:
        try:
            table, ics, problems = market.social_posts(posts, start or None)
        except ValueError as e:
            raise ToolError("bad_date", str(e), "Use YYYY-MM-DD.") from e
        write("launch/social-calendar.csv", table)
        write("launch/social-calendar.ics", ics)
        return (f"Wrote launch/social-calendar.csv and .ics ({len(posts)} posts; import the .ics into any calendar)."
                + ("\nFix:\n- " + "\n- ".join(problems) if problems else " All posts are within platform limits."))

    def launch_email(name: str, subject: str, body: str, preheader: str = "", cta_text: str = "", cta_url: str = "",
                     footer: str = "", lang: str = "tr") -> str:
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise ToolError("bad_name", "name: lowercase letters, digits and - only (e.g. welcome, launch).")
        problems = []
        if len(subject) > 60:
            problems.append(f"subject is {len(subject)} characters; keep it under 60 (it is cut on phones)")
        if not preheader:
            problems.append("no preheader: the inbox preview will show random text")
        if re.search(r"(?i)\b(free!!!|act now|%100 garanti|bedava!!!)", subject + body):
            problems.append("spam-trigger phrases")
        page, plain = pages.email(subject, preheader, body, cta_text, cta_url, footer=footer, lang=lang)
        write(f"launch/emails/{name}.html", page)
        write(f"launch/emails/{name}.txt", f"Subject: {subject}\n\n{plain}")
        return (f"Wrote launch/emails/{name}.html and .txt ({{{{unsubscribe_url}}}} is filled in by your mail service)."
                + ("\nFix:\n- " + "\n- ".join(problems) if problems else ""))

    def launch_pricing(competitors: list[dict], monthly_cost_per_user: float = 0.0, currency: str = "₺") -> str:
        text = market.pricing(competitors, monthly_cost_per_user, currency)
        write("launch/pricing.md", "# Pricing analysis\n\n" + text + "\n")
        return text

    def launch_legal(kinds: list[str], info: dict, lang: str = "tr") -> str:
        written = []
        for kind in kinds:
            try:
                text = market.legal(kind, info, lang)
            except ValueError as e:
                raise ToolError("bad_kind", str(e)) from e
            path = f"legal/{kind}{'' if kind == 'kvkk' else '-' + lang}.md"
            write(path, text)
            written.append(path)
        missing = sorted(set(re.findall(r"\[(company|product|email|address|country|retention|collected data|"
                                        r"purposes)\]", "".join((ws.root / p).read_text("utf-8") for p in written))))
        return (f"Wrote {', '.join(written)}. These are DRAFTS, not legal advice: a lawyer should review them before "
                "publishing." + (f"\nFill in: {', '.join(missing)}" if missing else ""))

    def launch_checklist() -> str:
        text, done, total = market.checklist(ws.root)
        write("LAUNCH.md", text)
        return f"{done}/{total} automatic checks pass. Wrote LAUNCH.md.\n\n{text}"

    tools = [
        Tool("launch_landing", "Landing page with SEO built in (meta, Open Graph, JSON-LD, sitemap, robots), features, "
             "pricing, FAQ, waitlist; responsive and dark-mode aware. product: name, tagline, description, "
             "features[{title,text}], plans[{name,price,currency,features[],best}], faq[{q,a}], lang, color, url, "
             "company, waitlist_url, cta_url.", obj({"product": {"type": "object"}}, ["product"]), launch_landing,
             WRITE, "launch"),
        Tool("launch_seo_audit", "SEO check of an HTML page: title, description, h1, lang, viewport, canonical, Open "
             "Graph, structured data, image alt texts.", obj({"path": S}, ["path"]), launch_seo_audit, SAFE, "launch"),
        Tool("launch_store_listing", "Google Play (title, short_description, full_description) or App Store (name, "
             "subtitle, keywords, description, promotional_text, release_notes) listing with limit checks, written "
             "in the fastlane layout.", obj({"platform": {"type": "string", "enum": ["play", "appstore"]},
                                             "fields": {"type": "object"}, "lang": S}, ["platform", "fields"]),
             launch_store_listing, WRITE, "launch"),
        Tool("launch_social", "Launch posts with per-platform limit checks and a posting calendar (CSV + .ics). "
             "posts: [{platform, text, date?, time?, media?}].", obj({"posts": ARR, "start": S}, ["posts"]),
             launch_social, WRITE, "launch"),
        Tool("launch_email", "E-mail (welcome, launch, newsletter) as mail-client-safe HTML plus plain text, from "
             "Markdown.", obj({"name": S, "subject": S, "body": S, "preheader": S, "cta_text": S, "cta_url": S,
                               "footer": S, "lang": S}, ["name", "subject", "body"]), launch_email, WRITE, "launch"),
        Tool("launch_pricing", "Pricing analysis from competitors' real prices: market range, median and suggested "
             "tiers, computed in code. competitors: [{name, plans:[{name, price}]}].",
             obj({"competitors": ARR, "monthly_cost_per_user": {"type": "number"}, "currency": S}, ["competitors"]),
             launch_pricing, WRITE, "launch"),
        Tool("launch_legal", "DRAFT legal texts: privacy, kvkk (Türkiye), cookies, terms. Not legal advice. info: "
             "company, product, email, address, country, data[], purposes[], processors[], retention, cookies[].",
             obj({"kinds": {"type": "array", "items": S}, "info": {"type": "object"}, "lang": S}, ["kinds", "info"]),
             launch_legal, WRITE, "launch"),
        Tool("launch_checklist", "Launch readiness: checks what exists (landing, SEO, legal, icons, store listings, "
             "social, e-mails, security, monitoring, tests) and writes LAUNCH.md.", obj({}), launch_checklist, SAFE,
             "launch"),
    ]
    for t in tools:
        reg.register(t)
