package fr.vintiz.feature.loyalty

import fr.vintiz.data.loyalty.LoyaltyConfigDto

/**
 * Validation côté client des champs d'adhésion fidélité. Le backend
 * fait la même validation au POST (email unique, mode paid =
 * payment_method requis), on fait un check rapide ici pour éviter
 * un aller-retour réseau sur les erreurs évidentes.
 *
 * Extrait en objet companion pour test JVM pur.
 */
object LoyaltySubscribeValidator {

    private val EMAIL = Regex("^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")

    fun validate(
        firstName: String,
        lastName: String,
        email: String,
        paymentMethod: String,
        config: LoyaltyConfigDto?,
    ): String? {
        if (firstName.isBlank()) return "Prénom requis"
        if (lastName.isBlank()) return "Nom requis"
        if (!EMAIL.matches(email.trim())) return "Email invalide"
        if (config?.mode == "paid" && paymentMethod.isBlank()) {
            return "Méthode de paiement requise pour le mode payant"
        }
        return null
    }
}
