package fr.vintiz.data.hardware.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.hardware.HardwareRepository
import timber.log.Timber

/**
 * Sync OneTime au boot de l'app : récupère la config matériel
 * persistée côté serveur (`data/hardware.json`) et la cache localement
 * Room. Si l'API est KO au démarrage, la tablette caisse continue à
 * imprimer avec le dernier cache valide.
 *
 * Programmé en OneTimeWorkRequest par VintizWorkScheduler.scheduleBoot()
 * — pas en periodic car le manager appelle déjà la sync manuellement
 * depuis Settings > Matériel quand il modifie quelque chose.
 */
@HiltWorker
class SyncHardwareConfigWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val repo: HardwareRepository,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        Timber.d("SyncHardwareConfig — boot")
        return when (repo.syncFromApi()) {
            is VintizResult.Success -> Result.success()
            is VintizResult.Failure -> Result.retry()
        }
    }

    companion object {
        const val UNIQUE_NAME = "sync_hardware_config"
    }
}
