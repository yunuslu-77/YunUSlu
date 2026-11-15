package dev.yai.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.yai.app.YaiApp
import dev.yai.app.data.Api
import dev.yai.app.data.objects
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject

data class ChatMsg(val fromUser: Boolean, val text: String, val time: Long = System.currentTimeMillis())

class MainViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = YaiApp.instance.prefs
    val api = Api { prefs.server }

    val status = MutableStateFlow<JSONObject?>(null)
    val approvals = MutableStateFlow<List<JSONObject>>(emptyList())
    val schedules = MutableStateFlow<List<JSONObject>>(emptyList())
    val memories = MutableStateFlow<List<JSONObject>>(emptyList())
    val agents = MutableStateFlow<List<JSONObject>>(emptyList())
    val skills = MutableStateFlow<List<JSONObject>>(emptyList())
    val pages = MutableStateFlow<List<JSONObject>>(emptyList())
    val settings = MutableStateFlow<JSONObject?>(null)
    val costs = MutableStateFlow<JSONObject?>(null)
    val chat = MutableStateFlow<List<ChatMsg>>(emptyList())
    val thinking = MutableStateFlow(false)
    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()
    val refreshing = MutableStateFlow(false)

    fun clearError() { _error.value = null }

    private fun io(block: suspend () -> Unit) = viewModelScope.launch {
        try { block() } catch (e: Exception) { _error.value = e.message ?: "Hata" }
    }

    fun refreshAll() = io {
        refreshing.value = true
        try {
            status.value = api.status()
            approvals.value = api.approvals().objects()
            schedules.value = api.schedules().objects()
            costs.value = api.costs()
            settings.value = api.settings()
        } finally { refreshing.value = false }
    }

    fun refreshBrain() = io {
        memories.value = api.memories().objects()
        agents.value = api.agents().objects()
        skills.value = api.skills().objects()
        pages.value = api.pages().objects()
    }

    fun loadHistory() = io {
        if (chat.value.isNotEmpty()) return@io
        chat.value = api.history().objects().map { ChatMsg(it.optString("role") == "user", it.optString("text"),
            (it.optDouble("ts", 0.0) * 1000).toLong()) }
    }

    fun send(text: String, onReply: (String) -> Unit = {}) {
        if (text.isBlank() || thinking.value) return
        chat.value = chat.value + ChatMsg(true, text)
        thinking.value = true
        io {
            try {
                val reply = api.chat(text)
                chat.value = chat.value + ChatMsg(false, reply)
                onReply(reply)
                approvals.value = api.approvals().objects()
            } catch (e: Exception) {
                chat.value = chat.value + ChatMsg(false, "⚠️ ${e.message}")
            } finally { thinking.value = false }
        }
    }

    fun decide(id: Int, approve: Boolean) = io {
        approvals.value = approvals.value.filter { it.optInt("id") != id }
        val reply = api.decide(id, approve)
        chat.value = chat.value + ChatMsg(false, reply)
        status.value = api.status()
    }

    fun addSchedule(whenText: String, task: String, kind: String, done: (String?) -> Unit) = viewModelScope.launch {
        try {
            api.addSchedule(whenText, task, kind)
            schedules.value = api.schedules().objects()
            done(null)
        } catch (e: Exception) { done(e.message) }
    }

    fun deleteSchedule(id: Int) = io { api.deleteSchedule(id); schedules.value = api.schedules().objects() }
    fun addMemory(fact: String) = io { api.addMemory(fact); memories.value = api.memories().objects() }
    fun deleteMemory(id: Int) = io { api.deleteMemory(id); memories.value = api.memories().objects() }
    fun setAgent(name: String) = io { api.setAgent(name); agents.value = api.agents().objects() }
    fun deleteSkill(name: String) = io { api.deleteSkill(name); skills.value = api.skills().objects() }
    fun setSetting(key: String, value: Boolean) = io { settings.value = api.setSetting(key, value) }
    suspend fun page(id: Int) = api.page(id)
}
