package fr.vintiz.hardware.sumup.sdk

import fr.vintiz.core.common.Money
import fr.vintiz.hardware.api.PaymentOutcome
import fr.vintiz.hardware.api.PaymentTerminalService
import fr.vintiz.hardware.api.TerminalStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import timber.log.Timber

/**
 * Squelette de l'implémentation SumUp Android SDK (BT direct, latence
 * 4-6 s vs 8-12 s REST polling — cf. docs/MIGRATION_ANDROID_NATIVE.md
 * §2.1 O3).
 *
 * Pour activer cette implémentation côté Mac dev :
 *
 * 1. Décommenter dans `build.gradle.kts` :
 *    implementation("com.sumup:merchant-sdk:5.+")
 *
 * 2. Récupérer Affiliate Key + App ID Android depuis
 *    https://developer.sumup.com/ (compte Vintiz SAS) — distinct du
 *    web. Stocker dans 1Password "Vintiz / SumUp Android" + le poser
 *    en BuildConfig.SUMUP_AFFILIATE_KEY côté flavor prod.
 *
 * 3. Brancher [initialize] depuis `VintizApp.onCreate` avec :
 *    SumUpAPI.openLoginActivity(activity, REQUEST_LOGIN, params)
 *    SumUpAPI.openCheckoutActivity(activity, REQUEST_CHECKOUT, request)
 *
 * 4. Toggle automatique via [AppPreferences.paymentBackend] = SumUpSdk
 *    quand le pairing BT est validé (test au [SumUpAPI.isLoggedIn]).
 *
 * En attendant, cette impl retourne `PaymentOutcome.Failed` avec un
 * message explicite pour que la UI bascule sur `SumUpRestTerminal`
 * (le toggle est piloté par AppPreferences.paymentBackend).
 */
class SumUpSdkTerminal : PaymentTerminalService {

    private val _status = MutableStateFlow(TerminalStatus.Unknown)
    override val status: StateFlow<TerminalStatus> = _status.asStateFlow()

    /**
     * Initialise le SDK SumUp. À appeler depuis VintizApp.onCreate
     * une fois la dependency décommentée — pour l'instant, no-op +
     * warning Timber.
     */
    fun initialize(affiliateKey: String) {
        Timber.w(
            "SumUpSdkTerminal.initialize appelé mais le SDK n'est pas activé. " +
                "Voir docs/ANDROID_PROD_OPS.md §1 pour la procédure d'activation."
        )
        _status.value = TerminalStatus.Offline
    }

    override suspend fun pay(
        amount: Money,
        foreignTxId: String,
        description: String,
    ): PaymentOutcome {
        Timber.w("SumUpSdkTerminal.pay appelé en mode stub")
        return PaymentOutcome.Failed(
            "SDK SumUp BT non actif — bascule recommandée sur le mode REST " +
                "(Settings → Paiement → REST polling)."
        )
    }

    override suspend fun cancel(checkoutId: String): Boolean {
        Timber.d("SumUpSdkTerminal.cancel stub — ignoré (no-op)")
        return false
    }
}
