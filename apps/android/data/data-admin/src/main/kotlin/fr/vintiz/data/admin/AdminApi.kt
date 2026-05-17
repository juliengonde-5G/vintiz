package fr.vintiz.data.admin

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Endpoints admin — alignés sur apps/api/app/api/admin/ (router.py + users.py).
 *
 * `/admin/transactions` retourne `{transactions: [...], count}` en
 * EUR float (pas cents). `/admin/users` retourne une liste plate
 * `UserOut` avec `{id, username, email, role, is_active}`. Refund
 * vit côté `/api/pos/transactions/{id}/refund` avec un body items+method.
 */
interface AdminApi {

    @GET("api/admin/transactions")
    suspend fun transactions(
        @Query("from") from: String? = null,
        @Query("to") to: String? = null,
        @Query("method") method: String? = null,
        @Query("type") type: String? = null,
        @Query("limit") limit: Int = 100,
    ): AdminTransactionListDto

    @GET("api/admin/users")
    suspend fun users(): List<AdminUserDto>

    @POST("api/admin/users")
    suspend fun createUser(@Body body: CreateUserRequest): AdminUserDto

    @DELETE("api/admin/users/{id}")
    suspend fun deleteUser(@Path("id") id: String): Map<String, Any?>

    @GET("api/admin/audit-logs")
    suspend fun auditLogs(
        @Query("entity") entity: String? = null,
        @Query("action") action: String? = null,
        @Query("limit") limit: Int = 100,
    ): List<AuditLogDto>

    @POST("api/pos/transactions/{id}/refund")
    suspend fun refund(
        @Path("id") id: String,
        @Body body: RefundRequest,
    ): Map<String, Any?>

    @GET("api/admin/payment-attempts")
    suspend fun paymentAttempts(
        @Query("limit") limit: Int = 100,
        @Query("status") status: String? = null,
    ): List<PaymentAttemptDto>
}

@JsonClass(generateAdapter = true)
data class AdminTransactionListDto(
    val transactions: List<AdminTransactionDto> = emptyList(),
    val count: Int = 0,
)

@JsonClass(generateAdapter = true)
data class AdminTransactionDto(
    val id: String,
    val transaction_number: String? = null,
    val type: String? = null, // sale | refund | void
    val is_invoice: Boolean = false,
    val invoice_number: String? = null,
    val total_ttc: Double = 0.0,
    val total_ht: Double = 0.0,
    val total_tva: Double = 0.0,
    val methods: List<String> = emptyList(),
    val cashier_id: String? = null,
    val client_id: String? = null,
    val client_company_name: String? = null,
    val created_at: String? = null,
)

@JsonClass(generateAdapter = true)
data class AdminUserDto(
    val id: String,
    val username: String,
    val email: String? = null,
    val role: String,
    val is_active: Boolean = true,
    val has_pin: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class CreateUserRequest(
    val username: String,
    val password: String,
    val email: String? = null,
    val role: String,
)

@JsonClass(generateAdapter = true)
data class AuditLogDto(
    val id: String,
    val timestamp: String? = null,
    val user_id: String? = null,
    val entity: String? = null,
    val entity_id: String? = null,
    val action: String? = null,
    val payload: Map<String, Any?>? = null,
    val client: String? = null,
)

@JsonClass(generateAdapter = true)
data class PaymentAttemptDto(
    val id: String,
    val transaction_id: String? = null,
    val drawer_id: String? = null,
    val cashier_id: String? = null,
    val checkout_id: String? = null,
    val amount_cents: Long = 0,
    val status: String,
    val card_brand: String? = null,
    val card_last4: String? = null,
    val error_detail: String? = null,
    val attempted_at: String? = null,
    val finished_at: String? = null,
)

@JsonClass(generateAdapter = true)
data class RefundRequest(
    val items: List<RefundItemDto>,
    val method: String,
    val reason: String? = null,
)

@JsonClass(generateAdapter = true)
data class RefundItemDto(
    val product_id: String? = null,
    val quantity: Int = 1,
    val amount_cents: Long,
)
