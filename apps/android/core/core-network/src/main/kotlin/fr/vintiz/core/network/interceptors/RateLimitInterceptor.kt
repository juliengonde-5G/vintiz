package fr.vintiz.core.network.interceptors

import okhttp3.Interceptor
import okhttp3.Response
import java.io.IOException

/**
 * Sur HTTP 429 (rate-limit FastAPI cf.
 * `apps/api/app/core/rate_limit.py`), respecte le header `Retry-After`
 * en attendant N secondes avant un retry unique. Au-delà d'un retry,
 * remonte la réponse 429 telle quelle pour que la couche UI affiche
 * "Trop de tentatives, réessayez dans Xs".
 *
 * Cas typique : `/auth/login` avec 10 tentatives/5 min/IP. Si l'utilisateur
 * relance après une erreur de saisie, on évite de spammer le serveur.
 */
class RateLimitInterceptor(
    private val sleeper: Sleeper = Sleeper.Real,
) : Interceptor {

    fun interface Sleeper {
        @Throws(InterruptedException::class)
        fun sleep(seconds: Long)

        companion object {
            val Real: Sleeper = Sleeper { seconds ->
                if (seconds > 0) Thread.sleep(seconds * 1000)
            }
        }
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())
        if (response.code != 429) return response

        val retryAfter = response.header("Retry-After")?.toLongOrNull() ?: 0L
        if (retryAfter <= 0 || retryAfter > MAX_RETRY_AFTER_SECONDS) {
            return response
        }

        response.close()
        try {
            sleeper.sleep(retryAfter)
        } catch (ie: InterruptedException) {
            Thread.currentThread().interrupt()
            throw IOException("Interrupted while waiting on rate-limit", ie)
        }
        return chain.proceed(chain.request())
    }

    private companion object {
        const val MAX_RETRY_AFTER_SECONDS = 60L
    }
}
