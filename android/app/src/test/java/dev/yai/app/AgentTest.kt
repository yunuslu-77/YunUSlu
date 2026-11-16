package dev.yai.app

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import dev.yai.app.core.AlarmScheduler
import dev.yai.app.core.Budget
import dev.yai.app.core.Db
import dev.yai.app.core.Gemini
import dev.yai.app.core.Llm
import dev.yai.app.core.LlmResult
import dev.yai.app.core.Notifier
import dev.yai.app.core.TimeParse
import dev.yai.app.core.ToolCall
import dev.yai.app.core.WhenError
import dev.yai.app.core.Yai
import dev.yai.app.data.Prefs
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

class FakeLlm : Llm {
    val script = ArrayDeque<Any>()          // String = metin cevap, List<Pair<String, JSONObject>> = araç çağrıları
    val requests = mutableListOf<JSONArray>()
    var systems = mutableListOf<String>()
    var toolCount = 0
    override suspend fun generate(smart: Boolean, system: String, contents: JSONArray, tools: JSONArray?): LlmResult {
        requests.add(JSONArray(contents.toString())); systems.add(system); toolCount = tools?.length() ?: 0
        val item = script.removeFirstOrNull() ?: "tamam"
        if (item is String) return LlmResult(item, emptyList(), JSONObject().put("role", "model").put("parts", JSONArray().put(JSONObject().put("text", item))))
        @Suppress("UNCHECKED_CAST") val calls = (item as List<Pair<String, JSONObject>>).map { ToolCall(it.first, it.second) }
        val parts = JSONArray().apply { calls.forEach { put(JSONObject().put("functionCall", JSONObject().put("name", it.name).put("args", it.args))) } }
        return LlmResult("", calls, JSONObject().put("role", "model").put("parts", parts))
    }
    override suspend fun search(query: String) = JSONObject().put("summary", "özet: $query")
    override suspend fun vision(image: ByteArray, mime: String, question: String) = "görüntü"
}

class FakeNotifier : Notifier {
    val approvals = mutableListOf<Pair<Long, String>>(); val messages = mutableListOf<String>()
    override fun approvalRequested(id: Long, summary: String) { approvals.add(id to summary) }
    override fun message(title: String, text: String) { messages.add(text) }
}

class FakeAlarms(private val db: Db) : AlarmScheduler {
    override fun add(kind: String, payload: String, spec: String) = db.addSchedule(kind, payload, spec, TimeParse.next(spec)!!)
    override fun remove(id: Long) = db.deleteSchedule(id)
}

@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class AgentTest {
    private lateinit var yai: Yai
    private lateinit var llm: FakeLlm
    private lateinit var notifier: FakeNotifier

    @Before fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<android.app.Application>()
        val db = Db(ctx, null)  // bellek içi
        llm = FakeLlm(); notifier = FakeNotifier()
        val prefs = Prefs(ctx).apply { apiKey = "AIza-test-anahtari-0123456789"; monthlyLimit = 9f; dailyLimit = 0.4f }
        yai = Yai(ctx, prefs, db, YaiApp.instance.learning, llm, notifier, FakeAlarms(db))
    }

    @Test fun simpleReplyAndHistory() = runTest {
        llm.script.add("Merhaba! 👋")
        assertEquals("Merhaba! 👋", yai.agent.handleUser("selam"))
        llm.script.add("İyiyim")
        yai.agent.handleUser("nasılsın")
        assertEquals(3, llm.requests.last().length())   // önceki 2 mesaj + yeni
        assertTrue("YAi" in llm.systems.last() && "ŞU AN" in llm.systems.last())
        assertTrue(llm.toolCount > 40)
    }

    @Test fun toolLoopRemembers() = runTest {
        llm.script.add(listOf("remember" to JSONObject().put("fact", "İzmir'de yaşıyor"), "get_datetime" to JSONObject()))
        llm.script.add("Kaydettim")
        assertEquals("Kaydettim", yai.agent.handleUser("İzmir'de yaşıyorum"))
        assertEquals("İzmir'de yaşıyor", yai.db.memories().single().fact)
        val last = llm.requests.last()
        val resp = last.getJSONObject(last.length() - 1).getJSONArray("parts")
        assertEquals("remember", resp.getJSONObject(0).getJSONObject("functionResponse").getString("name"))
        assertTrue(last.getJSONObject(last.length() - 2).getJSONArray("parts").getJSONObject(0).has("functionCall"))
        llm.script.add("ok"); yai.agent.handleUser("x")
        assertTrue("İzmir" in llm.systems.last())
    }

    @Test fun approvalFlow() = runTest {
        val args = JSONObject().put("number", "+905551112233").put("text", "Geliyorum")
        llm.script.add(listOf("phone_sms_send" to args)); llm.script.add("Onay bekliyorum")
        yai.agent.handleUser("anneme geliyorum yaz")
        assertEquals(1, notifier.approvals.size)
        assertTrue("Geliyorum" in notifier.approvals[0].second)
        val id = notifier.approvals[0].first
        // aynı istek tekrar gelirse yeni onay açılmaz
        llm.script.add(listOf("phone_sms_send" to args)); llm.script.add("bekliyorum")
        yai.agent.handleUser("tekrar")
        assertEquals(1, yai.db.pendingApprovals().size)
        llm.script.add("✅ Gönderildi")
        assertEquals("✅ Gönderildi", yai.agent.resolveApproval(id, true))
        assertTrue("ONAYLADI" in llm.requests.last().let { it.getJSONObject(it.length() - 1).toString() })
        assertTrue("zaten" in yai.agent.resolveApproval(id, true))
        assertEquals(0, yai.db.pendingApprovals().size)
    }

    @Test fun approvalDenied() = runTest {
        llm.script.add(listOf("phone_call" to JSONObject().put("number", "112"))); llm.script.add("bekliyorum")
        yai.agent.handleUser("ara")
        assertTrue("İptal" in yai.agent.resolveApproval(notifier.approvals[0].first, false))
    }

    @Test fun scheduleTool() = runTest {
        llm.script.add(listOf("create_schedule" to JSONObject().put("when", "hafta içi 08:00").put("task", "Sabah brifingi")))
        llm.script.add("Kurdum")
        yai.agent.handleUser("her hafta içi 8'de brifing ver")
        val s = yai.db.schedules().single()
        assertEquals("daily:08:00:1,2,3,4,5", s.spec)
        assertEquals("Sabah brifingi", s.payload)
        // geçersiz zaman hatası modele döner
        llm.script.add(listOf("set_reminder" to JSONObject().put("when", "bilmem").put("message", "x"))); llm.script.add("hata")
        yai.agent.handleUser("x")
        assertTrue("error" in llm.requests.last().toString())
    }

    @Test fun unknownToolAndBudget() = runTest {
        llm.script.add(listOf("yok_boyle" to JSONObject())); llm.script.add("tamam")
        yai.agent.handleUser("x")
        assertTrue("Bilinmeyen araç" in llm.requests.last().toString())
        val real = Gemini({ yai.prefs.apiKey }, Budget(yai.db, yai.prefs))
        yai.db.addUsage(LocalDate.now().toString(), LocalDate.now().toString().take(7), "x", 0, 0, 100.0)
        val y2 = Yai(yai.context, yai.prefs, yai.db, yai.learning, real, notifier, FakeAlarms(yai.db))
        assertTrue("bütçe" in y2.agent.handleUser("x").lowercase())
    }

    @Test fun nudgesWhenClaimingWithoutTool() = runTest {
        llm.script.add("Feneri açtım! 🔦")                                  // araç çağırmadan "açtım"
        llm.script.add(listOf("calculate" to JSONObject().put("expression", "2+2")))
        llm.script.add("Tamam")
        val r = yai.agent.handle("feneri aç")
        assertEquals("Tamam", r.text)
        assertTrue("Hiçbir araç çağırmadın" in llm.requests[1].toString())
        assertEquals("calculate", r.events.single().name)
        // kartlar geçmişe kaydedilir
        assertTrue(yai.db.recentMessages(5).last().cards!!.contains("calculate"))
    }

    @Test fun calculator() {
        val c = dev.yai.app.core.Calc
        assertEquals("2950", c.format(c.eval("2500*1.18")))
        assertEquals("18.4210526316", c.format(c.eval("(450-380)/380*100")))
        assertEquals("0.15", c.format(c.eval("15%")))
        assertEquals("1024", c.format(c.eval("2^10")))
        assertEquals("12", c.format(c.eval("sqrt(144)")))
        assertEquals("7", c.format(c.eval("3 + 4")))
        try { c.eval("5/0"); throw AssertionError() } catch (_: ArithmeticException) {}
    }

    @Test fun timeParse() {
        val z = ZoneId.of("Europe/Istanbul")
        val now = ZonedDateTime.of(LocalDate.of(2026, 11, 15), LocalTime.of(10, 0), z)  // Pazar
        assertEquals("daily:08:00:", TimeParse.parse("08:00", now))
        assertEquals("daily:08:30:1,2,3,4,5", TimeParse.parse("hafta içi 08:30", now))
        assertEquals("daily:07:15:1,3,5", TimeParse.parse("pzt,çar,cum 07:15", now))
        assertEquals("daily:18:00:5", TimeParse.parse("cumaları 18:00", now))
        assertEquals("once:" + now.plusMinutes(30).toInstant().toEpochMilli(), TimeParse.parse("+30dk", now))
        assertEquals("once:" + now.plusHours(2).toInstant().toEpochMilli(), TimeParse.parse("2 saat sonra", now))
        assertEquals("once:" + ZonedDateTime.of(LocalDate.of(2026, 11, 16), LocalTime.of(9, 0), z).toInstant().toEpochMilli(),
            TimeParse.parse("yarın 09:00", now))
        assertEquals("once:" + ZonedDateTime.of(LocalDate.of(2026, 12, 1), LocalTime.of(14, 30), z).toInstant().toEpochMilli(),
            TimeParse.parse("01.12.2026 14:30", now))
        for (bad in listOf("bugün 09:00", "merhaba", "25:00", "2020-01-01 10:00")) {
            try { TimeParse.parse(bad, now); throw AssertionError(bad) } catch (_: WhenError) {}
        }
        // pazar 10:00 → bir sonraki hafta içi 08:00 = pazartesi
        assertEquals(ZonedDateTime.of(LocalDate.of(2026, 11, 16), LocalTime.of(8, 0), z).toInstant().toEpochMilli(),
            TimeParse.next("daily:08:00:1,2,3,4,5", now))
        assertNull(TimeParse.next("once:1000", now))
        assertEquals("hafta içi 08:30", TimeParse.describe("daily:08:30:1,2,3,4,5"))
    }

    @Test fun geminiRestFormat() = runTest {
        val server = MockWebServer(); server.start()
        server.enqueue(MockResponse.Builder().code(200).body("""{"candidates":[{"content":{"role":"model","parts":[
            {"functionCall":{"name":"get_weather","args":{"city":"İzmir"}},"thoughtSignature":"abc"}]}}],
            "usageMetadata":{"promptTokenCount":1000,"candidatesTokenCount":50,"thoughtsTokenCount":10}}""").build())
        server.enqueue(MockResponse.Builder().code(400).body("""{"error":{"message":"API key not valid"}}""").build())
        val g = Gemini({ "KEY123" }, Budget(yai.db, yai.prefs), server.url("/v1beta/models/").toString())
        val tools = JSONArray().put(JSONObject().put("name", "get_weather").put("description", "hava").put("parametersJsonSchema",
            JSONObject().put("type", "object")))
        val r = g.generate(false, "sistem", JSONArray().put(JSONObject().put("role", "user").put("parts", JSONArray().put(JSONObject().put("text", "hava?")))), tools)
        assertEquals("get_weather", r.calls.single().name)
        assertEquals("İzmir", r.calls.single().args.getString("city"))
        assertEquals("abc", r.content!!.getJSONArray("parts").getJSONObject(0).getString("thoughtSignature"))
        val req = server.takeRequest()
        assertEquals("KEY123", req.headers["x-goog-api-key"])
        assertTrue(req.url.encodedPath.endsWith("gemini-3.5-flash-lite:generateContent"))
        val body = JSONObject(req.body!!.utf8())
        assertNotNull(body.getJSONArray("tools").getJSONObject(0).getJSONArray("functionDeclarations"))
        assertEquals("sistem", body.getJSONObject("systemInstruction").getJSONArray("parts").getJSONObject(0).getString("text"))
        assertTrue(Budget(yai.db, yai.prefs).today() > 0)
        try { g.generate(false, "s", JSONArray(), null); throw AssertionError() } catch (e: dev.yai.app.core.LlmException) {
            assertTrue("geçersiz" in e.message!!) }
        server.close()
    }
}
