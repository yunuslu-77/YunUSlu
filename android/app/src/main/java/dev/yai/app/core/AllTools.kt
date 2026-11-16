package dev.yai.app.core

import android.content.ContentUris
import android.content.ContentValues
import android.provider.CalendarContract
import dev.yai.app.bridge.YaiAccessibilityService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit

private val http = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS).build()
private val DAYS_TR = listOf("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

private suspend fun getText(url: String): Pair<Int, String> = withContext(Dispatchers.IO) {
    http.newCall(Request.Builder().url(url).header("User-Agent", "Mozilla/5.0 (Android) YAi").build()).execute().use { it.code to it.body.string() }
}

fun htmlToText(html: String, limit: Int = 8000): JSONObject {
    val title = Regex("<title[^>]*>(.*?)</title>", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)).find(html)?.groupValues?.get(1)?.trim() ?: ""
    val text = html.replace(Regex("<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\\1>", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)), " ")
        .replace(Regex("<br\\s*/?>|</p>|</div>|</li>|</h\\d>", RegexOption.IGNORE_CASE), "\n")
        .replace(Regex("<[^>]+>"), " ")
        .replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", "\"").replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
        .lines().map { it.replace(Regex("\\s+"), " ").trim() }.filter { it.isNotEmpty() }.joinToString("\n")
    return JSONObject().put("title", title).put("text", text.take(limit)).put("truncated", text.length > limit)
}

private val WMO = mapOf(0 to "açık", 1 to "çoğunlukla açık", 2 to "parçalı bulutlu", 3 to "kapalı", 45 to "sisli", 48 to "kırağılı sis",
    51 to "hafif çisenti", 53 to "çisenti", 55 to "yoğun çisenti", 61 to "hafif yağmur", 63 to "yağmur", 65 to "kuvvetli yağmur",
    71 to "hafif kar", 73 to "kar", 75 to "yoğun kar", 80 to "sağanak", 81 to "kuvvetli sağanak", 82 to "şiddetli sağanak",
    95 to "gök gürültülü fırtına", 96 to "dolulu fırtına", 99 to "şiddetli dolu")

private suspend fun phone(c: ToolCtx, action: String, args: JSONObject = JSONObject()): Any {
    if (!c.yai.prefs.phoneEnabled) throw ToolError("Telefon erişimi kapalı (Ayarlar).")
    return c.yai.commands.execute(action, args).data
}

private fun screenOk(c: ToolCtx) = c.yai.prefs.screenUntil > System.currentTimeMillis()

private suspend fun screen(c: ToolCtx, action: String, args: JSONObject = JSONObject()): Any {
    if (!screenOk(c)) throw ToolError("Ekran kontrol oturumu yok. Önce phone_screen_control ile kullanıcıdan onay al.")
    return phone(c, action, args)
}

private fun pngSize(b: ByteArray): Pair<Int, Int> =
    if (b.size > 24 && b[1] == 'P'.code.toByte()) {
        val w = ((b[16].toInt() and 0xff) shl 24) or ((b[17].toInt() and 0xff) shl 16) or ((b[18].toInt() and 0xff) shl 8) or (b[19].toInt() and 0xff)
        val h = ((b[20].toInt() and 0xff) shl 24) or ((b[21].toInt() and 0xff) shl 16) or ((b[22].toInt() and 0xff) shl 8) or (b[23].toInt() and 0xff)
        w to h
    } else 0 to 0

fun allTools(): List<Tool> = listOf(
    // ================= temel =================
    tool("get_datetime", "Şu anki tarih, saat ve gün.") { _, _ ->
        val n = ZonedDateTime.now()
        JSONObject().put("datetime", n.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"))).put("day", DAYS_TR[n.dayOfWeek.value - 1])
    },
    tool("remember", "Kullanıcı hakkında kalıcı bir bilgiyi hafızaya kaydeder (isim, şehir, tercih, aile, iş...).",
        "fact" to P.str("Hatırlanacak bilgi, tek cümle")) { c, a -> JSONObject().put("saved_id", c.yai.db.addMemory(a.getString("fact"))) },
    tool("list_memories", "Kalıcı hafızadaki bilgileri listeler.") { c, _ ->
        JSONArray().apply { c.yai.db.memories().forEach { put(JSONObject().put("id", it.id).put("fact", it.fact)) } } },
    tool("forget", "Hafızadan bir bilgiyi siler.", "memory_id" to P.int("Hafıza id")) { c, a ->
        JSONObject().put("deleted", c.yai.db.deleteMemory(a.getLong("memory_id"))) },

    // ================= notlar =================
    tool("create_page", "Not/rapor sayfası oluşturur (Beyin → Sayfalar'da görünür).", "title" to P.str("Başlık"), "content" to P.str("İçerik")) { c, a ->
        JSONObject().put("page_id", c.yai.db.savePage(null, a.getString("title"), a.getString("content"))) },
    tool("update_page", "Sayfayı günceller veya sonuna ekler.", "page_id" to P.int("Sayfa id"), "content" to P.str("İçerik"),
        "append" to P.bool("Sona ekle", false)) { c, a ->
        JSONObject().put("ok", c.yai.db.savePage(a.getLong("page_id"), null, a.getString("content"), a.optBoolean("append")) > 0) },
    tool("read_page", "Sayfayı okur.", "page_id" to P.int("Sayfa id")) { c, a ->
        c.yai.db.page(a.getLong("page_id"))?.let { JSONObject().put("title", it.title).put("content", it.content) } ?: throw ToolError("Sayfa yok") },
    tool("list_pages", "Sayfaları listeler.") { c, _ ->
        JSONArray().apply { c.yai.db.pages().forEach { put(JSONObject().put("id", it.id).put("title", it.title)) } } },

    // ================= beceriler =================
    tool("save_skill", "Tekrar eden bir işi beceri olarak kaydeder.", "name" to P.str("Kısa ad"), "trigger" to P.str("Ne zaman kullanılır"),
        "steps" to P.str("Adımlar"), approval = approvalAlways(),
        summary = { "🧠 Beceri kaydet: «${it.optString("name")}»\n${it.optString("steps")}" }) { c, a ->
        c.yai.db.saveSkill(a.getString("name"), a.getString("trigger"), a.getString("steps")); JSONObject().put("saved", true) },
    tool("use_skill", "Kayıtlı bir becerinin adımlarını getirir.", "name" to P.str("Beceri adı")) { c, a ->
        c.yai.db.useSkill(a.getString("name")) ?: throw ToolError("Beceri yok") },

    // ================= görevler =================
    tool("create_schedule", "Zamanlanmış görev kurar: zamanı gelince YAi 'task' talimatını kendisi çalıştırır ve sonucu bildirim " +
        "olarak gönderir (sabah brifingi, haftalık özet...). Zaman: ${TimeParse.HELP}",
        "when" to P.str("Zaman ifadesi"), "task" to P.str("Yapılacak iş")) { c, a ->
        val spec = try { TimeParse.parse(a.getString("when")) } catch (e: WhenError) { throw ToolError("${e.message}. Örnek: ${TimeParse.HELP}") }
        val id = c.yai.alarms.add("prompt", a.getString("task"), spec)
        JSONObject().put("schedule_id", id).put("when", TimeParse.describe(spec))
    },
    tool("set_reminder", "Hatırlatıcı kurar: zamanı gelince sadece bildirim gösterir (ücretsiz). Zaman: ${TimeParse.HELP}",
        "when" to P.str("Zaman ifadesi"), "message" to P.str("Hatırlatma metni")) { c, a ->
        val spec = try { TimeParse.parse(a.getString("when")) } catch (e: WhenError) { throw ToolError("${e.message}. Örnek: ${TimeParse.HELP}") }
        val id = c.yai.alarms.add("message", a.getString("message"), spec)
        JSONObject().put("schedule_id", id).put("when", TimeParse.describe(spec))
    },
    tool("list_schedules", "Kurulu görev ve hatırlatıcıları listeler.") { c, _ ->
        JSONArray().apply { c.yai.db.schedules().forEach { put(JSONObject().put("id", it.id).put("kind", it.kind)
            .put("text", it.payload).put("when", TimeParse.describe(it.spec))) } } },
    tool("delete_schedule", "Görev/hatırlatıcıyı siler.", "schedule_id" to P.int("Görev id")) { c, a ->
        JSONObject().put("deleted", c.yai.alarms.remove(a.getLong("schedule_id"))) },

    // ================= web =================
    tool("web_search", "Google'da arayıp güncel bilgiyi kaynaklarıyla özetler (haber, fiyat, kur, olay, genel bilgi).",
        "query" to P.str("Arama sorgusu")) { c, a -> c.yai.llm.search(a.getString("query")) },
    tool("fetch_url", "Bir web sayfasının metnini okur.", "url" to P.str("Adres")) { _, a ->
        val (code, body) = getText(a.getString("url"))
        htmlToText(body).put("status", code)
    },
    tool("get_weather", "Bir şehrin hava durumu ve 3 günlük tahmini.", "city" to P.str("Şehir")) { _, a ->
        val city = java.net.URLEncoder.encode(a.getString("city"), "UTF-8")
        val g = JSONObject(getText("https://geocoding-api.open-meteo.com/v1/search?name=$city&count=1&language=tr").second)
        val loc = g.optJSONArray("results")?.optJSONObject(0) ?: throw ToolError("Şehir bulunamadı")
        val w = JSONObject(getText("https://api.open-meteo.com/v1/forecast?latitude=${loc.getDouble("latitude")}&longitude=${loc.getDouble("longitude")}" +
            "&timezone=auto&forecast_days=3&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m" +
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max").second)
        val cur = w.getJSONObject("current"); val d = w.getJSONObject("daily")
        JSONObject().put("yer", loc.getString("name"))
            .put("şimdi", JSONObject().put("sıcaklık", cur.opt("temperature_2m")).put("hissedilen", cur.opt("apparent_temperature"))
                .put("durum", WMO[cur.optInt("weather_code")] ?: "?").put("rüzgar_kmh", cur.opt("wind_speed_10m")))
            .put("tahmin", JSONArray().apply { for (i in 0 until d.getJSONArray("time").length()) put(JSONObject()
                .put("tarih", d.getJSONArray("time").getString(i)).put("durum", WMO[d.getJSONArray("weather_code").getInt(i)] ?: "?")
                .put("max", d.getJSONArray("temperature_2m_max").get(i)).put("min", d.getJSONArray("temperature_2m_min").get(i))
                .put("yağış_%", d.getJSONArray("precipitation_probability_max").get(i))) })
    },

    // ================= takvim (telefonun Google Takvim'i) =================
    tool("calendar_list", "Telefondaki takvimden (Google Takvim dahil) yaklaşan etkinlikleri listeler.",
        "days" to P.int("Kaç gün ileri (varsayılan 1)", false)) { c, a ->
        val zone = ZoneId.systemDefault()
        val start = LocalDate.now().atStartOfDay(zone).toInstant().toEpochMilli()
        val end = start + a.optInt("days", 1).coerceIn(1, 31) * 86_400_000L
        val uri = CalendarContract.Instances.CONTENT_URI.buildUpon().also { ContentUris.appendId(it, start); ContentUris.appendId(it, end) }.build()
        val out = JSONArray()
        c.yai.context.contentResolver.query(uri, arrayOf(CalendarContract.Instances.TITLE, CalendarContract.Instances.BEGIN,
            CalendarContract.Instances.END, CalendarContract.Instances.EVENT_LOCATION, CalendarContract.Instances.ALL_DAY),
            null, null, CalendarContract.Instances.BEGIN + " ASC")?.use { cur ->
            val f = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
            while (cur.moveToNext() && out.length() < 60) out.put(JSONObject().put("title", cur.getString(0) ?: "(başlıksız)")
                .put("start", java.time.Instant.ofEpochMilli(cur.getLong(1)).atZone(zone).format(f))
                .put("end", java.time.Instant.ofEpochMilli(cur.getLong(2)).atZone(zone).format(f))
                .put("location", cur.getString(3) ?: "").put("all_day", cur.getInt(4) == 1))
        } ?: throw ToolError("Takvim izni yok (Ayarlar → İzinler)")
        out
    },
    tool("calendar_create", "Telefonun takvimine (Google Takvim) etkinlik ekler. Zaman: 'YYYY-AA-GG SS:DD'.",
        "title" to P.str("Başlık"), "start" to P.str("Başlangıç"), "end" to P.str("Bitiş", false),
        "location" to P.str("Yer", false), "description" to P.str("Açıklama", false)) { c, a ->
        val cr = c.yai.context.contentResolver
        val calId = cr.query(CalendarContract.Calendars.CONTENT_URI, arrayOf(CalendarContract.Calendars._ID, CalendarContract.Calendars.IS_PRIMARY),
            "${CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL}>=${CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR}", null,
            CalendarContract.Calendars.IS_PRIMARY + " DESC")?.use { if (it.moveToFirst()) it.getLong(0) else null }
            ?: throw ToolError("Yazılabilir takvim bulunamadı veya takvim izni yok")
        val f = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
        val s = LocalDateTime.parse(a.getString("start").replace("T", " ").take(16), f).atZone(ZoneId.systemDefault())
        val e = a.optString("end").takeIf { it.length >= 16 }?.let { LocalDateTime.parse(it.replace("T", " ").take(16), f).atZone(ZoneId.systemDefault()) } ?: s.plusHours(1)
        val uri = cr.insert(CalendarContract.Events.CONTENT_URI, ContentValues().apply {
            put(CalendarContract.Events.CALENDAR_ID, calId); put(CalendarContract.Events.TITLE, a.getString("title"))
            put(CalendarContract.Events.DTSTART, s.toInstant().toEpochMilli()); put(CalendarContract.Events.DTEND, e.toInstant().toEpochMilli())
            put(CalendarContract.Events.EVENT_TIMEZONE, ZoneId.systemDefault().id)
            put(CalendarContract.Events.EVENT_LOCATION, a.optString("location")); put(CalendarContract.Events.DESCRIPTION, a.optString("description"))
        }) ?: throw ToolError("Etkinlik eklenemedi")
        JSONObject().put("event_id", ContentUris.parseId(uri)).put("start", s.format(f))
    },

    // ================= telefon =================
    tool("phone_status", "Pil, şarj ve Wi-Fi durumu.") { c, _ -> JSONObject().put("battery", phone(c, "battery")).put("wifi", phone(c, "wifi")) },
    tool("phone_notifications", "Telefondaki bildirimleri okur (WhatsApp, Gmail, SMS vb. bildirimleri; e-postalar buradan görülür).",
        "app_filter" to P.str("Sadece bu uygulama (ör. whatsapp, gm)", false)) { c, a ->
        val all = phone(c, "notifications") as JSONArray
        val f = a.optString("app_filter").lowercase()
        JSONArray().apply { for (i in 0 until all.length()) all.getJSONObject(i).let { if (f.isBlank() || f in it.optString("packageName").lowercase()) put(it) } }
    },
    tool("phone_sms_list", "Son SMS'leri okur.", "limit" to P.int("Kaç mesaj", false), "from" to P.str("Sadece bu kişi/numara", false)) { c, a ->
        val list = phone(c, "sms_list", JSONObject().put("limit", if (a.has("from")) 60 else a.optInt("limit", 10))) as JSONArray
        val q = a.optString("from").lowercase(); val digits = q.filter { it.isDigit() }.takeLast(10)
        JSONArray().apply { for (i in 0 until list.length()) { val m = list.getJSONObject(i)
            val num = m.optString("number").filter { it.isDigit() }
            if (q.isBlank() || (digits.isNotEmpty() && digits in num) || q in m.optString("sender").lowercase()) put(m)
            if (length() >= a.optInt("limit", 10)) break } }
    },
    tool("phone_sms_send", "SMS gönderir.", "number" to P.str("Numara"), "text" to P.str("Mesaj"), approval = approvalAlways(),
        summary = { "💬 SMS gönder\nKime: ${it.optString("number")}\n\n${it.optString("text")}" }) { c, a -> phone(c, "sms_send", a) },
    tool("phone_call", "Arama başlatır.", "number" to P.str("Numara"), approval = approvalAlways(),
        summary = { "📞 Ara: ${it.optString("number")}" }) { c, a -> phone(c, "call", a) },
    tool("phone_call_log", "Son aramalar.", "limit" to P.int("Kaç kayıt", false)) { c, a -> phone(c, "call_log", JSONObject().put("limit", a.optInt("limit", 10))) },
    tool("phone_contacts", "Rehberde kişi arar (numara bulmak için).", "query" to P.str("İsim veya numara")) { c, a ->
        val all = phone(c, "contacts") as JSONArray; val q = a.getString("query").lowercase()
        JSONArray().apply { for (i in 0 until all.length()) { val p = all.getJSONObject(i)
            if (q in p.optString("name").lowercase() || q in p.optString("number")) put(p); if (length() >= 20) break } }
    },
    tool("phone_location", "Telefonun konumu.") { c, _ ->
        (phone(c, "location") as JSONObject).apply { put("maps", "https://maps.google.com/?q=${optDouble("latitude")},${optDouble("longitude")}") } },
    tool("phone_photo", "Kamerayla fotoğraf çekip ne gördüğünü söyler.", "question" to P.str("Fotoğrafla ilgili soru"),
        "camera" to P.str("back veya front", false, listOf("back", "front")), approval = approvalAlways(),
        summary = { "📷 Fotoğraf çek (${it.optString("camera", "back")} kamera)" }) { c, a ->
        val r = c.yai.commands.execute("photo", JSONObject().put("camera", a.optString("camera", "back")))
        JSONObject().put("answer", c.yai.llm.vision(r.file ?: throw ToolError("Fotoğraf alınamadı"), "image/jpeg", a.getString("question")))
    },
    tool("phone_clipboard_set", "Panoya metin kopyalar.", "text" to P.str("Metin")) { c, a -> phone(c, "clipboard_set", a) },
    tool("phone_torch", "Feneri açar/kapatır.", "on" to P.bool("Açık mı")) { c, a -> phone(c, "torch", a) },
    tool("phone_volume", "Ses seviyesi (0-15).", "stream" to P.str("Kanal", enum = listOf("music", "ring", "alarm", "notification", "call")),
        "level" to P.int("0-15")) { c, a -> phone(c, "volume", a) },
    tool("phone_speak", "Hoparlörden metni sesli okur.", "text" to P.str("Metin")) { c, a -> phone(c, "speak", a) },
    tool("phone_find", "Telefonu bulmak için sesi açar, titreşir ve konuşur.") { c, _ ->
        phone(c, "volume", JSONObject().put("stream", "music").put("level", 15)); phone(c, "vibrate", JSONObject().put("ms", 2000))
        phone(c, "speak", JSONObject().put("text", "Buradayım! Telefonun burada!")) },
    tool("phone_open_url", "Bağlantı açar (web, YouTube, harita, tel:, whatsapp:...).", "url" to P.str("Adres")) { c, a -> phone(c, "open_url", a) },
    tool("phone_list_apps", "Yüklü uygulamalar (ad ve paket adı).", "query" to P.str("Filtre", false)) { c, a ->
        val all = phone(c, "list_apps") as JSONArray; val q = a.optString("query").lowercase()
        JSONArray().apply { for (i in 0 until all.length()) all.getString(i).let { if (q.isBlank() || q in it.lowercase()) put(it) } }
    },
    tool("phone_open_app", "Uygulama açar (paket adıyla; bilmiyorsan phone_list_apps).", "package" to P.str("Paket adı")) { c, a -> phone(c, "open_app", a) },
    tool("phone_set_alarm", "Saat uygulamasına alarm kurar.", "hour" to P.int("Saat"), "minute" to P.int("Dakika"), "label" to P.str("Etiket", false)) { c, a ->
        phone(c, "alarm", a) },
    tool("phone_set_timer", "Geri sayım sayacı kurar.", "seconds" to P.int("Saniye"), "label" to P.str("Etiket", false)) { c, a -> phone(c, "timer", a) },
    tool("phone_tasker", "Tasker görevini çalıştırır.", "task" to P.str("Görev adı"), "param" to P.str("Parametre", false)) { c, a -> phone(c, "tasker", a) },

    // ================= ekran kontrolü ve öğrenme =================
    tool("phone_screen_control", "Ekran kontrol oturumu başlatır (dokunma/okuma/yazma için gerekir; kullanıcı onaylar).",
        "minutes" to P.int("Süre (en fazla 30)"), "reason" to P.str("Ne yapılacak"), approval = approvalAlways(),
        summary = { "🖐️ Ekranı ${it.optInt("minutes").coerceIn(1, 30)} dk kontrol et\nAmaç: ${it.optString("reason")}" }) { c, a ->
        if (YaiAccessibilityService.instance == null) throw ToolError("Ekran kontrolü kapalı: Ayarlar → İzinler → 'Ekran kontrolü ve öğrenme'")
        c.yai.prefs.screenUntil = System.currentTimeMillis() + a.optInt("minutes", 5).coerceIn(1, 30) * 60_000L
        JSONObject().put("enabled_minutes", a.optInt("minutes", 5).coerceIn(1, 30))
    },
    tool("phone_screen_read", "Ekrandaki yazıları/butonları ve koordinatlarını okur (ucuz; önce bunu kullan).") { c, _ -> screen(c, "ui_tree") },
    tool("phone_screen_look", "Ekran görüntüsüne bakıp soruyu cevaplar ve dokunulacak yerlerin koordinatlarını verir.",
        "question" to P.str("Soru")) { c, a ->
        if (!screenOk(c)) throw ToolError("Ekran kontrol oturumu yok. Önce phone_screen_control.")
        val img = c.yai.commands.execute("adb_screenshot", JSONObject()).file ?: throw ToolError("Görüntü alınamadı")
        val (w, h) = pngSize(img)
        JSONObject().put("width", w).put("height", h).put("analysis", c.yai.llm.vision(img, "image/png",
            "Android ekran görüntüsü, ${w}x$h piksel. ${a.getString("question")}\nKısaca anlat; ilgili tıklanabilir öğeler için 'öğe: (x, y)' merkez koordinatı ver."))
    },
    tool("phone_click_text", "Ekranda yazısı görünen butona/öğeye tıklar.", "text" to P.str("Öğenin yazısı")) { c, a -> screen(c, "click_text", a) },
    tool("phone_tap", "Ekranda bir noktaya dokunur.", "x" to P.int("x"), "y" to P.int("y")) { c, a -> screen(c, "adb_tap", a) },
    tool("phone_swipe", "Ekranda kaydırır.", "x1" to P.int("x1"), "y1" to P.int("y1"), "x2" to P.int("x2"), "y2" to P.int("y2")) { c, a -> screen(c, "adb_swipe", a) },
    tool("phone_type_text", "Seçili yazı alanına metin yazar.", "text" to P.str("Metin")) { c, a -> screen(c, "adb_text", a) },
    tool("phone_key", "Tuşa basar.", "key" to P.str("Tuş", enum = listOf("back", "home", "recents", "enter", "notifications"))) { c, a -> screen(c, "adb_key", a) },
    tool("phone_learned_apps", "Öğrenme modunda öğrenilmiş uygulamalar.") { c, _ -> c.yai.learning.learnedAppsJson() },
    tool("phone_app_guide", "Öğrenilmiş uygulamanın rehberi: ekranlar, butonlar ve hangi butonun nereye götürdüğü. Uygulamada iş yapmadan önce kullan.",
        "package" to P.str("Paket adı")) { c, a -> c.yai.learning.guideJson(a.getString("package")) },
)

