package fr.vintiz.core.network

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import fr.vintiz.core.network.interceptors.AuthInterceptor
import fr.vintiz.core.network.interceptors.ClientIdInterceptor
import fr.vintiz.core.network.interceptors.RateLimitInterceptor
import fr.vintiz.core.network.interceptors.RefreshTokenAuthenticator
import fr.vintiz.core.network.interceptors.RequestIdInterceptor
import fr.vintiz.core.security.TokenStorage
import okhttp3.CertificatePinner
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Assemble la chaîne OkHttp + Retrofit utilisée par toutes les `data-*`
 * layers. Ordre des interceptors (docs §3.3) :
 *
 *   1. ClientId  — `X-Client: vintiz-android/X.Y.Z`
 *   2. RequestId — propage / génère `x-request-id`
 *   3. Auth      — `Authorization: Bearer <jwt>`
 *   4. RateLimit — gère 429 + Retry-After
 *   5. Logging   — debug only, redact Authorization
 *
 * `RefreshTokenAuthenticator` est attaché en dehors de la chaîne et
 * n'est invoqué que sur 401.
 *
 * Cert-pinning : en prod uniquement, on pin le SPKI d'`api.vintiz.fr`
 * (rotation 1×/an documentée). En dev, [pinning] reste vide pour ne
 * pas casser MockWebServer ni les certificats développeur.
 */
class HttpClientFactory(
    private val tokenStorage: TokenStorage,
    private val baseUrl: String,
    private val clientId: String,
    private val debug: Boolean,
    private val refreshToken: suspend (String) -> String?,
    private val runBlocking: (suspend () -> String?) -> String?,
    private val pinning: List<CertPin> = emptyList(),
) {

    /**
     * Pin SPKI au format OkHttp : `sha256/...=`. À renseigner via
     * `BuildConfig.API_PIN_SHA256` côté flavor prod.
     */
    data class CertPin(val hostname: String, val sha256: String)

    val moshi: Moshi by lazy {
        Moshi.Builder()
            .add(KotlinJsonAdapterFactory())
            .build()
    }

    val okHttpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .addInterceptor(ClientIdInterceptor(clientId))
            .addInterceptor(RequestIdInterceptor())
            .addInterceptor(AuthInterceptor(tokenStorage))
            .addInterceptor(RateLimitInterceptor())
            .apply {
                if (debug) {
                    val logging = HttpLoggingInterceptor()
                    logging.level = HttpLoggingInterceptor.Level.BASIC
                    logging.redactHeader("Authorization")
                    logging.redactHeader("Cookie")
                    addInterceptor(logging)
                }
                if (pinning.isNotEmpty()) {
                    val builder = CertificatePinner.Builder()
                    pinning.forEach { builder.add(it.hostname, it.sha256) }
                    certificatePinner(builder.build())
                }
            }
            .authenticator(
                RefreshTokenAuthenticator(
                    tokenStorage = tokenStorage,
                    refresh = refreshToken,
                    runBlocking = runBlocking,
                )
            )
            .build()
    }

    val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
    }
}
