package fr.vintiz.pos.update

import android.app.Activity
import android.content.Context
import com.google.android.play.core.appupdate.AppUpdateManagerFactory
import com.google.android.play.core.install.model.AppUpdateType
import com.google.android.play.core.install.model.UpdateAvailability
import timber.log.Timber

/**
 * Wrapper Play Core In-App Update (cf. docs §3.9 sprint 12). Forcera
 * un update IMMEDIATE quand le backend remontera une version critique
 * (NF525 / faille sécurité). Sinon laisse Play Store gérer.
 *
 * Sur APK side-loadé (hors Play Store), `appUpdateInfo` retourne
 * `UpdateAvailability.UPDATE_NOT_AVAILABLE` — le wrapper ne fait rien
 * et n'erre pas. Pas de polyfill custom.
 */
class InAppUpdateManager(context: Context) {

    private val manager = AppUpdateManagerFactory.create(context)

    /**
     * À appeler dans `MainActivity.onResume`. Lance le flow immédiat
     * de mise à jour si une update est disponible et autorisée
     * (IMMEDIATE pour les release critiques, FLEXIBLE pour les
     * mineures — ici on prend IMMEDIATE par défaut, plus stricte).
     */
    fun checkAndPrompt(activity: Activity, requestCode: Int = REQUEST_CODE) {
        manager.appUpdateInfo
            .addOnSuccessListener { info ->
                val avail = info.updateAvailability()
                if (avail == UpdateAvailability.UPDATE_AVAILABLE &&
                    info.isUpdateTypeAllowed(AppUpdateType.IMMEDIATE)
                ) {
                    runCatching {
                        manager.startUpdateFlowForResult(
                            info, AppUpdateType.IMMEDIATE, activity, requestCode,
                        )
                    }.onFailure { Timber.w(it, "startUpdateFlow échoué") }
                }
            }
            .addOnFailureListener { Timber.d(it, "InAppUpdate non disponible (sideload ?)") }
    }

    companion object {
        const val REQUEST_CODE = 9001
    }
}
