package fr.vintiz.core.network.interceptors

import fr.vintiz.core.security.TokenStorage
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Injecte `Authorization: Bearer <jwt>` sur les requêtes sortantes
 * sauf si la requête porte le header `X-Skip-Auth: true` (utile pour
 * `/auth/login`, `/auth/refresh`, `/auth/magic-link/*` qui doivent
 * partir sans token).
 */
class AuthInterceptor(
    private val tokenStorage: TokenStorage,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        if (original.header(SKIP_AUTH_HEADER) != null) {
            return chain.proceed(
                original.newBuilder().removeHeader(SKIP_AUTH_HEADER).build(),
            )
        }
        val token = tokenStorage.getAccessToken() ?: return chain.proceed(original)
        val authorized = original.newBuilder()
            .addHeader("Authorization", "Bearer $token")
            .build()
        return chain.proceed(authorized)
    }

    companion object {
        const val SKIP_AUTH_HEADER = "X-Skip-Auth"
    }
}
