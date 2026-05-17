package fr.vintiz.data.auth

import fr.vintiz.core.network.interceptors.AuthInterceptor
import fr.vintiz.data.auth.dto.CashierLoginRequest
import fr.vintiz.data.auth.dto.CashierResponse
import fr.vintiz.data.auth.dto.TokenResponse
import retrofit2.http.Body
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.Header
import retrofit2.http.POST

/**
 * Endpoints d'authentification — voir `apps/api/app/api/auth/router.py`
 * et `apps/api/app/api/pos/router.py` (cashier).
 *
 * `X-Skip-Auth: true` court-circuite l'`AuthInterceptor` pour le login
 * et le refresh (qui ne doivent pas envoyer de Bearer obsolète).
 *
 * Le endpoint manager utilise `OAuth2PasswordRequestForm` côté FastAPI :
 * il EXIGE `application/x-www-form-urlencoded` (pas JSON), sinon 422.
 * Le cashier-login lui prend bien un body JSON.
 */
interface AuthApi {

    @FormUrlEncoded
    @POST("api/auth/login")
    suspend fun login(
        @Header(AuthInterceptor.SKIP_AUTH_HEADER) skipAuth: String = "true",
        @Field("username") username: String,
        @Field("password") password: String,
    ): TokenResponse

    @POST("api/auth/refresh")
    suspend fun refresh(
        @Header("Authorization") bearer: String,
        @Header(AuthInterceptor.SKIP_AUTH_HEADER) skipAuth: String = "true",
    ): TokenResponse

    @POST("api/pos/cashier/login")
    suspend fun cashierLogin(
        @Header(AuthInterceptor.SKIP_AUTH_HEADER) skipAuth: String = "true",
        @Body body: CashierLoginRequest,
    ): CashierResponse
}
