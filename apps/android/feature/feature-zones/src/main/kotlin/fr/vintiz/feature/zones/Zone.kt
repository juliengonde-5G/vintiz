package fr.vintiz.feature.zones

import androidx.compose.ui.graphics.Color
import fr.vintiz.data.zones.ZoneDto
import fr.vintiz.domain.zones.ScoreBucket
import fr.vintiz.domain.zones.Zone
import fr.vintiz.domain.zones.ZoneShape

/**
 * Convertit le DTO API en modèle métier domain-zones, en mappant le
 * `color_code` hex vers un Compose Color quand l'API en fournit un.
 */
internal fun ZoneDto.toDomain(): Zone = Zone(
    id = id,
    name = name,
    description = description,
    capacity = capacity,
    productTypes = product_types ?: emptyList(),
    colorHex = color_code,
    icon = icon,
    isWindow = is_window,
    posX = pos_x,
    posY = pos_y,
    width = width,
    height = height,
    shape = ZoneShape.fromKey(shape),
    nProducts = n_products,
    occupancyPct = occupancy_pct,
    avgScore = avg_score,
    scoreBucket = ScoreBucket.fromKey(score_bucket),
)

/**
 * Parse une couleur hex `"#RRGGBB"` ou `"#AARRGGBB"` ; retombe sur
 * une teinte par défaut selon le `scoreBucket` si l'API ne fournit
 * pas de `color_code` ou si le format est invalide.
 */
internal fun Zone.composeColor(): Color {
    val hex = colorHex?.trimStart('#')
    if (hex != null) {
        try {
            val value = hex.toLong(16)
            return if (hex.length == 6) Color(0xFF000000L or value)
            else Color(value)
        } catch (_: NumberFormatException) {
            // fallback below
        }
    }
    return when (scoreBucket) {
        ScoreBucket.Excellent -> Color(0xFFCDE5DF)
        ScoreBucket.Good -> Color(0xFFE6EFEC)
        ScoreBucket.Fair -> Color(0xFFF0E6D2)
        ScoreBucket.Poor -> Color(0xFFFFD5E5)
        ScoreBucket.Unknown -> Color(0xFFECEAE3)
    }
}
