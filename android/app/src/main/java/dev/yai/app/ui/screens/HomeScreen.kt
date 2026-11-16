package dev.yai.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Alarm
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Cloud
import androidx.compose.material.icons.rounded.Mail
import androidx.compose.material.icons.rounded.PhoneAndroid
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Savings
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material.icons.rounded.WbSunny
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import dev.yai.app.bridge.YaiAccessibilityService
import dev.yai.app.YaiApp
import dev.yai.app.ui.MainViewModel
import dev.yai.app.ui.components.IconBadge
import dev.yai.app.ui.components.SectionTitle
import dev.yai.app.ui.components.StatusDot
import dev.yai.app.ui.components.YaiCard
import dev.yai.app.ui.components.YaiLogo
import dev.yai.app.ui.theme.Brand
import java.util.Calendar
import java.util.Locale

@Composable
fun HomeScreen(vm: MainViewModel, openSettings: () -> Unit, openChatWith: (String) -> Unit) {
    val status by vm.status.collectAsState()
    val approvals by vm.approvals.collectAsState()
    val a11y = YaiAccessibilityService.instance != null
    val notifAccess = dev.yai.app.bridge.YaiNotificationListener.instance != null
    val learned = YaiApp.instance.learning.stats().count { it.screens > 0 }
    val name = status?.optString("bot_name")?.ifBlank { null } ?: "YAi"

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        // ---- gradyan başlık ----
        Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(bottomStart = 32.dp, bottomEnd = 32.dp))
            .background(Brand.gradient).statusBarsPadding().padding(20.dp)) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    YaiLogo(44.dp, corner = 14.dp)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(name, color = Color.White, style = MaterialTheme.typography.titleLarge)
                        Text("Telefonundaki yapay zekâ asistanı", color = Color.White.copy(alpha = 0.8f),
                            style = MaterialTheme.typography.labelMedium)
                    }
                    IconButton(onClick = { vm.refreshAll() }) { Icon(Icons.Rounded.Refresh, "Yenile", tint = Color.White) }
                    IconButton(onClick = openSettings) { Icon(Icons.Rounded.Settings, "Ayarlar", tint = Color.White) }
                }
                Spacer(Modifier.height(22.dp))
                Text(greeting(), color = Color.White, style = MaterialTheme.typography.headlineMedium)
                Spacer(Modifier.height(4.dp))
                Text("Bugün senin için ne yapayım?", color = Color.White.copy(alpha = 0.85f))
                Spacer(Modifier.height(16.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Chip("Gemini", status?.optBoolean("key") == true)
                    Chip("Ekran", a11y)
                    Chip("Bildirim", notifAccess)
                }
            }
        }

        Column(Modifier.padding(horizontal = 16.dp)) {
            // ---- hızlı işlemler ----
            SectionTitle("Hızlı işlemler")
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Quick(Icons.Rounded.WbSunny, "Brifing", Brand.Warning, Modifier.weight(1f)) {
                    openChatWith("Bana şimdi kısa bir brifing hazırla: hava durumu, bugünkü takvimim ve önemli bildirimler.") }
                Quick(Icons.Rounded.Mail, "Bildirimler", Brand.Violet, Modifier.weight(1f)) {
                    openChatWith("Telefonumdaki bildirimlerden önemli olanları (mesaj, mail) kısaca özetle.") }
                Quick(Icons.Rounded.Search, "Telefonu bul", Brand.Cyan, Modifier.weight(1f)) {
                    openChatWith("Telefonumu bul.") }
            }

            // ---- onaylar ----
            if (approvals.isNotEmpty()) {
                SectionTitle("Onay bekleyenler (${approvals.size})")
                approvals.forEach { a ->
                    YaiCard(Modifier.padding(bottom = 10.dp)) {
                        Row(verticalAlignment = Alignment.Top) {
                            IconBadge(Icons.Rounded.Shield, Brand.Warning)
                            Spacer(Modifier.width(12.dp))
                            Text(a.optString("summary"), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                        }
                        Spacer(Modifier.height(12.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Button(onClick = { vm.decide(a.optInt("id"), true) }, modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(containerColor = Brand.Success)) { Text("Onayla") }
                            OutlinedButton(onClick = { vm.decide(a.optInt("id"), false) }, modifier = Modifier.weight(1f)) { Text("İptal") }
                        }
                    }
                }
            }

            // ---- durum kartları ----
            SectionTitle("Durum")
            val spent = status?.optDouble("spent_month") ?: 0.0
            val limit = status?.optDouble("monthly_limit")?.takeIf { it > 0 } ?: 9.0
            YaiCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconBadge(Icons.Rounded.Savings, Brand.Violet)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text("Bu ayki API harcaması", style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(String.format(Locale.US, "%.2f \$ / %.0f \$", spent, limit), style = MaterialTheme.typography.titleLarge)
                    }
                }
                Spacer(Modifier.height(12.dp))
                LinearProgressIndicator(progress = { (spent / limit).toFloat().coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(8.dp)),
                    color = if (spent / limit > 0.8) Brand.Danger else Brand.Violet,
                    trackColor = MaterialTheme.colorScheme.surfaceVariant)
                Spacer(Modifier.height(6.dp))
                Text(String.format(Locale.US, "Bugün %.3f \$", status?.optDouble("spent_today") ?: 0.0),
                    style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Tile(Icons.Rounded.PhoneAndroid, "Ekran kontrolü", if (a11y) "Açık" else "Kapalı", Brand.Cyan, Modifier.weight(1f))
                Tile(Icons.Rounded.Alarm, "Görevler", "${status?.optInt("schedules") ?: 0} kurulu", Brand.Warning, Modifier.weight(1f))
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Tile(Icons.Rounded.Cloud, "Öğrenilen", "$learned uygulama", Brand.Indigo, Modifier.weight(1f))
                Tile(Icons.Rounded.CheckCircle, "Hafıza", "${status?.optInt("memories") ?: 0} bilgi", Brand.Success, Modifier.weight(1f))
            }
            Spacer(Modifier.height(28.dp))
        }
    }
}

private fun greeting(): String = when (Calendar.getInstance().get(Calendar.HOUR_OF_DAY)) {
    in 5..11 -> "Günaydın ☀️"; in 12..17 -> "İyi günler 👋"; in 18..22 -> "İyi akşamlar 🌙"; else -> "İyi geceler ✨"
}

@Composable
private fun Chip(label: String, on: Boolean) {
    Row(Modifier.clip(RoundedCornerShape(50)).background(Color.White.copy(alpha = 0.18f)).padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically) {
        StatusDot(on)
        Spacer(Modifier.width(6.dp))
        Text(label, color = Color.White, style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
private fun Quick(icon: ImageVector, label: String, tint: Color, modifier: Modifier, onClick: () -> Unit) {
    Column(modifier.clip(MaterialTheme.shapes.large).background(MaterialTheme.colorScheme.surface).clickable(onClick = onClick)
        .padding(vertical = 16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        IconBadge(icon, tint, size = 44.dp)
        Spacer(Modifier.height(8.dp))
        Text(label, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
private fun Tile(icon: ImageVector, title: String, value: String, tint: Color, modifier: Modifier) {
    Column(modifier.clip(MaterialTheme.shapes.large).background(MaterialTheme.colorScheme.surface).padding(16.dp)) {
        IconBadge(icon, tint, size = 36.dp)
        Spacer(Modifier.height(10.dp))
        Text(title, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    }
}
