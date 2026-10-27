"""Launch kit: store listings (fastlane layout), social posts and calendar, pricing analysis, legal drafts,
and the launch checklist. Limits are checked in code so the AI cannot "forget" them."""

from __future__ import annotations

import csv
import io
import re
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PLAY_LIMITS = {"title": 30, "short_description": 80, "full_description": 4000}
APPSTORE_LIMITS = {"name": 30, "subtitle": 30, "keywords": 100, "description": 4000, "promotional_text": 170,
                   "release_notes": 4000}
SOCIAL_LIMITS = {"x": 280, "twitter": 280, "threads": 500, "mastodon": 500, "bluesky": 300, "linkedin": 3000,
                 "instagram": 2200, "facebook": 63206, "tiktok": 2200, "youtube": 5000}
PLAY_LOCALES = {"tr": "tr-TR", "en": "en-US", "de": "de-DE", "fr": "fr-FR", "es": "es-ES", "ar": "ar"}
APPSTORE_LOCALES = {"tr": "tr", "en": "en-US", "de": "de-DE", "fr": "fr-FR", "es": "es-ES", "ar": "ar-SA"}


def store_listing(platform: str, lang: str, fields: dict) -> tuple[dict[str, str], list[str]]:
    """Returns (files, problems). Files follow the fastlane `supply` / `deliver` metadata layout."""
    problems = []
    if platform == "play":
        limits = PLAY_LIMITS
        base = f"fastlane/metadata/android/{PLAY_LOCALES.get(lang, lang)}"
        names = {"title": "title.txt", "short_description": "short_description.txt",
                 "full_description": "full_description.txt"}
    elif platform == "appstore":
        limits = APPSTORE_LIMITS
        base = f"fastlane/metadata/{APPSTORE_LOCALES.get(lang, lang)}"
        names = {k: f"{k}.txt" for k in limits}
    else:
        raise ValueError("platform must be play or appstore")
    files = {}
    for key, value in fields.items():
        if key not in limits:
            problems.append(f"{key}: not a {platform} field (use {', '.join(limits)})")
            continue
        value = str(value).strip()
        if len(value) > limits[key]:
            problems.append(f"{key}: {len(value)} characters, the limit is {limits[key]}")
        files[f"{base}/{names[key]}"] = value + "\n"
    for req in (("title", "short_description", "full_description") if platform == "play" else ("name", "description")):
        if req not in fields:
            problems.append(f"{req} is required")
    if platform == "appstore" and "keywords" in fields:
        kw = str(fields["keywords"])
        if ", " in kw:
            problems.append("keywords: separate with commas and no spaces to save characters")
        name_words = set(re.findall(r"\w+", str(fields.get("name", "")).lower()))
        dup = [k for k in kw.lower().split(",") if k.strip() in name_words]
        if dup:
            problems.append(f"keywords repeat words already in the name: {', '.join(dup)} (wasted characters)")
    text = " ".join(str(v) for v in fields.values()).lower()
    for word in ("best", "#1", "number one", "en iyi", "1 numara", "free forever"):
        if word in text:
            problems.append(f"'{word}': stores often reject unprovable superlatives")
    return files, problems


def social_posts(posts: list[dict], start: str | None = None) -> tuple[str, str, list[str]]:
    """posts: [{platform, text, date?, time?, media?}]. Returns (csv, ics, problems)."""
    problems = []
    day = date.fromisoformat(start) if start else date.today() + timedelta(days=1)
    rows = []
    for i, p in enumerate(posts):
        plat = p.get("platform", "").lower()
        text = p.get("text", "")
        limit = SOCIAL_LIMITS.get(plat)
        if limit is None:
            problems.append(f"post {i + 1}: unknown platform {plat!r}")
        elif len(text) > limit:
            problems.append(f"post {i + 1} ({plat}): {len(text)} characters, limit {limit}")
        tags = re.findall(r"#\w+", text)
        if plat in ("x", "twitter", "linkedin", "threads") and len(tags) > 3:
            problems.append(f"post {i + 1} ({plat}): {len(tags)} hashtags; 1-3 work better")
        when = p.get("date") or (day + timedelta(days=i)).isoformat()
        rows.append({"date": when, "time": p.get("time", "10:00"), "platform": plat, "text": text,
                     "media": p.get("media", "")})
    buf = io.StringIO()
    w = csv.DictWriter(buf, ["date", "time", "platform", "text", "media"])
    w.writeheader()
    w.writerows(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//YunUSlu//yWorkspace Launch Kit//TR"]
    for i, r in enumerate(rows):
        dt = r["date"].replace("-", "") + "T" + r["time"].replace(":", "") + "00"
        summary = f"{r['platform']}: {r['text'][:60]}".replace("\n", " ").replace(",", "\\,").replace(";", "\\;")
        ics += ["BEGIN:VEVENT", f"UID:yw-post-{i}-{dt}@yworkspace", f"DTSTAMP:{stamp}", f"DTSTART:{dt}",
                f"SUMMARY:{summary}", "END:VEVENT"]
    ics.append("END:VCALENDAR")
    return buf.getvalue(), "\r\n".join(ics) + "\r\n", problems


def pricing(competitors: list[dict], monthly_cost_per_user: float = 0.0, currency: str = "₺") -> str:
    """competitors: [{name, plans: [{name, price}]}]. Every number below is computed, not guessed."""
    prices = sorted(float(pl["price"]) for c in competitors for pl in c.get("plans", []) if float(pl["price"]) > 0)
    if not prices:
        return "No paid competitor plans given: research competitors' prices first."
    lo, med, hi = prices[0], statistics.median(prices), prices[-1]
    entries = [min(float(pl["price"]) for pl in c["plans"] if float(pl["price"]) > 0) for c in competitors
               if any(float(pl["price"]) > 0 for pl in c.get("plans", []))]
    rows = ["| Competitor | Plan | Price |", "|---|---|---|"]
    for c in competitors:
        for pl in c.get("plans", []):
            rows.append(f"| {c['name']} | {pl['name']} | {currency}{float(pl['price']):g} |")

    steps = [9, 19, 29, 39, 49, 59, 79, 99, 149, 199, 249, 299, 399, 499, 749, 999]

    def nice(x):
        return next((s for s in steps if s >= x), round(x, -2) - 1)

    def nice_down(x):
        return next((s for s in reversed(steps) if s <= x), steps[0])
    starter = max(nice_down(statistics.median(entries) * 0.95), nice(monthly_cost_per_user * 3))
    pro = nice(max(med, starter * 2))
    business = nice(max(hi * 0.9, pro * 2.2))
    out = ["Market: " + f"{len(prices)} paid plans, lowest {currency}{lo:g}, median {currency}{med:g}, "
           f"highest {currency}{hi:g}.", "", *rows, "",
           "Suggested tiers (rounded to price points people are used to):",
           "- Free: enough to see the value, with a clear limit",
           f"- Starter: {currency}{starter}/mo (under the typical competitor's entry plan)",
           f"- Pro: {currency}{pro}/mo (around the market median; the plan most people should pick)",
           f"- Business: {currency}{business}/mo (team features, priority support)",
           "- Yearly billing: 2 months free"]
    if monthly_cost_per_user:
        margin = (starter - monthly_cost_per_user) / starter * 100
        out.append(f"Starter gross margin at {currency}{monthly_cost_per_user:g}/user cost: {margin:.0f}%"
                   + (" - too low, raise the price or cut costs" if margin < 60 else ""))
    return "\n".join(out)


DISCLAIMER = {
    "tr": "> ⚠️ Bu metin yWorkspace tarafından hazırlanmış bir TASLAKTIR ve hukuki tavsiye değildir. Yayınlamadan önce "
          "bir hukuk uzmanına kontrol ettirin.",
    "en": "> ⚠️ This is a DRAFT generated by yWorkspace and is not legal advice. Have a lawyer review it before "
          "publishing.",
}


def legal(kind: str, info: dict, lang: str = "tr") -> str:
    """kind: privacy, kvkk, cookies, terms. info: company, product, email, address, country, data[], processors[],
    purposes[], retention, cookies[{name, purpose, duration}]."""
    c = {k: info.get(k) or f"[{k}]" for k in ("company", "product", "email", "address", "country", "retention")}
    data = info.get("data") or ["[collected data]"]
    purposes = info.get("purposes") or ["[purposes]"]
    procs = info.get("processors") or []
    today = date.today().isoformat()
    tr = lang == "tr"
    lines = [DISCLAIMER["tr" if tr else "en"], ""]
    li = lambda xs: [f"- {x}" for x in xs]  # noqa: E731
    if kind == "kvkk":
        lines += [f"# {c['product']} — KVKK Aydınlatma Metni", f"Son güncelleme: {today}", "",
                  "## 1. Veri sorumlusu",
                  f"6698 sayılı Kişisel Verilerin Korunması Kanunu (\"KVKK\") uyarınca veri sorumlusu {c['company']} "
                  f"({c['address']}) olup bu metin, kişisel verilerinizin nasıl işlendiği hakkında sizi bilgilendirmek "
                  "amacıyla hazırlanmıştır.", "", "## 2. İşlenen kişisel veriler", *li(data), "",
                  "## 3. İşleme amaçları", *li(purposes), "",
                  "## 4. Hukuki sebepler",
                  "Kişisel verileriniz KVKK m.5/2 kapsamında sözleşmenin kurulması ve ifası, hukuki yükümlülüklerin "
                  "yerine getirilmesi ve meşru menfaat sebeplerine; bu sebeplerin bulunmadığı hâllerde açık rızanıza "
                  "dayanılarak işlenir.", "",
                  "## 5. Aktarım",
                  *(li(procs) if procs else ["Kişisel verileriniz yalnızca hizmetin sunulması için gerekli olan "
                                             "tedarikçilere aktarılır."]),
                  "Yurt dışına aktarım yapılması hâlinde KVKK m.9 hükümlerine uyulur.", "",
                  "## 6. Saklama süresi", f"{c['retention']}", "",
                  "## 7. Haklarınız (KVKK m.11)",
                  *li(["Kişisel verilerinizin işlenip işlenmediğini öğrenme", "İşlenmişse bilgi talep etme",
                       "İşlenme amacını ve amaca uygun kullanılıp kullanılmadığını öğrenme",
                       "Aktarıldığı üçüncü kişileri bilme", "Eksik veya yanlış işlenmişse düzeltilmesini isteme",
                       "Silinmesini veya yok edilmesini isteme",
                       "Otomatik sistemlerle analiz sonucu aleyhinize bir sonuca itiraz etme",
                       "Kanuna aykırı işleme nedeniyle zararın giderilmesini talep etme"]), "",
                  f"Başvurularınızı {c['email']} adresine iletebilirsiniz. Başvurular en geç 30 gün içinde "
                  "sonuçlandırılır."]
    elif kind == "privacy":
        if tr:
            lines += [f"# {c['product']} — Gizlilik Politikası", f"Son güncelleme: {today}", "",
                      f"{c['company']} olarak gizliliğinize önem veriyoruz.", "", "## Topladığımız veriler", *li(data),
                      "", "## Neden topluyoruz", *li(purposes), "", "## Kimlerle paylaşıyoruz",
                      *(li(procs) or ["Verilerinizi satmıyoruz."]), "", "## Ne kadar saklıyoruz", c["retention"], "",
                      "## Güvenlik", "Veriler aktarımda şifrelenir; erişim yetkili kişilerle sınırlıdır.", "",
                      "## Haklarınız", "Verilerinize erişme, düzeltme, silme ve itiraz haklarınız vardır. "
                      "Türkiye'deki kullanıcılar için KVKK Aydınlatma Metni'ne bakın.", "",
                      "## İletişim", c["email"]]
        else:
            lines += [f"# {c['product']} — Privacy Policy", f"Last updated: {today}", "",
                      f"{c['company']} ({c['address']}) operates {c['product']}.", "", "## Data we collect", *li(data),
                      "", "## Why we collect it", *li(purposes), "", "## Who we share it with",
                      *(li(procs) or ["We do not sell your data."]), "", "## Retention", c["retention"], "",
                      "## Your rights", "You can access, correct, export or delete your data and object to "
                      "processing. EU/UK users have rights under the GDPR; California users under the CCPA.", "",
                      "## Contact", c["email"]]
    elif kind == "cookies":
        cookies = info.get("cookies") or []
        head = ("| Çerez | Amaç | Süre |" if tr else "| Cookie | Purpose | Duration |")
        lines += [f"# {c['product']} — " + ("Çerez Politikası" if tr else "Cookie Policy"),
                  ("Son güncelleme: " if tr else "Last updated: ") + today, "",
                  ("Zorunlu çerezler dışındaki çerezler yalnızca onayınızla kullanılır. Tercihinizi istediğiniz zaman "
                   "değiştirebilirsiniz." if tr else
                   "Cookies other than strictly necessary ones are only set with your consent, which you can change "
                   "at any time."), "", head, "|---|---|---|",
                  *[f"| {k.get('name')} | {k.get('purpose')} | {k.get('duration')} |" for k in cookies]]
    elif kind == "terms":
        if tr:
            lines += [f"# {c['product']} — Kullanım Koşulları", f"Son güncelleme: {today}", "",
                      "## 1. Taraflar", f"Bu koşullar {c['company']} ile hizmeti kullanan kişi arasındadır.", "",
                      "## 2. Hesap", "Hesap bilgilerinizin güvenliğinden siz sorumlusunuz.", "",
                      "## 3. Kabul edilebilir kullanım", "Hizmet yasa dışı amaçlarla, başkalarının haklarını ihlal "
                      "edecek şekilde veya sistemin güvenliğini tehlikeye atacak biçimde kullanılamaz.", "",
                      "## 4. Ücretler ve iptal", "Ücretli planlar dönem başında tahsil edilir; aboneliği istediğiniz "
                      "zaman iptal edebilirsiniz. 6502 sayılı Kanun kapsamındaki cayma hakkınız saklıdır.", "",
                      "## 5. Sorumluluğun sınırlandırılması", "Hizmet \"olduğu gibi\" sunulur; mevzuatın izin verdiği "
                      "ölçüde dolaylı zararlardan sorumluluk kabul edilmez.", "",
                      "## 6. Değişiklikler", "Önemli değişiklikler yürürlükten önce bildirilir.", "",
                      "## 7. Uygulanacak hukuk", f"{c['country']} hukuku uygulanır.", "", "## İletişim", c["email"]]
        else:
            lines += [f"# {c['product']} — Terms of Service", f"Last updated: {today}", "",
                      "## 1. Agreement", f"These terms are between you and {c['company']}.", "",
                      "## 2. Accounts", "You are responsible for keeping your account secure.", "",
                      "## 3. Acceptable use", "Do not use the service unlawfully, to infringe others' rights or to "
                      "compromise its security.", "", "## 4. Fees and cancellation", "Paid plans are billed in "
                      "advance; you can cancel at any time.", "", "## 5. Limitation of liability",
                      "The service is provided \"as is\" to the extent permitted by law.", "", "## 6. Changes",
                      "We will notify you of material changes before they take effect.", "", "## 7. Governing law",
                      f"The laws of {c['country']} apply.", "", "## Contact", c["email"]]
    else:
        raise ValueError("kind must be privacy, kvkk, cookies or terms")
    return "\n".join(lines) + "\n"


CHECKLIST = [
    ("landing", "Landing page", lambda r: (r / "landing/index.html").exists() or (r / "index.html").exists()),
    ("seo", "robots.txt and sitemap.xml", lambda r: any((r / d / "sitemap.xml").exists() for d in ("landing", "public", "."))),
    ("og", "Share image (og.png, 1200x630)", lambda r: any(r.glob("**/og.png"))),
    ("privacy", "Privacy policy", lambda r: any(r.glob("legal/privacy*")) or any(r.glob("**/privacy.html"))),
    ("terms", "Terms of service", lambda r: any(r.glob("legal/terms*"))),
    ("kvkk", "KVKK notice (users in Türkiye)", lambda r: any(r.glob("legal/kvkk*"))),
    ("icons", "App icons / favicon", lambda r: any(r.glob("**/favicon.ico"))),
    ("store", "Store listings", lambda r: (r / "fastlane/metadata").exists()),
    ("social", "Social media calendar", lambda r: (r / "launch/social-calendar.csv").exists()),
    ("emails", "Welcome and launch e-mails", lambda r: any(r.glob("launch/emails/*.html"))),
    ("security", "Security scan without critical/high findings", lambda r: _security_ok(r)),
    ("monitor", "Uptime monitoring and alerts", lambda r: (r / ".yw/monitor.json").exists()),
    ("tests", "Tests exist", lambda r: any(r.glob("tests/**/*")) or any(r.glob("**/*.test.*"))),
    ("readme", "README / help page", lambda r: (r / "README.md").exists()),
]
MANUAL = ["Backups are automatic and a restore was tested", "Analytics that respect privacy (e.g. Plausible, Umami)",
          "Error tracking (e.g. self-hosted GlitchTip / Sentry)", "Payment flow tested end to end in test mode",
          "Support channel (e-mail, form) answered", "Product Hunt page: tagline, gallery, first comment, hunter",
          "Press release / announcement post", "Launch day plan: hour by hour, who answers comments",
          "Post-launch: collect feedback, fix top 3 complaints within a week"]


def _security_ok(root: Path) -> bool:
    import json
    p = root / ".yw" / "security.json"
    if not p.exists():
        return False
    counts = json.loads(p.read_text("utf-8")).get("counts", {})
    return not counts.get("critical") and not counts.get("high")


def checklist(root: Path) -> tuple[str, int, int]:
    root = Path(root)
    lines = ["# Launch checklist", "", "## Checked automatically"]
    done = 0
    for _key, label, test in CHECKLIST:
        try:
            ok = bool(test(root))
        except OSError:
            ok = False
        done += ok
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    lines += ["", "## Check by hand", *(f"- [ ] {m}" for m in MANUAL)]
    return "\n".join(lines) + "\n", done, len(CHECKLIST)
