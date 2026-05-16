package fr.vintiz.data.clients.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
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
        return when (repo.identify("")) {
            is VintizResult.Success -> {
                prefs.setLastClientsSync(System.currentTimeMillis() / 1000)
                Result.success()
            }
            is VintizResult.Failure -> Result.retry()
        }
    }

    companion object {
        const val UNIQUE_NAME = "sync_clients"
    }
}
