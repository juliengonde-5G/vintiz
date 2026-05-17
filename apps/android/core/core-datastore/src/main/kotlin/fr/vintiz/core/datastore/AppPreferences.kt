package fr.vintiz.core.datastore

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "vintiz_prefs")

/**
 * Préférences non sensibles : sélection d'environnement
 * (alimente core-network), choix du backend imprimante / TPE (USB vs
 * réseau, SDK vs REST), horodatages de dernière sync.
 *
 * Le JWT et les secrets restent dans [fr.vintiz.core.security.TokenStorage]
 * (EncryptedSharedPreferences).
 */
class AppPreferences(private val context: Context) {

    val environment: Flow<Environment> = context.dataStore.data
        .map { prefs -> Environment.fromKey(prefs[KEY_ENV]) }

    suspend fun setEnvironment(env: Environment) {
        context.dataStore.edit { it[KEY_ENV] = env.key }
    }

    val printerBackend: Flow<PrinterBackend> = context.dataStore.data
        .map { prefs -> PrinterBackend.fromKey(prefs[KEY_PRINTER]) }

    suspend fun setPrinterBackend(backend: PrinterBackend) {
        context.dataStore.edit { it[KEY_PRINTER] = backend.key }
    }

    val paymentBackend: Flow<PaymentBackend> = context.dataStore.data
        .map { prefs -> PaymentBackend.fromKey(prefs[KEY_PAYMENT]) }

    suspend fun setPaymentBackend(backend: PaymentBackend) {
        context.dataStore.edit { it[KEY_PAYMENT] = backend.key }
    }

    val cameraScannerEnabled: Flow<Boolean> = context.dataStore.data
        .map { prefs -> prefs[KEY_CAMERA_SCAN] ?: false }

    suspend fun setCameraScannerEnabled(enabled: Boolean) {
        context.dataStore.edit { it[KEY_CAMERA_SCAN] = enabled }
    }

    val lastProductsSync: Flow<Long> = context.dataStore.data
        .map { prefs -> prefs[KEY_LAST_PRODUCTS_SYNC] ?: 0L }

    suspend fun setLastProductsSync(epochSeconds: Long) {
        context.dataStore.edit { it[KEY_LAST_PRODUCTS_SYNC] = epochSeconds }
    }

    val lastClientsSync: Flow<Long> = context.dataStore.data
        .map { prefs -> prefs[KEY_LAST_CLIENTS_SYNC] ?: 0L }

    suspend fun setLastClientsSync(epochSeconds: Long) {
        context.dataStore.edit { it[KEY_LAST_CLIENTS_SYNC] = epochSeconds }
    }

    val onboardingCompleted: Flow<Boolean> = context.dataStore.data
        .map { prefs -> prefs[KEY_ONBOARDING_DONE] ?: false }

    suspend fun setOnboardingCompleted(done: Boolean) {
        context.dataStore.edit { it[KEY_ONBOARDING_DONE] = done }
    }

    private companion object {
        val KEY_ENV: Preferences.Key<String> = stringPreferencesKey("env")
        val KEY_PRINTER: Preferences.Key<String> = stringPreferencesKey("printer_backend")
        val KEY_PAYMENT: Preferences.Key<String> = stringPreferencesKey("payment_backend")
        val KEY_CAMERA_SCAN: Preferences.Key<Boolean> = booleanPreferencesKey("camera_scan_enabled")
        val KEY_LAST_PRODUCTS_SYNC: Preferences.Key<Long> = longPreferencesKey("last_products_sync")
        val KEY_LAST_CLIENTS_SYNC: Preferences.Key<Long> = longPreferencesKey("last_clients_sync")
        val KEY_ONBOARDING_DONE: Preferences.Key<Boolean> = booleanPreferencesKey("onboarding_done")
    }
}

enum class Environment(val key: String, val baseUrl: String) {
    // Le flavor dev pointe sur prod tant que api.dev.vintiz.fr n'est
    // pas provisionné (cf. app/build.gradle.kts:30). À repointer ici si
    // un env dev dédié est déployé.
    Dev("dev", "https://api.vintiz.fr/"),
    Prod("prod", "https://api.vintiz.fr/");

    companion object {
        fun fromKey(key: String?): Environment = entries.firstOrNull { it.key == key } ?: Dev
    }
}

enum class PrinterBackend(val key: String) {
    UsbDirect("usb"),
    NetworkTcp("network");

    companion object {
        fun fromKey(key: String?): PrinterBackend =
            entries.firstOrNull { it.key == key } ?: NetworkTcp
    }
}

enum class PaymentBackend(val key: String) {
    SumUpSdk("sumup_sdk"),
    SumUpRest("sumup_rest");

    companion object {
        fun fromKey(key: String?): PaymentBackend =
            entries.firstOrNull { it.key == key } ?: SumUpSdk
    }
}
