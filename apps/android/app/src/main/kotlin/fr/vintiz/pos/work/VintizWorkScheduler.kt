package fr.vintiz.pos.work

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import fr.vintiz.data.clients.sync.PurgePiiWorker
import fr.vintiz.data.inventory.sync.SyncProductsWorker
import fr.vintiz.data.pos.sync.DrainTransactionsWorker
import java.util.concurrent.TimeUnit

/**
 * Programme les workers récurrents au boot de l'app — voir
 * docs/MIGRATION_ANDROID_NATIVE.md §3.4 tableau Workers.
 *
 * - DrainTransactions : 15 min, NetworkType.CONNECTED, backoff linéaire 30 s
 * - SyncProducts : 1 h, NetworkType.CONNECTED
 * - PurgePii : 1×/jour, sans contrainte réseau
 */
object VintizWorkScheduler {

    fun schedule(context: Context) {
        val wm = WorkManager.getInstance(context)

        val connected = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        wm.enqueueUniquePeriodicWork(
            DrainTransactionsWorker.UNIQUE_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<DrainTransactionsWorker>(15, TimeUnit.MINUTES)
                .setConstraints(connected)
                .build(),
        )

        wm.enqueueUniquePeriodicWork(
            SyncProductsWorker.UNIQUE_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<SyncProductsWorker>(1, TimeUnit.HOURS)
                .setConstraints(connected)
                .build(),
        )

        wm.enqueueUniquePeriodicWork(
            PurgePiiWorker.UNIQUE_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<PurgePiiWorker>(1, TimeUnit.DAYS).build(),
        )
    }
}
