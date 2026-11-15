package dev.yai.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import dev.yai.app.data.Prefs
import dev.yai.app.learn.LearningStore

class YaiApp : Application() {
    lateinit var prefs: Prefs
        private set
    lateinit var learning: LearningStore
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        prefs = Prefs(this)
        learning = LearningStore(this)
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_SERVICE, "YAi bağlantısı", NotificationManager.IMPORTANCE_MIN).apply {
                description = "YAi'nin sunucuyla bağlantıda kaldığını gösterir"
                setShowBadge(false)
            })
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_MESSAGES, "YAi mesajları", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "YAi'nin sana gönderdiği bildirimler"
            })
    }

    companion object {
        const val CHANNEL_SERVICE = "yai_service"
        const val CHANNEL_MESSAGES = "yai_messages"
        lateinit var instance: YaiApp
            private set
    }
}
