package fr.vintiz.core.common

/**
 * Wrapper Result discriminé pour les couches data/domain de Vintiz.
 *
 * Distinct du `kotlin.Result` standard pour exposer un type d'erreur
 * domaine au lieu d'un `Throwable` générique. Les couches UI matchent
 * `is Success` / `is Failure` plutôt que d'attraper des exceptions.
 */
sealed class VintizResult<out T> {
    data class Success<T>(val value: T) : VintizResult<T>()
    data class Failure(val error: VintizError) : VintizResult<Nothing>()

    inline fun <R> map(transform: (T) -> R): VintizResult<R> = when (this) {
        is Success -> Success(transform(value))
        is Failure -> this
    }

    inline fun <R> fold(
        onSuccess: (T) -> R,
        onFailure: (VintizError) -> R,
    ): R = when (this) {
        is Success -> onSuccess(value)
        is Failure -> onFailure(error)
    }
}

/**
 * Erreurs domaine consommées par la couche UI. Toute exception réseau /
 * I/O / parsing doit être convertie en [VintizError] dans les
 * repositories — la couche présentation n'attrape jamais
 * `IOException` / `HttpException` directement.
 */
sealed class VintizError(open val message: String) {
    data object Network : VintizError("Connexion indisponible")
    data class Http(val code: Int, override val message: String) : VintizError(message)
    data object Unauthorized : VintizError("Session expirée")
    data class Validation(val field: String, override val message: String) : VintizError(message)
    data object Idempotent : VintizError("Opération déjà appliquée")
    data class RateLimit(val retryAfterSeconds: Int) :
        VintizError("Trop de tentatives, réessayer dans ${retryAfterSeconds}s")
    data class Unknown(override val message: String, val cause: Throwable? = null) :
        VintizError(message)

    companion object {
        /**
         * Construit un [Http] dont la `message` n'est jamais vide.
         * Retrofit/OkHttp renvoient souvent `HttpException.message()`
         * en chaîne vide sur 4xx — l'UI affichait alors "⚠ " sans
         * texte. Cette factory garantit un fallback lisible.
         */
        fun http(code: Int, raw: String?): Http {
            val safe = raw?.takeIf { it.isNotBlank() } ?: defaultHttpMessage(code)
            return Http(code, safe)
        }
    }
}

/**
 * Texte par défaut pour les codes HTTP fréquents, utilisé quand le
 * serveur renvoie une reason phrase vide.
 */
internal fun defaultHttpMessage(code: Int): String = when (code) {
    400 -> "HTTP 400 — requête invalide"
    401 -> "HTTP 401 — non authentifié"
    403 -> "HTTP 403 — accès refusé"
    404 -> "HTTP 404 — route inconnue"
    409 -> "HTTP 409 — conflit (doublon ?)"
    422 -> "HTTP 422 — corps de requête invalide"
    429 -> "HTTP 429 — trop de tentatives"
    in 500..599 -> "HTTP $code — erreur serveur"
    else -> "HTTP $code"
}
