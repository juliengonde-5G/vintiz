package fr.vintiz.feature.zones

import androidx.compose.ui.graphics.Color

/**
 * Modèle simplifié pour le rendu IsoCanvas. Le vrai modèle viendra
 * d'un `data:data-zones` couplé à `apps/api/app/api/admin/zones` —
 * ce screen accepte des zones en mémoire pour démo / tests.
 */
data class Zone(
    val id: String,
    val name: String,
    val posX: Int,
    val posY: Int,
    val width: Int,
    val height: Int,
    val color: Color,
    val occupancy: Float, // 0..1
)

object DemoZones {
    val petitsPrix = Zone("petits_prix", "Petits prix", 0, 0, 120, 80, Color(0xFFCDE5DF), 0.75f)
    val extra = Zone("extra", "Extra", 130, 0, 100, 80, Color(0xFFFFD5E5), 0.55f)
    val chaussuresF = Zone("ch_f", "Chaussures F", 0, 90, 80, 60, Color(0xFFF0E6D2), 0.40f)
    val chaussuresH = Zone("ch_h", "Chaussures H", 90, 90, 80, 60, Color(0xFFF0E6D2), 0.30f)
    val portants = Zone("portants", "Portants", 180, 90, 80, 60, Color(0xFFE8E0CF), 0.90f)
    val vitrine = Zone("vitrine", "Vitrine", 0, 160, 260, 40, Color(0xFFCDE5DF), 0.20f)

    val all = listOf(petitsPrix, extra, chaussuresF, chaussuresH, portants, vitrine)
}
