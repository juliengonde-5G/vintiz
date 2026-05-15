package fr.vintiz.core.security

/**
 * Stockage chiffré du JWT manager + de l'identité caissière courante.
 *
 * Voir docs/MIGRATION_ANDROID_NATIVE.md §2.1 (R8) — le JWT ne doit
 * **jamais** transiter par `SharedPreferences` en clair ni par un
 * fichier non chiffré. L'implémentation Android (`AndroidTokenStorage`)
 * s'appuie sur `EncryptedSharedPreferences` + Android Keystore.
 */
interface TokenStorage {
    fun getAccessToken(): String?
    fun saveAccessToken(token: String)
    fun clearAccessToken()

    fun getCashierId(): String?
    fun saveCashierId(cashierId: String)
    fun clearCashierId()

    fun clearAll()
}
