package fr.vintiz.core.security

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

private const val FILE = "vintiz_client_secure_prefs"
private const val KEY_TOKEN = "client_access_token"
private const val KEY_EMAIL = "client_email"
private const val KEY_MEMBERSHIP = "client_membership_number"

/**
 * Implémentation Android de [ClientTokenStorage] basée sur
 * `EncryptedSharedPreferences` + Android Keystore (AES256-GCM/SIV).
 *
 * Fichier de prefs distinct (`vintiz_client_secure_prefs`) — aucun
 * partage avec `AndroidTokenStorage` (POS). Permet d'installer les deux
 * apps `fr.vintiz.pos` et `fr.vintiz.client` sur le même device sans
 * collision.
 */
class AndroidClientTokenStorage(context: Context) : ClientTokenStorage {

    private val prefs by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        EncryptedSharedPreferences.create(
            context,
            FILE,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    override fun getAccessToken(): String? = prefs.getString(KEY_TOKEN, null)
    override fun saveAccessToken(token: String) {
        prefs.edit().putString(KEY_TOKEN, token).apply()
    }
    override fun clearAccessToken() {
        prefs.edit().remove(KEY_TOKEN).apply()
    }

    override fun getEmail(): String? = prefs.getString(KEY_EMAIL, null)
    override fun saveEmail(email: String) {
        prefs.edit().putString(KEY_EMAIL, email).apply()
    }

    override fun getMembershipNumber(): String? = prefs.getString(KEY_MEMBERSHIP, null)
    override fun saveMembershipNumber(number: String?) {
        prefs.edit().apply {
            if (number == null) remove(KEY_MEMBERSHIP) else putString(KEY_MEMBERSHIP, number)
            apply()
        }
    }

    override fun clearAll() {
        prefs.edit().clear().apply()
    }
}

/**
 * Pont vers [TokenStorage] pour pouvoir réutiliser `HttpClientFactory`
 * (qui type strictement `TokenStorage`) sans toucher au cœur réseau.
 * Les méthodes cashier sont no-op côté client.
 */
class ClientTokenStorageAdapter(
    private val delegate: ClientTokenStorage,
) : TokenStorage {
    override fun getAccessToken(): String? = delegate.getAccessToken()
    override fun saveAccessToken(token: String) = delegate.saveAccessToken(token)
    override fun clearAccessToken() = delegate.clearAccessToken()

    override fun getCashierId(): String? = null
    override fun saveCashierId(cashierId: String) {}
    override fun clearCashierId() {}

    override fun clearAll() = delegate.clearAll()
}
