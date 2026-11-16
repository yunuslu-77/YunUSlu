package dev.yai.app.core

import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.time.ZonedDateTime
import java.util.concurrent.TimeUnit

class LlmException(message: String) : Exception(message)
class BudgetExceeded(message: String) : Exception(message)

data class ToolCall(val name: String, val args: JSONObject)
data class LlmResult(val text: String, val calls: List<ToolCall>, val content: JSONObject?)

/** Yapay zekâ modeli arayüzü (testlerde sahtesi kullanılır). */
interface Llm {
    suspend fun generate(smart: Boolean, system: String, contents: JSONArray, tools: JSONArray?): LlmResult
    suspend fun search(query: String): JSONObject
    suspend fun vision(image: ByteArray, mime: String, question: String): String
}

/** Fiyatlar (USD / 1M token): Google AI Studio, Kasım 2026. */
object Prices {
    private val table = mapOf(
        "gemini-3.5-flash-lite" to (0.30 to 2.50), "gemini-3.1-flash-lite" to (0.25 to 1.50),
        "gemini-2.5-flash-lite" to (0.10 to 0.40), "gemini-3.8-flash" to (1.50 to 7.50), "gemini-3.6-flash" to (1.50 to 7.50),
        "gemini-3-flash-preview" to (0.50 to 3.00),
    )
    fun of(model: String) = table.entries.firstOrNull { model.startsWith(it.key) }?.value ?: (2.0 to 12.0)
    fun cost(model: String, tin: Int, cached: Int, tout: Int): Double {
        val (pin, pout) = of(model)
        val c = cached.coerceAtMost(tin)
        return ((tin - c) * pin + c * pin * 0.1 + tout * pout) / 1_000_000
    }
}

class Budget(private val db: Db, private val prefs: dev.yai.app.data.Prefs) {
    private fun day() = ZonedDateTime.now().toLocalDate().toString()
    private fun month() = day().take(7)
    fun record(model: String, tin: Int, cached: Int, tout: Int) =
        db.addUsage(day(), month(), model, tin, tout, Prices.cost(model, tin, cached, tout))
    fun today() = db.spent("day", day())
    fun month_() = db.spent("month", month())
    fun choose(smart: Boolean): String {
        if (month_() >= prefs.monthlyLimit) throw BudgetExceeded(
            "Aylık bütçe limiti (%.2f \$) doldu. Ayarlar'dan limiti artırabilir veya ay başını bekleyebilirsin.".format(prefs.monthlyLimit))
        return if (smart && today() < prefs.dailyLimit) prefs.modelSmart else prefs.modelFast
    }
}

/** Gemini REST API (anahtar telefonda saklanır, istekler doğrudan Google'a gider). */
class Gemini(private val key: () -> String, private val budget: Budget,
             private val base: String = "https://generativelanguage.googleapis.com/v1beta/models/") : Llm {
    private val http = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS).build()

    private suspend fun post(model: String, body: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        if (key().isBlank()) throw LlmException("Gemini API anahtarı girilmemiş (Ayarlar).")
        var last: String? = null
        for (attempt in 0 until 3) {
            val req = Request.Builder().url("$base$model:generateContent").header("x-goog-api-key", key())
                .post(body.toString().toRequestBody("application/json".toMediaType())).build()
            try {
                http.newCall(req).execute().use { r ->
                    val text = r.body.string()
                    if (r.isSuccessful) {
                        val j = JSONObject(text)
                        j.optJSONObject("usageMetadata")?.let { u ->
                            budget.record(model, u.optInt("promptTokenCount"), u.optInt("cachedContentTokenCount"),
                                u.optInt("candidatesTokenCount") + u.optInt("thoughtsTokenCount"))
                        }
                        return@withContext j
                    }
                    val msg = runCatching { JSONObject(text).getJSONObject("error").getString("message") }.getOrDefault(text.take(300))
                    last = when (r.code) {
                        400 -> if ("API key" in msg) "API anahtarı geçersiz. Ayarlar'dan kontrol et." else "İstek hatası: $msg"
                        403 -> "Erişim reddedildi: $msg"
                        429 -> "Ücretsiz kullanım sınırına ulaşıldı, biraz sonra tekrar dene. ($msg)"
                        else -> "Gemini hatası (${r.code}): $msg"
                    }
                    if (r.code != 429 && r.code < 500) throw LlmException(last)
                }
            } catch (e: java.io.IOException) {
                last = "İnternet bağlantısı yok veya Gemini'ye ulaşılamadı."
            }
            delay(1500L * (attempt + 1))
        }
        throw LlmException(last ?: "Bilinmeyen hata")
    }

    override suspend fun generate(smart: Boolean, system: String, contents: JSONArray, tools: JSONArray?): LlmResult {
        val model = budget.choose(smart)
        val body = JSONObject().put("systemInstruction", JSONObject().put("parts", JSONArray().put(JSONObject().put("text", system))))
            .put("contents", contents)
        if (tools != null && tools.length() > 0) body.put("tools", JSONArray().put(JSONObject().put("functionDeclarations", tools)))
        val r = post(model, body)
        val cand = r.optJSONArray("candidates")?.optJSONObject(0)
        val content = cand?.optJSONObject("content")
        val parts = content?.optJSONArray("parts") ?: JSONArray()
        val calls = mutableListOf<ToolCall>()
        val text = StringBuilder()
        for (i in 0 until parts.length()) {
            val p = parts.getJSONObject(i)
            p.optJSONObject("functionCall")?.let { calls.add(ToolCall(it.getString("name"), it.optJSONObject("args") ?: JSONObject())) }
            if (p.has("text") && !p.optBoolean("thought")) text.append(p.getString("text"))
        }
        if (content == null && calls.isEmpty()) {
            val reason = cand?.optString("finishReason") ?: r.optJSONObject("promptFeedback")?.optString("blockReason") ?: "boş cevap"
            return LlmResult("⚠️ Model cevap vermedi ($reason).", emptyList(), null)
        }
        return LlmResult(text.toString().trim(), calls, content?.apply { if (!has("role")) put("role", "model") })
    }

    override suspend fun search(query: String): JSONObject {
        val model = budget.choose(false)
        val body = JSONObject()
            .put("contents", JSONArray().put(JSONObject().put("role", "user").put("parts", JSONArray()
                .put(JSONObject().put("text", "Şunu web'de araştır ve kısa, doğru bir Türkçe özet ver: $query")))))
            .put("tools", JSONArray().put(JSONObject().put("googleSearch", JSONObject())))
        val r = post(model, body)
        val cand = r.optJSONArray("candidates")?.optJSONObject(0)
        val parts = cand?.optJSONObject("content")?.optJSONArray("parts") ?: JSONArray()
        val text = (0 until parts.length()).joinToString("") { parts.getJSONObject(it).optString("text") }
        val sources = JSONArray()
        cand?.optJSONObject("groundingMetadata")?.optJSONArray("groundingChunks")?.let { ch ->
            for (i in 0 until minOf(ch.length(), 8)) ch.getJSONObject(i).optJSONObject("web")?.let {
                sources.put(JSONObject().put("title", it.optString("title")).put("url", it.optString("uri"))) }
        }
        return JSONObject().put("summary", text.trim()).put("sources", sources)
    }

    override suspend fun vision(image: ByteArray, mime: String, question: String): String {
        val model = budget.choose(true)
        val body = JSONObject().put("contents", JSONArray().put(JSONObject().put("role", "user").put("parts", JSONArray()
            .put(JSONObject().put("inlineData", JSONObject().put("mimeType", mime).put("data", Base64.encodeToString(image, Base64.NO_WRAP))))
            .put(JSONObject().put("text", question)))))
        val r = post(model, body)
        val parts = r.optJSONArray("candidates")?.optJSONObject(0)?.optJSONObject("content")?.optJSONArray("parts") ?: return ""
        return (0 until parts.length()).joinToString("") { parts.getJSONObject(it).optString("text") }.trim()
    }

    /** Anahtarı denemek için çok küçük bir istek. */
    suspend fun ping(): String {
        val body = JSONObject().put("contents", JSONArray().put(JSONObject().put("role", "user")
            .put("parts", JSONArray().put(JSONObject().put("text", "Sadece 'tamam' yaz.")))))
        val r = post(budget.choose(false), body)
        return r.optJSONArray("candidates")?.optJSONObject(0)?.optJSONObject("content")?.optJSONArray("parts")
            ?.optJSONObject(0)?.optString("text")?.trim() ?: ""
    }
}
