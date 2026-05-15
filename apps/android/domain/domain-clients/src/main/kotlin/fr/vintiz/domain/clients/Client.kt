package fr.vintiz.domain.clients

data class Client(
    val id: String,
    val firstName: String,
    val lastName: String,
    val email: String?,
    val phone: String?,
    val membershipNumber: String?,
    val loyaltyPoints: Int,
    val loyaltyTier: LoyaltyTier,
    val nfcUid: String?,
) {
    val displayName: String
        get() = "$firstName ${lastName.uppercase()}".trim()
}

enum class LoyaltyTier(val key: String) {
    None("none"),
    Bronze("bronze"),
    Silver("silver"),
    Gold("gold");

    companion object {
        fun fromKey(key: String?): LoyaltyTier =
            entries.firstOrNull { it.key.equals(key, ignoreCase = true) } ?: None
    }
}
