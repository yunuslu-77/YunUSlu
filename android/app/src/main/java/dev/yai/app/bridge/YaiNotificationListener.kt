package dev.yai.app.bridge

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import dev.yai.app.learn.Sensitive
import org.json.JSONArray
import org.json.JSONObject

/** Bildirimleri okur; sunucunun seçtiği uygulamalardan gelenleri köprü üzerinden iletir. */
class YaiNotificationListener : NotificationListenerService() {
    companion object {
        @Volatile var instance: YaiNotificationListener? = null
            private set
        var onPosted: ((JSONObject) -> Unit)? = null

        fun toJson(sbn: StatusBarNotification): JSONObject {
            val ex = sbn.notification.extras
            return JSONObject().put("packageName", sbn.packageName).put("id", sbn.id).put("when", sbn.postTime)
                .put("title", ex.getCharSequence("android.title")?.toString() ?: "")
                .put("content", (ex.getCharSequence("android.bigText") ?: ex.getCharSequence("android.text"))?.toString() ?: "")
        }
    }

    override fun onListenerConnected() { instance = this }
    override fun onListenerDisconnected() { instance = null }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName == packageName || sbn.isOngoing) return
        onPosted?.invoke(toJson(sbn).put("sensitive", Sensitive.isSensitive(sbn.packageName)))
    }

    fun list(): JSONArray = JSONArray().apply {
        activeNotifications?.filter { !it.isOngoing && it.packageName != packageName }?.forEach { put(toJson(it)) }
    }
}
