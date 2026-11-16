package dev.yai.app.bridge

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Bitmap
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import dev.yai.app.YaiApp
import dev.yai.app.learn.Sensitive
import kotlinx.coroutines.suspendCancellableCoroutine
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class BridgeError(message: String) : Exception(message)

/**
 * İki görevi var:
 * 1) Ekran kontrolü (sunucudan, kullanıcı onayıyla): ekranı okuma, dokunma, kaydırma, yazma, tuşlar, ekran görüntüsü.
 * 2) Öğrenme modu: SADECE kullanıcının seçtiği uygulamalarda ekran yapısını (buton etiketleri, gezinme) öğrenir.
 * Hassas uygulamalar (banka, şifre, 2FA...) her iki iş için de tamamen yok sayılır.
 */
class YaiAccessibilityService : AccessibilityService() {

    companion object {
        @Volatile var instance: YaiAccessibilityService? = null
            private set
        private const val MAX_LABEL = 30
        /** Tanılama: hizmet gerçekten olay alıyor mu? */
        @Volatile var lastEventAt = 0L
        @Volatile var eventCount = 0
        @Volatile var lastLearned = ""
        @Volatile var lastLearnedAt = 0L
    }

    private val main = Handler(Looper.getMainLooper())
    private var currentActivity = ""
    private var currentPkg = ""
    private var lastScreenId = -1L
    private var lastClickLabel: String? = null
    private val captureRunnable = Runnable { captureForLearning() }

    override fun onServiceConnected() {
        instance = this
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        instance = null
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        instance = null
        super.onDestroy()
    }

    override fun onInterrupt() {}

    // ------------------------------------------------------------------ öğrenme modu
    override fun onAccessibilityEvent(e: AccessibilityEvent) {
        lastEventAt = System.currentTimeMillis(); eventCount++
        val pkg = e.packageName?.toString() ?: return
        if (Sensitive.isSensitive(pkg)) return
        val store = YaiApp.instance.learning
        if (pkg != currentPkg) {
            currentPkg = pkg
            lastScreenId = -1
            lastClickLabel = null
        }
        if (!store.isLearning(pkg)) return
        when (e.eventType) {
            AccessibilityEvent.TYPE_VIEW_CLICKED -> {
                lastClickLabel = e.source?.let { safeLabel(it) }
                    ?: e.contentDescription?.toString()?.takeIf { it.length <= MAX_LABEL }
            }
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                e.className?.toString()?.takeIf { it.contains("Activity") || it.contains("Fragment") }?.let { currentActivity = it }
                scheduleCapture()
            }
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED -> scheduleCapture()
        }
    }

    private fun scheduleCapture() {
        main.removeCallbacks(captureRunnable)
        main.postDelayed(captureRunnable, 700)
    }

    private fun captureForLearning() {
        val root = rootInActiveWindow ?: return
        val pkg = root.packageName?.toString() ?: return
        val store = YaiApp.instance.learning
        if (!store.isLearning(pkg)) return
        val controls = LinkedHashSet<String>()
        var listItems = 0
        var title = ""
        fun walk(n: AccessibilityNodeInfo?, inList: Boolean, depth: Int) {
            if (n == null || depth > 40 || controls.size > 60) return
            val itemOfList = inList || n.collectionItemInfo != null
            if (n.collectionItemInfo != null) listItems++
            when {
                n.isPassword -> {}
                n.isEditable -> n.hintText?.toString()?.takeIf { it.length <= MAX_LABEL }?.let { controls.add("✎ $it") }
                !itemOfList && (n.isClickable || n.isCheckable) -> safeLabel(n)?.let { controls.add(it) }
                !itemOfList && title.isEmpty() && (n.isHeading || n.viewIdResourceName?.contains("title") == true) ->
                    n.text?.toString()?.takeIf { it.length <= 40 }?.let { title = it }
            }
            for (i in 0 until n.childCount) walk(n.getChild(i), itemOfList, depth + 1)
        }
        walk(root, false, 0)
        if (controls.isEmpty()) return
        val id = store.recordScreen(pkg, currentActivity.substringAfterLast('.'), title, controls.toList(), listItems)
        lastLearned = runCatching { packageManager.getApplicationLabel(packageManager.getApplicationInfo(pkg, 0)).toString() }.getOrDefault(pkg) +
            " › " + title.ifBlank { currentActivity.substringAfterLast('.').ifBlank { "ekran" } } + " (${controls.size} buton)"
        lastLearnedAt = System.currentTimeMillis()
        lastClickLabel?.let { if (lastScreenId > 0) store.recordTransition(lastScreenId, it, id) }
        lastClickLabel = null
        lastScreenId = id
    }

    /** Kişisel veri sızdırmayan kısa etiket: açıklama > kısa metin > görünüm id'si. */
    private fun safeLabel(n: AccessibilityNodeInfo): String? {
        if (n.isPassword || n.isEditable) return null
        n.contentDescription?.toString()?.trim()?.takeIf { it.isNotEmpty() && it.length <= MAX_LABEL }?.let { return it }
        n.text?.toString()?.trim()?.takeIf { it.isNotEmpty() && it.length <= MAX_LABEL }?.let { return it }
        n.viewIdResourceName?.substringAfterLast('/')?.let { return "#$it" }
        for (i in 0 until n.childCount) {
            val c = n.getChild(i) ?: continue
            (c.contentDescription ?: c.text)?.toString()?.trim()?.takeIf { it.isNotEmpty() && it.length <= MAX_LABEL }?.let { return it }
        }
        return null
    }

    // ------------------------------------------------------------------ ekran kontrolü
    private fun root(): AccessibilityNodeInfo {
        val r = rootInActiveWindow ?: throw BridgeError("Ekran okunamadı")
        if (Sensitive.isSensitive(r.packageName?.toString())) throw BridgeError("Hassas uygulama açık (banka/şifre). Güvenlik için okunamaz.")
        return r
    }

    @Suppress("DEPRECATION")
    fun uiTree(): JSONObject {
        val r = root()
        val nodes = JSONArray()
        val b = Rect()
        fun walk(n: AccessibilityNodeInfo?, depth: Int) {
            if (n == null || depth > 45 || nodes.length() >= 150) return
            val text = if (n.isPassword) "••••" else n.text?.toString()?.take(120)
            val desc = n.contentDescription?.toString()?.take(80)
            val id = n.viewIdResourceName?.substringAfterLast('/')
            if (n.isVisibleToUser && (!text.isNullOrBlank() || !desc.isNullOrBlank() || n.isClickable || n.isEditable)) {
                n.getBoundsInScreen(b)
                nodes.put(JSONObject().apply {
                    text?.takeIf { it.isNotBlank() }?.let { put("text", it) }
                    desc?.takeIf { it.isNotBlank() }?.let { put("desc", it) }
                    id?.let { put("id", it) }
                    if (n.isClickable) put("click", true)
                    if (n.isEditable) put("input", true)
                    if (n.isChecked) put("checked", true)
                    if (n.isScrollable) put("scroll", true)
                    put("x", b.centerX()); put("y", b.centerY())
                })
            }
            for (i in 0 until n.childCount) walk(n.getChild(i), depth + 1)
        }
        walk(r, 0)
        return JSONObject().put("app", r.packageName).put("nodes", nodes)
    }

    fun clickText(query: String): JSONObject {
        val q = query.lowercase().trim()
        var best: AccessibilityNodeInfo? = null
        fun walk(n: AccessibilityNodeInfo?) {
            if (n == null || best != null) return
            val label = ((n.text ?: "").toString() + " " + (n.contentDescription ?: "").toString()).lowercase()
            if (n.isVisibleToUser && label.contains(q)) best = n
            for (i in 0 until n.childCount) walk(n.getChild(i))
        }
        walk(root())
        var node = best ?: throw BridgeError("Ekranda '$query' bulunamadı")
        var target: AccessibilityNodeInfo? = node
        while (target != null && !target.isClickable) target = target.parent
        if (target != null && target.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return JSONObject().put("clicked", query)
        val b = Rect().also { node.getBoundsInScreen(it) }
        tapBlocking(b.centerX().toFloat(), b.centerY().toFloat())
        return JSONObject().put("tapped", query)
    }

    private fun tapBlocking(x: Float, y: Float) {
        val p = Path().apply { moveTo(x, y) }
        dispatchGesture(GestureDescription.Builder().addStroke(GestureDescription.StrokeDescription(p, 0, 60)).build(), null, null)
    }

    suspend fun gesture(x1: Float, y1: Float, x2: Float, y2: Float, ms: Long) {
        root() // hassas uygulama kontrolü
        val p = Path().apply { moveTo(x1, y1); if (x1 != x2 || y1 != y2) lineTo(x2, y2) }
        val g = GestureDescription.Builder().addStroke(GestureDescription.StrokeDescription(p, 0, ms.coerceIn(30, 3000))).build()
        suspendCancellableCoroutine { cont ->
            val ok = dispatchGesture(g, object : GestureResultCallback() {
                override fun onCompleted(d: GestureDescription?) { if (cont.isActive) cont.resume(Unit) }
                override fun onCancelled(d: GestureDescription?) {
                    if (cont.isActive) cont.resumeWithException(BridgeError("Hareket iptal edildi"))
                }
            }, null)
            if (!ok && cont.isActive) cont.resumeWithException(BridgeError("Hareket gönderilemedi"))
        }
    }

    fun typeText(text: String): JSONObject {
        val focus = root().findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: throw BridgeError("Seçili yazı alanı yok. Önce alana dokun.")
        if (focus.isPassword) throw BridgeError("Şifre alanlarına YAi yazmaz.")
        val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) }
        if (!focus.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) throw BridgeError("Yazı yazılamadı")
        return JSONObject().put("typed", text.length)
    }

    fun key(name: String): JSONObject {
        val ok = when (name) {
            "back" -> performGlobalAction(GLOBAL_ACTION_BACK)
            "home" -> performGlobalAction(GLOBAL_ACTION_HOME)
            "recents" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
            "notifications" -> performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
            "power" -> performGlobalAction(GLOBAL_ACTION_LOCK_SCREEN)
            "enter" -> rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
                ?.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id) ?: false
            else -> throw BridgeError("Bu tuş desteklenmiyor: $name")
        }
        if (!ok) throw BridgeError("Tuşa basılamadı: $name")
        return JSONObject().put("pressed", name)
    }

    suspend fun screenshotPng(): ByteArray {
        root()
        return suspendCancellableCoroutine { cont ->
            takeScreenshot(Display.DEFAULT_DISPLAY, mainExecutor, object : TakeScreenshotCallback {
                override fun onSuccess(s: ScreenshotResult) {
                    try {
                        val hw = Bitmap.wrapHardwareBuffer(s.hardwareBuffer, s.colorSpace)
                            ?: throw BridgeError("Görüntü dönüştürülemedi")
                        val bmp = hw.copy(Bitmap.Config.ARGB_8888, false)
                        s.hardwareBuffer.close()
                        val out = ByteArrayOutputStream()
                        bmp.compress(Bitmap.CompressFormat.PNG, 100, out)
                        cont.resume(out.toByteArray())
                    } catch (e: Exception) {
                        cont.resumeWithException(e)
                    }
                }
                override fun onFailure(code: Int) {
                    cont.resumeWithException(BridgeError("Ekran görüntüsü alınamadı (kod $code)"))
                }
            })
        }
    }
}
