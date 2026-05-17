package fr.vintiz.data.clients.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.datastore.AppPreferences
import fr.vintiz.data.clients.ClientsRepository
import kotlinx.coroutines.flow.first
import timber.log.Timber

/**
 * Sync best-effort des clientes — peuple le cache Room pour les
 * lookups offline POS (NFC, identify). Le critère "récent" est laissé
 * au serveur ; côté client on rafraîchit toutes les 6 h.
 *
 * V1 : on appelle `identify("")` qui retourne une page récente.
 * V2 : ajouter `?updated_since=<epoch>` côté backend pour réduire la
 * bande passante (TODO côté equipe API).
 */
@HiltWorker
class SyncClientsWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val repo: ClientsRepository,
    private val prefs: AppPreferences,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val lastSync = prefs.lastClientsSync.first()
        Timber.d("SyncClients — lastSync=%d", lastSync)
        return when (val r = repo.identify("")) {
            is VintizResult.Success -> {
                prefs.setLastClientsSync(System.currentTimeMillis() / 1000)
                Result.success()
            }
            is VintizResult.Failure -> r.error.mapWorkerResult("SyncClients")
        }
    }

    companion object {
        const val UNIQUE_NAME = "sync_clients"
    }
}

private fun VintizError.mapWorkerResult(tag: String): androidx.work.ListenableWorker.Result {
    return when (this) {
        is VintizError.Unauthorized -> {
            Timber.i("%s : 401/403, attendre login", tag)
            androidx.work.ListenableWorker.Result.success()
        }
        is VintizError.Http -> when (code) {
            401, 403 -> androidx.work.ListenableWorker.Result.success()
            in 500..599, 429 -> androidx.work.ListenableWorker.Result.retry()
            else -> androidx.work.ListenableWorker.Result.failure()
        }
        is VintizError.Network, is VintizError.RateLimit ->
            androidx.work.ListenableWorker.Result.retry()
        else -> androidx.work.ListenableWorker.Result.failure()
    }
}
