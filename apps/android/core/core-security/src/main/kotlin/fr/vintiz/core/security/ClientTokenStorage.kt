package fr.vintiz.core.security

/**
 * Stockage chiffré du JWT client (B2C) issu du flow magic-link OTP.
 *
 * Volontairement séparé de [TokenStorage] (manager / cashier POS) pour
 * que les deux apps Android (`:app-pos` et `:app-client`) cohabitent
 * sans partager d'état d'authentification. Voir
 * `docs/PLAN_ANDROID_CLIENT_APP.md` §2.2.
 *
 * L'implémentation Android (`AndroidClientTokenStorage`) s'appuie sur
 * `EncryptedSharedPreferences` + Android Keystore, dans un fichier de
 * préférences distinct (`vintiz_client_secure_prefs`).
 */
interface ClientTokenStorage {
    fun getAccessToken(): String?
    fun saveAccessToken(token: String)
    fun clearAccessToken()

    fun getEmail(): String?
    fun saveEmail(email: String)

    fun getMembershipNumber(): String?
    fun saveMembershipNumber(number: String?)

    fun clearAll()
}
