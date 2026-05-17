package fr.vintiz.data.personalshopper

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface PersonalShopperApi {

    /**
     * Recos Personal Shopper v2 pour la cliente identifiée (manager).
     * Mix embeddings produits + dernières interactions + tier fidélité.
     */
    @GET("api/crm/clients/{id}/personal-shopper-v2")
    suspend fun forClient(@Path("id") id: String): PersonalShopperPicksDto

    /** Côté POS : panneau Companion gated par consent profilage. */
    @GET("api/pos/clients/{id}/companion")
    suspend fun companion(
        @Path("id") id: String,
        @Query("cart_total_cents") cartTotalCents: Long = 0,
        @Query("items") items: String? = null,
    ): PosCompanionDto

    /** Log d'un click recommandation (mesure CTR côté backend). */
    @POST("api/crm/personal-shopper-v2/click")
    suspend fun logClick(@Body body: ClickEventDto): Map<String, Any?>
}

@JsonClass(generateAdapter = true)
data class PersonalShopperPicksDto(
    val client_id: String,
    val picks: List<PickDto>,
    val rationale: String? = null,
    val generated_at: String? = null,
)

@JsonClass(generateAdapter = true)
data class PickDto(
    val product_id: String,
    val name: String,
    val price_cents: Long,
    val photo_url: String? = null,
    val score: Double = 0.0,
    val reason: String? = null,
)

@JsonClass(generateAdapter = true)
data class PosCompanionDto(
    val loyalty_points: Int = 0,
    val gain_points_on_cart: Int = 0,
    val redeem_max_points: Int = 0,
    val redeem_max_cents: Long = 0,
    val upsells: List<UpsellDto> = emptyList(),
    val applicable_coupons: List<ApplicableCouponDto> = emptyList(),
    val alerts: List<CompanionAlertDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class UpsellDto(
    val product_id: String,
    val name: String,
    val price_cents: Long,
    val photo_url: String? = null,
    val reason: String? = null,
)

@JsonClass(generateAdapter = true)
data class ApplicableCouponDto(
    val code: String,
    val label: String,
    val discount_cents: Long = 0,
    val discount_percent: Int = 0,
)

@JsonClass(generateAdapter = true)
data class CompanionAlertDto(
    /** "at_risk" / "champion" / "hibernating" / "birthday" / "milestone" */
    val kind: String,
    val title: String,
    val detail: String? = null,
)

@JsonClass(generateAdapter = true)
data class ClickEventDto(
    val client_id: String,
    val product_id: String,
    val source: String = "pos",
)
