package fr.vintiz.core.design

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * Tokens typographie Vintiz — Fraunces (display), Manrope (body),
 * JetBrains Mono (codes / montants numériques).
 *
 * Sprint 0 : on retombe sur les familles système (Serif/SansSerif/Monospace)
 * tant que les .ttf ne sont pas embarqués dans
 * `core/core-design/src/main/res/font/`. Voir `apps/android/README.md` §Fonts.
 *
 * Une fois les fichiers déposés, remplacer les fallbacks par :
 *   private val Fraunces = FontFamily(
 *       Font(R.font.fraunces_regular, FontWeight.Normal),
 *       Font(R.font.fraunces_bold, FontWeight.Bold),
 *   )
 */
private val Fraunces: FontFamily = FontFamily.Serif
private val Manrope: FontFamily = FontFamily.SansSerif
private val JetBrainsMono: FontFamily = FontFamily.Monospace

/** Famille à utiliser pour les montants monétaires (chiffres tabulaires). */
val MoneyTypeface: FontFamily = JetBrainsMono

val VzTypography: Typography = Typography(
    displayLarge = TextStyle(
        fontFamily = Fraunces,
        fontWeight = FontWeight.Bold,
        fontSize = 64.sp,
        lineHeight = 68.sp,
        letterSpacing = (-0.5).sp,
    ),
    displayMedium = TextStyle(
        fontFamily = Fraunces,
        fontWeight = FontWeight.Bold,
        fontSize = 48.sp,
        lineHeight = 52.sp,
    ),
    headlineLarge = TextStyle(
        fontFamily = Fraunces,
        fontWeight = FontWeight.Bold,
        fontSize = 40.sp,
        lineHeight = 44.sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = Fraunces,
        fontWeight = FontWeight.Bold,
        fontSize = 28.sp,
        lineHeight = 32.sp,
    ),
    titleLarge = TextStyle(
        fontFamily = Manrope,
        fontWeight = FontWeight.Medium,
        fontSize = 20.sp,
        lineHeight = 28.sp,
    ),
    titleMedium = TextStyle(
        fontFamily = Manrope,
        fontWeight = FontWeight.Medium,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = Manrope,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = Manrope,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = Manrope,
        fontWeight = FontWeight.Medium,
        fontSize = 14.sp,
        lineHeight = 20.sp,
        letterSpacing = 0.5.sp,
    ),
    labelSmall = TextStyle(
        fontFamily = Manrope,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        letterSpacing = 1.3.sp,
    ),
)
