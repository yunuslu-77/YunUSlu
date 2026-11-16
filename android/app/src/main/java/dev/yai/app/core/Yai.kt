package dev.yai.app.core

import android.content.Context
import dev.yai.app.bridge.Commands
import dev.yai.app.data.Prefs
import dev.yai.app.learn.LearningStore
import kotlinx.coroutines.flow.MutableStateFlow

interface Notifier {
    fun approvalRequested(id: Long, summary: String)
    fun message(title: String, text: String)
}

interface AlarmScheduler {
    fun add(kind: String, payload: String, spec: String): Long
    fun remove(id: Long): Boolean
}

/** Uygulamanın tüm parçalarını birbirine bağlar. */
class Yai(
    val context: Context,
    val prefs: Prefs,
    val db: Db,
    val learning: LearningStore,
    llm: Llm? = null,
    notifier: Notifier? = null,
    alarms: AlarmScheduler? = null,
) {
    val budget = Budget(db, prefs)
    val llm: Llm = llm ?: Gemini({ prefs.apiKey }, budget)
    val commands = Commands(context)
    val notifier: Notifier = notifier ?: AndroidNotifier(context)
    val alarms: AlarmScheduler = alarms ?: Alarms(context, db)
    val agent = Agent(this)
    /** Arayüzün yenilenmesi için sayaç (onay, görev, mesaj değişince artar). */
    val changes = MutableStateFlow(0)
    fun changed() { changes.value++ }
}
