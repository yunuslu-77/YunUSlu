package dev.yai.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import dev.yai.app.core.Db
import dev.yai.app.core.Yai
import dev.yai.app.data.Prefs
import dev.yai.app.learn.LearningStore

class YaiApp : Application() {
    lateinit var prefs: Prefs
        private set
    lateinit var learning: LearningStore
        private set
    lateinit var yai: Yai
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        prefs = Prefs(this)
        learning = LearningStore(this)
        yai = Yai(this, prefs, Db(this), learning)
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL_SERVICE, "YAi çalışıyor", NotificationManager.IMPORTANCE_MIN).apply {
            description = "YAi arka planda bir görevi yaparken görünür"; setShowBadge(false) })
        nm.createNotificationChannel(NotificationChannel(CHANNEL_MESSAGES, "YAi mesajları", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Hatırlatmalar, görev sonuçları ve onay istekleri" })
    }

    companion object {
        const val CHANNEL_SERVICE = "yai_service"
        const val CHANNEL_MESSAGES = "yai_messages"
        lateinit var instance: YaiApp
            private set
    }
}
