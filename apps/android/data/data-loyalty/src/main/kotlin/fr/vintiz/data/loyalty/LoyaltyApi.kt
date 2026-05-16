package fr.vintiz.data.loyalty

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT

interface LoyaltyApi {

    @POST("api/v1/pos/loyalty/subscribe")
    suspend fun subscribe(@Body body: LoyaltySubscribeRequest): LoyaltyCardDto

    @GET("api/v1/admin/loyalty/config")
    suspend fun getConfig(): LoyaltyConfigDto

    @PUT("api/v1/admin/loyalty/config")
    suspend fun setConfig(@Body body: LoyaltyConfigDto): LoyaltyConfigDto

    @POST("api/v1/pos/coupons/validate")
    suspend fun validateCoupon(@Body body: ValidateCouponRequest): CouponPreviewDto
}

@JsonClass(generateAdapter = true)
data class LoyaltySubscribeRequest(
    val email: String,
    val first_name: String,
    val last_name: String,
    val phone: String? = null,
    val consent_newsletter: Boolean = false,
    val consent_personal_shopper: Boolean = false,
    val consent_trend_alerts: Boolean = false,
    val payment_method: String? = null, // "cash" / "card" si mode paid
)

@JsonClass(generateAdapter = true)
data class LoyaltyCardDto(
    val id: String,
    val membership_number: String,
    val first_name: String,
    val last_name: String,
    val email: String,
    val loyalty_points: Int = 0,
    val tier: String? = null,
)

@JsonClass(generateAdapter = true)
data class LoyaltyConfigDto(
    val mode: String, // "free" / "paid" / "first_purchase"
    val price_cents: Long = 0,
    val threshold_cents: Long = 0,
)

@JsonClass(generateAdapter = true)
data class ValidateCouponRequest(
    val code: String,
    val cart_total_cents: Long,
    val client_id: String? = null,
)

@JsonClass(generateAdapter = true)
data class CouponPreviewDto(
    val code: String,
    val valid: Boolean,
    val reason: String? = null,
    val discount_cents: Long = 0,
    val discount_percent: Int = 0,
    val applies_to: String? = null, // "cart" / "category" / "product"
    val new_total_cents: Long,
)
