package dev.yai.app.bridge

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.camera2.CameraManager
import android.location.LocationManager
import android.media.AudioManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.VibrationEffect
import android.os.VibratorManager
import android.provider.AlarmClock
import android.provider.CallLog
import android.provider.ContactsContract
import android.provider.Telephony
import android.speech.tts.TextToSpeech
import android.telephony.SmsManager
import androidx.core.content.ContextCompat
import dev.yai.app.YaiApp
import dev.yai.app.learn.Sensitive
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale
import kotlin.coroutines.resume

/**
 * Sunucudan gelen komutları telefonda çalıştırır. Komut adları Termux köprüsüyle aynıdır
 * (adb_* komutları burada erişilebilirlik hizmetiyle yapılır, ADB gerekmez).
 * Sadece buradaki komutlar çalışır; bilinmeyen komut reddedilir.
 */
class Commands(private val ctx: Context) {

    private var tts: TextToSpeech? = null

    data class Result(val data: Any, val file: ByteArray? = null)

    private fun need(perm: String) {
        if (ContextCompat.checkSelfPermission(ctx, perm) != PackageManager.PERMISSION_GRANTED)
            throw BridgeError("İzin yok: ${perm.substringAfterLast('.')}. YAi uygulamasında İzinler ekranından ver.")
    }

    private fun a11y() = YaiAccessibilityService.instance
        ?: throw BridgeError("Erişilebilirlik hizmeti kapalı. YAi → İzinler → 'Ekran kontrolü'nü aç.")

    private fun startActivity(i: Intent) {
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        // Arka plandan etkinlik başlatma: erişilebilirlik hizmeti varsa onun üzerinden başlat (Android izin veriyor)
        val svc = YaiAccessibilityService.instance
        if (svc != null) svc.startActivity(i) else ctx.startActivity(i)
    }

    suspend fun execute(action: String, a: JSONObject): Result = when (action) {
        "battery" -> Result(battery())
        "wifi" -> Result(wifi())
        "notifications" -> Result(YaiNotificationListener.instance?.list()
            ?: throw BridgeError("Bildirim erişimi kapalı. YAi → İzinler → 'Bildirim erişimi'ni aç."))
        "sms_list" -> Result(smsList(a.optInt("limit", 10)))
        "sms_send" -> Result(smsSend(a.getString("number"), a.getString("text")))
        "call" -> { need(Manifest.permission.CALL_PHONE)
            startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:" + Uri.encode(a.getString("number")))))
            Result(JSONObject().put("calling", a.getString("number"))) }
        "call_log" -> Result(callLog(a.optInt("limit", 10)))
        "contacts" -> Result(contacts())
        "location" -> Result(location())
        "photo" -> photo(a.optString("camera") == "front")
        "clipboard_get" -> Result(clipboardGet())
        "clipboard_set" -> Result(withContext(Dispatchers.Main) {
            val cm = ctx.getSystemService(android.content.ClipboardManager::class.java)
            cm.setPrimaryClip(android.content.ClipData.newPlainText("YAi", a.getString("text")))
            JSONObject().put("ok", true)
        })
        "torch" -> Result(torch(a.optBoolean("on")))
        "volume" -> Result(volume(a.optString("stream", "music"), a.optInt("level", 7)))
        "speak" -> Result(speak(a.getString("text")))
        "vibrate" -> Result(vibrate(a.optLong("ms", 1000)))
        "open_url" -> Result(openUrl(a.getString("url")))
        "list_apps" -> Result(listApps())
        "open_app" -> Result(openApp(a.getString("package")))
        "alarm" -> { startActivity(Intent(AlarmClock.ACTION_SET_ALARM)
                .putExtra(AlarmClock.EXTRA_HOUR, a.getInt("hour")).putExtra(AlarmClock.EXTRA_MINUTES, a.getInt("minute"))
                .putExtra(AlarmClock.EXTRA_MESSAGE, a.optString("label", "YAi")).putExtra(AlarmClock.EXTRA_SKIP_UI, true))
            Result(JSONObject().put("alarm", String.format(Locale.ROOT, "%02d:%02d", a.getInt("hour"), a.getInt("minute")))) }
        "timer" -> { startActivity(Intent(AlarmClock.ACTION_SET_TIMER)
                .putExtra(AlarmClock.EXTRA_LENGTH, a.getInt("seconds")).putExtra(AlarmClock.EXTRA_MESSAGE, a.optString("label", "YAi"))
                .putExtra(AlarmClock.EXTRA_SKIP_UI, true))
            Result(JSONObject().put("timer_seconds", a.getInt("seconds"))) }
        "notify" -> Result(notifyUser(a.getString("title"), a.getString("content")))
        "tasker" -> { ctx.sendBroadcast(Intent("yai.TASKER").putExtra("task", a.getString("task")).putExtra("par", a.optString("param")))
            Result(JSONObject().put("sent_to_tasker", a.getString("task"))) }
        // ---------- ekran kontrolü (erişilebilirlik) ----------
        "adb_status" -> Result(JSONObject().put("adb", if (YaiAccessibilityService.instance != null) "hazır" else "hazır değil")
            .put("mode", "accessibility"))
        "adb_screenshot" -> Result(JSONObject().put("ok", true), a11y().screenshotPng())
        "adb_tap" -> { a11y().gesture(a.getDouble("x").toFloat(), a.getDouble("y").toFloat(), a.getDouble("x").toFloat(), a.getDouble("y").toFloat(), 60)
            Result(JSONObject().put("tapped", JSONArray().put(a.getInt("x")).put(a.getInt("y")))) }
        "adb_swipe" -> { a11y().gesture(a.getDouble("x1").toFloat(), a.getDouble("y1").toFloat(), a.getDouble("x2").toFloat(),
                a.getDouble("y2").toFloat(), a.optLong("ms", 300))
            Result(JSONObject().put("swiped", true)) }
        "adb_text" -> Result(withContext(Dispatchers.Main) { a11y().typeText(a.getString("text")) })
        "adb_key" -> Result(withContext(Dispatchers.Main) { a11y().key(a.getString("key")) })
        "ui_tree" -> Result(withContext(Dispatchers.Main) { a11y().uiTree() })
        "click_text" -> Result(withContext(Dispatchers.Main) { a11y().clickText(a.getString("text")) })
        // ---------- öğrenme modu ----------
        "learned_apps" -> Result(YaiApp.instance.learning.learnedAppsJson())
        "app_guide" -> Result(YaiApp.instance.learning.guideJson(a.getString("package")))
        else -> throw BridgeError("İzin verilmeyen komut: $action")
    }

    // ------------------------------------------------------------------ uygulamalar
    private fun battery(): JSONObject {
        val bm = ctx.getSystemService(BatteryManager::class.java)
        val st = ctx.registerReceiver(null, android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val status = st?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        return JSONObject().put("percentage", bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY))
            .put("status", when (status) {
                BatteryManager.BATTERY_STATUS_CHARGING -> "CHARGING"; BatteryManager.BATTERY_STATUS_FULL -> "FULL"
                else -> "DISCHARGING" })
            .put("temperature", (st?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0) / 10.0)
    }

    @Suppress("DEPRECATION")
    private fun wifi(): JSONObject {
        val wm = ctx.applicationContext.getSystemService(WifiManager::class.java)
        val info = wm.connectionInfo
        return JSONObject().put("enabled", wm.isWifiEnabled).put("rssi", info?.rssi ?: 0)
            .put("ssid", info?.ssid?.trim('"') ?: "")
    }

    private fun smsList(limit: Int): JSONArray {
        need(Manifest.permission.READ_SMS)
        val out = JSONArray()
        ctx.contentResolver.query(Telephony.Sms.Inbox.CONTENT_URI,
            arrayOf(Telephony.Sms._ID, Telephony.Sms.ADDRESS, Telephony.Sms.BODY, Telephony.Sms.DATE, Telephony.Sms.READ),
            null, null, Telephony.Sms.DEFAULT_SORT_ORDER)?.use { c ->
            while (c.moveToNext() && out.length() < limit.coerceIn(1, 100)) {
                out.put(JSONObject().put("_id", c.getLong(0)).put("number", c.getString(1)).put("sender", c.getString(1))
                    .put("body", c.getString(2)).put("received", c.getLong(3)).put("read", c.getInt(4) == 1))
            }
        }
        return out
    }

    private fun smsSend(number: String, text: String): JSONObject {
        need(Manifest.permission.SEND_SMS)
        val sms = ctx.getSystemService(SmsManager::class.java)
        sms.sendMultipartTextMessage(number, null, sms.divideMessage(text), null, null)
        return JSONObject().put("sent", true)
    }

    private fun callLog(limit: Int): JSONArray {
        need(Manifest.permission.READ_CALL_LOG)
        val out = JSONArray()
        ctx.contentResolver.query(CallLog.Calls.CONTENT_URI,
            arrayOf(CallLog.Calls.NUMBER, CallLog.Calls.CACHED_NAME, CallLog.Calls.TYPE, CallLog.Calls.DATE, CallLog.Calls.DURATION),
            null, null, CallLog.Calls.DEFAULT_SORT_ORDER)?.use { c ->
            while (c.moveToNext() && out.length() < limit.coerceIn(1, 100)) {
                out.put(JSONObject().put("number", c.getString(0)).put("name", c.getString(1) ?: "")
                    .put("type", when (c.getInt(2)) { CallLog.Calls.INCOMING_TYPE -> "gelen"; CallLog.Calls.OUTGOING_TYPE -> "giden"
                        CallLog.Calls.MISSED_TYPE -> "cevapsız"; else -> "diğer" })
                    .put("date", c.getLong(3)).put("duration", c.getInt(4)))
            }
        }
        return out
    }

    private fun contacts(): JSONArray {
        need(Manifest.permission.READ_CONTACTS)
        val out = JSONArray()
        ctx.contentResolver.query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.NUMBER),
            null, null, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " ASC")?.use { c ->
            while (c.moveToNext() && out.length() < 3000) out.put(JSONObject().put("name", c.getString(0)).put("number", c.getString(1)))
        }
        return out
    }

    @SuppressLint("MissingPermission")
    private suspend fun location(): JSONObject {
        need(Manifest.permission.ACCESS_FINE_LOCATION)
        val lm = ctx.getSystemService(LocationManager::class.java)
        val provider = listOf(LocationManager.FUSED_PROVIDER, LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .firstOrNull { lm.isProviderEnabled(it) } ?: throw BridgeError("Konum kapalı")
        val loc = withTimeout(45_000) {
            suspendCancellableCoroutine { cont ->
                lm.getCurrentLocation(provider, null, ctx.mainExecutor) { l -> if (cont.isActive) cont.resume(l) }
            }
        } ?: lm.getLastKnownLocation(provider) ?: throw BridgeError("Konum alınamadı")
        return JSONObject().put("latitude", loc.latitude).put("longitude", loc.longitude).put("accuracy", loc.accuracy)
            .put("provider", provider)
    }

    private suspend fun photo(front: Boolean): Result {
        need(Manifest.permission.CAMERA)
        val d = CompletableDeferred<ByteArray>()
        CaptureActivity.pending = d
        startActivity(Intent(ctx, CaptureActivity::class.java).putExtra(CaptureActivity.EXTRA_FRONT, front))
        val bytes = withTimeout(40_000) { d.await() }
        return Result(JSONObject().put("bytes", bytes.size), bytes)
    }

    private suspend fun clipboardGet(): JSONObject = withContext(Dispatchers.Main) {
        val cm = ctx.getSystemService(android.content.ClipboardManager::class.java)
        val text = cm.primaryClip?.getItemAt(0)?.coerceToText(ctx)?.toString()
            ?: throw BridgeError("Android, arka planda panoyu okumaya izin vermiyor. YAi uygulamasını açıp tekrar dene.")
        JSONObject().put("text", text)
    }

    private fun torch(on: Boolean): JSONObject {
        val cm = ctx.getSystemService(CameraManager::class.java)
        val id = cm.cameraIdList.firstOrNull() ?: throw BridgeError("Fener yok")
        cm.setTorchMode(id, on)
        return JSONObject().put("torch", on)
    }

    private fun volume(stream: String, level: Int): JSONObject {
        val am = ctx.getSystemService(AudioManager::class.java)
        val s = when (stream) {
            "ring" -> AudioManager.STREAM_RING; "alarm" -> AudioManager.STREAM_ALARM
            "notification" -> AudioManager.STREAM_NOTIFICATION; "call" -> AudioManager.STREAM_VOICE_CALL
            "system" -> AudioManager.STREAM_SYSTEM; else -> AudioManager.STREAM_MUSIC
        }
        val max = am.getStreamMaxVolume(s)
        val v = (level.coerceIn(0, 15) * max / 15.0).toInt()
        am.setStreamVolume(s, v, 0)
        return JSONObject().put("stream", stream).put("level", v).put("max", max)
    }

    private suspend fun speak(text: String): JSONObject = withContext(Dispatchers.Main) {
        val engine = tts ?: suspendCancellableCoroutine { cont ->
            var t: TextToSpeech? = null
            t = TextToSpeech(ctx) { st -> if (cont.isActive) cont.resume(if (st == TextToSpeech.SUCCESS) t else null) }
        }?.also { it.language = Locale.forLanguageTag("tr-TR"); tts = it } ?: throw BridgeError("Seslendirme motoru yok")
        engine.speak(text, TextToSpeech.QUEUE_ADD, null, "yai-" + System.nanoTime())
        JSONObject().put("spoken", true)
    }

    private fun vibrate(ms: Long): JSONObject {
        val vm = ctx.getSystemService(VibratorManager::class.java)
        vm.defaultVibrator.vibrate(VibrationEffect.createOneShot(ms.coerceIn(100, 5000), VibrationEffect.DEFAULT_AMPLITUDE))
        return JSONObject().put("ok", true)
    }

    private fun openUrl(url: String): JSONObject {
        val scheme = url.substringBefore(':').lowercase()
        if (scheme !in setOf("http", "https", "geo", "tel", "mailto", "market", "whatsapp", "intent", "spotify", "youtube"))
            throw BridgeError("Bu tür bağlantı açılamaz")
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        return JSONObject().put("opened", url)
    }

    private fun listApps(): JSONArray {
        val pm = ctx.packageManager
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return JSONArray().apply {
            pm.queryIntentActivities(launcher, 0).map { it.activityInfo.packageName to it.loadLabel(pm).toString() }
                .distinctBy { it.first }.sortedBy { it.second.lowercase() }
                .forEach { (p, l) -> put("$l ($p)") }
        }
    }

    private fun openApp(pkg: String): JSONObject {
        if (Sensitive.isSensitive(pkg)) throw BridgeError("Hassas uygulamaları YAi açmaz (banka/şifre). Kendin açmalısın.")
        val i = ctx.packageManager.getLaunchIntentForPackage(pkg) ?: throw BridgeError("Uygulama bulunamadı: $pkg")
        startActivity(i)
        return JSONObject().put("opened", pkg)
    }

    private fun notifyUser(title: String, content: String): JSONObject {
        val n = androidx.core.app.NotificationCompat.Builder(ctx, YaiApp.CHANNEL_MESSAGES)
            .setSmallIcon(dev.yai.app.R.drawable.ic_stat_yai).setContentTitle(title).setContentText(content)
            .setStyle(androidx.core.app.NotificationCompat.BigTextStyle().bigText(content)).setAutoCancel(true).build()
        if (Build.VERSION.SDK_INT < 33 || ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED) {
            androidx.core.app.NotificationManagerCompat.from(ctx).notify((System.currentTimeMillis() % 100000).toInt(), n)
        }
        return JSONObject().put("ok", true)
    }

    fun shutdown() { tts?.shutdown(); tts = null }
}
