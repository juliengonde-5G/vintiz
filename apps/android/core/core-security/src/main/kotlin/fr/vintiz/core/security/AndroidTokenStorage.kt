package fr.vintiz.core.security

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

private const val FILE = "vintiz_secure_prefs"
private const val KEY_TOKEN = "access_token"
private const val KEY_CASHIER = "cashier_id"

class AndroidTokenStorage(context: Context) : TokenStorage {

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

    override fun getCashierId(): String? = prefs.getString(KEY_CASHIER, null)
    override fun saveCashierId(cashierId: String) {
        prefs.edit().putString(KEY_CASHIER, cashierId).apply()
    }
    override fun clearCashierId() {
        prefs.edit().remove(KEY_CASHIER).apply()
    }

    override fun clearAll() {
        prefs.edit().clear().apply()
    }
}
