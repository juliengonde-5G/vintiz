package fr.vintiz.pos.kiosk

import android.app.Activity
import android.content.Context
import timber.log.Timber

/**
 * Active le Lock Task Mode (Kiosk Mode) sur la tablette caisse —
 * verrouille l'utilisateur sur l'app Vintiz, empêche d'ouvrir
 * d'autres applis. Nécessite que l'application soit déclarée comme
 * "Device Owner" via DPC (Headwind / ScaleFusion / Miradore) ou un
 * Provisioning ADB :
 *
 *   adb shell dpm set-device-owner fr.vintiz.pos/.kiosk.VintizDeviceAdmin
 *
 * Si l'app n'est pas device-owner, [enable] silently no-op + warning
 * Timber. C'est documenté côté ops dans docs §4.3 — l'enrôlement MDM
 * est une opération humaine.
 */
class KioskManager(private val context: Context) {

    fun isLockTaskPermitted(): Boolean {
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as? android.app.admin.DevicePolicyManager
        return dpm?.isLockTaskPermitted(context.packageName) == true
    }

    /**
     * À appeler depuis l'Activity au onResume du POS (et seulement du
     * POS — on n'enferme pas l'utilisateur sur les écrans admin).
     */
    fun enable(activity: Activity) {
        if (!isLockTaskPermitted()) {
            Timber.w("Kiosk mode non autorisé — device-owner manquant")
            return
        }
        runCatching { activity.startLockTask() }
            .onFailure { Timber.w(it, "startLockTask échoué") }
    }

    fun disable(activity: Activity) {
        runCatching { activity.stopLockTask() }
            .onFailure { Timber.w(it, "stopLockTask échoué") }
    }
}
