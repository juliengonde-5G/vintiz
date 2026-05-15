package fr.vintiz.core.network.interceptors

import fr.vintiz.core.security.TokenStorage
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

/**
 * Sur HTTP 401, tente un refresh via le callback fourni puis rejoue la
 * requête une fois avec le nouveau token. Si le refresh échoue, vide le
 * stockage et abandonne — la couche UI catchera l'absence de token et
 * redirigera vers le login.
 *
 * Soft-401 (login, cashier/login, magic-link verify) doivent porter
 * l'entête `X-Skip-Auth: true` pour bypasser l'Authenticator —
 * l'erreur est attendue, ce n'est pas une session expirée.
 *
 * Référence pattern : `apps/web/src/lib/api.ts:10-13` (soft-401 list).
 */
class RefreshTokenAuthenticator(
    private val tokenStorage: TokenStorage,
    private val refresh: suspend (oldToken: String) -> String?,
    private val runBlocking: (suspend () -> String?) -> String?,
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.request.header(AuthInterceptor.SKIP_AUTH_HEADER) != null) return null
        if (responseCount(response) >= MAX_RETRIES) return null

        val current = tokenStorage.getAccessToken() ?: return null
        val refreshed = runBlocking { refresh(current) } ?: run {
            tokenStorage.clearAll()
            return null
        }
        tokenStorage.saveAccessToken(refreshed)

        return response.request.newBuilder()
            .header("Authorization", "Bearer $refreshed")
            .build()
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }

    private companion object {
        const val MAX_RETRIES = 2
    }
}
