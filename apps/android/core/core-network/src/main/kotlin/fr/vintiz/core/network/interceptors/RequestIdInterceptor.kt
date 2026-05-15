package fr.vintiz.core.network.interceptors

import okhttp3.Interceptor
import okhttp3.Response
import java.util.Locale
import kotlin.random.Random

/**
 * Génère / propage `x-request-id` côté client pour corréler une
 * action UI avec les logs serveur produits par
 * `apps/api/app/core/middleware.py:RequestIdMiddleware`.
 *
 * Si la requête entrante porte déjà un header (cas d'un retry après
 * refresh-token par exemple), on le préserve pour garder la trace
 * homogène d'un même bouton cliqué.
 */
class RequestIdInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val req = chain.request()
        val existing = req.header(HEADER)
        val withId = if (existing.isNullOrBlank()) {
            req.newBuilder().addHeader(HEADER, newRequestId()).build()
        } else {
            req
        }
        return chain.proceed(withId)
    }

    private fun newRequestId(): String {
        val bytes = ByteArray(8).also { Random.nextBytes(it) }
        return bytes.joinToString("") { "%02x".format(Locale.ROOT, it) }
    }

    companion object {
        const val HEADER = "x-request-id"
    }
}
