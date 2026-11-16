package dev.yai.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.yai.app.YaiApp
import dev.yai.app.core.Gemini
import dev.yai.app.core.TimeParse
import dev.yai.app.core.WhenError
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class ChatMsg(val fromUser: Boolean, val text: String, val time: Long = System.currentTimeMillis(),
                   val events: List<dev.yai.app.core.ToolEvent> = emptyList())

/** Arayüz durumu. Veriler doğrudan telefondaki YAi'den gelir (sunucu yok). */
class MainViewModel(app: Application) : AndroidViewModel(app) {
    val yai = YaiApp.instance.yai
    val prefs = yai.prefs

    val status = MutableStateFlow<JSONObject?>(null)
    val approvals = MutableStateFlow<List<JSONObject>>(emptyList())
    val schedules = MutableStateFlow<List<JSONObject>>(emptyList())
    val memories = MutableStateFlow<List<JSONObject>>(emptyList())
    val skills = MutableStateFlow<List<JSONObject>>(emptyList())
    val pages = MutableStateFlow<List<JSONObject>>(emptyList())
    val chat = MutableStateFlow<List<ChatMsg>>(emptyList())
    val thinking = MutableStateFlow(false)
    val pendingIds = MutableStateFlow<Set<Long>>(emptySet())
    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()

    init {
        viewModelScope.launch { yai.changes.collect { refreshAll() } }
    }

    fun clearError() { _error.value = null }

    fun refreshAll() {
        val db = yai.db
        status.value = JSONObject().put("bot_name", "YAi").put("key", prefs.hasKey)
            .put("spent_month", yai.budget.month_()).put("spent_today", yai.budget.today())
            .put("monthly_limit", prefs.monthlyLimit.toDouble())
            .put("schedules", db.schedules().size).put("memories", db.memories().size)
        approvals.value = db.pendingApprovals().map { JSONObject().put("id", it.id).put("summary", it.summary) }
        schedules.value = db.schedules().map { JSONObject().put("id", it.id).put("kind", it.kind).put("payload", it.payload)
            .put("when", TimeParse.describe(it.spec)).put("next_run", it.nextRun / 1000.0) }
        memories.value = db.memories().map { JSONObject().put("id", it.id).put("fact", it.fact) }
        skills.value = db.skills().let { s -> (0 until s.length()).map { s.getJSONObject(it) } }
        pages.value = db.pages().map { JSONObject().put("id", it.id).put("title", it.title) }
        chat.value = db.recentMessages(80).filter { !it.text.startsWith("[Sistem]") }.map { m ->
            ChatMsg(m.role == "user", m.text.removePrefix("[Zamanlanmış görev] "), m.ts, m.cards?.let { c ->
                runCatching { org.json.JSONArray(c).let { a -> (0 until a.length()).map { dev.yai.app.core.ToolEvent.fromJson(a.getJSONObject(it)) } } }
                    .getOrDefault(emptyList()) } ?: emptyList())
        }
        pendingIds.value = db.pendingApprovals().map { it.id }.toSet()
    }

    fun send(text: String, image: Pair<ByteArray, String>? = null, onReply: (String) -> Unit = {}) {
        if (text.isBlank() || thinking.value) return
        chat.value = chat.value + ChatMsg(true, text)
        thinking.value = true
        viewModelScope.launch {
            val reply = try {
                withContext(Dispatchers.Default) { yai.agent.handle(text, image).text }
            } catch (e: Exception) { "⚠️ ${e.message}" }
            thinking.value = false
            refreshAll()
            onReply(reply)
        }
    }

    fun decide(id: Int, approve: Boolean) {
        thinking.value = true
        viewModelScope.launch {
            try { withContext(Dispatchers.Default) { yai.agent.resolve(id.toLong(), approve) } }
            catch (e: Exception) { _error.value = e.message }
            thinking.value = false
            refreshAll()
        }
    }

    fun addSchedule(whenText: String, task: String, kind: String, done: (String?) -> Unit) {
        try {
            if (task.isBlank()) throw WhenError("Görev metni boş")
            yai.alarms.add(kind, task.trim(), TimeParse.parse(whenText))
            refreshAll(); done(null)
        } catch (e: Exception) { done(e.message) }
    }

    fun deleteSchedule(id: Int) { yai.alarms.remove(id.toLong()); refreshAll() }
    fun addMemory(fact: String) { yai.db.addMemory(fact); refreshAll() }
    fun deleteMemory(id: Int) { yai.db.deleteMemory(id.toLong()); refreshAll() }
    fun deleteSkill(name: String) { yai.db.deleteSkill(name); refreshAll() }
    fun page(id: Int): JSONObject? = yai.db.page(id.toLong())?.let { JSONObject().put("title", it.title).put("content", it.content) }
    fun clearChat() { yai.db.clearMessages(); refreshAll() }

    /** Anahtarı kaydedip küçük bir istekle dener. */
    suspend fun saveAndTestKey(key: String): String? {
        prefs.apiKey = key
        return try {
            withContext(Dispatchers.IO) { (yai.llm as? Gemini)?.ping() }
            null
        } catch (e: Exception) { e.message ?: "Anahtar denenemedi" }
    }
}
