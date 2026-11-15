package dev.yai.app.ui.screens

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
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.yai.app.data.SetupCode
import dev.yai.app.ui.components.YaiLogo
import dev.yai.app.ui.theme.Brand

@Composable
fun WelcomeScreen(onDone: (code: String?) -> Unit) {
    var code by remember { mutableStateOf("") }
    var err by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().background(Brand.gradient).statusBarsPadding().navigationBarsPadding().imePadding()
        .verticalScroll(rememberScrollState()).padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Spacer(Modifier.height(48.dp))
        YaiLogo(120.dp, corner = 36.dp)
        Spacer(Modifier.height(24.dp))
        Text("YAi", color = Color.White, fontSize = 44.sp, fontWeight = FontWeight.ExtraBold)
        Text("7/24 kişisel yapay zekâ ajanın", color = Color.White.copy(alpha = 0.9f), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(36.dp))
        listOf("💬" to "Yaz ya da konuş; işlerini o halletsin", "📱" to "Telefonunu senin onayınla kullanır",
            "🎓" to "Seçtiğin uygulamaları öğrenir", "⏰" to "Sabah brifingi, hatırlatma, takip").forEach { (e, t) ->
            Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(e, fontSize = 22.sp)
                Spacer(Modifier.width(12.dp))
                Text(t, color = Color.White, style = MaterialTheme.typography.bodyLarge)
            }
        }
        Spacer(Modifier.height(32.dp))
        Text("Telegram'da botuna /uygulama yaz, gelen kodu buraya yapıştır:", color = Color.White,
            textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(code, { code = it; err = false }, placeholder = { Text("YAI1:…", color = Color.White.copy(alpha = 0.6f)) },
            singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp), isError = err,
            colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Color.White, unfocusedTextColor = Color.White,
                focusedBorderColor = Color.White, unfocusedBorderColor = Color.White.copy(alpha = 0.5f), cursorColor = Color.White))
        if (err) Text("Kod geçersiz, tekrar kopyala.", color = Color(0xFFFFD6D6), modifier = Modifier.padding(top = 6.dp))
        Spacer(Modifier.height(16.dp))
        Button(onClick = { if (SetupCode.parse(code) != null) onDone(code) else err = true },
            modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(18.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Brand.Indigo)) {
            Text("Başla", fontWeight = FontWeight.Bold, fontSize = 17.sp)
        }
        TextButton(onClick = { onDone(null) }) { Text("Sonra yaparım", color = Color.White.copy(alpha = 0.85f)) }
        Spacer(Modifier.height(24.dp))
    }
}

