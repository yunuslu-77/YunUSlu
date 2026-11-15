package dev.yai.app.ui.screens

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.School
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.graphics.drawable.toBitmap
import dev.yai.app.YaiApp
import dev.yai.app.bridge.YaiAccessibilityService
import dev.yai.app.learn.Sensitive
import dev.yai.app.ui.components.IconBadge
import dev.yai.app.ui.components.YaiCard
import dev.yai.app.ui.theme.Brand
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private data class AppItem(val pkg: String, val label: String, val icon: ImageBitmap?, val sensitive: Boolean)

@Composable
fun LearnScreen() {
    val ctx = LocalContext.current
    val store = YaiApp.instance.learning
    var apps by remember { mutableStateOf<List<AppItem>>(emptyList()) }
    var query by remember { mutableStateOf("") }
    var version by remember { mutableIntStateOf(0) }
    val stats = remember(version) { store.stats().associateBy { it.pkg } }
    val a11yOn = YaiAccessibilityService.instance != null

    LaunchedEffect(Unit) {
        apps = withContext(Dispatchers.IO) {
            val pm = ctx.packageManager
            pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
                .distinctBy { it.activityInfo.packageName }
                .filter { it.activityInfo.packageName != ctx.packageName }
                .map {
                    val p = it.activityInfo.packageName
                    AppItem(p, it.loadLabel(pm).toString(),
                        runCatching { it.loadIcon(pm).toBitmap(96, 96).asImageBitmap() }.getOrNull(), Sensitive.isSensitive(p))
                }.sortedWith(compareBy({ it.sensitive }, { it.label.lowercase() }))
        }
    }

    LazyColumn(Modifier.fillMaxSize().statusBarsPadding(), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Text("Öğrenme modu", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(vertical = 8.dp))
            Box(Modifier.fillMaxWidth().clip(MaterialTheme.shapes.large).background(Brand.gradient).padding(18.dp)) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconBadge(Icons.Rounded.School, Color.White)
                        Spacer(Modifier.width(12.dp))
                        Text("YAi uygulamalarını nasıl kullandığını öğrenir", color = Color.White,
                            style = MaterialTheme.typography.titleMedium)
                    }
                    Spacer(Modifier.height(10.dp))
                    Text("Aşağıdan uygulama seç ve normal şekilde kullan. YAi o uygulamanın ekranlarını, buton adlarını ve " +
                        "hangi butonun nereye götürdüğünü öğrenir. Sonra \"WhatsApp'ta Ali'ye yaz\" gibi işleri kendisi yapabilir.",
                        color = Color.White.copy(alpha = 0.92f), style = MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.height(8.dp))
                    Text("🔒 Mesajların, yazdıkların ve şifreler kaydedilmez. Banka/şifre uygulamaları her zaman kapalı. " +
                        "Veriler sadece telefonunda durur.", color = Color.White, style = MaterialTheme.typography.labelMedium)
                }
            }
        }
        if (!a11yOn) item {
            YaiCard {
                Text("Önce ekran erişimini aç", style = MaterialTheme.typography.titleMedium)
                Text("Öğrenme modu ve ekran kontrolü için Ayarlar → Erişilebilirlik → YAi ekran kontrolü açık olmalı.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(10.dp))
                Button(onClick = { ctx.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }) {
                    Text("Erişilebilirlik ayarlarını aç")
                }
            }
        }
        item {
            OutlinedTextField(query, { query = it }, leadingIcon = { Icon(Icons.Rounded.Search, null) },
                placeholder = { Text("Uygulama ara") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp))
        }
        items(apps.filter { query.isBlank() || it.label.contains(query, true) }, key = { it.pkg }) { app ->
            val st = stats[app.pkg]
            val enabled = st?.enabled == true
            Row(Modifier.fillMaxWidth().clip(MaterialTheme.shapes.medium).background(MaterialTheme.colorScheme.surface).padding(12.dp),
                verticalAlignment = Alignment.CenterVertically) {
                if (app.icon != null) Image(app.icon, null, Modifier.size(42.dp).clip(RoundedCornerShape(12.dp)))
                else Box(Modifier.size(42.dp))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(app.label, fontWeight = FontWeight.Medium)
                    Text(when {
                        app.sensitive -> "Hassas uygulama · güvenlik için kapalı"
                        st != null && st.screens > 0 -> "${st.screens} ekran · ${st.transitions} geçiş öğrenildi"
                        enabled -> "Öğreniyor… uygulamayı kullan"
                        else -> "Öğrenilmedi"
                    }, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (st != null && st.screens > 0) TextButton(onClick = { store.forget(app.pkg); version++ },
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) { Text("Öğrendiklerini sil") }
                }
                if (app.sensitive) Icon(Icons.Rounded.Lock, "Kilitli", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                else Switch(checked = enabled, onCheckedChange = { store.setEnabled(app.pkg, app.label, it); version++ },
                    colors = SwitchDefaults.colors(checkedTrackColor = Brand.Violet))
            }
        }
    }
}
