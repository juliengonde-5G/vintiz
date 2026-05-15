package fr.vintiz.hardware.sumup.rest

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface SumUpRestApi {

    @POST("api/v1/pos/payments/cb/initiate")
    suspend fun initiate(@Body body: InitiateRequest): InitiateResponse

    @GET("api/v1/pos/payments/cb/{checkoutId}/status")
    suspend fun status(@Path("checkoutId") checkoutId: String): StatusResponse

    @DELETE("api/v1/pos/payments/cb/{checkoutId}")
    suspend fun cancel(@Path("checkoutId") checkoutId: String): Map<String, Any?>
}

@JsonClass(generateAdapter = true)
data class InitiateRequest(
    val amount_cents: Long,
    val description: String,
    val foreign_transaction_id: String,
)

@JsonClass(generateAdapter = true)
data class InitiateResponse(val checkout_id: String, val status: String)

@JsonClass(generateAdapter = true)
data class StatusResponse(
    val status: String,
    val card_brand: String? = null,
    val card_last4: String? = null,
    val auth_code: String? = null,
    val error_detail: String? = null,
)
