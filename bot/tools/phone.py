"""📱 Telefon kontrolü araçları (Android + Termux köprüsü).

Seviye 1-2: 'phone' grubu (SMS, bildirim, konum, kamera, alarm, uygulama açma, Tasker...)
Seviye 3:   'phone_screen' grubu (ADB ile ekranı görme, dokunma, kaydırma, yazma)
"""
from __future__ import annotations

import struct
import time

from ..phone_gateway import PhoneOffline
from .registry import P, ToolContext, tool


async def _phone(ctx: ToolContext, action: str, timeout: float = 40, **args):
    if not ctx.app.db.get("phone_enabled", True):
        return {"error": "Telefon erişimi kapalı (panelden veya /telefon ac ile açılabilir)"}
    try:
        return await ctx.app.phone.call(action, args, timeout=timeout)
    except PhoneOffline as e:
        return {"error": str(e)}


def _data(r: dict):
    return r if "error" in r else r.get("data")


# ---------------- Seviye 1: durum ve bilgi ----------------
@tool("phone_status", "Telefonun pil, şarj ve Wi-Fi durumunu verir; bağlı olup olmadığını gösterir.", "phone")
async def phone_status(ctx: ToolContext):
    if not ctx.app.phone.online:
        return {"online": False, "error": "Telefon bağlı değil"}
    bat = _data(await _phone(ctx, "battery"))
    wifi = _data(await _phone(ctx, "wifi"))
    return {"online": True, "device": ctx.app.phone.device, "battery": bat, "wifi": wifi}


@tool("phone_notifications", "Telefondaki güncel bildirimleri listeler.", "phone",
      {"app_filter": P(str, "Sadece bu uygulamayı içeren paket adları (ör. whatsapp)", required=False)})
async def phone_notifications(ctx: ToolContext, app_filter: str = ""):
    r = await _phone(ctx, "notifications")
    if "error" in r:
        return r
    items = r.get("data") or []
    if app_filter:
        items = [n for n in items if app_filter.lower() in str(n.get("packageName", "")).lower()]
    return [{"app": n.get("packageName"), "title": n.get("title"), "content": n.get("content"), "when": n.get("when")}
            for n in items][:40]


@tool("phone_sms_list", "Telefondaki son SMS'leri okur.", "phone",
      {"limit": P(int, "Kaç mesaj (varsayılan 10)", required=False),
       "number": P(str, "Sadece bu numara/kişiden gelenler", required=False)})
async def phone_sms_list(ctx: ToolContext, limit: int = 10, number: str = ""):
    r = await _phone(ctx, "sms_list", limit=int(limit) * (3 if number else 1))
    if "error" in r:
        return r
    msgs = r.get("data") or []
    if number:
        digits = "".join(c for c in number if c.isdigit())[-10:]
        msgs = [m for m in msgs if digits and digits in "".join(c for c in str(m.get("number", "")) if c.isdigit())
                or number.lower() in str(m.get("sender", "")).lower()]
    return msgs[:int(limit)]


@tool("phone_sms_send", "Telefondan SMS gönderir.", "phone",
      {"number": P(str, "Telefon numarası"), "text": P(str, "Mesaj")}, approval=True,
      summary=lambda a: f"💬 SMS gönder\nKime: {a['number']}\n\n{a['text']}")
async def phone_sms_send(ctx: ToolContext, number: str, text: str):
    return _data(await _phone(ctx, "sms_send", number=number, text=text))


@tool("phone_call", "Telefondan arama başlatır.", "phone", {"number": P(str, "Numara")}, approval=True,
      summary=lambda a: f"📞 Ara: {a['number']}")
async def phone_call(ctx: ToolContext, number: str):
    return _data(await _phone(ctx, "call", number=number))


@tool("phone_call_log", "Son aramaları listeler.", "phone", {"limit": P(int, "Kaç kayıt", required=False)})
async def phone_call_log(ctx: ToolContext, limit: int = 10):
    return _data(await _phone(ctx, "call_log", limit=int(limit)))


@tool("phone_contacts", "Rehberde kişi arar.", "phone", {"query": P(str, "İsim veya numara parçası")})
async def phone_contacts(ctx: ToolContext, query: str):
    r = await _phone(ctx, "contacts")
    if "error" in r:
        return r
    q = query.lower()
    return [c for c in (r.get("data") or []) if q in str(c.get("name", "")).lower() or q in str(c.get("number", ""))][:20]


@tool("phone_location", "Telefonun konumunu (enlem/boylam) verir.", "phone")
async def phone_location(ctx: ToolContext):
    r = _data(await _phone(ctx, "location", timeout=60))
    if isinstance(r, dict) and "latitude" in r:
        r["maps_link"] = f"https://maps.google.com/?q={r['latitude']},{r['longitude']}"
    return r


@tool("phone_photo", "Telefonun kamerasıyla fotoğraf çeker ve kullanıcıya yollar. İstenirse fotoğrafı yorumlar.", "phone",
      {"camera": P(str, "back (arka) veya front (ön)", required=False, enum=["back", "front"]),
       "question": P(str, "Fotoğrafla ilgili soru (isteğe bağlı)", required=False)}, approval=True,
      summary=lambda a: f"📷 Telefonla fotoğraf çek ({a.get('camera', 'back')} kamera)")
async def phone_photo(ctx: ToolContext, camera: str = "back", question: str = ""):
    r = await _phone(ctx, "photo", timeout=60, camera=camera)
    if "error" in r or "file" not in r:
        return r if "error" in r else {"error": "Fotoğraf alınamadı"}
    await ctx.app.notifier.send_photo(r["file"], "📷 Telefondan")
    out = {"sent": True}
    if question:
        out["answer"] = await ctx.app.llm.vision(r["file"], question, mime="image/jpeg")
    return out


@tool("phone_clipboard_get", "Telefonun panosundaki metni okur.", "phone")
async def phone_clipboard_get(ctx: ToolContext):
    return _data(await _phone(ctx, "clipboard_get"))


@tool("phone_clipboard_set", "Telefonun panosuna metin kopyalar.", "phone", {"text": P(str, "Metin")})
async def phone_clipboard_set(ctx: ToolContext, text: str):
    return _data(await _phone(ctx, "clipboard_set", text=text))


# ---------------- Seviye 1: eylemler ----------------
@tool("phone_torch", "Telefonun fenerini açar/kapatır.", "phone", {"on": P(bool, "Açık mı")})
async def phone_torch(ctx: ToolContext, on: bool):
    return _data(await _phone(ctx, "torch", on=bool(on)))


@tool("phone_volume", "Telefonun ses seviyesini ayarlar.", "phone",
      {"stream": P(str, "Ses kanalı", enum=["music", "ring", "alarm", "notification", "call", "system"]),
       "level": P(int, "Seviye (0-15)")})
async def phone_volume(ctx: ToolContext, stream: str, level: int):
    return _data(await _phone(ctx, "volume", stream=stream, level=int(level)))


@tool("phone_speak", "Telefonun hoparlöründen metni sesli okur.", "phone", {"text": P(str, "Okunacak metin")})
async def phone_speak(ctx: ToolContext, text: str):
    return _data(await _phone(ctx, "speak", text=text))


@tool("phone_vibrate", "Telefonu titretir (bulmak için de kullanılır).", "phone",
      {"ms": P(int, "Süre milisaniye (varsayılan 1000)", required=False)})
async def phone_vibrate(ctx: ToolContext, ms: int = 1000):
    return _data(await _phone(ctx, "vibrate", ms=int(ms)))


@tool("phone_find", "Telefonu bulmak için sesi açar, yüksek sesle konuşur ve titretir.", "phone")
async def phone_find(ctx: ToolContext):
    await _phone(ctx, "volume", stream="music", level=15)
    await _phone(ctx, "vibrate", ms=2000)
    return _data(await _phone(ctx, "speak", text="Buradayım! Telefonun burada!"))


@tool("phone_open_url", "Telefonda bir bağlantı açar (web, YouTube, harita...).", "phone", {"url": P(str, "Adres")})
async def phone_open_url(ctx: ToolContext, url: str):
    return _data(await _phone(ctx, "open_url", url=url))


@tool("phone_list_apps", "Telefonda yüklü uygulamaların paket adlarını listeler.", "phone",
      {"query": P(str, "Filtre (ör. whatsapp)", required=False)})
async def phone_list_apps(ctx: ToolContext, query: str = ""):
    r = await _phone(ctx, "list_apps")
    if "error" in r:
        return r
    apps = r.get("data") or []
    return [a for a in apps if query.lower() in a.lower()][:80] if query else apps[:150]


@tool("phone_open_app", "Telefonda uygulama açar (paket adıyla, ör. com.whatsapp). Paket bilinmiyorsa phone_list_apps kullan.",
      "phone", {"package": P(str, "Paket adı")})
async def phone_open_app(ctx: ToolContext, package: str):
    return _data(await _phone(ctx, "open_app", package=package))


@tool("phone_set_alarm", "Telefonun saat uygulamasına alarm kurar.", "phone",
      {"hour": P(int, "Saat (0-23)"), "minute": P(int, "Dakika"), "label": P(str, "Etiket", required=False)})
async def phone_set_alarm(ctx: ToolContext, hour: int, minute: int, label: str = "YAi"):
    return _data(await _phone(ctx, "alarm", hour=int(hour), minute=int(minute), label=label))


@tool("phone_set_timer", "Telefonda geri sayım sayacı kurar.", "phone",
      {"seconds": P(int, "Süre (saniye)"), "label": P(str, "Etiket", required=False)})
async def phone_set_timer(ctx: ToolContext, seconds: int, label: str = "YAi"):
    return _data(await _phone(ctx, "timer", seconds=int(seconds), label=label))


@tool("phone_notify", "Telefonda bildirim gösterir.", "phone", {"title": P(str, "Başlık"), "content": P(str, "İçerik")})
async def phone_notify(ctx: ToolContext, title: str, content: str):
    return _data(await _phone(ctx, "notify", title=title, content=content))


# ---------------- Seviye 2: Tasker ----------------
@tool("phone_tasker", "Telefondaki bir Tasker görevini adıyla çalıştırır (Wi-Fi, Bluetooth, rahatsız etmeyin, özel otomasyonlar).",
      "phone", {"task": P(str, "Tasker görev adı"), "param": P(str, "Görev parametresi (%par1)", required=False)})
async def phone_tasker(ctx: ToolContext, task: str, param: str = ""):
    return _data(await _phone(ctx, "tasker", task=task, param=param))


# ---------------- Seviye 3: ekran kontrolü (ADB) ----------------
def _screen_ok(ctx: ToolContext) -> bool:
    return ctx.app.db.get("screen_until", 0) > time.time()


def _png_size(data: bytes) -> tuple[int, int]:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    return (0, 0)


@tool("phone_screen_control", "Telefon ekranını kontrol etme oturumu başlatır (dokunma/kaydırma/yazma için gerekli). "
      "Kullanıcı onaylayınca belirtilen dakika boyunca geçerli olur.", "phone_screen",
      {"minutes": P(int, "Oturum süresi (dakika, en fazla 30)"), "reason": P(str, "Ne yapılacak")}, approval=True,
      summary=lambda a: f"🖐️ Telefon ekranını {min(int(a['minutes']), 30)} dk kontrol et\nAmaç: {a['reason']}")
async def phone_screen_control(ctx: ToolContext, minutes: int, reason: str):
    ctx.app.db.set("screen_until", time.time() + min(int(minutes), 30) * 60)
    r = await _phone(ctx, "adb_status")
    return {"enabled_minutes": min(int(minutes), 30), "adb": _data(r)}


@tool("phone_screen_look", "Telefon ekranının görüntüsünü alıp inceler. Dokunulacak öğelerin piksel koordinatlarını verir.",
      "phone_screen", {"question": P(str, "Ekranda ne aranıyor / soru"),
                       "send_to_user": P(bool, "Görüntü kullanıcıya da gönderilsin mi", required=False)})
async def phone_screen_look(ctx: ToolContext, question: str, send_to_user: bool = False):
    r = await _phone(ctx, "adb_screenshot", timeout=30)
    if "error" in r or "file" not in r:
        return r if "error" in r else {"error": "Ekran görüntüsü alınamadı"}
    img = r["file"]
    w, h = _png_size(img)
    if send_to_user:
        await ctx.app.notifier.send_photo(img, "📱 Telefon ekranı")
    prompt = (f"Bu bir Android telefon ekran görüntüsü, boyutu {w}x{h} piksel. {question}\n"
              "Ekranda ne olduğunu kısaca anlat. İlgili her tıklanabilir öğe için 'öğe: (x, y)' biçiminde "
              f"merkez piksel koordinatını ver (x 0-{w}, y 0-{h}).")
    return {"width": w, "height": h, "analysis": await ctx.app.llm.vision(img, prompt, tier="smart")}


async def _screen(ctx: ToolContext, action: str, **args):
    if not _screen_ok(ctx):
        return {"error": "Ekran kontrol oturumu yok. Önce phone_screen_control ile kullanıcıdan onay al."}
    return _data(await _phone(ctx, action, **args))


@tool("phone_tap", "Telefon ekranında bir noktaya dokunur.", "phone_screen", {"x": P(int, "x piksel"), "y": P(int, "y piksel")})
async def phone_tap(ctx: ToolContext, x: int, y: int):
    return await _screen(ctx, "adb_tap", x=int(x), y=int(y))


@tool("phone_swipe", "Telefon ekranında kaydırır.", "phone_screen",
      {"x1": P(int, "başlangıç x"), "y1": P(int, "başlangıç y"), "x2": P(int, "bitiş x"), "y2": P(int, "bitiş y"),
       "ms": P(int, "süre ms", required=False)})
async def phone_swipe(ctx: ToolContext, x1: int, y1: int, x2: int, y2: int, ms: int = 300):
    return await _screen(ctx, "adb_swipe", x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2), ms=int(ms))


@tool("phone_type_text", "Telefonda seçili alana yazı yazar.", "phone_screen", {"text": P(str, "Metin")})
async def phone_type_text(ctx: ToolContext, text: str):
    return await _screen(ctx, "adb_text", text=text)


@tool("phone_key", "Telefonda tuşa basar.", "phone_screen",
      {"key": P(str, "Tuş", enum=["back", "home", "recents", "enter", "power", "volume_up", "volume_down", "delete"])})
async def phone_key(ctx: ToolContext, key: str):
    return await _screen(ctx, "adb_key", key=key)


# ---------------- YAi uygulaması: erişilebilirlik ile ekran okuma ve öğrenme modu ----------------
@tool("phone_screen_read", "Telefon ekranındaki öğeleri (yazılar, butonlar, koordinatlar) metin olarak okur. "
      "Ekran görüntüsünden çok daha ucuzdur; önce bunu dene. YAi uygulaması gerekir.", "phone_screen")
async def phone_screen_read(ctx: ToolContext):
    if not _screen_ok(ctx):
        return {"error": "Ekran kontrol oturumu yok. Önce phone_screen_control ile kullanıcıdan onay al."}
    return _data(await _phone(ctx, "ui_tree"))


@tool("phone_click_text", "Telefon ekranında görünen yazıya/butona tıklar (ör. 'Ara', 'Gönder').", "phone_screen",
      {"text": P(str, "Tıklanacak öğenin yazısı veya açıklaması")})
async def phone_click_text(ctx: ToolContext, text: str):
    return await _screen(ctx, "click_text", text=text)


@tool("phone_learned_apps", "Öğrenme modunda öğrenilmiş telefon uygulamalarını listeler (kullanıcının YAi uygulamasında "
      "seçtiği uygulamalar).", "phone")
async def phone_learned_apps(ctx: ToolContext):
    return _data(await _phone(ctx, "learned_apps"))


@tool("phone_app_guide", "Öğrenilmiş bir uygulamanın kullanım rehberini getirir: hangi ekranlar var, her ekranda hangi "
      "butonlar var, hangi butona basınca hangi ekrana gidiliyor. Bir uygulamada iş yapmadan önce kullan.", "phone",
      {"package": P(str, "Uygulama paket adı (phone_learned_apps ile bulunur)")})
async def phone_app_guide(ctx: ToolContext, package: str):
    return _data(await _phone(ctx, "app_guide", package=package))
