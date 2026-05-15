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
        limit: Int = 50,
    ): VintizResult<List<AdminTransactionDto>> = call { api.transactions(from, to, method, limit) }

    suspend fun users(): VintizResult<List<UserDto>> = call { api.users() }

    suspend fun createUser(username: String, password: String, role: String): VintizResult<UserDto> =
        call { api.createUser(CreateUserRequest(username, password, role)) }

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
    ): VintizResult<AdminTransactionDto> = call {
        api.refund(transactionId, RefundRequest(items, method, reason))
    }

    private suspend inline fun <T> call(block: suspend () -> T): VintizResult<T> = try {
        VintizResult.Success(block())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: "HTTP error"))
    }
}
