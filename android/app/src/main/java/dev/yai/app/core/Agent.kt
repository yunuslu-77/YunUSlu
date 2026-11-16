package dev.yai.app.core

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/** Bir aracın gerçekten çalıştırılması (sohbette kart olarak gösterilir). */
data class ToolEvent(val name: String, val args: JSONObject, val result: String, val ok: Boolean) {
    fun toJson(): JSONObject = JSONObject().put("name", name).put("args", args).put("result", result).put("ok", ok)
    companion object {
        fun fromJson(j: JSONObject) = ToolEvent(j.getString("name"), j.optJSONObject("args") ?: JSONObject(), j.optString("result"), j.optBoolean("ok"))
    }
}

data class Reply(val text: String, val events: List<ToolEvent>)

/** YAi'nin beyni: Gemini ile araç kullanma döngüsü, hafıza ve onay sistemi. Tamamen telefonda çalışır. */
class Agent(private val yai: Yai, private val tools: List<Tool> = allTools()) {
    private val byName = tools.associateBy { it.name }
    private val lock = Mutex()
    var maxSteps = 12
    var historyLimit = 20

    private fun systemPrompt(): String {
        val mem = yai.db.memories().joinToString("\n") { "- (#${it.id}) ${it.fact}" }.ifBlank { "- (henüz yok)" }
        val skills = yai.db.skills().let { s -> (0 until s.length()).joinToString("\n") { "- ${s.getJSONObject(it).getString("name")}: ${s.getJSONObject(it).getString("trigger")}" } }
            .ifBlank { "- (henüz yok)" }
        val learned = yai.learning.learnedAppsJson().let { a -> (0 until a.length()).joinToString(", ") { a.getJSONObject(it).getString("name") } }
            .ifBlank { "yok" }
        val now = ZonedDateTime.now()
        val days = listOf("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
        return """Sen YAi'sin: kullanıcının telefonunda çalışan kişisel yapay zekâ asistanısın. Telefonu kullanıcının onayıyla kontrol edebilirsin.

KURALLAR
- Her zaman Türkçe, samimi ve kısa cevap ver. Gerekirse Markdown kullan: **kalın**, madde listesi, numaralı liste, tablo.
- EN ÖNEMLİ KURAL: Bir işlemi (alarm, SMS, arama, fener, ses, uygulama açma, hatırlatıcı...) ancak ilgili ARACI ÇAĞIRDIYSAN ve
  araç başarılı sonuç döndürdüyse "yaptım" de. Araç çağırmadan asla "yaptım / kurdum / açtım / gönderdim" deme.
  Araç hata döndürürse hatayı ve çözümünü (ör. hangi izin gerekli) kullanıcıya söyle.
- Sonuçlar kullanıcıya ayrıca kart olarak gösterilir; bu yüzden cevabında kartın içeriğini uzun uzun tekrar etme, kısa yorum yap.
- Hesaplama gereken her şeyde (yüzde, faiz, birim, aritmetik) calculate aracını kullan; kafadan hesap yapma.
- Bir işi yapan bir araç varsa sormadan kullan. Bilgi uydurma; emin değilsen web_search ile ara.
- Bazı araçlar (SMS, arama, fotoğraf, ekran kontrolü, beceri kaydı) kullanıcı onayı ister. Araç 'onay_bekleniyor' dönerse
  kullanıcıya onay butonuna basmasını söyle ve aynı aracı tekrar çağırma.
- Para gönderme, satın alma ve şifre girme işlemlerini ASLA kendin tamamlama. Banka/şifre uygulamaları sana kapalıdır.
- "Her sabah / her gün / her pazartesi ..." gibi tekrar eden işler için create_schedule; sadece hatırlatma için set_reminder kullan.
- Kullanıcı kendisiyle ilgili kalıcı bilgi verirse (isim, şehir, tercih, aile) remember ile kaydet.
- E-postalara doğrudan erişimin yok; Gmail bildirimlerini phone_notifications ile okuyabilirsin. Takvim için calendar_* araçları var.
- Uygulama açmak için phone_open_app'e uygulamanın adını yazman yeterli (ör. "WhatsApp").
- Bir uygulamada iş yapman istenirse: phone_screen_control ile oturum aç, uygulama öğrenildiyse phone_app_guide ile rehberine bak,
  phone_open_app ile aç, phone_screen_read ile ekranı oku, phone_click_text / phone_tap / phone_type_text ile ilerle, her adımdan sonra tekrar oku.
- Zamanlanmış görev olarak çalışıyorsan sonucu doğrudan kullanıcıya gidecek kısa bir bildirim metni olarak yaz.

KULLANICI HAKKINDA
$mem

BECERİLER
$skills

ÖĞRENİLMİŞ UYGULAMALAR: $learned

ŞU AN: ${now.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"))} (${days[now.dayOfWeek.value - 1]})"""
    }

    private fun textPart(t: String) = JSONObject().put("text", t)
    private fun turn(role: String, vararg parts: JSONObject) = JSONObject().put("role", role).put("parts", JSONArray().apply { parts.forEach { put(it) } })

    /** Kullanıcı mesajı (isteğe bağlı görsel). */
    suspend fun handleUser(text: String, image: Pair<ByteArray, String>? = null): String = handle(text, image).text

    suspend fun handle(text: String, image: Pair<ByteArray, String>? = null, done: List<ToolEvent> = emptyList()): Reply = lock.withLock {
        val contents = JSONArray()
        yai.db.recentMessages(historyLimit).forEach { contents.put(turn(if (it.role == "user") "user" else "model", textPart(it.text))) }
        val parts = mutableListOf(textPart(text))
        image?.let { (bytes, mime) -> parts.add(JSONObject().put("inlineData", JSONObject().put("mimeType", mime)
            .put("data", android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP)))) }
        contents.put(turn("user", *parts.toTypedArray()))
        yai.db.addMessage("user", if (image != null) "[Fotoğraf] $text" else text)
        val events = done.toMutableList()
        val reply = loop(contents, events, allowNudge = !text.startsWith("[Sistem]"))
        yai.db.addMessage("model", reply, JSONArray().apply { events.forEach { put(it.toJson()) } }.toString())
        Reply(reply, events)
    }

    /** Zamanlanmış görev: geçmişe de yazılır ki kullanıcı devam edebilsin. */
    suspend fun runTask(task: String): String = handleUser("[Zamanlanmış görev] $task")

    private val claimRe = Regex("(kurdum|kuruldu|açtım|açıldı|kapattım|kapatıldı|gönderdim|gönderildi|aradım|arıyorum|ayarladım|" +
        "ayarlandı|yaptım|tamamlandı|ekledim|eklendi|hatırlatacağım|başlattım|başlatıldı)", RegexOption.IGNORE_CASE)

    private suspend fun loop(contents: JSONArray, events: MutableList<ToolEvent>, allowNudge: Boolean = true): String {
        val decl = JSONArray().apply { tools.forEach { put(it.declaration()) } }
        val system = systemPrompt()
        var nudged = false
        return try {
            repeat(maxSteps) {
                val r = yai.llm.generate(true, system, contents, decl)
                if (r.calls.isEmpty()) {
                    // Araç çağırmadan "yaptım" dediyse: bir kez uyar ve gerçekten yapmasını iste
                    if (allowNudge && !nudged && events.isEmpty() && claimRe.containsMatchIn(r.text)) {
                        nudged = true
                        r.content?.let { contents.put(it) }
                        contents.put(turn("user", textPart("[Sistem] Hiçbir araç çağırmadın, bu yüzden hiçbir işlem YAPILMADI. " +
                            "İşlemi gerçekten yapmak için uygun aracı ŞİMDİ çağır. Yapamıyorsan nedenini dürüstçe söyle.")))
                        return@repeat
                    }
                    return r.text.ifBlank { "👍" }
                }
                contents.put(r.content)
                val responses = r.calls.map { call ->
                    val raw = execute(call.name, call.args)
                    val failed = raw is JSONObject && raw.has("error")
                    events.add(ToolEvent(call.name, call.args, raw?.toString()?.take(6000) ?: "tamam", !failed))
                    val result = clip(raw)
                    JSONObject().put("functionResponse", JSONObject().put("name", call.name).put("response", JSONObject().put("result", result)))
                }
                contents.put(turn("user", *responses.toTypedArray()))
            }
            "⚠️ Bu iş çok fazla adım sürdü, durdum. Daha küçük parçalara bölebilir misin?"
        } catch (e: BudgetExceeded) {
            "💸 ${e.message}"
        } catch (e: LlmException) {
            "⚠️ ${e.message}"
        }
    }

    private fun clip(v: Any?): Any {
        val s = when (v) { null -> "tamam"; is JSONObject, is JSONArray -> v.toString(); else -> v.toString() }
        if (s.length > 12000) return JSONObject().put("truncated", true).put("data", s.take(12000))
        return v ?: "tamam"
    }

    suspend fun execute(name: String, args: JSONObject, approved: Boolean = false): Any? {
        val t = byName[name] ?: return JSONObject().put("error", "Bilinmeyen araç: $name")
        if (!approved && t.approval(args)) {
            yai.db.findPending(name, args)?.let { return JSONObject().put("status", "onay_bekleniyor").put("approval_id", it) }
            val summary = t.describe(args)
            val id = yai.db.addApproval(name, args, summary)
            yai.notifier.approvalRequested(id, summary)
            return JSONObject().put("status", "onay_bekleniyor").put("approval_id", id)
                .put("note", "Kullanıcıya onay butonu gösterildi. Onaylanınca işlem otomatik yapılacak.")
        }
        return try {
            val r = t.run(ToolCtx(yai, approved), args)
            yai.db.audit(name, args.toString(), r.toString(), true)
            r
        } catch (e: Exception) {
            yai.db.audit(name, args.toString(), e.message ?: "", false)
            JSONObject().put("error", e.message ?: e.javaClass.simpleName)
        }
    }

    /** Kullanıcı onay/iptal butonuna bastı. */
    suspend fun resolveApproval(id: Long, approve: Boolean): String = resolve(id, approve).text

    suspend fun resolve(id: Long, approve: Boolean): Reply {
        val a = yai.db.approval(id) ?: return Reply("Bu onay bulunamadı.", emptyList())
        if (a.status != "pending") return Reply("Bu işlem zaten ${if (a.status == "approved") "yapıldı" else "iptal edildi"}.", emptyList())
        if (!approve) {
            yai.db.decideApproval(id, "denied")
            yai.db.addMessage("model", "❌ İptal edildi: ${a.summary}")
            return Reply("❌ İptal edildi.", emptyList())
        }
        yai.db.decideApproval(id, "approved")
        val result = execute(a.tool, a.args, approved = true)
        yai.db.decideApproval(id, "approved", result.toString().take(3000))
        val ev = ToolEvent(a.tool, a.args, result?.toString()?.take(6000) ?: "tamam", !(result is JSONObject && result.has("error")))
        return handle("[Sistem] Kullanıcı #$id işlemini ONAYLADI ve işlem yapıldı.\nİşlem: ${a.summary}\n" +
            "Sonuç: ${result.toString().take(3000)}\nKullanıcıya sonucu kısaca bildir; görevin devamı varsa devam et.", done = listOf(ev))
    }

    fun toolNames() = tools.map { it.name }
}
