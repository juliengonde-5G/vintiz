package fr.vintiz.data.authclient

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.security.ClientTokenStorage
import fr.vintiz.data.authclient.dto.MagicLinkRequestBody
import fr.vintiz.data.authclient.dto.MagicLinkVerifyBody
import retrofit2.HttpException
import timber.log.Timber
import java.io.IOException

/**
 * Orchestration du flow magic-link OTP.
 *
 * - `requestOtp(email)` : déclenche l'envoi du code par e-mail.
 *   Le backend renvoie toujours 204 (anti-énumération), donc Success
 *   ne prouve PAS que l'email existe — c'est intentionnel.
 *
 * - `verifyOtp(email, code)` : échange l'OTP contre un JWT 1h,
 *   persiste dans [ClientTokenStorage] avec l'email + le n° de carte.
 */
class ClientAuthRepository(
    private val api: ClientAuthApi,
    private val storage: ClientTokenStorage,
) {

    suspend fun requestOtp(email: String): VintizResult<Unit> = try {
        api.requestOtp(body = MagicLinkRequestBody(email = email.trim()))
        VintizResult.Success(Unit)
    } catch (http: HttpException) {
        mapHttp(http)
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (t: Throwable) {
        Timber.w(t, "magic-link request KO")
        VintizResult.Failure(VintizError.Unknown(t.message ?: "Échec inattendu", t))
    }

    suspend fun verifyOtp(email: String, code: String): VintizResult<Session> = try {
        val resp = api.verifyOtp(
            body = MagicLinkVerifyBody(email = email.trim(), code = code.trim()),
        )
        storage.saveAccessToken(resp.access_token)
        storage.saveEmail(email.trim())
        storage.saveMembershipNumber(resp.membership_number)
        VintizResult.Success(
            Session(
                clientId = resp.client_id,
                membershipNumber = resp.membership_number,
                expiresIn = resp.expires_in,
            ),
        )
    } catch (http: HttpException) {
        mapHttp(http)
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (t: Throwable) {
        Timber.w(t, "magic-link verify KO")
        VintizResult.Failure(VintizError.Unknown(t.message ?: "Échec inattendu", t))
    }

    fun isAuthenticated(): Boolean =
        !storage.getAccessToken().isNullOrBlank()

    fun currentEmail(): String? = storage.getEmail()

    fun currentMembershipNumber(): String? = storage.getMembershipNumber()

    fun logout() {
        storage.clearAll()
    }

    private fun <T> mapHttp(http: HttpException): VintizResult<T> = when (http.code()) {
        401 -> VintizResult.Failure(VintizError.Unauthorized)
        429 -> {
            val retry = http.response()?.headers()?.get("Retry-After")?.toIntOrNull() ?: 60
            VintizResult.Failure(VintizError.RateLimit(retry))
        }
        else -> VintizResult.Failure(VintizError.http(http.code(), http.message()))
    }

    data class Session(
        val clientId: String,
        val membershipNumber: String?,
        val expiresIn: Int,
    )
}
