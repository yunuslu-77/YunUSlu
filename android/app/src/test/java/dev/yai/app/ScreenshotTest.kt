package dev.yai.app

import android.graphics.Bitmap
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import dev.yai.app.ui.ChatMsg
import dev.yai.app.ui.MainViewModel
import dev.yai.app.ui.screens.BrainScreen
import dev.yai.app.ui.screens.ChatScreen
import dev.yai.app.ui.screens.HomeScreen
import dev.yai.app.ui.screens.LearnScreen
import dev.yai.app.ui.screens.SettingsScreen
import dev.yai.app.ui.screens.TasksScreen
import dev.yai.app.ui.screens.WelcomeScreen
import dev.yai.app.ui.theme.YaiTheme
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** Ekranların görüntüsünü app/build/screens/ klasörüne kaydeder (görsel kontrol için). */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w400dp-h860dp-xhdpi")
class ScreenshotTest {
    @get:Rule val rule = createComposeRule()

    private fun vm(): MainViewModel {
        val vm = MainViewModel(ApplicationProvider.getApplicationContext())
        vm.status.value = JSONObject("""{"bot_name":"YAi","key":true,"spent_today":0.042,"spent_month":2.37,
            "monthly_limit":9,"schedules":3,"memories":12}""")
        vm.approvals.value = listOf(JSONObject("""{"id":7,"summary":"📧 E-posta gönder\nKime: ali@ornek.com\nKonu: Yarınki toplantı"}"""))
        vm.schedules.value = listOf(
            JSONObject("""{"id":1,"kind":"prompt","payload":"Sabah brifingi hazırla","when":"tekrar: hafta içi 08:00","next_run":1763445600}"""),
            JSONObject("""{"id":2,"kind":"message","payload":"Faturayı öde","when":"bir kez: 20.11.2026 09:00","next_run":1763618400}"""),
            JSONObject("""{"id":3,"kind":"prompt","payload":"Haftalık harcama özetini çıkar","when":"tekrar: pazartesi 09:00","next_run":1763964000}"""))
        vm.memories.value = listOf(JSONObject("""{"id":1,"fact":"İzmir'de yaşıyor"}"""), JSONObject("""{"id":2,"fact":"Kahveyi şekersiz içer"}"""))
        val ev = { n: String, a: String, r: String -> dev.yai.app.core.ToolEvent(n, JSONObject(a), r, true) }
        vm.chat.value = listOf(ChatMsg(true, "Yarın 7:30'a alarm kur, İzmir'de hava nasıl?"),
            ChatMsg(false, "Alarmın hazır, yarın **güneşli** görünüyor ☀️", events = listOf(
                ev("phone_set_alarm", """{"hour":7,"minute":30,"label":"Uyan"}""", """{"alarm":"07:30"}"""),
                ev("get_weather", "{}", """{"yer":"İzmir","şimdi":{"sıcaklık":18.4,"hissedilen":17,"durum":"açık"},"tahmin":[
                    {"durum":"açık","max":21,"min":12,"yağış_%":0},{"durum":"parçalı bulutlu","max":19,"min":11,"yağış_%":10},
                    {"durum":"hafif yağmur","max":16,"min":10,"yağış_%":70}]}"""))),
            ChatMsg(true, "Anneme 'geliyorum' yaz ve 2500 TL'nin %18 KDV'li hali?"),
            ChatMsg(false, "Hesap:\n- KDV oranı: **%18**\n- Toplam: `2500 × 1.18`\n\n| Kalem | Tutar |\n|---|---|\n| Net | 2500 ₺ |\n| KDV | 450 ₺ |", events = listOf(
                ev("phone_sms_send", """{"number":"Anne","text":"Geliyorum"}""", """{"status":"onay_bekleniyor","approval_id":7}"""),
                ev("calculate", "{}", """{"expression":"2500*1.18","result":"2950","label":"KDV dahil fiyat"}"""))))
        vm.pendingIds.value = setOf(7L)
        return vm
    }

    private fun shot(name: String, content: @Composable () -> Unit) {
        rule.setContent { YaiTheme(dark = name.endsWith("_dark")) {
            Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) { content() } } }
        rule.waitForIdle()
        val bmp = rule.onRoot().captureToImage().asAndroidBitmap()
        val dir = File("build/screens").apply { mkdirs() }
        File(dir, "$name.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    @Test fun welcome() = shot("01_welcome") { WelcomeScreen({ null }) {} }
    @Test fun home() { val v = vm(); shot("02_home") { HomeScreen(v, {}, {}) } }
    @Test fun homeDark() { val v = vm(); shot("02_home_dark") { HomeScreen(v, {}, {}) } }
    @Test fun chat() { val v = vm(); shot("03_chat") { ChatScreen(v, null) {} } }
    @Test fun chatDark() { val v = vm(); shot("03_chat_dark") { ChatScreen(v, null) {} } }
    @Test fun settingsDark() { val v = vm(); shot("07_settings_dark") { SettingsScreen(v) {} } }
    @Test fun tasks() { val v = vm(); shot("04_tasks") { TasksScreen(v) } }
    @Test fun learn() = shot("05_learn") { LearnScreen() }
    @Test fun brain() { val v = vm(); shot("06_brain") { BrainScreen(v) } }
    @Test fun settings() { val v = vm(); shot("07_settings") { SettingsScreen(v) {} } }

    @Test fun sensitiveApps() {
        val s = dev.yai.app.learn.Sensitive
        assert(s.isSensitive("com.akbank.android.apps.akbank_direkt"))
        assert(s.isSensitive("com.x8bit.bitwarden"))
        assert(s.isSensitive("tr.gov.turkiye.edevlet.kapisi"))
        assert(!s.isSensitive("com.whatsapp"))
        assert(!s.isSensitive("com.spotify.music"))
    }

    @Test fun learningStoreSkipsSensitive() {
        val store = YaiApp.instance.learning
        store.setEnabled("com.akbank.android", "Akbank", true)
        store.setEnabled("com.whatsapp", "WhatsApp", true)
        assert(!store.isLearning("com.akbank.android"))
        assert(store.isLearning("com.whatsapp"))
        val a = store.recordScreen("com.whatsapp", "HomeActivity", "Sohbetler", listOf("Ara", "Yeni sohbet", "Kamera"), 12)
        val b = store.recordScreen("com.whatsapp", "SearchActivity", "", listOf("Geri", "✎ Ara…"), 0)
        store.recordTransition(a, "Ara", b)
        val guide = store.guideJson("com.whatsapp")
        assertEquals(2, guide.getJSONArray("screens").length())
        assertEquals("Ara", guide.getJSONArray("navigation").getJSONObject(0).getString("tap"))
        assertEquals(1, store.learnedAppsJson().length())
        @Suppress("UNUSED_VARIABLE") val unused = JSONArray()
    }
}
