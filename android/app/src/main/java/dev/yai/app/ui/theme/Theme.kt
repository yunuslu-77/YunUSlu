package dev.yai.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
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
    val Indigo = Color(0xFF2E1A9E)
    val Violet = Color(0xFF6D3BF5)
    val Cyan = Color(0xFF19C6E6)
    val Mint = Color(0xFF7CF3FF)
    val Success = Color(0xFF16A36A)
    val Warning = Color(0xFFE59A0B)
    val Danger = Color(0xFFE5484D)
    val gradient = Brush.linearGradient(listOf(Indigo, Violet, Cyan))
    val softGradient = Brush.linearGradient(listOf(Violet, Cyan))
}

private val Light = lightColorScheme(
    primary = Brand.Violet, onPrimary = Color.White,
    primaryContainer = Color(0xFFEAE3FF), onPrimaryContainer = Color(0xFF22106F),
    secondary = Brand.Cyan, onSecondary = Color(0xFF00313A),
    secondaryContainer = Color(0xFFD5F6FC), onSecondaryContainer = Color(0xFF003640),
    tertiary = Brand.Indigo,
    background = Color(0xFFF7F6FD), onBackground = Color(0xFF16142A),
    surface = Color.White, onSurface = Color(0xFF16142A),
    surfaceVariant = Color(0xFFF0EEF9), onSurfaceVariant = Color(0xFF5C5874),
    surfaceContainer = Color(0xFFF3F1FB), surfaceContainerHigh = Color(0xFFECE9F7),
    outline = Color(0xFFD9D5EA), outlineVariant = Color(0xFFE8E5F3),
    error = Brand.Danger,
)

private val Dark = darkColorScheme(
    primary = Color(0xFF9E80FF), onPrimary = Color(0xFF1C0B66),
    primaryContainer = Color(0xFF3A2596), onPrimaryContainer = Color(0xFFE9E2FF),
    secondary = Color(0xFF5FDDF2), onSecondary = Color(0xFF00363F),
    secondaryContainer = Color(0xFF0E4A56), onSecondaryContainer = Color(0xFFCDF6FD),
    tertiary = Color(0xFFB9A8FF),
    background = Color(0xFF0E0C1A), onBackground = Color(0xFFEAE7F7),
    surface = Color(0xFF17142A), onSurface = Color(0xFFEAE7F7),
    surfaceVariant = Color(0xFF221E3A), onSurfaceVariant = Color(0xFFADA8C6),
    surfaceContainer = Color(0xFF1C1931), surfaceContainerHigh = Color(0xFF26223F),
    outline = Color(0xFF3A3557), outlineVariant = Color(0xFF2B2745),
    error = Color(0xFFFF7A7E),
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
fun YaiTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val scheme = if (dark) Dark else Light
    MaterialTheme(colorScheme = scheme, typography = Type, shapes = AppShapes) {
        // Yüzey dışında kalan yazılar da temaya uygun renkte olsun (koyu modda siyah yazı kalmasın)
        CompositionLocalProvider(LocalContentColor provides scheme.onBackground, content = content)
    }
}
