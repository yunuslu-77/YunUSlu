from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.launch import market, pages


def session(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    return build_session(tmp_path / "urun", Config(sandbox="local"), with_engine=False)


PRODUCT = {"name": "Randevum", "tagline": "Kuaförler için randevu sistemi",
           "description": "Müşterileriniz 7/24 randevu alsın, siz işinize odaklanın. Hatırlatma SMS'leri dahil.",
           "features": [{"title": "Online randevu", "text": "Tek bağlantı"}, {"title": "Hatırlatma", "text": "SMS"}],
           "plans": [{"name": "Ücretsiz", "price": 0, "features": ["1 çalışan"]},
                     {"name": "Pro", "price": 199, "best": True, "features": ["10 çalışan"]}],
           "faq": [{"q": "Kart gerekir mi?", "a": "Hayır."}], "url": "https://randevum.example", "lang": "tr"}


def test_markdown_is_safe():
    out = pages.md("# Başlık\n\nMerhaba **dünya** <script>x</script>\n\n- bir\n- iki\n\n1. a\n2. b\n"
                   "[link](https://x.y) [kötü](javascript:alert(1))")
    assert "<h1>Başlık</h1>" in out and "<strong>dünya</strong>" in out and "&lt;script&gt;" in out
    assert "<ul><li>bir</li><li>iki</li></ul>" in out and "<ol><li>a</li><li>b</li></ol>" in out
    assert 'href="https://x.y"' in out and 'href="javascript' not in out


def test_landing_and_seo(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch)
    call = sess.registry.call
    r = call("launch_landing", {"product": PRODUCT})
    assert not r.is_error and "SEO score 100/100" in r.text, r.text
    root = sess.workspace.root
    page = (root / "landing/index.html").read_text()
    assert "FAQPage" in page and '"lowPrice": 0' in page and "₺199" in page and 'lang="tr"' in page
    assert "https://randevum.example/privacy.html" in (root / "landing/sitemap.xml").read_text()
    bad = "<html><head><title>x</title></head><body><h1>a</h1><h1>b</h1><img src=a.png></body></html>"
    score, problems, _ = pages.seo_audit(bad)
    assert score < 30 and any("2 h1" in p for p in problems) and any("alt" in p for p in problems)


def test_store_listing_limits(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch)
    call = sess.registry.call
    ok = call("launch_store_listing", {"platform": "play", "lang": "tr", "fields": {
        "title": "Randevum", "short_description": "Kuaförler için kolay randevu",
        "full_description": "Uzun açıklama"}}).text
    assert "All limits respected" in ok
    assert (sess.workspace.root / "fastlane/metadata/android/tr-TR/title.txt").read_text() == "Randevum\n"
    bad = call("launch_store_listing", {"platform": "appstore", "fields": {
        "name": "Randevum: en iyi kuaför uygulaması burada", "keywords": "randevum, kuaför", "description": "x"}}).text
    assert "FIX BEFORE SUBMITTING" in bad and "limit is 30" in bad and "en iyi" in bad and "no spaces" in bad


def test_social_email_pricing_legal_checklist(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch)
    call = sess.registry.call
    root = sess.workspace.root
    s = call("launch_social", {"start": "2026-11-02", "posts": [
        {"platform": "x", "text": "Randevum yayında! #kuaför"}, {"platform": "x", "text": "a" * 300},
        {"platform": "linkedin", "text": "Uzun duyuru"}]}).text
    assert "300 characters, limit 280" in s
    csv_text = (root / "launch/social-calendar.csv").read_text()
    assert "2026-11-03" in csv_text and "DTSTART:20261102T100000" in (root / "launch/social-calendar.ics").read_text()
    e = call("launch_email", {"name": "welcome", "subject": "Hoş geldin!", "preheader": "İlk adımlar",
                              "body": "Merhaba **Ayşe**,\n\nHesabın hazır.", "cta_text": "Başla",
                              "cta_url": "https://randevum.example/app"}).text
    assert "Fix" not in e
    html = (root / "launch/emails/welcome.html").read_text()
    assert "{{unsubscribe_url}}" in html and "<strong>Ayşe</strong>" in html and "Abonelikten çık" in html
    text = market.pricing([{"name": "A", "plans": [{"name": "Basic", "price": 149}, {"name": "Pro", "price": 299}]},
                           {"name": "B", "plans": [{"name": "Tek", "price": 249}, {"name": "Ekip", "price": 599}]}],
                          monthly_cost_per_user=20)
    assert "median ₺274" in text and "Starter: ₺149" in text and "Pro: ₺299" in text and "gross margin" in text
    leg = call("launch_legal", {"kinds": ["kvkk", "privacy", "terms"], "info": {
        "company": "Uslu Yazılım", "product": "Randevum", "email": "kvkk@randevum.example"}}).text
    assert "DRAFTS" in leg and "Fill in: address, collected data" in leg
    kvkk = (root / "legal/kvkk.md").read_text()
    assert "6698" in kvkk and "hukuki tavsiye değildir" in kvkk and "Uslu Yazılım" in kvkk
    call("launch_landing", {"product": PRODUCT})
    c = call("launch_checklist", {}).text
    assert "[x] Landing page" in c and "[x] KVKK" in c and "[ ] Store listings" in c
    assert (root / "LAUNCH.md").exists()
