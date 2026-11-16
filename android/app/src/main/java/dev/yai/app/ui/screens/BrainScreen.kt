package dev.yai.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.automirrored.rounded.Article
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.Lightbulb
import androidx.compose.material.icons.rounded.Psychology
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SecondaryTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.yai.app.ui.MainViewModel
import dev.yai.app.ui.components.EmptyState
import dev.yai.app.ui.components.ListRow
import dev.yai.app.ui.components.YaiCard
import dev.yai.app.ui.theme.Brand
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
fun BrainScreen(vm: MainViewModel) {
    var tab by remember { mutableIntStateOf(0) }
    val memories by vm.memories.collectAsState()
    val skills by vm.skills.collectAsState()
    val pages by vm.pages.collectAsState()
    var addMem by remember { mutableStateOf(false) }
    var openPage by remember { mutableStateOf<JSONObject?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) { vm.refreshAll() }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Text("Beyin", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(16.dp, 16.dp, 16.dp, 4.dp))
        Text("YAi'nin seni tanıdığı, öğrendiği ve çalıştığı her şey.", color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 16.dp))
        Spacer(Modifier.height(8.dp))
        SecondaryTabRow(selectedTabIndex = tab) {
            listOf("Hafıza", "Beceriler", "Sayfalar").forEachIndexed { i, t ->
                Tab(tab == i, { tab = i }, text = { Text(t) })
            }
        }
        LazyColumn(Modifier.fillMaxSize(), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            when (tab) {
                0 -> {
                    item {
                        TextButton(onClick = { addMem = true }) { Icon(Icons.Rounded.Add, null); Text(" Bilgi ekle") }
                    }
                    if (memories.isEmpty()) item { EmptyState(Icons.Rounded.Psychology, "Hafıza boş", "\"Ben İzmir'de yaşıyorum, hatırla\" diyebilirsin.") }
                    items(memories, key = { it.optInt("id") }) { m ->
                        YaiCard { ListRow(Icons.Rounded.Psychology, Brand.Violet, m.optString("fact")) {
                            IconButton(onClick = { vm.deleteMemory(m.optInt("id")) }) { Icon(Icons.Rounded.DeleteOutline, "Sil") } } }
                    }
                }
                1 -> {
                    if (skills.isEmpty()) item { EmptyState(Icons.Rounded.Lightbulb, "Henüz beceri yok",
                        "YAi sık yaptığın işleri fark edince beceri olarak kaydetmeyi önerir.") }
                    items(skills, key = { it.optString("name") }) { s ->
                        YaiCard { ListRow(Icons.Rounded.Lightbulb, Brand.Warning, s.optString("name"),
                            "${s.optString("trigger")}\n${s.optInt("uses")} kez kullanıldı") {
                            IconButton(onClick = { vm.deleteSkill(s.optString("name")) }) { Icon(Icons.Rounded.DeleteOutline, "Sil") } } }
                    }
                }
                else -> {
                    if (pages.isEmpty()) item { EmptyState(Icons.AutoMirrored.Rounded.Article, "Sayfa yok", "\"Bunu rapor olarak kaydet\" de.") }
                    items(pages, key = { it.optInt("id") }) { p ->
                        YaiCard { ListRow(Icons.AutoMirrored.Rounded.Article, Brand.Indigo, p.optString("title")) {
                            TextButton(onClick = { openPage = vm.page(p.optInt("id")) }) { Text("Aç") }
                        } }
                    }
                }
            }
        }
    }
    if (addMem) {
        var fact by remember { mutableStateOf("") }
        AlertDialog(onDismissRequest = { addMem = false }, title = { Text("Hafızaya ekle") },
            text = { OutlinedTextField(fact, { fact = it }, placeholder = { Text("Kahveyi şekersiz içerim") }, modifier = Modifier.fillMaxWidth()) },
            confirmButton = { TextButton(onClick = { if (fact.isNotBlank()) vm.addMemory(fact.trim()); addMem = false }) { Text("Ekle") } },
            dismissButton = { TextButton(onClick = { addMem = false }) { Text("Vazgeç") } })
    }
    openPage?.let { p ->
        AlertDialog(onDismissRequest = { openPage = null }, title = { Text(p.optString("title")) },
            text = { Column(Modifier.verticalScroll(rememberScrollState())) { Text(p.optString("content")) } },
            confirmButton = { TextButton(onClick = { openPage = null }) { Text("Kapat") } })
    }
}

