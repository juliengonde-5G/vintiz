package fr.vintiz.data.admin

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import java.io.IOException

class AdminRepository(private val api: AdminApi) {

    suspend fun transactions(
        from: String? = null,
        to: String? = null,
        method: String? = null,
        limit: Int = 100,
    ): VintizResult<List<AdminTransactionDto>> = call {
        api.transactions(from = from, to = to, method = method, limit = limit).transactions
    }

    suspend fun users(): VintizResult<List<AdminUserDto>> = call { api.users() }

    suspend fun createUser(
        username: String,
        password: String,
        role: String,
        email: String? = null,
    ): VintizResult<AdminUserDto> =
        call { api.createUser(CreateUserRequest(username, password, email, role)) }

    suspend fun deleteUser(id: String): VintizResult<Unit> =
        call { api.deleteUser(id); Unit }

    suspend fun auditLogs(
        entity: String? = null,
        action: String? = null,
        limit: Int = 100,
    ): VintizResult<List<AuditLogDto>> = call { api.auditLogs(entity, action, limit) }

    suspend fun refund(
        transactionId: String,
        items: List<RefundItemDto>,
        method: String,
        reason: String? = null,
    ): VintizResult<Map<String, Any?>> = call {
        api.refund(transactionId, RefundRequest(items, method, reason))
    }

    suspend fun paymentAttempts(
        limit: Int = 100,
        status: String? = null,
    ): VintizResult<List<PaymentAttemptDto>> = call { api.paymentAttempts(limit, status) }

    private suspend inline fun <T> call(block: suspend () -> T): VintizResult<T> = try {
        VintizResult.Success(block())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    } catch (t: Throwable) {
        // Anti-crash : JsonDataException ou autres exceptions non
        // attendues (schéma DTO désynchronisé, NPE Moshi, etc.).
        VintizResult.Failure(VintizError.Unknown(t.message ?: t::class.simpleName ?: "Erreur inconnue"))
    }
}
