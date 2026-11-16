package dev.yai.app.ui.components

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.List
import androidx.compose.material.icons.automirrored.rounded.Message
import androidx.compose.material.icons.rounded.Alarm
import androidx.compose.material.icons.rounded.Calculate
import androidx.compose.material.icons.rounded.Call
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Event
import androidx.compose.material.icons.rounded.HourglassTop
import androidx.compose.material.icons.rounded.Language
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material.icons.rounded.Timer
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.yai.app.core.ToolEvent
import dev.yai.app.ui.theme.Brand
import org.json.JSONArray
import org.json.JSONObject

private val HIDDEN = setOf("get_datetime", "use_skill", "read_page", "phone_screen_read", "phone_app_guide", "phone_learned_apps",
    "phone_list_apps", "phone_screen_look", "list_pages", "phone_contacts")

private fun obj(s: String) = runCatching { JSONObject(s) }.getOrNull()
private fun arr(s: String) = runCatching { JSONArray(s) }.getOrNull()

@Composable
fun ToolCard(ev: ToolEvent, pending: Set<Long>, onDecide: (Long, Boolean) -> Unit) {
    val res = obj(ev.result)
    val approvalId = res?.takeIf { it.optString("status") == "onay_bekleniyor" }?.optLong("approval_id")
    when {
        approvalId != null -> ApprovalCard(ev, approvalId, approvalId in pending, onDecide)
        !ev.ok -> ErrorChip(ev, res?.optString("error") ?: ev.result)
        ev.name in HIDDEN -> {}
        ev.name == "get_weather" && res != null -> WeatherCard(res)
        ev.name == "calculate" && res != null -> MathCard(res)
        ev.name == "web_search" && res != null -> SourcesCard(res)
        ev.name in setOf("phone_set_alarm", "phone_set_timer", "create_schedule", "set_reminder", "calendar_create") -> TaskCard(ev, res)
        ev.name in setOf("phone_notifications", "phone_sms_list", "calendar_list", "list_schedules", "phone_call_log", "list_memories") ->
            ListCard(ev)
        else -> DoneChip(ev)
    }
}

@Composable
private fun CardShell(content: @Composable () -> Unit) {
    Box(Modifier.widthIn(max = 330.dp).fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Color.White)
        .border(1.dp, Color(0xFFD3EAFB), RoundedCornerShape(20.dp))) { content() }
}

@Composable
private fun Header(icon: ImageVector, title: String, sub: String? = null) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        IconBadge(icon, Brand.Sky, size = 36.dp)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = Brand.Deep, maxLines = 2, overflow = TextOverflow.Ellipsis)
            sub?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

// ---------------- hava durumu ----------------
private fun weatherEmoji(d: String) = when {
    "fırtına" in d -> "⛈️"; "kar" in d -> "❄️"; "yağmur" in d || "sağanak" in d || "çisenti" in d -> "🌧️"
    "sis" in d -> "🌫️"; "kapalı" in d -> "☁️"; "parçalı" in d -> "⛅"; "açık" in d -> "☀️"; else -> "🌤️"
}

@Composable
private fun WeatherCard(r: JSONObject) {
    val now = r.optJSONObject("şimdi") ?: JSONObject()
    val days = r.optJSONArray("tahmin") ?: JSONArray()
    Box(Modifier.widthIn(max = 330.dp).fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Brand.gradient).padding(16.dp)) {
        Column {
            Text("📍 " + r.optString("yer"), color = Color.White, style = MaterialTheme.typography.labelLarge)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(weatherEmoji(now.optString("durum")), fontSize = 44.sp)
                Spacer(Modifier.width(10.dp))
                Column {
                    Text("${now.optDouble("sıcaklık").let { if (it.isNaN()) "?" else Math.round(it).toString() }}°", color = Color.White,
                        fontSize = 44.sp, fontWeight = FontWeight.Bold)
                    Text("${now.optString("durum")} · hissedilen ${now.optDouble("hissedilen").let { if (it.isNaN()) "?" else Math.round(it) }}°",
                        color = Color.White.copy(alpha = 0.9f), style = MaterialTheme.typography.bodyMedium)
                }
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (i in 0 until minOf(3, days.length())) {
                    val d = days.getJSONObject(i)
                    Column(Modifier.weight(1f).clip(RoundedCornerShape(14.dp)).background(Color.White.copy(alpha = 0.22f)).padding(8.dp),
                        horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(listOf("Bugün", "Yarın", "Sonra")[i], color = Color.White, style = MaterialTheme.typography.labelMedium)
                        Text(weatherEmoji(d.optString("durum")), fontSize = 22.sp)
                        Text("${Math.round(d.optDouble("max"))}° / ${Math.round(d.optDouble("min"))}°", color = Color.White,
                            style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                        Text("☔ %${d.optInt("yağış_%")}", color = Color.White.copy(alpha = 0.9f), style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        }
    }
}

// ---------------- hesap ----------------
@Composable
private fun MathCard(r: JSONObject) = CardShell {
    Column(Modifier.padding(14.dp)) {
        Header(Icons.Rounded.Calculate, r.optString("label").ifBlank { "Hesap" })
        Spacer(Modifier.height(8.dp))
        Text(r.optString("expression"), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace)
        Text("= " + r.optString("result"), fontSize = 30.sp, fontWeight = FontWeight.Bold, color = Brand.Sky)
    }
}

// ---------------- web kaynakları ----------------
@Composable
private fun SourcesCard(r: JSONObject) {
    val ctx = LocalContext.current
    val src = r.optJSONArray("sources") ?: JSONArray()
    CardShell {
        Column(Modifier.padding(14.dp)) {
            Header(Icons.Rounded.Language, "Web'den bulunanlar", "${src.length()} kaynak")
            for (i in 0 until minOf(src.length(), 5)) {
                val s = src.getJSONObject(i)
                Text("🔗 " + s.optString("title").ifBlank { s.optString("url") }, color = Brand.Deep, maxLines = 1, overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 6.dp)
                        .clickable { runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(s.optString("url")))) } })
            }
        }
    }
}

// ---------------- görev / alarm ----------------
@Composable
private fun TaskCard(ev: ToolEvent, r: JSONObject?) {
    val a = ev.args
    val (icon, title, sub) = when (ev.name) {
        "phone_set_alarm" -> Triple(Icons.Rounded.Alarm, "Alarm kuruldu", "%02d:%02d".format(a.optInt("hour"), a.optInt("minute")) +
            (a.optString("label").takeIf { it.isNotBlank() }?.let { " · $it" } ?: ""))
        "phone_set_timer" -> Triple(Icons.Rounded.Timer, "Sayaç başladı", "${a.optInt("seconds") / 60} dk ${a.optInt("seconds") % 60} sn")
        "set_reminder" -> Triple(Icons.Rounded.Alarm, a.optString("message"), "Hatırlatma · " + (r?.optString("when") ?: a.optString("when")))
        "create_schedule" -> Triple(Icons.Rounded.HourglassTop, a.optString("task"), "Görev · " + (r?.optString("when") ?: a.optString("when")))
        else -> Triple(Icons.Rounded.Event, a.optString("title"), "Takvim · " + (r?.optString("start") ?: a.optString("start")))
    }
    CardShell {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f)) { Header(icon, title, sub) }
            Icon(Icons.Rounded.CheckCircle, "Tamam", tint = Brand.Sky)
        }
    }
}

// ---------------- listeler ----------------
@Composable
private fun ListCard(ev: ToolEvent) {
    val items = arr(ev.result) ?: return DoneChip(ev)
    val title = when (ev.name) { "phone_notifications" -> "Bildirimler"; "phone_sms_list" -> "SMS'ler"; "calendar_list" -> "Takvim"
        "list_schedules" -> "Görevler"; "phone_call_log" -> "Son aramalar"; else -> "Hafıza" }
    CardShell {
        Column(Modifier.padding(14.dp)) {
            Header(Icons.AutoMirrored.Rounded.List, title, "${items.length()} kayıt")
            for (i in 0 until minOf(items.length(), 6)) {
                val o = items.optJSONObject(i) ?: continue
                val (l1, l2) = when (ev.name) {
                    "phone_notifications" -> o.optString("title") to o.optString("content")
                    "phone_sms_list" -> o.optString("sender") to o.optString("body")
                    "calendar_list" -> o.optString("title") to (o.optString("start") + (o.optString("location").takeIf { it.isNotBlank() }?.let { " · $it" } ?: ""))
                    "list_schedules" -> o.optString("text") to o.optString("when")
                    "phone_call_log" -> (o.optString("name").ifBlank { o.optString("number") }) to o.optString("type")
                    else -> o.optString("fact") to ""
                }
                Column(Modifier.fillMaxWidth().padding(top = 8.dp).clip(RoundedCornerShape(12.dp)).background(Brand.SkyPale).padding(10.dp)) {
                    Text(l1, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium)
                    if (l2.isNotBlank()) Text(l2, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

// ---------------- onay (mesaj / arama / ekran) ----------------
@Composable
private fun ApprovalCard(ev: ToolEvent, id: Long, stillPending: Boolean, onDecide: (Long, Boolean) -> Unit) {
    val a = ev.args
    val (icon, title, body) = when (ev.name) {
        "phone_sms_send" -> Triple(Icons.AutoMirrored.Rounded.Message, "SMS: ${a.optString("number")}", a.optString("text"))
        "phone_call" -> Triple(Icons.Rounded.Call, "Arama", a.optString("number"))
        "phone_photo" -> Triple(Icons.Rounded.Shield, "Fotoğraf çekilsin mi?", a.optString("question"))
        else -> Triple(Icons.Rounded.Shield, "Onay gerekiyor", a.toString().take(200))
    }
    CardShell {
        Column(Modifier.padding(14.dp)) {
            Header(icon, title, if (stillPending) "Onayını bekliyor" else "Karar verildi")
            if (body.isNotBlank()) Text(body, modifier = Modifier.fillMaxWidth().padding(top = 10.dp).clip(RoundedCornerShape(12.dp))
                .background(Brand.SkyPale).padding(12.dp), style = MaterialTheme.typography.bodyLarge)
            if (stillPending) Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onClick = { onDecide(id, true) }, modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Brand.Sky)) {
                    Text(if (ev.name == "phone_call") "Ara" else if (ev.name == "phone_sms_send") "Gönder" else "Onayla") }
                OutlinedButton(onClick = { onDecide(id, false) }, modifier = Modifier.weight(1f)) { Text("İptal") }
            }
        }
    }
}

// ---------------- basit sonuçlar ----------------
private val LABELS = mapOf(
    "phone_torch" to "Fener", "phone_volume" to "Ses seviyesi ayarlandı", "phone_speak" to "Sesli okundu", "phone_find" to "Telefon çalıyor",
    "phone_open_url" to "Bağlantı açıldı", "phone_open_app" to "Uygulama açıldı", "phone_clipboard_set" to "Panoya kopyalandı",
    "remember" to "Hafızaya eklendi", "forget" to "Hafızadan silindi", "create_page" to "Not kaydedildi", "update_page" to "Not güncellendi",
    "delete_schedule" to "Görev silindi", "phone_status" to "Telefon durumu okundu", "phone_location" to "Konum alındı",
    "phone_click_text" to "Dokunuldu", "phone_tap" to "Dokunuldu", "phone_swipe" to "Kaydırıldı", "phone_type_text" to "Yazıldı",
    "phone_key" to "Tuşa basıldı", "phone_screen_control" to "Ekran kontrolü açık", "fetch_url" to "Sayfa okundu",
    "phone_sms_send" to "SMS gönderildi", "phone_call" to "Arama başlatıldı", "phone_tasker" to "Tasker görevi çalıştı",
    "save_skill" to "Beceri kaydedildi", "phone_photo" to "Fotoğraf çekildi",
)

@Composable
private fun DoneChip(ev: ToolEvent) {
    val label = when (ev.name) {
        "phone_torch" -> if (ev.args.optBoolean("on")) "Fener açıldı" else "Fener kapatıldı"
        "phone_open_app" -> "Açıldı: " + ev.args.optString("app")
        "phone_location" -> obj(ev.result)?.let { "Konum: %.4f, %.4f".format(it.optDouble("latitude"), it.optDouble("longitude")) } ?: "Konum alındı"
        "phone_status" -> obj(ev.result)?.optJSONObject("battery")?.let { "Pil %${it.optInt("percentage")}" } ?: "Telefon durumu"
        else -> LABELS[ev.name] ?: ev.name
    }
    Chip(Icons.Rounded.CheckCircle, label, Brand.Sky)
}

@Composable
private fun ErrorChip(ev: ToolEvent, err: String) =
    Chip(Icons.Rounded.ErrorOutline, (LABELS[ev.name]?.let { "$it: " } ?: "${ev.name}: ") + err.take(160), Brand.Danger)

@Composable
private fun Chip(icon: ImageVector, text: String, tint: Color) {
    Row(Modifier.widthIn(max = 330.dp).clip(RoundedCornerShape(14.dp)).background(tint.copy(alpha = 0.10f))
        .padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = tint, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(8.dp))
        Text(text, color = if (tint == Brand.Danger) tint else Brand.Deep, style = MaterialTheme.typography.bodyMedium)
    }
}
