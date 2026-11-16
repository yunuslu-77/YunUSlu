package dev.yai.app.ui.screens

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Accessibility
import androidx.compose.material.icons.rounded.BatterySaver
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Key
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.PhoneAndroid
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.ui.text.input.PasswordVisualTransformation
import android.app.AlarmManager
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LifecycleResumeEffect
import dev.yai.app.bridge.YaiAccessibilityService
import dev.yai.app.ui.MainViewModel
import dev.yai.app.ui.components.ListRow
import dev.yai.app.ui.components.SectionTitle
import dev.yai.app.ui.components.YaiCard
import dev.yai.app.ui.theme.Brand

val RUNTIME_PERMISSIONS = arrayOf(
    Manifest.permission.READ_SMS, Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS,
    Manifest.permission.CALL_PHONE, Manifest.permission.READ_CALL_LOG, Manifest.permission.READ_CONTACTS,
    Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.CAMERA,
    Manifest.permission.RECORD_AUDIO, Manifest.permission.POST_NOTIFICATIONS,
    Manifest.permission.READ_CALENDAR, Manifest.permission.WRITE_CALENDAR,
)

private fun granted(ctx: Context, p: String) = ContextCompat.checkSelfPermission(ctx, p) == PackageManager.PERMISSION_GRANTED

@Composable
fun SettingsScreen(vm: MainViewModel, back: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var key by remember { mutableStateOf("") }
    var keyMsg by remember { mutableStateOf<String?>(null) }
    var phoneOn by remember { mutableStateOf(vm.prefs.phoneEnabled) }
    var monthly by remember { mutableStateOf(vm.prefs.monthlyLimit.toString()) }
    var daily by remember { mutableStateOf(vm.prefs.dailyLimit.toString()) }
    var tick by remember { mutableIntStateOf(0) }
    LifecycleResumeEffect(Unit) { tick++; onPauseOrDispose { } }
    val permLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { tick++ }
    fun open(i: Intent) = runCatching { ctx.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }

    Column(Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 8.dp)) {
            IconButton(onClick = back) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Geri") }
            Text("Ayarlar", style = MaterialTheme.typography.headlineMedium)
        }

        SectionTitle("Gemini API anahtarı")
        YaiCard {
            ListRow(Icons.Rounded.Key, Brand.Violet, if (vm.prefs.hasKey) "Anahtar kayıtlı ✓" else "Anahtar yok",
                if (vm.prefs.hasKey) "…" + vm.prefs.apiKey.takeLast(4) else "aistudio.google.com/apikey adresinden al")
            OutlinedTextField(key, { key = it; keyMsg = null }, label = { Text("Yeni anahtar (AIza…)") }, singleLine = true,
                visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
            keyMsg?.let { Text(it, color = if (it.startsWith("✓")) Brand.Success else MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 6.dp)) }
            Spacer(Modifier.height(10.dp))
            Button(onClick = { scope.launch { val e = vm.saveAndTestKey(key.trim()); keyMsg = e ?: "✓ Anahtar çalışıyor"; if (e == null) key = "" } },
                enabled = key.trim().length >= 20, modifier = Modifier.fillMaxWidth()) { Text("Kaydet ve dene") }
        }

        SectionTitle("Bütçe")
        YaiCard {
            Text("Harcama bu sınırlara gelince YAi ucuz modele geçer veya durur.", color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(monthly, { monthly = it; it.replace(',', '.').toFloatOrNull()?.let { v -> vm.prefs.monthlyLimit = v } },
                label = { Text("Aylık limit (\$)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(daily, { daily = it; it.replace(',', '.').toFloatOrNull()?.let { v -> vm.prefs.dailyLimit = v } },
                label = { Text("Günlük akıllı model limiti (\$)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        }

        SectionTitle("Telefon")
        YaiCard {
            ListRow(Icons.Rounded.PhoneAndroid, Brand.Cyan, "YAi telefonu kullanabilsin", "SMS, arama, alarm, ekran kontrolü…") {
                Switch(phoneOn, { phoneOn = it; vm.prefs.phoneEnabled = it }, colors = SwitchDefaults.colors(checkedTrackColor = Brand.Violet))
            }
            TextButton(onClick = { vm.clearChat() }) { Text("Sohbet geçmişini temizle") }
        }

        SectionTitle("İzinler")
        Text("Her izni sadece ilgili özellik için kullanır. Android 13+ sürümünde erişilebilirlik ve bildirim erişimi kilitliyse " +
            "önce 'Kısıtlı ayarlara izin ver' adımını yap.", style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 8.dp))
        key(tick) {
            val runtimeOk = RUNTIME_PERMISSIONS.count { granted(ctx, it) }
            val a11y = YaiAccessibilityService.instance != null
            val notif = NotificationManagerCompat.getEnabledListenerPackages(ctx).contains(ctx.packageName)
            val overlay = Settings.canDrawOverlays(ctx)
            val battery = ctx.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(ctx.packageName)
            YaiCard {
                Perm(Icons.Rounded.Key, "Telefon izinleri", "SMS, arama, rehber, konum, kamera, mikrofon, takvim ($runtimeOk/${RUNTIME_PERMISSIONS.size})",
                    runtimeOk == RUNTIME_PERMISSIONS.size) { permLauncher.launch(RUNTIME_PERMISSIONS) }
                Perm(Icons.Rounded.Security, "Kısıtlı ayarlara izin ver", "Uygulama bilgisi → ⋮ → Kısıtlı ayarlara izin ver (Android 13+)",
                    a11y && notif) { open(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + ctx.packageName))) }
                Perm(Icons.Rounded.Accessibility, "Ekran kontrolü ve öğrenme", "Erişilebilirlik → YAi ekran kontrolü", a11y) {
                    open(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
                Perm(Icons.Rounded.Notifications, "Bildirim erişimi", "Bildirimleri okuyup sana iletebilmesi için", notif) {
                    open(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }
                Perm(Icons.Rounded.Layers, "Diğer uygulamaların üzerinde göster", "Uygulama/alarm açabilmesi için", overlay) {
                    open(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + ctx.packageName))) }
                val exact = Build.VERSION.SDK_INT < 31 || ctx.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()
                Perm(Icons.Rounded.Tune, "Tam zamanlı alarmlar", "Görevlerin dakikası dakikasına çalışması için", exact) {
                    open(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:" + ctx.packageName))) }
                Perm(Icons.Rounded.BatterySaver, "Pil kısıtlamasını kaldır", "Görevlerin zamanında çalışması için", battery) {
                    open(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + ctx.packageName))) }
            }
        }

        Spacer(Modifier.height(16.dp))
        Text("YAi ${runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: ""}",
            style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.align(Alignment.CenterHorizontally))
        Spacer(Modifier.height(32.dp))
    }
}

@Composable
private fun key(k: Int, content: @Composable () -> Unit) = androidx.compose.runtime.key(k) { content() }

@Composable
private fun Perm(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, sub: String, ok: Boolean, onClick: () -> Unit) {
    ListRow(icon, if (ok) Brand.Success else Brand.Warning, title, sub) {
        if (ok) Icon(Icons.Rounded.CheckCircle, "Tamam", tint = Brand.Success)
        else TextButton(onClick = onClick) { Text("Aç") }
    }
}

