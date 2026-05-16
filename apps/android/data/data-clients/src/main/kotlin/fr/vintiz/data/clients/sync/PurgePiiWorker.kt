package fr.vintiz.data.clients.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import fr.vintiz.core.database.dao.ClientDao
import timber.log.Timber

/**
 * Purge RGPD : supprime du cache local toute cliente qui n'a pas été
 * rafraîchie depuis 30 jours. Aligne sur docs/MIGRATION_ANDROID_NATIVE.md
 * §2.2 R8 (cache PII TTL 30 j obligatoire).
 *
 * Programmé en periodic 1×/jour par le WorkManager dans
 * `app/VintizApp.onCreate` (à câbler dans bloc suivant).
 */
@HiltWorker
class PurgePiiWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val dao: ClientDao,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val cutoff = System.currentTimeMillis() - TTL_MS
        val deleted = dao.purgeOlderThan(cutoff)
        Timber.i("RGPD purge — %d clientes supprimées du cache local", deleted)
        return Result.success()
    }

    companion object {
        const val UNIQUE_NAME = "purge_pii"
        private const val TTL_MS = 30L * 24 * 3600 * 1000 // 30 jours
    }
}
