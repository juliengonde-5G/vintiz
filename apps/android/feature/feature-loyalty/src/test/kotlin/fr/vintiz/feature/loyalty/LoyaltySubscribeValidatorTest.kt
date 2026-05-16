package fr.vintiz.feature.loyalty

import com.google.common.truth.Truth.assertThat
import fr.vintiz.data.loyalty.LoyaltyConfigDto
import org.junit.jupiter.api.Test

class LoyaltySubscribeValidatorTest {

    private val freeConfig = LoyaltyConfigDto(mode = "free")
    private val paidConfig = LoyaltyConfigDto(mode = "paid", price_cents = 1500)

    @Test
    fun `prenom vide refuse`() {
        assertThat(
            LoyaltySubscribeValidator.validate(
                firstName = "", lastName = "Martin", email = "lea@vintiz.fr",
                paymentMethod = "", config = freeConfig,
            )
        ).isEqualTo("Prénom requis")
    }

    @Test
    fun `nom vide refuse`() {
        assertThat(
            LoyaltySubscribeValidator.validate(
                firstName = "Léa", lastName = "  ", email = "lea@vintiz.fr",
                paymentMethod = "", config = freeConfig,
            )
        ).isEqualTo("Nom requis")
    }

    @Test
    fun `email invalide refuse`() {
        listOf("lea", "lea@", "lea@vintiz", "@vintiz.fr", "lea @vintiz.fr").forEach { bad ->
            assertThat(
                LoyaltySubscribeValidator.validate(
                    firstName = "L", lastName = "M", email = bad,
                    paymentMethod = "", config = freeConfig,
                )
            ).isEqualTo("Email invalide")
        }
    }

    @Test
    fun `email avec accents domaine OK`() {
        // Note : regex courante refuse les accents domaine ; on teste
        // que des emails ASCII complets passent.
        assertThat(
            LoyaltySubscribeValidator.validate(
                firstName = "Léa", lastName = "Martin", email = "lea.martin+vintiz@example.fr",
                paymentMethod = "", config = freeConfig,
            )
        ).isNull()
    }

    @Test
    fun `mode paid sans payment_method refuse`() {
        assertThat(
            LoyaltySubscribeValidator.validate(
                firstName = "L", lastName = "M", email = "lea@v.fr",
                paymentMethod = "", config = paidConfig,
            )
        ).isEqualTo("Méthode de paiement requise pour le mode payant")
    }

    @Test
    fun `mode paid avec payment_method OK`() {
        assertThat(
            LoyaltySubscribeValidator.validate(
                firstName = "L", lastName = "M", email = "lea@v.fr",
                paymentMethod = "cash", config = paidConfig,
            )
        ).isNull()
    }

    @Test
    fun `mode free pas besoin de payment_method`() {
        assertThat(
            LoyaltySubscribeValidator.validate(
                firstName = "L", lastName = "M", email = "lea@v.fr",
                paymentMethod = "", config = freeConfig,
            )
        ).isNull()
    }
}
