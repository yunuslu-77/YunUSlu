package dev.yai.app.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

object Brand {
    // Açık mavi + beyaz tema
    val Sky = Color(0xFF2E9BEA)          // ana mavi
    val SkyLight = Color(0xFF6CC4FF)
    val SkyPale = Color(0xFFEAF6FF)
    val Deep = Color(0xFF1677C9)         // yazı vurgusu için koyu mavi
    val Indigo = Deep
    val Violet = Sky
    val Cyan = SkyLight
    val Mint = Color(0xFFFFFFFF)
    val Success = Color(0xFF2E9BEA)
    val Warning = Color(0xFF4AA8F0)
    val Danger = Color(0xFFE5484D)
    val gradient = Brush.linearGradient(listOf(Color(0xFF6CC4FF), Color(0xFF2E9BEA)))
    val softGradient = Brush.linearGradient(listOf(Color(0xFF6CC4FF), Color(0xFF2E9BEA)))
}

private val Light = lightColorScheme(
    primary = Brand.Sky, onPrimary = Color.White,
    primaryContainer = Color(0xFFD6EEFF), onPrimaryContainer = Color(0xFF0B4A7E),
    secondary = Brand.SkyLight, onSecondary = Color.White,
    secondaryContainer = Color(0xFFE3F3FF), onSecondaryContainer = Color(0xFF0B4A7E),
    tertiary = Brand.Deep,
    background = Color(0xFFF2F9FF), onBackground = Color(0xFF0E2A44),
    surface = Color.White, onSurface = Color(0xFF0E2A44),
    surfaceVariant = Color(0xFFE6F3FD), onSurfaceVariant = Color(0xFF4F6A82),
    surfaceContainer = Color(0xFFEDF7FF), surfaceContainerHigh = Color(0xFFE3F2FE),
    outline = Color(0xFFC4E1F7), outlineVariant = Color(0xFFDDEEFB),
    error = Brand.Danger,
)

private val Type = Typography(
    headlineLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 30.sp, lineHeight = 36.sp),
    headlineMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 24.sp, lineHeight = 30.sp),
    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 16.sp, lineHeight = 23.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 14.sp),
    labelMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Medium, fontSize = 12.sp),
)

private val AppShapes = Shapes(
    small = RoundedCornerShape(12.dp), medium = RoundedCornerShape(18.dp), large = RoundedCornerShape(26.dp),
)

@Composable
fun YaiTheme(@Suppress("UNUSED_PARAMETER") dark: Boolean = false, content: @Composable () -> Unit) {
    val scheme = Light  // her zaman açık mavi + beyaz
    MaterialTheme(colorScheme = scheme, typography = Type, shapes = AppShapes) {
        // Yüzey dışında kalan yazılar da temaya uygun renkte olsun (koyu modda siyah yazı kalmasın)
        CompositionLocalProvider(LocalContentColor provides scheme.onBackground, content = content)
    }
}
