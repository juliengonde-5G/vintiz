package fr.vintiz.data.admin

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface AdminApi {

    @GET("api/v1/admin/transactions")
    suspend fun transactions(
        @Query("from") from: String? = null,
        @Query("to") to: String? = null,
        @Query("method") method: String? = null,
        @Query("limit") limit: Int = 50,
    ): List<AdminTransactionDto>

    @GET("api/v1/admin/users")
    suspend fun users(): List<UserDto>

    @POST("api/v1/admin/users")
    suspend fun createUser(@Body body: CreateUserRequest): UserDto

    @DELETE("api/v1/admin/users/{id}")
    suspend fun deleteUser(@Path("id") id: String): Map<String, Any?>

    @GET("api/v1/admin/audit-logs")
    suspend fun auditLogs(
        @Query("entity") entity: String? = null,
        @Query("action") action: String? = null,
        @Query("limit") limit: Int = 100,
    ): List<AuditLogDto>

    @POST("api/v1/pos/transactions/{id}/refund")
    suspend fun refund(
        @Path("id") id: String,
        @Body body: RefundRequest,
    ): AdminTransactionDto
}

@JsonClass(generateAdapter = true)
data class AdminTransactionDto(
    val id: String,
    val timestamp: String,
    val total_cents: Long,
    val payment_method: String,
    val cashier_id: String? = null,
    val cashier_name: String? = null,
    val status: String,
)

@JsonClass(generateAdapter = true)
data class UserDto(
    val id: String,
    val username: String,
    val role: String,
    val has_pin: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class CreateUserRequest(
    val username: String,
    val password: String,
    val role: String,
)

@JsonClass(generateAdapter = true)
data class AuditLogDto(
    val id: String,
    val timestamp: String,
    val user_id: String? = null,
    val entity: String,
    val entity_id: String? = null,
    val action: String,
    val payload: Map<String, Any?>? = null,
    val client: String? = null,
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
