package fr.vintiz.domain.zones

/**
 * Modèle métier d'une zone du plan boutique. Aligné sur
 * `apps/api/app/services/merchandising.py:zone_occupancy` (P2-005).
 *
 * `occupancyPct` est le ratio nProducts/capacity × 100 (0..150),
 * peut dépasser 100 si le stock courant a temporairement débordé la
 * capacité théorique (par exemple un arrivage avant tri).
 */
data class Zone(
    val id: String,
    val name: String,
    val description: String?,
    val capacity: Int?,
    val productTypes: List<String>,
    val colorHex: String?,
    val icon: String?,
    val isWindow: Boolean,
    val posX: Int,
    val posY: Int,
    val width: Int,
    val height: Int,
    val shape: ZoneShape,
    val nProducts: Int,
    val occupancyPct: Double?,
    val avgScore: Double?,
    val scoreBucket: ScoreBucket,
) {
    /**
     * Saturé si l'occupation dépasse 95 %. Aligne sur le seuil utilisé
     * dans le service de réallocation côté backend (P2-006).
     */
    val isSaturated: Boolean
        get() = occupancyPct != null && occupancyPct >= 95.0

    /**
     * Sous-rempli si on a la capa mais qu'on est en dessous de 50 %.
     * Utile pour le manager qui regroupe ou repositionne.
     */
    val isUnderused: Boolean
        get() = occupancyPct != null && occupancyPct < 50.0

    /** Ratio 0..1 capé à 1 pour les barres de progression UI. */
    val occupancyRatio: Float
        get() = occupancyPct?.let { (it / 100.0).coerceAtMost(1.0).toFloat() } ?: 0f
}

enum class ZoneShape(val key: String) {
    Rectangle("rectangle"),
    Square("square"),
    LShape("l-shape"),
    Custom("custom");

    companion object {
        fun fromKey(key: String?): ZoneShape =
            entries.firstOrNull { it.key.equals(key, ignoreCase = true) } ?: Rectangle
    }
}

/**
 * Buckets de score moyen produit (P2-005). Bon pour colorer la zone
 * en gradient sage/teal-soft/teal/teal-deep selon performance.
 */
enum class ScoreBucket(val key: String, val label: String) {
    Excellent("excellent", "Excellent"),
    Good("good", "Bon"),
    Fair("fair", "Moyen"),
    Poor("poor", "Faible"),
    Unknown("unknown", "—");

    companion object {
        fun fromKey(key: String?): ScoreBucket =
            entries.firstOrNull { it.key.equals(key, ignoreCase = true) } ?: Unknown
    }
}
