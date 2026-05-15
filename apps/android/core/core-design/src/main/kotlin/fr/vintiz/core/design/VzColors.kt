package fr.vintiz.core.design

import androidx.compose.ui.graphics.Color

/**
 * Tokens couleurs Vintiz — charte v3 « Sauge Néo » (2026-04).
 *
 * Source de vérité : [apps/web/tailwind.config.ts] palette `vz-*`.
 * Tout changement de teinte doit être synchronisé entre Tailwind et ces
 * constantes pour préserver la cohérence visuelle web / Android.
 */
object VzColors {
    val Bg = Color(0xFFF6F5F1)
    val BgAlt = Color(0xFFECEAE3)
    val Surface = Color(0xFFFFFFFF)

    val Ink = Color(0xFF0E0E0C)
    val InkSoft = Color(0xFF4A4A47)
    val InkMute = Color(0xFF8B8B86)

    val Line = Color(0xFFD5D3CC)

    val Teal = Color(0xFF0B7A6A)
    val TealDeep = Color(0xFF054238)
    val TealSoft = Color(0xFFCDE5DF)

    val Accent = Color(0xFFE84E8B)
    val AccentSoft = Color(0xFFFFD5E5)

    val Gold = Color(0xFF8E7B57)
}
