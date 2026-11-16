package dev.yai.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import dev.yai.app.ui.theme.Brand

/** Basit Markdown: başlık, **kalın**, *italik*, `kod`, madde/numaralı liste, tablo, kod bloğu, $formül$. */
fun inline(text: String, codeBg: Color): AnnotatedString = buildAnnotatedString {
    val re = Regex("""\*\*(.+?)\*\*|`([^`]+)`|\$([^$]+)\$|(?<![*\w])\*([^*\n]+)\*(?!\*)""")
    var last = 0
    for (m in re.findAll(text)) {
        append(text.substring(last, m.range.first))
        when {
            m.groups[1] != null -> withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(m.groupValues[1]) }
            m.groups[2] != null -> withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = codeBg)) { append(" ${m.groupValues[2]} ") }
            m.groups[3] != null -> withStyle(SpanStyle(fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, color = Brand.Deep,
                background = codeBg)) { append(" ${m.groupValues[3]} ") }
            m.groups[4] != null -> withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(m.groupValues[4]) }
        }
        last = m.range.last + 1
    }
    append(text.substring(last))
}

@Composable
fun MarkdownText(md: String, color: Color = MaterialTheme.colorScheme.onSurface, modifier: Modifier = Modifier) {
    val codeBg = Brand.SkyPale
    val lines = md.trimEnd().lines()
    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        var i = 0
        while (i < lines.size) {
            val line = lines[i]
            val t = line.trim()
            when {
                t.startsWith("```") -> {
                    val code = StringBuilder(); i++
                    while (i < lines.size && !lines[i].trim().startsWith("```")) { code.appendLine(lines[i]); i++ }
                    Text(code.toString().trimEnd(), fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodyMedium,
                        color = Brand.Deep, modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(codeBg).padding(10.dp))
                }
                t.startsWith("|") && i + 1 < lines.size && lines[i + 1].trim().matches(Regex("^\\|?\\s*:?-{2,}.*")) -> {
                    val rows = mutableListOf<List<String>>()
                    rows.add(cells(t)); i += 2
                    while (i < lines.size && lines[i].trim().startsWith("|")) { rows.add(cells(lines[i].trim())); i++ }
                    i--
                    Table(rows, codeBg)
                }
                t.startsWith("### ") || t.startsWith("## ") || t.startsWith("# ") ->
                    Text(inline(t.trimStart('#', ' '), codeBg), style = MaterialTheme.typography.titleMedium, color = Brand.Deep)
                Regex("^[-•*]\\s+").containsMatchIn(t) -> Row {
                    Text("•", color = Brand.Sky, fontWeight = FontWeight.Bold, modifier = Modifier.width(16.dp))
                    Text(inline(t.replace(Regex("^[-•*]\\s+"), ""), codeBg), color = color, style = MaterialTheme.typography.bodyLarge)
                }
                Regex("^\\d+[.)]\\s+").containsMatchIn(t) -> Row {
                    val n = Regex("^(\\d+)").find(t)!!.value
                    Text("$n.", color = Brand.Sky, fontWeight = FontWeight.Bold, modifier = Modifier.width(24.dp))
                    Text(inline(t.replace(Regex("^\\d+[.)]\\s+"), ""), codeBg), color = color, style = MaterialTheme.typography.bodyLarge)
                }
                t.isEmpty() -> {}
                else -> Text(inline(line, codeBg), color = color, style = MaterialTheme.typography.bodyLarge)
            }
            i++
        }
    }
}

private fun cells(row: String) = row.trim().trim('|').split("|").map { it.trim() }

@Composable
private fun Table(rows: List<List<String>>, codeBg: Color) {
    val cols = rows.maxOf { it.size }
    Column(Modifier.horizontalScroll(rememberScrollState()).clip(RoundedCornerShape(10.dp))
        .background(MaterialTheme.colorScheme.surface)) {
        rows.forEachIndexed { r, row ->
            Row(Modifier.background(if (r == 0) Brand.SkyPale else Color.Transparent)) {
                for (c in 0 until cols) Text(inline(row.getOrElse(c) { "" }, codeBg), modifier = Modifier.widthIn(min = 72.dp, max = 180.dp)
                    .padding(horizontal = 10.dp, vertical = 6.dp), fontWeight = if (r == 0) FontWeight.SemiBold else FontWeight.Normal,
                    style = MaterialTheme.typography.bodyMedium, color = if (r == 0) Brand.Deep else MaterialTheme.colorScheme.onSurface)
            }
        }
    }
}
