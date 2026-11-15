package dev.yai.app.bridge

import android.Manifest
import android.app.Notification
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.BatteryManager
import android.util.Base64
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import dev.yai.app.MainActivity
import dev.yai.app.R
import dev.yai.app.YaiApp
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Telefon köprüsü: sunucuya WebSocket ile sürekli bağlı kalır, komutları çalıştırır, olayları (pil, SMS, bildirim) bildirir.
 * Protokol Termux köprüsüyle aynıdır (bkz. bot/phone_gateway.py).
 */
class BridgeService : LifecycleService() {

    enum class State { OFF, CONNECTING, ONLINE, ERROR }

    companion object {
        private val _state = MutableStateFlow(State.OFF)
        val state: StateFlow<State> = _state
        private val _detail = MutableStateFlow("")
        val detail: StateFlow<String> = _detail
        @Volatile private var current: BridgeService? = null

        fun start(ctx: Context, fromBackground: Boolean = false) {
            val i = Intent(ctx, BridgeService::class.java).putExtra("bg", fromBackground)
            ContextCompat.startForegroundService(ctx, i)
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, BridgeService::class.java))
        }

        fun emitEvent(event: String, data: JSONObject) {
            current?.send(JSONObject().put("type", "event").put("event", event).put("data", data))
        }
    }

    private val http = OkHttpClient.Builder().pingInterval(30, TimeUnit.SECONDS).readTimeout(0, TimeUnit.MILLISECONDS).build()
    private var ws: WebSocket? = null
    private var loop: Job? = null
    private lateinit var commands: Commands
    private var notifyApps: List<String> = emptyList()
    private var batteryThreshold = 15
    private var batteryAlerted = false
    @Volatile private var wasOnline = false

    private val batteryReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            val level = i.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) * 100 / i.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
            val charging = i.getIntExtra(BatteryManager.EXTRA_STATUS, -1) == BatteryManager.BATTERY_STATUS_CHARGING
            if (level in 0..batteryThreshold && !charging && !batteryAlerted) {
                batteryAlerted = true
                emitEvent("battery_low", JSONObject().put("percentage", level).put("status", "DISCHARGING"))
            } else if (level > batteryThreshold + 5 || charging) batteryAlerted = false
        }
    }

    override fun onCreate() {
        super.onCreate()
        current = this
        commands = Commands(this)
        registerReceiver(batteryReceiver, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        YaiNotificationListener.onPosted = { n ->
            val pkg = n.optString("packageName")
            if (!n.optBoolean("sensitive") && notifyApps.any { pkg.contains(it) }) {
                n.put("app_label", appLabel(pkg))
                send(JSONObject().put("type", "event").put("event", "notification").put("data", n))
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        val bg = intent?.getBooleanExtra("bg", false) ?: false
        val hasLoc = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val type = ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE or
            (if (hasLoc && !bg) ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION else 0)
        try {
            ServiceCompat.startForeground(this, 1, buildNotification("Bağlanıyor…"), type)
        } catch (e: Exception) {
            ServiceCompat.startForeground(this, 1, buildNotification("Bağlanıyor…"), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        }
        if (loop?.isActive != true) loop = lifecycleScope.launch { connectLoop() }
        return START_STICKY
    }

    override fun onDestroy() {
        current = null
        loop?.cancel()
        ws?.close(1000, "kapatıldı")
        runCatching { unregisterReceiver(batteryReceiver) }
        YaiNotificationListener.onPosted = null
        commands.shutdown()
        _state.value = State.OFF
        super.onDestroy()
    }

    private fun buildNotification(text: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, YaiApp.CHANNEL_SERVICE)
            .setSmallIcon(R.drawable.ic_stat_yai).setContentTitle("YAi").setContentText(text)
            .setOngoing(true).setContentIntent(open).setPriority(NotificationCompat.PRIORITY_MIN)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE).build()
    }

    private fun updateNotification(text: String) {
        val nm = getSystemService(android.app.NotificationManager::class.java)
        nm.notify(1, buildNotification(text))
    }

    private fun setState(s: State, d: String) {
        _state.value = s
        _detail.value = d
        updateNotification(when (s) {
            State.ONLINE -> "Sunucuya bağlı ✓"; State.CONNECTING -> "Bağlanıyor…"
            State.ERROR -> "Bağlantı yok: $d"; State.OFF -> "Kapalı" })
    }

    private suspend fun connectLoop() {
        var backoff = 2_000L
        while (true) {
            val cfg = YaiApp.instance.prefs.server
            if (!cfg.isComplete || cfg.phoneToken.isBlank()) {
                setState(State.ERROR, "Kurulum kodu girilmemiş"); delay(10_000); continue
            }
            setState(State.CONNECTING, cfg.url)
            val closed = kotlinx.coroutines.CompletableDeferred<String>()
            ws = http.newWebSocket(Request.Builder().url(cfg.wsUrl).build(), object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    webSocket.send(JSONObject().put("type", "hello").put("token", cfg.phoneToken)
                        .put("device", YaiApp.instance.prefs.deviceName).toString())
                }
                override fun onMessage(webSocket: WebSocket, text: String) = handle(text)
                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { closed.complete(reason.ifBlank { "kapandı" }) }
                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    closed.complete(t.message ?: "bağlantı hatası")
                }
            })
            wasOnline = false
            val reason = closed.await()
            if (wasOnline) backoff = 2_000
            setState(State.ERROR, reason)
            delay(backoff)
            backoff = (backoff * 2).coerceAtMost(60_000)
        }
    }

    private fun handle(text: String) {
        val msg = runCatching { JSONObject(text) }.getOrNull() ?: return
        when (msg.optString("type")) {
            "config" -> {
                val apps = msg.optJSONArray("notify_apps") ?: JSONArray()
                notifyApps = (0 until apps.length()).map { apps.getString(it) }
                batteryThreshold = msg.optInt("battery_threshold", 15)
                wasOnline = true
                setState(State.ONLINE, "bağlı")
            }
            "error" -> setState(State.ERROR, "Sunucu reddetti: " + msg.optString("error") + " (kurulum kodunu yenile)")
            "cmd" -> lifecycleScope.launch {
                val id = msg.optString("id")
                val out = JSONObject().put("type", "result").put("id", id)
                try {
                    val r = withTimeout(55_000) { commands.execute(msg.optString("action"), msg.optJSONObject("args") ?: JSONObject()) }
                    out.put("ok", true).put("data", r.data)
                    r.file?.let { out.put("file_b64", Base64.encodeToString(it, Base64.NO_WRAP)) }
                } catch (e: Exception) {
                    out.put("ok", false).put("error", e.message ?: e.javaClass.simpleName)
                }
                send(out)
            }
        }
    }

    fun send(obj: JSONObject) {
        ws?.send(obj.toString())
    }

    private fun appLabel(pkg: String): String = runCatching {
        packageManager.getApplicationLabel(packageManager.getApplicationInfo(pkg, 0)).toString()
    }.getOrDefault(pkg)
}
