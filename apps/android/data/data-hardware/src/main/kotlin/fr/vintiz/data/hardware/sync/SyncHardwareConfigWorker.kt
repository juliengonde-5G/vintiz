package fr.vintiz.data.hardware.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import fr.vintiz.core.common.VintizError
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
        return when (val r = repo.syncFromApi()) {
            is VintizResult.Success -> Result.success()
            is VintizResult.Failure -> r.error.toWorkerResult("SyncHardwareConfig")
        }
    }

    companion object {
        const val UNIQUE_NAME = "sync_hardware_config"
    }
}

/**
 * Mapping centralisé Failure → Result WorkManager pour éviter le retry
 * en boucle quand l'erreur n'est pas transitoire. Dupliqué dans les
 * autres workers (data-clients, data-inventory) car core-common est en
 * kotlin-jvm pur et ne peut pas dépendre de androidx.work.
 */
internal fun VintizError.toWorkerResult(tag: String): androidx.work.ListenableWorker.Result {
    return when (this) {
        is VintizError.Unauthorized -> {
            Timber.i("%s : 401/403, attendre login utilisateur", tag)
            androidx.work.ListenableWorker.Result.success()
        }
        is VintizError.Http -> when (code) {
            401, 403 -> {
                Timber.i("%s : HTTP %d, attendre login", tag, code)
                androidx.work.ListenableWorker.Result.success()
            }
            in 500..599, 429 -> {
                Timber.w("%s : HTTP %d transitoire, retry", tag, code)
                androidx.work.ListenableWorker.Result.retry()
            }
            else -> {
                Timber.w("%s : HTTP %d permanent, failure", tag, code)
                androidx.work.ListenableWorker.Result.failure()
            }
        }
        is VintizError.Network, is VintizError.RateLimit -> {
            Timber.i("%s : %s, retry", tag, message)
            androidx.work.ListenableWorker.Result.retry()
        }
        else -> {
            Timber.w("%s : %s, failure", tag, message)
            androidx.work.ListenableWorker.Result.failure()
        }
    }
}
