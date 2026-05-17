package fr.vintiz.data.authclient

import fr.vintiz.core.network.interceptors.AuthInterceptor
import fr.vintiz.data.authclient.dto.MagicLinkRequestBody
import fr.vintiz.data.authclient.dto.MagicLinkVerifyBody
import fr.vintiz.data.authclient.dto.MagicLinkVerifyResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST

/**
 * Endpoints du flow magic-link OTP côté app cliente (B2C).
 *
 * Volontairement séparé du [fr.vintiz.data.auth.AuthApi] (manager/cashier)
 * : la 2ème app Android ne doit pas dépendre de l'auth staff. Voir
 * `docs/PLAN_ANDROID_CLIENT_APP.md` §2.1 et §2.3.
 *
 * Backend : `apps/api/app/api/auth/router.py` — body **JSON**, 204 sur
 * request, JWT 1h sur verify.
 *
 * `X-Skip-Auth: true` court-circuite l'`AuthInterceptor` (pas de Bearer
 * obsolète envoyé pendant le login).
 */
interface ClientAuthApi {

    @POST("api/auth/magic-link/request")
    suspend fun requestOtp(
        @Header(AuthInterceptor.SKIP_AUTH_HEADER) skipAuth: String = "true",
        @Body body: MagicLinkRequestBody,
    ): Response<Unit>

    @POST("api/auth/magic-link/verify")
    suspend fun verifyOtp(
        @Header(AuthInterceptor.SKIP_AUTH_HEADER) skipAuth: String = "true",
        @Body body: MagicLinkVerifyBody,
    ): MagicLinkVerifyResponse
}
