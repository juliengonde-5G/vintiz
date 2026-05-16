package fr.vintiz.feature.fiscal

/**
 * Validation côté client des bornes de période fiscale. Le backend
 * NF525 fait sa propre validation au moment de l'export (avec parsing
 * complet ISO 8601 + period_from < period_to + cohérence avec les
 * transactions existantes), mais on fait un check léger ici pour
 * éviter un round-trip réseau sur des saisies évidentes.
 *
 * Extrait en objet companion pour test JVM pur.
 */
object FiscalDateValidator {

    private val ISO_DATE = Regex("^\\d{4}-\\d{2}-\\d{2}$")

    fun validate(from: String?, to: String?): String? {
        if (!from.isNullOrBlank() && !ISO_DATE.matches(from)) {
            return "Format date début invalide (YYYY-MM-DD)"
        }
        if (!to.isNullOrBlank() && !ISO_DATE.matches(to)) {
            return "Format date fin invalide (YYYY-MM-DD)"
        }
        if (!from.isNullOrBlank() && !to.isNullOrBlank() && from > to) {
            return "La date de début doit être avant la date de fin"
        }
        return null
    }
}
