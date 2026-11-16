package dev.yai.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.yai.app.ui.components.YaiLogo
import dev.yai.app.ui.theme.Brand
import kotlinx.coroutines.launch

/** Tek kurulum adımı: Gemini API anahtarını yapıştır. */
@Composable
fun WelcomeScreen(testKey: suspend (String) -> String?, onDone: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var key by remember { mutableStateOf("") }
    var err by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().background(Brand.gradient).statusBarsPadding().navigationBarsPadding().imePadding()
        .verticalScroll(rememberScrollState()).padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Spacer(Modifier.height(40.dp))
        YaiLogo(120.dp, corner = 36.dp)
        Spacer(Modifier.height(24.dp))
        Text("YAi", color = Color.White, fontSize = 44.sp, fontWeight = FontWeight.ExtraBold)
        Text("Telefonundaki yapay zekâ asistanı", color = Color.White.copy(alpha = 0.9f), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(32.dp))
        listOf("💬" to "Yaz ya da konuş; işlerini o halletsin", "📱" to "Telefonunu senin onayınla kullanır",
            "🎓" to "Seçtiğin uygulamaları öğrenir", "⏰" to "Sabah brifingi, hatırlatma, takip").forEach { (e, t) ->
            Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(e, fontSize = 22.sp); Spacer(Modifier.width(12.dp))
                Text(t, color = Color.White, style = MaterialTheme.typography.bodyLarge)
            }
        }
        Spacer(Modifier.height(28.dp))
        Text("Başlamak için tek gereken: Gemini API anahtarın", color = Color.White, textAlign = TextAlign.Center,
            style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(10.dp))
        OutlinedButton(onClick = { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://aistudio.google.com/apikey"))) },
            colors = ButtonDefaults.outlinedButtonColors(contentColor = Color.White)) { Text("🔑 Anahtarımı al (AI Studio)") }
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(key, { key = it; err = null }, placeholder = { Text("AIza…", color = Color.White.copy(alpha = 0.6f)) },
            singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp), isError = err != null,
            visualTransformation = PasswordVisualTransformation(),
            colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Color.White, unfocusedTextColor = Color.White,
                focusedBorderColor = Color.White, unfocusedBorderColor = Color.White.copy(alpha = 0.5f), cursorColor = Color.White))
        err?.let { Text(it, color = Color(0xFFFFD6D6), modifier = Modifier.padding(top = 6.dp), textAlign = TextAlign.Center) }
        Spacer(Modifier.height(16.dp))
        Button(onClick = {
            if (key.trim().length < 20) { err = "Anahtar çok kısa görünüyor. Tamamını kopyaladığından emin ol."; return@Button }
            busy = true
            scope.launch { val e = testKey(key.trim()); busy = false; if (e == null) onDone() else err = e }
        }, enabled = !busy, modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(18.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Brand.Indigo)) {
            if (busy) CircularProgressIndicator(Modifier.size(22.dp), color = Brand.Indigo, strokeWidth = 2.dp)
            else Text("Başla", fontWeight = FontWeight.Bold, fontSize = 17.sp)
        }
        Spacer(Modifier.height(12.dp))
        Text("Anahtarın sadece bu telefonda saklanır ve doğrudan Google'a gönderilir.", color = Color.White.copy(alpha = 0.8f),
            style = MaterialTheme.typography.labelMedium, textAlign = TextAlign.Center)
        Spacer(Modifier.height(24.dp))
    }
}
