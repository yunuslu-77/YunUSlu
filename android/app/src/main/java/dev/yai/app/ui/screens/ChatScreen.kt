package dev.yai.app.ui.screens

import android.content.Intent
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.Mic
import androidx.compose.material.icons.automirrored.rounded.VolumeOff
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.yai.app.ui.ChatMsg
import dev.yai.app.ui.MainViewModel
import dev.yai.app.ui.components.EmptyState
import dev.yai.app.ui.components.YaiLogo
import dev.yai.app.ui.theme.Brand
import java.util.Locale

@Composable
fun ChatScreen(vm: MainViewModel, prefill: String?, consumePrefill: () -> Unit) {
    val ctx = LocalContext.current
    val messages by vm.chat.collectAsState()
    val thinking by vm.thinking.collectAsState()
    var input by rememberSaveable { mutableStateOf("") }
    var speak by remember { mutableStateOf(vm.prefs.speakReplies) }
    val list = rememberLazyListState()

    val tts = remember { mutableStateOf<TextToSpeech?>(null) }
    DisposableEffect(Unit) {
        var engine: TextToSpeech? = null
        engine = TextToSpeech(ctx) { if (it == TextToSpeech.SUCCESS) { engine!!.language = Locale.forLanguageTag("tr-TR"); tts.value = engine } }
        onDispose { engine?.shutdown() }
    }
    val onReply: (String) -> Unit = { r -> if (speak) tts.value?.speak(r.take(600), TextToSpeech.QUEUE_FLUSH, null, "yai") }

    val mic = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { res ->
        res.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { vm.send(it, onReply = onReply) }
    }

    LaunchedEffect(prefill) { prefill?.let { vm.send(it, onReply = onReply); consumePrefill() } }
    LaunchedEffect(messages.size, thinking) { if (messages.isNotEmpty()) list.animateScrollToItem(messages.size + if (thinking) 1 else 0) }

    Column(Modifier.fillMaxSize().imePadding()) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically) {
            YaiLogo(36.dp, corner = 12.dp)
            Column(Modifier.weight(1f).padding(start = 12.dp)) {
                Text("YAi", style = MaterialTheme.typography.titleMedium)
                Text(if (thinking) "düşünüyor…" else "çevrimiçi", style = MaterialTheme.typography.labelMedium,
                    color = if (thinking) Brand.Violet else Brand.Success)
            }
            IconButton(onClick = { speak = !speak; vm.prefs.speakReplies = speak }) {
                Icon(if (speak) Icons.AutoMirrored.Rounded.VolumeUp else Icons.AutoMirrored.Rounded.VolumeOff, "Sesli cevap",
                    tint = if (speak) Brand.Violet else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        LazyColumn(Modifier.weight(1f).fillMaxWidth(), state = list,
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (messages.isEmpty()) item {
                EmptyState(Icons.Rounded.Mic, "Merhaba! 👋",
                    "Yaz ya da mikrofona dokunup konuş.\n\"Her sabah 8'de brifing ver\", \"Annemi ara\", \"Okunmamış maillerimi özetle\"")
            }
            items(messages) { Bubble(it) }
            if (thinking) item { Typing() }
        }
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.Bottom) {
            TextField(value = input, onValueChange = { input = it }, modifier = Modifier.weight(1f),
                placeholder = { Text("YAi'ye yaz…") }, maxLines = 5, shape = RoundedCornerShape(24.dp),
                colors = TextFieldDefaults.colors(focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent,
                    focusedContainerColor = MaterialTheme.colorScheme.surface, unfocusedContainerColor = MaterialTheme.colorScheme.surface))
            Spacer(Modifier.size(8.dp))
            val canSend = input.isNotBlank()
            Box(Modifier.size(52.dp).clip(CircleShape).background(Brand.gradient), contentAlignment = Alignment.Center) {
                IconButton(onClick = {
                    if (canSend) { vm.send(input.trim(), onReply = onReply); input = "" }
                    else mic.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                        .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "tr-TR")
                        .putExtra(RecognizerIntent.EXTRA_PROMPT, "YAi seni dinliyor…"))
                }) {
                    Icon(if (canSend) Icons.AutoMirrored.Rounded.Send else Icons.Rounded.Mic,
                        if (canSend) "Gönder" else "Konuş", tint = Color.White)
                }
            }
        }
    }
}

@Composable
private fun Bubble(m: ChatMsg) {
    val shape = if (m.fromUser) RoundedCornerShape(20.dp, 20.dp, 6.dp, 20.dp) else RoundedCornerShape(20.dp, 20.dp, 20.dp, 6.dp)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (m.fromUser) Arrangement.End else Arrangement.Start) {
        Box(Modifier.widthIn(max = 310.dp).clip(shape)
            .then(if (m.fromUser) Modifier.background(Brand.softGradient) else Modifier.background(MaterialTheme.colorScheme.surface))
            .padding(horizontal = 14.dp, vertical = 10.dp)) {
            SelectionContainer {
                Text(m.text, color = if (m.fromUser) Color.White else MaterialTheme.colorScheme.onSurface,
                    style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}

@Composable
private fun Typing() {
    val t = rememberInfiniteTransition(label = "typing")
    Row(Modifier.clip(RoundedCornerShape(20.dp)).background(MaterialTheme.colorScheme.surface).padding(16.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        repeat(3) { i ->
            val a by t.animateFloat(0.25f, 1f, infiniteRepeatable(tween(600, delayMillis = i * 180), RepeatMode.Reverse), label = "dot$i")
            Box(Modifier.size(8.dp).alpha(a).clip(CircleShape).background(Brand.Violet))
        }
    }
}
