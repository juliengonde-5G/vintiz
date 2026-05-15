package fr.vintiz.core.network.interceptors

import okhttp3.Interceptor
import okhttp3.Response

/**
 * Étiquette chaque requête sortante avec l'identité du client (web /
 * site / android). Lu côté serveur par
 * `apps/api/app/core/audit_context.py` pour distinguer l'origine d'une
 * action dans `EventLog` et `AuditLog`.
 *
 * Format attendu : `vintiz-android/<versionName>` — ex.
 * `vintiz-android/0.1.0-dev`.
 */
class ClientIdInterceptor(
    private val clientId: String,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val tagged = chain.request().newBuilder()
            .addHeader("X-Client", clientId)
            .build()
        return chain.proceed(tagged)
    }
}
