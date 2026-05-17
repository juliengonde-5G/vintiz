package fr.vintiz.pos

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import fr.vintiz.pos.work.VintizWorkScheduler
import javax.inject.Inject
import timber.log.Timber

@HiltAndroidApp
class VintizApp : Application(), Configuration.Provider {

    @Inject lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }
        createNotificationChannel()
        VintizWorkScheduler.schedule(this)
    }

    /**
     * Sans cette déclaration, les notifications FCM postées par
     * VintizFcmService sont silencieusement ignorées sur Android 8+.
     * minSdk = 26 donc la branche pré-Oreo n'existe pas.
     */
    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Vintiz — alertes manager",
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Notifications transactions, dépôts, stock."
        }
        val mgr = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        mgr.createNotificationChannel(channel)
    }

    companion object {
        const val CHANNEL_ID = "vintiz_default"
    }
}
