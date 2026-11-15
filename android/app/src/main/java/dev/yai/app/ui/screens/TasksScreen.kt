package dev.yai.app.ui.screens

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Alarm
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.EventRepeat
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import dev.yai.app.ui.MainViewModel
import dev.yai.app.ui.components.EmptyState
import dev.yai.app.ui.components.ListRow
import dev.yai.app.ui.components.YaiCard
import dev.yai.app.ui.theme.Brand
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun TasksScreen(vm: MainViewModel) {
    val schedules by vm.schedules.collectAsState()
    var adding by remember { mutableStateOf(false) }
    val fmt = remember { SimpleDateFormat("d MMM EEE HH:mm", Locale.forLanguageTag("tr")) }

    Box(Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize().statusBarsPadding(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp, 8.dp, 16.dp, 96.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item {
                Text("Görevler", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(vertical = 8.dp))
                Text("Zamanlanmış görevler ve hatırlatıcılar. Sohbetten sesle de kurabilirsin: \"her sabah 8'de brifing ver\".",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(8.dp))
            }
            if (schedules.isEmpty()) item {
                EmptyState(Icons.Rounded.EventRepeat, "Henüz görev yok", "Sağ alttaki + ile ilk görevini ekle.")
            }
            items(schedules, key = { it.optInt("id") }) { s ->
                val isMsg = s.optString("kind") == "message"
                YaiCard {
                    ListRow(if (isMsg) Icons.Rounded.Alarm else Icons.Rounded.AutoAwesome, if (isMsg) Brand.Warning else Brand.Violet,
                        s.optString("payload"),
                        "${if (isMsg) "Hatırlatma" else "YAi görevi"} · ${s.optString("when")}\nSıradaki: " +
                            fmt.format(Date((s.optDouble("next_run") * 1000).toLong()))) {
                        IconButton(onClick = { vm.deleteSchedule(s.optInt("id")) }) {
                            Icon(Icons.Rounded.DeleteOutline, "Sil", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
        ExtendedFloatingActionButton(onClick = { adding = true }, modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp),
            containerColor = Brand.Violet, contentColor = Color.White,
            icon = { Icon(Icons.Rounded.Add, null) }, text = { Text("Görev ekle") })
    }
    if (adding) AddScheduleDialog(vm) { adding = false }
}

@Composable
private fun AddScheduleDialog(vm: MainViewModel, close: () -> Unit) {
    var whenText by remember { mutableStateOf("08:00") }
    var task by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("prompt") }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(onDismissRequest = close, title = { Text("Yeni görev") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(kind == "prompt", { kind = "prompt" }, { Text("YAi görevi") })
                    FilterChip(kind == "message", { kind = "message" }, { Text("Hatırlatma") })
                }
                OutlinedTextField(whenText, { whenText = it }, label = { Text("Ne zaman") }, singleLine = true,
                    supportingText = { Text("08:00 · hafta içi 08:30 · pzt,cum 09:00 · +30dk · yarın 09:00") },
                    modifier = Modifier.fillMaxWidth())
                OutlinedTextField(task, { task = it }, label = { Text(if (kind == "prompt") "YAi ne yapsın?" else "Hatırlatma metni") },
                    placeholder = { Text(if (kind == "prompt") "Sabah brifingi hazırla" else "Faturayı öde") },
                    modifier = Modifier.fillMaxWidth(), minLines = 2)
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = { TextButton(onClick = { vm.addSchedule(whenText, task, kind) { e -> if (e == null) close() else error = e } }) { Text("Kaydet") } },
        dismissButton = { TextButton(onClick = close) { Text("Vazgeç") } })
}
