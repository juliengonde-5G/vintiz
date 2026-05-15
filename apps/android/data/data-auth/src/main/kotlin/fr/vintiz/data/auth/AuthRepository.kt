package fr.vintiz.data.auth

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.security.TokenStorage
import fr.vintiz.data.auth.dto.CashierLoginRequest
import fr.vintiz.data.auth.dto.LoginRequest
import retrofit2.HttpException
import timber.log.Timber
import java.io.IOException

class AuthRepository(
    private val api: AuthApi,
    private val tokenStorage: TokenStorage,
) {

    suspend fun login(username: String, password: String): VintizResult<Unit> = try {
        val token = api.login(body = LoginRequest(username = username, password = password))
        tokenStorage.saveAccessToken(token.access_token)
        VintizResult.Success(Unit)
    } catch (http: HttpException) {
        mapHttp(http)
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (t: Throwable) {
        Timber.w(t, "login KO")
        VintizResult.Failure(VintizError.Unknown(t.message ?: "Échec inattendu", t))
    }

    suspend fun cashierLogin(pin: String): VintizResult<String> = try {
        val resp = api.cashierLogin(body = CashierLoginRequest(pin = pin))
        tokenStorage.saveCashierId(resp.id)
        VintizResult.Success(resp.id)
    } catch (http: HttpException) {
        mapHttp(http)
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    }

    /**
     * Implémente le callback `refreshToken` passé à
     * [fr.vintiz.core.network.HttpClientFactory] — retourne le nouveau
     * token ou `null` si le refresh a échoué (force le logout).
     */
    suspend fun refresh(oldToken: String): String? = try {
        api.refresh(bearer = "Bearer $oldToken").access_token
    } catch (t: Throwable) {
        Timber.w(t, "refresh KO — token effacé")
        null
    }

    fun logout() {
        tokenStorage.clearAll()
    }

    private fun <T> mapHttp(http: HttpException): VintizResult<T> = when (http.code()) {
        401 -> VintizResult.Failure(VintizError.Unauthorized)
        429 -> {
            val retry = http.response()?.headers()?.get("Retry-After")?.toIntOrNull() ?: 60
            VintizResult.Failure(VintizError.RateLimit(retry))
        }
        else -> VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: "HTTP error"))
    }
}
