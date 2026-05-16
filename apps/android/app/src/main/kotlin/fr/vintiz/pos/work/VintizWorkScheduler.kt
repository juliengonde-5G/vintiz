package fr.vintiz.pos.work

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import fr.vintiz.data.clients.sync.PurgePiiWorker
import fr.vintiz.data.clients.sync.SyncClientsWorker
import fr.vintiz.data.hardware.sync.SyncHardwareConfigWorker
import fr.vintiz.data.inventory.sync.SyncProductsWorker
import fr.vintiz.data.pos.sync.DrainTransactionsWorker
import java.util.concurrent.TimeUnit

/**
 * Programme les workers récurrents au boot de l'app — voir
 * docs/MIGRATION_ANDROID_NATIVE.md §3.4 tableau Workers.
 *
 * Trigger              | Période   | Réseau    | Backoff
 * DrainTransactions    | 15 min    | CONNECTED | LINEAR 30 s
 * SyncProducts         | 1 h       | CONNECTED | EXP 1-60 min (défaut)
 * SyncClients          | 6 h       | CONNECTED | EXP
 * PurgePii (RGPD)      | 1 jour    | -         | -
 * SyncHardwareConfig   | OneTime   | CONNECTED | EXP — au boot
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
                .setBackoffCriteria(BackoffPolicy.LINEAR, 30, TimeUnit.SECONDS)
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
            SyncClientsWorker.UNIQUE_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<SyncClientsWorker>(6, TimeUnit.HOURS)
                .setConstraints(connected)
                .build(),
        )

        wm.enqueueUniquePeriodicWork(
            PurgePiiWorker.UNIQUE_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<PurgePiiWorker>(1, TimeUnit.DAYS).build(),
        )

        wm.enqueueUniqueWork(
            SyncHardwareConfigWorker.UNIQUE_NAME,
            ExistingWorkPolicy.KEEP,
            OneTimeWorkRequestBuilder<SyncHardwareConfigWorker>()
                .setConstraints(connected)
                .build(),
        )
    }
}
